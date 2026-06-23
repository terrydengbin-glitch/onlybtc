from __future__ import annotations

import ast
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.schemas import AdversarialReview, FinalControllerJson, JudgeSynthesis


def build_final_controller_json(
    debate_id: str,
    judge_synthesis_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        debate = _load_debate(session, debate_id)
        judge_row = _load_judge_synthesis(session, debate_id, judge_synthesis_id)
        judge = _judge_payload(judge_row)
        review_row = _latest_adversarial_review(session, debate_id, judge.judge_synthesis_id)
        review = _review_payload(review_row, judge.judge_synthesis_id)
        votes = _load_votes(session, debate_id)
        challenges = _load_challenges(session, debate_id)
        revisions = _load_revisions(session, debate_id)
        runtime_trace = _load_runtime_trace(session, debate_id, judge_row, review_row)
        pack = _load_pack(session, judge.pack_id)
        radar_run_id = _radar_run_id_from_pack(session, judge.pack_id)
        radar_rows = _load_radar_outputs(session, radar_run_id)
        alerts = _load_alerts(session, judge.controller_run_id)

        final_json = _build_payload(
            debate=debate,
            judge=judge,
            review=review,
            votes=votes,
            challenges=challenges,
            revisions=revisions,
            judge_payload=judge_row.payload or {},
            pack=pack,
            runtime_trace=runtime_trace,
        )
        final_json = FinalControllerJson.model_validate(
            _sanitize_nested(final_json.model_dump(mode="json"))
        )
        snapshot_id = f"snapshot-{uuid4().hex[:12]}"
        session.add(
            schema.DashboardSnapshot(
                snapshot_id=snapshot_id,
                run_id=final_json.run_id,
                btc_price=_latest_btc_price(session),
                state=final_json.trend_state,
                bias=final_json.dominant_regime or final_json.trend_state,
                confidence=final_json.confidence,
                risk_level=_risk_level(final_json),
                alert_level=_alert_level(final_json),
                payload=final_json.model_dump(mode="json"),
            )
        )
        session.add_all(
            [
                schema.SnapshotModule(
                    snapshot_id=snapshot_id,
                    module_id=row.module_id,
                    signal=row.signal,
                    strength=row.strength,
                    payload={
                        "confidence": row.confidence,
                        "data_quality": row.data_quality,
                        "evidence_summary": row.evidence_summary,
                        "risk_flags": row.risk_flags,
                        "invalidation_signals": row.invalidation_signals,
                    },
                )
                for row in radar_rows
            ]
        )
        session.add_all(
            [
                schema.SnapshotAlert(snapshot_id=snapshot_id, alert_id=alert.alert_id)
                for alert in alerts
            ]
        )
        judge_payload = dict(judge_row.payload or {})
        judge_payload["final_controller_json"] = final_json.model_dump(mode="json")
        judge_payload["dashboard_snapshot_id"] = snapshot_id
        judge_row.payload = judge_payload
        debate.publish_allowed = final_json.publish_allowed

    return {
        "status": "completed",
        "snapshot_id": snapshot_id,
        "final_controller_json": final_json.model_dump(mode="json"),
        "snapshot_module_count": len(radar_rows),
        "snapshot_alert_count": len(alerts),
    }


def _load_debate(session, debate_id: str) -> schema.LlmDebate:
    debate = session.scalar(select(schema.LlmDebate).where(schema.LlmDebate.debate_id == debate_id))
    if debate is None:
        raise RuntimeError(f"LLM debate not found: {debate_id}")
    return debate


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


def _latest_adversarial_review(
    session,
    debate_id: str,
    judge_synthesis_id: str,
) -> schema.AdversarialReview | None:
    rows = session.scalars(
        select(schema.AdversarialReview)
        .where(schema.AdversarialReview.debate_id == debate_id)
        .order_by(schema.AdversarialReview.created_at.desc(), schema.AdversarialReview.id.desc())
    ).all()
    for row in rows:
        if (row.issues or {}).get("judge_synthesis_id") == judge_synthesis_id:
            return row
    return rows[0] if rows else None


def _review_payload(
    row: schema.AdversarialReview | None,
    judge_synthesis_id: str,
) -> AdversarialReview | None:
    if row is None:
        return None
    issues = row.issues or {}
    required_changes = row.required_changes or {}
    return AdversarialReview(
        review_id=str(issues.get("review_id") or f"review-row-{row.id}"),
        judge_synthesis_id=str(issues.get("judge_synthesis_id") or judge_synthesis_id),
        passed=bool(row.review_passed),
        publish_allowed=bool(issues.get("publish_allowed", row.review_passed)),
        findings=[str(item) for item in issues.get("findings") or []],
        required_fixes=[
            str(item) for item in required_changes.get("required_fixes") or []
        ],
        evidence_ids=[],
    )


def _judge_payload(row: schema.JudgeSynthesis) -> JudgeSynthesis:
    payload = row.payload or {}
    allowed = {
        key: value
        for key, value in payload.items()
        if key in JudgeSynthesis.model_fields
    }
    return JudgeSynthesis.model_validate(allowed)


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


def _load_pack(session, pack_id: str) -> schema.EvidencePack:
    pack = session.scalar(select(schema.EvidencePack).where(schema.EvidencePack.pack_id == pack_id))
    if pack is None:
        raise RuntimeError(f"Evidence pack not found: {pack_id}")
    return pack


def _radar_run_id_from_pack(session, pack_id: str) -> str | None:
    item = session.scalar(
        select(schema.EvidenceItem)
        .where(schema.EvidenceItem.pack_id == pack_id)
        .order_by(schema.EvidenceItem.id)
        .limit(1)
    )
    if item is None:
        return None
    return (item.data or {}).get("p2_radar_run_id")


def _load_radar_outputs(session, radar_run_id: str | None) -> list[schema.RadarOutput]:
    if radar_run_id is None:
        return []
    return session.scalars(
        select(schema.RadarOutput)
        .where(schema.RadarOutput.run_id == radar_run_id)
        .order_by(schema.RadarOutput.module_id)
    ).all()


def _load_alerts(session, run_id: str) -> list[schema.AlgorithmAlert]:
    return session.scalars(
        select(schema.AlgorithmAlert)
        .where(schema.AlgorithmAlert.run_id == run_id)
        .order_by(schema.AlgorithmAlert.level.desc(), schema.AlgorithmAlert.created_at.desc())
    ).all()


def _build_payload(
    debate: schema.LlmDebate,
    judge: JudgeSynthesis,
    review: AdversarialReview | None,
    votes: list[schema.LlmModelVote],
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    judge_payload: dict[str, Any],
    pack: schema.EvidencePack,
    runtime_trace: dict[str, Any],
) -> FinalControllerJson:
    publish_allowed = bool(judge.publish_allowed and (review.publish_allowed if review else False))
    blocked_by = list(judge.blocked_by)
    revision_gate = _revision_gate(challenges, revisions, judge_payload, review)
    review_gate_failed = False
    if review is None:
        publish_allowed = False
        review_gate_failed = True
        blocked_by.append("adversarial_review_missing")
    elif not review.passed:
        publish_allowed = False
        review_gate_failed = True
        blocked_by.append("adversarial_review_failed")
    if blocked_by:
        publish_allowed = False
    if revision_gate["revision_integrity"] == "failed":
        publish_allowed = False
        blocked_by.append("revision_gate_failed")
    publish_scope = _publish_scope(
        publish_allowed=publish_allowed,
        blocked_by=blocked_by,
        revision_gate=revision_gate,
        review_gate_failed=review_gate_failed,
    )
    return FinalControllerJson(
        run_id=judge.controller_run_id,
        evidence_pack_id=judge.pack_id,
        debate_id=debate.debate_id,
        judge_synthesis_id=judge.judge_synthesis_id,
        adversarial_review_id=review.review_id if review else None,
        analyst_vote_ids=[f"vote-{vote.id}" for vote in votes],
        challenge_ids=[_sanitize_text(f"challenge-row-{challenge.id}") for challenge in challenges],
        revision_ids=[_sanitize_text(f"revision-row-{revision.id}") for revision in revisions],
        agent_runtime_trace_ids=runtime_trace["trace_ids"],
        runtime_mode=runtime_trace["runtime_mode"],
        llm_runtime_integrity=runtime_trace["integrity"],
        agent_runtime_failures=runtime_trace["failures"],
        fallback_used=runtime_trace["fallback_used"],
        fallback_reasons=runtime_trace["fallback_reasons"],
        llm_budget_summary=runtime_trace["budget_summary"],
        revision_integrity=revision_gate["revision_integrity"],
        revision_round_count=revision_gate["revision_round_count"],
        unresolved_challenge_count=revision_gate["unresolved_challenge_count"],
        unresolved_high_challenge_count=revision_gate["unresolved_high_challenge_count"],
        revision_required_fixes=revision_gate["revision_required_fixes"],
        adversarial_publish_gate_reason=revision_gate["adversarial_publish_gate_reason"],
        watch_only=publish_scope in {"watch_only", "dashboard_only"},
        dashboard_only=publish_scope == "dashboard_only",
        publish_scope=publish_scope,
        publish_block_reason=_publish_block_reason(blocked_by, revision_gate),
        revised_vote_matrix_summary=revision_gate["revised_vote_matrix_summary"],
        dominant_regime=judge.dominant_regime,
        consensus_level=judge.consensus_level,
        disagreement_level=judge.disagreement_level,
        minority_objections=_sanitized_claims(judge.minority_objections),
        state_machine_constraints_applied=judge.state_machine_constraints_applied,
        publish_constraints=blocked_by,
        trend_state=judge.trend_state,
        risk_state=judge.risk_state,
        dominant_drivers=_dominant_drivers(judge),
        invalidation_watch=blocked_by,
        observation_points=_observation_points(judge),
        data_quality_notes=_data_quality_notes(pack, judge),
        confidence=judge.confidence,
        confidence_discount=judge.confidence_discount,
        publish_allowed=publish_allowed,
        blocked_by=blocked_by,
        evidence_ids=judge.evidence_ids,
    )


def _load_runtime_trace(
    session,
    debate_id: str,
    judge_row: schema.JudgeSynthesis,
    review_row: schema.AdversarialReview | None,
) -> dict[str, Any]:
    runtime_results: list[dict[str, Any]] = []
    runtime_modes: list[str] = []
    rounds = session.scalars(
        select(schema.LlmRound)
        .where(schema.LlmRound.debate_id == debate_id)
        .order_by(schema.LlmRound.round_number)
    ).all()
    for row in rounds:
        parsed = _safe_literal_dict(row.summary)
        runtime_results.extend(
            item for item in parsed.get("results", []) if isinstance(item, dict)
        )
        runtime_results.extend(
            item for item in parsed.get("runtime_results", []) if isinstance(item, dict)
        )
        if parsed.get("runtime_mode"):
            runtime_modes.append(str(parsed["runtime_mode"]))
    judge_payload = judge_row.payload or {}
    runtime_results.extend(judge_payload.get("runtime_results") or [])
    if judge_payload.get("runtime_mode"):
        runtime_modes.append(str(judge_payload["runtime_mode"]))
    if review_row is not None:
        review_issues = review_row.issues or {}
        runtime_results.extend(review_issues.get("runtime_results") or [])
        if review_issues.get("runtime_mode"):
            runtime_modes.append(str(review_issues["runtime_mode"]))

    trace_ids = [
        _sanitize_text(str(item.get("trace_id")))
        for item in runtime_results
        if item.get("trace_id")
    ]
    failures = [
        _sanitize_text(f"{item.get('agent_name')}: {item.get('error')}")
        for item in runtime_results
        if item.get("error")
    ]
    fallback_reasons = [
        _sanitize_text(f"{item.get('agent_name')}: {item.get('fallback_reason')}")
        for item in runtime_results
        if item.get("fallback_used")
    ]
    fallback_used = bool(fallback_reasons)
    runtime_mode = (
        "llm" if "llm" in runtime_modes else (runtime_modes[0] if runtime_modes else "mock")
    )
    if failures:
        integrity = "failed"
    elif fallback_used:
        integrity = "fallback_used"
    elif runtime_results:
        integrity = "passed"
    else:
        integrity = "not_evaluated"
    prompt_tokens = sum(
        int((item.get("token_usage") or {}).get("prompt_tokens_estimated") or 0)
        for item in runtime_results
    )
    completion_tokens = sum(
        int((item.get("token_usage") or {}).get("completion_tokens_estimated") or 0)
        for item in runtime_results
    )
    return {
        "trace_ids": trace_ids,
        "runtime_mode": runtime_mode,
        "integrity": integrity,
        "failures": failures,
        "fallback_used": fallback_used,
        "fallback_reasons": fallback_reasons,
        "budget_summary": {
            "runtime_result_count": len(runtime_results),
            "prompt_tokens_estimated": prompt_tokens,
            "completion_tokens_estimated": completion_tokens,
            "total_tokens_estimated": prompt_tokens + completion_tokens,
        },
    }


def _safe_literal_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _revision_gate(
    challenges: list[schema.LlmChallenge],
    revisions: list[schema.LlmRevision],
    judge_payload: dict[str, Any],
    review: AdversarialReview | None,
) -> dict[str, Any]:
    revision_by_challenge = {
        str((revision.payload or {}).get("challenge_id")): revision for revision in revisions
    }
    material = [
        challenge
        for challenge in challenges
        if challenge.severity in {"medium", "high", "critical"}
    ]
    unresolved = [
        challenge
        for challenge in material
        if str((_parse_challenge(challenge) or {}).get("challenge_id")) not in revision_by_challenge
    ]
    unresolved_high = [
        challenge for challenge in unresolved if challenge.severity in {"high", "critical"}
    ]
    review_fixes = list(review.required_fixes if review else [])
    revision_fixes = [fix for fix in review_fixes if "Revision" in fix or "revision" in fix]
    revision_summary = dict(judge_payload.get("revision_summary") or {})
    if unresolved_high or revision_fixes:
        integrity = "failed"
    elif unresolved:
        integrity = "partial"
    elif revisions:
        integrity = "passed"
    else:
        integrity = "not_evaluated"
    return {
        "revision_integrity": integrity,
        "revision_round_count": 1 if revisions else 0,
        "unresolved_challenge_count": len(unresolved),
        "unresolved_high_challenge_count": len(unresolved_high),
        "revision_required_fixes": revision_fixes,
        "adversarial_publish_gate_reason": "; ".join(revision_fixes) if revision_fixes else None,
        "revised_vote_matrix_summary": _sanitize_nested(revision_summary),
    }


def _publish_scope(
    publish_allowed: bool,
    blocked_by: list[str],
    revision_gate: dict[str, Any],
    review_gate_failed: bool = False,
) -> str:
    if publish_allowed:
        return "publish_candidate"
    if review_gate_failed:
        return "dashboard_only"
    if revision_gate["revision_integrity"] == "failed":
        return "dashboard_only"
    if blocked_by:
        return "watch_only"
    return "blocked"


def _publish_block_reason(
    blocked_by: list[str],
    revision_gate: dict[str, Any],
) -> str | None:
    if revision_gate["adversarial_publish_gate_reason"]:
        return str(revision_gate["adversarial_publish_gate_reason"])
    if blocked_by:
        return ", ".join(sorted(set(blocked_by)))
    return None


def _parse_challenge(challenge: schema.LlmChallenge) -> dict[str, Any]:
    try:
        parsed = json.loads(challenge.issue)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _dominant_drivers(judge: JudgeSynthesis) -> list[str]:
    claims = sorted(judge.accepted_claims, key=lambda item: item.strength, reverse=True)
    return [_sanitize_text(claim.claim) for claim in claims[:5]]


def _observation_points(judge: JudgeSynthesis) -> list[str]:
    points = [_sanitize_text(claim.claim) for claim in judge.minority_objections[:5]]
    if judge.blocked_by:
        points.append("Monitor blocked constraints: " + ", ".join(judge.blocked_by))
    return points


def _sanitized_claims(claims: list[Any]) -> list[Any]:
    sanitized = []
    for claim in claims:
        payload = claim.model_dump(mode="json")
        payload["claim"] = _sanitize_text(str(payload["claim"]))
        sanitized.append(type(claim).model_validate(payload))
    return sanitized


def _sanitize_text(text: str) -> str:
    return (
        text.replace("leverage_microstructure_analyst", "microstructure_analyst")
        .replace("leverage_microstructure", "microstructure")
        .replace("Leverage & Microstructure", "Microstructure")
    )


def _sanitize_nested(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_nested(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _data_quality_notes(pack: schema.EvidencePack, judge: JudgeSynthesis) -> list[str]:
    notes = [f"evidence_pack_data_quality_score={pack.data_quality_score:.3f}"]
    if judge.confidence_discount:
        notes.append(f"confidence_discount={judge.confidence_discount:.3f}")
    if "run_mode_integrity_invalidation" in judge.blocked_by:
        notes.append(
            "production_readiness=blocked_by_run_mode_integrity; "
            "data_quality_score_does_not_override_publish_gate"
        )
    elif judge.blocked_by:
        notes.append("production_readiness=constrained_by_hard_constraints")
    else:
        notes.append("production_readiness=eligible")
    return notes


def _latest_btc_price(session) -> float | None:
    row = session.scalar(
        select(schema.MetricValue)
        .where(schema.MetricValue.metric_id.in_(["btc_spot_price", "btc_price"]))
        .order_by(schema.MetricValue.ts.desc(), schema.MetricValue.id.desc())
        .limit(1)
    )
    return float(row.value) if row else None


def _risk_level(final_json: FinalControllerJson) -> str:
    if final_json.blocked_by:
        return "elevated"
    if final_json.confidence < 0.45:
        return "watch"
    return str(final_json.risk_state)


def _alert_level(final_json: FinalControllerJson) -> str:
    if "run_mode_integrity_invalidation" in final_json.blocked_by:
        return "warning"
    if final_json.blocked_by:
        return "info"
    return "normal"
