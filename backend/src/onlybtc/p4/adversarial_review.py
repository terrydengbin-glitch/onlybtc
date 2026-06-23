from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.agent_runtime import AgentRuntimeAdapter, RuntimeResult
from onlybtc.p4.prompts import (
    PROHIBITED_TRADING_TERMS,
    build_adversarial_reviewer_system_prompt,
)
from onlybtc.p4.schemas import AdversarialReview, JudgeSynthesis

RuntimeMode = Literal["mock", "llm"]


def run_adversarial_review(
    debate_id: str,
    judge_synthesis_id: str | None = None,
    runtime_mode: RuntimeMode = "mock",
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        debate = _load_debate(session, debate_id)
        judge_row = _load_judge_synthesis(session, debate_id, judge_synthesis_id)
        synthesis = _judge_payload(judge_row.payload)
        challenges = _load_challenges(session, debate_id)
        revisions = _load_revisions(session, debate_id)
        votes = _load_votes(session, debate_id)

        findings, required_fixes = _review_synthesis(
            synthesis=synthesis,
            challenges=challenges,
            revisions=revisions,
            judge_payload=judge_row.payload or {},
            votes=votes,
        )
        passed = not required_fixes
        publish_allowed = bool(synthesis.publish_allowed and passed)
        fallback_review = AdversarialReview(
            review_id=f"review-{uuid4().hex[:12]}",
            judge_synthesis_id=synthesis.judge_synthesis_id,
            passed=passed,
            publish_allowed=publish_allowed,
            findings=findings,
            required_fixes=required_fixes,
            evidence_ids=synthesis.evidence_ids,
        )
        review, runtime_results = _run_review_runtime(
            fallback_review=fallback_review,
            synthesis=synthesis,
            challenges=challenges,
            revisions=revisions,
            votes=votes,
            runtime_mode=runtime_mode,
        )
        session.add(
            schema.AdversarialReview(
                run_id=synthesis.controller_run_id,
                debate_id=debate_id,
                review_passed=review.passed,
                issues={
                    "review_id": review.review_id,
                    "judge_synthesis_id": review.judge_synthesis_id,
                    "findings": review.findings,
                    "publish_allowed": review.publish_allowed,
                    "runtime_mode": runtime_mode,
                    "runtime_results": [
                        result.model_dump(mode="json") for result in runtime_results
                    ],
                },
                required_changes={"required_fixes": review.required_fixes},
            )
        )
        debate.publish_allowed = publish_allowed

    return {
        "status": "completed",
        "runtime_mode": runtime_mode,
        "adversarial_review": review.model_dump(mode="json"),
        "runtime_results": [result.model_dump(mode="json") for result in runtime_results],
    }


def _run_review_runtime(
    fallback_review: AdversarialReview,
    synthesis: JudgeSynthesis,
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    votes: list[schema.LlmModelVote],
    runtime_mode: RuntimeMode,
) -> tuple[AdversarialReview, list[RuntimeResult]]:
    if runtime_mode == "mock":
        return fallback_review, []
    payload = {
        "fallback_review": fallback_review.model_dump(mode="json"),
        "judge_synthesis": synthesis.model_dump(mode="json"),
        "challenges": [_parse_challenge_issue(challenge.issue) for challenge in challenges],
        "revisions": [revision.payload for revision in revisions],
        "votes": [
            {
                "model_name": vote.model_name,
                "vote": vote.vote,
                "confidence": vote.confidence,
                "evidence_ids": vote.evidence_ids,
            }
            for vote in votes
        ],
    }
    prompt = build_adversarial_reviewer_system_prompt().model_copy(
        update={
            "evidence_ids": fallback_review.evidence_ids,
            "user_prompt": (
                "Produce one AdversarialReview JSON object using only the supplied JSON. "
                "Preserve evidence_ids and block publish if judge constraints, evidence, "
                "or runtime integrity are insufficient.\n\n"
                f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
            ),
        }
    )
    adapter = AgentRuntimeAdapter()
    result = adapter.run_llm_or_mock(
        prompt,
        AdversarialReview,
        fallback_output=fallback_review.model_dump(mode="json"),
    )
    if result.structured_output:
        return AdversarialReview.model_validate(result.structured_output), [result]
    return fallback_review, [result]


def _load_debate(session, debate_id: str) -> schema.LlmDebate:
    debate = session.scalar(select(schema.LlmDebate).where(schema.LlmDebate.debate_id == debate_id))
    if debate is None:
        raise RuntimeError(f"LLM debate not found: {debate_id}")
    return debate


def _judge_payload(payload: dict[str, Any]) -> JudgeSynthesis:
    return JudgeSynthesis.model_validate(
        {key: value for key, value in (payload or {}).items() if key in JudgeSynthesis.model_fields}
    )


def _load_judge_synthesis(
    session,
    debate_id: str,
    judge_synthesis_id: str | None,
) -> schema.JudgeSynthesis:
    rows = session.scalars(
        select(schema.JudgeSynthesis)
        .where(schema.JudgeSynthesis.debate_id == debate_id)
        .order_by(schema.JudgeSynthesis.created_at.desc(), schema.JudgeSynthesis.id.desc())
    ).all()
    if not rows:
        raise RuntimeError(f"No judge synthesis found for debate_id={debate_id}")
    if judge_synthesis_id is None:
        return rows[0]
    for row in rows:
        payload = row.payload or {}
        if payload.get("judge_synthesis_id") == judge_synthesis_id:
            return row
    raise RuntimeError(
        f"Judge synthesis {judge_synthesis_id} not found for debate_id={debate_id}"
    )


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


def _load_votes(session, debate_id: str) -> list[schema.LlmModelVote]:
    return session.scalars(
        select(schema.LlmModelVote)
        .where(schema.LlmModelVote.debate_id == debate_id)
        .order_by(schema.LlmModelVote.model_name)
    ).all()


def _review_synthesis(
    synthesis: JudgeSynthesis,
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    judge_payload: dict[str, Any],
    votes: list[schema.LlmModelVote],
) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    required_fixes: list[str] = []

    _check_evidence_ids(synthesis, findings, required_fixes)
    _check_state_machine_constraints(synthesis, findings, required_fixes)
    _check_cross_exam_coverage(synthesis, challenges, findings, required_fixes)
    _check_revision_gate(synthesis, challenges, revisions, judge_payload, findings, required_fixes)
    _check_guardrail_inputs(votes, findings, required_fixes)
    _check_trading_advice(synthesis, findings, required_fixes)
    _check_publish_confidence(synthesis, findings, required_fixes)

    if not required_fixes:
        findings.append(
            "adversarial review passed; judge output preserves evidence and constraints"
        )
    return findings, required_fixes


def _check_evidence_ids(
    synthesis: JudgeSynthesis,
    findings: list[str],
    required_fixes: list[str],
) -> None:
    evidence_ids = set(synthesis.evidence_ids)
    if not evidence_ids or "no-evidence-id-available" in evidence_ids:
        required_fixes.append("judge synthesis must reference concrete evidence_ids")
    for group_name, claims in (
        ("accepted_claims", synthesis.accepted_claims),
        ("rejected_claims", synthesis.rejected_claims),
        ("minority_objections", synthesis.minority_objections),
    ):
        missing = [
            claim.claim
            for claim in claims
            if not claim.evidence_ids or "no-evidence-id-available" in claim.evidence_ids
        ]
        if missing:
            required_fixes.append(f"{group_name} contains claims without concrete evidence_ids")
    if not required_fixes:
        findings.append("all judge claims preserve concrete evidence_ids")


def _check_state_machine_constraints(
    synthesis: JudgeSynthesis,
    findings: list[str],
    required_fixes: list[str],
) -> None:
    applied = set(synthesis.state_machine_constraints_applied)
    blocked = set(synthesis.blocked_by)
    if blocked:
        if not synthesis.rejected_claims:
            required_fixes.append("blocked state requires rejected_claims explaining the rejection")
        findings.append("judge retained blocked_by constraints: " + ", ".join(sorted(blocked)))
    if (
        "run_mode_integrity_invalidation" in blocked
        and "run_mode_or_p3_block_critical" not in applied
    ):
        required_fixes.append(
            "run_mode_integrity_invalidation must be carried into state_machine_constraints_applied"
        )
    if blocked and synthesis.confidence_discount <= 0:
        required_fixes.append("blocked state requires a non-zero confidence_discount")


def _check_cross_exam_coverage(
    synthesis: JudgeSynthesis,
    challenges: list[schema.LlmChallenge],
    findings: list[str],
    required_fixes: list[str],
) -> None:
    material_challenges = [
        challenge
        for challenge in challenges
        if challenge.severity in {"medium", "high", "critical"}
    ]
    if not material_challenges:
        findings.append("no material cross-exam challenges required judge preservation")
        return
    if not synthesis.minority_objections:
        required_fixes.append("material cross-exam challenges require minority_objections")
        return
    challenge_evidence = set()
    for challenge in material_challenges:
        parsed = _parse_challenge_issue(challenge.issue)
        challenge_evidence.update(str(item) for item in parsed.get("evidence_ids") or [])
    objection_evidence = {
        evidence_id
        for claim in synthesis.minority_objections
        for evidence_id in claim.evidence_ids
    }
    missing = sorted(challenge_evidence - objection_evidence - set(synthesis.evidence_ids))
    if missing:
        required_fixes.append(
            "judge minority_objections missed challenge evidence_ids: " + ", ".join(missing)
        )
    else:
        findings.append(
            f"judge preserved {len(material_challenges)} material cross-exam challenge(s)"
        )


def _check_revision_gate(
    synthesis: JudgeSynthesis,
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    judge_payload: dict[str, Any],
    findings: list[str],
    required_fixes: list[str],
) -> None:
    material_challenges = [
        challenge
        for challenge in challenges
        if challenge.severity in {"medium", "high", "critical"}
    ]
    if not material_challenges:
        findings.append("no material challenge requires revision gate")
        return
    revision_by_challenge = {
        str((revision.payload or {}).get("challenge_id")): revision for revision in revisions
    }
    unresolved = []
    missing_evidence = []
    weak_rejections = []
    for challenge in material_challenges:
        parsed = _parse_challenge_issue(challenge.issue)
        challenge_id = str(parsed.get("challenge_id") or "")
        revision = revision_by_challenge.get(challenge_id)
        if revision is None:
            unresolved.append(challenge)
            continue
        payload = revision.payload or {}
        evidence_ids = payload.get("evidence_ids") or []
        if not evidence_ids or "no-evidence-id-available" in evidence_ids:
            missing_evidence.append(challenge_id)
        if payload.get("changed") is False and not payload.get("rejected_points"):
            weak_rejections.append(challenge_id)
    unresolved_high = [
        challenge for challenge in unresolved if challenge.severity in {"high", "critical"}
    ]
    if unresolved_high:
        unresolved_high_ids = [
            str(_parse_challenge_issue(item.issue).get("challenge_id"))
            for item in unresolved_high
        ]
        required_fixes.append(
            "high/critical challenges missing CrossExamRevision: "
            + ", ".join(unresolved_high_ids)
        )
    elif unresolved:
        findings.append(f"{len(unresolved)} medium challenge(s) remain unresolved but non-blocking")
    if missing_evidence:
        required_fixes.append(
            "CrossExamRevision missing concrete evidence_ids: " + ", ".join(missing_evidence)
        )
    if weak_rejections:
        required_fixes.append(
            "CrossExamRevision changed=false lacks rejected_points: " + ", ".join(weak_rejections)
        )
    revision_summary = judge_payload.get("revision_summary") or {}
    if revisions and not revision_summary:
        required_fixes.append("judge synthesis must preserve revision_summary")
    elif revisions:
        findings.append(
            "judge consumed revision matrix with "
            f"{revision_summary.get('revision_count', len(revisions))} revision(s)"
        )
    if required_fixes:
        findings.append("revision gate limited publish scope")
    elif synthesis.publish_allowed:
        findings.append("revision gate passed with publish_allowed preserved")


def _check_guardrail_inputs(
    votes: list[schema.LlmModelVote],
    findings: list[str],
    required_fixes: list[str],
) -> None:
    votes_without_evidence = [
        vote.model_name
        for vote in votes
        if not vote.evidence_ids or "no-evidence-id-available" in vote.evidence_ids
    ]
    if votes_without_evidence:
        required_fixes.append(
            "analyst votes missing concrete evidence_ids: " + ", ".join(votes_without_evidence)
        )
    else:
        findings.append(f"all {len(votes)} analyst vote(s) retain evidence references")


def _check_trading_advice(
    synthesis: JudgeSynthesis,
    findings: list[str],
    required_fixes: list[str],
) -> None:
    payload = _normalize_guardrail_text(
        "\n".join(_collect_free_text(synthesis.model_dump(mode="json"))).lower()
    )
    matched = [term for term in PROHIBITED_TRADING_TERMS if term.lower() in payload]
    if matched:
        required_fixes.append("judge synthesis contains prohibited trading advice terms")
    else:
        findings.append("no prohibited trading advice terms found")


def _check_publish_confidence(
    synthesis: JudgeSynthesis,
    findings: list[str],
    required_fixes: list[str],
) -> None:
    if synthesis.blocked_by and synthesis.confidence > 0.65:
        required_fixes.append("judge confidence is too high while hard constraints are active")
    if synthesis.blocked_by and synthesis.publish_allowed:
        findings.append("publish is limited/watch-only because hard constraints remain active")


def _parse_challenge_issue(issue: str) -> dict[str, Any]:
    try:
        parsed = json.loads(issue)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_guardrail_text(text: str) -> str:
    return (
        text.replace("leverage_microstructure_analyst", "")
        .replace("leverage_microstructure", "")
        .replace("leverage & microstructure", "")
    )


def _collect_free_text(value: Any, parent_key: str | None = None) -> list[str]:
    free_text_keys = {
        "claim",
        "uncertainty",
        "dominant_regime",
        "trend_state",
        "risk_state",
    }
    if isinstance(value, dict):
        text: list[str] = []
        for key, item in value.items():
            text.extend(_collect_free_text(item, key))
        return text
    if isinstance(value, list):
        text: list[str] = []
        for item in value:
            text.extend(_collect_free_text(item, parent_key))
        return text
    if isinstance(value, str) and parent_key in free_text_keys:
        return [value]
    return []
