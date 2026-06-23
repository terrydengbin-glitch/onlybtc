from __future__ import annotations

import json
import re
from statistics import mean
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.agent_runtime import AgentRuntimeAdapter, RuntimeResult
from onlybtc.p4.prompts import build_judge_system_prompt
from onlybtc.p4.rule_baseline import build_rule_baseline
from onlybtc.p4.schemas import JudgeSynthesis, KeyClaim
from onlybtc.p4.state_machine import run_state_machine

RuntimeMode = Literal["mock", "llm"]


def run_judge_synthesis(
    debate_id: str,
    pack_id: str | None = None,
    runtime_mode: RuntimeMode = "mock",
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    baseline = build_rule_baseline(pack_id=pack_id, db=db)
    state = run_state_machine(pack_id=pack_id, baseline=baseline, db=db)
    with db.session() as session:
        debate = _load_debate(session, debate_id)
        votes = _load_votes(session, debate_id)
        challenges = _load_challenges(session, debate_id)
        revisions = _load_revisions(session, debate_id)
        if not votes:
            raise RuntimeError(f"No analyst votes found for debate_id={debate_id}")
        fallback_synthesis = _build_synthesis(
            debate=debate,
            votes=votes,
            challenges=challenges,
            revisions=revisions,
            baseline=baseline,
            state=state,
        )
        synthesis, runtime_results = _run_judge_runtime(
            fallback_synthesis=fallback_synthesis,
            debate=debate,
            votes=votes,
            challenges=challenges,
            revisions=revisions,
            baseline=baseline,
            state=state,
            runtime_mode=runtime_mode,
        )
        session.add(
            schema.JudgeSynthesis(
                run_id=synthesis.controller_run_id,
                debate_id=debate_id,
                final_state=synthesis.trend_state,
                confidence=synthesis.confidence,
                confidence_discount=synthesis.confidence_discount,
                summary=_summary(synthesis),
                payload={
                    **synthesis.model_dump(mode="json"),
                    "revision_summary": _revision_summary(revisions),
                    "runtime_mode": runtime_mode,
                    "runtime_results": [
                        result.model_dump(mode="json") for result in runtime_results
                    ],
                },
            )
        )
        debate.final_state = synthesis.trend_state
        debate.publish_allowed = synthesis.publish_allowed
        debate.consensus_score = synthesis.confidence
        debate.disagreement_level = synthesis.disagreement_level
    return {
        "status": "completed",
        "runtime_mode": runtime_mode,
        "judge_synthesis": synthesis.model_dump(mode="json"),
        "runtime_results": [result.model_dump(mode="json") for result in runtime_results],
    }


def _run_judge_runtime(
    fallback_synthesis: JudgeSynthesis,
    debate: schema.LlmDebate,
    votes: list[schema.LlmModelVote],
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    baseline: dict[str, Any],
    state: dict[str, Any],
    runtime_mode: RuntimeMode,
) -> tuple[JudgeSynthesis, list[RuntimeResult]]:
    if runtime_mode == "mock":
        return fallback_synthesis, []
    payload = {
        "fallback_rule_synthesis": fallback_synthesis.model_dump(mode="json"),
        "debate": {
            "debate_id": debate.debate_id,
            "run_id": debate.run_id,
            "consensus_score": debate.consensus_score,
            "disagreement_level": debate.disagreement_level,
        },
        "votes": [_vote_payload(vote) for vote in votes],
        "challenges": [_challenge_payload(challenge) for challenge in challenges],
        "revisions": [_revision_payload(revision) for revision in revisions],
        "baseline": baseline,
        "state_machine": state,
    }
    prompt = build_judge_system_prompt().model_copy(
        update={
            "evidence_ids": _allowed_evidence_ids(payload, fallback_synthesis),
            "user_prompt": (
                "Produce one JudgeSynthesis JSON object using only the supplied JSON. "
                "Hard state-machine constraints and evidence_ids must be preserved. "
                "If uncertain, stay close to fallback_rule_synthesis and lower confidence.\n\n"
                f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
            ),
        }
    )
    adapter = AgentRuntimeAdapter()
    result = adapter.run_llm_or_mock(
        prompt,
        JudgeSynthesis,
        fallback_output=fallback_synthesis.model_dump(mode="json"),
    )
    if result.structured_output:
        return JudgeSynthesis.model_validate(result.structured_output), [result]
    return fallback_synthesis, [result]


def _allowed_evidence_ids(
    payload: dict[str, Any],
    fallback_synthesis: JudgeSynthesis,
) -> list[str]:
    ids = set(fallback_synthesis.evidence_ids)
    ids.update(_find_evidence_ids(payload))
    return sorted(ids)


def _find_evidence_ids(value: Any) -> list[str]:
    ids: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            ids.extend(_find_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.extend(_find_evidence_ids(item))
    elif isinstance(value, str):
        ids.extend(re.findall(r"ev-[A-Za-z0-9-]+", value))
    return ids


def _vote_payload(vote: schema.LlmModelVote) -> dict[str, Any]:
    return {
        "model_name": vote.model_name,
        "vote": vote.vote,
        "confidence": vote.confidence,
        "evidence_ids": vote.evidence_ids,
        "changed": vote.changed,
    }


def _challenge_payload(challenge: schema.LlmChallenge) -> dict[str, Any]:
    parsed = _parse_challenge(challenge) or {}
    return {
        "challenger": challenge.challenger,
        "target": challenge.target,
        "severity": challenge.severity,
        "issue": parsed,
    }


def _revision_payload(revision: schema.LlmRevision) -> dict[str, Any]:
    return dict(revision.payload or {})


def _load_debate(session, debate_id: str) -> schema.LlmDebate:
    debate = session.scalar(select(schema.LlmDebate).where(schema.LlmDebate.debate_id == debate_id))
    if debate is None:
        raise RuntimeError(f"LLM debate not found: {debate_id}")
    return debate


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


def _load_revisions(session, debate_id: str) -> list[schema.LlmRevision]:
    return session.scalars(
        select(schema.LlmRevision)
        .where(schema.LlmRevision.debate_id == debate_id)
        .order_by(schema.LlmRevision.created_at)
    ).all()


def _build_synthesis(
    debate: schema.LlmDebate,
    votes: list[schema.LlmModelVote],
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    baseline: dict[str, Any],
    state: dict[str, Any],
) -> JudgeSynthesis:
    accepted_claims = _accepted_claims(votes, baseline, state)
    rejected_claims = _rejected_claims(challenges, revisions, baseline, state)
    minority_objections = _minority_objections(challenges, revisions)
    confidence_discount = _judge_confidence_discount(
        baseline, state, challenges, votes, revisions
    )
    confidence = _judge_confidence(baseline, votes, confidence_discount)
    evidence_ids = _evidence_ids(accepted_claims, rejected_claims, minority_objections, state)
    return JudgeSynthesis(
        judge_synthesis_id=f"judge-{uuid4().hex[:12]}",
        debate_id=debate.debate_id,
        pack_id=str(baseline["pack_id"]),
        controller_run_id=str(baseline["controller_run_id"]),
        dominant_regime=_dominant_regime(baseline, state),
        trend_state=str(state["trend_state"]),
        risk_state=str(state["risk_state"]),
        consensus_level=_consensus_level(votes),
        disagreement_level=_disagreement_level(votes, challenges),
        accepted_claims=accepted_claims,
        rejected_claims=rejected_claims,
        minority_objections=minority_objections,
        confidence=confidence,
        confidence_discount=confidence_discount,
        blocked_by=list(state.get("blocked_by") or []),
        publish_allowed=bool(state.get("publish_allowed", False)),
        evidence_ids=evidence_ids,
        state_machine_constraints_applied=[
            str(item.get("constraint") or item.get("condition_id") or "unknown")
            for item in state.get("state_machine_constraints_applied", [])
        ],
    )


def _accepted_claims(
    votes: list[schema.LlmModelVote],
    baseline: dict[str, Any],
    state: dict[str, Any],
) -> list[KeyClaim]:
    claims = [
        KeyClaim(
            claim=(
                f"Rule baseline signal is {baseline['baseline_signal']} with "
                f"confidence={baseline['baseline_confidence']}."
            ),
            evidence_ids=_baseline_evidence_ids(baseline),
            direction=_direction_from_signal(str(baseline["baseline_signal"])),
            strength=float(baseline["baseline_confidence"]),
            uncertainty="rule baseline before judge synthesis",
        ),
        KeyClaim(
            claim=(
                f"State machine sets trend_state={state['trend_state']} and "
                f"risk_state={state['risk_state']}."
            ),
            evidence_ids=_state_evidence_ids(state) or _baseline_evidence_ids(baseline),
            direction="neutral",
            strength=0.8 if state.get("blocked_by") else 0.55,
            uncertainty="hard constraints apply before judge synthesis",
        ),
    ]
    for vote in votes:
        claims.append(
            KeyClaim(
                claim=(
                    f"{vote.model_name} analyst vote={vote.vote} "
                    f"with confidence={vote.confidence}."
                ),
                evidence_ids=_safe_evidence_ids(
                    vote.evidence_ids,
                    _baseline_evidence_ids(baseline),
                ),
                direction=_direction_from_signal(vote.vote),
                strength=float(vote.confidence),
                uncertainty="analyst independent review",
            )
        )
    return claims


def _rejected_claims(
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    baseline: dict[str, Any],
    state: dict[str, Any],
) -> list[KeyClaim]:
    claims: list[KeyClaim] = []
    if state.get("blocked_by"):
        claims.append(
            KeyClaim(
                claim=(
                    "Aggressive state transition or critical publish is rejected because "
                    f"blocked_by={', '.join(state['blocked_by'])}."
                ),
                evidence_ids=_state_evidence_ids(state) or _baseline_evidence_ids(baseline),
                direction="risk_off",
                strength=0.85,
                uncertainty="state machine hard block",
            )
        )
    for challenge in challenges:
        parsed = _parse_challenge(challenge)
        if not parsed:
            continue
        revision = _revision_for_challenge(revisions, str(parsed.get("challenge_id") or ""))
        if parsed.get("challenge_type") in {"evidence_conflict", "ignored_invalidation"}:
            claims.append(
                KeyClaim(
                    claim=(
                        "Rejected or constrained challenged claim after revision review: "
                        f"{parsed['claim_under_review']}"
                    ),
                    evidence_ids=_safe_evidence_ids(
                        (revision.payload or {}).get("evidence_ids") if revision else None,
                        parsed.get("evidence_ids"),
                        _baseline_evidence_ids(baseline),
                    ),
                    direction="unknown",
                    strength=0.6 if challenge.severity == "medium" else 0.8,
                    uncertainty="unresolved cross-examination challenge",
                )
            )
    return claims


def _minority_objections(
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
) -> list[KeyClaim]:
    objections: list[KeyClaim] = []
    for challenge in challenges:
        parsed = _parse_challenge(challenge)
        if not parsed:
            continue
        revision = _revision_for_challenge(revisions, str(parsed.get("challenge_id") or ""))
        revision_payload = revision.payload if revision else {}
        suffix = ""
        if revision_payload:
            suffix = (
                f" Revision changed={revision_payload.get('changed')} "
                f"revised_confidence={revision_payload.get('revised_confidence')}."
            )
        objections.append(
            KeyClaim(
                claim=str(parsed["claim_under_review"]) + suffix,
                evidence_ids=_safe_evidence_ids(
                    revision_payload.get("evidence_ids"), parsed.get("evidence_ids"), []
                ),
                direction="unknown",
                strength=0.55 if challenge.severity == "medium" else 0.75,
                uncertainty=f"cross-exam severity={challenge.severity}",
            )
        )
    return objections[:12]


def _judge_confidence_discount(
    baseline: dict[str, Any],
    state: dict[str, Any],
    challenges: list[schema.LlmChallenge],
    votes: list[schema.LlmModelVote],
    revisions: list[schema.LlmRevision],
) -> float:
    base_discount = float(baseline.get("confidence_discount") or 0)
    state_discount = 0.18 if state.get("blocked_by") else 0.0
    challenge_discount = min(0.22, len(challenges) * 0.025)
    vote_discount = 0.08 if _disagreement_level(votes, challenges) in {"medium", "high"} else 0.0
    revised_ids = {str((revision.payload or {}).get("challenge_id")) for revision in revisions}
    unresolved_high = [
        challenge
        for challenge in challenges
        if challenge.severity in {"high", "critical"}
        and str((_parse_challenge(challenge) or {}).get("challenge_id")) not in revised_ids
    ]
    revision_discount = min(0.15, len(unresolved_high) * 0.05)
    return round(
        min(
            0.75,
            base_discount + state_discount + challenge_discount + vote_discount + revision_discount,
        ),
        4,
    )


def _judge_confidence(
    baseline: dict[str, Any],
    votes: list[schema.LlmModelVote],
    confidence_discount: float,
) -> float:
    vote_confidence = mean(float(vote.confidence) for vote in votes) if votes else 0.0
    raw = (float(baseline.get("baseline_confidence") or 0) + vote_confidence) / 2
    return round(max(0.0, min(1.0, raw - confidence_discount * 0.35)), 4)


def _consensus_level(votes: list[schema.LlmModelVote]) -> str:
    unique_votes = {vote.vote for vote in votes}
    avg_confidence = mean(float(vote.confidence) for vote in votes) if votes else 0.0
    if len(unique_votes) == 1 and avg_confidence >= 0.7:
        return "high"
    if len(unique_votes) <= 2 and avg_confidence >= 0.55:
        return "medium"
    return "low"


def _disagreement_level(
    votes: list[schema.LlmModelVote],
    challenges: list[schema.LlmChallenge],
) -> str:
    unique_votes = {vote.vote for vote in votes}
    high_challenges = [challenge for challenge in challenges if challenge.severity == "high"]
    if len(unique_votes) >= 3 or high_challenges:
        return "high"
    if len(unique_votes) == 2 or challenges:
        return "medium"
    return "low"


def _revision_for_challenge(
    revisions: list[schema.LlmRevision],
    challenge_id: str,
) -> schema.LlmRevision | None:
    for revision in revisions:
        if (revision.payload or {}).get("challenge_id") == challenge_id:
            return revision
    return None


def _revision_summary(revisions: list[schema.LlmRevision]) -> dict[str, Any]:
    return {
        "revision_count": len(revisions),
        "changed_count": sum(1 for revision in revisions if revision.changed),
        "revised_vote_matrix": [
            {
                "challenge_id": revision.challenge_id,
                "responding_agent": revision.responding_agent,
                "changed": revision.changed,
                "previous_vote": revision.previous_vote,
                "revised_vote": revision.revised_vote,
                "previous_confidence": revision.previous_confidence,
                "revised_confidence": revision.revised_confidence,
            }
            for revision in revisions
        ],
    }


def _dominant_regime(baseline: dict[str, Any], state: dict[str, Any]) -> str:
    if state.get("blocked_by"):
        return "constrained_" + str(state["risk_state"])
    return str(baseline["baseline_signal"]) + "_baseline"


def _parse_challenge(challenge: schema.LlmChallenge) -> dict[str, Any] | None:
    try:
        return json.loads(challenge.issue)
    except json.JSONDecodeError:
        return None


def _summary(synthesis: JudgeSynthesis) -> str:
    return (
        f"Judge synthesis {synthesis.judge_synthesis_id}: "
        f"trend_state={synthesis.trend_state}, risk_state={synthesis.risk_state}, "
        f"confidence={synthesis.confidence}, blocked_by={synthesis.blocked_by}."
    )


def _evidence_ids(
    *claim_groups: list[KeyClaim] | dict[str, Any],
) -> list[str]:
    ids: list[str] = []
    for group in claim_groups:
        if isinstance(group, dict):
            ids.extend(_state_evidence_ids(group))
        else:
            for claim in group:
                ids.extend(claim.evidence_ids)
    return sorted(set(ids)) or ["no-evidence-id-available"]


def _baseline_evidence_ids(baseline: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for context in (baseline.get("analyst_context") or {}).values():
        ids.extend(str(item) for item in context.get("evidence_ids") or [])
    return sorted(set(ids))[:20] or ["no-evidence-id-available"]


def _state_evidence_ids(state: dict[str, Any]) -> list[str]:
    return [str(item) for item in state.get("evidence_ids") or []]


def _safe_evidence_ids(*groups: Any) -> list[str]:
    ids: list[str] = []
    for group in groups:
        if isinstance(group, list):
            ids.extend(str(item) for item in group if item)
    return sorted(set(ids))[:20] or ["no-evidence-id-available"]


def _direction_from_signal(signal: str) -> str:
    if signal in {"bullish", "bearish", "mixed", "risk_off"}:
        return signal
    return "neutral"
