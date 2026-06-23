from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.constants import ANALYST_MODULES

SIGNAL_SCORES = {
    "bullish": 1.0,
    "bearish": -1.0,
    "mixed": 0.0,
    "neutral": 0.0,
}

IGNORABLE_PROVIDER_REQUIRED_GAPS = {
    "whale_flow",
    "miner_flow",
    "hibor",
    "regulatory_event_score",
}


def build_rule_baseline(
    pack_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        pack = _load_pack(session, pack_id)
        items = _pack_evidence_items(session, pack.pack_id)
    p2_items = [item for item in items if item.data.get("source_layer") == "p2_radar"]
    event_items = [item for item in items if item.data.get("source_layer") == "p3_event"]
    module_baselines = _module_baselines(p2_items)
    aggregate_score = _aggregate_signal_score(module_baselines)
    confidence_discount, discount_reasons = _confidence_discount(p2_items, event_items)
    risk_constraints = _risk_constraints(p2_items, event_items)
    analyst_context = _analyst_context(p2_items, event_items)
    baseline_confidence = max(0.0, min(1.0, 0.72 - confidence_discount))
    return {
        "status": "completed",
        "schema_version": "p4.rule_baseline.v1",
        "pack_id": pack.pack_id,
        "controller_run_id": pack.run_id,
        "aggregate_signal_score": round(aggregate_score, 4),
        "baseline_signal": _signal_from_score(aggregate_score),
        "baseline_confidence": round(baseline_confidence, 4),
        "confidence_discount": round(confidence_discount, 4),
        "confidence_discount_reasons": discount_reasons,
        "module_baselines": module_baselines,
        "risk_constraints": risk_constraints,
        "analyst_context": analyst_context,
        "coverage": {
            "p2_radar_evidence_count": len(p2_items),
            "p3_event_evidence_count": len(event_items),
            "missing_evidence_count": sum(
                1
                for item in p2_items
                if item.data.get("available") is False
                and not _is_ignorable_provider_required_gap(item)
            ),
            "ignored_provider_required_missing_count": sum(
                1 for item in p2_items if _is_provider_required_gap(item)
            ),
            "ignored_optional_context_missing_count": sum(
                1 for item in p2_items if _is_optional_context_gap(item)
            ),
            "low_quality_evidence_count": sum(
                1
                for item in p2_items
                if _quality_score(item) is not None and _quality_score(item) < 0.5
            ),
        },
    }


def _load_pack(session, pack_id: str | None) -> schema.EvidencePack:
    if pack_id:
        pack = session.scalar(
            select(schema.EvidencePack).where(schema.EvidencePack.pack_id == pack_id)
        )
    else:
        pack = session.scalar(
            select(schema.EvidencePack).order_by(schema.EvidencePack.created_at.desc())
        )
    if pack is None:
        raise RuntimeError("No P4 evidence pack found")
    return pack


def _pack_evidence_items(session, pack_id: str) -> list[schema.EvidenceItem]:
    return session.scalars(
        select(schema.EvidenceItem)
        .where(schema.EvidenceItem.pack_id == pack_id)
        .order_by(schema.EvidenceItem.evidence_id)
    ).all()


def _module_baselines(items: list[schema.EvidenceItem]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[schema.EvidenceItem]] = defaultdict(list)
    for item in items:
        grouped[item.module_id].append(item)
    baselines: dict[str, dict[str, Any]] = {}
    for module_id, module_items in grouped.items():
        signal_items = [
            item
            for item in module_items
            if item.data.get("affects_signal") is True and item.data.get("available") is not False
        ]
        score = _weighted_signal_score(signal_items)
        qualities = [
            score
            for score in (_quality_score(item) for item in module_items)
            if score is not None
        ]
        role_counts = Counter(str(item.data.get("role") or "unknown") for item in module_items)
        baselines[module_id] = {
            "signal_score": round(score, 4),
            "baseline_signal": _signal_from_score(score),
            "evidence_count": len(module_items),
            "signal_evidence_count": len(signal_items),
            "missing_count": sum(1 for item in module_items if item.data.get("available") is False),
            "avg_quality_score": round(mean(qualities), 4) if qualities else None,
            "role_counts": dict(role_counts),
            "evidence_ids": [item.evidence_id for item in module_items],
        }
    return baselines


def _weighted_signal_score(items: list[schema.EvidenceItem]) -> float:
    if not items:
        return 0.0
    weighted_scores = []
    weights = []
    for item in items:
        direction_score = SIGNAL_SCORES.get(str(item.direction), 0.0)
        quality = _quality_score(item)
        quality_weight = quality if quality is not None else 0.65
        strength = max(0.05, min(1.0, float(item.strength or 0.0)))
        weighted_scores.append(direction_score * strength * quality_weight)
        weights.append(strength)
    return sum(weighted_scores) / max(sum(weights), 0.0001)


def _aggregate_signal_score(module_baselines: dict[str, dict[str, Any]]) -> float:
    if not module_baselines:
        return 0.0
    return mean(float(module["signal_score"]) for module in module_baselines.values())


def _confidence_discount(
    p2_items: list[schema.EvidenceItem],
    event_items: list[schema.EvidenceItem],
) -> tuple[float, list[dict[str, Any]]]:
    reasons: list[dict[str, Any]] = []
    missing_items = [
        item
        for item in p2_items
        if item.data.get("available") is False
        and not _is_ignorable_provider_required_gap(item)
    ]
    low_quality_items = [
        item
        for item in p2_items
        if _quality_score(item) is not None and _quality_score(item) < 0.5
    ]
    fallback_items = [item for item in p2_items if item.data.get("fallback_reason")]
    monitor_events = [
        item
        for item in event_items
        if str(item.data.get("publish_impact") or "").lower() in {"monitor", "risk_lock"}
    ]
    _append_discount_reason(reasons, "missing_evidence", missing_items)
    _append_discount_reason(reasons, "low_quality_evidence", low_quality_items)
    _append_discount_reason(reasons, "fallback_used", fallback_items)
    _append_discount_reason(reasons, "event_publish_constraint", monitor_events)
    discount = min(
        0.65,
        len(missing_items) * 0.008
        + len(low_quality_items) * 0.012
        + len(fallback_items) * 0.004
        + len(monitor_events) * 0.02,
    )
    return discount, reasons


def _append_discount_reason(
    reasons: list[dict[str, Any]],
    reason: str,
    items: list[schema.EvidenceItem],
) -> None:
    if not items:
        return
    reasons.append(
        {
            "reason": reason,
            "count": len(items),
            "evidence_ids": [item.evidence_id for item in items[:12]],
        }
    )


def _risk_constraints(
    p2_items: list[schema.EvidenceItem],
    event_items: list[schema.EvidenceItem],
) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    risk_items = [
        item
        for item in p2_items
        if item.data.get("affects_risk_flags") is True and item.data.get("available") is not False
    ]
    if risk_items:
        constraints.append(
            {
                "constraint": "risk_context_present",
                "severity": "medium",
                "evidence_ids": [item.evidence_id for item in risk_items[:20]],
                "description": (
                    "Risk/event context evidence must be considered before Judge synthesis."
                ),
            }
        )
    for item in event_items:
        if item.data.get("event_phase") or item.data.get("publish_impact"):
            gate_level = _event_gate_level(item)
            constraints.append(
                {
                    "constraint": "event_window_publish_constraint",
                    "severity": "medium",
                    "gate_level": gate_level,
                    "event_type": item.data.get("event_type"),
                    "event_phase": item.data.get("event_phase"),
                    "publish_impact": item.data.get("publish_impact"),
                    "evidence_ids": [item.evidence_id],
                }
            )
    missing_signal_items = [
        item
        for item in p2_items
        if item.data.get("affects_signal") is True and item.data.get("available") is False
        and not _is_ignorable_provider_required_gap(item)
    ]
    if missing_signal_items:
        constraints.append(
            {
                "constraint": "missing_primary_signal_evidence",
                "severity": "high",
                "evidence_ids": [item.evidence_id for item in missing_signal_items[:20]],
                "description": "Primary signal gaps require confidence discount.",
            }
        )
    return constraints


def _analyst_context(
    p2_items: list[schema.EvidenceItem],
    event_items: list[schema.EvidenceItem],
) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {}
    for analyst_id in ANALYST_MODULES:
        items = [
            item for item in p2_items if item.data.get("assigned_analyst") == analyst_id
        ] + [item for item in event_items if item.data.get("assigned_analyst") == analyst_id]
        context[analyst_id] = {
            "evidence_count": len(items),
            "risk_constraint_count": sum(
                1 for item in items if item.data.get("affects_risk_flags") is True
            ),
            "missing_count": sum(
                1
                for item in items
                if item.data.get("available") is False
                and not _is_ignorable_provider_required_gap(item)
            ),
            "ignored_provider_required_missing_count": sum(
                1 for item in items if _is_provider_required_gap(item)
            ),
            "avg_quality_score": _avg_quality(items),
            "evidence_ids": [item.evidence_id for item in items],
        }
    return context


def _avg_quality(items: list[schema.EvidenceItem]) -> float | None:
    qualities = [score for score in (_quality_score(item) for item in items) if score is not None]
    return round(mean(qualities), 4) if qualities else None


def _quality_score(item: schema.EvidenceItem) -> float | None:
    value = item.data.get("quality_score")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_ignorable_provider_required_gap(item: schema.EvidenceItem) -> bool:
    return _is_optional_context_gap(item) or _is_provider_required_gap(item)


def _is_optional_context_gap(item: schema.EvidenceItem) -> bool:
    return (
        item.data.get("available") is False
        and item.data.get("affects_confidence") is False
        and item.data.get("affects_signal") is False
    )


def _is_provider_required_gap(item: schema.EvidenceItem) -> bool:
    metric_id = str(item.data.get("metric_id") or "")
    evidence_tier = str(item.data.get("evidence_tier") or "")
    return (
        item.data.get("available") is False
        and metric_id in IGNORABLE_PROVIDER_REQUIRED_GAPS
        and evidence_tier == "provider_required"
    )


def _event_gate_level(item: schema.EvidenceItem) -> str:
    publish_impact = str(item.data.get("publish_impact") or "").lower()
    event_phase = str(item.data.get("event_phase") or "").lower()
    if publish_impact in {"block_all_publish", "block_critical_publish"}:
        return publish_impact
    if event_phase in {"event_day", "t0", "t-0"}:
        return "block_critical_publish"
    if publish_impact in {"discount_confidence", "risk_lock"}:
        return "discount"
    return "watch"


def _signal_from_score(score: float) -> str:
    if score >= 0.18:
        return "bullish"
    if score <= -0.18:
        return "bearish"
    if abs(score) >= 0.08:
        return "mixed"
    return "neutral"
