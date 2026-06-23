from __future__ import annotations

from typing import Any

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.rule_baseline import build_rule_baseline


def run_state_machine(
    pack_id: str | None = None,
    baseline: dict[str, Any] | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    baseline = baseline or build_rule_baseline(pack_id=pack_id, db=db)
    run_id = str(baseline["controller_run_id"])
    with db.session() as session:
        invalidations = _invalidation_events(session, run_id)
    constraints = list(baseline.get("risk_constraints") or [])
    constraints.extend(_invalidation_constraints(invalidations))
    blocked_by = _blocked_by(constraints, baseline)
    critical_publish_allowed = not blocked_by and baseline["baseline_confidence"] >= 0.62
    trend_state = _trend_state(
        signal=str(baseline["baseline_signal"]),
        confidence=float(baseline["baseline_confidence"]),
        blocked_by=blocked_by,
    )
    risk_state = _risk_state(
        baseline=baseline,
        constraints=constraints,
        blocked_by=blocked_by,
        critical_publish_allowed=critical_publish_allowed,
    )
    transition_allowed = critical_publish_allowed and trend_state in {
        "bullish_candidate",
        "bearish_candidate",
    }
    publish_allowed = critical_publish_allowed
    return {
        "status": "completed",
        "schema_version": "p4.state_machine.v1",
        "pack_id": baseline["pack_id"],
        "controller_run_id": run_id,
        "baseline_signal": baseline["baseline_signal"],
        "baseline_confidence": baseline["baseline_confidence"],
        "trend_state": trend_state,
        "risk_state": risk_state,
        "state_transition_allowed": transition_allowed,
        "critical_publish_allowed": critical_publish_allowed,
        "analysis_output_allowed": True,
        "publish_allowed": publish_allowed,
        "blocked_by": blocked_by,
        "state_transition_reason": _transition_reason(
            baseline=baseline,
            trend_state=trend_state,
            risk_state=risk_state,
            blocked_by=blocked_by,
            transition_allowed=transition_allowed,
        ),
        "state_machine_constraints_applied": constraints,
        "evidence_ids": _constraint_evidence_ids(constraints),
        "invalidation_events": invalidations,
    }


def _invalidation_events(session, run_id: str) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(schema.InvalidationEvent).where(schema.InvalidationEvent.run_id == run_id)
    ).all()
    return [
        {
            "condition_id": row.condition_id,
            "run_id": row.run_id,
            "status": row.status,
            "action": row.action,
            "payload": row.payload or {},
        }
        for row in rows
        if row.status in {"triggered", "near_triggered"}
    ]


def _invalidation_constraints(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    for event in events:
        action = str(event.get("action") or "")
        severity = "high" if event.get("status") == "triggered" else "medium"
        constraint = {
            "constraint": "p3_invalidation",
            "severity": severity,
            "condition_id": event.get("condition_id"),
            "status": event.get("status"),
            "action": action,
            "publish_impact": (event.get("payload") or {}).get("publish_impact"),
            "evidence_ids": [],
        }
        if action == "block_critical_publish":
            constraint["constraint"] = "run_mode_or_p3_block_critical"
            constraint["severity"] = "critical"
        constraints.append(constraint)
    return constraints


def _blocked_by(
    constraints: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> list[str]:
    blocked: list[str] = []
    if float(baseline["baseline_confidence"]) < 0.5:
        blocked.append("low_baseline_confidence")
    for constraint in constraints:
        name = str(constraint.get("constraint") or "")
        severity = str(constraint.get("severity") or "")
        action = str(constraint.get("action") or "")
        publish_impact = str(constraint.get("publish_impact") or "")
        gate_level = str(constraint.get("gate_level") or "")
        if name == "missing_primary_signal_evidence" and gate_level not in {"watch", "discount"}:
            blocked.append("missing_primary_signal_evidence")
        if name == "event_window_publish_constraint" and gate_level in {
            "block_critical_publish",
            "block_all_publish",
        }:
            blocked.append("event_window_publish_constraint")
        if severity == "critical" or action == "block_critical_publish":
            blocked.append(str(constraint.get("condition_id") or name))
        if publish_impact in {"block_critical_publish", "block_all_publish"}:
            blocked.append(str(constraint.get("condition_id") or name))
    return sorted(set(blocked))


def _trend_state(signal: str, confidence: float, blocked_by: list[str]) -> str:
    if blocked_by:
        return "constrained_watch"
    if confidence < 0.5:
        return "insufficient_confidence"
    if signal == "bullish":
        return "bullish_candidate"
    if signal == "bearish":
        return "bearish_candidate"
    if signal == "mixed":
        return "mixed_watch"
    return "neutral_watch"


def _risk_state(
    baseline: dict[str, Any],
    constraints: list[dict[str, Any]],
    blocked_by: list[str],
    critical_publish_allowed: bool,
) -> str:
    if blocked_by:
        if any("event_window" in item for item in blocked_by):
            return "event_watch"
        return "warning"
    if not critical_publish_allowed:
        return "watch"
    if abs(float(baseline["aggregate_signal_score"])) >= 0.35:
        return "warning"
    if constraints:
        return "watch"
    return "normal"


def _transition_reason(
    baseline: dict[str, Any],
    trend_state: str,
    risk_state: str,
    blocked_by: list[str],
    transition_allowed: bool,
) -> str:
    if transition_allowed:
        return (
            f"State transition allowed: baseline_signal={baseline['baseline_signal']}, "
            f"confidence={baseline['baseline_confidence']}."
        )
    if blocked_by:
        return (
            f"State transition constrained by {', '.join(blocked_by)}; "
            f"trend_state={trend_state}, risk_state={risk_state}."
        )
    return (
        f"No aggressive transition: baseline_signal={baseline['baseline_signal']}, "
        f"confidence={baseline['baseline_confidence']}, risk_state={risk_state}."
    )


def _constraint_evidence_ids(constraints: list[dict[str, Any]]) -> list[str]:
    evidence_ids: list[str] = []
    for constraint in constraints:
        evidence_ids.extend(str(item) for item in constraint.get("evidence_ids") or [])
    return sorted(set(evidence_ids))
