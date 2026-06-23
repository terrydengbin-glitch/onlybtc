from __future__ import annotations

import json
from typing import Any, Literal

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.agent_runtime import AgentRuntimeAdapter, RuntimeResult
from onlybtc.p4.prompts import build_cross_exam_revision_prompt
from onlybtc.p4.schemas import CrossExamRevision

RuntimeMode = Literal["mock", "llm"]


def run_cross_exam_revisions(
    debate_id: str,
    runtime_mode: RuntimeMode = "mock",
    max_rounds: int = 1,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        votes = _load_votes(session, debate_id)
        vote_by_agent = {vote.model_name: vote for vote in votes}
        challenges = _load_challenges(session, debate_id)
        if not challenges:
            _persist_round(session, debate_id, [], [], runtime_mode, max_rounds)
            return {
                "status": "completed",
                "debate_id": debate_id,
                "runtime_mode": runtime_mode,
                "revision_count": 0,
                "unresolved_challenge_count": 0,
                "unresolved_high_challenge_count": 0,
                "revisions": [],
                "runtime_results": [],
            }
        revisions, runtime_results = _build_revisions(
            challenges=challenges,
            vote_by_agent=vote_by_agent,
            runtime_mode=runtime_mode,
        )
        for revision in revisions:
            session.add(
                schema.LlmRevision(
                    debate_id=debate_id,
                    challenge_id=revision.challenge_id,
                    responding_agent=revision.responding_agent,
                    changed=revision.changed,
                    previous_vote=revision.previous_vote,
                    revised_vote=revision.revised_vote,
                    previous_confidence=revision.previous_confidence,
                    revised_confidence=revision.revised_confidence,
                    payload=revision.model_dump(mode="json"),
                )
            )
            vote = vote_by_agent.get(revision.responding_agent)
            if vote is not None and revision.changed:
                vote.vote = revision.revised_vote
                vote.confidence = revision.revised_confidence
                vote.changed = True
                vote.evidence_ids = sorted(set([*vote.evidence_ids, *revision.evidence_ids]))
        _persist_round(session, debate_id, revisions, runtime_results, runtime_mode, max_rounds)
        coverage = _coverage(challenges, revisions)

    return {
        "status": "completed",
        "debate_id": debate_id,
        "runtime_mode": runtime_mode,
        "revision_count": len(revisions),
        **coverage,
        "revisions": [revision.model_dump(mode="json") for revision in revisions],
        "runtime_results": [result.model_dump(mode="json") for result in runtime_results],
    }


def _build_revisions(
    challenges: list[schema.LlmChallenge],
    vote_by_agent: dict[str, schema.LlmModelVote],
    runtime_mode: RuntimeMode,
) -> tuple[list[CrossExamRevision], list[RuntimeResult]]:
    adapter = AgentRuntimeAdapter()
    revisions: list[CrossExamRevision] = []
    runtime_results: list[RuntimeResult] = []
    for challenge in challenges:
        parsed = _parse_challenge(challenge)
        vote = vote_by_agent.get(challenge.target)
        if vote is None:
            continue
        fallback = _fallback_revision(parsed, vote)
        if runtime_mode == "mock":
            revisions.append(fallback)
            continue
        revision_prompt_json = json.dumps(
            _revision_prompt_payload(parsed, vote),
            ensure_ascii=False,
            indent=2,
        )
        prompt = build_cross_exam_revision_prompt(
            agent_id=vote.model_name,
            evidence_ids=fallback.evidence_ids,
        ).model_copy(
            update={
                "user_prompt": (
                    "Produce one CrossExamRevision JSON object using only the supplied JSON. "
                    "Preserve challenge_id, responding_agent and evidence_ids unless the "
                    "challenge requires a stricter evidence-backed correction.\n\n"
                    f"{revision_prompt_json}"
                )
            }
        )
        result = adapter.run_llm_or_mock(
            prompt,
            CrossExamRevision,
            fallback_output=fallback.model_dump(mode="json"),
        )
        runtime_results.append(result)
        if result.structured_output:
            revisions.append(CrossExamRevision.model_validate(result.structured_output))
        else:
            revisions.append(fallback)
    return revisions, runtime_results


def _fallback_revision(parsed: dict[str, Any], vote: schema.LlmModelVote) -> CrossExamRevision:
    severity = str(parsed.get("severity") or "medium")
    challenge_type = str(parsed.get("challenge_type") or "missing_evidence")
    evidence_ids = _safe_evidence_ids(parsed.get("evidence_ids"), vote.evidence_ids)
    confidence_cut = 0.08 if severity in {"high", "critical"} else 0.03
    should_reduce = challenge_type in {"ignored_invalidation", "data_quality", "missing_evidence"}
    revised_confidence = (
        round(max(0.0, vote.confidence - confidence_cut), 4)
        if should_reduce
        else vote.confidence
    )
    changed = revised_confidence != vote.confidence
    return CrossExamRevision(
        challenge_id=str(parsed.get("challenge_id") or f"challenge-row-{vote.id}"),
        responding_agent=vote.model_name,  # type: ignore[arg-type]
        changed=changed,
        previous_vote=vote.vote,  # type: ignore[arg-type]
        revised_vote=vote.vote,  # type: ignore[arg-type]
        previous_confidence=vote.confidence,
        revised_confidence=revised_confidence,
        accepted_points=[
            f"Accepted challenge type={challenge_type}; confidence adjusted for audit gate."
        ]
        if changed
        else [],
        rejected_points=[]
        if changed
        else ["No vote change; original evidence still supports scoped conclusion."],
        reason=(
            "Revision reduced confidence because the challenge identified hard constraints, "
            "missing evidence, or data-quality uncertainty."
            if changed
            else "Revision keeps the original vote because cited evidence remains sufficient."
        ),
        evidence_ids=evidence_ids,
    )


def _coverage(
    challenges: list[schema.LlmChallenge],
    revisions: list[CrossExamRevision],
) -> dict[str, int | str]:
    revised_ids = {revision.challenge_id for revision in revisions}
    challenge_ids = {_parse_challenge(challenge).get("challenge_id") for challenge in challenges}
    unresolved = [
        challenge
        for challenge in challenges
        if _parse_challenge(challenge).get("challenge_id") not in revised_ids
    ]
    unresolved_high = [
        challenge for challenge in unresolved if challenge.severity in {"high", "critical"}
    ]
    integrity = "passed" if not unresolved_high else "failed"
    if unresolved and not unresolved_high:
        integrity = "partial"
    return {
        "revision_integrity": integrity,
        "challenge_count": len(challenge_ids),
        "unresolved_challenge_count": len(unresolved),
        "unresolved_high_challenge_count": len(unresolved_high),
    }


def _persist_round(
    session,
    debate_id: str,
    revisions: list[CrossExamRevision],
    runtime_results: list[RuntimeResult],
    runtime_mode: RuntimeMode,
    max_rounds: int,
) -> None:
    session.add(
        schema.LlmRound(
            debate_id=debate_id,
            round_number=3,
            round_type="cross_exam_revision",
            summary=str(
                {
                    "round_type": "cross_exam_revision",
                    "revision_count": len(revisions),
                    "max_rounds": max_rounds,
                    "runtime_mode": runtime_mode,
                    "revisions": [revision.model_dump(mode="json") for revision in revisions],
                    "runtime_results": [
                        result.model_dump(mode="json") for result in runtime_results
                    ],
                }
            ),
        )
    )


def _load_votes(session, debate_id: str) -> list[schema.LlmModelVote]:
    return session.scalars(
        select(schema.LlmModelVote)
        .where(schema.LlmModelVote.debate_id == debate_id)
        .order_by(schema.LlmModelVote.model_name)
    ).all()


def _load_challenges(session, debate_id: str) -> list[schema.LlmChallenge]:
    return session.scalars(
        select(schema.LlmChallenge)
        .where(schema.LlmChallenge.debate_id == debate_id)
        .order_by(schema.LlmChallenge.created_at)
    ).all()


def _parse_challenge(challenge: schema.LlmChallenge) -> dict[str, Any]:
    try:
        parsed = json.loads(challenge.issue)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _vote_payload(vote: schema.LlmModelVote) -> dict[str, Any]:
    return {
        "model_name": vote.model_name,
        "vote": vote.vote,
        "confidence": vote.confidence,
        "evidence_ids": vote.evidence_ids,
        "changed": vote.changed,
    }


def _revision_prompt_payload(
    parsed: dict[str, Any],
    vote: schema.LlmModelVote,
) -> dict[str, Any]:
    return {"challenge": parsed, "vote": _vote_payload(vote)}


def _safe_evidence_ids(*groups: Any) -> list[str]:
    evidence_ids: list[str] = []
    for group in groups:
        if isinstance(group, list):
            evidence_ids.extend(str(item) for item in group if item)
    return sorted(set(evidence_ids))[:20] or ["no-evidence-id-available"]
