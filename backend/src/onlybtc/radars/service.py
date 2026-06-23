from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.radars.models import RadarMetricRule, RadarModule, Signal
from onlybtc.radars.registry import RADAR_MODULES, radar_metric_contract
from onlybtc.sources.service import historical_window


def analyze_radars(
    module_ids: list[str] | None = None,
    run_id: str | None = None,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    selected = [
        module
        for module in RADAR_MODULES
        if module_ids is None or module.module_id in set(module_ids)
    ]
    run_id = run_id or f"radar-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    outputs = [
        _analyze_module(
            module,
            run_id,
            db,
            run_mode,
            collect_run_id=collect_run_id,
            historical_fallback=historical_fallback,
        )
        for module in selected
    ]

    with db.session() as session:
        for output in outputs:
            _persist_radar_output(session, output)

    return {
        "run_id": run_id,
        "analyzed": len(outputs),
        "modules": [
            {
                "module_id": item["module_id"],
                "signal": item["signal"],
                "strength": item["strength"],
                "confidence": item["confidence"],
                "data_quality": item["data_quality"],
            }
            for item in outputs
        ],
        "collect_run_id": collect_run_id,
        "historical_fallback": historical_fallback,
    }


def latest_radar_outputs(db: Database = database) -> list[dict[str, Any]]:
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.RadarOutput).order_by(schema.RadarOutput.created_at.desc()).limit(20)
        ).all()
    return [_model_dict(row) for row in rows]


def _analyze_module(
    module: RadarModule,
    run_id: str,
    db: Database,
    run_mode: str,
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
) -> dict[str, Any]:
    metric_windows = {
        rule.metric_id: historical_window(
            rule.metric_id,
            run_mode=run_mode,
            collect_run_id=collect_run_id,
            historical_fallback=historical_fallback,
            db=db,
        )
        for rule in module.metrics
    }
    contributions = [
        _metric_contribution(module, rule, metric_windows[rule.metric_id])
        for rule in module.metrics
    ]
    usable = [item for item in contributions if item["available"]]
    scoring_usable = [item for item in usable if item["affects_signal"]]
    net_score = sum(item["score"] for item in usable)
    signal = _signal_from_score(net_score, scoring_usable)
    strength = min(abs(net_score), 1.0)
    quality_relevant = [item for item in contributions if item["quality_blocking"]]
    quality_usable = [item for item in usable if item["quality_blocking"]]
    if not quality_relevant and usable:
        quality_usable = usable
    raw_coverage = len(usable) / len(module.metrics) if module.metrics else 0
    coverage = len(quality_usable) / len(quality_relevant) if quality_relevant else raw_coverage
    current_run_usable = [
        item for item in quality_usable if item.get("feature_run_scope") == "current_run"
    ]
    same_run_coverage = (
        len(current_run_usable) / len(quality_relevant)
        if quality_relevant and collect_run_id
        else 1.0
    )
    quality_detail = _radar_quality_detail(
        coverage,
        quality_usable,
        raw_coverage=raw_coverage,
        same_run_coverage=same_run_coverage,
    )
    avg_quality = quality_detail["overall_score"]
    confidence = round(min(0.95, 0.35 + strength * 0.35 + coverage * 0.2 + avg_quality * 0.1), 3)
    module_semantics = _module_semantics(module.module_id, contributions)
    return {
        "run_id": run_id,
        "module_id": module.module_id,
        "signal": signal,
        "strength": round(strength, 3),
        "confidence": confidence,
        "data_quality": _quality_label(avg_quality, coverage),
        "features": contributions,
        "evidence_summary": {
            "module_name": module.name,
            "net_score": round(net_score, 4),
            "quality_explanation": quality_detail,
            "supporting": [
                item for item in scoring_usable if item["direction"] == signal
            ],
            "context_metrics": [
                item
                for item in usable
                if item["role"] != "primary_signal" or not item["affects_signal"]
            ],
        },
        "conflicting_evidence": {
            "items": [
                item
                for item in usable
                if item["affects_signal"]
                and item["direction"] not in {signal, "neutral"}
                and signal != "mixed"
            ],
            "source_conflicts": [
                item["conflict"]
                for item in usable
                if item.get("conflict", {}).get("detected")
            ],
        },
        "risk_flags": _risk_flags(module.module_id, usable),
        "invalidation_signals": {
            "missing_metrics": [
                item["metric_id"]
                for item in contributions
                if not item["available"] and item["quality_blocking"]
            ],
            "provider_required_metrics": [
                item["metric_id"]
                for item in contributions
                if not item["available"] and item["evidence_tier"] == "provider_required"
            ],
            "context_unavailable_metrics": [
                item["metric_id"]
                for item in contributions
                if not item["available"]
                and not item["quality_blocking"]
                and item["evidence_tier"] != "provider_required"
            ],
            "stale_metrics": [
                item["metric_id"]
                for item in contributions
                if item.get("collection_freshness_status") == "stale"
            ],
            "expired_metrics": [
                item["metric_id"]
                for item in contributions
                if item.get("collection_freshness_status") == "expired"
            ],
            "business_lagging_metrics": [
                item["metric_id"]
                for item in contributions
                if item.get("business_recency_status")
                in {"lagging", "outdated", "provider_stale_suspect"}
            ],
            "low_coverage": coverage < 0.7,
        },
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "historical_fallback": historical_fallback,
        "non_production": run_mode != "live",
        **module_semantics,
    }


def _metric_contribution(
    module: RadarModule,
    rule: RadarMetricRule,
    window: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence_tier = _metric_evidence_tier(module.module_id, rule.metric_id)
    quality_blocking = rule.affects_confidence and evidence_tier != "provider_required"
    contract = radar_metric_contract(module.module_id, rule)
    if window is None or window.get("current") is None:
        return {
            "metric_id": rule.metric_id,
            **contract,
            "available": False,
            "score": 0.0,
            "direction": "neutral",
            "quality_score": 0.0,
            "source_run_id": None,
            "feature_run_scope": "provider_required"
            if evidence_tier == "provider_required"
            else "missing",
            "current_run_has_value": False,
            "fallback_age_seconds": None,
            "fallback_reason": None,
            "role": rule.role,
            "affects_signal": rule.affects_signal,
            "affects_confidence": rule.affects_confidence,
            "affects_risk_flags": rule.affects_risk_flags,
            "driver_eligible": rule.driver_eligible,
            "evidence_tier": evidence_tier,
            "quality_blocking": quality_blocking,
        }
    if window.get("collection_freshness_status", window.get("freshness_status")) == "expired":
        return {
            "metric_id": rule.metric_id,
            **contract,
            "available": False,
            "score": 0.0,
            "direction": "neutral",
            "quality_score": 0.0,
            "source_id": window.get("source_id"),
            "source_run_id": window.get("source_run_id"),
            "feature_run_scope": window.get("feature_run_scope", "unspecified_history"),
            "current_run_has_value": window.get("current_run_has_value", False),
            "fallback_age_seconds": window.get("fallback_age_seconds"),
            "fallback_reason": window.get("fallback_reason"),
            "role": rule.role,
            "affects_signal": rule.affects_signal,
            "affects_confidence": rule.affects_confidence,
            "affects_risk_flags": rule.affects_risk_flags,
            "driver_eligible": rule.driver_eligible,
            "freshness_status": "expired",
            "collection_freshness_status": "expired",
            "business_recency_status": window.get("business_recency_status"),
            "source_ts": window.get("source_ts"),
            "collected_at": window.get("collected_at"),
            "freshness_minutes": window.get("freshness_minutes"),
            "stale_after_minutes": window.get("stale_after_minutes"),
            "is_stale": window.get("is_stale"),
            "selected_reason": window.get("selected_reason"),
            "candidates": window.get("candidates", []),
            "conflict": window.get("conflict"),
            "evidence_tier": evidence_tier,
            "quality_blocking": quality_blocking,
        }

    change = window.get("change_24h")
    current = float(window["current"])
    raw_change = _effective_change(current, change, window.get("ma_30d"))
    magnitude = min(abs(raw_change) * 4, 1.0) if rule.change_sensitive else 0.2
    if rule.metric_id == "btc_funding_rate":
        magnitude = min(abs(current) * 4000, 1.0)
    if rule.metric_id == "btc_open_interest" and change is None:
        magnitude = 0.35

    direction = _direction(rule, raw_change, current)
    sign = 1 if direction == "bullish" else -1 if direction == "bearish" else 0
    score = sign * rule.weight * max(magnitude, 0.05) if rule.affects_signal else 0.0
    semantic_overlay = _metric_semantic_overlay(rule, current, change, score, direction)
    score = float(semantic_overlay.pop("score", score))
    direction = semantic_overlay.pop("direction", direction)
    return {
        "metric_id": rule.metric_id,
        **contract,
        "available": True,
        "current": current,
        "change_24h": change,
        "score": round(score, 4),
        "direction": direction,
        "weight": rule.weight,
        "role": rule.role,
        "affects_signal": rule.affects_signal,
        "affects_confidence": rule.affects_confidence,
        "affects_risk_flags": rule.affects_risk_flags,
        "driver_eligible": rule.driver_eligible,
        "quality_score": float(
            window.get("effective_quality_score") or window.get("quality_score") or 0.0
        ),
        "freshness_status": window.get("freshness_status"),
        "collection_freshness_status": window.get(
            "collection_freshness_status",
            window.get("freshness_status"),
        ),
        "business_recency_status": window.get("business_recency_status"),
        "freshness_policy": window.get("freshness_policy"),
        "source_ts": window.get("source_ts"),
        "collected_at": window.get("collected_at"),
        "freshness_minutes": window.get("freshness_minutes"),
        "stale_after_minutes": window.get("stale_after_minutes"),
        "is_stale": window.get("is_stale"),
        "source_id": window.get("source_id"),
        "source_run_id": window.get("source_run_id"),
        "feature_run_scope": window.get("feature_run_scope", "unspecified_history"),
        "current_run_has_value": window.get("current_run_has_value", False),
        "fallback_age_seconds": window.get("fallback_age_seconds"),
        "fallback_reason": window.get("fallback_reason"),
        "selected_reason": window.get("selected_reason"),
        "candidates": window.get("candidates", []),
        "conflict": window.get("conflict"),
        "evidence_tier": evidence_tier,
        "quality_blocking": quality_blocking,
        **semantic_overlay,
    }


def _metric_semantic_overlay(
    rule: RadarMetricRule,
    current: float,
    change: Any,
    score: float,
    direction: Signal,
) -> dict[str, Any]:
    if rule.metric_id not in {"etf_net_flow", "etf_net_flow_usd", "etf_flow_7d", "etf_flow_7d_usd"}:
        return {}

    flow_state = (
        "bullish_inflow" if current > 0 else "bearish_outflow" if current < 0 else "neutral"
    )
    absolute_direction: Signal = (
        "bullish" if current > 0 else "bearish" if current < 0 else "neutral"
    )
    absolute_score = abs(float(score))
    signed_score = (
        absolute_score if absolute_direction == "bullish"
        else -absolute_score if absolute_direction == "bearish"
        else 0.0
    )
    marginal_state, marginal_direction = _etf_marginal_state(current, change)
    return {
        "direction": absolute_direction,
        "score": round(signed_score, 4),
        "flow_state": flow_state,
        "marginal_state": marginal_state,
        "marginal_direction": marginal_direction,
        "semantic_rule_id": (
            "p2.etf_flow.absolute_positive"
            if absolute_direction == "bullish"
            else "p2.etf_flow.absolute_negative"
            if absolute_direction == "bearish"
            else "p2.etf_flow.neutral"
        ),
        "semantic_warning": (
            "ETF outflow easing is pressure_easing/improving, not bullish demand."
            if flow_state == "bearish_outflow" and marginal_state == "pressure_easing"
            else None
        ),
    }


def _etf_marginal_state(current: float, change: Any) -> tuple[str | None, str]:
    if change in {None, 0}:
        return "stable", "stable"
    change_value = float(change)
    if current < 0:
        if change_value > 0:
            return "pressure_easing", "improving"
        if change_value < 0:
            return "pressure_worsening", "worsening"
    if current > 0:
        if change_value > 0:
            return "inflow_strengthening", "strengthening"
        if change_value < 0:
            return "inflow_weakening", "weakening"
    return "stable", "stable"


def _module_semantics(module_id: str, contributions: list[dict[str, Any]]) -> dict[str, Any]:
    if module_id != "fund_flow":
        return {}
    etf_items = [
        item
        for item in contributions
        if item.get("metric_id") in {"etf_net_flow", "etf_net_flow_usd", "etf_flow_7d", "etf_flow_7d_usd"}
        and item.get("available")
    ]
    etf_score = sum(
        1.0 if float(item.get("current") or 0.0) > 0 else -1.0 if float(item.get("current") or 0.0) < 0 else 0.0
        for item in etf_items
    )
    absolute_direction = _direction_from_score(etf_score)
    marginal_direction = _fund_flow_marginal_direction(contributions)
    exchange_support = sum(
        float(item.get("current") or 0.0)
        for item in contributions
        if item.get("metric_id") in {"exchange_balance_delta_1d_proxy", "btc_exchange_netflow_z_60d"}
        and item.get("available")
    )
    conflict = (
        absolute_direction == "bearish"
        and (marginal_direction == "improving" or exchange_support > 0.03)
    ) or (
        absolute_direction == "bullish"
        and marginal_direction in {"weakening", "worsening"}
    )
    return {
        "fund_flow_profile_version": "p2.c33.fund_flow.registry.v2.2",
        "fund_flow_absolute_direction": absolute_direction,
        "fund_flow_marginal_direction": marginal_direction,
        "fund_flow_conflict_level": "high" if conflict else "low",
        "fund_flow_state": _fund_flow_module_state(absolute_direction, marginal_direction),
    }


def _fund_flow_marginal_direction(contributions: list[dict[str, Any]]) -> str:
    marginal_states = {
        str(item.get("marginal_state"))
        for item in contributions
        if item.get("metric_id") in {"etf_net_flow", "etf_net_flow_usd", "etf_flow_7d", "etf_flow_7d_usd"}
        and item.get("marginal_state")
    }
    if "pressure_easing" in marginal_states:
        return "improving"
    if "pressure_worsening" in marginal_states:
        return "worsening"
    if "inflow_strengthening" in marginal_states:
        return "strengthening"
    if "inflow_weakening" in marginal_states:
        return "weakening"
    exchange_support = sum(
        float(item.get("current") or 0.0)
        for item in contributions
        if item.get("metric_id") in {"exchange_balance_delta_1d_proxy", "btc_exchange_netflow_z_60d"}
        and item.get("available")
    )
    if exchange_support < -0.03:
        return "improving"
    if exchange_support > 0.03:
        return "worsening"
    return "stable"


def _fund_flow_module_state(absolute_direction: str, marginal_direction: str) -> str:
    if absolute_direction == "bearish" and marginal_direction == "improving":
        return "bearish_but_improving"
    if absolute_direction == "bullish" and marginal_direction in {"weakening", "worsening"}:
        return "bullish_but_weakening"
    if absolute_direction == "bearish" and marginal_direction == "worsening":
        return "bearish"
    if absolute_direction == "bullish" and marginal_direction in {"improving", "strengthening"}:
        return "bullish"
    return "neutral_mixed"


def _direction_from_score(score: float) -> Signal:
    if score > 0.03:
        return "bullish"
    if score < -0.03:
        return "bearish"
    return "neutral"


def _direction(rule: RadarMetricRule, change: float, current: float) -> Signal:
    if rule.higher_is == "neutral":
        return "neutral"
    if rule.higher_is == "mixed":
        return "mixed"
    if rule.metric_id == "btc_funding_rate" and current > 0.0003:
        return "bearish"
    if change == 0:
        return "neutral"
    if rule.higher_is == "bullish":
        return "bullish" if change > 0 else "bearish"
    return "bearish" if change > 0 else "bullish"


def _effective_change(current: float, change: Any, ma_30d: Any) -> float:
    if change not in {None, 0}:
        return float(change)
    if ma_30d in {None, 0}:
        return 0.0
    return (current - float(ma_30d)) / abs(float(ma_30d))


def _signal_from_score(net_score: float, usable: list[dict[str, Any]]) -> Signal:
    if not usable:
        return "neutral"
    if abs(net_score) < 0.08:
        return "mixed"
    return "bullish" if net_score > 0 else "bearish"


def _quality_label(avg_quality: float, coverage: float) -> str:
    if coverage < 0.5 or avg_quality < 0.55:
        return "low"
    if coverage < 0.8 or avg_quality < 0.75:
        return "medium"
    return "high"


def _radar_quality_detail(
    coverage: float,
    usable: list[dict[str, Any]],
    raw_coverage: float | None = None,
    same_run_coverage: float = 1.0,
) -> dict[str, Any]:
    if not usable:
        return {
            "overall_score": 0.0,
            "coverage_score": round(coverage, 4),
            "raw_coverage_score": round(raw_coverage if raw_coverage is not None else coverage, 4),
            "same_run_coverage_score": round(same_run_coverage, 4),
            "collection_freshness_score": 0.0,
            "business_recency_score": 0.0,
            "source_quality_score": 0.0,
            "conflict_penalty": 0.0,
            "main_discount_reasons": ["no_usable_metrics"],
        }
    source_quality = sum(item["quality_score"] for item in usable) / len(usable)
    collection_score = sum(
        _collection_quality_score(item.get("collection_freshness_status"))
        for item in usable
    ) / len(usable)
    business_score = sum(
        _business_recency_score(item.get("business_recency_status"))
        for item in usable
    ) / len(usable)
    conflict_count = sum(1 for item in usable if item.get("conflict", {}).get("detected"))
    conflict_penalty = min(conflict_count * 0.04, 0.16)
    score = (
        coverage * 0.25
        + collection_score * 0.25
        + business_score * 0.15
        + source_quality * 0.35
        - max(0.0, 1.0 - same_run_coverage) * 0.25
        - conflict_penalty
    )
    reasons: list[str] = []
    if coverage < 0.8:
        reasons.append("low_coverage")
    if collection_score < 0.85:
        reasons.append("collection_freshness_discount")
    if business_score < 0.85:
        reasons.append("business_recency_discount")
    if conflict_count:
        reasons.append(f"source_conflict:{conflict_count}")
    if same_run_coverage < 0.8:
        reasons.append("historical_fallback_dependency")
    return {
        "overall_score": round(max(min(score, 1.0), 0.0), 4),
        "coverage_score": round(coverage, 4),
        "raw_coverage_score": round(raw_coverage if raw_coverage is not None else coverage, 4),
        "same_run_coverage_score": round(same_run_coverage, 4),
        "collection_freshness_score": round(collection_score, 4),
        "business_recency_score": round(business_score, 4),
        "source_quality_score": round(source_quality, 4),
        "conflict_penalty": round(-conflict_penalty, 4),
        "main_discount_reasons": reasons,
    }


def _metric_evidence_tier(module_id: str, metric_id: str) -> str:
    if module_id == "onchain_valuation" and metric_id in {"whale_flow", "miner_flow"}:
        return "provider_required"
    if module_id == "asia_risk" and metric_id == "hibor":
        return "provider_required"
    if module_id == "event_policy" and metric_id == "regulatory_event_score":
        return "provider_required"
    if "proxy" in metric_id:
        return "proxy"
    return "exact"


def _collection_quality_score(status: Any) -> float:
    return {"fresh": 1.0, "stale": 0.65, "expired": 0.25, "missing": 0.0}.get(
        str(status or "missing"),
        0.0,
    )


def _business_recency_score(status: Any) -> float:
    return {
        "current": 1.0,
        "expected_lag": 0.95,
        "lagging": 0.85,
        "outdated": 0.65,
        "provider_stale_suspect": 0.8,
        "unknown": 0.75,
    }.get(
        str(status or "unknown"),
        0.75,
    )


def _risk_flags(module_id: str, contributions: list[dict[str, Any]]) -> dict[str, Any]:
    values = {item["metric_id"]: item for item in contributions}
    flagged_context = {
        item["metric_id"]: item.get("current")
        for item in contributions
        if item.get("affects_risk_flags")
    }
    if module_id == "derivatives_crowding":
        return {
            "funding_positive": values.get("btc_funding_rate", {}).get("current", 0) > 0,
            "open_interest_rising": (values.get("btc_open_interest", {}).get("change_24h") or 0)
            > 0,
            "context": flagged_context,
        }
    if module_id == "treasury_credit":
        return {
            "real_yield_pressure": (values.get("real_yield_10y", {}).get("change_24h") or 0)
            > 0,
            "context": flagged_context,
        }
    if module_id == "event_policy":
        return {
            "fomc_blackout_active": bool(values.get("fomc_blackout_active", {}).get("current", 0)),
            "context": flagged_context,
        }
    if module_id in {"btc_adoption", "trade_structure_flow", "btc_total_state"}:
        return {"context": flagged_context}
    return {}


def _persist_radar_output(session: Any, output: dict[str, Any]) -> None:
    session.add(
        schema.RadarOutput(
            run_id=output["run_id"],
            module_id=output["module_id"],
            signal=output["signal"],
            strength=output["strength"],
            confidence=output["confidence"],
            data_quality=output["data_quality"],
            evidence_summary=output["evidence_summary"],
            conflicting_evidence=output["conflicting_evidence"],
            risk_flags=output["risk_flags"],
            invalidation_signals=output["invalidation_signals"],
        )
    )
    session.add(
        schema.ModuleJsonOutput(
            run_id=output["run_id"],
            module_id=output["module_id"],
            schema_version="1.0",
            payload=output,
        )
    )
    for feature in output["features"]:
        session.add(
            schema.FeatureValue(
                run_id=output["run_id"],
                module_id=output["module_id"],
                feature_id=feature["metric_id"],
                value=feature.get("current"),
                metadata_json=feature,
            )
        )


def _model_dict(item: Any) -> dict[str, Any]:
    return {
        column.name: getattr(item, column.name)
        for column in item.__table__.columns
        if column.name != "id"
    }
