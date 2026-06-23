from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.agent_runtime import AgentRuntimeAdapter, RuntimeResult
from onlybtc.p4.prompts import build_cross_examiner_system_prompt
from onlybtc.p4.rule_baseline import build_rule_baseline
from onlybtc.p4.schemas import CrossExamChallenge
from onlybtc.p4.state_machine import run_state_machine

RuntimeMode = Literal["mock", "llm"]


def run_cross_examination(
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
        if not votes:
            raise RuntimeError(f"No analyst votes found for debate_id={debate_id}")
        candidate_challenges = _generate_challenges(
            debate_id=debate_id,
            votes=votes,
            baseline=baseline,
            state=state,
        )
        challenges, runtime_results = _run_challenge_runtime(
            candidate_challenges,
            votes=votes,
            baseline=baseline,
            state=state,
            runtime_mode=runtime_mode,
        )
        for challenge in challenges:
            session.add(
                schema.LlmChallenge(
                    debate_id=debate_id,
                    challenger=challenge.from_agent,
                    target=challenge.to_agent,
                    issue=challenge.model_dump_json(),
                    severity=challenge.severity,
                )
            )
        session.add(
            schema.LlmRound(
                debate_id=debate_id,
                round_number=2,
                round_type="cross_examination",
                summary=str(
                    {
                        "pack_id": baseline["pack_id"],
                        "controller_run_id": baseline["controller_run_id"],
                        "challenge_count": len(challenges),
                        "state_machine": {
                            "trend_state": state["trend_state"],
                            "risk_state": state["risk_state"],
                            "critical_publish_allowed": state["critical_publish_allowed"],
                            "blocked_by": state["blocked_by"],
                        },
                        "runtime_mode": runtime_mode,
                        "runtime_results": [
                            result.model_dump(mode="json") for result in runtime_results
                        ],
                    }
                ),
            )
        )
    return {
        "status": "completed",
        "pack_id": baseline["pack_id"],
        "debate_id": debate.debate_id,
        "run_id": debate.run_id,
        "runtime_mode": runtime_mode,
        "challenge_count": len(challenges),
        "challenges": [challenge.model_dump(mode="json") for challenge in challenges],
        "runtime_results": [result.model_dump(mode="json") for result in runtime_results],
        "state_machine": {
            "trend_state": state["trend_state"],
            "risk_state": state["risk_state"],
            "critical_publish_allowed": state["critical_publish_allowed"],
            "blocked_by": state["blocked_by"],
        },
    }


def _run_challenge_runtime(
    candidates: list[CrossExamChallenge],
    votes: list[schema.LlmModelVote],
    baseline: dict[str, Any],
    state: dict[str, Any],
    runtime_mode: RuntimeMode,
) -> tuple[list[CrossExamChallenge], list[RuntimeResult]]:
    if runtime_mode == "mock":
        return candidates, []
    adapter = AgentRuntimeAdapter()
    results: list[RuntimeResult] = []
    challenges: list[CrossExamChallenge] = []
    for candidate in candidates:
        payload = {
            "candidate_challenge": candidate.model_dump(mode="json"),
            "votes": [_vote_payload(vote) for vote in votes],
            "baseline": baseline,
            "state_machine": state,
        }
        prompt = build_cross_examiner_system_prompt().model_copy(
            update={
                "evidence_ids": candidate.evidence_ids,
                "user_prompt": (
                    "Rewrite or confirm this cross-examination challenge using only "
                    "the supplied JSON. Return one CrossExamChallenge JSON object. "
                    "Preserve to_agent, challenge_type, severity, and evidence_ids "
                    "unless the supplied JSON clearly requires a stricter correction.\n\n"
                    f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                ),
            }
        )
        result = adapter.run_llm_or_mock(
            prompt,
            CrossExamChallenge,
            fallback_output=candidate.model_dump(mode="json"),
        )
        results.append(result)
        if result.structured_output:
            challenges.append(CrossExamChallenge.model_validate(result.structured_output))
    return _dedupe_challenges(challenges or candidates), results


def _vote_payload(vote: schema.LlmModelVote) -> dict[str, Any]:
    return {
        "model_name": vote.model_name,
        "vote": vote.vote,
        "confidence": vote.confidence,
        "evidence_ids": vote.evidence_ids,
        "changed": vote.changed,
    }


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


def _generate_challenges(
    debate_id: str,
    votes: list[schema.LlmModelVote],
    baseline: dict[str, Any],
    state: dict[str, Any],
) -> list[CrossExamChallenge]:
    challenges: list[CrossExamChallenge] = []
    for vote in votes:
        challenges.extend(_state_machine_challenges(debate_id, vote, state))
        challenges.extend(_baseline_alignment_challenges(debate_id, vote, baseline))
        challenges.extend(_confidence_and_evidence_challenges(debate_id, vote, baseline))
    return _dedupe_challenges(challenges)


def _state_machine_challenges(
    debate_id: str,
    vote: schema.LlmModelVote,
    state: dict[str, Any],
) -> list[CrossExamChallenge]:
    if not state.get("blocked_by"):
        return []
    if vote.vote in {"bullish", "bearish", "risk_off"} or vote.confidence >= 0.62:
        return [
            CrossExamChallenge(
                challenge_id=_challenge_id(debate_id, vote.model_name, "state_machine"),
                from_agent="cross_examiner_agent",
                to_agent=vote.model_name,  # type: ignore[arg-type]
                challenge_type="ignored_invalidation",
                claim_under_review=(
                    f"{vote.model_name} vote={vote.vote}, confidence={vote.confidence} "
                    "must account for state-machine blocks: "
                    + ", ".join(state["blocked_by"])
                ),
                evidence_ids=_safe_evidence_ids(state.get("evidence_ids"), vote.evidence_ids),
                severity="high",
                required_response=(
                    "Explain whether the vote or confidence should be reduced because "
                    "critical publish is blocked by state-machine constraints."
                ),
            )
        ]
    return []


def _baseline_alignment_challenges(
    debate_id: str,
    vote: schema.LlmModelVote,
    baseline: dict[str, Any],
) -> list[CrossExamChallenge]:
    baseline_signal = str(baseline.get("baseline_signal"))
    opposing = (
        (baseline_signal == "bearish" and vote.vote == "bullish")
        or (baseline_signal == "bullish" and vote.vote == "bearish")
        or (baseline_signal in {"mixed", "neutral"} and vote.vote in {"bullish", "bearish"})
    )
    if not opposing:
        return []
    context = (baseline.get("analyst_context") or {}).get(vote.model_name, {})
    return [
        CrossExamChallenge(
            challenge_id=_challenge_id(debate_id, vote.model_name, "baseline_alignment"),
            from_agent="cross_examiner_agent",
            to_agent=vote.model_name,  # type: ignore[arg-type]
            challenge_type="evidence_conflict",
            claim_under_review=(
                f"{vote.model_name} vote={vote.vote} conflicts with rule baseline "
                f"signal={baseline_signal}."
            ),
            evidence_ids=_safe_evidence_ids(context.get("evidence_ids"), vote.evidence_ids),
            severity="medium",
            required_response=(
                "Identify which cited evidence justifies diverging from the rule baseline, "
                "or revise vote/confidence."
            ),
        )
    ]


def _confidence_and_evidence_challenges(
    debate_id: str,
    vote: schema.LlmModelVote,
    baseline: dict[str, Any],
) -> list[CrossExamChallenge]:
    challenges: list[CrossExamChallenge] = []
    context = (baseline.get("analyst_context") or {}).get(vote.model_name, {})
    if not vote.evidence_ids:
        challenges.append(
            CrossExamChallenge(
                challenge_id=_challenge_id(debate_id, vote.model_name, "missing_evidence"),
                from_agent="cross_examiner_agent",
                to_agent=vote.model_name,  # type: ignore[arg-type]
                challenge_type="missing_evidence",
                claim_under_review=f"{vote.model_name} vote has no evidence_ids.",
                evidence_ids=_safe_evidence_ids(context.get("evidence_ids"), []),
                severity="high",
                required_response="Provide evidence_ids from the current Evidence Pack.",
            )
        )
    if vote.confidence < 0.55:
        challenges.append(
            CrossExamChallenge(
                challenge_id=_challenge_id(debate_id, vote.model_name, "low_confidence"),
                from_agent="cross_examiner_agent",
                to_agent=vote.model_name,  # type: ignore[arg-type]
                challenge_type="missing_evidence",
                claim_under_review=(
                    f"{vote.model_name} confidence={vote.confidence} is below the "
                    "independent-review threshold."
                ),
                evidence_ids=_safe_evidence_ids(vote.evidence_ids, context.get("evidence_ids")),
                severity="medium",
                required_response=(
                    "Clarify whether evidence is insufficient, conflicting, stale, or "
                    "quality-discounted."
                ),
            )
        )
    if int(context.get("missing_count") or 0) > 0:
        challenges.append(
            CrossExamChallenge(
                challenge_id=_challenge_id(debate_id, vote.model_name, "missing_scope_data"),
                from_agent="cross_examiner_agent",
                to_agent=vote.model_name,  # type: ignore[arg-type]
                challenge_type="data_quality",
                claim_under_review=(
                    f"{vote.model_name} scope has missing_count={context.get('missing_count')}."
                ),
                evidence_ids=_safe_evidence_ids(context.get("evidence_ids"), vote.evidence_ids),
                severity="medium",
                required_response=(
                    "Explain how missing or low-quality scope evidence affects confidence."
                ),
            )
        )
    return challenges


def _safe_evidence_ids(*groups: Any) -> list[str]:
    evidence_ids: list[str] = []
    for group in groups:
        if isinstance(group, list):
            evidence_ids.extend(str(item) for item in group if item)
    return sorted(set(evidence_ids))[:20] or ["no-evidence-id-available"]


def _dedupe_challenges(challenges: list[CrossExamChallenge]) -> list[CrossExamChallenge]:
    seen: set[str] = set()
    deduped: list[CrossExamChallenge] = []
    for challenge in challenges:
        if challenge.challenge_id in seen:
            continue
        seen.add(challenge.challenge_id)
        deduped.append(challenge)
    return deduped


def _challenge_id(debate_id: str, analyst: str, reason: str) -> str:
    return f"ch-{debate_id[-10:]}-{analyst}-{reason}-{uuid4().hex[:4]}"
