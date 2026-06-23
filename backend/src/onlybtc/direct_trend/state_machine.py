from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.direct_trend.evidence import BTC_DIRECT_TREND_EVIDENCE_MODULE_ID
from onlybtc.direct_trend.registry import (
    BTC_DIRECT_EVIDENCE_REGISTRY_MODULE_ID,
    DirectEvidenceRegistryEntry,
    direct_evidence_registry,
)

BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID = "btc_direct_trend_state_machine"
BTC_DIRECT_TREND_STATE_MACHINE_SCHEMA_VERSION = "p3.c62.direct_trend_state_machine.v1"

DEFAULT_THRESHOLDS: dict[str, float] = {
    "strong_direction": 60.0,
    "trend_direction": 50.0,
    "acceptance": 60.0,
    "trust": 65.0,
    "weak_acceptance": 45.0,
    "event_cap": 65.0,
    "volatility_shock": 70.0,
    "agreement_categories": 3.0,
}


def build_direct_trend_state_machine(
    evidence_run_id: str | None = None,
    registry_run_id: str | None = None,
    state_run_id: str | None = None,
    thresholds: dict[str, float] | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    state_run_id = state_run_id or _generate_state_run_id()
    threshold_config = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    with db.session() as session:
        evidence_run_id = evidence_run_id or _latest_run_id(
            session,
            module_id=BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
            table="feature_values",
        )
        registry_run_id = registry_run_id or _latest_run_id(
            session,
            module_id=BTC_DIRECT_EVIDENCE_REGISTRY_MODULE_ID,
            table="module_json_outputs",
        )
        registry = _registry_from_payload(session, registry_run_id)
        evidence_rows = _evidence_rows(session, evidence_run_id) if evidence_run_id else []
        evidence = [_evidence_item(row, registry) for row in evidence_rows]
        freshness = _freshness_summary(evidence)
        h4 = _build_horizon_state("4h", evidence, freshness, threshold_config)
        h1d = _build_horizon_state("1d", evidence, freshness, threshold_config, h4_state=h4)
        payload = {
            "schema_version": BTC_DIRECT_TREND_STATE_MACHINE_SCHEMA_VERSION,
            "state_run_id": state_run_id,
            "evidence_run_id": evidence_run_id,
            "registry_run_id": registry_run_id,
            "asof_ts": datetime.now(UTC).isoformat(),
            "base_symbol": "BTCUSDT",
            "thresholds": threshold_config,
            "horizons": {"4h": h4, "1d": h1d},
            "freshness_summary": freshness,
            "source_fresh": _source_fresh(freshness),
            "missing_evidence": freshness["missing_evidence"],
            "stale_evidence": freshness["stale_evidence"],
            "blocked_evidence": freshness["blocked_evidence"],
        }
        session.add(
            schema.ModuleJsonOutput(
                run_id=state_run_id,
                module_id=BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID,
                schema_version=BTC_DIRECT_TREND_STATE_MACHINE_SCHEMA_VERSION,
                payload=payload,
            )
        )
    return payload


def _build_horizon_state(
    horizon: str,
    evidence: list[dict[str, Any]],
    freshness: dict[str, Any],
    thresholds: dict[str, float],
    h4_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items = [item for item in evidence if horizon in item.get("horizons", [])]
    trigger_items = _usable(items, role="trigger_eligible")
    acceptance_items = _usable(items, role="acceptance_gate")
    context_items = _usable(items, role="radar_context")
    trust_items = _usable(items, roles={"trust_cap", "quality_gate"})
    direction_score = _direction_score(trigger_items)
    acceptance = _acceptance(direction_score, acceptance_items)
    trust_score = _trust_score(trust_items, freshness)
    radar_context_bias = _clip(_avg([_score(item) for item in context_items]) * 15.0, -15.0, 15.0)
    display_score = direction_score * trust_score / 100.0
    agreement_categories = _agreement_categories(direction_score, trigger_items, acceptance_items)
    conflicts = _conflicts(direction_score, items)
    semantics = _semantics(items)
    blocked = _blocked_for_horizon(horizon, items)
    state = _state_for_horizon(
        horizon=horizon,
        direction_score=direction_score,
        acceptance_score=acceptance["score"],
        trust_score=trust_score,
        agreement_categories=agreement_categories,
        conflicts=conflicts,
        blocked=blocked,
        semantics=semantics,
        thresholds=thresholds,
        h4_state=h4_state,
    )
    return {
        "horizon": horizon,
        "state": state,
        "direction": _direction_label(direction_score),
        "direction_score": round(direction_score, 2),
        "acceptance_score": round(acceptance["score"], 2),
        "trust_score": round(trust_score, 2),
        "display_score": round(display_score, 2),
        "evidence_agreement": agreement_categories,
        "conflict_score": round(conflicts["score"], 2),
        "event_trust_cap": round(_event_trust_cap(trust_items), 2),
        "liquidity_trust_cap": 100.0,
        "data_quality_score": round(_data_quality_score(freshness), 2),
        "radar_context_bias": round(radar_context_bias, 2),
        "regime_trust": round(_regime_trust(context_items), 2),
        "acceptance": acceptance,
        "semantic_flags": semantics,
        "freshness_summary": _horizon_freshness(items),
        "evidence": _compact_evidence(items),
        "reason": _state_reason(state, direction_score, acceptance, trust_score, conflicts),
    }


def _state_for_horizon(
    horizon: str,
    direction_score: float,
    acceptance_score: float,
    trust_score: float,
    agreement_categories: int,
    conflicts: dict[str, Any],
    blocked: bool,
    semantics: list[str],
    thresholds: dict[str, float],
    h4_state: dict[str, Any] | None,
) -> str:
    if blocked:
        return "blocked"
    event_capped = trust_score < thresholds["event_cap"]
    volatility = any(flag in semantics for flag in ("liquidation_shock", "volatility_shock"))
    if horizon == "4h":
        if event_capped:
            return "event_distorted"
        if volatility:
            return "volatility_shock"
        if abs(direction_score) >= thresholds["strong_direction"]:
            if conflicts["opposed_acceptance"] > 0 and acceptance_score < thresholds["weak_acceptance"]:
                return "fast_trend_rejection"
            if (
                trust_score >= thresholds["trust"]
                and acceptance_score >= thresholds["acceptance"]
                and agreement_categories >= thresholds["agreement_categories"]
            ):
                return "fast_trend_acceptance"
            return "impulse_watch"
        if abs(direction_score) >= thresholds["trend_direction"]:
            return "breakout_testing"
        if "btc_resilient" in semantics:
            return "absorption_after_sweep"
        return "range_chop"

    if event_capped:
        return "macro_event_capped"
    if "crowded_long_rejection" in semantics:
        return "crowded_long_risk"
    if "btc_resilient" in semantics and direction_score >= 0:
        return "pullback_in_uptrend"
    if abs(direction_score) >= thresholds["trend_direction"]:
        h4_accepted = (h4_state or {}).get("state") == "fast_trend_acceptance"
        if acceptance_score >= thresholds["acceptance"] and trust_score >= thresholds["trust"]:
            return "trend_accepted"
        if conflicts["score"] >= 35:
            return "trend_fragile"
        if h4_accepted:
            return "trend_building"
        return "trend_fragile"
    if (h4_state or {}).get("state") == "fast_trend_acceptance":
        return "trend_building"
    return "range_compression_before_expansion"


def _direction_score(items: list[dict[str, Any]]) -> float:
    scores = [_score(item) * 100.0 for item in items if item.get("affects_direction")]
    if not scores:
        return 0.0
    return _clip(sum(scores) / len(scores), -100.0, 100.0)


def _acceptance(direction_score: float, items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items or direction_score == 0:
        return {"score": 0.0, "aligned": 0, "opposed": 0, "total": len(items)}
    sign = 1 if direction_score > 0 else -1
    aligned = 0
    opposed = 0
    strength = 0.0
    for item in items:
        score = _score(item)
        if score * sign >= 0.05:
            aligned += 1
            strength += min(abs(score) * 100.0, 100.0)
        elif score * sign <= -0.05:
            opposed += 1
    total = max(len(items), 1)
    raw = (aligned / total) * 70.0 + (strength / total) * 0.3 - opposed * 15.0
    return {
        "score": _clip(raw, 0.0, 100.0),
        "aligned": aligned,
        "opposed": opposed,
        "total": len(items),
    }


def _trust_score(items: list[dict[str, Any]], freshness: dict[str, Any]) -> float:
    caps = []
    for item in items:
        value = item.get("value")
        feature_id = str(item.get("feature_id") or "")
        is_numeric_trust_cap = feature_id.endswith(
            ("event_trust_cap", "ordinary_radar_trust", "trade_permission_modifier")
        )
        if item["role"] == "trust_cap" and is_numeric_trust_cap and isinstance(value, (int, float)):
            caps.append(_clip(float(value) * 100.0 if abs(float(value)) <= 1 else float(value), 0, 100))
        if item["role"] == "quality_gate" and str(item.get("feature_id", "")).endswith("emergency_level"):
            caps.append(max(35.0, 100.0 - float(value or 0.0) * 25.0))
    trust = min(caps) if caps else 100.0
    trust -= len(freshness["stale_evidence"]) * 3.0
    trust -= len(freshness["missing_evidence"]) * 5.0
    return _clip(trust, 0.0, 100.0)


def _freshness_summary(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    missing = []
    stale = []
    blocked = []
    for item in evidence:
        state = item.get("freshness_state")
        feature_id = item["feature_id"]
        if state == "missing":
            missing.append(feature_id)
        if state in {"stale", "blocked"}:
            stale.append(feature_id)
        if state in {"missing", "stale", "blocked"} and item.get("blocking_level") in {
            "block_confirmed",
            "block_all",
        }:
            blocked.append(feature_id)
    return {
        "missing_evidence": missing,
        "stale_evidence": stale,
        "blocked_evidence": blocked,
        "fresh_count": sum(1 for item in evidence if item.get("freshness_state") == "fresh"),
        "partial_count": sum(1 for item in evidence if item.get("freshness_state") == "partial"),
        "total_count": len(evidence),
    }


def _source_fresh(freshness: dict[str, Any]) -> bool | str:
    if freshness["blocked_evidence"] or freshness["stale_evidence"]:
        return False
    if freshness["missing_evidence"] or freshness["partial_count"]:
        return "partial"
    return True


def _evidence_item(
    row: schema.FeatureValue,
    registry: dict[str, DirectEvidenceRegistryEntry],
) -> dict[str, Any]:
    metadata = row.metadata_json or {}
    entry = registry.get(row.feature_id)
    if entry is None:
        return {
            "feature_id": row.feature_id,
            "registered": False,
            "role": "unregistered",
            "horizons": [],
            "value": row.value,
            "score": _coerce_score(metadata.get("feature_score"), row.value),
            "freshness_state": metadata.get("freshness_state", "missing"),
            "blocking_level": "block_all",
            "affects_direction": False,
            "semantic_state": metadata.get("semantic_state"),
            "category": metadata.get("category"),
        }
    return {
        "feature_id": row.feature_id,
        "registered": True,
        "role": entry.role,
        "horizons": list(entry.horizons),
        "required_for": list(entry.required_for),
        "value": row.value,
        "score": _coerce_score(metadata.get("feature_score"), row.value),
        "freshness_state": metadata.get("freshness_state", "missing"),
        "blocking_level": entry.blocking_level,
        "fallback_policy": entry.fallback_policy,
        "affects_direction": entry.affects_direction,
        "affects_confidence": entry.affects_confidence,
        "direction_semantics": entry.direction_semantics,
        "semantic_state": metadata.get("semantic_state"),
        "category": metadata.get("category"),
        "source_asof_ts": metadata.get("source_asof_ts"),
        "valid_until": metadata.get("valid_until"),
    }


def _registry_from_payload(
    session,
    registry_run_id: str | None,
) -> dict[str, DirectEvidenceRegistryEntry]:
    if registry_run_id:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == registry_run_id,
                schema.ModuleJsonOutput.module_id == BTC_DIRECT_EVIDENCE_REGISTRY_MODULE_ID,
            )
        )
        if row and isinstance(row.payload, dict):
            entries = row.payload.get("entries")
            if isinstance(entries, list) and entries:
                return {
                    str(item["feature_id"]): DirectEvidenceRegistryEntry(
                        feature_id=str(item["feature_id"]),
                        role=str(item["role"]),
                        horizons=tuple(item.get("horizons") or ()),
                        freshness_tier=str(item["freshness_tier"]),
                        direction_semantics=str(item["direction_semantics"]),
                        source_cadence=str(item["source_cadence"]),
                        expected_update_sec=int(item["expected_update_sec"]),
                        stale_after_sec=int(item["stale_after_sec"]),
                        blocking_level=str(item["blocking_level"]),
                        fallback_policy=str(item["fallback_policy"]),
                        required_for=tuple(item.get("required_for") or ()),
                        affects_direction=bool(item["affects_direction"]),
                        affects_confidence=bool(item["affects_confidence"]),
                        notes=str(item.get("notes") or ""),
                        event_phase_roles=dict(item.get("event_phase_roles") or {}),
                    )
                    for item in entries
                }
    return direct_evidence_registry()


def _latest_run_id(session, module_id: str, table: str) -> str | None:
    model = schema.FeatureValue if table == "feature_values" else schema.ModuleJsonOutput
    run_col = model.run_id
    return session.scalar(
        select(run_col)
        .where(model.module_id == module_id)
        .group_by(run_col)
        .having(func.count(model.id) > 0)
        .order_by(func.max(model.created_at).desc())
        .limit(1)
    )


def _evidence_rows(session, evidence_run_id: str) -> list[schema.FeatureValue]:
    return session.scalars(
        select(schema.FeatureValue)
        .where(
            schema.FeatureValue.run_id == evidence_run_id,
            schema.FeatureValue.module_id == BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
        )
        .order_by(schema.FeatureValue.feature_id)
    ).all()


def _usable(
    items: list[dict[str, Any]],
    role: str | None = None,
    roles: set[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = roles or ({role} if role else set())
    return [
        item
        for item in items
        if item.get("role") in allowed and item.get("freshness_state") not in {"missing", "stale", "blocked"}
    ]


def _score(item: dict[str, Any]) -> float:
    return _clip(float(item.get("score") or 0.0), -1.0, 1.0)


def _coerce_score(score: Any, value: Any) -> float:
    if isinstance(score, (int, float)):
        return _clip(float(score), -1.0, 1.0)
    if isinstance(value, (int, float)):
        numeric = float(value)
        if abs(numeric) <= 1.0:
            return _clip(numeric, -1.0, 1.0)
        return _clip(numeric / 100.0, -1.0, 1.0)
    return 0.0


def _agreement_categories(
    direction_score: float,
    trigger_items: list[dict[str, Any]],
    acceptance_items: list[dict[str, Any]],
) -> int:
    if direction_score == 0:
        return 0
    sign = 1 if direction_score > 0 else -1
    categories = {
        item.get("category")
        for item in [*trigger_items, *acceptance_items]
        if item.get("category") and _score(item) * sign > 0.05
    }
    return len(categories)


def _conflicts(direction_score: float, items: list[dict[str, Any]]) -> dict[str, Any]:
    if direction_score == 0:
        return {"score": 0.0, "opposed_acceptance": 0, "opposed_features": []}
    sign = 1 if direction_score > 0 else -1
    opposed = [
        item
        for item in items
        if item.get("role") in {"acceptance_gate", "radar_context"} and _score(item) * sign < -0.05
    ]
    return {
        "score": _clip(len(opposed) * 20.0, 0.0, 100.0),
        "opposed_acceptance": sum(1 for item in opposed if item.get("role") == "acceptance_gate"),
        "opposed_features": [item["feature_id"] for item in opposed],
    }


def _semantics(items: list[dict[str, Any]]) -> list[str]:
    flags = set()
    for item in items:
        state = item.get("semantic_state")
        if state:
            flags.add(str(state))
        if item["feature_id"].endswith("residual_semantic") and state in {
            "external_pressure_down_but_btc_resilient",
            "risk_assets_down_but_btc_absorbing",
        }:
            flags.add("btc_resilient")
        if item["feature_id"].endswith("liquidation_followthrough_score") and abs(float(item.get("value") or 0)) >= 70:
            flags.add("liquidation_shock")
    return sorted(flags)


def _blocked_for_horizon(horizon: str, items: list[dict[str, Any]]) -> bool:
    del horizon
    return any(
        item.get("freshness_state") in {"missing", "stale", "blocked"}
        and item.get("blocking_level") == "block_all"
        for item in items
    )


def _event_trust_cap(items: list[dict[str, Any]]) -> float:
    trust_caps = [
        float(item.get("value"))
        for item in items
        if item["feature_id"].endswith("event_trust_cap") and isinstance(item.get("value"), (int, float))
    ]
    if not trust_caps:
        return 100.0
    value = min(trust_caps)
    return _clip(value * 100.0 if abs(value) <= 1 else value, 0.0, 100.0)


def _data_quality_score(freshness: dict[str, Any]) -> float:
    total = max(int(freshness.get("total_count") or 0), 1)
    penalty = len(freshness["missing_evidence"]) * 8 + len(freshness["stale_evidence"]) * 10
    penalty += len(freshness["blocked_evidence"]) * 12
    return _clip(100.0 - penalty / total, 0.0, 100.0)


def _regime_trust(items: list[dict[str, Any]]) -> float:
    regime = [abs(_score(item)) * 100.0 for item in items if item.get("freshness_state") == "fresh"]
    return _clip(_avg(regime), 0.0, 100.0)


def _horizon_freshness(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "missing_evidence": [item["feature_id"] for item in items if item.get("freshness_state") == "missing"],
        "stale_evidence": [item["feature_id"] for item in items if item.get("freshness_state") in {"stale", "blocked"}],
        "blocked_evidence": [
            item["feature_id"]
            for item in items
            if item.get("freshness_state") in {"missing", "stale", "blocked"}
            and item.get("blocking_level") in {"block_confirmed", "block_all"}
        ],
    }


def _compact_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "feature_id": item["feature_id"],
            "role": item["role"],
            "score": round(_score(item), 4),
            "value": item.get("value"),
            "freshness_state": item.get("freshness_state"),
            "semantic_state": item.get("semantic_state"),
            "source_asof_ts": item.get("source_asof_ts"),
            "valid_until": item.get("valid_until"),
        }
        for item in items
    ]


def _state_reason(
    state: str,
    direction_score: float,
    acceptance: dict[str, Any],
    trust_score: float,
    conflicts: dict[str, Any],
) -> str:
    return (
        f"{state}: direction={direction_score:.1f}, acceptance={acceptance['score']:.1f}, "
        f"trust={trust_score:.1f}, conflicts={conflicts['score']:.1f}."
    )


def _direction_label(score: float) -> str:
    if score >= 15:
        return "bullish"
    if score <= -15:
        return "bearish"
    return "neutral"


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _generate_state_run_id() -> str:
    return f"p3c62-state-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
