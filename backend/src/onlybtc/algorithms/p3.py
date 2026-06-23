from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from onlybtc.algorithms.features import calculate_p3_features
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.registry import METRIC_DEFINITIONS
from onlybtc.sources.service import historical_window

ANOMALY_MODULE_ID = "p3_anomaly_engine"
DIVERGENCE_MODULE_ID = "p3_divergence_engine"
EVENT_MODULE_ID = "p3_event_window_engine"
SCORED_METRIC_MODULE_ID = "p3_scored_metric_evidence"
SCORED_RADAR_MODULE_ID = "p3_scored_radar_module"

TREND_STRONG_DIRECTION_THRESHOLD = 12.0
TREND_CONTEXTUAL_DIRECTION_THRESHOLD = 2.0
TREND_SUPPORT_CONFIRM_THRESHOLD = 4.0
TREND_PRESSURE_CONFIRM_THRESHOLD = -2.0
TREND_CONFLICT_THRESHOLD = 0.65
TREND_INTERNAL_CONFLICT_THRESHOLD = 0.5
TREND_EVENT_RISK_LOCK_THRESHOLD = 60.0
CRYPTO_BREADTH_NEUTRAL_DEADBAND = 0.08
CRYPTO_BREADTH_MILD_BULLISH_THRESHOLD = 0.12

KEY_METRICS = (
    "btc_price",
    "btc_1h_close",
    "sp500",
    "dow_jones",
    "russell_2000",
    "gold",
    "wti_oil",
    "brent_oil",
    "dxy_proxy",
    "vix",
    "ofr_fsi",
    "btc_funding_rate",
    "btc_open_interest",
    "btc_global_long_short_account_ratio",
    "btc_top_long_short_account_ratio",
    "btc_top_long_short_position_ratio",
    "liquidation_long_usd",
    "liquidation_short_usd",
    "mvrv_zscore",
    "nupl",
    "sopr",
    "sth_cost_basis",
    "lth_cost_basis",
    "cpi_days_until",
    "fomc_days_until",
    "pce_days_until",
    "nfp_days_until",
    "macro_surprise_score",
    "fed_speech_risk",
)

EVENT_COUNTDOWN_METRICS = {
    "cpi_days_until": "CPI",
    "fomc_days_until": "FOMC",
    "pce_days_until": "PCE",
    "nfp_days_until": "NFP",
}

EVENT_COUNTDOWN_HOUR_METRICS = {
    "cpi_hours_until": "CPI",
    "fomc_hours_until": "FOMC",
    "pce_hours_until": "PCE",
    "nfp_hours_until": "NFP",
}

EVENT_SIGNED_DISTANCE_METRICS = {
    "cpi_days_until": "cpi_signed_days",
    "fomc_days_until": "fomc_signed_days",
    "pce_days_until": "pce_signed_days",
    "nfp_days_until": "nfp_signed_days",
}

SCORE_BUCKET_V2_VALUES = (
    "positive",
    "negative",
    "neutral_confirmed",
    "context_only",
    "combo_required",
    "rule_gap_zero",
    "unavailable",
)

CONTEXT_ONLY_METRICS = {
    "btc_block_height",
    "btc_halving_blocks_remaining",
    "btc_halving_estimated_days",
    "fomc_blackout_active",
    "next_fed_speech_hours_until",
    *EVENT_COUNTDOWN_HOUR_METRICS.keys(),
    "mempool_blocks_to_clear",
    "mempool_fee_fastest",
    "mempool_fee_half_hour",
    "mempool_fee_hour",
    "btc_global_long_account_ratio",
    "btc_global_short_account_ratio",
    "btc_top_long_account_ratio",
    "btc_top_short_account_ratio",
    "btc_top_long_position_ratio",
    "btc_top_short_position_ratio",
    *EVENT_COUNTDOWN_METRICS.keys(),
    *EVENT_SIGNED_DISTANCE_METRICS.values(),
}

DERIVATIVES_LONG_SHORT_RATIO_METRICS = {
    "btc_global_long_short_account_ratio",
    "btc_top_long_short_account_ratio",
    "btc_top_long_short_position_ratio",
}

DERIVATIVES_CROWDING_V25_PROFILE_METRICS = {
    "btc_trend_prior_score",
    "btc_trend_confidence",
    "btc_response_z_15m",
    "btc_response_z_1h",
    "btc_response_z_4h",
    "derivatives_pressure_z",
    "derivatives_residual_z",
    "derivatives_acceptance_score",
    "derivatives_rejection_score",
    "oi_impulse_z_1h",
    "oi_price_efficiency",
    "oi_participation_type_score",
    "funding_rate_8h_equiv_z",
    "predicted_funding_z",
    "basis_acceptance_score",
    "retail_crowding_score",
    "smart_money_divergence_score",
    "liquidation_impulse_z_15m",
    "liquidation_followthrough_score",
    "liquidation_absorption_score",
}

COMBO_REQUIRED_METRICS = {
    "btc_open_interest",
    "realized_price",
    "sth_cost_basis",
    "lth_cost_basis",
    "cap_real_usd",
    "miner_flow",
    "whale_flow",
    "hibor",
    "regulatory_event_score",
}

KLINE_DERIVED_METRICS = {
    "btc_return_1h",
    "btc_return_4h",
    "btc_return_24h",
    "btc_drawdown_24h",
    "btc_close_position_1h",
    "btc_candle_body_pct_1h",
    "btc_upper_wick_ratio_1h",
    "btc_lower_wick_ratio_1h",
    "btc_breakdown_24h_low",
    "btc_breakout_24h_high",
    "btc_rebound_quality_1h",
    "btc_down_volume_pressure",
    "btc_return_5m",
    "btc_return_15m",
    "btc_slope_tstat_1h",
    "btc_slope_acceleration_15m_proxy",
    "btc_slope_acceleration_15m",
    "btc_taker_imbalance_z_20",
    "btc_taker_imbalance_z_60",
    "btc_taker_imbalance_accel_3",
    "btc_taker_imbalance_persistence_5",
    "btc_taker_imbalance_z_60_5m",
    "btc_taker_imbalance_z_60_15m",
    "btc_flow_price_acceptance_1h",
    "btc_flow_price_acceptance_5m",
    "btc_flow_price_acceptance_15m",
    "btc_price_vs_vwap_1h_z",
    "btc_price_vs_vwap_z_5m",
    "btc_price_vs_vwap_z_15m",
    "btc_vwap_acceptance_duration_1m_proxy",
    "btc_vwap_acceptance_duration_5m",
    "btc_vwap_acceptance_duration_15m",
    "btc_micro_range_breakout_15m_proxy",
    "btc_local_range_breakout_1h",
    "btc_local_range_breakdown_1h",
    "btc_false_breakout_score",
    "btc_false_breakdown_score",
    "btc_orderflow_residual_z_60",
    "btc_orderflow_residual_z_180",
    "btc_orderflow_residual_z_60_5m",
    "btc_orderflow_residual_z_60_15m",
    "btc_volatility_regime_code",
}

KLINE_RAW_CONTEXT_METRICS = {
    "btc_1h_open",
    "btc_1h_high",
    "btc_1h_low",
    "btc_1h_close",
    "btc_1h_volume",
    "btc_vwap_1h",
    "btc_local_range_high_1h",
    "btc_local_range_low_1h",
    "btc_major_range_high_4h",
    "btc_major_range_low_4h",
}

KLINE_V22_PROFILE_METRICS = {
    "btc_flow_price_acceptance_1h",
    "btc_price_vs_vwap_1h_z",
    "btc_taker_imbalance_z_60",
    "btc_orderflow_residual_z_60",
    "btc_volatility_regime_code",
}

TRADE_STRUCTURE_PRICE_RESPONSE_METRICS = {
    "btc_return_5m",
    "btc_return_15m",
    "btc_close_position_5m",
    "btc_close_position_15m",
    "btc_range_expansion_z_5m",
    "btc_range_expansion_z_15m",
    "btc_volume_zscore_5m",
    "btc_volume_zscore_15m",
    "btc_flow_price_efficiency_5m",
    "btc_flow_price_efficiency_15m",
}

TRADE_STRUCTURE_V23_PROFILE_METRICS = {
    "trade_price_acceptance_score_5m",
    "trade_price_acceptance_score_15m",
    "trade_btc_return_z_5m",
    "trade_btc_return_z_15m",
    "trade_btc_return_z_1h",
    "trade_structure_residual_z",
}

NEUTRAL_CONFIRMED_RULE_MARKERS = (
    ".zero_neutral",
    ".normal",
    ".flat",
    ".neutral",
)


def run_p3_pipeline(
    run_id: str | None = None,
    metric_ids: list[str] | None = None,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    p2_radar_run_id: str | None = None,
    historical_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    run_id = run_id or _generate_p3_run_id()
    selected_metrics = metric_ids or list(
        dict.fromkeys(metric.metric_id for metric in METRIC_DEFINITIONS)
    )

    feature_result = calculate_p3_features(
        metric_ids=selected_metrics,
        run_id=run_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    radar_result = analyze_radars(
        run_id=run_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    scored_result = build_scored_evidence(
        run_id=run_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        p2_radar_run_id=p2_radar_run_id,
        db=db,
    )
    anomaly_result = detect_anomalies(
        run_id=run_id,
        metric_ids=selected_metrics,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    divergence_result = detect_divergences(
        run_id=run_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    module_invalidation_result = check_module_invalidations(
        run_id=run_id,
        run_mode=run_mode,
        db=db,
    )
    event_result = detect_event_windows(
        run_id=run_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    global_invalidation_result = check_global_invalidations(
        run_id=run_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        db=db,
    )
    alert_result = generate_algorithm_alerts(
        run_id=run_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        db=db,
    )

    return {
        "状态": "完成",
        "run_id": run_id,
        "features": feature_result,
        "radars": radar_result,
        "scored_evidence": scored_result,
        "anomalies": anomaly_result,
        "divergences": divergence_result,
        "module_invalidations": module_invalidation_result,
        "global_invalidations": global_invalidation_result,
        "event_windows": event_result,
        "alerts": alert_result,
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "p2_radar_run_id": p2_radar_run_id,
        "historical_fallback": historical_fallback,
        "non_production": run_mode != "live",
    }


def build_scored_evidence(
    run_id: str,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    p2_radar_run_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    metric_definitions = {item.metric_id: item for item in METRIC_DEFINITIONS}
    modules_by_id = {module.module_id: module for module in RADAR_MODULES}
    metric_items: list[dict[str, Any]] = []
    module_payloads: list[tuple[str, dict[str, Any], list[dict[str, Any]]]] = []
    with db.session() as session:
        module_rows = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.run_id == run_id)
            .order_by(schema.ModuleJsonOutput.module_id)
        ).all()
        feature_lookup = _build_feature_lookup(
            [
                feature
                for module_row in module_rows
                for feature in ((module_row.payload or {}).get("features") or [])
                if isinstance(feature, dict)
            ]
        )
        for module_row in module_rows:
            module_id = module_row.module_id
            if module_id not in modules_by_id:
                continue
            payload = module_row.payload or {}
            features = payload.get("features") or []
            module_metric_items = [
                _scored_metric_item(
                    run_id=run_id,
                    run_mode=run_mode,
                    collect_run_id=collect_run_id,
                    p2_radar_run_id=p2_radar_run_id,
                    module_id=module_id,
                    feature=feature,
                    feature_lookup=feature_lookup,
                    metric_definitions=metric_definitions,
                )
                for feature in features
                if isinstance(feature, dict)
            ]
            metric_items.extend(module_metric_items)
            module_payloads.append((module_id, payload, module_metric_items))

        _apply_effective_scores(metric_items)
        module_items = [
            _scored_module_item(
                run_id=run_id,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                p2_radar_run_id=p2_radar_run_id,
                module_id=module_id,
                payload=payload,
                metric_items=module_metric_items,
            )
            for module_id, payload, module_metric_items in module_payloads
        ]

        for item in metric_items:
            session.add(
                schema.FeatureValue(
                    run_id=run_id,
                    module_id=SCORED_METRIC_MODULE_ID,
                    feature_id=f"{item['radar_module']}.{item['metric_id']}.scored",
                    value=item["metric_score"],
                    metadata_json=item,
                )
            )
        for item in module_items:
            session.add(
                schema.FeatureValue(
                    run_id=run_id,
                    module_id=SCORED_RADAR_MODULE_ID,
                    feature_id=f"{item['radar_module']}.scored_module",
                    value=item["module_score"],
                    metadata_json=item,
                )
            )

    return {
        "schema_version": "p3.scored_evidence.v1",
        "run_id": run_id,
        "p3_run_id": run_id,
        "p2_radar_run_id": p2_radar_run_id,
        "collect_run_id": collect_run_id,
        "metric_count": len(metric_items),
        "module_count": len(module_items),
        "score_bucket_counts": _score_bucket_counts(metric_items),
        "score_bucket_v2_counts": _score_bucket_v2_counts(metric_items),
        "module_direction_counts": _module_direction_counts(module_items),
        "metric_items": metric_items,
        "module_items": module_items,
        "run_mode": run_mode,
    }


def _scored_metric_item(
    run_id: str,
    run_mode: str,
    collect_run_id: str | None,
    p2_radar_run_id: str | None,
    module_id: str,
    feature: dict[str, Any],
    feature_lookup: dict[str, dict[str, Any]],
    metric_definitions: dict[str, Any],
) -> dict[str, Any]:
    metric_id = str(feature.get("metric_id") or "unknown_metric")
    metric_definition = metric_definitions.get(metric_id)
    available = bool(feature.get("available"))
    base_metric_score = float(feature.get("score") or 0.0) if available else 0.0
    base_direction = str(feature.get("direction") or "neutral") if available else "unavailable"
    semantic = _semantic_metric_view(
        module_id=module_id,
        feature=feature,
        base_metric_score=base_metric_score,
        base_direction=base_direction,
        available=available,
        feature_lookup=feature_lookup,
    )
    metric_score = float(semantic["metric_score"])
    direction = str(semantic["direction"])
    score_bucket = _score_bucket(metric_score, available, feature)
    score_bucket_v2 = _score_bucket_v2(
        metric_id=metric_id,
        module_id=module_id,
        metric_score=metric_score,
        available=available,
        feature=feature,
        semantic=semantic,
        score_bucket=score_bucket,
    )
    value = feature.get("current")
    quality_score = float(feature.get("quality_score") or 0.0)
    source_id = feature.get("source_id")
    source_run_id = feature.get("source_run_id")
    fallback_used = bool(feature.get("fallback_reason"))
    return {
        "schema_version": "p3.scored_metric_evidence.v1",
        "p3_run_id": run_id,
        "p2_radar_run_id": p2_radar_run_id,
        "collect_run_id": collect_run_id,
        "evidence_id": f"p3-score-{run_id}-{module_id}-{metric_id}",
        "radar_module": module_id,
        "metric_id": metric_id,
        "metric_name": getattr(metric_definition, "name", metric_id),
        "source_id": source_id,
        "source_run_id": source_run_id,
        "value": value,
        "direction": direction,
        "metric_score": round(metric_score, 4),
        "base_metric_score": round(base_metric_score, 4),
        "base_direction": base_direction,
        "score_bucket": score_bucket,
        "score_bucket_v2": score_bucket_v2["bucket"],
        "zero_reason_type": score_bucket_v2["reason_type"],
        "zero_reason": score_bucket_v2["reason"],
        "decision_zero": score_bucket_v2["decision_zero"],
        "weight": feature.get("weight"),
        "quality_score": round(quality_score, 4),
        "source_ts": feature.get("source_ts"),
        "collected_at": feature.get("collected_at"),
        "freshness_minutes": feature.get("freshness_minutes"),
        "stale_after_minutes": feature.get("stale_after_minutes"),
        "is_stale": feature.get("is_stale"),
        "freshness_status": feature.get("collection_freshness_status")
        or feature.get("freshness_status"),
        "business_recency_status": feature.get("business_recency_status"),
        "horizon_tags": feature.get("horizon_tags") or [],
        "module_weight": feature.get("module_weight"),
        "duplicate_group_id": feature.get("duplicate_group_id") or metric_id,
        "duplicate_policy": feature.get("duplicate_policy"),
        "duplicate_group_max_weight": feature.get("duplicate_group_max_weight"),
        "metric_explanation": _metric_explanation(
            metric_id,
            module_id,
            getattr(metric_definition, "name", metric_id),
            value,
            direction,
            score_bucket,
            semantic,
        ),
        "score_reason": _score_reason(feature, metric_score, score_bucket, semantic),
        "semantic_rule_id": semantic.get("semantic_rule_id"),
        "semantic_warning": semantic.get("semantic_warning"),
        "signal_type": semantic.get("signal_type"),
        "risk_score": semantic.get("risk_score"),
        "event_risk_score": semantic.get("event_risk_score"),
        "flow_direction_score": semantic.get("flow_direction_score"),
        "flow_momentum_score": semantic.get("flow_momentum_score"),
        "flow_state": semantic.get("flow_state"),
        "aggressive_flow_state": semantic.get("aggressive_flow_state"),
        "crowding_state": semantic.get("crowding_state"),
        "leverage_risk_score": semantic.get("leverage_risk_score"),
        "derivatives_confirmation_score": semantic.get("derivatives_confirmation_score"),
        "funding_state": semantic.get("funding_state"),
        "crowding_signal": semantic.get("crowding_signal"),
        "direction_contribution": semantic.get("direction_contribution"),
        "trend_confirmation": semantic.get("trend_confirmation"),
        "oi_state": semantic.get("oi_state"),
        "oi_confirmation": semantic.get("oi_confirmation"),
        "oi_trend_signal": semantic.get("oi_trend_signal"),
        "positioning_signal": semantic.get("positioning_signal"),
        "crowding_contribution": semantic.get("crowding_contribution"),
        "positioning_scope": semantic.get("positioning_scope"),
        "valuation_state": semantic.get("valuation_state"),
        "price_trend_score": semantic.get("price_trend_score"),
        "volume_confirmation_score": semantic.get("volume_confirmation_score"),
        "candle_structure_score": semantic.get("candle_structure_score"),
        "breakdown_risk_score": semantic.get("breakdown_risk_score"),
        "rebound_quality_score": semantic.get("rebound_quality_score"),
        "selling_pressure_score": semantic.get("selling_pressure_score"),
        "metric_self_direction": semantic.get("metric_self_direction"),
        "metric_self_score": semantic.get("metric_self_score"),
        "module_composite_score": semantic.get("module_composite_score"),
        "module_composite_direction": semantic.get("module_composite_direction"),
        "module_composite_state": semantic.get("module_composite_state"),
        "kline_composite_contribution": semantic.get("kline_composite_contribution"),
        "kline_trend_state": semantic.get("kline_trend_state"),
        "kline_confirmation_status": semantic.get("kline_confirmation_status"),
        "price_response_state": semantic.get("price_response_state"),
        "price_response_confidence": semantic.get("price_response_confidence"),
        "flow_price_efficiency_state": semantic.get("flow_price_efficiency_state"),
        "price_response_source": semantic.get("price_response_source"),
        "volume_interpretation": semantic.get("volume_interpretation"),
        "candle_interpretation": semantic.get("candle_interpretation"),
        "thresholds_used": semantic.get("thresholds_used"),
        "component_metrics": semantic.get("component_metrics"),
        "history_context": {
            "previous_value": feature.get("previous"),
            "change_24h": feature.get("change_24h"),
            "change_7d": feature.get("change_7d"),
            "ma_30d": feature.get("ma_30d"),
        },
        "run_scope": feature.get("feature_run_scope"),
        "fallback_used": fallback_used,
        "fallback_reason": feature.get("fallback_reason"),
        "available": available,
        "evidence_tier": feature.get("evidence_tier"),
        "role": feature.get("role"),
        "affects_signal": feature.get("affects_signal"),
        "affects_confidence": feature.get("affects_confidence"),
        "driver_eligible": feature.get("driver_eligible", True),
        "run_mode": run_mode,
    }


def _build_feature_lookup(features: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for feature in features:
        metric_id = str(feature.get("metric_id") or "")
        if not metric_id:
            continue
        existing = lookup.get(metric_id)
        if existing is None:
            lookup[metric_id] = feature
            continue
        if existing.get("current") in {None, ""} and feature.get("current") not in {None, ""}:
            lookup[metric_id] = feature
            continue
        if feature.get("feature_run_scope") == "current_run" and existing.get("feature_run_scope") != "current_run":
            lookup[metric_id] = feature
    return lookup


def _apply_effective_scores(metric_items: list[dict[str, Any]]) -> None:
    group_abs_score: dict[str, float] = {}
    group_cap: dict[str, float] = {}
    for item in metric_items:
        group = str(item.get("duplicate_group_id") or item.get("metric_id"))
        group_abs_score[group] = group_abs_score.get(group, 0.0) + abs(
            float(item.get("metric_score") or 0.0)
        )
        cap = float(item.get("duplicate_group_max_weight") or 0.0)
        if cap > 0:
            group_cap[group] = max(group_cap.get(group, 0.0), cap)

    for item in metric_items:
        freshness_weight = _freshness_weight(item)
        horizon_weight = _horizon_weight(item)
        duplicate_adjustment = _duplicate_adjustment(item, group_abs_score, group_cap)
        metric_score = float(item.get("metric_score") or 0.0)
        quality_score = float(item.get("quality_score") or 0.0)
        effective = (
            metric_score * quality_score * freshness_weight * horizon_weight * duplicate_adjustment
        )
        warnings = []
        if item.get("freshness_minutes") is None:
            warnings.append("missing_freshness_minutes")
        if not item.get("horizon_tags"):
            warnings.append("missing_horizon_tags")
        item.update(
            {
                "freshness_weight": round(freshness_weight, 4),
                "horizon_weight": round(horizon_weight, 4),
                "duplicate_adjustment": round(duplicate_adjustment, 4),
                "metric_effective_score": round(effective, 4),
                "effective_score_formula": (
                    "metric_score * quality_score * freshness_weight * "
                    "horizon_weight * duplicate_adjustment"
                ),
                "effective_score_warnings": warnings,
            }
        )


def _freshness_weight(item: dict[str, Any]) -> float:
    if item.get("available") is False:
        return 0.0
    status = str(item.get("freshness_status") or "unknown")
    business = str(item.get("business_recency_status") or "unknown")
    collection_weight = {
        "fresh": 1.0,
        "stale": 0.65,
        "expired": 0.25,
        "missing": 1.0,
        "unknown": 1.0,
    }.get(status, 1.0)
    business_weight = {
        "current": 1.0,
        "expected_lag": 0.95,
        "lagging": 0.85,
        "outdated": 0.65,
        "provider_stale_suspect": 0.8,
        "unknown": 0.9,
    }.get(business, 0.9)
    return max(min(collection_weight * business_weight, 1.0), 0.0)


def _horizon_weight(item: dict[str, Any]) -> float:
    tags = set(item.get("horizon_tags") or [])
    if not tags:
        return 1.0
    if "h24" in tags:
        return 1.0
    if "d3" in tags:
        return 0.9
    if "d7" in tags:
        return 0.8
    if "structural" in tags:
        return 0.7
    return 1.0


def _duplicate_adjustment(
    item: dict[str, Any],
    group_abs_score: dict[str, float],
    group_cap: dict[str, float],
) -> float:
    group = str(item.get("duplicate_group_id") or item.get("metric_id"))
    total = group_abs_score.get(group, 0.0)
    cap = group_cap.get(group, 0.0)
    if total <= 0 or cap <= 0 or total <= cap:
        return 1.0
    return max(min(cap / total, 1.0), 0.2)


def _scored_module_item(
    run_id: str,
    run_mode: str,
    collect_run_id: str | None,
    p2_radar_run_id: str | None,
    module_id: str,
    payload: dict[str, Any],
    metric_items: list[dict[str, Any]],
) -> dict[str, Any]:
    positive = [item for item in metric_items if item["score_bucket"] == "positive"]
    negative = [item for item in metric_items if item["score_bucket"] == "negative"]
    zero = [item for item in metric_items if item["score_bucket"] == "zero"]
    unavailable = [item for item in metric_items if item["score_bucket"] == "unavailable"]
    zero_breakdown = _zero_breakdown(metric_items)
    module_score = round(sum(float(item.get("metric_score") or 0.0) for item in metric_items), 4)
    module_effective_score = round(
        sum(float(item.get("metric_effective_score") or 0.0) for item in metric_items),
        4,
    )
    aggregation = _module_aggregation_audit(
        metric_items,
        module_score,
        module_effective_score,
        payload,
    )
    state_machine = _module_state_machine(module_id, metric_items, aggregation)
    module_semantic_profile = _module_semantic_profile(
        module_id,
        metric_items,
        aggregation,
        payload,
    )
    if module_id == "btc_total_state" and module_semantic_profile.get("semantic_profile_version") == "p3.c41.btc_total_state.v2":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or state_machine.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("btc_short_term_state") or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("display_summary") or state_machine.get("trend_state_reason"),
        }
    if module_id == "options_volatility" and module_semantic_profile.get("semantic_profile_version") == "p3.c42.options_volatility.v2.1":
        module_score = 0.0
        module_effective_score = 0.0
        aggregation = {
            **aggregation,
            "module_raw_score": 0.0,
            "module_final_score": 0.0,
            "module_score": 0.0,
            "module_effective_score": 0.0,
        }
        state_machine = {
            **state_machine,
            "direction_score": 0.0,
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("options_short_term_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "event_policy" and module_semantic_profile.get("semantic_profile_version") == "p3.c43.event_policy.v2.1":
        module_score = 0.0
        module_effective_score = 0.0
        aggregation = {
            **aggregation,
            "module_raw_score": 0.0,
            "module_final_score": 0.0,
            "module_score": 0.0,
            "module_effective_score": 0.0,
        }
        state_machine = {
            **state_machine,
            "direction_score": 0.0,
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("event_short_term_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "crypto_breadth" and module_semantic_profile.get("semantic_profile_version") == "p3.c44.crypto_breadth.v3":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("crypto_breadth_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "macro_radar" and module_semantic_profile.get("semantic_profile_version") == "p3.c45.macro_radar.v3":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("macro_trend_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "dollar_liquidity" and module_semantic_profile.get("semantic_profile_version") == "p3.c46.dollar_liquidity.v2.1":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("dollar_liquidity_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "treasury_credit" and module_semantic_profile.get("semantic_profile_version") == "p3.c47.treasury_credit.v2.1":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("treasury_credit_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "fund_flow" and module_semantic_profile.get("semantic_profile_version") == "p3.c50.fund_flow.v2.2":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("fund_flow_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "onchain_valuation" and module_semantic_profile.get("semantic_profile_version") == "p3.c52.onchain_valuation.v2.2":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("onchain_valuation_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "btc_adoption" and module_semantic_profile.get("semantic_profile_version") == "p3.c54.btc_adoption.v2.3":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("btc_adoption_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "asia_risk" and module_semantic_profile.get("semantic_profile_version") == "p3.c56.asia_risk.v2.3":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("asia_risk_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "trade_structure_flow" and module_semantic_profile.get("semantic_profile_version") == "p3.c58.trade_structure_flow.v2.3":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(float(module_semantic_profile.get("module_effective_score") or module_score), 4)
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("trade_structure_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    if module_id == "derivatives_crowding" and module_semantic_profile.get("semantic_profile_version") == "p3.c60.derivatives_crowding.v2.5":
        module_score = round(float(module_semantic_profile.get("module_score") or 0.0), 4)
        module_effective_score = round(
            float(module_semantic_profile.get("module_effective_score") or module_score),
            4,
        )
        aggregation = {
            **aggregation,
            "module_raw_score": module_score,
            "module_final_score": module_effective_score,
            "module_score": module_score,
            "module_effective_score": module_effective_score,
        }
        state_machine = {
            **state_machine,
            "direction_score": round(module_effective_score * 100, 2),
            "risk_score": float(module_semantic_profile.get("risk_score") or 0.0),
            "trend_state": module_semantic_profile.get("derivatives_state")
            or state_machine.get("trend_state"),
            "trend_state_reason": module_semantic_profile.get("summary")
            or state_machine.get("trend_state_reason"),
        }
    module_direction = _module_direction(
        module_score,
        positive,
        negative,
        unavailable,
        payload,
        len(metric_items),
    )
    if module_id == "btc_total_state" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "options_volatility" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "event_policy" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "crypto_breadth" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "macro_radar" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "dollar_liquidity" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "treasury_credit" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "fund_flow" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "onchain_valuation" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "btc_adoption" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "asia_risk" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "trade_structure_flow" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "kline_orderflow" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    if module_id == "derivatives_crowding" and module_semantic_profile.get("module_direction"):
        module_direction = str(module_semantic_profile["module_direction"])
    module_effective_direction = _direction_from_score(module_effective_score)
    if module_id == "derivatives_crowding":
        if module_semantic_profile.get("module_direction"):
            module_effective_direction = str(module_semantic_profile["module_direction"])
        else:
            module_effective_direction = _derivatives_effective_direction(module_effective_score)
    elif module_id == "trade_structure_flow" and module_semantic_profile.get("module_direction"):
        module_effective_direction = str(module_semantic_profile["module_direction"])
    elif module_id == "kline_orderflow":
        module_effective_direction = _kline_effective_direction(module_effective_score)
    module_quality = payload.get("evidence_summary", {}).get("quality_explanation", {})
    return {
        "schema_version": "p3.scored_radar_module.v1",
        "p3_run_id": run_id,
        "p2_radar_run_id": p2_radar_run_id,
        "collect_run_id": collect_run_id,
        "radar_module": module_id,
        "module_score": module_score,
        "module_effective_score": module_effective_score,
        "module_direction": module_direction,
        "module_effective_direction": module_effective_direction,
        "module_strength": round(min(abs(module_score), 1.0), 4),
        "module_effective_strength": round(min(abs(module_effective_score), 1.0), 4),
        "source_module_confidence": payload.get("confidence"),
        "module_confidence": aggregation["module_confidence"],
        "module_quality_score": module_quality.get("overall_score"),
        "module_raw_score": aggregation["module_raw_score"],
        "module_final_score": aggregation["module_final_score"],
        "coverage_score": aggregation["coverage_score"],
        "conflict_score": aggregation["conflict_score"],
        "freshness_factor": aggregation["freshness_factor"],
        "freshness_score": state_machine["freshness_score"],
        "quality_score": aggregation["quality_score"],
        "conflict_penalty": aggregation["conflict_penalty"],
        "raw_effective_conflict": aggregation["raw_effective_conflict"],
        "module_state": aggregation["module_state"],
        "direction_score": state_machine["direction_score"],
        "risk_score": state_machine["risk_score"],
        "confidence_score": state_machine["confidence_score"],
        "trend_state": state_machine["trend_state"],
        "trend_state_reason": state_machine["trend_state_reason"],
        "module_semantic_profile": module_semantic_profile,
        **module_semantic_profile,
        "top_positive": aggregation["top_positive"],
        "top_negative": aggregation["top_negative"],
        "top_contributors": aggregation["top_contributors"],
        "score_bucket": _module_score_bucket(module_direction),
        "positive_metric_count": len(positive),
        "negative_metric_count": len(negative),
        "zero_metric_count": len(zero),
        "unavailable_metric_count": len(unavailable),
        "score_bucket_v2_counts": zero_breakdown["score_bucket_v2_counts"],
        "zero_breakdown": zero_breakdown,
        "decision_zero_metric_count": zero_breakdown["decision_zero_metric_count"],
        "decision_zero_metric_ratio": zero_breakdown["decision_zero_metric_ratio"],
        "rule_gap_zero_ratio": zero_breakdown["rule_gap_zero_ratio"],
        "context_zero_ratio": zero_breakdown["context_zero_ratio"],
        "neutral_confirmed_ratio": zero_breakdown["neutral_confirmed_ratio"],
        "combo_required_ratio": zero_breakdown["combo_required_ratio"],
        "top_positive_evidence_ids": [
            item["evidence_id"] for item in _top_scored_items(positive, reverse=True, limit=5)
        ],
        "top_negative_evidence_ids": [
            item["evidence_id"] for item in _top_scored_items(negative, reverse=False, limit=5)
        ],
        "module_explanation": _module_explanation(
            module_id, module_score, module_direction, positive, negative, unavailable
        ),
        "data_boundary": [
            f"{item['metric_id']} unavailable: {item.get('evidence_tier') or 'missing'}"
            for item in unavailable
        ],
        "metric_items": [item["evidence_id"] for item in metric_items],
        "run_mode": run_mode,
    }


def _score_bucket(metric_score: float, available: bool, feature: dict[str, Any]) -> str:
    if not available or feature.get("feature_run_scope") in {"provider_required", "missing"}:
        return "unavailable"
    if metric_score > 0.0001:
        return "positive"
    if metric_score < -0.0001:
        return "negative"
    return "zero"


def _score_bucket_v2(
    *,
    metric_id: str,
    module_id: str,
    metric_score: float,
    available: bool,
    feature: dict[str, Any],
    semantic: dict[str, Any],
    score_bucket: str,
) -> dict[str, Any]:
    if score_bucket in {"positive", "negative", "unavailable"}:
        return {
            "bucket": score_bucket,
            "reason_type": score_bucket,
            "reason": f"score_bucket_v2 mirrors legacy {score_bucket}",
            "decision_zero": False,
        }

    run_scope = str(feature.get("feature_run_scope") or "")
    evidence_tier = str(feature.get("evidence_tier") or "")
    signal_type = str(semantic.get("signal_type") or "")
    rule_id = str(semantic.get("semantic_rule_id") or "")

    if not available or run_scope in {"provider_required", "missing"}:
        return {
            "bucket": "unavailable",
            "reason_type": "unavailable",
            "reason": "metric is unavailable or provider-required for this run",
            "decision_zero": False,
        }
    if (
        metric_id in CONTEXT_ONLY_METRICS
        or signal_type == "context_signal"
        or feature.get("affects_signal") is False
        or str(feature.get("role") or "") in {"confirmation_factor", "structure_context", "price_context"}
    ):
        return {
            "bucket": "context_only",
            "reason_type": "context_only",
            "reason": "context or audit metric; not a directional decision zero",
            "decision_zero": False,
        }
    if metric_id in COMBO_REQUIRED_METRICS or "context_required" in rule_id:
        return {
            "bucket": "combo_required",
            "reason_type": "combo_required",
            "reason": "metric needs a paired rule or provider before directional scoring",
            "decision_zero": False,
        }
    if (
        signal_type in {"risk_signal", "regime_signal"}
        or any(marker in rule_id for marker in NEUTRAL_CONFIRMED_RULE_MARKERS)
        or evidence_tier in {"context", "audit"}
        or abs(metric_score) <= 0.0001 and str(semantic.get("direction")) == "neutral"
    ):
        return {
            "bucket": "neutral_confirmed",
            "reason_type": "neutral_confirmed",
            "reason": "available metric is inside a neutral or normal semantic range",
            "decision_zero": False,
        }
    return {
        "bucket": "rule_gap_zero",
        "reason_type": "rule_gap_zero",
        "reason": f"{module_id}.{metric_id} produced zero without a specific neutral/context rule",
        "decision_zero": True,
    }


def _module_direction(
    module_score: float,
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
    payload: dict[str, Any],
    total_metric_count: int,
) -> str:
    unavailable_share = len(unavailable) / max(total_metric_count, 1)
    if unavailable_share >= 0.5 and abs(module_score) < 0.08:
        return "unavailable"
    if abs(module_score) < 0.08:
        if positive and negative:
            return "mixed"
        return "neutral"
    return "bullish" if module_score > 0 else "bearish"


def _module_score_bucket(module_direction: str) -> str:
    if module_direction == "bullish":
        return "positive"
    if module_direction == "bearish":
        return "negative"
    if module_direction == "unavailable":
        return "unavailable"
    return "zero"


def _direction_from_score(score: float) -> str:
    if score > 0.0001:
        return "bullish"
    if score < -0.0001:
        return "bearish"
    return "neutral"


def _derivatives_effective_direction(score: float) -> str:
    if abs(score) < 0.10:
        return "neutral"
    if score >= 0.25:
        return "bullish"
    if score <= -0.25:
        return "bearish"
    if score > 0:
        return "mild_bullish"
    return "mild_bearish"


def _kline_effective_direction(score: float) -> str:
    if abs(score) < 0.12:
        return "neutral"
    return "bullish" if score > 0 else "bearish"


def _kline_effective_bias(score: float) -> str:
    if abs(score) < 0.05:
        return "neutral"
    if abs(score) < 0.12:
        return "mild_support" if score > 0 else "mild_pressure"
    return "support" if score > 0 else "pressure"


def _kline_display_summary(trend_state: str, module_effective_score: float) -> str:
    if trend_state == "neutral_wait_confirm" and module_effective_score > 0:
        return "Short-term support exists, but kline structure still waits for confirmation."
    if trend_state == "neutral_wait_confirm" and module_effective_score < 0:
        return "Short-term pressure exists, but kline structure still waits for confirmation."
    if trend_state == "bullish_confirmation":
        return "Short-term price and volume confirm bullish participation."
    if trend_state == "bearish_pressure":
        return "Short-term volume confirms downside pressure."
    return _kline_reason({"trend_state": trend_state})


def _derivatives_effective_bias(score: float) -> str:
    if abs(score) < 0.0001:
        return "neutral"
    if abs(score) < 0.25:
        return "mild_support" if score > 0 else "mild_pressure"
    return "strong_support" if score > 0 else "strong_pressure"


def _funding_state_from_value(value: Any) -> str:
    current = _safe_float(value)
    if current is None:
        return "funding_mild"
    if current > 0.0008:
        return "funding_extreme"
    if current > 0.0003:
        return "funding_elevated"
    if current < -0.0002:
        return "funding_negative"
    return "funding_mild"


def _oi_state_from_change(item: dict[str, Any]) -> str:
    history = item.get("history_context") or {}
    change = _safe_float(history.get("change_24h"))
    if change is None or abs(change) < 0.005:
        return "oi_flat"
    if change > 0:
        return "oi_rising"
    return "oi_falling"


def _positioning_signal_from_ratio(value: Any) -> str:
    ratio = _safe_float(value)
    if ratio is None:
        return "balanced"
    if ratio >= 2.0:
        return "extreme_long"
    if ratio >= 1.35:
        return "long_skew"
    if ratio <= 0.5:
        return "extreme_short"
    if ratio <= 0.75:
        return "short_skew"
    return "balanced"


def _positioning_directional_score(signal: str, weight: float) -> tuple[float, str]:
    if signal == "extreme_long":
        return -weight * 0.45, "mild_pressure"
    if signal == "long_skew":
        return -weight * 0.18, "mild_pressure"
    if signal == "extreme_short":
        return weight * 0.45, "squeeze_support"
    if signal == "short_skew":
        return weight * 0.18, "mild_support"
    return 0.0, "neutral"


def _positioning_state_from_signal(signal: str, prefix: str = "") -> str:
    prefix = f"{prefix}_" if prefix else ""
    if signal == "extreme_long":
        return f"{prefix}extreme_long"
    if signal == "long_skew":
        return f"{prefix}long_skew"
    if signal == "extreme_short":
        return f"{prefix}extreme_short"
    if signal == "short_skew":
        return f"{prefix}short_skew"
    return "balanced"


def _opposite_positioning(left: str, right: str) -> bool:
    long_states = {"long_skew", "extreme_long", "top_long_skew", "top_extreme_long"}
    short_states = {"short_skew", "extreme_short", "top_short_skew", "top_extreme_short"}
    return (left in long_states and right in short_states) or (
        left in short_states and right in long_states
    )


def _derivatives_crowding_profile(
    *,
    funding_state: str,
    oi_state: str,
    module_effective_score: float,
    crowding_states: list[str],
    metric_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metric_items = metric_items or []
    global_ratio = _metric_by_id(metric_items, "btc_global_long_short_account_ratio") or {}
    top_account_ratio = _metric_by_id(metric_items, "btc_top_long_short_account_ratio") or {}
    top_position_ratio = _metric_by_id(metric_items, "btc_top_long_short_position_ratio") or {}
    global_signal = str(global_ratio.get("positioning_signal") or _positioning_signal_from_ratio(global_ratio.get("value")))
    top_account_signal = str(
        top_account_ratio.get("positioning_signal")
        or _positioning_signal_from_ratio(top_account_ratio.get("value"))
    )
    top_position_signal = str(
        top_position_ratio.get("positioning_signal")
        or _positioning_signal_from_ratio(top_position_ratio.get("value"))
    )
    positioning_state = _positioning_state_from_signal(global_signal)
    top_positioning_state = _positioning_state_from_signal(top_position_signal, "top")
    conflict = _opposite_positioning(positioning_state, top_positioning_state)
    squeeze_risk = "none"
    if top_position_signal in {"extreme_long", "long_skew"} and funding_state in {
        "funding_elevated",
        "funding_hot",
        "funding_extreme",
    } and oi_state == "oi_rising":
        squeeze_risk = "long_squeeze_risk"
    elif top_position_signal in {"extreme_short", "short_skew"} and funding_state == "funding_negative" and oi_state == "oi_rising":
        squeeze_risk = "short_squeeze_risk"
    bias = _derivatives_effective_bias(module_effective_score)
    profile: dict[str, Any] = {
        "trend_direction": "neutral",
        "trend_state": "neutral_wait_confirm",
        "crowding_state": "balanced",
        "leverage_heat_state": "normal",
        "module_effective_bias": bias,
        "confirmation_state": "unconfirmed",
        "funding_state": funding_state,
        "oi_state": oi_state,
        "positioning_state": positioning_state,
        "top_positioning_state": top_positioning_state,
        "top_trader_bias_state": _positioning_state_from_signal(top_account_signal, "top"),
        "positioning_conflict_level": "high" if conflict else "none",
        "long_short_squeeze_risk": squeeze_risk,
        "long_short_combo_applied": any(
            item.get("metric_id") in DERIVATIVES_LONG_SHORT_RATIO_METRICS
            for item in metric_items
        ),
    }
    if squeeze_risk == "long_squeeze_risk":
        profile.update(
            {
                "crowding_state": "long_crowded",
                "leverage_heat_state": "hot",
                "module_effective_bias": "mild_pressure",
            }
        )
        return profile
    if squeeze_risk == "short_squeeze_risk":
        profile.update(
            {
                "crowding_state": "short_crowded",
                "leverage_heat_state": "elevated",
                "module_effective_bias": "mild_support",
            }
        )
        return profile
    if funding_state == "funding_mild" and oi_state == "oi_flat":
        profile.update(
            {
                "crowding_state": "not_crowded",
                "leverage_heat_state": "low_to_normal",
                "module_effective_bias": "mild_support" if module_effective_score >= 0 else "neutral",
            }
        )
        return profile
    if funding_state in {"funding_elevated", "funding_hot", "funding_extreme"} and oi_state == "oi_rising":
        profile.update(
            {
                "crowding_state": "long_crowded",
                "leverage_heat_state": "hot",
                "module_effective_bias": "mild_pressure",
            }
        )
        return profile
    if funding_state == "funding_negative" and oi_state == "oi_rising":
        profile.update(
            {
                "crowding_state": "short_crowded",
                "leverage_heat_state": "elevated",
                "module_effective_bias": "mild_support",
            }
        )
        return profile
    if any("long_crowding" in state or "overheated" in state for state in crowding_states):
        profile.update(
            {
                "trend_direction": "bearish",
                "trend_state": "bearish_pressure",
                "crowding_state": "long_crowded",
                "leverage_heat_state": "elevated",
                "module_effective_bias": "mild_pressure",
            }
        )
    elif any("short_crowding" in state for state in crowding_states):
        profile.update(
            {
                "crowding_state": "short_crowded",
                "leverage_heat_state": "elevated",
                "module_effective_bias": "mild_support",
            }
        )
    elif any("trend_confirmed" in state for state in crowding_states):
        profile.update(
            {
                "trend_direction": "bullish" if module_effective_score > 0 else "bearish",
                "trend_state": "confirmed_bullish" if module_effective_score > 0 else "confirmed_bearish",
                "confirmation_state": "confirmed",
                "crowding_state": "not_crowded",
                "leverage_heat_state": "low_to_normal",
            }
        )
    return profile


def _derivatives_trend_state(score: float) -> str:
    if score >= 25:
        return "uptrend"
    if score <= -25:
        return "downtrend"
    if abs(score) <= 12:
        return "range"
    return "transition"


def _derivatives_participation_type(score: float, oi_impulse_z: float, btc_response_z: float) -> str:
    if score >= 25 and btc_response_z >= 0:
        return "healthy_participation"
    if oi_impulse_z >= 1 and btc_response_z < -0.25:
        return "inefficient_leverage_build"
    if oi_impulse_z < -0.5 and btc_response_z > 0.4:
        return "short_covering_rally"
    if oi_impulse_z >= 1 and btc_response_z <= -0.5:
        return "short_building_pressure"
    if oi_impulse_z < -0.5 and btc_response_z <= -0.5:
        return "deleveraging_drop"
    return "noise_churn"


def _derivatives_crowding_v25_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
    legacy_profile: dict[str, Any],
) -> dict[str, Any]:
    def value(metric_id: str, default: float = 0.0) -> float:
        raw = _metric_value(metric_items, metric_id)
        return default if raw is None else float(raw)

    trend_prior_score = value("btc_trend_prior_score")
    trend_strength_z = value("btc_trend_strength_z")
    trend_confidence = value("btc_trend_confidence", 50.0)
    trend_age_bars = value("btc_trend_age_bars")
    volatility_code = value("btc_volatility_regime_code")
    volatility_regime = {
        0.0: "low",
        1.0: "normal",
        2.0: "high",
        3.0: "shock",
    }.get(float(round(volatility_code)), "normal")
    trend_state = _derivatives_trend_state(trend_prior_score)

    btc_response_15m = value("btc_response_z_15m")
    btc_response_1h = value("btc_response_z_1h")
    btc_response_4h = value("btc_response_z_4h")
    residual_z = value("derivatives_residual_z")
    acceptance_score_raw = value("derivatives_acceptance_score")
    rejection_score = value("derivatives_rejection_score")
    oi_impulse_1h = value("oi_impulse_z_1h")
    oi_efficiency = value("oi_price_efficiency")
    oi_type_score = value("oi_participation_type_score")
    funding_z = value("funding_rate_8h_equiv_z")
    funding_accel = value("funding_acceleration_z_24h")
    predicted_funding_z = value("predicted_funding_z")
    basis_acceptance = value("basis_acceptance_score")
    global_ratio_z = value("global_account_ratio_z")
    top_position_z = value("top_position_ratio_z")
    positioning_gap_z = value("top_vs_global_positioning_gap_z")
    retail_crowding = value("retail_crowding_score")
    smart_money_divergence = value("smart_money_divergence_score")
    liquidation_impulse_15m = value("liquidation_impulse_z_15m")
    liquidation_followthrough = value("liquidation_followthrough_score")
    liquidation_absorption = value("liquidation_absorption_score")
    oi_source_coverage = value("oi_source_coverage_score", 70.0)

    btc_acceptance_score = _clamp(
        0.40 * acceptance_score_raw
        - 0.25 * rejection_score
        + 0.25 * residual_z * 35.0
        + 0.10 * btc_response_1h * 35.0,
        -100.0,
        100.0,
    )
    participation_type = _derivatives_participation_type(oi_type_score, oi_impulse_1h, btc_response_1h)
    oi_participation_score = _clamp(
        0.40 * oi_type_score
        + 0.30 * oi_efficiency * 35.0
        + 0.30 * oi_impulse_1h * btc_response_1h * 20.0,
        -100.0,
        100.0,
    )
    funding_basis_score = _clamp(
        0.45 * basis_acceptance
        - 0.25 * max(funding_z - 1.2, 0.0) * 30.0
        + 0.20 * max(-funding_z - 1.0, 0.0) * 25.0
        - 0.10 * abs(funding_accel) * 15.0,
        -100.0,
        100.0,
    )
    positioning_skew_score = _clamp(
        -0.35 * retail_crowding
        + 0.35 * smart_money_divergence
        - 0.15 * max(global_ratio_z, 0.0) * 20.0
        - 0.15 * max(positioning_gap_z, 0.0) * 20.0,
        -100.0,
        100.0,
    )
    liquidation_response_score = _clamp(
        liquidation_absorption
        + max(liquidation_followthrough, 0.0) * 0.25
        - max(-liquidation_followthrough, 0.0) * 0.75
        - liquidation_impulse_15m * max(-btc_response_15m, 0.0) * 20.0,
        -100.0,
        100.0,
    )
    trend_prior_alignment_score = _clamp(
        (1.0 if trend_state == "uptrend" else -1.0 if trend_state == "downtrend" else 0.0)
        * btc_response_1h
        * 25.0,
        -100.0,
        100.0,
    )
    residual_confirmation_score = _clamp(residual_z / 2.0, -1.0, 1.0) * 100.0
    crowding_fragility_score = _clamp(
        max(
            max(funding_z, predicted_funding_z, 0.0) * 28.0,
            retail_crowding,
            max(oi_impulse_1h, 0.0) * 28.0,
            liquidation_impulse_15m * 25.0,
            max(top_position_z, 0.0) * 22.0,
        ),
        0.0,
        100.0,
    )
    squeeze_risk_score = _clamp(
        max(-funding_z - 1.0, 0.0) * 30.0
        + max(-top_position_z - 0.5, 0.0) * 22.0
        - max(funding_z - 1.0, 0.0) * 30.0
        - retail_crowding * 0.25,
        -100.0,
        100.0,
    )
    trend_acceptance_score = _clamp(
        0.45 * btc_acceptance_score
        + 0.20 * oi_participation_score
        + 0.15 * funding_basis_score
        + 0.10 * liquidation_response_score
        + 0.10 * trend_prior_alignment_score,
        -100.0,
        100.0,
    )
    data_quality_flags: list[str] = []
    proxy_flags: list[str] = []
    if oi_source_coverage <= 75:
        proxy_flags.append("single_exchange_oi_coverage")
    if value("liquidation_long_usd") or value("liquidation_short_usd") or liquidation_impulse_15m:
        data_quality_flags.append("liquidation_snapshot_only")
    if trend_confidence < 50:
        data_quality_flags.append("trend_prior_low_confidence")
    data_quality_penalty = 5.0 * len(proxy_flags) + 6.0 * len(data_quality_flags)
    module_score_raw = (
        0.35 * btc_acceptance_score
        + 0.20 * oi_participation_score
        + 0.15 * funding_basis_score
        + 0.15 * liquidation_response_score
        + 0.10 * positioning_skew_score
        + 0.05 * trend_prior_alignment_score
        - data_quality_penalty
    )

    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    conflict_drivers: list[str] = []
    early_warning_flags: list[str] = []
    if btc_acceptance_score >= 25:
        support_drivers.append("btc_accepting_derivatives_structure")
    if btc_acceptance_score <= -25:
        pressure_drivers.append("btc_rejecting_derivatives_structure")
    if crowding_fragility_score >= 55:
        early_warning_flags.append("crowding_fragility_elevated")
    if squeeze_risk_score >= 35:
        support_drivers.append("short_squeeze_risk")
    if squeeze_risk_score <= -35:
        pressure_drivers.append("long_liquidation_risk")

    state = "derivatives_neutral"
    implication = "neutral"
    direction = "neutral"
    stage = "none"

    if liquidation_impulse_15m >= 2 and btc_response_15m <= -1.0 and btc_response_1h <= -0.75 and residual_z <= -1:
        state, implication, direction, stage = (
            "forced_selling_followthrough",
            "liquidation_followthrough",
            "bearish",
            "fast_signal",
        )
    elif liquidation_impulse_15m >= 2 and btc_response_15m >= 0 and residual_z >= 0.75 and btc_acceptance_score > 0:
        state, implication, direction, stage = (
            "forced_selling_absorbed",
            "forced_selling_absorbed",
            "bullish",
            "fast_signal",
        )
    elif liquidation_impulse_15m >= 2 and btc_response_15m > 0 and oi_impulse_1h < 0 and funding_z > 0 and btc_response_1h <= 0 and residual_z < 0:
        state, implication, direction, stage = (
            "short_squeeze_exhaustion",
            "squeeze_exhausting",
            "neutral",
            "early_warning",
        )
    elif trend_state == "uptrend" and btc_response_1h >= 0.5 and participation_type == "healthy_participation" and -0.5 <= funding_z <= 1.2 and residual_z >= 0:
        state, implication, direction, stage = (
            "derivatives_accepted_uptrend",
            "trend_confirmed",
            "bullish",
            "confirmed_signal",
        )
    elif trend_state in {"uptrend", "transition"} and oi_impulse_1h >= 1.0 and funding_z >= 1.0 and btc_response_15m <= -0.75 and btc_response_1h <= -0.5 and residual_z <= -1:
        state, implication, direction, stage = (
            "uptrend_crowding_failure",
            "trend_rejected",
            "bearish",
            "fast_signal",
        )
    elif trend_state == "downtrend" and btc_response_1h <= -0.5 and oi_impulse_1h >= 1.0 and funding_z <= 0.5 and top_position_z <= -0.5 and residual_z <= -0.5:
        state, implication, direction, stage = (
            "short_building_confirms_downtrend",
            "trend_confirmed",
            "bearish",
            "confirmed_signal",
        )
    elif funding_z <= -1.2 and top_position_z <= -1.0 and value("oi_impulse_z_4h") >= 0.75 and btc_response_1h >= 0 and residual_z >= 0.5:
        state, implication, direction, stage = (
            "short_squeeze_setup",
            "squeeze_setup",
            "bullish",
            "early_warning",
        )
    elif trend_state == "uptrend" and oi_impulse_1h >= 1.5 and funding_z >= 1.2 and global_ratio_z >= 1.0 and -0.25 <= btc_response_1h <= 0.75:
        state, implication, direction, stage = (
            "uptrend_long_crowding_fragility",
            "trend_fragile",
            "neutral",
            "early_warning",
        )
    elif abs(trend_acceptance_score) >= 55 and residual_confirmation_score * trend_acceptance_score > 0:
        direction = "bullish" if trend_acceptance_score > 0 else "bearish"
        stage = "fast_signal"
        state = "derivatives_acceptance_fast_signal"
        implication = "trend_confirmed" if direction == "bullish" else "trend_rejected"
    elif abs(crowding_fragility_score) >= 55:
        state, implication, direction, stage = (
            "crowding_fragility_warning",
            "trend_fragile",
            "neutral",
            "early_warning",
        )

    if stage == "confirmed_signal" and trend_confidence < 50:
        stage = "fast_signal"
        conflict_drivers.append("confirmed_signal_capped_by_low_trend_prior_confidence")
    if stage == "confirmed_signal" and (btc_acceptance_score * residual_confirmation_score <= 0):
        stage = "conflict"
        direction = "neutral"
        conflict_drivers.append("confirmed_signal_blocked_without_btc_acceptance_and_residual")
    if volatility_regime == "shock" and stage == "confirmed_signal":
        stage = "fast_signal"
        early_warning_flags.append("shock_vol_confirmed_signal_capped")

    module_score = round(_clamp(module_score_raw / 100.0, -1.0, 1.0), 4)
    confidence = round(_clamp(76.0 - data_quality_penalty - len(conflict_drivers) * 10.0, 0.0, 100.0), 2)
    scores = {
        "trend_acceptance_score": round(trend_acceptance_score, 2),
        "crowding_fragility_score": round(crowding_fragility_score, 2),
        "squeeze_risk_score": round(squeeze_risk_score, 2),
        "btc_acceptance_score": round(btc_acceptance_score, 2),
        "oi_participation_score": round(oi_participation_score, 2),
        "funding_basis_score": round(funding_basis_score, 2),
        "positioning_skew_score": round(positioning_skew_score, 2),
        "liquidation_response_score": round(liquidation_response_score, 2),
        "residual_confirmation_score": round(residual_confirmation_score, 2),
        "data_quality_penalty": round(data_quality_penalty, 2),
    }
    trend_prior = {
        "btc_trend_state": trend_state,
        "trend_strength_z": round(trend_strength_z, 4),
        "trend_confidence": round(trend_confidence, 2),
        "trend_age_bars": round(trend_age_bars, 2),
        "volatility_regime": volatility_regime,
    }
    states = {
        "funding": {
            "funding_rate_8h_equiv_z": round(funding_z, 4),
            "funding_acceleration_z_24h": round(funding_accel, 4),
            "predicted_funding_z": round(predicted_funding_z, 4),
            "basis_acceptance_score": round(basis_acceptance, 2),
        },
        "open_interest": {
            "oi_impulse_z_1h": round(oi_impulse_1h, 4),
            "oi_price_efficiency": round(oi_efficiency, 4),
            "oi_participation_type": participation_type,
            "oi_source_coverage_score": round(oi_source_coverage, 2),
        },
        "positioning": {
            "global_account_ratio_z": round(global_ratio_z, 4),
            "top_position_ratio_z": round(top_position_z, 4),
            "top_vs_global_positioning_gap_z": round(positioning_gap_z, 4),
            "retail_crowding_score": round(retail_crowding, 2),
            "smart_money_divergence_score": round(smart_money_divergence, 2),
        },
        "liquidation": {
            "liquidation_impulse_z_15m": round(liquidation_impulse_15m, 4),
            "liquidation_followthrough_score": round(liquidation_followthrough, 2),
            "liquidation_absorption_score": round(liquidation_absorption, 2),
        },
        "btc_response": {
            "btc_response_z_15m": round(btc_response_15m, 4),
            "btc_response_z_1h": round(btc_response_1h, 4),
            "btc_response_z_4h": round(btc_response_4h, 4),
        },
        "trend_acceptance": {
            "derivatives_pressure_z": round(value("derivatives_pressure_z"), 4),
            "derivatives_expected_return_z": round(value("derivatives_expected_return_z"), 4),
            "derivatives_residual_z": round(residual_z, 4),
        },
    }
    summary = (
        f"derivatives_crowding.v2.5 state={state}; stage={stage}; "
        f"trend={trend_state}; acceptance={trend_acceptance_score:.1f}; "
        "direction requires BTC response, trend prior and standardized residual."
    )
    contract = {
        "module": "derivatives_crowding",
        "version": "p3.c60.derivatives_crowding.v2.5",
        "module_direction": direction,
        "module_score": module_score,
        "confidence_score": confidence,
        "signal_stage": stage,
        "derivatives_state": state,
        "btc_implication": implication,
        "trend_prior": trend_prior,
        "scores": scores,
        "states": states,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "conflict_drivers": conflict_drivers,
        "early_warning_flags": early_warning_flags,
        "data_quality_flags": data_quality_flags,
        "proxy_flags": proxy_flags,
        "invalidation_conditions": [
            "BTC response turns opposite to derivatives residual",
            "trend prior confidence falls below confirmed threshold",
            "liquidation response fails to follow through within 15m-1h",
        ],
    }
    return {
        **legacy_profile,
        "semantic_profile_version": "p3.c60.derivatives_crowding.v2.5",
        "module_direction": direction,
        "module_score": module_score,
        "module_effective_score": module_score,
        "confidence_score": confidence,
        "risk_score": round(crowding_fragility_score, 2),
        "signal_stage": stage,
        "derivatives_state": state,
        "btc_implication": implication,
        "trend_prior": trend_prior,
        "scores": scores,
        "states": states,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "conflict_drivers": conflict_drivers,
        "early_warning_flags": early_warning_flags,
        "data_quality_flags": data_quality_flags,
        "proxy_flags": proxy_flags,
        "invalidation_conditions": contract["invalidation_conditions"],
        "summary": summary,
        "display_state": stage,
        "display_summary": summary,
        "derivatives_crowding_v25": contract,
        "trend_acceptance_score": scores["trend_acceptance_score"],
        "crowding_fragility_score": scores["crowding_fragility_score"],
        "squeeze_risk_score": scores["squeeze_risk_score"],
    }


def _top_scored_items(
    items: list[dict[str, Any]], reverse: bool, limit: int
) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: float(item.get("metric_score") or 0.0), reverse=reverse)[
        :limit
    ]


def _module_aggregation_audit(
    metric_items: list[dict[str, Any]],
    module_score: float,
    module_effective_score: float,
    payload: dict[str, Any],
) -> dict[str, Any]:
    expected_weight = sum(abs(float(item.get("weight") or 0.0)) for item in metric_items)
    active_items = [item for item in metric_items if item.get("score_bucket") != "unavailable"]
    active_weight = sum(abs(float(item.get("weight") or 0.0)) for item in active_items)
    if expected_weight <= 0:
        expected_weight = float(len(metric_items) or 1)
        active_weight = float(len(active_items))
    coverage_score = _clamp(active_weight / expected_weight if expected_weight else 0.0)

    positive_abs = sum(
        abs(float(item.get("metric_effective_score") or item.get("metric_score") or 0.0))
        for item in metric_items
        if float(item.get("metric_effective_score") or item.get("metric_score") or 0.0) > 0
    )
    negative_abs = sum(
        abs(float(item.get("metric_effective_score") or item.get("metric_score") or 0.0))
        for item in metric_items
        if float(item.get("metric_effective_score") or item.get("metric_score") or 0.0) < 0
    )
    conflict_base = max(positive_abs, negative_abs)
    conflict_score = _clamp(min(positive_abs, negative_abs) / conflict_base) if conflict_base else 0.0

    freshness_score = _weighted_average(metric_items, "freshness_weight", default=1.0)
    quality = _module_quality_score(metric_items, payload)
    raw_effective_conflict = _has_raw_effective_conflict(module_score, module_effective_score)
    conflict_penalty = 1.0 - conflict_score * 0.35
    if raw_effective_conflict:
        conflict_penalty *= 0.65
    module_confidence = _clamp(quality * coverage_score * freshness_score * conflict_penalty)

    active_weight_for_score = active_weight or float(len(active_items) or 1)
    module_raw_score = round(
        sum(
            float(item.get("metric_score") or 0.0) * abs(float(item.get("weight") or 1.0))
            for item in active_items
        )
        / active_weight_for_score,
        4,
    )
    module_final_score = round(module_raw_score * module_confidence, 4)
    zero_breakdown = _zero_breakdown(metric_items)

    return {
        "module_score": module_score,
        "module_effective_score": module_effective_score,
        "module_raw_score": module_raw_score,
        "module_final_score": module_final_score,
        "coverage_score": round(coverage_score, 4),
        "conflict_score": round(conflict_score, 4),
        "freshness_factor": round(freshness_score, 4),
        "quality_score": round(quality, 4),
        "conflict_penalty": round(conflict_penalty, 4),
        "module_confidence": round(module_confidence, 4),
        "raw_effective_conflict": raw_effective_conflict,
        "zero_breakdown": zero_breakdown,
        "decision_zero_metric_ratio": zero_breakdown["decision_zero_metric_ratio"],
        "module_state": _module_state(
            module_score,
            module_effective_score,
            raw_effective_conflict,
            conflict_score,
        ),
        "top_positive": _module_top_items(metric_items, positive=True, limit=5),
        "top_negative": _module_top_items(metric_items, positive=False, limit=5),
        "top_contributors": _module_top_contributors(metric_items, limit=6),
    }


def _module_state_machine(
    module_id: str,
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    direction_score = round(_clamp(float(aggregation["module_final_score"]), -1.0, 1.0) * 100, 2)
    confidence_score = round(_clamp(float(aggregation["module_confidence"])) * 100, 2)
    freshness_score = round(_clamp(float(aggregation["freshness_factor"])) * 100, 2)
    risk_score = _module_risk_score(metric_items, aggregation)
    trend_state, reason = _trend_state_from_module(
        module_id=module_id,
        direction_score=direction_score,
        risk_score=risk_score,
        confidence_score=confidence_score,
        aggregation=aggregation,
        metric_items=metric_items,
    )
    return {
        "direction_score": direction_score,
        "risk_score": risk_score,
        "confidence_score": confidence_score,
        "freshness_score": freshness_score,
        "trend_state": trend_state,
        "trend_state_reason": reason,
    }


def _module_risk_score(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> float:
    risk_values: list[tuple[float, float]] = []
    for item in metric_items:
        weight = abs(float(item.get("weight") or 1.0))
        for key in ("risk_score", "event_risk_score", "leverage_risk_score"):
            value = item.get(key)
            if value is not None:
                risk_values.append((_clamp(float(value)) * 100, weight))
    if risk_values:
        numerator = sum(value * weight for value, weight in risk_values)
        denominator = sum(weight for _, weight in risk_values) or 1.0
        metric_risk = numerator / denominator
    else:
        metric_risk = 0.0
    unavailable_share = sum(
        1 for item in metric_items if item.get("score_bucket") == "unavailable"
    ) / max(len(metric_items), 1)
    conflict_risk = float(aggregation.get("conflict_score") or 0.0) * 70
    coverage_risk = (1.0 - float(aggregation.get("coverage_score") or 1.0)) * 55
    unavailable_risk = unavailable_share * 55
    return round(_clamp(max(metric_risk, conflict_risk, coverage_risk, unavailable_risk), 0, 100), 2)


def _module_semantic_profile(
    module_id: str,
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    if module_id == "kline_orderflow":
        kline_items = [item for item in metric_items if item.get("kline_trend_state")]
        primary = kline_items[0] if kline_items else {}
        trend_state = str(primary.get("kline_trend_state") or "neutral_wait_confirm")
        effective_score = float(aggregation.get("module_effective_score") or 0.0)
        legacy = {
            "price_trend_score": primary.get("price_trend_score"),
            "volume_confirmation_score": primary.get("volume_confirmation_score"),
            "candle_structure_score": primary.get("candle_structure_score"),
            "breakdown_risk_score": primary.get("breakdown_risk_score"),
            "rebound_quality_score": primary.get("rebound_quality_score"),
            "selling_pressure_score": primary.get("selling_pressure_score"),
            "kline_trend_state": trend_state,
            "module_effective_bias": _kline_effective_bias(effective_score),
            "display_state": trend_state,
            "display_summary": _kline_display_summary(trend_state, effective_score),
            "confirmation_status": primary.get("kline_confirmation_status") or "waiting",
            "top_kline_reason": primary.get("score_reason") or primary.get("metric_explanation"),
            "volume_interpretation": primary.get("volume_interpretation"),
            "candle_interpretation": primary.get("candle_interpretation"),
            "semantic_profile_version": "p3.c29.kline_orderflow.v1",
        }
        has_v22_inputs = any(_metric_by_id(metric_items, metric_id) is not None for metric_id in KLINE_V22_PROFILE_METRICS)
        if not has_v22_inputs:
            return legacy
        profile = _kline_orderflow_v22_profile(metric_items, aggregation)
        return {**legacy, **profile}
    if module_id == "event_policy":
        return _event_policy_v21_profile(metric_items, aggregation)
    if module_id == "fund_flow":
        return _fund_flow_v22_profile(metric_items, aggregation, payload)
    if module_id == "derivatives_crowding":
        funding = _metric_by_id(metric_items, "btc_funding_rate") or {}
        oi = _metric_by_id(metric_items, "btc_open_interest") or {}
        funding_state = str(funding.get("funding_state") or _funding_state_from_value(funding.get("value")))
        oi_state = str(oi.get("oi_state") or _oi_state_from_change(oi))
        crowding_states = [
            str(item.get("crowding_state"))
            for item in metric_items
            if item.get("crowding_state")
        ]
        risk = _module_risk_score(metric_items, aggregation)
        profile = _derivatives_crowding_profile(
            funding_state=funding_state,
            oi_state=oi_state,
            module_effective_score=float(aggregation.get("module_final_score") or 0.0),
            crowding_states=crowding_states,
            metric_items=metric_items,
        )
        legacy = {
            "derivatives_combo_state": crowding_states[0] if crowding_states else "combo_required",
            "crowding_score": risk,
            "liquidation_risk": risk,
            "oi_funding_combo_applied": bool(crowding_states),
            "semantic_profile_version": "p3.c32.derivatives_crowding.v2",
            **profile,
        }
        if any(_metric_by_id(metric_items, metric_id) is not None for metric_id in DERIVATIVES_CROWDING_V25_PROFILE_METRICS):
            return _derivatives_crowding_v25_profile(metric_items, aggregation, legacy)
        return legacy
    if module_id == "onchain_valuation":
        return _onchain_valuation_v22_profile(metric_items, aggregation)
    if module_id == "btc_total_state":
        return _btc_total_state_v2_profile(metric_items)
    if module_id == "options_volatility":
        return _options_volatility_v21_profile(metric_items, aggregation)
    if module_id == "asia_risk":
        return _asia_risk_v23_profile(metric_items, aggregation)
    if module_id == "crypto_breadth":
        return _crypto_breadth_v3_profile(metric_items, aggregation)
    if module_id == "macro_radar":
        return _macro_radar_v3_profile(metric_items, aggregation)
    if module_id == "dollar_liquidity":
        return _dollar_liquidity_v21_profile(metric_items, aggregation)
    if module_id == "treasury_credit":
        return _treasury_credit_v21_profile(metric_items, aggregation)
    if module_id == "trade_structure_flow":
        return _trade_structure_flow_profile(metric_items, aggregation)
    if module_id == "btc_adoption":
        return _btc_adoption_v23_profile(metric_items, aggregation)
    return {}


def _btc_total_state_v2_profile(metric_items: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        "price_state": [
            item.get("metric_id")
            for item in metric_items
            if item.get("metric_id") in {"btc_price", "btc_1h_close", "btc_1h_open", "btc_1h_high", "btc_1h_low"}
            or str(item.get("metric_id") or "").startswith("btc_return_")
            or item.get("metric_id")
            in {
                "btc_1h_return_pct",
                "btc_4h_return_pct",
                "btc_24h_return_pct",
                "btc_price_vs_1h_close_pct",
            }
        ],
        "perp_state": [
            item.get("metric_id")
            for item in metric_items
            if item.get("metric_id") in {"btc_funding_rate", "btc_funding_band", "btc_open_interest"}
            or str(item.get("metric_id") or "").startswith("btc_oi_change_")
        ],
        "cycle_context": [
            item.get("metric_id")
            for item in metric_items
            if "halving" in str(item.get("metric_id") or "")
        ],
        "audit_context": [
            item.get("metric_id")
            for item in metric_items
            if item.get("metric_id") == "btc_block_height"
        ],
    }
    price_state = _btc_total_price_state(metric_items)
    perp_state = _btc_total_perp_state(metric_items, price_state["state"])
    short_term_state, direction, score = _btc_total_short_term_state(
        price_state["state"],
        perp_state["state"],
        perp_state["confirmation"],
        perp_state["risk_state"],
        perp_state["basis"]["funding_band"],
    )
    support_drivers, pressure_drivers = _btc_total_drivers(short_term_state, price_state, perp_state)
    cycle_context = _btc_total_cycle_context(metric_items)
    audit_context = _btc_total_audit_context(metric_items)
    risk_score = {"normal": 20.0, "elevated": 65.0, "extreme": 85.0}.get(
        str(perp_state.get("risk_state") or "normal"),
        20.0,
    )
    return {
        "semantic_profile_version": "p3.c41.btc_total_state.v2",
        "direction_driver_scope": ["price_state", "perp_state"],
        "context_only_scope": ["cycle_context", "audit_context"],
        "btc_total_state_groups": groups,
        "btc_total_direction_basis": "price_state_and_perp_state",
        "cycle_context_affects_direction": False,
        "audit_context_affects_direction": False,
        "price_state": price_state,
        "perp_state": perp_state,
        "cycle_context": cycle_context,
        "audit_context": audit_context,
        "btc_short_term_state": short_term_state,
        "module_direction": direction,
        "module_effective_direction": direction,
        "module_score": score,
        "module_effective_score": score,
        "risk_score": risk_score,
        "display_state": short_term_state,
        "display_summary": _btc_total_summary(short_term_state),
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "context_notes": [
            "halving_context_only: halving metrics explain cycle background and do not affect 24h direction"
        ]
        if groups["cycle_context"]
        else [],
        "audit_notes": [
            f"{audit_context['state']}: block height is used for chain-sync audit and does not affect direction"
        ]
        if groups["audit_context"]
        else [],
    }


def _btc_total_price_state(metric_items: list[dict[str, Any]]) -> dict[str, Any]:
    price = _metric_value(metric_items, "btc_price")
    close_1h = _metric_value(metric_items, "btc_1h_close")
    return_1h = _metric_value(metric_items, "btc_1h_return_pct")
    return_4h = _metric_value(metric_items, "btc_4h_return_pct")
    return_24h = _metric_value(metric_items, "btc_24h_return_pct")
    price_change = return_24h
    if price_change is None:
        price_item = _metric_by_id(metric_items, "btc_price") or {}
        price_change = _history_change(price_item, "change_24h")
    if price_change is None:
        close_item = _metric_by_id(metric_items, "btc_1h_close") or {}
        price_change = _history_change(close_item, "change_24h")
    if price_change is None and price and close_1h:
        price_change = (price - close_1h) / abs(close_1h)
    state = "price_context_missing"
    strength = "weak"
    if price_change is not None:
        if price_change > 0.003:
            state = "price_up"
        elif price_change < -0.003:
            state = "price_down"
        else:
            state = "price_flat"
        abs_change = abs(price_change)
        strength = "strong" if abs_change >= 0.02 else "normal" if abs_change >= 0.0075 else "weak"
    return {
        "state": state,
        "strength": strength,
        "basis": {
            "btc_price": price,
            "btc_1h_close": close_1h,
            "btc_1h_return_pct": return_1h,
            "btc_4h_return_pct": return_4h,
            "btc_24h_return_pct": price_change,
            "btc_price_vs_1h_close_pct": (price - close_1h) / abs(close_1h)
            if price is not None and close_1h
            else None,
        },
        "affects_direction": True,
    }


def _btc_total_perp_state(
    metric_items: list[dict[str, Any]],
    price_state: str,
) -> dict[str, Any]:
    funding = _metric_value(metric_items, "btc_funding_rate")
    funding_band_value = _metric_value(metric_items, "btc_funding_band")
    oi = _metric_value(metric_items, "btc_open_interest")
    oi_change_1h = _metric_value(metric_items, "btc_oi_change_1h_pct")
    oi_change_4h = _metric_value(metric_items, "btc_oi_change_4h_pct")
    oi_change_24h = _metric_value(metric_items, "btc_oi_change_24h_pct")
    if oi_change_24h is None:
        oi_change_24h = _history_change(_metric_by_id(metric_items, "btc_open_interest") or {}, "change_24h")
    oi_change = oi_change_1h if oi_change_1h is not None else oi_change_4h if oi_change_4h is not None else oi_change_24h
    oi_state = "oi_missing"
    if oi_change is not None:
        oi_state = "oi_up" if oi_change > 0.003 else "oi_down" if oi_change < -0.003 else "oi_flat"
    funding_band = _btc_total_funding_band(funding, funding_band_value)
    state = "perp_neutral"
    confirmation = "not_confirming"
    risk_state = "normal"
    if price_state == "price_up" and oi_state == "oi_up":
        if funding_band in {"elevated_positive", "extreme_positive"}:
            state = "long_crowding"
            confirmation = "confirming"
            risk_state = "extreme" if funding_band == "extreme_positive" else "elevated"
        else:
            state = "healthy_participation"
            confirmation = "confirming"
    elif price_state == "price_up" and oi_state == "oi_down":
        state = "short_covering"
        confirmation = "weak_confirming"
    elif price_state == "price_down" and oi_state == "oi_up":
        state = "long_crowding" if funding is not None and funding > 0 else "perp_pressure"
        confirmation = "confirming"
        risk_state = "elevated" if funding is not None and funding > 0 else "normal"
    elif price_state == "price_down" and oi_state == "oi_down":
        state = "deleveraging"
        confirmation = "weak_confirming"
    elif funding_band == "negative" and price_state in {"price_up", "price_flat"}:
        state = "short_crowding"
        confirmation = "risk_only"
    return {
        "state": state,
        "confirmation": confirmation,
        "risk_state": risk_state,
        "basis": {
            "btc_funding_rate": funding,
            "btc_funding_band": funding_band,
            "funding_band": funding_band,
            "btc_open_interest": oi,
            "btc_oi_change_1h_pct": oi_change_1h,
            "btc_oi_change_4h_pct": oi_change_4h,
            "btc_oi_change_24h_pct": oi_change_24h,
            "oi_state": oi_state,
        },
        "affects_direction": True,
    }


def _btc_total_short_term_state(
    price_state: str,
    perp_state: str,
    confirmation: str,
    risk_state: str,
    funding_band: str,
) -> tuple[str, str, float]:
    if price_state == "price_up" and perp_state == "healthy_participation":
        return "price_up_confirmed", "bullish", 0.35
    if price_state == "price_up" and perp_state == "short_covering":
        return "short_covering_bounce", "bullish", 0.18
    if price_state == "price_up" and perp_state == "long_crowding":
        return "overheated_upside", "bullish", 0.20
    if price_state == "price_down" and perp_state == "long_crowding":
        return "long_crowding_downside", "bearish", -0.42
    if price_state == "price_down" and perp_state == "deleveraging":
        return "deleveraging_downside", "bearish", -0.25
    if price_state == "price_down":
        return "price_down_confirmed", "bearish", -0.35 if confirmation == "confirming" else -0.18
    if funding_band == "negative" and price_state in {"price_up", "price_flat"}:
        return "short_squeeze_potential", "bullish" if price_state == "price_up" else "neutral", 0.12 if price_state == "price_up" else 0.0
    if risk_state in {"elevated", "extreme"} and price_state == "price_flat":
        return "neutral_wait_confirm", "neutral", 0.0
    return "neutral_wait_confirm", "neutral", 0.0


def _btc_total_cycle_context(metric_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "state": "halving_context_only",
        "basis": {
            "btc_halving_estimated_days": _metric_value(metric_items, "btc_halving_estimated_days"),
            "btc_halving_blocks_remaining": _metric_value(metric_items, "btc_halving_blocks_remaining"),
        },
        "affects_direction": False,
        "affects_confidence": False,
    }


def _btc_total_audit_context(metric_items: list[dict[str, Any]]) -> dict[str, Any]:
    block_height = _metric_by_id(metric_items, "btc_block_height")
    state = "block_height_missing"
    if block_height and block_height.get("available"):
        freshness = str(block_height.get("freshness_status") or "")
        state = "block_height_stale" if block_height.get("is_stale") or freshness in {"stale", "expired"} else "block_height_synced"
    return {
        "state": state,
        "basis": {"btc_block_height": _metric_value(metric_items, "btc_block_height")},
        "affects_direction": False,
        "affects_confidence": False,
    }


def _btc_total_drivers(
    short_term_state: str,
    price_state: dict[str, Any],
    perp_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    driver = {
        "driver_type": "composite",
        "state": short_term_state,
        "price_state": price_state.get("state"),
        "perp_state": perp_state.get("state"),
        "confirmation": perp_state.get("confirmation"),
    }
    if short_term_state in {"price_up_confirmed", "short_covering_bounce", "overheated_upside", "short_squeeze_potential"}:
        return [driver], []
    if short_term_state in {"price_down_confirmed", "long_crowding_downside", "deleveraging_downside"}:
        return [], [driver]
    return [], []


def _btc_total_summary(short_term_state: str) -> str:
    return {
        "price_up_confirmed": "price up with OI expansion and mild funding confirms short-term BTC support",
        "short_covering_bounce": "price up while OI falls, so the bounce is likely supported by short covering",
        "overheated_upside": "price and OI rise together, but funding is elevated; direction is bullish with higher crowding risk",
        "long_crowding_downside": "price falls while OI and positive funding persist, showing downside pressure from crowded longs",
        "deleveraging_downside": "price falls while OI contracts, indicating bearish pressure with leverage release",
        "price_down_confirmed": "price structure is down and perps are not offsetting the weakness",
        "short_squeeze_potential": "negative funding with stable or rising price marks squeeze potential, not standalone trend confirmation",
        "neutral_wait_confirm": "price, OI and funding do not form a decisive short-term BTC state",
    }.get(short_term_state, short_term_state)


def _btc_total_funding_band(value: float | None, band_value: float | None = None) -> str:
    if value is None:
        if band_value is not None:
            if band_value >= 2:
                return "extreme_positive"
            if band_value >= 1:
                return "elevated_positive"
            if band_value <= -1:
                return "negative"
            return "mild"
        return "missing"
    if value >= 0.001:
        return "extreme_positive"
    if value >= 0.0003:
        return "elevated_positive"
    if value <= -0.0001:
        return "negative"
    return "mild"


def _history_change(item: dict[str, Any], key: str) -> float | None:
    history = item.get("history_context") or {}
    value = history.get(key)
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _metric_by_id(metric_items: list[dict[str, Any]], metric_id: str) -> dict[str, Any] | None:
    return next((item for item in metric_items if item.get("metric_id") == metric_id), None)


def _metric_value(metric_items: list[dict[str, Any]], metric_id: str) -> float | None:
    item = _metric_by_id(metric_items, metric_id)
    if not item:
        return None
    value = item.get("value")
    if value is None:
        value = item.get("current")
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _metric_value_any(metric_items: list[dict[str, Any]], metric_ids: tuple[str, ...]) -> float | None:
    for metric_id in metric_ids:
        value = _metric_value(metric_items, metric_id)
        if value is not None:
            return value
    return None


def _kline_orderflow_v22_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    ret_5m = _metric_value_any(metric_items, ("btc_return_5m", "btc_return_5m_proxy")) or 0.0
    ret_15m = _metric_value(metric_items, "btc_return_15m") or 0.0
    ret_1h = _metric_value(metric_items, "btc_return_1h") or 0.0
    slope_tstat = _metric_value(metric_items, "btc_slope_tstat_1h") or 0.0
    slope_accel = _metric_value_any(metric_items, ("btc_slope_acceleration_15m", "btc_slope_acceleration_15m_proxy")) or 0.0
    volume_z = _metric_value(metric_items, "btc_volume_zscore_1h") or 0.0
    taker_z = _metric_value(metric_items, "btc_taker_imbalance_z_60") or 0.0
    taker_accel = _metric_value(metric_items, "btc_taker_imbalance_accel_3") or 0.0
    flow_accept_1h = _metric_value(metric_items, "btc_flow_price_acceptance_1h") or 0.0
    flow_accept_15m = _metric_value(metric_items, "btc_flow_price_acceptance_15m")
    flow_accept = flow_accept_15m if flow_accept_15m is not None else flow_accept_1h
    vwap_z = _metric_value(metric_items, "btc_price_vs_vwap_1h_z") or 0.0
    vwap_z_5m = _metric_value(metric_items, "btc_price_vs_vwap_z_5m")
    vwap_duration = _metric_value_any(
        metric_items,
        ("btc_vwap_acceptance_duration_15m", "btc_vwap_acceptance_duration_5m", "btc_vwap_acceptance_duration_1m_proxy"),
    ) or 0.0
    residual_z = _metric_value(metric_items, "btc_orderflow_residual_z_60") or 0.0
    false_breakout = _metric_value(metric_items, "btc_false_breakout_score") or 0.0
    false_breakdown = _metric_value(metric_items, "btc_false_breakdown_score") or 0.0
    breakout = _metric_value(metric_items, "btc_local_range_breakout_1h") or 0.0
    breakdown = _metric_value(metric_items, "btc_local_range_breakdown_1h") or 0.0
    lower_wick = _metric_value(metric_items, "btc_lower_wick_ratio_1h") or 0.0
    volatility_code = _metric_value(metric_items, "btc_volatility_regime_code") or 0.0
    volatility_regime = _kline_volatility_regime(volatility_code)

    slope_acceleration_score = _clamp(slope_accel / 0.006, -1.0, 1.0) * 100
    aggressor_flow_score = _clamp(taker_accel / 0.35, -1.0, 1.0) * 100
    vwap_reclaim_rejection_score = _clamp((vwap_z / 1.5) + (vwap_duration / 8.0), -1.0, 1.0) * 100
    micro_range_break_score = _clamp((breakout - breakdown) + (ret_5m / 0.006), -1.0, 1.0) * 100
    residual_surprise_score = _clamp(residual_z / 1.5, -1.0, 1.0) * 100
    trend_sensitivity_score = round(
        0.25 * slope_acceleration_score
        + 0.25 * aggressor_flow_score
        + 0.20 * vwap_reclaim_rejection_score
        + 0.15 * micro_range_break_score
        + 0.15 * residual_surprise_score,
        2,
    )

    price_structure_score = _clamp((slope_tstat / 2.5) + (ret_15m / 0.01) + (ret_1h / 0.02), -1.0, 1.0) * 100
    flow_price_acceptance_score = _clamp(flow_accept, -1.0, 1.0) * 100
    vwap_acceptance_score = _clamp((vwap_z / 1.5) + (vwap_duration / 6.0), -1.0, 1.0) * 100
    volume_confirmation_score = (
        _clamp(volume_z / 2.0, 0.0, 1.0) * 100 * (1 if ret_1h >= 0 else -1)
        if abs(ret_1h) > 0.0001
        else 0.0
    )
    residual_confirmation_score = _clamp(residual_z / 1.5, -1.0, 1.0) * 100
    false_breakout_component = -100 * _clamp(false_breakout, 0.0, 1.0)
    false_breakdown_component = 100 * _clamp(false_breakdown, 0.0, 1.0)
    contradiction_penalty = 0.0
    if (price_structure_score > 25 and flow_price_acceptance_score < -25) or (
        price_structure_score < -25 and flow_price_acceptance_score > 25
    ):
        contradiction_penalty = 12.0
    data_quality_flags: list[str] = []
    data_quality_penalty = 0.0
    if _metric_by_id(metric_items, "btc_taker_imbalance_z_60") is None:
        data_quality_flags.append("taker_volume_missing")
        data_quality_penalty += 12.0
    if _metric_by_id(metric_items, "btc_return_1h") is None:
        data_quality_flags.append("kline_data_missing")
        data_quality_penalty += 30.0
    if volatility_regime == "shock_vol":
        data_quality_penalty += 8.0
    trend_reliability_score = round(
        0.30 * price_structure_score
        + 0.25 * flow_price_acceptance_score
        + 0.20 * vwap_acceptance_score
        + 0.15 * volume_confirmation_score
        + 0.10 * residual_confirmation_score
        + 0.10 * false_breakdown_component
        + 0.10 * false_breakout_component
        - data_quality_penalty
        - contradiction_penalty,
        2,
    )

    state = "neutral"
    stage = "none"
    implication = "neutral"
    module_direction = "neutral"
    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    conflict_drivers: list[str] = []
    early_warning_flags: list[str] = []
    rejection_flags: list[str] = []

    if false_breakout >= 0.5 and taker_z > 0 and residual_z <= -0.8:
        state = "false_breakout_confirmed"
        stage = "fast_signal"
        module_direction = "bearish"
        implication = "failed_upside_breakout"
        rejection_flags.append("false_breakout_with_negative_residual")
    elif false_breakdown >= 0.5 and taker_z < 0 and residual_z >= 0.8:
        state = "false_breakdown_confirmed"
        stage = "fast_signal"
        module_direction = "bullish"
        implication = "failed_downside_breakdown"
        rejection_flags.append("false_breakdown_with_positive_residual")
    elif taker_z >= 1.2 and ret_15m <= 0 and vwap_z <= 0 and residual_z <= -1.0:
        state = "taker_buy_absorption"
        stage = "early_warning"
        module_direction = "bearish"
        implication = "buy_flow_absorbed"
        rejection_flags.append("taker_buy_absorbed_by_price")
    elif taker_z <= -1.2 and ret_15m >= 0 and lower_wick >= 0.35 and residual_z >= 1.0:
        state = "taker_sell_exhaustion"
        stage = "early_warning"
        module_direction = "bullish"
        implication = "sell_pressure_exhausted"
        rejection_flags.append("taker_sell_exhausted")
    elif (
        volatility_regime != "shock_vol"
        and slope_tstat >= 2.0
        and ret_15m > 0
        and flow_accept > 0
        and vwap_z > 0
        and vwap_duration >= 2
        and residual_z >= -0.3
    ):
        state = "trend_up_confirmed"
        stage = "confirmed_signal"
        module_direction = "bullish"
        implication = "upside_trend_confirmed"
        support_drivers.extend(["price_structure_up", "flow_accepted", "vwap_accepted"])
    elif (
        volatility_regime != "shock_vol"
        and slope_tstat <= -2.0
        and ret_15m < 0
        and flow_accept < 0
        and vwap_z < 0
        and vwap_duration <= -2
        and residual_z <= 0.3
    ):
        state = "trend_down_confirmed"
        stage = "confirmed_signal"
        module_direction = "bearish"
        implication = "downside_trend_confirmed"
        pressure_drivers.extend(["price_structure_down", "flow_accepted_down", "vwap_lost"])
    elif slope_accel > 0 and taker_accel > 0 and (vwap_z_5m if vwap_z_5m is not None else vwap_z) > 0 and ret_5m > 0:
        state = "bullish_fast_shift"
        stage = "early_warning"
        module_direction = "bullish"
        implication = "upside_shift_attempt"
        early_warning_flags.append("bullish_fast_shift_unconfirmed")
    elif slope_accel < 0 and taker_accel < 0 and (vwap_z_5m if vwap_z_5m is not None else vwap_z) < 0 and ret_5m < 0:
        state = "bearish_fast_shift"
        stage = "early_warning"
        module_direction = "bearish"
        implication = "downside_shift_attempt"
        early_warning_flags.append("bearish_fast_shift_unconfirmed")
    elif abs(trend_sensitivity_score) >= 35 and abs(trend_reliability_score) < 20:
        state = "range_chop"
        stage = "conflict"
        conflict_drivers.append("sensitivity_without_reliability")

    if contradiction_penalty:
        conflict_drivers.append("price_structure_and_flow_acceptance_conflict")
        if stage == "confirmed_signal":
            stage = "conflict"
            module_direction = "neutral"

    signed_score = trend_reliability_score if stage == "confirmed_signal" else trend_sensitivity_score
    if state in {"false_breakout_confirmed", "taker_buy_absorption"}:
        signed_score = min(signed_score, -35.0)
    if state in {"false_breakdown_confirmed", "taker_sell_exhaustion"}:
        signed_score = max(signed_score, 35.0)
    module_score = round(_clamp(signed_score / 100.0, -1.0, 1.0), 4)
    confidence_score = round(_clamp(62.0 + abs(trend_reliability_score) * 0.25 - data_quality_penalty - contradiction_penalty, 0.0, 100.0), 2)
    key_levels = {
        "vwap_15m": _metric_value(metric_items, "btc_vwap_15m"),
        "vwap_1h": _metric_value(metric_items, "btc_vwap_1h"),
        "vwap_4h": None,
        "micro_range_high_15m": _metric_value_any(metric_items, ("btc_micro_range_high_15m_proxy", "btc_local_range_high_15m")),
        "micro_range_low_15m": _metric_value_any(metric_items, ("btc_micro_range_low_15m_proxy", "btc_local_range_low_15m")),
        "local_range_high_1h": _metric_value(metric_items, "btc_local_range_high_1h"),
        "local_range_low_1h": _metric_value(metric_items, "btc_local_range_low_1h"),
        "major_range_high_4h": _metric_value(metric_items, "btc_major_range_high_4h"),
        "major_range_low_4h": _metric_value(metric_items, "btc_major_range_low_4h"),
    }
    scores = {
        "price_structure_score": round(price_structure_score, 2),
        "slope_acceleration_score": round(slope_acceleration_score, 2),
        "aggressor_flow_score": round(aggressor_flow_score, 2),
        "flow_price_acceptance_score": round(flow_price_acceptance_score, 2),
        "vwap_acceptance_score": round(vwap_acceptance_score, 2),
        "volume_confirmation_score": round(volume_confirmation_score, 2),
        "residual_confirmation_score": round(residual_confirmation_score, 2),
        "false_breakout_score": round(abs(false_breakout_component), 2),
        "false_breakdown_score": round(false_breakdown_component, 2),
        "contradiction_penalty": round(contradiction_penalty, 2),
        "data_quality_penalty": round(data_quality_penalty, 2),
    }
    drivers = {
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "conflict_drivers": conflict_drivers,
        "early_warning_flags": early_warning_flags,
        "rejection_flags": rejection_flags,
        "data_quality_flags": data_quality_flags,
    }
    invalidation_conditions = _kline_v22_invalidation_conditions(state)
    summary = (
        f"kline_orderflow.v2.2 state={state}; stage={stage}; "
        f"sensitivity={trend_sensitivity_score:.1f}, reliability={trend_reliability_score:.1f}. "
        "Active flow is directional only when price, VWAP and residual accept it."
    )
    contract = {
        "semantic_profile_version": "p3.c57.kline_orderflow.v2.2",
        "module_direction": module_direction,
        "module_score": module_score,
        "trend_sensitivity_score": trend_sensitivity_score,
        "trend_reliability_score": trend_reliability_score,
        "confidence_score": confidence_score,
        "signal_stage": stage,
        "volatility_regime": volatility_regime,
        "kline_orderflow_state": state,
        "btc_implication": implication,
        "scores": scores,
        "key_levels": key_levels,
        "drivers": drivers,
        "invalidation_conditions": invalidation_conditions,
    }
    return {
        **contract,
        "version": "p3.c57.kline_orderflow.v2.2",
        "display_state": stage,
        "display_summary": summary,
        "trend_state": state,
        "trend_state_reason": summary,
        "kline_trend_state": state,
        "confirmation_status": stage,
        "top_kline_reason": summary,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "conflict_drivers": conflict_drivers,
        "early_warning_flags": early_warning_flags,
        "rejection_flags": rejection_flags,
        "data_quality_flags": data_quality_flags,
        "kline_orderflow_v22": contract,
    }


def _kline_volatility_regime(code: float) -> str:
    if code <= -0.5:
        return "low_vol"
    if code >= 1.5:
        return "shock_vol"
    if code >= 0.5:
        return "high_vol"
    return "normal_vol"


def _kline_v22_invalidation_conditions(state: str) -> list[str]:
    mapping = {
        "trend_up_confirmed": [
            "close loses 1h VWAP for two consecutive buckets",
            "flow_price_acceptance turns negative",
            "orderflow_residual_z_60 falls below -0.8",
        ],
        "trend_down_confirmed": [
            "close reclaims 1h VWAP for two consecutive buckets",
            "flow_price_acceptance turns positive",
            "orderflow_residual_z_60 rises above +0.8",
        ],
        "taker_buy_absorption": ["price closes above VWAP with positive residual"],
        "taker_sell_exhaustion": ["price loses local range low again with negative residual"],
        "false_breakout_confirmed": ["price reclaims local range high with VWAP acceptance"],
        "false_breakdown_confirmed": ["price loses local range low with VWAP rejection"],
    }
    return mapping.get(state, ["new confirmed structure in the opposite direction"])


def _score_from_signed(value: float, scale: float) -> float:
    if scale <= 0:
        return 0.0
    return _clamp(value / scale, -1.0, 1.0)


def _crypto_breadth_v3_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    btc_return_4h = _metric_value(metric_items, "btc_return_4h") or 0.0
    btc_return_24h = _metric_value_any(
        metric_items,
        ("btc_return_24h_pct", "btc_24h_return_pct", "btc_return_24h"),
    ) or 0.0
    btc_return_3d = _metric_value(metric_items, "btc_return_3d_pct") or 0.0
    btc_vol_z = _metric_value(metric_items, "btc_vol_adjusted_return_24h_z") or 0.0
    top50_advance = _metric_value_any(
        metric_items,
        ("top50_advance_pct_24h", "top50_strength"),
    ) or 0.0
    top50_advance_3d = _metric_value(metric_items, "top50_advance_pct_3d") or 0.0
    ad_slope = _metric_value(metric_items, "top50_ad_line_7d_slope") or 0.0
    equal_return = _metric_value(metric_items, "top50_equal_weight_return_24h_pct") or 0.0
    cap_return = _metric_value(metric_items, "top50_cap_weight_return_24h_pct") or 0.0
    equal_minus_cap = _metric_value(metric_items, "top50_equal_minus_cap_weight_return_24h_pct")
    if equal_minus_cap is None:
        equal_minus_cap = equal_return - cap_return
    total_return = _metric_value(metric_items, "total_return_24h_pct") or 0.0
    total2_return = _metric_value(metric_items, "total2_return_24h_pct") or 0.0
    total2_return_3d = _metric_value(metric_items, "total2_return_3d_pct") or 0.0
    total2_vs_btc = _metric_value(metric_items, "total2_vs_btc_return_24h_pct")
    if total2_vs_btc is None:
        total2_vs_btc = total2_return - btc_return_24h
    btc_d_change = _metric_value(metric_items, "btc_dominance_change_24h_pp") or 0.0
    btc_d_change_3d = _metric_value(metric_items, "btc_dominance_change_3d_pp") or 0.0
    eth_btc_return = _metric_value(metric_items, "eth_btc_return_24h_pct") or 0.0
    eth_btc_return_3d = _metric_value(metric_items, "eth_btc_return_3d_pct") or 0.0
    sector_heat = _metric_value(metric_items, "sector_heat") or 0.0
    sector_heat_change = _metric_value(metric_items, "sector_heat_change_24h") or 0.0
    overheat_penalty = _metric_value(metric_items, "overheat_penalty") or 0.0

    if btc_return_24h >= 0.025 or btc_return_3d >= 0.06:
        btc_trend_state = "strong_uptrend"
        btc_anchor_score = 0.85
    elif btc_return_24h >= 0.005 or btc_return_3d >= 0.015:
        btc_trend_state = "weak_uptrend"
        btc_anchor_score = 0.45
    elif btc_return_24h <= -0.025 or btc_return_3d <= -0.06:
        btc_trend_state = "strong_downtrend"
        btc_anchor_score = -0.85
    elif btc_return_24h <= -0.005 or btc_return_3d <= -0.015:
        btc_trend_state = "weak_downtrend"
        btc_anchor_score = -0.45
    else:
        btc_trend_state = "range"
        btc_anchor_score = 0.0

    if top50_advance >= 0.65 and ad_slope >= 0:
        breadth_state = "strong"
        breadth_score = 0.8
    elif top50_advance >= 0.55 or top50_advance_3d > 0:
        breadth_state = "improving"
        breadth_score = 0.45
    elif top50_advance <= 0.35:
        breadth_state = "weak"
        breadth_score = -0.75
    elif top50_advance <= 0.45 or ad_slope < -0.03:
        breadth_state = "deteriorating"
        breadth_score = -0.45
    else:
        breadth_state = "neutral"
        breadth_score = 0.0

    if total2_return > 0.01 and total2_vs_btc >= -0.005:
        diffusion_state = "broad_expansion"
        diffusion_score = 0.65
    elif total2_return > 0.005 and total2_vs_btc > 0:
        diffusion_state = "alt_expansion"
        diffusion_score = 0.45
    elif btc_return_24h > 0.005 and total2_vs_btc < -0.01:
        diffusion_state = "btc_only"
        diffusion_score = -0.25
    elif total2_return < -0.01:
        diffusion_state = "contraction"
        diffusion_score = -0.65
    else:
        diffusion_state = "neutral"
        diffusion_score = 0.0

    if btc_d_change > 0.25 and eth_btc_return < 0:
        leadership_state = "btc_led"
        leadership_score = 0.15 if btc_return_24h >= 0 else -0.25
    elif eth_btc_return > 0.006 and btc_d_change <= 0:
        leadership_state = "eth_led"
        leadership_score = 0.35
    elif btc_d_change < -0.25 and total2_return > 0:
        leadership_state = "alt_led"
        leadership_score = 0.30
    elif total_return < 0 and btc_d_change > 0:
        leadership_state = "stablecoin_led"
        leadership_score = -0.45
    else:
        leadership_state = "balanced"
        leadership_score = 0.0

    sector_score = _clamp((sector_heat - 50.0) / 50.0, -1.0, 1.0)
    if sector_heat >= 80:
        sector_state = "overheated"
    elif sector_heat >= 60 and sector_heat_change >= 0:
        sector_state = "risk_on"
    elif sector_heat <= 35:
        sector_state = "risk_off"
    else:
        sector_state = "balanced"

    bearish_divergence = (
        btc_return_24h > 0.005
        and (top50_advance <= 0.45 or total2_vs_btc < -0.01 or equal_minus_cap < -0.005)
    )
    bullish_divergence = (
        btc_return_24h <= 0.002
        and (top50_advance >= 0.52 or total2_vs_btc > 0.005 or eth_btc_return > 0.004)
    )
    concentrated = equal_minus_cap < -0.005 or (btc_d_change > 0.25 and top50_advance <= 0.5)
    overheated = top50_advance >= 0.75 and sector_heat >= 80 and btc_d_change < -0.25
    concentration_penalty = 0.08 if concentrated else 0.0
    total_overheat_penalty = max(overheat_penalty, 0.10 if overheated else 0.0)
    if overheated:
        quality_state = "overheated"
        quality_score = -0.35
        divergence = "none"
    elif bearish_divergence:
        quality_state = "bearish_divergence"
        quality_score = -0.65
        divergence = "bearish"
    elif bullish_divergence:
        quality_state = "bullish_divergence"
        quality_score = 0.35
        divergence = "bullish"
    elif concentrated:
        quality_state = "concentrated"
        quality_score = -0.30
        divergence = "none"
    else:
        quality_state = "healthy" if breadth_score > 0 and diffusion_score >= 0 else "neutral"
        quality_score = 0.25 if quality_state == "healthy" else 0.0
        divergence = "none"

    if overheated:
        state = "alt_chase_overheat"
        direction = "bullish"
        score = 0.08
        confidence_adjustment = -0.05
        risk_score = 78.0
        btc_implication = "rotation_supportive_but_not_outperformance"
    elif (
        btc_trend_state in {"weak_downtrend", "strong_downtrend"}
        and total2_return < 0
        and top50_advance <= 0.40
        and eth_btc_return <= 0
    ):
        state = "broad_risk_off"
        direction = "bearish"
        score = -0.35
        confidence_adjustment = 0.05
        risk_score = 82.0
        btc_implication = "risk_off_pressure"
    elif bearish_divergence:
        state = "breadth_bearish_divergence"
        direction = "bearish"
        score = -0.12
        confidence_adjustment = -0.10
        risk_score = 68.0
        btc_implication = "trend_fragile"
    elif (
        btc_trend_state in {"weak_uptrend", "strong_uptrend"}
        and top50_advance >= 0.60
        and total2_return > 0
        and eth_btc_return >= -0.003
    ):
        state = "btc_broad_confirmed_uptrend"
        direction = "bullish"
        score = 0.34
        confidence_adjustment = 0.07
        risk_score = 32.0
        btc_implication = "trend_confirmed"
    elif (
        btc_return_24h > 0.005
        and btc_d_change > 0
        and total2_return <= 0.005
        and top50_advance <= 0.45
    ):
        state = "narrow_btc_rally_fragile"
        direction = "neutral"
        score = 0.06
        confidence_adjustment = -0.08
        risk_score = 62.0
        btc_implication = "trend_fragile"
    elif btc_return_24h >= -0.002 and btc_d_change > 0.20 and eth_btc_return < 0 and total2_return <= 0.006:
        state = "btc_defensive_leadership"
        direction = "bullish"
        score = 0.10
        confidence_adjustment = -0.04
        risk_score = 48.0
        btc_implication = "defensive_bid"
    elif (
        btc_trend_state in {"range", "weak_uptrend"}
        and eth_btc_return > 0.004
        and btc_d_change < 0
        and total2_return > 0
        and top50_advance >= 0.50
    ):
        state = "alt_beta_rotation"
        direction = "bullish"
        score = 0.20
        confidence_adjustment = 0.04
        risk_score = 42.0
        btc_implication = "rotation_supportive_but_not_outperformance"
    elif btc_return_24h <= 0.002 and bullish_divergence:
        state = "risk_off_but_breadth_improving"
        direction = "neutral"
        score = 0.08
        confidence_adjustment = 0.02
        risk_score = 50.0
        btc_implication = "early_repair"
    else:
        raw_score = (
            0.25 * btc_anchor_score
            + 0.25 * breadth_score
            + 0.20 * diffusion_score
            + 0.15 * leadership_score
            + 0.10 * sector_score
            + 0.05 * _score_from_signed(equal_return, 0.03)
            - concentration_penalty
            - total_overheat_penalty
        )
        score = round(_clamp(raw_score, -0.40, 0.40), 4)
        direction = _direction_from_score(score)
        state = "neutral_wait_confirm"
        confidence_adjustment = 0.0
        risk_score = 45.0 if abs(score) < 0.08 else 55.0
        btc_implication = "neutral"
        if score >= CRYPTO_BREADTH_MILD_BULLISH_THRESHOLD:
            direction = "bullish"
            if btc_trend_state in {"weak_uptrend", "strong_uptrend"} and breadth_score > 0 and diffusion_score >= 0:
                state = "btc_broad_confirmed_uptrend"
                confidence_adjustment = 0.04
                risk_score = 38.0
                btc_implication = "trend_confirmed"
            elif diffusion_score > 0 and (breadth_score > 0 or eth_btc_return > 0 or total2_vs_btc > 0):
                state = "alt_beta_rotation"
                confidence_adjustment = 0.03
                risk_score = 44.0
                btc_implication = "rotation_supportive_but_not_outperformance"
            elif leadership_state == "btc_led" or btc_d_change > 0:
                state = "btc_defensive_leadership"
                confidence_adjustment = -0.02
                risk_score = 48.0
                btc_implication = "defensive_bid"
            else:
                state = "risk_off_but_breadth_improving"
                confidence_adjustment = 0.01
                risk_score = 50.0
                btc_implication = "early_repair"
        elif state == "neutral_wait_confirm":
            score = round(
                _clamp(
                    score,
                    -CRYPTO_BREADTH_NEUTRAL_DEADBAND,
                    CRYPTO_BREADTH_NEUTRAL_DEADBAND,
                ),
                4,
            )
            direction = "neutral"
            risk_score = 45.0

    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    risk_drivers: list[str] = []
    if breadth_score > 0:
        support_drivers.append("top50_breadth_participation")
    if diffusion_score > 0:
        support_drivers.append("total2_market_cap_diffusion")
    if eth_btc_return > 0:
        support_drivers.append("eth_btc_leadership_improving")
    if bearish_divergence:
        pressure_drivers.append("btc_up_breadth_deteriorating")
        risk_drivers.append("breadth_bearish_divergence")
    if diffusion_score < 0:
        pressure_drivers.append("market_cap_diffusion_weak")
    if concentrated:
        risk_drivers.append("breadth_concentration")
    if overheated:
        risk_drivers.append("alt_beta_overheat")

    legacy_support_count = sum(
        1
        for item in metric_items
        if str(item.get("metric_id") or "") in {"btc_dominance", "eth_btc", "top50_strength"}
        and float(item.get("metric_score") or 0.0) > 0
    )
    legacy_pressure_count = sum(
        1
        for item in metric_items
        if str(item.get("metric_id") or "") in {"btc_dominance", "eth_btc", "top50_strength"}
        and float(item.get("metric_score") or 0.0) < 0
    )
    legacy_regime = (
        "risk_expansion"
        if state in {"btc_broad_confirmed_uptrend", "alt_beta_rotation"} or legacy_support_count >= 2
        else "breadth_pressure"
        if state in {"broad_risk_off", "breadth_bearish_divergence"} or legacy_pressure_count >= 2
        else "btc_or_sector_specific"
    )
    summary = (
        f"crypto_breadth.v3 state={state}; BTC trend={btc_trend_state}, "
        f"top50 advance={top50_advance:.2f}, total2_vs_btc={total2_vs_btc:.4f}."
    )
    return {
        "module_purpose": "btc_trend_confirmation_by_crypto_market_diffusion",
        "primary_question": "is_btc_trend_confirmed_or_refuted_by_crypto_market_breadth",
        "crypto_breadth_state": state,
        "module_direction": direction,
        "module_score": round(score, 4),
        "module_effective_score": round(score, 4),
        "confidence_adjustment": confidence_adjustment,
        "risk_score": risk_score,
        "btc_implication": btc_implication,
        "btc_trend_anchor": {
            "state": btc_trend_state,
            "score": round(btc_anchor_score, 4),
            "basis": {
                "btc_return_4h_pct": btc_return_4h,
                "btc_return_24h_pct": btc_return_24h,
                "btc_return_3d_pct": btc_return_3d,
                "btc_vol_adjusted_return_24h_z": btc_vol_z,
            },
        },
        "breadth_participation": {
            "state": breadth_state,
            "score": round(breadth_score, 4),
            "basis": {
                "top50_advance_pct_24h": top50_advance,
                "top50_advance_pct_3d": top50_advance_3d,
                "top50_ad_line_7d_slope": ad_slope,
                "top50_equal_weight_return_24h_pct": equal_return,
                "top50_cap_weight_return_24h_pct": cap_return,
                "top50_equal_minus_cap_weight_return_24h_pct": equal_minus_cap,
            },
        },
        "market_cap_diffusion": {
            "state": diffusion_state,
            "score": round(diffusion_score, 4),
            "basis": {
                "total_return_24h_pct": total_return,
                "total2_return_24h_pct": total2_return,
                "total2_return_3d_pct": total2_return_3d,
                "total2_vs_btc_return_24h_pct": total2_vs_btc,
            },
        },
        "btc_vs_alt_leadership": {
            "state": leadership_state,
            "score": round(leadership_score, 4),
            "basis": {
                "btc_dominance_change_24h_pp": btc_d_change,
                "btc_dominance_change_3d_pp": btc_d_change_3d,
                "eth_btc_return_24h_pct": eth_btc_return,
                "eth_btc_return_3d_pct": eth_btc_return_3d,
            },
        },
        "sector_risk_appetite": {
            "state": sector_state,
            "score": round(sector_score, 4),
            "basis": {
                "sector_heat": sector_heat,
                "sector_heat_change_24h": sector_heat_change,
            },
        },
        "breadth_quality": {
            "state": quality_state,
            "score": round(quality_score, 4),
            "basis": {
                "breadth_price_divergence": divergence,
                "volume_breadth_confirm": breadth_score > 0 and equal_return >= 0,
                "overheat_penalty": total_overheat_penalty,
                "concentration_penalty": concentration_penalty,
            },
        },
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "risk_drivers": risk_drivers,
        "context_notes": [
            "crypto_breadth confirms or refutes BTC trend quality; it is not a standalone price target."
        ],
        "summary": summary,
        "display_summary": summary,
        "display_state": state,
        "crypto_breadth_regime": legacy_regime,
        "breadth_support_count": max(len(support_drivers), legacy_support_count),
        "breadth_pressure_count": max(len(pressure_drivers), legacy_pressure_count),
        "semantic_profile_version": "p3.c44.crypto_breadth.v3",
    }


def _macro_radar_v3_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    nasdaq_return_raw = _metric_value_any(metric_items, ("nasdaq_return_24h_pct",))
    sp500_return_raw = _metric_value_any(metric_items, ("sp500_return_24h_pct",))
    nasdaq_return = nasdaq_return_raw or 0.0
    sp500_return = sp500_return_raw or 0.0
    russell_return = _metric_value(metric_items, "russell_return_24h_pct") or 0.0
    equity_breadth = _metric_value(metric_items, "equity_breadth_score")
    if equity_breadth is None:
        equity_values = [nasdaq_return, sp500_return, russell_return]
        equity_breadth = sum(1 for value in equity_values if value > 0) / max(len(equity_values), 1)

    us2y_change = _metric_value(metric_items, "us2y_change_1d_bps") or 0.0
    us10y_change = _metric_value(metric_items, "us10y_change_1d_bps") or 0.0
    us10y_change_3d = _metric_value(metric_items, "us10y_change_3d_bps") or 0.0
    real_yield_change = _metric_value(metric_items, "real_yield_change_1d_bps") or 0.0
    curve_change = _metric_value(metric_items, "yield_curve_2s10s_change_bps") or 0.0
    rates_impulse_z = _metric_value(metric_items, "rates_impulse_z") or 0.0

    dxy_change_1h = _metric_value(metric_items, "dxy_change_1h_pct") or 0.0
    dxy_change_4h = _metric_value(metric_items, "dxy_change_4h_pct") or 0.0
    dxy_change_24h = _metric_value(metric_items, "dxy_change_24h_pct") or 0.0
    dxy_impulse_z = _metric_value(metric_items, "dxy_impulse_z") or 0.0

    vix_level = _metric_value(metric_items, "vix") or 0.0
    vix_change_1d = _metric_value(metric_items, "vix_change_1d_pct") or 0.0
    vix_change_3d = _metric_value(metric_items, "vix_change_3d_pct") or 0.0
    vix_z = _metric_value(metric_items, "vix_zscore_60d") or 0.0
    vix_impulse_z = _metric_value(metric_items, "vix_impulse_z") or 0.0

    ofr_fsi = _metric_value(metric_items, "ofr_fsi") or 0.0
    ofr_change = _metric_value(metric_items, "ofr_fsi_change_1d") or 0.0
    ofr_z = _metric_value(metric_items, "ofr_fsi_zscore_252d") or 0.0

    gold_change = _metric_value(metric_items, "gold") or 0.0
    oil_change = _metric_value_any(metric_items, ("wti_oil", "brent_oil")) or 0.0

    btc_return_1h_raw = _metric_value_any(metric_items, ("btc_return_1h_pct", "btc_return_1h"))
    btc_return_4h_raw = _metric_value_any(metric_items, ("btc_return_4h_pct", "btc_return_4h"))
    btc_return_24h_raw = _metric_value_any(
        metric_items,
        ("btc_return_24h_pct", "btc_24h_return_pct", "btc_return_24h"),
    )
    btc_return_1h = btc_return_1h_raw or 0.0
    btc_return_4h = btc_return_4h_raw or 0.0
    btc_return_24h = btc_return_24h_raw or 0.0
    btc_vs_ndx = _metric_value(metric_items, "btc_vs_ndx_relative_return")
    if btc_vs_ndx is None and btc_return_24h_raw is not None and nasdaq_return_raw is not None:
        btc_vs_ndx = btc_return_24h - nasdaq_return
    btc_vs_spx = _metric_value(metric_items, "btc_vs_spx_relative_return")
    if btc_vs_spx is None and btc_return_24h_raw is not None and sp500_return_raw is not None:
        btc_vs_spx = btc_return_24h - sp500_return
    btc_residual = _metric_value(metric_items, "btc_beta_residual")
    if btc_residual is None and btc_return_24h_raw is not None and nasdaq_return_raw is not None and sp500_return_raw is not None:
        btc_residual = btc_return_24h - ((1.25 * nasdaq_return + sp500_return) / 2.0)
    btc_follow_through = _metric_value(metric_items, "btc_macro_follow_through")

    event_hours = [
        value
        for value in (
            _metric_value(metric_items, "cpi_hours_until"),
            _metric_value(metric_items, "fomc_hours_until"),
            _metric_value(metric_items, "nfp_hours_until"),
            _metric_value(metric_items, "pce_hours_until"),
        )
        if value is not None
    ]
    nearest_event_hours = min(event_hours, key=lambda value: abs(value)) if event_hours else None
    if nearest_event_hours is not None and -1 <= nearest_event_hours <= 2:
        event_state = "post_or_live_high_impact"
        event_risk_level = "high"
        event_score_penalty = 0.06
    elif nearest_event_hours is not None and 0 < nearest_event_hours <= 6:
        event_state = "pre_event_hard_lock"
        event_risk_level = "high"
        event_score_penalty = 0.05
    elif nearest_event_hours is not None and 0 < nearest_event_hours <= 24:
        event_state = "pre_event_caution"
        event_risk_level = "medium"
        event_score_penalty = 0.03
    else:
        event_state = "neutral"
        event_risk_level = "normal"
        event_score_penalty = 0.0

    equity_score = _clamp(
        0.55 * _score_from_signed(nasdaq_return, 0.02)
        + 0.30 * _score_from_signed(sp500_return, 0.015)
        + 0.15 * _score_from_signed(russell_return, 0.02)
        + (float(equity_breadth) - 0.5) * 0.35,
        -1.0,
        1.0,
    )
    if equity_score >= 0.35 and equity_breadth >= 0.55:
        equity_state = "broad_risk_on"
    elif nasdaq_return > 0 and equity_breadth < 0.5:
        equity_state = "mega_cap_only"
    elif equity_score <= -0.35:
        equity_state = "equity_risk_off"
    else:
        equity_state = "equity_neutral"

    rate_pressure = max(us2y_change, us10y_change, real_yield_change)
    rate_tailwind = min(us2y_change, us10y_change, real_yield_change)
    if rate_pressure >= 12 or rates_impulse_z >= 1.5:
        rates_state = "rates_shock"
        rates_score = -0.9
        rates_risk = 85.0
    elif rate_pressure >= 5:
        rates_state = "rates_headwind"
        rates_score = -0.55
        rates_risk = 62.0
    elif rate_tailwind <= -5:
        rates_state = "rates_tailwind"
        rates_score = 0.45
        rates_risk = 28.0
    else:
        rates_state = "rates_neutral"
        rates_score = 0.0
        rates_risk = 35.0

    if dxy_change_4h >= 0.006 or dxy_impulse_z >= 1.5:
        dollar_state = "dollar_squeeze"
        dollar_score = -0.8
    elif dxy_change_24h >= 0.003:
        dollar_state = "dollar_headwind"
        dollar_score = -0.45
    elif dxy_change_24h <= -0.003:
        dollar_state = "dollar_tailwind"
        dollar_score = 0.40
    else:
        dollar_state = "dollar_neutral"
        dollar_score = 0.0

    if vix_change_1d >= 0.20 or vix_impulse_z >= 1.5 or vix_level >= 30:
        vol_state = "vol_shock"
        vol_score = -0.85
        vol_risk = 88.0
    elif vix_change_1d >= 0.08 or vix_z >= 1.0 or vix_level >= 24:
        vol_state = "vol_stress"
        vol_score = -0.55
        vol_risk = 68.0
    elif vix_change_1d <= -0.08 or vix_level <= 16:
        vol_state = "vol_calm"
        vol_score = 0.35
        vol_risk = 25.0
    else:
        vol_state = "vol_normal"
        vol_score = 0.0
        vol_risk = 38.0

    if ofr_z >= 1.5 or ofr_change >= 0.4:
        stress_state = "stress_shock"
        stress_score = -0.65
        stress_risk = 85.0
    elif ofr_z >= 0.75 or ofr_change > 0.1:
        stress_state = "stress_rising"
        stress_score = -0.35
        stress_risk = 62.0
    elif ofr_z <= -0.5:
        stress_state = "stress_low"
        stress_score = 0.20
        stress_risk = 25.0
    else:
        stress_state = "stress_normal"
        stress_score = 0.0
        stress_risk = 35.0

    commodity_score = 0.0
    commodity_state = "commodity_neutral"
    if oil_change > 0 and dollar_score < 0:
        commodity_state = "inflation_pressure_context"
        commodity_score = -0.10
    elif gold_change > 0 and equity_score < 0:
        commodity_state = "defensive_bid_context"
        commodity_score = -0.05

    risk_on_impulse = nasdaq_return > 0.003 and vix_change_1d < 0 and dxy_change_4h <= 0
    risk_off_impulse = (
        (dxy_change_4h > 0.003 and us2y_change > 3)
        or (vix_change_1d > 0.08 and nasdaq_return < 0)
    )
    if rate_pressure >= 12 or (dxy_impulse_z >= 1.5 and rates_impulse_z >= 1.0):
        impulse_state = "dollar_rate_shock"
        impulse_score = -0.85
    elif vix_change_1d >= 0.20 or vix_impulse_z >= 1.5:
        impulse_state = "volatility_shock"
        impulse_score = -0.65
    elif risk_off_impulse:
        impulse_state = "risk_off_impulse"
        impulse_score = -0.55
    elif risk_on_impulse:
        impulse_state = "risk_on_impulse"
        impulse_score = 0.45
    elif abs(equity_score) > 0.25 or abs(dollar_score) > 0.25 or abs(rates_score) > 0.25:
        impulse_state = "mixed_impulse"
        impulse_score = _clamp((equity_score + dollar_score + rates_score + vol_score) / 4, -0.35, 0.35)
    else:
        impulse_state = "no_impulse"
        impulse_score = 0.0

    macro_environment_score = _clamp(
        0.24 * equity_score
        + 0.22 * rates_score
        + 0.18 * dollar_score
        + 0.16 * vol_score
        + 0.10 * stress_score
        + 0.10 * commodity_score,
        -1.0,
        1.0,
    )

    relative_values = [
        value for value in (btc_residual, btc_vs_ndx, btc_vs_spx) if value is not None
    ]
    relative_signal = sum(relative_values) / len(relative_values) if relative_values else None
    missing_reasons: list[str] = []
    if not relative_values:
        missing_reasons.append("btc_relative_basis_missing")
    if btc_return_24h_raw is None and not relative_values:
        missing_reasons.append("btc_return_missing")
    if nasdaq_return_raw is None and sp500_return_raw is None and not relative_values:
        missing_reasons.append("equity_return_missing")

    if missing_reasons:
        btc_relative_state = "missing"
        btc_relative_score = 0.0
    elif macro_environment_score > 0.12 and (relative_signal or 0.0) > 0.003:
        btc_relative_state = "btc_outperforming_macro"
        btc_relative_score = 0.65
    elif macro_environment_score > 0.12 and btc_return_24h >= 0 and (btc_follow_through == 1.0 or (relative_signal or 0.0) >= -0.002):
        btc_relative_state = "btc_following_macro"
        btc_relative_score = 0.35
    elif macro_environment_score > 0.12 and (relative_signal or 0.0) < -0.004:
        btc_relative_state = "btc_rejecting_macro_tailwind"
        btc_relative_score = -0.45
    elif macro_environment_score < -0.12 and (relative_signal or 0.0) > 0.004 and btc_return_24h >= 0:
        btc_relative_state = "btc_resisting_macro_headwind"
        btc_relative_score = 0.45
    elif macro_environment_score < -0.12 and (btc_return_24h < 0 or (relative_signal or 0.0) < -0.004):
        btc_relative_state = "btc_lagging_macro"
        btc_relative_score = -0.45
    elif (relative_signal or 0.0) < -0.004:
        btc_relative_state = "btc_lagging_macro"
        btc_relative_score = -0.35
    elif (relative_signal or 0.0) > 0.004:
        btc_relative_state = "btc_resisting_macro_headwind" if macro_environment_score < 0 else "btc_outperforming_macro"
        btc_relative_score = 0.35
    else:
        btc_relative_state = "btc_following_macro"
        btc_relative_score = 0.0

    module_score_raw = (
        macro_environment_score
        + 0.30 * impulse_score
        + 0.25 * btc_relative_score
        - event_score_penalty
    )
    score = round(_clamp(module_score_raw, -0.50, 0.50), 4)

    shock_active = impulse_state in {"dollar_rate_shock", "volatility_shock"} or rates_state == "rates_shock"
    if shock_active:
        macro_state = "macro_shock_risk"
        direction = "bearish" if score < -0.10 else "neutral"
        btc_implication = "wait_for_confirmation"
        risk_score = max(rates_risk, vol_risk, stress_risk, 82.0)
        confidence_adjustment = -0.14
    elif macro_environment_score > 0.12 and btc_relative_state in {"btc_outperforming_macro", "btc_following_macro"}:
        macro_state = "macro_trend_confirmed_bullish"
        direction = "bullish"
        btc_implication = "macro_confirmed_uptrend"
        risk_score = max(25.0, min(rates_risk, vol_risk, stress_risk))
        confidence_adjustment = 0.08
    elif macro_environment_score > 0.12 and btc_relative_state == "btc_rejecting_macro_tailwind":
        macro_state = "macro_tailwind_but_btc_lagging"
        direction = "neutral"
        score = round(_clamp(score, 0.02, 0.12), 4)
        btc_implication = "macro_tailwind_not_absorbed"
        risk_score = 48.0
        confidence_adjustment = -0.05
    elif macro_environment_score < -0.12 and btc_relative_state in {"btc_lagging_macro", "btc_following_macro"}:
        macro_state = "macro_headwind_confirmed_bearish"
        direction = "bearish"
        btc_implication = "macro_confirmed_downtrend"
        risk_score = max(rates_risk, vol_risk, stress_risk, 68.0)
        confidence_adjustment = -0.10
    elif macro_environment_score < -0.12 and btc_relative_state == "btc_resisting_macro_headwind":
        macro_state = "btc_resisting_macro_headwind"
        direction = "neutral"
        score = round(_clamp(score, -0.05, 0.12), 4)
        btc_implication = "btc_internal_strength_against_macro"
        risk_score = 55.0
        confidence_adjustment = 0.02
    elif abs(score) >= 0.08:
        macro_state = "macro_mixed"
        direction = _direction_from_score(score)
        btc_implication = "wait_for_confirmation"
        risk_score = max(rates_risk, vol_risk, stress_risk, 50.0)
        confidence_adjustment = -0.02 if risk_score >= 60 else 0.0
    else:
        macro_state = "macro_neutral"
        direction = "neutral"
        btc_implication = "neutral"
        risk_score = max(rates_risk, vol_risk, stress_risk, 35.0)
        confidence_adjustment = 0.0

    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    risk_drivers: list[str] = []
    invalidation_conditions: list[str] = []
    if equity_score > 0.25:
        support_drivers.append("equity_beta_risk_on")
    if rates_score > 0.2:
        support_drivers.append("rates_tailwind")
    if dollar_score > 0.2:
        support_drivers.append("dollar_tailwind")
    if btc_relative_score > 0.2:
        support_drivers.append("btc_relative_strength")
    if rates_score < -0.25:
        pressure_drivers.append("rates_pressure")
        risk_drivers.append(rates_state)
    if dollar_score < -0.25:
        pressure_drivers.append("dollar_pressure")
        risk_drivers.append(dollar_state)
    if vol_score < -0.25:
        risk_drivers.append(vol_state)
    if stress_score < -0.25:
        risk_drivers.append(stress_state)
    if btc_relative_score < -0.2:
        pressure_drivers.append("btc_not_absorbing_macro_tailwind")
    if event_state != "neutral":
        risk_drivers.append(event_state)
    if direction == "bullish":
        invalidation_conditions.extend([
            "DXY and US2Y impulse turn higher together",
            "BTC beta residual turns negative while equities stay firm",
        ])
    elif direction == "bearish":
        invalidation_conditions.extend([
            "BTC residual turns positive against macro headwind",
            "VIX falls while Nasdaq and BTC recover together",
        ])

    summary = (
        f"macro_radar.v3 state={macro_state}; environment={macro_environment_score:.3f}, "
        f"impulse={impulse_state}, BTC relative={btc_relative_state}."
    )
    return {
        "module_purpose": "btc_macro_trend_confirmation_and_refutation",
        "timeframe_focus": {
            "sensitive_window": "1h-4h",
            "trend_window": "24h-3d",
            "event_window": "0-24h around high-impact macro events",
        },
        "equity_beta": {
            "state": equity_state,
            "score": round(equity_score, 4),
            "basis": {
                "nasdaq_return_24h_pct": nasdaq_return,
                "sp500_return_24h_pct": sp500_return,
                "russell_return_24h_pct": russell_return,
                "equity_breadth_score": equity_breadth,
            },
        },
        "rates_pressure": {
            "state": rates_state,
            "score": round(rates_score, 4),
            "risk_score": rates_risk,
            "basis": {
                "us2y_change_1d_bps": us2y_change,
                "us10y_change_1d_bps": us10y_change,
                "us10y_change_3d_bps": us10y_change_3d,
                "real_yield_change_1d_bps": real_yield_change,
                "yield_curve_2s10s_change_bps": curve_change,
                "rates_impulse_z": rates_impulse_z,
            },
        },
        "dollar_pressure": {
            "state": dollar_state,
            "score": round(dollar_score, 4),
            "basis": {
                "dxy_change_1h_pct": dxy_change_1h,
                "dxy_change_4h_pct": dxy_change_4h,
                "dxy_change_24h_pct": dxy_change_24h,
                "dxy_impulse_z": dxy_impulse_z,
            },
        },
        "volatility_stress": {
            "state": vol_state,
            "score": round(vol_score, 4),
            "risk_score": vol_risk,
            "basis": {
                "vix": vix_level,
                "vix_change_1d_pct": vix_change_1d,
                "vix_change_3d_pct": vix_change_3d,
                "vix_zscore_60d": vix_z,
                "vix_impulse_z": vix_impulse_z,
            },
        },
        "financial_stress": {
            "state": stress_state,
            "score": round(stress_score, 4),
            "risk_score": stress_risk,
            "basis": {
                "ofr_fsi": ofr_fsi,
                "ofr_fsi_change_1d": ofr_change,
                "ofr_fsi_zscore_252d": ofr_z,
            },
        },
        "commodity_context": {
            "state": commodity_state,
            "score": round(commodity_score, 4),
            "basis": {
                "gold": gold_change,
                "oil": oil_change,
            },
        },
        "macro_impulse": {
            "state": impulse_state,
            "score": round(impulse_score, 4),
            "basis": {
                "risk_on_impulse": risk_on_impulse,
                "risk_off_impulse": risk_off_impulse,
                "dxy_impulse_z": dxy_impulse_z,
                "rates_impulse_z": rates_impulse_z,
                "vix_impulse_z": vix_impulse_z,
            },
        },
        "btc_relative_confirmation": {
            "state": btc_relative_state,
            "score": round(btc_relative_score, 4),
            "missing_reason": ";".join(missing_reasons) if missing_reasons else None,
            "btc_beta_residual": None if btc_residual is None else round(float(btc_residual), 6),
            "basis": {
                "btc_return_1h_pct": btc_return_1h,
                "btc_return_4h_pct": btc_return_4h,
                "btc_return_24h_pct": btc_return_24h,
                "btc_vs_ndx_relative_return": btc_vs_ndx,
                "btc_vs_spx_relative_return": btc_vs_spx,
                "btc_macro_follow_through": btc_follow_through,
            },
        },
        "event_window": {
            "state": event_state,
            "risk_level": event_risk_level,
            "nearest_event_hours": nearest_event_hours,
            "score_penalty": event_score_penalty,
        },
        "macro_trend_state": macro_state,
        "module_direction": direction,
        "module_score": score,
        "module_effective_score": score,
        "risk_score": round(risk_score, 2),
        "confidence_adjustment": confidence_adjustment,
        "btc_implication": btc_implication,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "risk_drivers": risk_drivers,
        "invalidation_conditions": invalidation_conditions,
        "context_notes": [
            "macro_radar.v3 confirms or refutes BTC trend quality through cross-asset macro context.",
            "DXY, VIX, rates, equities and commodities are composite inputs, not standalone BTC direction calls.",
        ],
        "summary": summary,
        "display_summary": summary,
        "display_state": macro_state,
        "semantic_profile_version": "p3.c45.macro_radar.v3",
    }


def _dollar_liquidity_v21_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    fed_assets = _metric_value(metric_items, "fed_balance_sheet")
    tga = _metric_value(metric_items, "tga")
    on_rrp = _metric_value(metric_items, "on_rrp")
    reserves = _metric_value(metric_items, "bank_reserves")
    sofr = _metric_value(metric_items, "sofr")
    iorb = _metric_value(metric_items, "iorb")
    net_liquidity = _metric_value(metric_items, "net_liquidity_proxy_bil")
    net_change_1w = _metric_value(metric_items, "net_liquidity_change_1w_bil") or 0.0
    net_change_4w = _metric_value(metric_items, "net_liquidity_change_4w_bil") or 0.0
    impulse_z = _metric_value(metric_items, "liquidity_impulse_z") or 0.0
    acceleration = _metric_value(metric_items, "liquidity_acceleration") or 0.0
    reserve_change = _metric_value(metric_items, "reserve_change_1w_bil") or 0.0
    tga_change = _metric_value(metric_items, "tga_change_1w_bil") or 0.0
    rrp_depleted = bool((_metric_value(metric_items, "rrp_depleted") or 0.0) >= 0.5)
    spread = _metric_value(metric_items, "sofr_iorb_spread_bps")
    funding_stress_z = _metric_value(metric_items, "funding_stress_z") or 0.0
    sofr_jump = _metric_value(metric_items, "sofr_jump_1d_bps") or 0.0
    btc_1d = _metric_value(metric_items, "btc_1d_return") or 0.0
    btc_5d = _metric_value(metric_items, "btc_5d_return") or 0.0
    btc_20d = _metric_value(metric_items, "btc_20d_return") or 0.0
    btc_residual = _metric_value(metric_items, "btc_vs_liquidity_residual")
    if btc_residual is None:
        btc_residual = btc_5d - _clamp(net_change_1w / 1000.0, -0.08, 0.08)

    if impulse_z >= 1.0 and net_change_1w > 50:
        liquidity_impulse_score, impulse_state = 0.25, "expansion_impulse"
    elif impulse_z >= 0.5 or net_change_1w > 50:
        liquidity_impulse_score, impulse_state = 0.12, "expansion_impulse"
    elif impulse_z <= -1.0 and net_change_1w < -50:
        liquidity_impulse_score, impulse_state = -0.25, "contraction_impulse"
    elif impulse_z <= -0.5 or net_change_1w < -50:
        liquidity_impulse_score, impulse_state = -0.12, "contraction_impulse"
    elif abs(acceleration) >= 50:
        liquidity_impulse_score = 0.06 if acceleration > 0 else -0.06
        impulse_state = "mixed"
    else:
        liquidity_impulse_score, impulse_state = 0.0, "neutral"

    if reserve_change > 50:
        reserve_score, reserve_state = 0.15, "reserve_buffer_improving"
    elif reserve_change < -50:
        reserve_score, reserve_state = -0.15, "reserve_buffer_deteriorating"
    else:
        reserve_score, reserve_state = 0.0, "reserve_buffer_stable"

    if tga_change < -50:
        tga_score, drain_state = 0.15, "drain_easing"
    elif tga_change > 50:
        tga_score, drain_state = -0.15, "drain_intensifying"
    else:
        tga_score, drain_state = 0.0, "drain_neutral"
    if rrp_depleted and drain_state == "drain_easing":
        tga_score = min(tga_score, 0.08)
        drain_state = "drain_easing_but_rrp_buffer_low"

    spread_value = float(spread or 0.0)
    if spread_value > 15 or funding_stress_z > 1.5 or sofr_jump > 12:
        funding_score, funding_state, funding_risk = -0.25, "stress", 82.0
    elif spread_value > 5 or sofr_jump > 5:
        funding_score, funding_state, funding_risk = -0.10, "tightening", 62.0
    elif spread_value < -10 and funding_stress_z < 0:
        funding_score, funding_state, funding_risk = 0.05, "easing", 25.0
    else:
        funding_score, funding_state, funding_risk = 0.0, "normal", 35.0

    if liquidity_impulse_score > 0 and btc_5d > 0:
        btc_response_state, btc_response_score = "absorbing_tailwind", 0.20
    elif liquidity_impulse_score > 0 and btc_5d <= 0:
        btc_response_state, btc_response_score = "rejecting_tailwind", -0.10
    elif liquidity_impulse_score < 0 and btc_5d < 0:
        btc_response_state, btc_response_score = "following_headwind", -0.20
    elif liquidity_impulse_score < 0 and btc_5d >= 0:
        btc_response_state, btc_response_score = "resisting_headwind", 0.10
    else:
        btc_response_state, btc_response_score = "neutral", 0.0

    raw_score = (
        0.30 * liquidity_impulse_score
        + 0.20 * reserve_score
        + 0.15 * tga_score
        + 0.20 * funding_score
        + 0.30 * btc_response_score
    )
    score = round(_clamp(raw_score, -0.45, 0.45), 4)

    if funding_score <= -0.25:
        state = "funding_stress_override"
        direction = "bearish"
        risk_score = max(funding_risk, 78.0)
        confidence_adjustment = -0.12
    elif liquidity_impulse_score > 0 and funding_score >= 0 and btc_response_score > 0:
        state, direction = "liquidity_tailwind_confirmed", "bullish"
        risk_score, confidence_adjustment = max(25.0, funding_risk), 0.06
    elif liquidity_impulse_score > 0 and btc_response_score < 0:
        state, direction = "liquidity_tailwind_rejected", "neutral"
        score = round(_clamp(score, -0.05, 0.12), 4)
        risk_score, confidence_adjustment = max(48.0, funding_risk), -0.05
    elif liquidity_impulse_score < 0 and btc_response_score < 0:
        state, direction = "liquidity_headwind_confirmed", "bearish"
        risk_score, confidence_adjustment = max(65.0, funding_risk), -0.08
    elif liquidity_impulse_score < 0 and btc_response_score > 0:
        state, direction = "btc_internal_strength_against_liquidity_headwind", "neutral"
        score = round(_clamp(score, -0.05, 0.12), 4)
        risk_score, confidence_adjustment = max(45.0, funding_risk), 0.02
    elif abs(score) >= 0.08:
        state, direction = "liquidity_mixed", _direction_from_score(score)
        risk_score = max(42.0, funding_risk)
        confidence_adjustment = -0.02 if risk_score >= 60 else 0.0
    else:
        state, direction = "liquidity_neutral", "neutral"
        risk_score, confidence_adjustment = funding_risk, 0.0

    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    risk_drivers: list[str] = []
    if liquidity_impulse_score > 0:
        support_drivers.append("net_liquidity_expansion")
    if reserve_score > 0:
        support_drivers.append("reserve_buffer_improving")
    if btc_response_score > 0:
        support_drivers.append("btc_absorbing_or_resisting_liquidity")
    if liquidity_impulse_score < 0:
        pressure_drivers.append("net_liquidity_contraction")
    if reserve_score < 0:
        pressure_drivers.append("reserve_buffer_deteriorating")
    if btc_response_score < 0:
        pressure_drivers.append("btc_rejecting_or_following_liquidity")
    if funding_score < 0:
        risk_drivers.append(f"repo_funding_{funding_state}")
    if rrp_depleted:
        risk_drivers.append("liquidity_buffer_low")

    summary = (
        f"dollar_liquidity.v2.1 state={state}; impulse={impulse_state}, "
        f"funding={funding_state}, BTC response={btc_response_state}."
    )
    return {
        "semantic_profile_version": "p3.c46.dollar_liquidity.v2.1",
        "module_purpose": "confirm_or_refute_btc_trend_by_usd_liquidity_and_funding_conditions",
        "data_freshness": {
            "weekly_macro_asof": None,
            "daily_funding_asof": None,
            "btc_price_asof": None,
            "is_stale": False,
            "stale_reasons": [],
        },
        "liquidity_level": {
            "fed_assets_bil": (fed_assets / 1000.0) if fed_assets is not None else None,
            "tga_bil": (tga / 1000.0) if tga is not None else None,
            "on_rrp_bil": on_rrp,
            "bank_reserves_bil": (reserves / 1000.0) if reserves is not None else None,
            "net_liquidity_proxy_bil": net_liquidity,
            "rrp_depleted": rrp_depleted,
        },
        "liquidity_impulse": {
            "net_liquidity_change_1w_bil": net_change_1w,
            "net_liquidity_change_4w_bil": net_change_4w,
            "liquidity_impulse_z": impulse_z,
            "liquidity_acceleration": acceleration,
            "state": impulse_state,
            "score": round(liquidity_impulse_score, 4),
        },
        "reserve_buffer": {
            "reserve_change_1w_bil": reserve_change,
            "state": reserve_state,
            "score": round(reserve_score, 4),
        },
        "liquidity_drain_pressure": {
            "tga_change_1w_bil": tga_change,
            "rrp_depleted": rrp_depleted,
            "state": drain_state,
            "score": round(tga_score, 4),
        },
        "repo_funding_pressure": {
            "sofr": sofr,
            "iorb": iorb,
            "sofr_iorb_spread_bps": spread,
            "funding_stress_z": funding_stress_z,
            "sofr_jump_1d_bps": sofr_jump,
            "state": funding_state,
            "score": round(funding_score, 4),
        },
        "btc_response_confirmation": {
            "btc_1d_return": btc_1d,
            "btc_5d_return": btc_5d,
            "btc_20d_return": btc_20d,
            "btc_vs_liquidity_residual": btc_residual,
            "state": btc_response_state,
            "score": round(btc_response_score, 4),
        },
        "dollar_liquidity_state": state,
        "module_direction": direction,
        "module_score": score,
        "module_effective_score": score,
        "risk_score": round(risk_score, 2),
        "confidence_adjustment": confidence_adjustment,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "risk_drivers": risk_drivers,
        "context_notes": [
            "dollar_liquidity.v2.1 uses net liquidity, repo funding pressure and BTC response confirmation.",
            "Raw SOFR, TGA, ON RRP and Fed balance sheet levels are composite inputs, not standalone BTC direction calls.",
        ],
        "summary": summary,
        "display_state": state,
        "display_summary": summary,
    }


def _fund_flow_v22_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    etf_1d = _metric_value_any(metric_items, ("etf_net_flow_usd", "etf_net_flow")) or 0.0
    etf_3d = _metric_value(metric_items, "etf_flow_3d_usd") or etf_1d
    etf_7d = _metric_value_any(metric_items, ("etf_flow_7d_usd", "etf_flow_7d")) or etf_3d
    etf_z_1d = _metric_value(metric_items, "etf_flow_1d_z_60d") or 0.0
    etf_z_3d = _metric_value(metric_items, "etf_flow_3d_z_60d") or 0.0
    etf_z_7d = _metric_value(metric_items, "etf_flow_7d_z_60d") or 0.0
    inflow_streak = _metric_value(metric_items, "etf_inflow_streak_days") or 0.0
    outflow_streak = _metric_value(metric_items, "etf_outflow_streak_days") or 0.0
    etf_accel = _metric_value(metric_items, "etf_flow_acceleration_3d") or 0.0
    etf_reversal = (_metric_value(metric_items, "etf_flow_reversal_2d") or 0.0) >= 1.0
    etf_shock = (_metric_value(metric_items, "etf_flow_shock_flag") or 0.0) >= 1.0
    source_count = _metric_value(metric_items, "etf_flow_data_source_count") or 0.0
    source_diff = _metric_value(metric_items, "etf_flow_cross_source_diff_pct") or 0.0

    stable_7d = _metric_value(metric_items, "stablecoin_mcap_change_7d") or 0.0
    stable_30d = _metric_value(metric_items, "stablecoin_mcap_change_30d") or 0.0
    stable_z = _metric_value(metric_items, "stablecoin_mcap_change_7d_z_120d") or 0.0
    ssr_z = _metric_value(metric_items, "ssr_z_180d") or 0.0
    liquidity_regime = _metric_value(metric_items, "stablecoin_liquidity_regime") or 0.0

    exchange_1d = _metric_value_any(
        metric_items,
        ("btc_exchange_netflow_1d", "exchange_balance_delta_1d_proxy"),
    ) or 0.0
    exchange_7d = _metric_value(metric_items, "btc_exchange_netflow_7d") or exchange_1d
    exchange_z = _metric_value(metric_items, "btc_exchange_netflow_z_60d") or 0.0
    large_transfer = (_metric_value(metric_items, "large_single_transfer_flag") or 0.0) >= 1.0
    exchange_confirmed = (_metric_value(metric_items, "exchange_flow_confirmed") or 0.0) >= 1.0

    btc_return_4h = _metric_value_any(metric_items, ("btc_return_4h", "btc_4h_return_pct")) or 0.0
    btc_return_24h = _metric_value_any(
        metric_items,
        ("btc_return_24h", "btc_return_24h_pct", "btc_24h_return_pct"),
    ) or 0.0
    btc_return_3d = _metric_value_any(metric_items, ("btc_return_3d", "btc_return_3d_pct")) or 0.0
    expected_return = _metric_value(metric_items, "fund_flow_expected_return_24h") or 0.0
    residual = _metric_value(metric_items, "fund_flow_residual_24h")
    if residual is None:
        residual = btc_return_24h - expected_return
    residual_z = _metric_value(metric_items, "fund_flow_residual_z_60d") or 0.0

    etf_score = _clamp(
        22.0 * etf_z_1d
        + 20.0 * etf_z_3d
        + 16.0 * etf_z_7d
        + (6.0 * min(inflow_streak, 5.0))
        - (7.0 * min(outflow_streak, 5.0))
        + (12.0 if etf_accel > 0 else -12.0 if etf_accel < 0 else 0.0)
        + (10.0 if etf_3d > 0 else -10.0 if etf_3d < 0 else 0.0)
        + (-8.0 if etf_reversal and etf_1d < 0 else 8.0 if etf_reversal and etf_1d > 0 else 0.0),
        -100.0,
        100.0,
    )
    stablecoin_score = _clamp(
        38.0 * liquidity_regime
        + 18.0 * stable_z
        - 14.0 * ssr_z
        + (8.0 if stable_7d > 0 and stable_30d > 0 else -8.0 if stable_7d < 0 and stable_30d <= 0 else 0.0),
        -100.0,
        100.0,
    )
    exchange_score = 0.0 if large_transfer else _clamp(
        -38.0 * exchange_z
        + (12.0 if exchange_7d < 0 else -12.0 if exchange_7d > 0 else 0.0),
        -100.0,
        100.0,
    )
    btc_response_score = _clamp(
        48.0 * residual_z
        + (12.0 if residual > 0 else -12.0 if residual < 0 else 0.0)
        + (8.0 if btc_return_24h > 0 else -8.0 if btc_return_24h < 0 else 0.0),
        -100.0,
        100.0,
    )

    data_quality_penalty = 0.0
    data_quality_flags: list[str] = []
    early_warning_flags: list[str] = []
    if source_count == 1:
        data_quality_flags.append("etf_single_source")
    if source_diff > 0.15:
        data_quality_penalty += 6.0
        data_quality_flags.append("etf_cross_source_mismatch")
    if large_transfer:
        data_quality_penalty += 10.0
        data_quality_flags.append("possible_exchange_internal_transfer")
    if etf_shock:
        early_warning_flags.append("etf_flow_shock")
    stale_metrics = [
        item.get("metric_id")
        for item in metric_items
        if item.get("is_stale") is True and str(item.get("metric_id") or "").startswith("etf")
    ]
    if stale_metrics:
        data_quality_penalty += 8.0
        data_quality_flags.append("etf_flow_stale")

    raw_weighted_score = (
        0.40 * etf_score
        + 0.20 * stablecoin_score
        + 0.20 * exchange_score
        + 0.20 * btc_response_score
        - data_quality_penalty
    )
    state = "fund_flow_neutral"
    direction = "neutral"
    btc_implication = "neutral"
    confidence_score = 72.0 - data_quality_penalty

    if abs(exchange_z) >= 2.0 and large_transfer:
        state, direction, btc_implication = "exchange_flow_untrusted", "neutral", "data_quality_warning"
        raw_weighted_score = _clamp(raw_weighted_score, -15.0, 15.0)
        confidence_score -= 10.0
    elif (etf_3d > 0 or stable_7d > 0) and btc_return_24h <= 0 and residual_z <= -1.0:
        state, direction, btc_implication = "btc_rejecting_flow_tailwind", "bearish", "internal_weakness"
        raw_weighted_score = _clamp(raw_weighted_score, -70.0, -28.0)
        confidence_score += 10.0
    elif (etf_3d < 0 or exchange_z >= 1.0) and btc_return_24h >= 0 and residual_z >= 1.0:
        state, direction, btc_implication = "btc_resisting_flow_headwind", "bullish", "internal_strength"
        raw_weighted_score = _clamp(raw_weighted_score, 25.0, 65.0)
        confidence_score += 10.0
    elif etf_3d < 0 and etf_7d < 0 and outflow_streak >= 3 and btc_return_24h < 0 and residual_z < 0:
        state, direction, btc_implication = "etf_outflow_confirmed", "bearish", "institutional_demand_drag"
        raw_weighted_score = _clamp(raw_weighted_score, -75.0, -35.0)
        confidence_score += 8.0
    elif (etf_z_1d <= -1.0 or outflow_streak >= 2 or etf_reversal) and btc_return_24h >= -0.005:
        state, direction, btc_implication = "etf_outflow_warning", "neutral", "trend_fragile"
        raw_weighted_score = _clamp(raw_weighted_score, -28.0, -8.0)
        early_warning_flags.append("etf_outflow_warning")
    elif etf_3d > 0 and etf_7d > 0 and etf_z_7d >= 0.75 and inflow_streak >= 3 and btc_return_24h > 0 and residual_z >= 0:
        state, direction, btc_implication = "etf_demand_confirmed", "bullish", "trend_confirmed"
        raw_weighted_score = _clamp(raw_weighted_score, 30.0, 68.0)
        confidence_score += 8.0
    elif (etf_z_1d >= 1.0 or etf_accel > 0 or inflow_streak >= 2) and (btc_return_4h >= 0 or btc_return_24h >= 0):
        state, direction, btc_implication = "etf_demand_accelerating", "bullish", "early_institutional_demand"
        raw_weighted_score = _clamp(raw_weighted_score, 10.0, 35.0)
        early_warning_flags.append("etf_demand_accelerating")
    elif etf_7d > 0 and etf_accel < 0 and etf_z_1d <= -0.5:
        state, direction, btc_implication = "etf_demand_fading", "neutral", "bullish_momentum_fading"
        raw_weighted_score = _clamp(raw_weighted_score, -24.0, -5.0)
        early_warning_flags.append("etf_demand_fading")
    elif stable_7d > 0 and stable_30d > 0 and ssr_z <= 0 and btc_return_3d >= 0:
        state, direction, btc_implication = "stablecoin_liquidity_tailwind", "bullish", "liquidity_support"
        raw_weighted_score = _clamp(raw_weighted_score, 8.0, 28.0)
    elif stable_7d < 0 and stable_30d <= 0 and ssr_z > 0:
        state, direction, btc_implication = "stablecoin_liquidity_drain", "bearish", "liquidity_drain"
        raw_weighted_score = _clamp(raw_weighted_score, -32.0, -8.0)
    elif exchange_7d < 0 and exchange_z <= -1.0 and not large_transfer and etf_3d >= 0 and btc_return_24h >= 0:
        state, direction, btc_implication = "supply_squeeze_support", "bullish", "tradable_supply_tight"
        raw_weighted_score = _clamp(raw_weighted_score, 10.0, 34.0)
    elif exchange_1d > 0 and exchange_z >= 1.5 and btc_return_24h <= 0 and not large_transfer:
        state, direction, btc_implication = "exchange_supply_pressure", "bearish", "spot_supply_pressure"
        raw_weighted_score = _clamp(raw_weighted_score, -45.0, -18.0)

    risk_score = _clamp(
        35.0
        + max(0.0, -etf_score) * 0.25
        + max(0.0, -stablecoin_score) * 0.12
        + max(0.0, -exchange_score) * 0.18
        + max(0.0, data_quality_penalty),
        0.0,
        100.0,
    )
    if state in {"etf_outflow_confirmed", "exchange_supply_pressure", "btc_rejecting_flow_tailwind"}:
        risk_score = max(risk_score, 68.0)
    if state == "exchange_flow_untrusted":
        risk_score = max(risk_score, 55.0)
    module_score = round(_clamp(raw_weighted_score / 100.0, -0.75, 0.68), 4)
    confidence_score = round(_clamp(confidence_score, 25.0, 95.0), 2)

    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    if etf_score > 15:
        support_drivers.append("etf_demand")
    if stablecoin_score > 15:
        support_drivers.append("stablecoin_liquidity")
    if exchange_score > 15:
        support_drivers.append("tradable_supply_tight")
    if btc_response_score > 15:
        support_drivers.append("btc_accepting_or_resisting_flow")
    if etf_score < -15:
        pressure_drivers.append("etf_outflow_or_fading")
    if stablecoin_score < -15:
        pressure_drivers.append("stablecoin_liquidity_drain")
    if exchange_score < -15:
        pressure_drivers.append("exchange_supply_pressure")
    if btc_response_score < -15:
        pressure_drivers.append("btc_rejecting_flow")

    summary = (
        f"fund_flow.v2.2 state={state}; ETF score={round(etf_score, 1)}, "
        f"stablecoin score={round(stablecoin_score, 1)}, exchange score={round(exchange_score, 1)}, "
        f"BTC response={round(btc_response_score, 1)}."
    )
    return {
        "semantic_profile_version": "p3.c50.fund_flow.v2.2",
        "module_purpose": "fund_flow_confirmation_rejection_for_btc_trend",
        "timeframe": {
            "fast_warning": "4h-24h",
            "confirmation": "1d-7d",
            "regime": "20d-60d",
        },
        "fund_flow_state": state,
        "module_direction": direction,
        "module_score": module_score,
        "module_effective_score": module_score,
        "risk_score": round(risk_score, 2),
        "confidence_score": confidence_score,
        "btc_implication": btc_implication,
        "scores": {
            "etf_demand_score": round(etf_score, 2),
            "stablecoin_liquidity_score": round(stablecoin_score, 2),
            "exchange_supply_score": round(exchange_score, 2),
            "btc_response_score": round(btc_response_score, 2),
            "data_quality_penalty": round(data_quality_penalty, 2),
        },
        "states": {
            "etf_demand": {
                "state": state if state.startswith("etf_") else "etf_neutral",
                "flow_1d_z": etf_z_1d,
                "flow_3d_usd": etf_3d,
                "flow_7d_usd": etf_7d,
                "inflow_streak_days": inflow_streak,
                "outflow_streak_days": outflow_streak,
                "flow_acceleration_3d": etf_accel,
            },
            "stablecoin_liquidity": {
                "state": "stablecoin_liquidity_tailwind"
                if liquidity_regime > 0
                else "stablecoin_liquidity_drain"
                if liquidity_regime < 0
                else "stablecoin_liquidity_neutral",
                "mcap_change_7d": stable_7d,
                "mcap_change_30d": stable_30d,
                "ssr_z_180d": ssr_z,
            },
            "exchange_supply": {
                "state": "exchange_flow_untrusted"
                if large_transfer
                else "exchange_supply_pressure"
                if exchange_z >= 1.5
                else "supply_squeeze_support"
                if exchange_z <= -1.0
                else "exchange_supply_neutral",
                "btc_exchange_netflow_1d": exchange_1d,
                "btc_exchange_netflow_7d": exchange_7d,
                "btc_exchange_netflow_z_60d": exchange_z,
                "large_single_transfer_flag": large_transfer,
                "exchange_flow_confirmed": exchange_confirmed,
            },
            "btc_response_confirmation": {
                "state": "btc_rejecting_flow_tailwind"
                if residual_z <= -1.0
                else "btc_resisting_flow_headwind"
                if residual_z >= 1.0
                else "btc_flow_response_neutral",
                "btc_return_4h": btc_return_4h,
                "btc_return_24h": btc_return_24h,
                "expected_return_24h": expected_return,
                "residual_24h": residual,
                "residual_z_60d": residual_z,
            },
        },
        "fund_flow_absolute_direction": payload.get("fund_flow_absolute_direction") or direction,
        "fund_flow_marginal_direction": payload.get("fund_flow_marginal_direction") or "v2_state_machine",
        "fund_flow_conflict_level": payload.get("fund_flow_conflict_level")
        or ("high" if state in {"btc_rejecting_flow_tailwind", "btc_resisting_flow_headwind"} else "low"),
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "early_warning_flags": sorted(set(early_warning_flags)),
        "data_quality_flags": data_quality_flags,
        "context_notes": [
            "fund_flow.v2.2 scores whether ETF, stablecoin and exchange-supply signals are accepted or rejected by BTC price response.",
            "Stablecoin supply is a liquidity regime input, not a standalone BTC buy signal.",
            "Large exchange netflow spikes are downgraded when single-transfer/internal-transfer risk is present.",
        ],
        "summary": summary,
        "display_state": state,
        "display_summary": summary,
    }


def _onchain_valuation_v22_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    btc_price = _metric_value_any(metric_items, ("btc_price", "btc_1h_close")) or 0.0
    realized_price = _metric_value_any(metric_items, ("realized_price", "realized_price_derived"))
    sth_cost = _metric_value(metric_items, "sth_cost_basis")
    lth_cost = _metric_value(metric_items, "lth_cost_basis")
    sth_upper = _metric_value(metric_items, "sth_upper_band")
    sth_lower = _metric_value(metric_items, "sth_lower_band")
    sth_band = _metric_value(metric_items, "sth_band_pct") or 0.02
    btc_vs_sth = _metric_value(metric_items, "btc_vs_sth_cost_basis_pct") or 0.0
    btc_vs_realized = _metric_value(metric_items, "btc_vs_realized_price_pct") or 0.0
    btc_vs_lth = _metric_value(metric_items, "btc_vs_lth_cost_basis_pct") or 0.0
    mvrv = _metric_value(metric_items, "mvrv_zscore")
    mvrv_ratio = _metric_value(metric_items, "mvrv_ratio")
    nupl = _metric_value_any(metric_items, ("nupl", "nupl_proxy"))
    sopr = _metric_value(metric_items, "sopr")
    sopr_z = _metric_value(metric_items, "sopr_z_90d") or 0.0
    sopr_change = _metric_value(metric_items, "sopr_change_1d") or 0.0
    sopr_cross = _metric_value(metric_items, "sopr_cross_1_direction") or 0.0
    sopr_above_streak = _metric_value(metric_items, "sopr_above_1_streak_days") or 0.0
    sopr_below_streak = _metric_value(metric_items, "sopr_below_1_streak_days") or 0.0
    realized_cap_impulse = _metric_value(metric_items, "realized_cap_impulse_z_180d") or 0.0
    realized_cap_change_30d = _metric_value(metric_items, "realized_cap_change_30d_pct") or 0.0
    residual_z = _metric_value(metric_items, "onchain_residual_z_90d") or 0.0
    residual = _metric_value(metric_items, "onchain_residual_24h") or 0.0
    expected_return = _metric_value(metric_items, "onchain_expected_return_24h") or 0.0
    btc_return_4h = _metric_value_any(metric_items, ("onchain_btc_return_4h", "btc_return_4h")) or 0.0
    btc_return_24h = _metric_value_any(
        metric_items, ("onchain_btc_return_24h", "btc_return_24h", "btc_24h_return_pct")
    ) or 0.0
    btc_return_3d = _metric_value_any(metric_items, ("onchain_btc_return_3d", "btc_return_3d")) or 0.0
    btc_return_7d = _metric_value(metric_items, "onchain_btc_return_7d") or 0.0
    miner_pressure = _metric_value(metric_items, "miner_pressure_proxy") or 0.0
    whale_pressure = _metric_value(metric_items, "whale_pressure_proxy") or 0.0

    valuation_regime_score = 0.0
    if mvrv is not None:
        if mvrv < 0.5:
            valuation_regime_score += 35.0
        elif mvrv < 1.2:
            valuation_regime_score += 18.0
        elif mvrv < 3.5:
            valuation_regime_score += 4.0
        elif mvrv < 7.0:
            valuation_regime_score -= 28.0
        else:
            valuation_regime_score -= 55.0
    if nupl is not None:
        if nupl < 0.25:
            valuation_regime_score += 26.0
        elif nupl < 0.5:
            valuation_regime_score += 6.0
        elif nupl < 0.75:
            valuation_regime_score -= 24.0
        else:
            valuation_regime_score -= 48.0
    if mvrv_ratio is not None and mvrv is None:
        valuation_regime_score += 18.0 if mvrv_ratio < 1.2 else -25.0 if mvrv_ratio > 3.0 else 0.0
    valuation_regime_score = _clamp(valuation_regime_score, -100.0, 100.0)

    lth_cost_basis_score = _clamp(
        70.0 * btc_vs_lth if lth_cost else 0.0,
        -45.0,
        45.0,
    )
    realized_cap_trend_score = _clamp(
        35.0 * realized_cap_impulse + 18.0 * (1.0 if realized_cap_change_30d > 0 else -1.0 if realized_cap_change_30d < 0 else 0.0),
        -100.0,
        100.0,
    )
    miner_whale_context_score = _clamp(-18.0 * miner_pressure - 18.0 * whale_pressure, -60.0, 30.0)

    btc_response_score = _clamp(
        48.0 * residual_z
        + (12.0 if residual > 0 else -12.0 if residual < 0 else 0.0)
        + (8.0 if btc_return_24h > 0 else -8.0 if btc_return_24h < 0 else 0.0),
        -100.0,
        100.0,
    )
    cost_basis_reaction_score = _clamp(
        180.0 * btc_vs_sth
        + (20.0 if sth_upper and btc_price > sth_upper else -20.0 if sth_lower and btc_price < sth_lower else 0.0)
        + (10.0 if btc_vs_realized > 0 else -10.0 if btc_vs_realized < 0 else 0.0),
        -100.0,
        100.0,
    )
    profit_realization_delta_score = _clamp(
        22.0 * sopr_cross
        + 25.0 * sopr_change
        + (14.0 if sopr is not None and sopr >= 1.0 else -14.0 if sopr is not None else 0.0)
        - max(sopr_z - 1.2, 0.0) * 22.0,
        -100.0,
        100.0,
    )
    realized_cap_impulse_score = _clamp(38.0 * realized_cap_impulse, -100.0, 100.0)

    trend_delta_score = _clamp(
        0.35 * btc_response_score
        + 0.30 * cost_basis_reaction_score
        + 0.20 * profit_realization_delta_score
        + 0.15 * realized_cap_impulse_score,
        -100.0,
        100.0,
    )
    regime_score = _clamp(
        0.35 * valuation_regime_score
        + 0.25 * realized_cap_trend_score
        + 0.20 * lth_cost_basis_score
        + 0.20 * miner_whale_context_score,
        -100.0,
        100.0,
    )

    data_quality_penalty = 0.0
    data_quality_flags: list[str] = []
    proxy_flags: list[str] = []
    exact_metric_ids = {str(item.get("metric_id")) for item in metric_items if item.get("metric_id")}
    if "sopr" not in exact_metric_ids:
        data_quality_penalty += 8.0
        data_quality_flags.append("sopr_missing")
    if "sth_cost_basis" not in exact_metric_ids:
        data_quality_penalty += 10.0
        proxy_flags.append("sth_cost_basis_proxy_or_missing")
    if "lth_cost_basis" not in exact_metric_ids:
        proxy_flags.append("lth_cost_basis_proxy_or_missing")
    if "miner_flow" not in exact_metric_ids:
        proxy_flags.append("miner_provider_optional_missing")
    if "whale_flow" not in exact_metric_ids:
        proxy_flags.append("whale_provider_optional_missing")
    if any(item.get("is_stale") is True for item in metric_items if item.get("metric_id") in {"sth_cost_basis", "lth_cost_basis"}):
        data_quality_penalty += 10.0
        data_quality_flags.append("sth_lth_cost_basis_stale")

    signal_stage = "none"
    state = "onchain_neutral"
    direction = "neutral"
    implication = "neutral"
    early_warning_flags: list[str] = []
    support_drivers: list[str] = []
    pressure_drivers: list[str] = []

    confirmed_bullish = 0
    confirmed_bearish = 0
    if sth_upper and btc_price > sth_upper and sopr is not None and sopr >= 1 and realized_cap_impulse >= 0 and residual_z > 0:
        confirmed_bullish += 1
    if realized_cap_impulse > 0.5 and btc_return_3d > 0 and residual_z >= 0:
        confirmed_bullish += 1
    if sth_lower and btc_price < sth_lower and sopr is not None and sopr < 1 and sopr_below_streak >= 2 and residual_z < -1:
        confirmed_bearish += 1
    if (regime_score > 0 or realized_cap_impulse > 0) and btc_return_3d <= 0 and residual_z <= -1 and (not sth_cost or btc_vs_sth <= sth_band):
        confirmed_bearish += 1

    if confirmed_bullish >= 2:
        state, direction, signal_stage, implication = "sth_reclaim_confirmed", "bullish", "confirmed_signal", "trend_reclaim"
        trend_delta_score = max(trend_delta_score, 35.0)
    elif confirmed_bearish >= 2:
        state, direction, signal_stage, implication = "sth_breakdown_confirmed", "bearish", "confirmed_signal", "trend_breakdown"
        trend_delta_score = min(trend_delta_score, -35.0)
    elif (regime_score > 0 or realized_cap_impulse > 0) and btc_return_3d <= 0 and residual_z <= -1:
        state, direction, signal_stage, implication = "btc_rejecting_onchain_tailwind", "bearish", "confirmed_signal", "internal_weakness"
        trend_delta_score = min(trend_delta_score, -32.0)
    elif (sopr_cross > 0 and btc_return_24h > 0 and sopr_change > 0) or (
        sth_upper and btc_price > sth_upper and btc_return_24h > 0 and residual_z > 0
    ):
        state, direction, signal_stage, implication = "sth_reclaim_fast", "bullish", "fast_signal", "trend_reclaim"
        trend_delta_score = max(trend_delta_score, 18.0)
    elif sth_cost and abs(btc_vs_sth) <= sth_band and btc_return_24h <= 0 and residual_z < -0.8:
        state, direction, signal_stage, implication = "sth_rejection_fast", "bearish", "fast_signal", "trend_fragile"
        trend_delta_score = min(trend_delta_score, -18.0)
    elif sopr_z >= 1.2 and btc_return_24h <= 0 and btc_return_3d <= btc_return_7d:
        state, direction, signal_stage, implication = "profit_taking_warning", "neutral", "early_warning", "distribution_risk"
        early_warning_flags.append("sopr_profit_taking_warning")
    elif sth_cost and abs(btc_vs_sth) <= sth_band and residual_z < -0.5:
        state, direction, signal_stage, implication = "sth_retest_warning", "neutral", "early_warning", "trend_fragile"
        early_warning_flags.append("sth_retest_warning")
    elif valuation_regime_score < -45:
        state, direction, signal_stage, implication = "euphoria_top_risk", "neutral", "early_warning", "distribution_risk"
        early_warning_flags.append("valuation_overheated")

    if valuation_regime_score > 0 and btc_response_score <= -40 and residual_z <= -1:
        state, direction, signal_stage, implication = "btc_rejecting_onchain_tailwind", "bearish", "confirmed_signal", "internal_weakness"
        trend_delta_score = min(trend_delta_score, -40.0)

    if cost_basis_reaction_score > 15:
        support_drivers.append("sth_cost_basis_reclaim_or_support")
    if realized_cap_impulse_score > 15:
        support_drivers.append("realized_cap_inflow")
    if btc_response_score > 15:
        support_drivers.append("btc_accepting_onchain_tailwind")
    if valuation_regime_score > 15:
        support_drivers.append("valuation_regime_supportive")
    if cost_basis_reaction_score < -15:
        pressure_drivers.append("sth_cost_basis_breakdown_or_rejection")
    if profit_realization_delta_score < -15:
        pressure_drivers.append("sopr_profit_taking_or_loss_realization")
    if btc_response_score < -15:
        pressure_drivers.append("btc_rejecting_onchain_tailwind")
    if miner_whale_context_score < -15:
        pressure_drivers.append("miner_whale_proxy_pressure")

    module_score = _clamp((0.70 * trend_delta_score + 0.30 * regime_score - data_quality_penalty) / 100.0, -0.80, 0.80)
    module_bias = (
        "supportive"
        if regime_score >= 18
        else "fragile"
        if regime_score <= -18
        else "overheated"
        if valuation_regime_score <= -45
        else "capitulation"
        if valuation_regime_score >= 45 and btc_vs_sth < 0
        else "neutral"
    )
    confidence_score = _clamp(
        72.0
        + min(abs(trend_delta_score), 40.0) * 0.18
        - data_quality_penalty
        - (8.0 if signal_stage == "early_warning" else 0.0),
        25.0,
        95.0,
    )
    risk_score = _clamp(40.0 + max(0.0, -trend_delta_score) * 0.35 + max(0.0, -regime_score) * 0.2, 0.0, 100.0)

    invalidation_conditions = _onchain_invalidation_conditions(state, sth_cost, sth_upper, sth_lower)
    summary = (
        f"onchain_valuation.v2.2 state={state}; stage={signal_stage}; "
        f"trend_delta={round(trend_delta_score, 1)}, regime={round(regime_score, 1)}, "
        f"residual_z={round(residual_z, 2)}."
    )
    return {
        "semantic_profile_version": "p3.c52.onchain_valuation.v2.2",
        "module_purpose": "onchain_cost_basis_profitability_confirmation_rejection",
        "module_direction": direction,
        "module_bias": module_bias,
        "module_score": round(module_score, 4),
        "module_effective_score": round(module_score, 4),
        "trend_delta_score": round(trend_delta_score, 2),
        "regime_score": round(regime_score, 2),
        "confidence_score": round(confidence_score, 2),
        "risk_score": round(risk_score, 2),
        "signal_stage": signal_stage,
        "onchain_valuation_state": state,
        "btc_implication": implication,
        "scores": {
            "btc_response_score": round(btc_response_score, 2),
            "cost_basis_reaction_score": round(cost_basis_reaction_score, 2),
            "profit_realization_delta_score": round(profit_realization_delta_score, 2),
            "realized_cap_impulse_score": round(realized_cap_impulse_score, 2),
            "valuation_regime_score": round(valuation_regime_score, 2),
            "realized_cap_trend_score": round(realized_cap_trend_score, 2),
            "lth_cost_basis_score": round(lth_cost_basis_score, 2),
            "miner_whale_context_score": round(miner_whale_context_score, 2),
            "data_quality_penalty": round(data_quality_penalty, 2),
        },
        "states": {
            "valuation_regime": {
                "state": module_bias,
                "mvrv_zscore": mvrv,
                "mvrv_ratio": mvrv_ratio,
                "nupl": nupl,
            },
            "cost_basis": {
                "state": "above_sth_band"
                if sth_upper and btc_price > sth_upper
                else "below_sth_band"
                if sth_lower and btc_price < sth_lower
                else "testing_sth_band"
                if sth_cost and abs(btc_vs_sth) <= sth_band
                else "cost_basis_neutral",
                "btc_vs_sth_cost_basis_pct": btc_vs_sth,
                "sth_band_pct": sth_band,
            },
            "profit_realization": {
                "state": "sopr_recovery"
                if sopr_cross > 0
                else "sopr_loss_realization"
                if sopr is not None and sopr < 1
                else "sopr_profit_taking_warning"
                if sopr_z >= 1.2
                else "sopr_neutral",
                "sopr": sopr,
                "sopr_z_90d": sopr_z,
                "sopr_cross_1_direction": sopr_cross,
                "sopr_above_1_streak_days": sopr_above_streak,
                "sopr_below_1_streak_days": sopr_below_streak,
            },
            "btc_response_confirmation": {
                "state": "btc_rejecting_onchain_tailwind"
                if residual_z <= -1
                else "btc_accepting_onchain_tailwind"
                if residual_z >= 1
                else "btc_onchain_response_neutral",
                "expected_return_24h": expected_return,
                "residual_24h": residual,
                "residual_z_90d": residual_z,
                "btc_return_4h": btc_return_4h,
                "btc_return_24h": btc_return_24h,
                "btc_return_3d": btc_return_3d,
            },
        },
        "key_levels": {
            "realized_price": realized_price,
            "sth_cost_basis": sth_cost,
            "sth_upper_band": sth_upper,
            "sth_lower_band": sth_lower,
            "lth_cost_basis": lth_cost,
        },
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "early_warning_flags": sorted(set(early_warning_flags)),
        "invalidation_conditions": invalidation_conditions,
        "proxy_flags": sorted(set(proxy_flags)),
        "data_quality_flags": data_quality_flags,
        "context_notes": [
            "MVRV and NUPL are regime inputs and cannot confirm short-term direction alone.",
            "STH cost basis uses a dynamic volatility band instead of a fixed 2% threshold.",
            "Confirmed signals require price response, an on-chain metric and BTC residual evidence.",
            "Tier-3 miner/whale proxies are context only and cannot trigger confirmed_signal.",
        ],
        "summary": summary,
        "display_state": state,
        "display_summary": summary,
        "onchain_cost_basis_state": state,
        "cost_basis_combo_applied": True,
        "valuation_state_count": sum(1 for item in metric_items if item.get("valuation_state")),
    }


def _onchain_invalidation_conditions(
    state: str,
    sth_cost: float | None,
    sth_upper: float | None,
    sth_lower: float | None,
) -> list[str]:
    if state in {"sth_reclaim_fast", "sth_reclaim_confirmed"}:
        level = sth_cost or sth_lower
        return [
            f"BTC closes back below STH cost basis ({round(level, 2) if level else 'missing'})",
            "SOPR falls back below 1 for at least 1 daily sample",
            "onchain_residual_z_90d turns negative",
        ]
    if state in {"sth_rejection_fast", "sth_breakdown_confirmed", "btc_rejecting_onchain_tailwind"}:
        level = sth_cost or sth_upper
        return [
            f"BTC reclaims STH cost basis ({round(level, 2) if level else 'missing'})",
            "SOPR recovers above 1",
            "onchain_residual_z_90d turns positive",
        ]
    if state == "profit_taking_warning":
        return [
            "BTC absorbs profit taking with positive 24h return",
            "SOPR_z_90d cools below 1.0",
        ]
    return ["No active onchain signal; invalidation requires a new fast or confirmed state."]


def _btc_adoption_v23_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    active_z = _metric_value(metric_items, "active_entities_or_addresses_z_60d") or 0.0
    tx_z = _metric_value(metric_items, "transaction_count_z_60d") or 0.0
    tx_z_30d = _metric_value(metric_items, "transaction_count_z_30d") or tx_z
    transfer_z = _metric_value(metric_items, "transfer_volume_adjusted_usd_z_60d") or 0.0
    transfer_z_30d = _metric_value(metric_items, "transfer_volume_adjusted_usd_z_30d") or transfer_z
    transfer_change_7d = _metric_value(metric_items, "transfer_volume_adjusted_usd_change_7d_pct") or 0.0
    settlement_velocity_z = _metric_value(metric_items, "settlement_velocity_z_60d") or 0.0
    nvt = _metric_value(metric_items, "nvt_proxy")
    nvt_z = _metric_value(metric_items, "nvt_proxy_z_180d") or 0.0
    nvt_change = _metric_value(metric_items, "nvt_proxy_change_7d") or 0.0
    fee_pressure_z = _metric_value_any(metric_items, ("fee_pressure_z_60d", "fee_pressure_z_30d")) or 0.0
    mempool_vsize_z = _metric_value(metric_items, "mempool_vsize_z_30d") or 0.0
    activity_spike_flag = _metric_value(metric_items, "activity_spike_flag") or 0.0
    congestion_flag = _metric_value(metric_items, "congestion_without_settlement_flag") or 0.0
    hashrate_change = _clamp(_metric_value(metric_items, "hashrate_14d_ma_change_7d_pct") or 0.0, -0.25, 0.25)
    hashrate_z = _metric_value(metric_items, "hashrate_z_90d") or 0.0
    hashprice_z = _metric_value(metric_items, "hashprice_z_90d")
    if hashprice_z is None:
        hashprice_z = _metric_value(metric_items, "hashprice_z") or 0.0
    miner_revenue_z = _metric_value(metric_items, "miner_revenue_z_90d") or 0.0
    miner_pressure = _metric_value(metric_items, "miner_security_pressure_proxy") or 0.0
    lightning_health = _metric_value(metric_items, "lightning_public_network_health_score") or 0.0
    lightning_capacity_change = _metric_value(metric_items, "lightning_capacity_change_30d_pct") or 0.0
    reachable_nodes_change = _metric_value(metric_items, "bitcoin_reachable_nodes_change_30d_pct") or 0.0
    residual_z = _metric_value(metric_items, "adoption_residual_z_90d") or 0.0
    residual = _metric_value(metric_items, "adoption_residual_24h") or 0.0
    expected_return = _metric_value(metric_items, "adoption_expected_return_24h") or 0.0
    btc_return_4h = _metric_value_any(metric_items, ("adoption_btc_return_4h", "btc_return_4h")) or 0.0
    btc_return_24h = _metric_value_any(
        metric_items, ("adoption_btc_return_24h", "btc_return_24h", "btc_24h_return_pct")
    ) or 0.0
    btc_return_3d = _metric_value_any(metric_items, ("adoption_btc_return_3d", "btc_return_3d")) or 0.0
    btc_return_7d = _metric_value_any(metric_items, ("adoption_btc_return_7d", "btc_return_7d")) or 0.0

    activity_quality_score = _clamp(
        22.0 * active_z + 18.0 * tx_z + 20.0 * transfer_z,
        -100.0,
        100.0,
    )
    if activity_spike_flag >= 1.0:
        activity_quality_score = min(activity_quality_score, 0.0)
    short_activity_impulse_score = _clamp(22.0 * tx_z_30d + 16.0 * active_z, -100.0, 100.0)
    settlement_demand_score = _clamp(
        35.0 * transfer_z - 35.0 * nvt_change + 14.0 * settlement_velocity_z,
        -100.0,
        100.0,
    )
    short_settlement_impulse_score = _clamp(35.0 * transfer_z_30d - 20.0 * nvt_change, -100.0, 100.0)
    nvt_improvement_score = _clamp(-70.0 * nvt_change - 15.0 * nvt_z, -100.0, 100.0)
    fee_mempool_score = _clamp(
        18.0 * fee_pressure_z
        + 10.0 * mempool_vsize_z
        - 25.0 * congestion_flag,
        -100.0,
        100.0,
    )
    btc_response_score = _clamp(
        45.0 * residual_z
        + (12.0 if residual > 0 else -12.0 if residual < 0 else 0.0)
        + (8.0 if btc_return_24h > 0 else -8.0 if btc_return_24h < 0 else 0.0),
        -100.0,
        100.0,
    )
    price_acceptance_score = _metric_value(metric_items, "price_acceptance_score")
    if price_acceptance_score is None:
        price_acceptance_score = btc_response_score

    network_security_score = _clamp(18.0 * hashrate_z + 35.0 * hashrate_change - 30.0 * miner_pressure, -100.0, 100.0)
    miner_pressure_score = _clamp(-28.0 * miner_pressure + 12.0 * hashprice_z + 8.0 * miner_revenue_z, -100.0, 100.0)
    l2_adoption_score = _clamp(0.35 * lightning_health + 80.0 * lightning_capacity_change, -100.0, 100.0)
    network_health_score = _clamp(45.0 * reachable_nodes_change + 0.25 * network_security_score, -100.0, 100.0)

    fast_trend_score = _clamp(
        0.40 * btc_response_score
        + 0.25 * fee_mempool_score
        + 0.20 * short_activity_impulse_score
        + 0.15 * short_settlement_impulse_score,
        -100.0,
        100.0,
    )
    core_confirmation_score = _clamp(
        0.35 * settlement_demand_score
        + 0.25 * activity_quality_score
        + 0.25 * nvt_improvement_score
        + 0.15 * float(price_acceptance_score),
        -100.0,
        100.0,
    )
    regime_context_score = _clamp(
        0.35 * network_security_score
        + 0.25 * l2_adoption_score
        + 0.25 * miner_pressure_score
        + 0.15 * network_health_score,
        -100.0,
        100.0,
    )

    exact_metric_ids = {str(item.get("metric_id")) for item in metric_items if item.get("metric_id")}
    proxy_flags: list[str] = []
    data_quality_flags: list[str] = []
    early_warning_flags: list[str] = []
    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    conflict_drivers: list[str] = []
    data_quality_penalty = 0.0
    if "active_addresses" in exact_metric_ids and "active_entities_or_addresses_z_60d" in exact_metric_ids:
        proxy_flags.append("raw_address_count_not_entity_adjusted")
        activity_quality_score *= 0.65
    if "transfer_volume_adjusted_usd" not in exact_metric_ids:
        data_quality_penalty += 12.0
        data_quality_flags.append("transfer_volume_adjusted_usd_missing")
    if "adoption_residual_z_90d" not in exact_metric_ids:
        data_quality_penalty += 8.0
        data_quality_flags.append("adoption_residual_fallback_or_missing")
    if any(item.get("is_stale") is True for item in metric_items if item.get("metric_id") in {"mempool_vsize", "mempool_min_fee_rate", "fee_pressure_z_60d"}):
        data_quality_penalty += 8.0
        data_quality_flags.append("fee_mempool_data_stale")

    module_score_points = _clamp(
        0.35 * fast_trend_score
        + 0.45 * core_confirmation_score
        + 0.20 * regime_context_score
        - data_quality_penalty,
        -100.0,
        100.0,
    )
    direction = "bullish" if module_score_points >= 25.0 else "bearish" if module_score_points <= -25.0 else "neutral"
    signal_stage = (
        "none"
        if abs(module_score_points) < 15
        else "early_warning"
        if abs(module_score_points) < 25
        else "fast_signal"
        if abs(module_score_points) < 40
        else "confirmed_signal"
    )

    conflict = fast_trend_score * core_confirmation_score < 0 and abs(fast_trend_score - core_confirmation_score) >= 45
    if conflict:
        signal_stage = "conflict"
        direction = "neutral" if abs(btc_response_score) < 70 else direction
        conflict_drivers.append("fast_trend_score_core_confirmation_score_conflict")

    state = "btc_adoption_neutral"
    implication = "neutral"
    if activity_spike_flag >= 1.0:
        state, direction, signal_stage, implication = "activity_spike_untrusted", "neutral", "early_warning", "non_economic_activity_warning"
        data_quality_penalty += 8.0
        early_warning_flags.append("activity_spike_without_settlement_confirmation")
    elif transfer_z >= 1.0 and nvt_change < 0 and btc_return_24h >= 0:
        state, implication = "settlement_demand_confirmed", "trend_confirmed"
        if signal_stage == "early_warning":
            signal_stage = "fast_signal"
        direction = "bullish"
    elif active_z >= 1.0 and tx_z >= 0.8 and transfer_z >= 0.5 and btc_return_24h >= 0:
        state, implication = "activity_expansion_confirmed", "trend_confirmed"
        direction = "bullish"
    elif transfer_change_7d < 0 and nvt_change > 0 and btc_return_24h <= 0:
        state, direction, implication = "settlement_demand_fading", "bearish", "internal_weakness"
    elif fee_pressure_z >= 1.5 and mempool_vsize_z >= 1.5 and transfer_z <= 0 and btc_return_24h <= 0:
        state, direction, implication = "mempool_congestion_risk", "neutral", "trend_fragile"
        early_warning_flags.append("mempool_congestion_without_settlement")
    elif fee_pressure_z >= 1.0 and transfer_z >= 0.5 and btc_return_24h >= 0:
        state, direction, implication = "healthy_fee_demand", "bullish", "network_activity_support"
    elif settlement_demand_score >= 20 and activity_quality_score >= 10 and btc_return_24h > 0 and residual_z >= 0:
        state, direction, implication = "btc_accepting_adoption_tailwind", "bullish", "trend_confirmed"
    elif (settlement_demand_score >= 20 or activity_quality_score >= 20) and btc_return_24h <= 0 and residual_z <= -1:
        state, direction, signal_stage, implication = "btc_rejecting_adoption_tailwind", "bearish", "confirmed_signal", "internal_weakness"
    elif (settlement_demand_score <= -20 or activity_quality_score <= -20) and btc_return_24h >= 0 and residual_z >= 1:
        state, direction, signal_stage, implication = "btc_resisting_adoption_headwind", "bullish", "confirmed_signal", "external_support"
    elif hashrate_change < -0.03 and hashprice_z <= -1 and miner_revenue_z <= -1:
        state, direction, implication = "miner_security_pressure", "neutral", "regime_headwind"
    elif l2_adoption_score >= 18:
        state, implication = "l2_adoption_supportive", "network_activity_support"
    elif network_security_score >= 18:
        state, implication = "network_security_supportive", "network_activity_support"

    if signal_stage == "confirmed_signal" and abs(core_confirmation_score) < 15:
        signal_stage = "fast_signal"

    if activity_quality_score > 15:
        support_drivers.append("activity_quality_expansion")
    if settlement_demand_score > 15:
        support_drivers.append("settlement_demand_improving")
    if fee_mempool_score > 15 and transfer_z > 0:
        support_drivers.append("healthy_fee_demand")
    if btc_response_score > 15:
        support_drivers.append("btc_accepting_adoption_tailwind")
    if l2_adoption_score > 15:
        support_drivers.append("l2_adoption_context_supportive")
    if activity_spike_flag >= 1:
        pressure_drivers.append("activity_spike_untrusted")
    if settlement_demand_score < -15:
        pressure_drivers.append("settlement_demand_fading")
    if congestion_flag >= 1:
        pressure_drivers.append("congestion_without_settlement")
    if btc_response_score < -15:
        pressure_drivers.append("btc_rejecting_adoption_tailwind")
    if miner_pressure_score < -15:
        pressure_drivers.append("miner_security_pressure")

    module_score = _clamp(module_score_points / 100.0, -0.80, 0.80)
    confidence_score = _clamp(
        72.0
        + min(abs(module_score_points), 45.0) * 0.18
        - data_quality_penalty
        - (10.0 if signal_stage in {"early_warning", "conflict"} else 0.0),
        25.0,
        95.0,
    )
    risk_score = _clamp(35.0 + max(0.0, -fast_trend_score) * 0.25 + max(0.0, -core_confirmation_score) * 0.25, 0.0, 100.0)
    invalidation_conditions = _btc_adoption_invalidation_conditions(state)
    summary = (
        f"btc_adoption.v2.3 state={state}; stage={signal_stage}; "
        f"fast={round(fast_trend_score, 1)}, core={round(core_confirmation_score, 1)}, "
        f"regime={round(regime_context_score, 1)}, residual_z={round(residual_z, 2)}."
    )
    structural_items = [
        item
        for item in metric_items
        if "structural" in set(item.get("horizon_tags") or [])
        or item.get("signal_type") == "context_signal"
    ]
    return {
        "semantic_profile_version": "p3.c54.btc_adoption.v2.3",
        "module_purpose": "btc_adoption_confirmation_rejection_for_btc_trend",
        "adoption_horizon_focus": "structural",
        "adoption_timeframe_focus": "fast_core_regime",
        "network_health_context_count": len(structural_items),
        "short_term_direction_weight": 0.35,
        "adoption_state": direction,
        "module_direction": direction,
        "module_score": round(module_score, 4),
        "module_effective_score": round(module_score, 4),
        "confidence_score": round(confidence_score, 2),
        "risk_score": round(risk_score, 2),
        "timeframe": {
            "fast_layer": "0h-24h",
            "core_layer": "1d-7d",
            "regime_layer": "14d-90d",
        },
        "signal_stage": signal_stage,
        "btc_adoption_state": state,
        "btc_implication": implication,
        "scores": {
            "fast_trend_score": round(fast_trend_score, 2),
            "core_confirmation_score": round(core_confirmation_score, 2),
            "regime_context_score": round(regime_context_score, 2),
            "activity_quality_score": round(activity_quality_score, 2),
            "settlement_demand_score": round(settlement_demand_score, 2),
            "fee_mempool_score": round(fee_mempool_score, 2),
            "network_security_score": round(network_security_score, 2),
            "l2_adoption_score": round(l2_adoption_score, 2),
            "btc_response_score": round(btc_response_score, 2),
            "data_quality_penalty": round(data_quality_penalty, 2),
        },
        "states": {
            "activity": {
                "state": "activity_spike_untrusted" if activity_spike_flag >= 1 else "activity_expanding" if activity_quality_score > 15 else "activity_neutral",
                "active_entities_or_addresses_z_60d": active_z,
                "transaction_count_z_60d": tx_z,
                "activity_spike_flag": activity_spike_flag,
            },
            "settlement": {
                "state": "settlement_demand_confirmed" if settlement_demand_score > 20 else "settlement_demand_fading" if settlement_demand_score < -20 else "settlement_neutral",
                "transfer_volume_adjusted_usd_z_60d": transfer_z,
                "nvt_proxy": nvt,
                "nvt_proxy_change_7d": nvt_change,
            },
            "fee_mempool": {
                "state": "mempool_congestion_risk" if congestion_flag >= 1 else "healthy_fee_demand" if fee_mempool_score > 15 and transfer_z > 0 else "fee_mempool_neutral",
                "fee_pressure_z_60d": fee_pressure_z,
                "mempool_vsize_z_30d": mempool_vsize_z,
            },
            "security": {
                "state": "miner_security_pressure" if miner_pressure >= 1 else "network_security_supportive" if network_security_score > 18 else "network_security_neutral",
                "hashrate_14d_ma_change_7d_pct": hashrate_change,
                "hashprice_z_90d": hashprice_z,
            },
            "lightning": {
                "state": "l2_adoption_supportive" if l2_adoption_score > 18 else "l2_adoption_neutral",
                "lightning_public_network_health_score": lightning_health,
                "lightning_capacity_change_30d_pct": lightning_capacity_change,
            },
            "btc_response_confirmation": {
                "state": "btc_rejecting_adoption_tailwind" if residual_z <= -1 else "btc_accepting_adoption_tailwind" if residual_z >= 1 else "btc_adoption_response_neutral",
                "expected_return_24h": expected_return,
                "residual_24h": residual,
                "residual_z_90d": residual_z,
                "btc_return_4h": btc_return_4h,
                "btc_return_24h": btc_return_24h,
                "btc_return_3d": btc_return_3d,
                "btc_return_7d": btc_return_7d,
            },
        },
        "support_drivers": sorted(set(support_drivers)),
        "pressure_drivers": sorted(set(pressure_drivers)),
        "conflict_drivers": sorted(set(conflict_drivers)),
        "early_warning_flags": sorted(set(early_warning_flags)),
        "data_quality_flags": sorted(set(data_quality_flags)),
        "proxy_flags": sorted(set(proxy_flags)),
        "invalidation_conditions": invalidation_conditions,
        "context_notes": [
            "Raw active addresses, transaction count, hashrate and Lightning levels are context only.",
            "Confirmed adoption signals require core chain demand and BTC response evidence.",
            "Fee pressure is supportive only when adjusted settlement demand and price response confirm it.",
        ],
        "summary": summary,
        "display_state": state,
        "display_summary": summary,
    }


def _btc_adoption_invalidation_conditions(state: str) -> list[str]:
    if state in {"settlement_demand_confirmed", "activity_expansion_confirmed", "healthy_fee_demand", "btc_accepting_adoption_tailwind"}:
        return [
            "Adjusted transfer volume z-score falls back below neutral",
            "NVT proxy starts rising over the 7d window",
            "adoption_residual_z_90d turns negative",
        ]
    if state in {"btc_rejecting_adoption_tailwind", "settlement_demand_fading", "mempool_congestion_risk"}:
        return [
            "BTC 24h return turns positive while adoption_residual_z_90d recovers above zero",
            "Adjusted transfer volume z-score improves above neutral",
            "Fee/mempool pressure cools without price weakness",
        ]
    if state == "activity_spike_untrusted":
        return [
            "Adjusted transfer volume confirms the transaction spike",
            "Fee pressure cools and activity remains elevated",
        ]
    if state == "miner_security_pressure":
        return [
            "Hashprice_z_90d recovers above -1",
            "Hashrate 14d moving average stops falling over 7d",
        ]
    return ["No active BTC adoption signal; invalidation requires a new fast/core state."]


def _asia_risk_v23_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    raw_pressure_count = sum(
        1
        for metric_id in ("usdcnh", "usdjpy", "jgb_10y")
        if (
            (item := _metric_by_id(metric_items, metric_id)) is not None
            and float(item.get("metric_score") or 0.0) < 0
        )
    )
    risk_off_pressure = _clamp(_metric_value(metric_items, "risk_off_pressure_score") or 0.0, 0.0, 100.0)
    if risk_off_pressure <= 0 and raw_pressure_count >= 2:
        risk_off_pressure = 65.0
    asia_session_trend = _clamp(_metric_value(metric_items, "asia_session_trend_score") or 0.0, -100.0, 100.0)
    regional_demand = _clamp(_metric_value(metric_items, "regional_demand_score") or 0.0, -100.0, 100.0)
    btc_response = _clamp(_metric_value(metric_items, "btc_response_score") or 0.0, -100.0, 100.0)
    jpy_carry = _clamp(_metric_value(metric_items, "jpy_carry_unwind_pressure") or 0.0, 0.0, 100.0)
    cnh_pressure = _clamp(_metric_value(metric_items, "cnh_devaluation_pressure") or 0.0, 0.0, 100.0)
    equity_pressure = _clamp(_metric_value(metric_items, "asia_equity_downside_pressure") or 0.0, 0.0, 100.0)
    return_4h_z = _metric_value(metric_items, "asia_session_btc_return_4h_z") or 0.0
    return_8h_z = _metric_value(metric_items, "asia_session_btc_return_8h_z") or 0.0
    vwap_z = _metric_value(metric_items, "asia_session_vwap_distance_z") or 0.0
    range_position = _metric_value(metric_items, "asia_session_range_position")
    if range_position is None:
        range_position = 0.5
    residual_z = _metric_value(metric_items, "asia_risk_residual_z_90d") or 0.0
    residual = _metric_value(metric_items, "asia_risk_residual_24h") or 0.0
    expected_return = _metric_value(metric_items, "asia_expected_btc_return_24h") or 0.0
    low_break = (_metric_value(metric_items, "asia_session_low_break_flag") or 0.0) >= 1.0
    high_break = (_metric_value(metric_items, "asia_session_high_break_flag") or 0.0) >= 1.0
    btc_4h = _metric_value(metric_items, "asia_session_btc_return_4h") or 0.0
    btc_8h = _metric_value(metric_items, "asia_session_btc_return_8h") or 0.0
    btc_24h = _metric_value(metric_items, "asia_session_btc_return_24h") or _metric_value_any(
        metric_items, ("btc_return_24h", "btc_24h_return_pct")
    ) or 0.0
    premium_state_value = _metric_value(metric_items, "korea_premium_state")
    premium_state = _asia_korea_premium_state(premium_state_value)
    korea_premium_z = _metric_value(metric_items, "korea_premium_z_90d") or 0.0
    hk_flow_1d_z = _metric_value(metric_items, "hk_btc_etf_flow_1d_z") or 0.0
    hk_flow_5d_z = _metric_value(metric_items, "hk_btc_etf_flow_5d_z") or 0.0
    volume_z = _metric_value(metric_items, "asia_session_btc_volume_z_30d") or 0.0
    realized_vol_z = _metric_value(metric_items, "asia_session_btc_realized_vol_z_30d") or 0.0
    downside_vol_z = _metric_value(metric_items, "asia_session_downside_vol_z_30d") or 0.0
    usdjpy_return_24h = _metric_value(metric_items, "usdjpy_return_24h") or 0.0
    usdcnh_return_24h = _metric_value(metric_items, "usdcnh_return_24h") or 0.0

    exact_metric_ids = {str(item.get("metric_id")) for item in metric_items if item.get("metric_id")}
    data_quality_flags: list[str] = []
    proxy_flags: list[str] = []
    early_warning_flags: list[str] = []
    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    conflict_drivers: list[str] = []
    data_quality_penalty = 0.0
    if "asia_risk_residual_z_90d" not in exact_metric_ids or "btc_response_score" not in exact_metric_ids:
        data_quality_penalty += 18.0
        data_quality_flags.append("btc_response_unavailable")
    if "korea_premium_index" not in exact_metric_ids:
        proxy_flags.append("korea_premium_missing_or_proxy")
    if "hk_btc_etf_flow_5d_z" not in exact_metric_ids:
        data_quality_penalty += 5.0
        proxy_flags.append("hk_etf_flow_missing")
    if any(
        item.get("is_stale") is True
        for item in metric_items
        if item.get("metric_id") in {"usdjpy", "usdcnh", "usdjpy_return_4h", "usdcnh_return_4h"}
    ):
        data_quality_penalty += 10.0
        data_quality_flags.append("asia_fx_fast_data_stale")

    unconfirmed_risk_penalty = risk_off_pressure if btc_response > -30 and return_8h_z > -0.8 and not low_break else 0.0
    module_score_points = _clamp(
        0.55 * btc_response
        + 0.25 * asia_session_trend
        + 0.15 * regional_demand
        - 0.05 * unconfirmed_risk_penalty
        - data_quality_penalty,
        -100.0,
        100.0,
    )
    direction = "bullish" if module_score_points >= 25 else "bearish" if module_score_points <= -25 else "neutral"
    signal_stage = (
        "none"
        if abs(module_score_points) < 15
        else "early_warning"
        if abs(module_score_points) < 25
        else "fast_signal"
        if abs(module_score_points) < 45
        else "confirmed_signal"
    )
    state = "asia_risk_neutral"
    implication = "neutral"

    if "btc_response_unavailable" in data_quality_flags:
        direction, signal_stage, state, implication = "neutral", "none", "asia_risk_neutral", "neutral"
    elif jpy_carry >= 70 and return_8h_z <= -0.8 and residual_z <= -1.0 and low_break:
        state, direction, signal_stage, implication = "jpy_carry_unwind_confirmed", "bearish", "confirmed_signal", "risk_off_confirmed"
        pressure_drivers.append("jpy_carry_unwind_confirmed")
    elif risk_off_pressure >= 70 and return_8h_z <= -0.8 and residual_z <= -1.0 and low_break:
        state, direction, signal_stage, implication = "asia_risk_off_confirmed", "bearish", "confirmed_signal", "risk_off_confirmed"
        pressure_drivers.append("asia_risk_off_confirmed")
    elif risk_off_pressure >= 60 and return_8h_z >= 0 and residual_z >= 1.0 and float(range_position) >= 0.6:
        state, direction, signal_stage, implication = "btc_resisting_asia_risk", "bullish", "conflict", "internal_strength"
        support_drivers.append("btc_resisting_asia_risk")
        conflict_drivers.append("asia_risk_pressure_rejected_by_btc")
    elif regional_demand >= 40 and risk_off_pressure <= 40 and return_8h_z <= -0.5 and residual_z <= -1.0:
        state, direction, signal_stage, implication = "btc_rejecting_asia_tailwind", "bearish", "fast_signal", "internal_weakness"
        pressure_drivers.append("btc_rejecting_asia_tailwind")
    elif premium_state == "healthy_premium" and hk_flow_5d_z >= 0 and return_8h_z >= 0.5 and volume_z >= 0.5:
        state, direction, signal_stage, implication = "asia_crypto_demand_support", "bullish", "fast_signal", "regional_demand_support"
        support_drivers.append("asia_crypto_demand_support")
    elif premium_state in {"fomo_premium", "stress_premium"} and realized_vol_z >= 1.5:
        state, direction, signal_stage, implication = "kimchi_premium_stress", "neutral", "early_warning", "trend_fragile"
        early_warning_flags.append("kimchi_premium_extreme_with_volatility")
    elif jpy_carry >= 60 and btc_response > -30:
        state, direction, signal_stage, implication = "jpy_carry_unwind_warning", "neutral", "early_warning", "trend_fragile"
        early_warning_flags.append("jpy_carry_unwind_unconfirmed")
    elif cnh_pressure >= 55:
        state, direction, signal_stage, implication = "cnh_pressure_warning", "neutral", "early_warning", "trend_fragile"
        early_warning_flags.append("cnh_devaluation_pressure_unconfirmed")

    if signal_stage == "confirmed_signal" and "btc_response_unavailable" in data_quality_flags:
        signal_stage = "none"
        direction = "neutral"
    if risk_off_pressure >= 50:
        pressure_drivers.append("risk_off_pressure_elevated")
    if jpy_carry >= 50:
        pressure_drivers.append("jpy_carry_unwind_pressure")
    if cnh_pressure >= 45:
        pressure_drivers.append("cnh_pressure")
    if equity_pressure >= 45:
        pressure_drivers.append("asia_equity_downside_pressure")
    if regional_demand >= 25:
        support_drivers.append("regional_demand_support")
    if btc_response >= 25:
        support_drivers.append("btc_response_positive")
    if btc_response <= -25:
        pressure_drivers.append("btc_response_negative")

    confidence_score = _clamp(
        72.0
        + min(abs(module_score_points), 45.0) * 0.15
        - data_quality_penalty
        - (10.0 if signal_stage in {"early_warning", "conflict"} else 0.0),
        25.0,
        95.0,
    )
    risk_score = _clamp(risk_off_pressure + max(0.0, -btc_response) * 0.2, 0.0, 100.0)
    module_score = _clamp(module_score_points / 100.0, -0.8, 0.8)
    invalidation_conditions = _asia_risk_invalidation_conditions(state)
    summary = (
        f"asia_risk.v2.3 state={state}; stage={signal_stage}; "
        f"risk={round(risk_off_pressure, 1)}, session={round(asia_session_trend, 1)}, "
        f"demand={round(regional_demand, 1)}, response={round(btc_response, 1)}, residual_z={round(residual_z, 2)}."
    )
    return {
        "semantic_profile_version": "p3.c56.asia_risk.v2.3",
        "module_purpose": "asia_session_risk_and_btc_response_confirmation_rejection",
        "asia_risk_composite": "risk_off" if risk_off_pressure >= 60 or raw_pressure_count >= 2 else "mixed_or_quiet",
        "asia_pressure_count": max(
            raw_pressure_count,
            int(jpy_carry >= 50) + int(cnh_pressure >= 45) + int(equity_pressure >= 45),
        ),
        "asia_risk_score": round(risk_score, 2),
        "module_direction": direction,
        "module_score": round(module_score, 4),
        "module_effective_score": round(module_score, 4),
        "module_score_signed": round(module_score_points, 2),
        "confidence_score": round(confidence_score, 2),
        "risk_score": round(risk_score, 2),
        "signal_stage": signal_stage,
        "asia_risk_state": state,
        "btc_implication": implication,
        "scores": {
            "risk_off_pressure_score": round(risk_off_pressure, 2),
            "asia_session_trend_score": round(asia_session_trend, 2),
            "regional_demand_score": round(regional_demand, 2),
            "btc_response_score": round(btc_response, 2),
            "jpy_carry_unwind_pressure": round(jpy_carry, 2),
            "cnh_devaluation_pressure": round(cnh_pressure, 2),
            "asia_equity_downside_pressure": round(equity_pressure, 2),
            "data_quality_penalty": round(data_quality_penalty, 2),
        },
        "btc_response": {
            "asia_session_btc_return_4h_z": round(return_4h_z, 4),
            "asia_session_btc_return_8h_z": round(return_8h_z, 4),
            "asia_session_vwap_distance_z": round(vwap_z, 4),
            "asia_session_range_position": round(float(range_position), 4),
            "asia_risk_residual_z_90d": round(residual_z, 4),
            "residual_24h": residual,
            "expected_return_24h": expected_return,
            "low_break_flag": low_break,
            "high_break_flag": high_break,
        },
        "states": {
            "jpy_carry": {
                "state": "carry_unwind_pressure" if jpy_carry >= 60 else "carry_neutral",
                "jpy_carry_unwind_pressure": jpy_carry,
                "usdjpy_return_24h": usdjpy_return_24h,
            },
            "cnh_pressure": {
                "state": "cnh_pressure_warning" if cnh_pressure >= 55 else "cnh_neutral",
                "cnh_devaluation_pressure": cnh_pressure,
                "usdcnh_return_24h": usdcnh_return_24h,
            },
            "asia_equities": {
                "state": "asia_equity_drag" if equity_pressure >= 45 else "asia_equity_neutral",
                "asia_equity_downside_pressure": equity_pressure,
            },
            "korea_premium": {
                "state": premium_state,
                "korea_premium_z_90d": korea_premium_z,
            },
            "hk_etf_flow": {
                "state": "hk_etf_support" if hk_flow_5d_z > 0 else "hk_etf_drag" if hk_flow_5d_z < 0 else "hk_etf_neutral_or_missing",
                "hk_btc_etf_flow_1d_z": hk_flow_1d_z,
                "hk_btc_etf_flow_5d_z": hk_flow_5d_z,
            },
            "btc_response_confirmation": {
                "state": "btc_resisting_asia_risk" if residual_z >= 1 else "btc_confirming_asia_risk" if residual_z <= -1 else "btc_asia_response_neutral",
                "btc_return_4h": btc_4h,
                "btc_return_8h": btc_8h,
                "btc_return_24h": btc_24h,
                "asia_risk_residual_z_90d": residual_z,
            },
        },
        "support_drivers": sorted(set(support_drivers)),
        "pressure_drivers": sorted(set(pressure_drivers)),
        "conflict_drivers": sorted(set(conflict_drivers)),
        "early_warning_flags": sorted(set(early_warning_flags)),
        "data_quality_flags": sorted(set(data_quality_flags)),
        "proxy_flags": sorted(set(proxy_flags)),
        "invalidation_conditions": invalidation_conditions,
        "summary": summary,
        "context_notes": [
            "USDJPY, USDCNH and Asia equity levels are context only.",
            "Risk-off pressure is not bearish until BTC Asia session response confirms it.",
            "Korea premium is split into healthy demand, FOMO/stress and fading/dislocation states.",
        ],
        "display_state": state,
        "display_summary": summary,
    }


def _asia_korea_premium_state(value: float | None) -> str:
    if value is None:
        return "missing"
    if value <= -1.5:
        return "collapsing_premium"
    if value < 0:
        return "stress_premium"
    if value >= 2:
        return "fomo_premium"
    if value >= 1:
        return "healthy_premium"
    if value <= -0.5:
        return "discount"
    return "neutral"


def _asia_risk_invalidation_conditions(state: str) -> list[str]:
    if state in {"jpy_carry_unwind_confirmed", "asia_risk_off_confirmed"}:
        return [
            "Asia session BTC reclaims VWAP/range midpoint",
            "asia_risk_residual_z_90d recovers above zero",
            "JPY/CNH pressure cools below warning threshold",
        ]
    if state == "btc_resisting_asia_risk":
        return [
            "BTC loses Asia session range midpoint",
            "asia_risk_residual_z_90d falls below zero",
            "Risk-off pressure remains elevated and BTC low-break confirms",
        ]
    if state == "btc_rejecting_asia_tailwind":
        return [
            "Asia session BTC return turns positive",
            "regional_demand_score falls below support threshold",
            "asia_risk_residual_z_90d recovers above zero",
        ]
    if state == "asia_crypto_demand_support":
        return [
            "Korea premium leaves healthy range or flips into stress",
            "HK ETF flow z-score turns negative",
            "BTC Asia session return loses confirmation",
        ]
    if state in {"jpy_carry_unwind_warning", "cnh_pressure_warning", "kimchi_premium_stress"}:
        return [
            "Warning pressure cools below threshold",
            "BTC response confirms the opposite direction",
        ]
    return ["No active Asia risk signal; invalidation requires a new BTC response state."]


def _treasury_credit_v21_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    treasury_2y = _metric_value(metric_items, "treasury_2y")
    treasury_10y = _metric_value(metric_items, "treasury_10y")
    treasury_30y = _metric_value(metric_items, "treasury_30y")
    real_yield = _metric_value(metric_items, "real_yield_10y")
    breakeven = _metric_value(metric_items, "breakeven_10y")
    hy_oas = _metric_value(metric_items, "hy_spread")
    ig_oas = _metric_value(metric_items, "ig_oas")

    change_2y_1d = _metric_value(metric_items, "treasury_2y_change_1d_bps") or 0.0
    change_2y_3d = _metric_value(metric_items, "treasury_2y_change_3d_bps") or 0.0
    z_2y = _metric_value(metric_items, "treasury_2y_z_60d") or 0.0
    change_10y_1d = _metric_value(metric_items, "treasury_10y_change_1d_bps") or 0.0
    change_10y_3d = _metric_value(metric_items, "treasury_10y_change_3d_bps") or 0.0
    z_10y = _metric_value(metric_items, "treasury_10y_z_60d") or 0.0
    change_30y_3d = _metric_value(metric_items, "treasury_30y_change_3d_bps") or 0.0
    real_change_1d = _metric_value(metric_items, "real_yield_10y_change_1d_bps") or 0.0
    real_change_3d = _metric_value(metric_items, "real_yield_10y_change_3d_bps") or 0.0
    real_z = _metric_value(metric_items, "real_yield_10y_z_60d") or 0.0
    breakeven_change_1d = _metric_value(metric_items, "breakeven_10y_change_1d_bps") or 0.0
    breakeven_change_3d = _metric_value(metric_items, "breakeven_10y_change_3d_bps") or 0.0
    curve_2s10s = _metric_value(metric_items, "yield_curve_2s10s_bps")
    curve_change_1d = _metric_value(metric_items, "curve_2s10s_change_1d_bps") or 0.0
    curve_change_5d = _metric_value(metric_items, "curve_2s10s_change_5d_bps") or 0.0
    curve_10s30s = _metric_value(metric_items, "yield_curve_10s30s_bps")
    hy_change_1d = _metric_value(metric_items, "hy_oas_change_1d_bps") or 0.0
    hy_change_5d = _metric_value(metric_items, "hy_oas_change_5d_bps") or 0.0
    hy_z = _metric_value(metric_items, "hy_oas_z_60d") or 0.0
    hy_percentile = _metric_value(metric_items, "hy_oas_percentile_252d")

    btc_return_24h = _metric_value_any(
        metric_items,
        ("btc_return_24h", "btc_return_24h_pct", "btc_24h_return_pct"),
    ) or 0.0
    btc_return_4h = _metric_value_any(metric_items, ("btc_return_4h", "btc_return_4h_pct")) or 0.0
    btc_residual = _metric_value(metric_items, "btc_residual_24h")
    if btc_residual is None:
        expected = _metric_value(metric_items, "btc_expected_return_24h") or 0.0
        btc_residual = btc_return_24h - expected
    btc_residual_z = _metric_value(metric_items, "btc_residual_z_60d") or 0.0
    btc_vs_rates = _metric_value(metric_items, "btc_vs_rates_residual_24h")
    if btc_vs_rates is None:
        btc_vs_rates = btc_return_24h + 0.00025 * real_change_1d
    btc_vs_credit = _metric_value(metric_items, "btc_vs_credit_residual_3d")

    vix_change = _metric_value(metric_items, "vix_change_1d_pct") or 0.0
    nasdaq_return = _metric_value(metric_items, "nasdaq_return_24h_pct") or 0.0

    if change_2y_1d >= 12 or z_2y >= 1.6:
        policy_state, policy_score, policy_risk = "policy_rate_shock", -0.85, 82.0
    elif change_2y_1d >= 8 or change_2y_3d >= 15:
        policy_state, policy_score, policy_risk = "policy_tightening_headwind", -0.55, 62.0
    elif change_2y_1d <= -6:
        policy_state, policy_score, policy_risk = "policy_easing_tailwind", 0.45, 28.0
    else:
        policy_state, policy_score, policy_risk = "policy_neutral", 0.0, 35.0

    if real_change_1d >= 12 or real_z >= 1.6:
        real_state, real_score, real_risk = "real_yield_shock", -0.9, 85.0
    elif real_change_1d >= 7 or real_change_3d >= 12:
        real_state, real_score, real_risk = "real_yield_headwind", -0.62, 66.0
    elif real_change_1d <= -5:
        real_state, real_score, real_risk = "real_yield_tailwind", 0.50, 25.0
    else:
        real_state, real_score, real_risk = "real_yield_neutral", 0.0, 35.0

    duration_pressure = max(change_10y_1d, change_10y_3d / 2.0, change_30y_3d / 2.0)
    duration_tailwind = min(change_10y_1d, change_10y_3d / 2.0)
    if duration_pressure >= 14 or z_10y >= 1.6:
        duration_state, duration_score, duration_risk = "term_premium_shock", -0.75, 76.0
    elif duration_pressure >= 8:
        duration_state, duration_score, duration_risk = "duration_headwind", -0.42, 55.0
    elif duration_tailwind <= -8:
        duration_state, duration_score, duration_risk = "duration_tailwind", 0.28, 30.0
    else:
        duration_state, duration_score, duration_risk = "duration_neutral", 0.0, 35.0

    if curve_change_1d > 5 and change_10y_1d > 0 and change_2y_1d <= 3:
        curve_state, curve_score = "bear_steepening_risk", -0.25
    elif curve_change_1d < -5 and change_2y_1d > 0:
        curve_state, curve_score = "bear_flattening_policy_pressure", -0.22
    elif curve_change_1d > 5 and change_2y_1d < 0:
        curve_state, curve_score = "bull_steepening_tailwind", 0.20
    elif change_10y_1d <= -8 and change_2y_1d <= -6 and hy_change_5d >= 15:
        curve_state, curve_score = "bull_flattening_growth_scare", -0.35
    else:
        curve_state, curve_score = "curve_neutral", 0.0

    if change_10y_1d > 0 and breakeven_change_1d > 0 and real_change_1d <= 3:
        inflation_state, inflation_score = "reflation_supportive", 0.28
    elif change_10y_1d > 0 and real_change_1d > breakeven_change_1d + 2:
        inflation_state, inflation_score = "real_rate_tightening", -0.35
    elif breakeven_change_1d >= 6 and real_change_1d > 0:
        inflation_state, inflation_score = "inflation_risk_premium", -0.18
    else:
        inflation_state, inflation_score = "inflation_neutral", 0.0

    if hy_change_5d >= 25 or hy_z >= 2.0:
        credit_state, credit_score, credit_risk = "credit_stress", -0.90, 88.0
    elif hy_change_1d >= 6 or hy_change_5d >= 15 or hy_z >= 1.2:
        credit_state, credit_score, credit_risk = "credit_widening_warning", -0.55, 72.0
    elif hy_change_5d <= -10:
        credit_state, credit_score, credit_risk = "credit_risk_on", 0.35, 28.0
    else:
        credit_state, credit_score, credit_risk = "credit_neutral", 0.0, 35.0

    external_score = _clamp(
        0.15 * policy_score
        + 0.20 * real_score
        + 0.12 * duration_score
        + 0.10 * curve_score
        + 0.08 * inflation_score
        + 0.20 * credit_score,
        -1.0,
        1.0,
    )
    headwind_signal = any(
        score_value < -0.10
        for score_value in (policy_score, real_score, duration_score, credit_score)
    )
    headwind_signal = headwind_signal or any(
        value > 0
        for value in (change_2y_1d, real_change_1d, max(change_10y_1d - breakeven_change_1d, 0.0), hy_change_5d)
    )
    tailwind_signal = any(
        score_value > 0.10
        for score_value in (policy_score, real_score, duration_score, credit_score, inflation_score)
    )
    tailwind_signal = tailwind_signal or any(
        value < 0
        for value in (change_2y_1d, real_change_1d, max(change_10y_1d - breakeven_change_1d, 0.0), hy_change_5d)
    )
    if (external_score > 0.12 or tailwind_signal) and btc_return_24h > 0 and btc_residual >= 0:
        btc_response_state, btc_response_score = "btc_following_tailwind", 0.45
    elif (external_score > 0.12 or tailwind_signal) and (btc_return_24h <= 0 or btc_residual < 0):
        btc_response_state, btc_response_score = "btc_rejecting_tailwind", -0.45
    elif (external_score < -0.12 or headwind_signal) and btc_return_24h < 0 and btc_residual < 0:
        btc_response_state, btc_response_score = "btc_following_headwind", -0.45
    elif (external_score < -0.12 or headwind_signal) and btc_return_24h >= 0 and btc_residual > 0:
        btc_response_state, btc_response_score = "btc_resisting_headwind", 0.38
    else:
        btc_response_state, btc_response_score = "btc_credit_neutral", 0.0

    raw_score = external_score + 0.15 * btc_response_score
    score = round(_clamp(raw_score, -0.60, 0.45), 4)

    early_warning_flags: list[str] = []
    if policy_state in {"policy_tightening_headwind", "policy_rate_shock"} or real_state in {"real_yield_headwind", "real_yield_shock"}:
        early_warning_flags.append("rates_headwind")
    if credit_state == "credit_widening_warning":
        early_warning_flags.append("credit_widening_warning")

    if hy_change_5d >= 25 or (hy_z >= 2.0 and btc_return_24h < 0 and (vix_change > 0 or nasdaq_return < 0)):
        state, direction = "credit_stress_confirmed", "bearish"
        score = round(_clamp(score, -0.60, -0.35), 4)
        risk_score = max(credit_risk, 82.0)
        btc_implication = "credit_risk_off"
        confidence_adjustment = -0.12
    elif (change_10y_1d <= -8 and change_2y_1d <= -6 and hy_change_5d >= 15 and btc_return_24h < 0):
        state, direction = "curve_growth_scare", "bearish"
        score = round(_clamp(score, -0.42, -0.20), 4)
        risk_score = max(credit_risk, 68.0)
        btc_implication = "risk_off_not_rates_tailwind"
        confidence_adjustment = -0.08
    elif (change_2y_1d >= 10 or real_change_1d >= 10) and btc_return_24h < 0 and btc_residual < 0:
        state, direction = "rates_headwind_confirmed", "bearish"
        score = round(_clamp(score, -0.45, -0.25), 4)
        risk_score = max(policy_risk, real_risk, 68.0)
        btc_implication = "macro_rates_headwind"
        confidence_adjustment = -0.08
    elif (hy_change_1d >= 6 or hy_change_5d >= 15 or hy_z >= 1.2):
        state, direction = "credit_widening_warning", "neutral"
        score = round(_clamp(score, -0.20, -0.08), 4)
        risk_score = max(credit_risk, 65.0)
        btc_implication = "trend_fragile"
        confidence_adjustment = -0.06
    elif (change_2y_1d >= 8 or real_change_1d >= 7):
        state, direction = "rates_headwind_warning", "neutral"
        score = round(_clamp(score, -0.18, -0.05), 4)
        risk_score = max(policy_risk, real_risk, 58.0)
        btc_implication = "trend_fragile"
        confidence_adjustment = -0.04
    elif (change_2y_1d > 0 or real_change_1d > 0) and hy_change_5d <= 8 and btc_return_24h >= 0 and btc_residual > 0:
        state, direction = "btc_resisting_rates_headwind", "neutral"
        score = round(_clamp(score, 0.05, 0.18), 4)
        risk_score = max(policy_risk, real_risk, 48.0)
        btc_implication = "internal_strength"
        confidence_adjustment = 0.02
    elif change_2y_1d < 0 and real_change_1d < 0 and hy_change_5d <= 0 and (btc_return_24h <= 0 or btc_residual < 0):
        state, direction = "btc_rejecting_rates_tailwind", "bearish"
        score = round(_clamp(score, -0.32, -0.15), 4)
        risk_score = max(35.0, min(policy_risk, real_risk, credit_risk))
        btc_implication = "internal_weakness"
        confidence_adjustment = -0.04
    elif change_10y_1d > 0 and breakeven_change_1d > 0 and real_change_1d <= 3 and hy_change_5d <= 0 and btc_return_24h > 0:
        state, direction = "reflation_supportive", "bullish"
        score = round(_clamp(score, 0.12, 0.28), 4)
        risk_score = max(28.0, min(duration_risk, credit_risk))
        btc_implication = "reflation_support"
        confidence_adjustment = 0.04
    elif change_2y_1d <= -6 and real_change_1d <= -5 and hy_change_5d <= 5 and btc_return_24h > 0 and btc_residual >= 0:
        state, direction = "rates_tailwind_confirmed", "bullish"
        score = round(_clamp(score, 0.20, 0.38), 4)
        risk_score = max(25.0, min(policy_risk, real_risk, credit_risk))
        btc_implication = "trend_confirmed"
        confidence_adjustment = 0.06
    elif abs(score) >= 0.08:
        state, direction = "treasury_credit_mixed", _direction_from_score(score)
        risk_score = max(policy_risk, real_risk, duration_risk, credit_risk, 45.0)
        btc_implication = "trend_fragile" if risk_score >= 60 else "neutral"
        confidence_adjustment = -0.02 if risk_score >= 60 else 0.0
    else:
        state, direction = "treasury_credit_neutral", "neutral"
        risk_score = max(policy_risk, real_risk, duration_risk, credit_risk, 35.0)
        btc_implication = "neutral"
        confidence_adjustment = 0.0

    data_quality_flags: list[str] = []
    if hy_percentile is None:
        data_quality_flags.append("insufficient_hy_oas_history")
    stale_metrics = [
        item.get("metric_id")
        for item in metric_items
        if item.get("is_stale") is True
        and item.get("metric_id") in {"treasury_2y", "treasury_10y", "real_yield_10y", "hy_spread"}
    ]
    if stale_metrics:
        data_quality_flags.append("rates_or_credit_data_stale")
        confidence_adjustment -= 0.10

    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    risk_drivers: list[str] = []
    if policy_score > 0.2 or real_score > 0.2:
        support_drivers.append("rates_tailwind")
    if inflation_state == "reflation_supportive":
        support_drivers.append("reflation_supportive")
    if credit_score > 0.2:
        support_drivers.append("credit_spreads_tightening")
    if btc_response_score > 0.2:
        support_drivers.append("btc_resisting_or_following_rates")
    if policy_score < -0.25 or real_score < -0.25:
        pressure_drivers.append("rates_real_yield_pressure")
    if duration_score < -0.25:
        pressure_drivers.append("duration_pressure")
    if credit_score < -0.25:
        pressure_drivers.append("credit_spread_widening")
    if btc_response_score < -0.2:
        pressure_drivers.append("btc_rejecting_or_following_rates")
    if policy_risk >= 60:
        risk_drivers.append(policy_state)
    if real_risk >= 60:
        risk_drivers.append(real_state)
    if credit_risk >= 60:
        risk_drivers.append(credit_state)

    summary = (
        f"treasury_credit.v2.1 state={state}; policy={policy_state}, "
        f"real_yield={real_state}, credit={credit_state}, BTC response={btc_response_state}."
    )
    return {
        "semantic_profile_version": "p3.c47.treasury_credit.v2.1",
        "module_purpose": "btc_trend_confirmation_by_rates_curve_and_credit_stress",
        "timeframe": {
            "fast_nowcast": "4h-24h",
            "confirmation": "1d-5d",
            "regime": "20d-60d",
        },
        "states": {
            "policy_rate_pressure": {
                "state": policy_state,
                "score": round(policy_score, 4),
                "risk_score": policy_risk,
                "basis": {
                    "treasury_2y": treasury_2y,
                    "treasury_2y_change_1d_bps": change_2y_1d,
                    "treasury_2y_change_3d_bps": change_2y_3d,
                    "treasury_2y_z_60d": z_2y,
                },
            },
            "real_yield_pressure": {
                "state": real_state,
                "score": round(real_score, 4),
                "risk_score": real_risk,
                "basis": {
                    "real_yield_10y": real_yield,
                    "real_yield_10y_change_1d_bps": real_change_1d,
                    "real_yield_10y_change_3d_bps": real_change_3d,
                    "real_yield_10y_z_60d": real_z,
                },
            },
            "duration_term_pressure": {
                "state": duration_state,
                "score": round(duration_score, 4),
                "risk_score": duration_risk,
                "basis": {
                    "treasury_10y": treasury_10y,
                    "treasury_30y": treasury_30y,
                    "treasury_10y_change_1d_bps": change_10y_1d,
                    "treasury_10y_change_3d_bps": change_10y_3d,
                    "treasury_30y_change_3d_bps": change_30y_3d,
                    "term_premium_affects_signal": False,
                },
            },
            "curve_regime": {
                "state": curve_state,
                "score": round(curve_score, 4),
                "basis": {
                    "yield_curve_2s10s_bps": curve_2s10s,
                    "curve_2s10s_change_1d_bps": curve_change_1d,
                    "curve_2s10s_change_5d_bps": curve_change_5d,
                    "yield_curve_10s30s_bps": curve_10s30s,
                },
            },
            "inflation_mix": {
                "state": inflation_state,
                "score": round(inflation_score, 4),
                "basis": {
                    "breakeven_10y": breakeven,
                    "breakeven_10y_change_1d_bps": breakeven_change_1d,
                    "breakeven_10y_change_3d_bps": breakeven_change_3d,
                    "real_yield_10y_change_1d_bps": real_change_1d,
                },
            },
            "credit_stress": {
                "state": credit_state,
                "score": round(credit_score, 4),
                "risk_score": credit_risk,
                "basis": {
                    "hy_oas": hy_oas,
                    "ig_oas": ig_oas,
                    "hy_oas_change_1d_bps": hy_change_1d,
                    "hy_oas_change_5d_bps": hy_change_5d,
                    "hy_oas_z_60d": hy_z,
                    "hy_oas_percentile_252d": hy_percentile,
                },
            },
            "btc_response_confirmation": {
                "state": btc_response_state,
                "score": round(btc_response_score, 4),
                "basis": {
                    "btc_return_4h": btc_return_4h,
                    "btc_return_24h": btc_return_24h,
                    "btc_residual_24h": btc_residual,
                    "btc_residual_z_60d": btc_residual_z,
                    "btc_vs_rates_residual_24h": btc_vs_rates,
                    "btc_vs_credit_residual_3d": btc_vs_credit,
                },
            },
        },
        "treasury_credit_state": state,
        "module_direction": direction,
        "module_score": score,
        "module_effective_score": score,
        "risk_score": round(risk_score, 2),
        "confidence_adjustment": round(confidence_adjustment, 4),
        "btc_implication": btc_implication,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "risk_drivers": risk_drivers,
        "early_warning_flags": early_warning_flags,
        "data_quality_flags": data_quality_flags,
        "context_notes": [
            "treasury_credit.v2.1 confirms or refutes BTC trend through rates, real yield, curve and credit stress.",
            "2Y, 10Y, real yield and HY OAS levels are composite inputs, not standalone BTC direction calls.",
        ],
        "summary": summary,
        "display_state": state,
        "display_summary": summary,
    }


EVENT_POLICY_PRIORITY = {
    "fomc": 1,
    "cpi": 2,
    "nfp": 3,
    "pce": 4,
    "fed_speech": 5,
    "blackout": 6,
}


def _event_policy_v21_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    event_rows: list[dict[str, Any]] = []
    for event_type in ("cpi", "fomc", "pce", "nfp"):
        hours = _metric_value(metric_items, f"{event_type}_hours_until")
        days = _metric_value(metric_items, f"{event_type}_days_until")
        signed_days = _metric_value(metric_items, f"{event_type}_signed_days")
        if hours is None and days is not None:
            hours = max(days, 0.0) * 24.0
        row = _classify_macro_event_window(
            event_type=event_type,
            hours_until=hours,
            signed_days=signed_days,
            macro_surprise=_event_policy_surprise(metric_items),
        )
        if row:
            event_rows.append(row)

    speech_hours = _metric_value(metric_items, "next_fed_speech_hours_until")
    speech_scheduled = _metric_value(metric_items, "fed_speech_scheduled_risk") or 0.0
    speech_content = _metric_value(metric_items, "fed_speech_risk") or 0.0
    speech_row = _classify_fed_speech_window(
        hours_until=speech_hours,
        scheduled_risk=max(speech_scheduled, speech_content),
    )
    if speech_row:
        event_rows.append(speech_row)

    blackout_active = (_metric_value(metric_items, "fomc_blackout_active") or 0.0) >= 0.5
    fomc_hours = _metric_value(metric_items, "fomc_hours_until")
    fomc_days = _metric_value(metric_items, "fomc_days_until")
    if fomc_hours is None and fomc_days is not None:
        fomc_hours = max(fomc_days, 0.0) * 24.0
    if blackout_active:
        blackout_risk = 10.0
        blackout_phase = "neutral"
        blackout_lock = "none"
        if fomc_hours is not None and fomc_hours <= 12:
            blackout_risk = 90.0
            blackout_phase = "hard_lock"
            blackout_lock = "hard"
        elif fomc_hours is not None and fomc_hours <= 48:
            blackout_risk = 72.0
            blackout_phase = "caution"
            blackout_lock = "soft"
        event_rows.append(
            {
                "event_type": "blackout",
                "hours_until": fomc_hours,
                "phase": blackout_phase,
                "lock_level": blackout_lock,
                "risk_score": blackout_risk,
                "reason_code": "BLACKOUT_CONTEXT"
                if blackout_lock == "none"
                else "BLACKOUT_WITH_FOMC_WINDOW",
                "note": "FOMC blackout is a policy visibility context; it is not a standalone direction signal.",
            }
        )

    active_rows = [row for row in event_rows if float(row.get("risk_score") or 0.0) > 0]
    dominant = _dominant_event_row(active_rows)
    nearest = _nearest_event_row(active_rows)
    phase = str((dominant or {}).get("phase") or "neutral")
    risk_score = round(float((dominant or {}).get("risk_score") or 0.0), 2)
    lock_level = str((dominant or {}).get("lock_level") or "none")
    trade_gate = _event_trade_gate(phase, risk_score, dominant)
    confidence_adjustment = _event_confidence_adjustment(phase, risk_score)
    summary = _event_policy_summary(dominant, nearest, phase, trade_gate)
    context_notes = [
        "Event policy is an event-timing gate, not directional alpha.",
        "Blackout active alone is treated as a context amplifier, not an independent hard gate.",
    ]
    if not active_rows:
        context_notes.append("No major macro event window is currently active.")
    return {
        "module": "event_policy",
        "semantic_profile_version": "p3.c43.event_policy.v2.1",
        "version": "p3.c43.event_policy.v2.1",
        "module_purpose": "event_risk_and_trade_permission",
        "module_direction": "neutral",
        "module_score": 0.0,
        "module_effective_score": 0.0,
        "affects_direction": False,
        "dominant_event_type": (dominant or {}).get("event_type"),
        "nearest_event_type": (nearest or {}).get("event_type"),
        "nearest_event_ts": None,
        "nearest_event_hours": None
        if not nearest or nearest.get("hours_until") is None
        else round(float(nearest["hours_until"]), 2),
        "event_window_phase": phase,
        "event_short_term_state": _event_short_term_state(phase, dominant),
        "event_risk_lock_level": lock_level,
        "event_lock_level": lock_level,
        "penalty_channel": "event_timing_only",
        "risk_score": risk_score,
        "event_risk_score": risk_score,
        "event_uncertainty_score": risk_score,
        "confidence_adjustment": confidence_adjustment,
        "trade_gate": trade_gate,
        "risk_drivers": active_rows,
        "context_notes": context_notes,
        "summary": summary,
        "event_policy_score": 0.0,
        "direction_score_component": 0.0,
        "aggregation_guard": {
            "directional_score_allowed": False,
            "bullish_bearish_vote_allowed": False,
            "confidence_adjustment_floor": -0.15,
            "module_final_score_before_guard": round(
                float(aggregation.get("module_final_score") or 0.0),
                4,
            ),
        },
    }


def _event_policy_surprise(metric_items: list[dict[str, Any]]) -> float:
    values = [
        abs(value)
        for value in (
            _metric_value(metric_items, "macro_surprise_score"),
            _metric_value(metric_items, "aggregate_macro_surprise"),
        )
        if value is not None
    ]
    return max(values) if values else 0.0


def _classify_macro_event_window(
    *,
    event_type: str,
    hours_until: float | None,
    signed_days: float | None,
    macro_surprise: float,
) -> dict[str, Any] | None:
    is_fomc = event_type == "fomc"
    if signed_days is not None and signed_days < 0:
        elapsed_hours = abs(signed_days) * 24.0
        if elapsed_hours <= 0.5:
            return _event_row(
                event_type,
                elapsed_hours,
                "post_digest",
                "hard",
                80.0 if is_fomc else 75.0,
                "WAIT_FIRST_REACTION",
                "Event has just landed; first reaction should settle before new entries.",
            )
        if elapsed_hours <= 2.0 and macro_surprise >= 0.65:
            return _event_row(
                event_type,
                elapsed_hours,
                "post_digest",
                "soft",
                68.0,
                "EXTENDED_POST_EVENT_DIGEST",
                "Event surprise or reaction proxy is elevated, so digest window remains active.",
            )
        if elapsed_hours <= 2.0:
            return _event_row(
                event_type,
                elapsed_hours,
                "post_digest",
                "soft",
                45.0,
                "POST_EVENT_REDUCE_SIZE",
                "Event has landed recently; reduce size until the first repricing wave settles.",
            )
        return None
    if hours_until is None:
        return None
    if is_fomc:
        if hours_until <= 12:
            return _event_row(event_type, hours_until, "hard_lock", "hard", 90.0, "WAIT_POLICY_RELEASE", "FOMC is inside the 12h hard-lock window.")
        if hours_until <= 48:
            return _event_row(event_type, hours_until, "caution", "soft", 70.0, "PRE_FOMC_48H_CAUTION", "FOMC is inside the 48h caution window.")
    else:
        if hours_until <= 6:
            return _event_row(event_type, hours_until, "hard_lock", "hard", 85.0, "WAIT_DATA_RELEASE", f"{event_type.upper()} is inside the 6h hard-lock window.")
        if hours_until <= 24:
            return _event_row(event_type, hours_until, "caution", "soft", 65.0, f"PRE_{event_type.upper()}_24H_CAUTION", f"{event_type.upper()} is inside the 24h caution window.")
    return None


def _classify_fed_speech_window(
    *,
    hours_until: float | None,
    scheduled_risk: float,
) -> dict[str, Any] | None:
    if hours_until is None:
        return None
    if hours_until <= 3 and scheduled_risk >= 0.7:
        return _event_row(
            "fed_speech",
            hours_until,
            "hard_lock",
            "hard",
            75.0,
            "WAIT_FED_SPEECH",
            "High-risk Fed speech is inside the 3h risk window.",
        )
    if hours_until <= 12 and scheduled_risk >= 0.35:
        return _event_row(
            "fed_speech",
            hours_until,
            "caution",
            "soft",
            55.0,
            "PRE_FED_SPEECH_CAUTION",
            "Fed speech timing warrants reduced breakout confidence.",
        )
    return None


def _event_row(
    event_type: str,
    hours: float | None,
    phase: str,
    lock_level: str,
    risk_score: float,
    reason_code: str,
    note: str,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "hours_until": None if hours is None else round(float(hours), 2),
        "phase": phase,
        "lock_level": lock_level,
        "risk_score": round(float(risk_score), 2),
        "reason_code": reason_code,
        "note": note,
    }


def _dominant_event_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (
            -float(row.get("risk_score") or 0.0),
            EVENT_POLICY_PRIORITY.get(str(row.get("event_type")), 99),
        ),
    )[0]


def _nearest_event_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get("hours_until") is not None]
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: abs(float(row.get("hours_until") or 0.0)))[0]


def _event_trade_gate(
    phase: str,
    risk_score: float,
    dominant: dict[str, Any] | None,
) -> dict[str, Any]:
    reason_code = str((dominant or {}).get("reason_code") or "EVENT_NEUTRAL")
    if phase == "hard_lock":
        return {
            "allow_new_position": False,
            "allow_add_position": False,
            "allow_breakout_entry": False,
            "allow_market_entry": False,
            "position_size_multiplier": 0.0,
            "require_wait_until_ts": None,
            "reason_code": reason_code,
        }
    if phase == "post_digest":
        multiplier = 0.5 if risk_score < 70 else 0.0
        return {
            "allow_new_position": multiplier > 0,
            "allow_add_position": False,
            "allow_breakout_entry": False,
            "allow_market_entry": multiplier > 0,
            "position_size_multiplier": multiplier,
            "require_wait_until_ts": None,
            "reason_code": reason_code,
        }
    if phase == "caution":
        multiplier = 0.5 if risk_score >= 68 else 0.7
        return {
            "allow_new_position": True,
            "allow_add_position": False,
            "allow_breakout_entry": False,
            "allow_market_entry": True,
            "position_size_multiplier": multiplier,
            "require_wait_until_ts": None,
            "reason_code": reason_code,
        }
    return {
        "allow_new_position": True,
        "allow_add_position": True,
        "allow_breakout_entry": True,
        "allow_market_entry": True,
        "position_size_multiplier": 1.0,
        "require_wait_until_ts": None,
        "reason_code": "EVENT_NEUTRAL",
    }


def _event_confidence_adjustment(phase: str, risk_score: float) -> float:
    if phase == "hard_lock":
        return -0.15
    if phase == "post_digest":
        return -0.12 if risk_score >= 70 else -0.08
    if phase == "caution":
        return -0.1 if risk_score >= 68 else -0.06
    return 0.0


def _event_short_term_state(phase: str, dominant: dict[str, Any] | None) -> str:
    if not dominant:
        return "event_neutral"
    event_type = str(dominant.get("event_type") or "event")
    if phase == "hard_lock":
        return f"{event_type}_hard_lock"
    if phase == "post_digest":
        return f"{event_type}_post_digest"
    if phase == "caution":
        return f"{event_type}_caution"
    return "event_neutral"


def _event_policy_summary(
    dominant: dict[str, Any] | None,
    nearest: dict[str, Any] | None,
    phase: str,
    trade_gate: dict[str, Any],
) -> str:
    if not dominant:
        return "Event policy is neutral; no active macro event gate is restricting trade permission."
    dominant_type = str(dominant.get("event_type") or "event")
    nearest_type = str((nearest or {}).get("event_type") or dominant_type)
    return (
        f"Event policy is in {phase} because dominant_event={dominant_type}; "
        f"nearest_event={nearest_type}. trade_gate={trade_gate.get('reason_code')} "
        f"and position_size_multiplier={trade_gate.get('position_size_multiplier')}."
    )


def _options_volatility_v21_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    iv = _metric_value(metric_items, "options_iv")
    rv = _metric_value(metric_items, "options_rv")
    pcr = _metric_value(metric_items, "put_call_ratio")
    skew = _metric_value(metric_items, "options_skew")
    expiry_notional = _metric_value(metric_items, "options_expiry_notional")
    max_pain_raw = _metric_value(metric_items, "max_pain_distance")
    gamma_raw = _metric_value(metric_items, "gamma_wall_proxy_distance")
    spread = _metric_value(metric_items, "iv_rv_spread")
    if spread is None and iv is not None and rv is not None:
        spread = iv - rv
    ratio = _metric_value(metric_items, "iv_rv_ratio")
    if ratio is None and iv is not None and rv:
        ratio = iv / rv
    iv_change = _metric_value(metric_items, "iv_change_1d")
    rv_change = _metric_value(metric_items, "rv_change_1d")
    pcr_z = _metric_value(metric_items, "put_call_ratio_z")
    pcr_change = _metric_value(metric_items, "put_call_ratio_change_1d")
    skew_abs = _metric_value(metric_items, "options_skew_abs")
    if skew_abs is None and skew is not None:
        skew_abs = abs(skew)
    expiry_days = _metric_value(metric_items, "expiry_days")
    expiry_z = _metric_value(metric_items, "expiry_notional_z")
    max_pain_distance_pct = _metric_value(metric_items, "max_pain_distance_pct")
    if max_pain_distance_pct is None and max_pain_raw is not None:
        max_pain_distance_pct = abs(max_pain_raw)
    gamma_distance_pct = _metric_value(metric_items, "gamma_wall_distance_pct")
    if gamma_distance_pct is None and gamma_raw is not None:
        gamma_distance_pct = abs(gamma_raw)

    required = [iv, rv, pcr, skew, expiry_notional, max_pain_raw, gamma_raw]
    missing_count = sum(1 for value in required if value is None)
    missing_ratio = missing_count / len(required)
    data_quality_state = "data_quality_degraded" if missing_ratio > 0.5 else "usable"
    skew_side = "unknown"
    if skew is not None:
        skew_side = "downside" if skew > 0.5 else "upside" if skew < -0.5 else "balanced"
    gamma_wall_side = "unknown"
    if gamma_raw is not None:
        gamma_wall_side = "above" if gamma_raw > 0.005 else "below" if gamma_raw < -0.005 else "near"

    iv_rv_spread_high = spread is not None and spread >= 5.0
    iv_rising = iv_change is None or iv_change >= 0
    rv_rising = rv_change is None or rv_change >= 0
    vol_expansion = bool(iv_rv_spread_high and iv_rising and rv_rising)
    realized_shock = bool(iv is not None and rv is not None and rv > iv and rv_rising)
    vol_compression = bool(
        iv is not None
        and rv is not None
        and iv <= 45
        and rv <= 40
        and (iv_change is None or iv_change <= 0)
        and (rv_change is None or rv_change <= 0)
    )
    volatility_state = (
        "vol_expansion_risk"
        if vol_expansion
        else "realized_vol_shock"
        if realized_shock
        else "vol_compression"
        if vol_compression
        else "iv_over_rv"
        if spread is not None and spread > 0
        else "vol_neutral"
    )

    pcr_high = bool((pcr is not None and pcr >= 1.2) or (pcr_z is not None and pcr_z >= 1.0))
    call_demand = bool((pcr is not None and pcr <= 0.75) or skew_side == "upside")
    downside_protection = bool(pcr_high and skew_side == "downside" and (skew_abs or 0) >= 2.0)
    protection_state = (
        "downside_protection_bid"
        if downside_protection
        else "call_chase_elevated"
        if call_demand
        else "balanced"
    )

    tail_elevated = bool((skew_abs or 0) >= 8.0 and iv_rising and (spread is None or spread >= 0))
    downside_tail = bool(skew_side == "downside" and (skew_abs or 0) >= 5.0 and pcr_high)
    upside_tail = bool(skew_side == "upside" and (skew_abs or 0) >= 5.0 and call_demand)
    tail_state = (
        "tail_risk_elevated"
        if tail_elevated and not downside_protection
        else "downside_tail_risk"
        if downside_tail
        else "upside_tail_risk"
        if upside_tail
        else "tail_risk_neutral"
    )

    days = expiry_days if expiry_days is not None else 999.0
    expiry_large = bool(
        (expiry_z is not None and expiry_z >= 1.5)
        or (expiry_notional or 0) >= 10_000_000_000
    )
    expiry_state = (
        "large_expiry_near"
        if days <= 3 and expiry_large
        else "large_expiry_week"
        if days <= 7 and expiry_large
        else "expiry_missing"
        if expiry_notional is None
        else "expiry_normal"
    )

    near_threshold = 0.01
    far_threshold = 0.035
    max_pain_near = max_pain_distance_pct is not None and max_pain_distance_pct <= near_threshold
    gamma_near = gamma_distance_pct is not None and gamma_distance_pct <= near_threshold
    pinning_likely = bool((max_pain_near or gamma_near) and days <= 7 and not realized_shock)
    pinning_state = (
        "pinning_likely"
        if pinning_likely
        else "gamma_wall_near"
        if gamma_near
        else "max_pain_far"
        if max_pain_distance_pct is not None and max_pain_distance_pct >= far_threshold
        else "structure_neutral"
    )

    if data_quality_state == "data_quality_degraded":
        short_state = "data_quality_degraded"
    elif pinning_likely and vol_expansion:
        short_state = (
            "pinning_before_expiry_vol_after"
            if days <= 2
            else "vol_expansion_risk_with_structure_resistance"
        )
    elif tail_state == "tail_risk_elevated":
        short_state = "tail_risk_elevated"
    elif protection_state == "downside_protection_bid":
        short_state = "downside_protection_bid"
    elif volatility_state == "vol_expansion_risk":
        short_state = "vol_expansion_risk"
    elif expiry_state == "large_expiry_near":
        short_state = "large_expiry_near"
    elif pinning_state == "pinning_likely":
        short_state = "pinning_likely"
    elif volatility_state == "vol_compression":
        short_state = "vol_compression"
    else:
        short_state = "vol_neutral"

    sub_scores = {
        "volatility_risk_score": 75.0 if volatility_state == "vol_expansion_risk" else 55.0 if realized_shock else 25.0,
        "protection_risk_score": 78.0 if protection_state == "downside_protection_bid" else 52.0 if protection_state == "call_chase_elevated" else 20.0,
        "tail_risk_score": 82.0 if tail_state == "tail_risk_elevated" else 70.0 if tail_state in {"downside_tail_risk", "upside_tail_risk"} else 20.0,
        "expiry_risk_score": 68.0 if expiry_state == "large_expiry_near" else 58.0 if expiry_state == "large_expiry_week" else 15.0,
        "pinning_risk_score": 50.0 if pinning_state == "pinning_likely" else 35.0 if pinning_state == "gamma_wall_near" else 15.0,
    }
    if data_quality_state == "data_quality_degraded":
        sub_scores = {key: min(value, 35.0) for key, value in sub_scores.items()}
    risk_score = round(
        max(sub_scores.values()) * 0.60
        + (sum(sub_scores.values()) / len(sub_scores)) * 0.40,
        2,
    )
    confidence_adjustment = (
        -0.15
        if risk_score >= 80
        else -0.10
        if risk_score >= 65
        else -0.05
        if short_state in {"pinning_likely", "large_expiry_near", "pinning_before_expiry_vol_after"}
        else 0.0
    )
    trade_permission_hint = (
        "wait_post_expiry"
        if short_state in {"large_expiry_near", "pinning_before_expiry_vol_after"}
        else "avoid_chasing"
        if short_state in {"downside_protection_bid", "tail_risk_elevated"}
        else "increase_risk_mode"
        if short_state.startswith("vol_expansion")
        else "reduce_breakout_confidence"
        if short_state == "pinning_likely"
        else "normal"
    )
    risk_drivers = [
        {"driver_type": "volatility_regime", "state": volatility_state, "risk_score": sub_scores["volatility_risk_score"]},
        {"driver_type": "protection_demand", "state": protection_state, "risk_score": sub_scores["protection_risk_score"]},
        {"driver_type": "tail_risk", "state": tail_state, "risk_score": sub_scores["tail_risk_score"]},
        {"driver_type": "expiry_pressure", "state": expiry_state, "risk_score": sub_scores["expiry_risk_score"]},
        {"driver_type": "pinning_structure", "state": pinning_state, "risk_score": sub_scores["pinning_risk_score"]},
    ]
    context_notes = [
        "options_volatility is risk and structure context, not directional alpha.",
        "Put/call, skew, max pain and gamma wall do not directly imply bullish or bearish direction.",
    ]
    summary = (
        f"Options structure state is {short_state}; it adjusts risk and confidence, "
        "not final direction."
    )
    return {
        "module": "options_volatility",
        "semantic_profile_version": "p3.c42.options_volatility.v2.1",
        "version": "p3.c42.options_volatility.v2.1",
        "module_purpose": "volatility_risk_and_expiry_structure",
        "module_direction": "neutral",
        "module_score": 0.0,
        "module_effective_score": 0.0,
        "risk_score": risk_score,
        "confidence_adjustment": confidence_adjustment,
        "trade_permission_hint": trade_permission_hint,
        "volatility_regime": {
            "state": volatility_state,
            "basis": {
                "options_iv": iv,
                "options_rv": rv,
                "iv_rv_spread": spread,
                "iv_rv_ratio": ratio,
                "iv_change_1d": iv_change,
                "rv_change_1d": rv_change,
            },
        },
        "protection_demand": {
            "state": protection_state,
            "basis": {
                "put_call_ratio": pcr,
                "put_call_ratio_z": pcr_z,
                "put_call_ratio_change_1d": pcr_change,
                "skew_side": skew_side,
            },
        },
        "tail_risk": {
            "state": tail_state,
            "basis": {
                "options_skew": skew,
                "skew_abs": skew_abs,
                "skew_side": skew_side,
            },
        },
        "expiry_pressure": {
            "state": expiry_state,
            "basis": {
                "options_expiry_notional": expiry_notional,
                "expiry_days": expiry_days,
                "expiry_notional_z": expiry_z,
            },
        },
        "pinning_structure": {
            "state": pinning_state,
            "basis": {
                "max_pain_distance_pct": max_pain_distance_pct,
                "gamma_wall_distance_pct": gamma_distance_pct,
                "gamma_wall_side": gamma_wall_side,
            },
        },
        "data_quality": {
            "state": data_quality_state,
            "missing_ratio": round(missing_ratio, 4),
            "missing_count": missing_count,
            "required_count": len(required),
            "coverage_score": aggregation.get("coverage_score"),
        },
        "options_short_term_state": short_state,
        "volatility_state": short_state,
        "risk_drivers": risk_drivers,
        "context_notes": context_notes,
        "summary": summary,
    }


def _trade_structure_flow_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    taker_ratio = _metric_value(metric_items, "taker_buy_sell_ratio")
    aggressive_flow_state = _aggressive_flow_state(taker_ratio)
    price_response_state = _price_response_state(metric_items, aggressive_flow_state)
    liquidation_state = _liquidation_state(metric_items, price_response_state)
    mempool_pressure_state = _mempool_pressure_state(metric_items)
    stablecoin_liquidity_state = _stablecoin_liquidity_state(metric_items)
    trade_structure_state = _trade_structure_state(
        aggressive_flow_state,
        price_response_state,
        liquidation_state,
    )
    confirmation_state = _trade_structure_confirmation_state(
        trade_structure_state,
        stablecoin_liquidity_state,
    )
    module_effective_bias = _trade_structure_effective_bias(
        trade_structure_state,
        stablecoin_liquidity_state,
        float(aggregation.get("module_effective_score") or 0.0),
    )
    risk_state = _trade_structure_risk_state(
        liquidation_state,
        mempool_pressure_state,
        trade_structure_state,
    )
    legacy = {
        "aggressive_flow_state": aggressive_flow_state,
        "price_response_state": price_response_state,
        "liquidation_state": liquidation_state,
        "liquidation_flow_state": liquidation_state,
        "liquidation_data_quality": "snapshot_not_full_market_volume",
        "mempool_pressure_state": mempool_pressure_state,
        "stablecoin_liquidity_state": stablecoin_liquidity_state,
        "stablecoin_buying_power_state": stablecoin_liquidity_state,
        "trade_structure_state": trade_structure_state,
        "module_effective_bias": module_effective_bias,
        "confirmation_state": confirmation_state,
        "risk_state": risk_state,
        "semantic_profile_version": "p3.c37.trade_structure_flow.v1",
        "component_metrics": [
            "taker_buy_sell_ratio",
            "btc_return_5m",
            "btc_return_15m",
            "btc_close_position_5m",
            "btc_close_position_15m",
            "liquidation_long_usd",
            "liquidation_short_usd",
            "mempool_blocks_to_clear",
            "mempool_min_fee_rate_sat_vb",
            "stablecoin_buying_power_proxy",
        ],
    }
    if not any(str(item.get("metric_id") or "") in TRADE_STRUCTURE_V23_PROFILE_METRICS for item in metric_items):
        return legacy
    return {**legacy, **_trade_structure_flow_v23_profile(metric_items, aggregation)}


def _trade_structure_flow_v23_profile(
    metric_items: list[dict[str, Any]],
    aggregation: dict[str, Any],
) -> dict[str, Any]:
    def value(metric_id: str, default: float = 0.0) -> float:
        raw = _metric_value(metric_items, metric_id)
        return default if raw is None else float(raw)

    ret_z_5m = value("trade_btc_return_z_5m")
    ret_z_15m = value("trade_btc_return_z_15m")
    ret_z_1h = value("trade_btc_return_z_1h")
    price_acceptance_5m = value("trade_price_acceptance_score_5m")
    price_acceptance_15m = value("trade_price_acceptance_score_15m")
    aggressive_flow_score = _clamp(
        (value("trade_agg_flow_delta_z_5m") * 0.45 + value("trade_agg_flow_delta_z_15m") * 0.55) / 2.5,
        -1.0,
        1.0,
    ) * 100.0
    absorption = max(value("trade_flow_absorption_score_5m"), value("trade_flow_absorption_score_15m"))
    exhaustion = max(value("trade_flow_exhaustion_score_5m"), value("trade_flow_exhaustion_score_15m"))
    liquidity_directional_score = _clamp(
        (value("trade_liquidity_directional_score_5m") * 0.35 + value("trade_liquidity_directional_score_15m") * 0.65)
        / 100.0,
        -1.0,
        1.0,
    ) * 100.0
    depth_thinning_15m = value("trade_depth_thinning_z_15m")
    spread_15m = value("trade_spread_z_15m")
    spot_led_score = value("trade_spot_led_score")
    perp_led_score = value("trade_perp_led_score")
    volume_quality_score = value("trade_volume_quality_score")
    spot_perp_quality_score = _clamp((spot_led_score - perp_led_score * 0.35 + volume_quality_score * 0.45) / 100.0, -1.0, 1.0) * 100.0
    oi_change_1h = value("btc_oi_change_1h_pct")
    funding = value("btc_funding_rate")
    funding_band = value("btc_funding_band")
    leverage_participation = value("trade_leverage_participation_score")
    leverage_crowding = max(value("trade_leverage_crowding_risk_score"), funding_band * 35.0 if funding_band > 0 else 0.0)
    leverage_structure_score = _clamp((leverage_participation - leverage_crowding) / 100.0, -1.0, 1.0) * 100.0
    long_liq = value("liquidation_long_usd")
    short_liq = value("liquidation_short_usd")
    liq_total = long_liq + short_liq
    liquidation_long_z = min(long_liq / 1_000_000.0, 3.0)
    liquidation_short_z = min(short_liq / 1_000_000.0, 3.0)
    liquidation_followthrough = value("trade_liquidation_followthrough_score")
    liquidation_absorption = max(value("trade_liquidation_absorption_score"), exhaustion)
    liquidation_cascade = max(value("trade_liquidation_cascade_score"), liquidation_long_z * max(-ret_z_15m, 0.0) * 25.0)
    squeeze_failure = max(value("trade_squeeze_failure_score"), liquidation_short_z * max(-value("trade_structure_residual_z"), 0.0) * 20.0)
    liquidation_response_score = _clamp(
        (liquidation_absorption - liquidation_cascade - squeeze_failure + max(liquidation_followthrough, 0.0) * 0.25) / 100.0,
        -1.0,
        1.0,
    ) * 100.0
    residual_z = value("trade_structure_residual_z")
    residual_confirmation_score = _clamp(residual_z / 2.0, -1.0, 1.0) * 100.0
    price_acceptance_score = _clamp((price_acceptance_5m * 0.35 + price_acceptance_15m * 0.65) / 100.0, -1.0, 1.0) * 100.0
    data_quality_flags: list[str] = []
    proxy_flags = ["orderbook_depth_missing_using_kline_spread_proxy"]
    if liq_total > 0:
        data_quality_flags.append("liquidation_snapshot_only")
    data_quality_penalty = 5.0 if proxy_flags else 0.0
    module_score_raw = (
        0.35 * price_acceptance_score
        + 0.20 * aggressive_flow_score
        + 0.15 * liquidity_directional_score
        + 0.15 * spot_perp_quality_score
        + 0.10 * leverage_structure_score
        + 0.05 * liquidation_response_score
        - data_quality_penalty
    )
    fast_mode_score = (
        0.40 * price_acceptance_score
        + 0.25 * aggressive_flow_score
        + 0.20 * liquidity_directional_score
        + 0.15 * liquidation_response_score
    )
    confirmed_score = (
        0.35 * price_acceptance_score
        + 0.25 * spot_perp_quality_score
        + 0.15 * leverage_structure_score
        + 0.15 * liquidity_directional_score
        + 0.10 * residual_confirmation_score
    )

    support_drivers: list[str] = []
    pressure_drivers: list[str] = []
    conflict_drivers: list[str] = []
    early_warning_flags: list[str] = []
    direction = "neutral"
    stage = "none"
    state = "trade_structure_neutral"
    implication = "neutral"

    if price_acceptance_score > 25:
        support_drivers.append("price_acceptance_positive")
    if price_acceptance_score < -25:
        pressure_drivers.append("price_acceptance_negative")
    if residual_confirmation_score > 40:
        support_drivers.append("btc_resisting_structure_pressure")
    if residual_confirmation_score < -40:
        pressure_drivers.append("btc_rejecting_structure_tailwind")
    if depth_thinning_15m >= 1.5 or spread_15m >= 1.5:
        early_warning_flags.append("liquidity_thinning")

    # Priority router: liquidation response > liquidity breakdown > leverage failure > spot-led trend > warnings.
    if data_quality_flags and not any(item.get("available", True) for item in metric_items):
        state, implication, direction, stage = "data_invalid", "neutral", "neutral", "none"
    elif liquidation_long_z >= 2 and ret_z_5m < -0.5 and ret_z_15m < -0.8 and residual_z <= -1:
        state, implication, direction, stage = (
            "liquidation_cascade_confirmed",
            "downside_cascade_confirmed",
            "bearish",
            "fast_signal",
        )
    elif liquidation_long_z >= 2 and ret_z_5m >= 0 and residual_z >= 1:
        state, implication, direction, stage = (
            "forced_selling_absorbed",
            "forced_selling_absorbed",
            "bullish",
            "fast_signal",
        )
    elif liquidation_short_z >= 2 and ret_z_5m > 0.5 and ret_z_15m > 0.8 and oi_change_1h < 0 and residual_z >= 1:
        state, implication, direction, stage = (
            "short_squeeze_confirmed",
            "short_squeeze_confirmed",
            "bullish",
            "fast_signal",
        )
    elif depth_thinning_15m >= 1.5 and spread_15m >= 1 and ret_z_15m < -0.8 and residual_z <= -1:
        state, implication, direction, stage = (
            "downside_liquidity_breakdown_confirmed",
            "downside_liquidity_stress_confirmed",
            "bearish",
            "confirmed_signal",
        )
    elif oi_change_1h > 0 and (funding_band >= 1 or funding > 0.0003) and ret_z_15m < -0.5 and residual_z <= -1:
        state, implication, direction, stage = "long_crowding_failure", "crowded_longs_failing", "bearish", "fast_signal"
    elif squeeze_failure >= 45 and residual_z < 0:
        state, implication, direction, stage = "squeeze_failed", "upside_squeeze_failed", "bearish", "conflict"
    elif spot_led_score >= 60 and volume_quality_score >= 50 and ret_z_15m > 0.8 and ret_z_1h > 0 and residual_z >= 0:
        state, implication, direction, stage = (
            "spot_led_trend_accepted",
            "spot_led_trend_confirmed",
            "bullish",
            "confirmed_signal",
        )
    elif spot_led_score >= 60 and volume_quality_score >= 50 and ret_z_15m > 0.8 and residual_z <= -1:
        state, implication, direction, stage = (
            "btc_rejecting_trade_structure_tailwind",
            "internal_weakness",
            "neutral",
            "conflict",
        )
        conflict_drivers.append("confirmed_signal_blocked_without_price_acceptance_and_residual_alignment")
    elif perp_led_score >= 60 and oi_change_1h > 0 and (funding_band >= 1 or funding > 0.0003) and spot_led_score < 40 and ret_z_15m >= 0:
        state, implication, direction, stage = (
            "perp_led_rally_fragile",
            "leverage_supported_but_fragile",
            "neutral",
            "early_warning",
        )
        early_warning_flags.append("perp_led_rally_fragile")
    elif (depth_thinning_15m >= 1.5 or spread_15m >= 1.5) and abs(ret_z_15m) < 0.5:
        state, implication, direction, stage = "liquidity_breakdown_warning", "liquidity_fragile", "neutral", "early_warning"
    elif value("trade_agg_flow_delta_z_5m") > 1 and ret_z_5m > 0.5 and value("trade_spread_z_5m") <= 1:
        state, implication, direction, stage = "micro_turn_up_candidate", "upside_micro_turn_candidate", "bullish", "early_warning"
    elif value("trade_agg_flow_delta_z_5m") < -1 and ret_z_5m < -0.5 and value("trade_depth_thinning_z_5m") >= 1:
        state, implication, direction, stage = "micro_turn_down_candidate", "downside_micro_turn_candidate", "bearish", "early_warning"
    elif abs(fast_mode_score) >= 55 and (ret_z_5m * ret_z_15m) > 0:
        direction = "bullish" if fast_mode_score > 0 else "bearish"
        stage = "fast_signal"
        state = "trade_structure_fast_signal"
        implication = "structure_fast_confirmation"
    elif abs(fast_mode_score) >= 35:
        direction = "bullish" if fast_mode_score > 0 else "bearish"
        stage = "early_warning"
        state = "trade_structure_early_warning"
        implication = "structure_pressure_emerging"

    if stage == "confirmed_signal" and (price_acceptance_score * residual_confirmation_score <= 0):
        stage = "conflict"
        direction = "neutral"
        conflict_drivers.append("confirmed_signal_blocked_without_price_acceptance_and_residual_alignment")
    if fast_mode_score * confirmed_score < 0 and abs(fast_mode_score - confirmed_score) >= 60:
        stage = "conflict"
        direction = "neutral"
        conflict_drivers.append("fast_and_confirmed_scores_diverge")

    module_score = round(_clamp(module_score_raw / 100.0, -1.0, 1.0), 4)
    confidence = round(_clamp(72.0 - data_quality_penalty - len(conflict_drivers) * 10.0, 0.0, 100.0), 2)
    risk_score = round(
        _clamp(max(depth_thinning_15m * 25.0, spread_15m * 20.0, leverage_crowding, liquidation_cascade, squeeze_failure), 0.0, 100.0),
        2,
    )
    multi_horizon = {
        "5m": {
            "direction": _direction_from_score(ret_z_5m),
            "score": round(ret_z_5m * 25.0, 2),
            "price_acceptance": round(price_acceptance_5m, 2),
            "confirmed_by_15m": (ret_z_5m * ret_z_15m) > 0 and abs(ret_z_15m) >= 0.5,
        },
        "15m": {
            "direction": _direction_from_score(ret_z_15m),
            "score": round(ret_z_15m * 25.0, 2),
            "price_acceptance": round(price_acceptance_15m, 2),
        },
        "1h": {
            "direction": _direction_from_score(ret_z_1h),
            "score": round(ret_z_1h * 25.0, 2),
            "price_acceptance": round(price_acceptance_score, 2),
        },
    }
    scores = {
        "price_acceptance_score": round(price_acceptance_score, 2),
        "aggressive_flow_score": round(aggressive_flow_score, 2),
        "liquidity_directional_score": round(liquidity_directional_score, 2),
        "spot_perp_quality_score": round(spot_perp_quality_score, 2),
        "leverage_structure_score": round(leverage_structure_score, 2),
        "liquidation_response_score": round(liquidation_response_score, 2),
        "residual_confirmation_score": round(residual_confirmation_score, 2),
        "fast_mode_score": round(fast_mode_score, 2),
        "confirmed_score": round(confirmed_score, 2),
        "data_quality_penalty": round(data_quality_penalty, 2),
    }
    states = {
        "liquidity": {
            "spread_z_5m": value("trade_spread_z_5m"),
            "spread_z_15m": spread_15m,
            "depth_thinning_z_5m": value("trade_depth_thinning_z_5m"),
            "depth_thinning_z_15m": depth_thinning_15m,
            "liquidity_directional_score": round(liquidity_directional_score, 2),
        },
        "aggressive_flow": {
            "agg_flow_delta_z_5m": value("trade_agg_flow_delta_z_5m"),
            "agg_flow_delta_z_15m": value("trade_agg_flow_delta_z_15m"),
            "absorption_score": round(absorption, 2),
            "exhaustion_score": round(exhaustion, 2),
        },
        "spot_perp_lead": {
            "spot_led_score": round(spot_led_score, 2),
            "perp_led_score": round(perp_led_score, 2),
            "volume_quality_score": round(volume_quality_score, 2),
        },
        "leverage": {
            "open_interest_change_1h_pct": oi_change_1h,
            "funding_rate": funding,
            "funding_band": funding_band,
            "leverage_participation_score": round(leverage_participation, 2),
            "leverage_crowding_risk_score": round(leverage_crowding, 2),
        },
        "liquidation": {
            "long_usd": long_liq,
            "short_usd": short_liq,
            "liquidation_long_z": round(liquidation_long_z, 2),
            "liquidation_short_z": round(liquidation_short_z, 2),
            "followthrough_score": round(liquidation_followthrough, 2),
            "absorption_score": round(liquidation_absorption, 2),
            "cascade_score": round(liquidation_cascade, 2),
            "squeeze_failure_score": round(squeeze_failure, 2),
        },
        "btc_response": {
            "btc_return_z_5m": round(ret_z_5m, 4),
            "btc_return_z_15m": round(ret_z_15m, 4),
            "btc_return_z_1h": round(ret_z_1h, 4),
        },
        "residual": {
            "structure_pressure_z": round(value("trade_structure_pressure_z"), 4),
            "expected_return_z": round(value("trade_expected_return_z"), 4),
            "trade_structure_residual_z": round(residual_z, 4),
        },
    }
    summary = (
        f"trade_structure_flow.v2.3 state={state}; stage={stage}; "
        f"score={module_score:.3f}; residual_z={residual_z:.2f}; "
        "direction requires price acceptance and standardized residual."
    )
    contract = {
        "module": "trade_structure_flow",
        "version": "p3.c58.trade_structure_flow.v2.3",
        "module_direction": direction,
        "module_score": module_score,
        "confidence_score": confidence,
        "signal_stage": stage,
        "trade_structure_state": state,
        "btc_implication": implication,
        "scores": scores,
        "multi_horizon": multi_horizon,
        "states": states,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "conflict_drivers": conflict_drivers,
        "early_warning_flags": early_warning_flags,
        "data_quality_flags": data_quality_flags,
        "proxy_flags": proxy_flags,
        "invalidation_conditions": [
            "opposite 15m price acceptance with residual confirmation",
            "liquidity warning invalidated if spread/depth proxies normalize and BTC holds range",
        ],
    }
    return {
        "semantic_profile_version": "p3.c58.trade_structure_flow.v2.3",
        "module_direction": direction,
        "module_score": module_score,
        "module_effective_score": module_score,
        "confidence_score": confidence,
        "risk_score": risk_score,
        "signal_stage": stage,
        "trade_structure_state": state,
        "btc_implication": implication,
        "scores": scores,
        "multi_horizon": multi_horizon,
        "states": states,
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "conflict_drivers": conflict_drivers,
        "early_warning_flags": early_warning_flags,
        "data_quality_flags": data_quality_flags,
        "proxy_flags": proxy_flags,
        "invalidation_conditions": contract["invalidation_conditions"],
        "summary": summary,
        "display_state": stage,
        "display_summary": summary,
        "trade_structure_flow_v23": contract,
    }


def _aggressive_flow_state(taker_ratio: float | None) -> str:
    if taker_ratio is None:
        return "unknown"
    if taker_ratio > 1.30:
        return "strong_buying_pressure"
    if taker_ratio >= 1.12:
        return "buying_pressure"
    if taker_ratio >= 1.03:
        return "mild_buy_pressure"
    if taker_ratio > 0.97:
        return "neutral"
    if taker_ratio > 0.88:
        return "mild_sell_pressure"
    if taker_ratio >= 0.70:
        return "selling_pressure"
    return "strong_selling_pressure"


def _price_response_state(
    metric_items: list[dict[str, Any]],
    aggressive_flow_state: str,
) -> str:
    lookup = {
        str(item.get("metric_id") or ""): {"current": _metric_value(metric_items, str(item.get("metric_id") or ""))}
        for item in metric_items
        if item.get("metric_id")
    }
    detail = _trade_structure_price_response_detail(lookup)
    state = str(detail["price_response_state"])
    if state == "unknown" and aggressive_flow_state == "neutral":
        return "neutral_price_response"
    return state


def _liquidation_state(
    metric_items: list[dict[str, Any]],
    price_response_state: str,
) -> str:
    long_liq = _metric_value(metric_items, "liquidation_long_usd") or 0.0
    short_liq = _metric_value(metric_items, "liquidation_short_usd") or 0.0
    if max(long_liq, short_liq) < 1_000_000:
        return "quiet"
    if long_liq > short_liq * 1.5:
        if price_response_state in {"downside_response", "weak_downside_response"}:
            return "long_flush_panic_risk"
        if price_response_state in {"upside_response", "weak_upside_response"}:
            return "long_flush_absorbed"
        return "long_flush"
    if short_liq > long_liq * 1.5:
        if price_response_state in {"upside_response", "weak_upside_response"}:
            return "short_squeeze_chase_risk"
        if price_response_state in {"downside_response", "weak_downside_response"}:
            return "squeeze_failed"
        return "short_squeeze"
    return "mixed_liquidation"


def _mempool_pressure_state(metric_items: list[dict[str, Any]]) -> str:
    blocks = _metric_value(metric_items, "mempool_blocks_to_clear")
    min_fee = _metric_value(metric_items, "mempool_min_fee_rate_sat_vb")
    vsize = _metric_value(metric_items, "mempool_vsize_mb")
    if blocks is not None and blocks <= 2 and (min_fee is None or min_fee <= 5):
        return "normal_context"
    if (blocks is not None and blocks > 6 and min_fee is not None and min_fee >= 50) or (
        vsize is not None and vsize >= 50
    ):
        return "extreme_execution_risk"
    if (blocks is not None and blocks > 2) or (min_fee is not None and min_fee > 10) or (
        vsize is not None and vsize > 5
    ):
        return "execution_friction"
    return "normal_context"


def _stablecoin_liquidity_state(metric_items: list[dict[str, Any]]) -> str:
    item = _metric_by_id(metric_items, "stablecoin_buying_power_proxy")
    value = _metric_value(metric_items, "stablecoin_buying_power_proxy")
    score = float((item or {}).get("metric_score") or 0.0)
    direction = str((item or {}).get("direction") or "")
    if score < 0 or direction == "bearish" or (value is not None and value < -100_000_000):
        return "liquidity_pressure"
    if score > 0 or direction == "bullish" or (value is not None and value > 100_000_000):
        return "liquidity_support"
    return "neutral_liquidity"


def _trade_structure_state(
    aggressive_flow_state: str,
    price_response_state: str,
    liquidation_state: str,
) -> str:
    if liquidation_state in {
        "short_squeeze_chase_risk",
        "long_flush_panic_risk",
        "long_flush_absorbed",
        "squeeze_failed",
    }:
        return liquidation_state
    if aggressive_flow_state in {"strong_buying_pressure", "buying_pressure"}:
        if price_response_state == "upside_response":
            return "bullish_confirmation"
        if price_response_state == "no_upside_response":
            return "absorption_or_trapped_long"
        if price_response_state == "upside_rejected":
            return "buy_pressure_rejected"
        return "buy_pressure_unconfirmed"
    if aggressive_flow_state in {"strong_selling_pressure", "selling_pressure"}:
        if price_response_state == "downside_response":
            return "bearish_confirmation"
        if price_response_state == "no_downside_response":
            return "sell_absorption_or_trapped_short"
        if price_response_state == "downside_rejected":
            return "sell_pressure_rejected"
        return "sell_pressure_unconfirmed"
    if aggressive_flow_state in {"mild_buy_pressure", "mild_sell_pressure"}:
        return "mixed_structure"
    return "quiet_structure"


def _trade_structure_confirmation_state(
    trade_structure_state: str,
    stablecoin_liquidity_state: str,
) -> str:
    if trade_structure_state in {"bullish_confirmation", "bearish_confirmation"}:
        return "weak_confirmed" if stablecoin_liquidity_state == "liquidity_pressure" else "confirmed"
    if trade_structure_state in {"quiet_structure", "mixed_structure"}:
        return "not_applicable"
    return "unconfirmed"


def _trade_structure_effective_bias(
    trade_structure_state: str,
    stablecoin_liquidity_state: str,
    module_effective_score: float,
) -> str:
    if trade_structure_state == "bullish_confirmation":
        return "mild_support" if stablecoin_liquidity_state == "liquidity_pressure" else "support"
    if trade_structure_state == "bearish_confirmation":
        return "pressure"
    if trade_structure_state == "buy_pressure_unconfirmed":
        return "mild_support"
    if trade_structure_state in {"sell_pressure_unconfirmed", "absorption_or_trapped_long", "buy_pressure_rejected"}:
        return "mild_pressure"
    if trade_structure_state in {"sell_absorption_or_trapped_short", "sell_pressure_rejected"}:
        return "mild_support"
    return _direction_from_score(module_effective_score)


def _trade_structure_risk_state(
    liquidation_state: str,
    mempool_pressure_state: str,
    trade_structure_state: str,
) -> str:
    if mempool_pressure_state in {"execution_friction", "extreme_execution_risk"}:
        return mempool_pressure_state
    if liquidation_state != "quiet":
        return liquidation_state
    if trade_structure_state in {
        "absorption_or_trapped_long",
        "sell_absorption_or_trapped_short",
        "buy_pressure_rejected",
        "sell_pressure_rejected",
    }:
        return trade_structure_state
    return "normal_context"


def _trend_state_from_module(
    module_id: str,
    direction_score: float,
    risk_score: float,
    confidence_score: float,
    aggregation: dict[str, Any],
    metric_items: list[dict[str, Any]],
) -> tuple[str, str]:
    module_state = str(aggregation.get("module_state") or "")
    conflict_score = float(aggregation.get("conflict_score") or 0.0)
    raw_effective_conflict = bool(aggregation.get("raw_effective_conflict"))
    has_improving_pressure = _module_has_improving_pressure(metric_items)
    has_crowding = _module_has_crowding(metric_items)

    if module_id == "kline_orderflow":
        kline_states = [
            str(item.get("kline_trend_state"))
            for item in metric_items
            if item.get("kline_trend_state")
        ]
        if kline_states:
            state = kline_states[0]
            reason = next(
                (
                    str(item.get("score_reason") or item.get("metric_explanation"))
                    for item in metric_items
                    if item.get("kline_trend_state") == state
                ),
                "Kline orderflow uses price, candle structure, volume confirmation and 24h context.",
            )
            return state, reason
    if module_id == "event_policy" and risk_score >= TREND_EVENT_RISK_LOCK_THRESHOLD:
        return (
            "event_risk_locked",
            "Event-policy risk is elevated, so the module locks publishing tone rather than forcing direction.",
        )
    if (
        (module_state == "bearish_but_improving" or has_improving_pressure)
        and direction_score <= -TREND_CONTEXTUAL_DIRECTION_THRESHOLD
        and confidence_score >= 35
    ):
        return (
            "bearish_but_improving",
            "Bearish pressure remains, but improving flow/deleveraging evidence keeps it from becoming one-way pressure.",
        )
    if (
        module_state == "internal_conflict"
        and conflict_score >= TREND_INTERNAL_CONFLICT_THRESHOLD
    ) or conflict_score >= TREND_CONFLICT_THRESHOLD or raw_effective_conflict:
        return (
            "conflict_no_trade",
            "Raw/effective or internal module signals conflict enough to require confirmation.",
        )
    if direction_score >= TREND_STRONG_DIRECTION_THRESHOLD:
        if risk_score >= 65 or has_crowding:
            return (
                "bullish_but_crowded",
                "Directional support is positive, but leverage/risk metrics show crowding.",
            )
        if confidence_score >= 55:
            return (
                "risk_on_confirmed",
                "Positive direction is supported by adequate module confidence and no major conflict.",
            )
    if direction_score >= TREND_SUPPORT_CONFIRM_THRESHOLD and module_state == "support_dominant":
        if risk_score >= 55 or has_crowding:
            return (
                "bullish_but_crowded",
                "Support is visible, but risk or crowding prevents a clean risk-on confirmation.",
            )
        if confidence_score >= 60:
            return (
                "risk_on_confirmed",
                "Support-dominant module has enough confidence to mark local risk-on confirmation.",
            )
    if direction_score <= TREND_STRONG_DIRECTION_THRESHOLD * -1:
        if module_state == "bearish_but_improving" or has_improving_pressure:
            return (
                "bearish_but_improving",
                "Pressure remains bearish, but flow or effective-score evidence shows easing pressure.",
            )
        return (
            "bearish_pressure",
            "Negative direction is dominant and not yet offset by enough improving evidence.",
        )
    if (
        direction_score <= TREND_PRESSURE_CONFIRM_THRESHOLD
        and module_state == "pressure_dominant"
        and confidence_score >= 55
    ):
        return (
            "bearish_pressure",
            "Pressure-dominant module has enough confidence to mark directional pressure even below strong-score threshold.",
        )
    return (
        "neutral_wait_confirm",
        "Support and pressure are not strong enough for a directional module state.",
    )


def _module_has_crowding(metric_items: list[dict[str, Any]]) -> bool:
    crowded_states = {
        "overheated_long_crowding",
        "elevated_long_crowding",
        "long_crowding_downside",
        "leverage_build_unconfirmed",
    }
    return any(str(item.get("crowding_state") or "") in crowded_states for item in metric_items)


def _module_has_improving_pressure(metric_items: list[dict[str, Any]]) -> bool:
    improving_states = {"bearish_but_improving", "deleveraging", "deleveraging_selloff"}
    return any(
        str(item.get("flow_state") or item.get("crowding_state") or "") in improving_states
        for item in metric_items
    )


def _weighted_average(
    items: list[dict[str, Any]],
    value_key: str,
    default: float,
) -> float:
    numerator = 0.0
    denominator = 0.0
    for item in items:
        weight = abs(float(item.get("weight") or 1.0))
        value = item.get(value_key)
        if value is None:
            value = default
        numerator += float(value) * weight
        denominator += weight
    if denominator <= 0:
        return default
    return _clamp(numerator / denominator)


def _module_quality_score(metric_items: list[dict[str, Any]], payload: dict[str, Any]) -> float:
    quality = payload.get("evidence_summary", {}).get("quality_explanation", {}).get(
        "overall_score"
    )
    if quality is not None:
        return _clamp(float(quality))
    return _weighted_average(metric_items, "quality_score", default=1.0)


def _has_raw_effective_conflict(module_score: float, module_effective_score: float) -> bool:
    return (
        _direction_from_score(module_score) != _direction_from_score(module_effective_score)
        and abs(module_score) > 0.08
        and abs(module_effective_score) > 0.03
    )


def _module_state(
    module_score: float,
    module_effective_score: float,
    raw_effective_conflict: bool,
    conflict_score: float,
) -> str:
    if raw_effective_conflict:
        if module_score < 0 < module_effective_score:
            return "bearish_but_improving"
        if module_score > 0 > module_effective_score:
            return "bullish_but_deteriorating"
        return "raw_effective_conflict"
    if conflict_score >= 0.5:
        return "internal_conflict"
    if module_effective_score > 0.08:
        return "support_dominant"
    if module_effective_score < -0.08:
        return "pressure_dominant"
    return "balanced"


def _module_top_items(
    metric_items: list[dict[str, Any]],
    positive: bool,
    limit: int,
) -> list[dict[str, Any]]:
    signed = [
        item
        for item in metric_items
        if (float(item.get("metric_effective_score") or item.get("metric_score") or 0.0) > 0)
        == positive
        and abs(float(item.get("metric_effective_score") or item.get("metric_score") or 0.0))
        > 0
    ]
    return [
        _module_contributor_item(item)
        for item in sorted(
            signed,
            key=lambda item: abs(
                float(item.get("metric_effective_score") or item.get("metric_score") or 0.0)
            ),
            reverse=True,
        )[:limit]
    ]


def _module_top_contributors(
    metric_items: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    return [
        _module_contributor_item(item)
        for item in sorted(
            metric_items,
            key=lambda item: abs(
                float(item.get("metric_effective_score") or item.get("metric_score") or 0.0)
            ),
            reverse=True,
        )[:limit]
    ]


def _module_contributor_item(item: dict[str, Any]) -> dict[str, Any]:
    score = float(item.get("metric_effective_score") or item.get("metric_score") or 0.0)
    if score > 0.0001:
        contribution_side = "positive"
    elif score < -0.0001:
        contribution_side = "negative"
    else:
        contribution_side = "zero"
    return {
        "evidence_id": item.get("evidence_id"),
        "metric_id": item.get("metric_id"),
        "direction": item.get("direction") or _direction_from_score(score),
        "contribution_side": contribution_side,
        "direction_contribution": item.get("direction_contribution"),
        "funding_state": item.get("funding_state"),
        "crowding_signal": item.get("crowding_signal"),
        "trend_confirmation": item.get("trend_confirmation"),
        "oi_state": item.get("oi_state"),
        "oi_confirmation": item.get("oi_confirmation"),
        "oi_trend_signal": item.get("oi_trend_signal"),
        "positioning_signal": item.get("positioning_signal"),
        "crowding_contribution": item.get("crowding_contribution"),
        "positioning_scope": item.get("positioning_scope"),
        "metric_score": item.get("metric_score"),
        "metric_effective_score": item.get("metric_effective_score"),
        "score_bucket": item.get("score_bucket"),
        "quality_score": item.get("quality_score"),
        "freshness_weight": item.get("freshness_weight"),
        "reason": item.get("score_reason") or item.get("metric_explanation"),
    }


def _score_bucket_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        bucket: sum(1 for item in items if item["score_bucket"] == bucket)
        for bucket in (
            "positive",
            "negative",
            "zero",
            "unavailable",
        )
    }


def _score_bucket_v2_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        bucket: sum(1 for item in items if item.get("score_bucket_v2") == bucket)
        for bucket in SCORE_BUCKET_V2_VALUES
    }


def _zero_breakdown(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items) or 1
    counts = _score_bucket_v2_counts(items)
    raw_zero = sum(1 for item in items if item.get("score_bucket") == "zero")
    decision_zero = counts.get("rule_gap_zero", 0)
    return {
        "raw_zero_metric_count": raw_zero,
        "raw_zero_metric_ratio": round(raw_zero / total, 4),
        "score_bucket_v2_counts": counts,
        "decision_zero_metric_count": decision_zero,
        "decision_zero_metric_ratio": round(decision_zero / total, 4),
        "context_zero_ratio": round(counts.get("context_only", 0) / total, 4),
        "neutral_confirmed_ratio": round(counts.get("neutral_confirmed", 0) / total, 4),
        "combo_required_ratio": round(counts.get("combo_required", 0) / total, 4),
        "rule_gap_zero_ratio": round(decision_zero / total, 4),
        "unavailable_ratio": round(counts.get("unavailable", 0) / total, 4),
    }


def _module_direction_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        direction: sum(1 for item in items if item["module_direction"] == direction)
        for direction in ("bullish", "bearish", "mixed", "neutral", "unavailable")
    }


def _metric_explanation(
    metric_id: str,
    module_id: str,
    metric_name: str,
    value: Any,
    direction: str,
    score_bucket: str,
    semantic: dict[str, Any] | None = None,
) -> str:
    semantic = semantic or {}
    if semantic.get("metric_explanation"):
        return str(semantic["metric_explanation"])
    direction_text = {
        "bullish": "偏多",
        "bearish": "偏空",
        "mixed": "混合",
        "neutral": "中性",
        "unavailable": "不可用",
    }.get(direction, direction)
    bucket_text = {
        "positive": "本轮贡献正分",
        "negative": "本轮贡献负分",
        "zero": "本轮没有形成明确方向贡献",
        "unavailable": "本轮没有可靠生产数据，作为数据边界处理",
    }[score_bucket]
    return (
        f"{module_id} - {metric_name or metric_id}；用于衡量该 Radar 板块中的 "
        f"{metric_id} 变化。当前值为 {value if value is not None else '不可用'}，"
        f"方向为{direction_text}，{bucket_text}。"
    )


def _score_reason(
    feature: dict[str, Any],
    metric_score: float,
    score_bucket: str,
    semantic: dict[str, Any] | None = None,
) -> str:
    semantic = semantic or {}
    if semantic.get("score_reason"):
        return str(semantic["score_reason"])
    if score_bucket == "unavailable":
        return (
            f"指标不可用于本轮方向评分；run_scope={feature.get('feature_run_scope')}, "
            f"evidence_tier={feature.get('evidence_tier')}。"
        )
    if score_bucket == "zero":
        return "指标数据可用，但方向为中性/混合或权重不影响信号，因此计为 0 分观察项。"
    return (
        f"指标方向为 {feature.get('direction')}，权重={feature.get('weight')}，"
        f"质量分={feature.get('quality_score')}，形成 metric_score={round(metric_score, 4)}。"
    )


def _trade_structure_price_response_semantic(
    metric_id: str,
    module_id: str,
    current: float | None,
    feature_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    detail = _trade_structure_price_response_detail(feature_lookup)
    return _semantic_result(
        metric_id,
        module_id,
        current,
        "neutral",
        0.0,
        "semantic.trade_structure.price_response_confirmation",
        (
            f"Price response layer is {detail['price_response_state']} from "
            f"{detail['price_response_source']}; confidence="
            f"{detail['price_response_confidence']}."
        ),
        signal_type="confirmation_context",
        price_response_state=detail["price_response_state"],
        price_response_confidence=detail["price_response_confidence"],
        flow_price_efficiency_state=detail["flow_price_efficiency_state"],
        price_response_source=detail["price_response_source"],
        thresholds_used={
            "strong_buy_taker_ratio": 1.30,
            "strong_sell_taker_ratio": 0.70,
            "close_position_confirm": 0.55,
            "close_position_reject": 0.45,
        },
        component_metrics=[
            "taker_buy_sell_ratio",
            "btc_return_5m",
            "btc_return_15m",
            "btc_close_position_5m",
            "btc_close_position_15m",
            "btc_flow_price_efficiency_5m",
            "btc_return_1h",
            "btc_close_position_1h",
        ],
    )


def _trade_structure_price_response_detail(
    feature_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    taker_ratio = _lookup_current(feature_lookup, "taker_buy_sell_ratio")
    ret_5m = _lookup_current(feature_lookup, "btc_return_5m")
    ret_15m = _lookup_current(feature_lookup, "btc_return_15m")
    close_5m = _lookup_current(feature_lookup, "btc_close_position_5m")
    close_15m = _lookup_current(feature_lookup, "btc_close_position_15m")
    efficiency = _lookup_current(feature_lookup, "btc_flow_price_efficiency_5m")
    if efficiency is None:
        efficiency = _lookup_current(feature_lookup, "btc_flow_price_efficiency_15m")
    source = "5m_15m" if ret_5m is not None or ret_15m is not None else "1h_fallback"
    if ret_5m is None and ret_15m is None:
        ret_5m = _lookup_current(feature_lookup, "btc_return_1h")
        ret_15m = ret_5m
        close_5m = _lookup_current(feature_lookup, "btc_close_position_1h")
        close_15m = close_5m
    state = "unknown"
    confidence = 0.0
    if taker_ratio is not None and ret_5m is None:
        state = "need_kline_confirmation"
    elif taker_ratio is not None and ret_5m is not None:
        close_ref = close_5m if close_5m is not None else close_15m
        flow_state = _aggressive_flow_state(taker_ratio)
        if flow_state in {"strong_buying_pressure", "buying_pressure", "mild_buy_pressure"}:
            if ret_5m <= 0:
                state = "no_upside_response"
                confidence = 0.8
            elif close_ref is not None and close_ref < 0.45:
                state = "upside_rejected"
                confidence = 0.7
            elif ret_15m is not None and ret_15m > 0 and close_ref is not None and close_ref > 0.55:
                if flow_state == "strong_buying_pressure":
                    state = "upside_response"
                    confidence = 0.85
                else:
                    state = "weak_upside_response"
                    confidence = 0.55 if flow_state == "buying_pressure" else 0.4
            else:
                state = "weak_upside_response"
                confidence = 0.35
        elif flow_state in {"strong_selling_pressure", "selling_pressure", "mild_sell_pressure"}:
            if ret_5m >= 0:
                state = "no_downside_response"
                confidence = 0.8
            elif close_ref is not None and close_ref > 0.55:
                state = "downside_rejected"
                confidence = 0.7
            elif ret_15m is not None and ret_15m < 0 and close_ref is not None and close_ref < 0.45:
                if flow_state == "strong_selling_pressure":
                    state = "downside_response"
                    confidence = 0.85
                else:
                    state = "weak_downside_response"
                    confidence = 0.55 if flow_state == "selling_pressure" else 0.4
            else:
                state = "weak_downside_response"
                confidence = 0.35
        else:
            state = "neutral"
            confidence = 0.25
    if efficiency is None:
        efficiency_state = "unknown"
    elif efficiency >= 0.02:
        efficiency_state = "efficient"
    elif efficiency <= 0.005:
        efficiency_state = "inefficient"
    else:
        efficiency_state = "neutral"
    return {
        "price_response_state": state,
        "price_response_confidence": round(confidence, 4),
        "flow_price_efficiency_state": efficiency_state,
        "price_response_source": source,
    }


def _semantic_metric_view(
    module_id: str,
    feature: dict[str, Any],
    base_metric_score: float,
    base_direction: str,
    available: bool,
    feature_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metric_id = str(feature.get("metric_id") or "unknown_metric")
    weight = float(feature.get("weight") or 0.0)
    current = _safe_float(feature.get("current"))
    change = _safe_float(feature.get("change_24h"))
    if not available:
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "unavailable",
            0.0,
            "semantic.unavailable",
            "本轮没有可靠生产数据，作为数据边界处理，不参与方向评分。",
        )
    if module_id == "trade_structure_flow" and metric_id in TRADE_STRUCTURE_PRICE_RESPONSE_METRICS:
        return _trade_structure_price_response_semantic(
            metric_id,
            module_id,
            current,
            feature_lookup or {},
        )
    if module_id == "trade_structure_flow" and metric_id == "taker_buy_sell_ratio" and current is not None:
        override = _semantic_override(
            metric_id,
            module_id,
            current,
            change,
            weight,
            feature,
            feature_lookup or {},
        )
        if override is not None:
            return override
    if not feature.get("affects_signal", True) or weight == 0:
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.context_only",
            "该指标用于上下文或审计，不直接参与本轮方向评分。",
        )

    override = _semantic_override(
        metric_id,
        module_id,
        current,
        change,
        weight,
        feature,
        feature_lookup or {},
    )
    if override is not None:
        return override

    return _semantic_result(
        metric_id,
        module_id,
        current,
        base_direction,
        base_metric_score,
        "semantic.radar_rule",
        "沿用 Radar 原始方向规则，并按权重、变化幅度和数据质量形成分数。",
    )



def _lookup_current(feature_lookup: dict[str, dict[str, Any]], metric_id: str) -> float | None:
    feature = feature_lookup.get(metric_id) or {}
    return _safe_float(feature.get("current"))


def _lookup_change(feature_lookup: dict[str, dict[str, Any]], metric_id: str) -> float | None:
    feature = feature_lookup.get(metric_id) or {}
    return _safe_float(feature.get("change_24h"))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _event_risk_from_days(days: float | None) -> float:
    if days is None:
        return 0.0
    distance = abs(days)
    if distance <= 1:
        return 1.0
    if distance <= 3:
        return 0.7
    if distance <= 7:
        return 0.4
    if distance <= 14:
        return 0.2
    return 0.0


def _event_risk_from_hours(hours: float | None) -> float:
    if hours is None:
        return 0.0
    distance = abs(hours)
    if distance <= 24:
        return 1.0
    if distance <= 72:
        return 0.7
    if distance <= 168:
        return 0.4
    if distance <= 336:
        return 0.2
    return 0.0


def _kline_orderflow_semantic(
    *,
    metric_id: str,
    module_id: str,
    current: float | None,
    weight: float,
    feature_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    snapshot = _kline_structure_snapshot(feature_lookup)
    metric_score = _kline_metric_score(metric_id, weight, snapshot)
    direction = _direction_from_score(metric_score)
    if direction == "neutral" and snapshot["trend_state"] in {"bearish_but_absorbed", "rebound_unconfirmed"}:
        direction = "neutral"
    module_composite_score = float(snapshot["price_trend_score"])
    module_composite_direction = _direction_from_score(module_composite_score)
    kline_composite_contribution = _kline_composite_contribution(metric_id, weight, snapshot)
    reason = (
        f"{_kline_reason(snapshot)} Metric self direction is {direction}; "
        f"module composite state is {snapshot['trend_state']}."
    )
    return _semantic_result(
        metric_id,
        module_id,
        current,
        direction,
        metric_score,
        "semantic.kline_orderflow.composite",
        reason,
        signal_type="direction_signal" if direction in {"bullish", "bearish"} else "regime_signal",
        risk_score=snapshot["risk_score"],
        thresholds_used={
            "volume_zscore_confirmation": 1.5,
            "close_position_low": 0.3,
            "close_position_high": 0.7,
            "large_24h_drop": -0.03,
            "wick_absorption": 0.45,
        },
        component_metrics=[
            "btc_return_1h",
            "btc_return_4h",
            "btc_return_24h",
            "btc_close_position_1h",
            "btc_volume_zscore_1h",
            "btc_upper_wick_ratio_1h",
            "btc_lower_wick_ratio_1h",
            "btc_breakdown_24h_low",
            "btc_breakout_24h_high",
        ],
        price_trend_score=snapshot["price_trend_score"],
        volume_confirmation_score=snapshot["volume_confirmation_score"],
        candle_structure_score=snapshot["candle_structure_score"],
        breakdown_risk_score=snapshot["breakdown_risk_score"],
        rebound_quality_score=snapshot["rebound_quality_score"],
        selling_pressure_score=snapshot["selling_pressure_score"],
        metric_self_direction=direction,
        metric_self_score=metric_score,
        module_composite_score=module_composite_score,
        module_composite_direction=module_composite_direction,
        module_composite_state=snapshot["trend_state"],
        kline_composite_contribution=kline_composite_contribution,
        kline_trend_state=snapshot["trend_state"],
        kline_confirmation_status=snapshot["confirmation_status"],
        volume_interpretation=snapshot["volume_interpretation"],
        candle_interpretation=snapshot["candle_interpretation"],
    )


def _kline_structure_snapshot(feature_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ret_1h = _lookup_current(feature_lookup, "btc_return_1h") or 0.0
    ret_4h = _lookup_current(feature_lookup, "btc_return_4h") or 0.0
    ret_24h = _lookup_current(feature_lookup, "btc_return_24h") or 0.0
    drawdown_24h = _lookup_current(feature_lookup, "btc_drawdown_24h") or 0.0
    close_position = _lookup_current(feature_lookup, "btc_close_position_1h")
    close_position = 0.5 if close_position is None else _clamp(close_position)
    body_pct = _lookup_current(feature_lookup, "btc_candle_body_pct_1h") or 0.0
    upper_wick = _lookup_current(feature_lookup, "btc_upper_wick_ratio_1h") or 0.0
    lower_wick = _lookup_current(feature_lookup, "btc_lower_wick_ratio_1h") or 0.0
    volume_zscore = _lookup_current(feature_lookup, "btc_volume_zscore_1h") or 0.0
    breakdown = (_lookup_current(feature_lookup, "btc_breakdown_24h_low") or 0.0) >= 0.5
    breakout = (_lookup_current(feature_lookup, "btc_breakout_24h_high") or 0.0) >= 0.5
    volume_strength = _clamp((volume_zscore - 1.0) / 2.0) if volume_zscore > 1.0 else 0.0
    price_trend_score = _clamp(ret_1h / 0.02, -1.0, 1.0) * 0.55
    price_trend_score += _clamp(ret_4h / 0.04, -1.0, 1.0) * 0.25
    price_trend_score += _clamp(ret_24h / 0.08, -1.0, 1.0) * 0.20
    price_trend_score = round(_clamp(price_trend_score, -1.0, 1.0), 4)
    volume_confirmation_score = round(
        _clamp((1.0 if ret_1h > 0 else -1.0 if ret_1h < 0 else 0.0) * volume_strength, -1.0, 1.0),
        4,
    )
    candle_structure_score = round(
        _clamp((close_position - 0.5) * 2.0 + lower_wick * 0.35 - upper_wick * 0.35, -1.0, 1.0),
        4,
    )
    breakdown_risk_score = 0.0
    if breakdown and close_position < 0.4:
        breakdown_risk_score = -(0.7 + volume_strength * 0.3)
    elif breakout and close_position > 0.6 and upper_wick < 0.35:
        breakdown_risk_score = 0.45 + volume_strength * 0.25
    elif breakout and upper_wick > 0.45 and close_position < 0.5:
        breakdown_risk_score = -0.55
    rebound_quality_score = _clamp(max(ret_1h, 0.0) / 0.01, 0.0, 1.0) * _clamp(
        (close_position - 0.45) / 0.35, 0.0, 1.0
    )
    if ret_24h < -0.03 and volume_zscore < 1.0:
        rebound_quality_score *= 0.35
    selling_pressure_score = _clamp(max(-ret_1h, 0.0) / 0.015, 0.0, 1.0) * _clamp(
        (0.55 - close_position) / 0.35, 0.0, 1.0
    ) * max(volume_strength, 0.35 if ret_1h < 0 else 0.0)
    trend_state = "neutral_wait_confirm"
    if breakdown and close_position < 0.4:
        trend_state = "breakdown_risk"
    if ret_1h < 0 and volume_zscore > 1.5 and close_position < 0.3:
        trend_state = "bearish_pressure"
    if ret_1h < 0 and volume_zscore > 1.5 and lower_wick > 0.45 and close_position > 0.45:
        trend_state = "bearish_but_absorbed"
    if ret_24h < -0.03 and ret_1h > 0 and volume_zscore < 1.0:
        trend_state = "rebound_unconfirmed"
    if breakout and upper_wick > 0.45 and close_position < 0.5:
        trend_state = "false_breakout_risk"
    if ret_1h > 0 and volume_zscore > 1.5 and close_position > 0.7:
        trend_state = "bullish_confirmation"

    volume_interpretation = "volume is a confirmation factor, not an independent bullish signal"
    if volume_zscore > 1.5 and ret_1h < 0:
        volume_interpretation = "volume spike confirms downside pressure"
    elif volume_zscore > 1.5 and ret_1h > 0:
        volume_interpretation = "volume spike confirms upside participation"
    elif volume_zscore < 1.0 and ret_1h > 0:
        volume_interpretation = "rebound volume is not yet confirmed"
    candle_interpretation = "close is mid-range; candle needs confirmation"
    if close_position < 0.3:
        candle_interpretation = "close near candle low signals seller control"
    elif close_position > 0.7:
        candle_interpretation = "close near candle high signals buyer control"
    elif lower_wick > 0.45:
        candle_interpretation = "long lower wick shows absorption, not a confirmed reversal"
    risk_score = _clamp(max(abs(min(breakdown_risk_score, 0.0)), selling_pressure_score, max(-drawdown_24h / 0.08, 0.0)))
    return {
        "ret_1h": ret_1h,
        "ret_4h": ret_4h,
        "ret_24h": ret_24h,
        "price_trend_score": round(price_trend_score, 4),
        "volume_confirmation_score": volume_confirmation_score,
        "candle_structure_score": candle_structure_score,
        "breakdown_risk_score": round(breakdown_risk_score, 4),
        "rebound_quality_score": round(rebound_quality_score, 4),
        "selling_pressure_score": round(selling_pressure_score, 4),
        "trend_state": trend_state,
        "confirmation_status": _kline_confirmation_status(trend_state),
        "volume_interpretation": volume_interpretation,
        "candle_interpretation": candle_interpretation,
        "risk_score": round(risk_score, 4),
    }


def _kline_metric_score(metric_id: str, weight: float, snapshot: dict[str, Any]) -> float:
    mapping = {
        "btc_return_1h": _clamp(float(snapshot["ret_1h"]) / 0.02, -1.0, 1.0),
        "btc_return_4h": _clamp(float(snapshot["ret_4h"]) / 0.04, -1.0, 1.0),
        "btc_return_24h": _clamp(float(snapshot["ret_24h"]) / 0.08, -1.0, 1.0),
        "btc_drawdown_24h": min(snapshot["breakdown_risk_score"], 0.0) or -snapshot["risk_score"] * 0.35,
        "btc_close_position_1h": snapshot["candle_structure_score"],
        "btc_candle_body_pct_1h": snapshot["candle_structure_score"] * 0.35,
        "btc_upper_wick_ratio_1h": min(snapshot["candle_structure_score"], 0.0),
        "btc_lower_wick_ratio_1h": snapshot["rebound_quality_score"] * 0.25
        if snapshot["trend_state"] == "bearish_but_absorbed"
        else 0.0,
        "btc_breakdown_24h_low": min(snapshot["breakdown_risk_score"], 0.0),
        "btc_breakout_24h_high": max(snapshot["breakdown_risk_score"], 0.0),
        "btc_rebound_quality_1h": snapshot["rebound_quality_score"] * 0.4,
        "btc_down_volume_pressure": -snapshot["selling_pressure_score"],
    }
    if snapshot["trend_state"] == "rebound_unconfirmed" and metric_id == "btc_rebound_quality_1h":
        return min(weight * 0.08, 0.01)
    if snapshot["trend_state"] == "bearish_pressure" and metric_id == "btc_rebound_quality_1h":
        return 0.0
    return round(weight * float(mapping.get(metric_id, 0.0)), 4)


def _kline_composite_contribution(metric_id: str, weight: float, snapshot: dict[str, Any]) -> float:
    mapping = {
        "btc_return_1h": snapshot["price_trend_score"],
        "btc_return_4h": snapshot["price_trend_score"] * 0.65,
        "btc_return_24h": snapshot["price_trend_score"] * 0.45,
        "btc_drawdown_24h": min(snapshot["breakdown_risk_score"], 0.0) or -snapshot["risk_score"] * 0.35,
        "btc_close_position_1h": snapshot["candle_structure_score"],
        "btc_candle_body_pct_1h": snapshot["candle_structure_score"] * 0.35,
        "btc_upper_wick_ratio_1h": min(snapshot["candle_structure_score"], 0.0),
        "btc_lower_wick_ratio_1h": snapshot["rebound_quality_score"] * 0.25
        if snapshot["trend_state"] == "bearish_but_absorbed"
        else 0.0,
        "btc_breakdown_24h_low": min(snapshot["breakdown_risk_score"], 0.0),
        "btc_breakout_24h_high": max(snapshot["breakdown_risk_score"], 0.0),
        "btc_rebound_quality_1h": snapshot["rebound_quality_score"] * 0.4,
        "btc_down_volume_pressure": -snapshot["selling_pressure_score"],
    }
    return round(weight * float(mapping.get(metric_id, 0.0)), 4)


def _kline_confirmation_status(trend_state: str) -> str:
    if trend_state in {"bullish_confirmation", "bearish_pressure"}:
        return "confirmed"
    if trend_state in {"bearish_but_absorbed", "rebound_unconfirmed"}:
        return "needs_next_candle"
    if trend_state in {"breakdown_risk", "false_breakout_risk"}:
        return "risk_active"
    return "waiting"


def _kline_reason(snapshot: dict[str, Any]) -> str:
    state = snapshot["trend_state"]
    messages = {
        "bullish_confirmation": "Price rose with strong volume and a high close, so the kline structure confirms upside participation.",
        "bearish_pressure": "Price fell on elevated volume and closed near the candle low, so volume confirms downside pressure rather than bullish demand.",
        "bearish_but_absorbed": "Price fell on high volume but left a long lower wick; selling was partly absorbed, yet reversal still needs confirmation.",
        "rebound_unconfirmed": "A small 1h rebound appears inside a weak 24h background without volume confirmation, so it is not a bullish reversal.",
        "breakdown_risk": "BTC closed below the prior 24h low area, which raises breakdown risk.",
        "false_breakout_risk": "BTC pushed above the prior 24h high but failed to hold it, leaving false-breakout risk.",
        "neutral_wait_confirm": "Kline structure does not yet show a confirmed directional setup.",
    }
    return messages.get(state, messages["neutral_wait_confirm"])


def _fund_flow_state(current: float, change: float | None) -> tuple[float, str]:
    if current < 0:
        if change is not None and change > 0:
            return _clamp(abs(change), 0.0, 1.0), "bearish_but_improving"
        if change is not None and change < 0:
            return -_clamp(abs(change), 0.0, 1.0), "bearish_and_worsening"
        return 0.0, "bearish_outflow"
    if change is not None and change < 0:
        return -_clamp(abs(change), 0.0, 1.0), "bullish_but_fading"
    if change is not None and change > 0:
        return _clamp(abs(change), 0.0, 1.0), "bullish_inflow_expanding"
    return 0.0, "bullish_inflow"


def _cost_basis_signal(metric_id: str, btc_price: float, basis: float, weight: float) -> dict[str, Any]:
    premium = (btc_price - basis) / basis if basis else 0.0
    if metric_id == "sth_cost_basis":
        if premium > 0.03:
            return {
                "direction": "bullish",
                "score": weight * 0.22,
                "rule": "semantic.cost_basis.price_relative.above_sth",
                "state": "above_sth_cost_basis",
                "risk": 0.15,
                "reason": "BTC is trading more than 3% above short-term holder cost basis, so short-term holders remain structurally in profit.",
            }
        if premium < -0.02:
            return {
                "direction": "bearish",
                "score": -weight * 0.28,
                "rule": "semantic.cost_basis.price_relative.below_sth",
                "state": "below_sth_cost_basis",
                "risk": 0.7,
                "reason": "BTC is more than 2% below short-term holder cost basis, increasing short-holder loss pressure.",
            }
        return {
            "direction": "neutral",
            "score": 0.0,
            "rule": "semantic.cost_basis.price_relative.sth_test",
            "state": "testing_sth_cost_basis",
            "risk": 0.45,
            "reason": "BTC is close to short-term holder cost basis, so this is a support/resistance test rather than a clean direction signal.",
        }
    if premium > 0.05:
        return {
            "direction": "bullish",
            "score": weight * 0.16,
            "rule": f"semantic.cost_basis.price_relative.above_{metric_id}",
            "state": f"above_{metric_id}",
            "risk": 0.18,
            "reason": f"BTC is trading comfortably above {metric_id}, keeping the broader cost-basis structure constructive.",
        }
    if premium < -0.03:
        return {
            "direction": "bearish",
            "score": -weight * 0.3,
            "rule": f"semantic.cost_basis.price_relative.below_{metric_id}",
            "state": f"below_{metric_id}",
            "risk": 0.75,
            "reason": f"BTC is below {metric_id}, which weakens the broader on-chain valuation structure.",
        }
    return {
        "direction": "neutral",
        "score": 0.0,
        "rule": f"semantic.cost_basis.price_relative.near_{metric_id}",
        "state": f"near_{metric_id}",
        "risk": 0.35,
        "reason": f"BTC is close to {metric_id}, so the metric is treated as a valuation context and confirmation zone.",
    }


def _semantic_override(
    metric_id: str,
    module_id: str,
    current: float | None,
    change: float | None,
    weight: float,
    feature: dict[str, Any],
    feature_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if module_id == "trade_structure_flow" and metric_id == "taker_buy_sell_ratio" and current is not None:
        aggressive_flow_state = _aggressive_flow_state(current)
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.trade_structure.aggressive_flow_context",
            (
                "Taker buy/sell ratio describes aggressive flow pressure and must be "
                "confirmed by price response before it can affect directional conviction."
            ),
            signal_type="confirmation_context",
            aggressive_flow_state=aggressive_flow_state,
            thresholds_used={
                "strong_buying_pressure": 1.30,
                "buying_pressure": 1.12,
                "mild_buy_pressure": 1.03,
                "neutral_lower": 0.97,
                "mild_sell_pressure": 0.88,
                "selling_pressure": 0.70,
            },
            component_metrics=[
                "taker_buy_sell_ratio",
                "btc_return_5m",
                "btc_return_15m",
                "btc_close_position_5m",
                "btc_close_position_15m",
            ],
        )
    if module_id == "kline_orderflow" and metric_id in KLINE_RAW_CONTEXT_METRICS:
        role_reason = {
            "btc_1h_volume": "成交量是量价结构确认因子，不能单独作为 bullish/bearish 方向指标。",
            "btc_1h_high": "1h high 只描述区间结构，必须结合 return、close position 和 volume z-score 解读。",
            "btc_1h_low": "1h low 只描述区间结构，必须结合 return、close position 和 volume z-score 解读。",
            "btc_1h_open": "1h open 是 K 线结构上下文，不直接参与方向评分。",
            "btc_1h_close": "1h close 是价格上下文，方向判断应由派生量价结构指标完成。",
        }.get(
            metric_id,
            "Kline/orderflow level is context only; direction requires price acceptance, VWAP and residual confirmation.",
        )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.kline.raw_context_only",
            role_reason,
            signal_type="context_signal",
            thresholds_used={"p3_c29_guard": "raw_ohlcv_not_direct_direction"},
            component_metrics=[metric_id],
            kline_confirmation_status="raw_context_only",
            volume_interpretation=(
                "Volume confirms price/candle structure; it does not create direction alone."
                if metric_id == "btc_1h_volume"
                else None
            ),
        )
    if module_id == "kline_orderflow" and metric_id in KLINE_DERIVED_METRICS:
        return _kline_orderflow_semantic(
            metric_id=metric_id,
            module_id=module_id,
            current=current,
            weight=weight,
            feature_lookup=feature_lookup,
        )
    if metric_id in EVENT_COUNTDOWN_METRICS and current is not None:
        risk = _event_risk_from_days(current)
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.event_countdown.risk_overlay",
            "Event countdown is treated as a risk overlay instead of a direct bullish or bearish signal.",
            signal_type="risk_signal",
            risk_score=risk,
            event_risk_score=risk,
            thresholds_used={"0_1d": 1.0, "1_3d": 0.7, "3_7d": 0.4, "7_14d": 0.2},
            component_metrics=[metric_id],
        )
    if metric_id in EVENT_COUNTDOWN_HOUR_METRICS and current is not None:
        risk = _event_risk_from_hours(current)
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.event_countdown_hours.risk_overlay",
            "Hour-level event countdown is treated as a trade-permission risk overlay, not a direct BTC direction signal.",
            signal_type="risk_signal",
            risk_score=risk,
            event_risk_score=risk,
            thresholds_used={"0_6h": 1.0, "6_24h": 0.7, "24_72h": 0.4, "72_168h": 0.2},
            component_metrics=[metric_id],
        )
    if metric_id in EVENT_SIGNED_DISTANCE_METRICS and current is not None:
        risk = _event_risk_from_days(current)
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.event_signed_distance.risk_overlay",
            "Signed event distance is used to lock risk and reduce confidence near major releases, not to force a price direction.",
            signal_type="risk_signal",
            risk_score=risk,
            event_risk_score=risk,
            thresholds_used={"0_1d": 1.0, "1_3d": 0.7, "3_7d": 0.4, "7_14d": 0.2},
            component_metrics=[metric_id],
        )
    if metric_id in {
        "fed_speech_risk",
        "fed_speech_scheduled_risk",
        "fed_speech_content_risk",
        "fed_speaker_weight",
        "fed_speech_hawkish_score",
        "fed_speech_dovish_score",
        "fomc_event_risk",
        "regulatory_event_score",
        "macro_surprise_score",
        "aggregate_macro_surprise",
    } and current is not None:
        risk = _clamp(abs(current), 0.0, 1.0)
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            f"semantic.{metric_id}.risk_overlay",
            "Policy and regulatory event metrics are risk overlays; they shape tone and confidence rather than directional score.",
            signal_type="risk_signal",
            risk_score=risk,
            event_risk_score=risk,
            thresholds_used={"risk_scale": "0_to_1"},
            component_metrics=[metric_id],
        )
    if metric_id == "next_fed_speech_hours_until" and current is not None:
        risk = _event_risk_from_hours(current)
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.next_fed_speech_hours_until.risk_overlay",
            "Fed speech timing is treated as a near-term event risk overlay, not a direct price direction.",
            signal_type="risk_signal",
            risk_score=risk,
            event_risk_score=risk,
            thresholds_used={"0_24h": 1.0, "24_72h": 0.7, "72_168h": 0.4, "168_336h": 0.2},
            component_metrics=[metric_id],
        )
    if metric_id in {"macro_surprise_score", "aggregate_macro_surprise"} and _near_zero(current):
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.macro_surprise.zero_neutral",
            "宏观惊喜为 0 表示本轮没有明确超预期冲击，默认中性观察，不贡献正负分。",
        )
    if metric_id in {"etf_net_flow", "etf_flow_7d"} and current is not None:
        scale = 250_000_000.0 if metric_id == "etf_net_flow" else 1_000_000_000.0
        magnitude = min(abs(current) / scale, 1.0)
        score = weight * max(magnitude, 0.05)
        momentum, flow_state = _fund_flow_state(current, change)
        flow_momentum_score = round(weight * momentum * 0.35, 4)
        thresholds = {
            "etf_net_flow_scale": 250_000_000.0,
            "etf_flow_7d_scale": 1_000_000_000.0,
            "momentum_source": "change_24h",
        }
        if current < 0:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -score,
                "semantic.etf_flow.absolute_negative",
                "ETF flow is net negative, so absolute institutional marginal demand is bearish; momentum is stored separately as pressure easing or worsening.",
                "If outflow momentum improves, describe it as bearish pressure easing rather than bullish demand.",
                signal_type="direction_signal",
                flow_direction_score=round(-score, 4),
                flow_momentum_score=flow_momentum_score,
                flow_state=flow_state,
                thresholds_used=thresholds,
                component_metrics=[metric_id],
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "bullish",
            score,
            "semantic.etf_flow.absolute_positive",
            "ETF flow is net positive, which supports spot BTC demand; momentum is stored separately to show whether inflow is expanding or fading.",
            signal_type="direction_signal",
            flow_direction_score=round(score, 4),
            flow_momentum_score=flow_momentum_score,
            flow_state=flow_state,
            thresholds_used=thresholds,
            component_metrics=[metric_id],
        )
    
    if metric_id == "mvrv_zscore" and current is not None:
        if current < 0.5:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.45,
                "semantic.mvrv.undervalued",
                "MVRV Z-Score 处于低估区，历史上更接近积累或修复环境。",
            )
        if current < 1.2:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.18,
                "semantic.mvrv.low_constructive",
                "MVRV Z-Score 仍处于偏低区间，未显示周期性过热，估值压力有限。",
            )
        if current < 3.5:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "neutral",
                0.0,
                "semantic.mvrv.mid_cycle",
                "MVRV Z-Score 处于中性区间，不能仅因边际上升判定为顶部风险。",
            )
        if current < 7.0:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.55,
                "semantic.mvrv.high_distribution",
                "MVRV Z-Score 进入偏高区，未实现利润较厚，分配风险上升。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "bearish",
            -weight,
            "semantic.mvrv.extreme_top_risk",
            "MVRV Z-Score 进入极端高位，周期性顶部和获利分配风险显著。",
        )
    if metric_id == "sopr" and current is not None:
        if current < 0.98:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.35,
                "semantic.sopr.loss_realization",
                "SOPR 明显低于 1，说明链上花费整体处于亏损实现，短线风险偏弱。",
            )
        if current <= 1.02:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "neutral",
                0.0,
                "semantic.sopr.breakeven_test",
                "SOPR 接近 1，代表市场处在盈亏平衡测试区，应作为卖压/支撑观察项。",
            )
        if current <= 1.08:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.2,
                "semantic.sopr.profitability_recovery",
                "SOPR 温和高于 1，说明链上重新进入盈利花费区，趋势修复但尚未过热。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "bearish",
            -weight * 0.45,
            "semantic.sopr.profit_taking_hot",
            "SOPR 持续高位意味着获利了结压力上升，需警惕分配。",
        )
    if metric_id == "nupl" and current is not None:
        if current < 0.25:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.35,
                "semantic.nupl.low_accumulation",
                "NUPL 偏低，市场未实现利润有限，更接近修复或积累状态。",
            )
        if current < 0.5:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "neutral",
                0.0,
                "semantic.nupl.optimism_neutral",
                "NUPL 处于温和盈利区，趋势健康但不构成单独方向信号。",
            )
        if current < 0.75:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.3,
                "semantic.nupl.belief_risk",
                "NUPL 进入较高盈利区，获利盘和分配风险开始上升。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "bearish",
            -weight * 0.7,
            "semantic.nupl.euphoria",
            "NUPL 进入狂热区，周期性过热风险较高。",
        )
    if metric_id in {"realized_price", "sth_cost_basis", "lth_cost_basis"} and current is not None:
        btc_price = _lookup_current(feature_lookup, "btc_price") or _lookup_current(feature_lookup, "btc_1h_close")
        if btc_price is not None:
            signal = _cost_basis_signal(metric_id, btc_price, current, weight)
            return _semantic_result(
                metric_id,
                module_id,
                current,
                signal["direction"],
                signal["score"],
                signal["rule"],
                signal["reason"],
                signal_type="regime_signal",
                risk_score=signal["risk"],
                valuation_state=signal["state"],
                thresholds_used={
                    "sth_above": 0.03,
                    "sth_below": -0.02,
                    "realized_lth_above": 0.05,
                    "realized_lth_below": -0.03,
                    "btc_price": btc_price,
                },
                component_metrics=[metric_id, "btc_price" if _lookup_current(feature_lookup, "btc_price") is not None else "btc_1h_close"],
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            f"semantic.{metric_id}.context_required",
            "Cost-basis metrics require BTC spot price context; without price context they remain valuation context only.",
            signal_type="context_signal",
            valuation_state="price_context_missing",
            component_metrics=[metric_id, "btc_price"],
        )
    if metric_id == "cap_real_usd" and current is not None:
        if change is not None and change > 0.01:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.12,
                "semantic.realized_cap.change_positive",
                "Realized cap is expanding, suggesting capital stored on-chain is increasing.",
                signal_type="regime_signal",
                valuation_state="realized_cap_expanding",
                thresholds_used={"positive_change": 0.01, "negative_change": -0.01},
                component_metrics=[metric_id],
            )
        if change is not None and change < -0.01:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.12,
                "semantic.realized_cap.change_negative",
                "Realized cap is contracting, suggesting on-chain capital base is weakening.",
                signal_type="regime_signal",
                valuation_state="realized_cap_contracting",
                thresholds_used={"positive_change": 0.01, "negative_change": -0.01},
                component_metrics=[metric_id],
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.realized_cap.context_only",
            "Realized cap level is useful context, but a flat change does not create a standalone direction score.",
            signal_type="context_signal",
            valuation_state="realized_cap_flat",
            thresholds_used={"positive_change": 0.01, "negative_change": -0.01},
            component_metrics=[metric_id],
        )
    
    if metric_id == "btc_funding_rate" and current is not None:
        price_change = _lookup_change(feature_lookup, "btc_price") or _lookup_change(feature_lookup, "btc_1h_close")
        oi_change = _lookup_change(feature_lookup, "btc_open_interest")
        if current > 0.0008:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight,
                "semantic.funding.overheated",
                "Funding is overheated, showing crowded long leverage and elevated liquidation risk.",
                signal_type="risk_signal",
                crowding_state="overheated_long_crowding",
                leverage_risk_score=0.95,
                funding_state="funding_extreme",
                crowding_signal="long_crowding",
                direction_contribution="mild_pressure",
                trend_confirmation="unconfirmed",
                thresholds_used={"overheated": 0.0008, "elevated": 0.0003, "negative_squeeze": -0.0002},
                component_metrics=[metric_id],
            )
        if current > 0.0003:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.45,
                "semantic.funding.elevated",
                "Funding is elevated but not extreme, so long leverage pressure is bearish with limited strength.",
                signal_type="risk_signal",
                crowding_state="elevated_long_crowding",
                leverage_risk_score=0.65,
                funding_state="funding_elevated",
                crowding_signal="long_crowding",
                direction_contribution="mild_pressure",
                trend_confirmation="unconfirmed",
                thresholds_used={"overheated": 0.0008, "elevated": 0.0003, "negative_squeeze": -0.0002},
                component_metrics=[metric_id],
            )
        if price_change is not None and oi_change is not None:
            if price_change > 0.005 and oi_change > 0.005 and abs(current) <= 0.0003:
                return _semantic_result(
                    metric_id,
                    module_id,
                    current,
                    "bullish",
                    weight * 0.12,
                    "semantic.funding.price_oi_healthy_trend",
                    "Price and open interest are rising while funding remains mild, confirming healthier trend participation rather than overheated leverage.",
                    signal_type="direction_signal",
                    crowding_state="trend_confirmed_new_longs",
                    leverage_risk_score=0.25,
                    derivatives_confirmation_score=0.35,
                    funding_state="funding_mild",
                    crowding_signal="not_hot",
                    direction_contribution="mild_support",
                    trend_confirmation="confirmed",
                    thresholds_used={"price_change_up": 0.005, "oi_change_up": 0.005, "funding_mild_abs_max": 0.0003},
                    component_metrics=[metric_id, "btc_open_interest", "btc_price"],
                )
            if price_change < -0.005 and oi_change > 0.005 and current > 0:
                return _semantic_result(
                    metric_id,
                    module_id,
                    current,
                    "bearish",
                    -weight * 0.25,
                    "semantic.funding.price_down_oi_up_long_crowding",
                    "Price is falling while open interest rises and funding is positive, indicating long crowding into downside pressure.",
                    signal_type="risk_signal",
                    crowding_state="long_crowding_downside",
                    leverage_risk_score=0.75,
                    derivatives_confirmation_score=-0.35,
                    funding_state=_funding_state_from_value(current),
                    crowding_signal="long_crowding",
                    direction_contribution="mild_pressure",
                    trend_confirmation="unconfirmed",
                    thresholds_used={"price_change_down": -0.005, "oi_change_up": 0.005, "funding_positive": 0},
                    component_metrics=[metric_id, "btc_open_interest", "btc_price"],
                )
        if current < -0.0002:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.35,
                "semantic.funding.negative_squeeze",
                "Funding is meaningfully negative, leaving room for a short-squeeze style recovery.",
                signal_type="risk_signal",
                crowding_state="short_crowding_reversal_risk",
                leverage_risk_score=0.45,
                funding_state="funding_negative",
                crowding_signal="short_crowding",
                direction_contribution="mild_support",
                trend_confirmation="unconfirmed",
                thresholds_used={"negative_squeeze": -0.0002},
                component_metrics=[metric_id],
            )
        score = weight * 0.12 if change is not None and change < 0 else 0.0
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            score,
            "semantic.funding.normalized",
            "Funding is mild; it only contributes if marginal leverage heat is cooling.",
            signal_type="risk_signal",
            crowding_state="funding_mild",
            leverage_risk_score=0.2,
            funding_state="funding_mild",
            crowding_signal="not_hot",
            direction_contribution="mild_support" if score > 0 else "neutral",
            trend_confirmation="unconfirmed",
            thresholds_used={"overheated": 0.0008, "elevated": 0.0003, "negative_squeeze": -0.0002},
            component_metrics=[metric_id],
        )
    if metric_id == "btc_open_interest":
        price_change = _lookup_change(feature_lookup, "btc_price") or _lookup_change(feature_lookup, "btc_1h_close")
        funding = _lookup_current(feature_lookup, "btc_funding_rate")
        if change is not None and price_change is not None:
            if price_change > 0.005 and change > 0.005 and (funding is None or abs(funding) <= 0.0003):
                return _semantic_result(
                    metric_id,
                    module_id,
                    current,
                    "bullish",
                    weight * 0.35,
                    "semantic.oi.price_up_oi_up_funding_mild",
                    "Price and open interest are rising while funding is mild, suggesting new trend participation.",
                    signal_type="direction_signal",
                    crowding_state="trend_confirmed_new_longs",
                    leverage_risk_score=0.25,
                    derivatives_confirmation_score=0.35,
                    oi_state="oi_rising",
                    oi_confirmation="confirms_trend",
                    oi_trend_signal="bullish_confirmed",
                    thresholds_used={"price_change_up": 0.005, "oi_change_up": 0.005, "funding_mild_abs_max": 0.0003},
                    component_metrics=[metric_id, "btc_price", "btc_funding_rate"],
                )
            if price_change > 0.005 and change < -0.005:
                return _semantic_result(
                    metric_id,
                    module_id,
                    current,
                    "bullish",
                    weight * 0.15,
                    "semantic.oi.price_up_oi_down_short_covering",
                    "Price is rising while open interest falls, which is consistent with short covering and a lighter but less durable bullish impulse.",
                    signal_type="direction_signal",
                    crowding_state="short_covering",
                    leverage_risk_score=0.2,
                    derivatives_confirmation_score=0.15,
                    oi_state="oi_falling",
                    oi_confirmation="confirms_trend",
                    oi_trend_signal="bullish_confirmed",
                    thresholds_used={"price_change_up": 0.005, "oi_change_down": -0.005},
                    component_metrics=[metric_id, "btc_price"],
                )
            if price_change < -0.005 and change > 0.005 and (funding or 0) > 0:
                return _semantic_result(
                    metric_id,
                    module_id,
                    current,
                    "bearish",
                    -weight * 0.45,
                    "semantic.oi.price_down_oi_up_positive_funding",
                    "Price is falling while open interest rises and funding is positive, indicating long crowding and higher downside liquidation risk.",
                    signal_type="risk_signal",
                    crowding_state="long_crowding_downside",
                    leverage_risk_score=0.8,
                    derivatives_confirmation_score=-0.45,
                    oi_state="oi_rising",
                    oi_confirmation="confirms_crowding",
                    oi_trend_signal="bearish_confirmed",
                    thresholds_used={"price_change_down": -0.005, "oi_change_up": 0.005, "funding_positive": 0},
                    component_metrics=[metric_id, "btc_price", "btc_funding_rate"],
                )
            if price_change < -0.005 and change < -0.005:
                return _semantic_result(
                    metric_id,
                    module_id,
                    current,
                    "bearish",
                    -weight * 0.15,
                    "semantic.oi.price_down_oi_down_deleveraging",
                    "Price and open interest are both falling, so downside is active but leverage is being cleared.",
                    signal_type="risk_signal",
                    crowding_state="deleveraging_selloff",
                    leverage_risk_score=0.35,
                    derivatives_confirmation_score=-0.15,
                    oi_state="oi_falling",
                    oi_confirmation="confirms_trend",
                    oi_trend_signal="bearish_confirmed",
                    thresholds_used={"price_change_down": -0.005, "oi_change_down": -0.005},
                    component_metrics=[metric_id, "btc_price"],
                )
        if change is None or abs(change) < 0.005:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "neutral",
                0.0,
                "semantic.oi.flat",
                "Open interest is flat, so it cannot independently confirm trend or crowding direction.",
                signal_type="risk_signal",
                crowding_state="oi_flat",
                leverage_risk_score=0.15,
                oi_state="oi_flat",
                oi_confirmation="none",
                oi_trend_signal="unconfirmed",
                thresholds_used={"flat_abs_change": 0.005},
                component_metrics=[metric_id],
            )
        if change > 0.03:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * min(change * 8, 1.0),
                "semantic.oi.leverage_build",
                "Open interest is rising quickly without enough price/funding confirmation, so leverage crowding risk increases.",
                signal_type="risk_signal",
                crowding_state="leverage_build_unconfirmed",
                leverage_risk_score=0.65,
                oi_state="oi_rising",
                oi_confirmation="confirms_crowding",
                oi_trend_signal="unconfirmed",
                thresholds_used={"fast_build": 0.03},
                component_metrics=[metric_id],
            )
        if change < -0.02:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * min(abs(change) * 5, 0.5),
                "semantic.oi.deleveraging",
                "Open interest is falling, showing leverage cleanup that can make later trend recovery healthier.",
                signal_type="risk_signal",
                crowding_state="deleveraging",
                leverage_risk_score=0.25,
                oi_state="oi_falling",
                oi_confirmation="none",
                oi_trend_signal="unconfirmed",
                thresholds_used={"deleveraging": -0.02},
                component_metrics=[metric_id],
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.oi.mild_change",
            "Open interest changed mildly and remains a microstructure watch item.",
            signal_type="risk_signal",
            crowding_state="oi_mild_change",
            leverage_risk_score=0.2,
            oi_state="oi_rising" if (change or 0) > 0 else "oi_falling" if (change or 0) < 0 else "oi_flat",
            oi_confirmation="none",
            oi_trend_signal="unconfirmed",
            thresholds_used={"flat_abs_change": 0.005, "fast_build": 0.03, "deleveraging": -0.02},
            component_metrics=[metric_id],
        )
    if metric_id in DERIVATIVES_LONG_SHORT_RATIO_METRICS and current is not None:
        signal = _positioning_signal_from_ratio(current)
        score, contribution = _positioning_directional_score(signal, weight)
        scope = (
            "global_account"
            if metric_id == "btc_global_long_short_account_ratio"
            else "top_account"
            if metric_id == "btc_top_long_short_account_ratio"
            else "top_position"
        )
        if signal in {"extreme_long", "long_skew"}:
            explanation = (
                "Long/short ratio is skewed to longs; this is positioning pressure, not direct trend confirmation."
            )
        elif signal in {"extreme_short", "short_skew"}:
            explanation = (
                "Long/short ratio is skewed to shorts; this can support short-squeeze risk when combined with funding and OI."
            )
        else:
            explanation = "Long/short ratio is balanced, so positioning does not confirm directional crowding."
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            score,
            "semantic.derivatives.long_short_positioning",
            explanation,
            signal_type="risk_signal",
            crowding_state=signal,
            leverage_risk_score=0.65 if signal.startswith("extreme") else 0.4 if signal != "balanced" else 0.15,
            positioning_signal=signal,
            crowding_contribution=contribution,
            positioning_scope=scope,
            trend_confirmation="unconfirmed",
            thresholds_used={
                "extreme_long": 2.0,
                "long_skew": 1.35,
                "short_skew": 0.75,
                "extreme_short": 0.5,
            },
            component_metrics=[metric_id, "btc_funding_rate", "btc_open_interest"],
        )
    
    if metric_id == "futures_basis" and current is not None:
        if current > 0.08:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.65,
                "semantic.basis.overheated",
                "期货基差过高，代表杠杆做多或套利拥挤，偏空。",
            )
        if current > 0.02:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "neutral",
                0.0,
                "semantic.basis.normal_contango",
                "期货处于正常升水，说明风险偏好存在但未过热。",
            )
        if current < -0.01:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.35,
                "semantic.basis.backwardation_stress",
                "期货贴水可能反映短线压力或避险需求，按轻度偏空处理。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.basis.flat",
            "期货基差接近零，未形成清晰方向贡献。",
        )
    if metric_id == "ofr_fsi" and current is not None:
        if current < -0.5:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * min(abs(current) / 3, 1.0),
                "semantic.ofr.low_stress",
                "OFR FSI 为负且压力较低，宏观金融压力对 BTC 的压制有限。",
            )
        if current > 0.5:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * min(abs(current) / 3, 1.0),
                "semantic.ofr.high_stress",
                "OFR FSI 为正且压力上升，代表金融压力偏高，对风险资产不利。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.ofr.neutral_stress",
            "OFR FSI 接近中性，未形成明确宏观压力方向。",
        )
    if metric_id == "vix" and current is not None:
        if current < 15:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.25,
                "semantic.vix.low_risk",
                "VIX 处于低波动区，对风险资产情绪偏友好。",
            )
        if current <= 22:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "neutral",
                0.0,
                "semantic.vix.normal",
                "VIX 处于常态区间，不能单独构成强方向信号。",
            )
        if current <= 30:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.45,
                "semantic.vix.elevated",
                "VIX 偏高，风险厌恶升温，对 BTC 偏空。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "bearish",
            -weight * 0.9,
            "semantic.vix.stress",
            "VIX 高位代表市场压力显著，风险资产承压。",
        )
    if (
        metric_id in {"treasury_2y", "treasury_10y", "treasury_30y", "real_yield_10y", "sofr"}
        and current is not None
    ):
        threshold = {
            "treasury_2y": 4.0,
            "treasury_10y": 4.2,
            "treasury_30y": 4.5,
            "real_yield_10y": 1.8,
            "sofr": 3.5,
        }[metric_id]
        if current >= threshold:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.45,
                f"semantic.{metric_id}.restrictive",
                "利率/真实利率处于偏高或限制性区间，折现率和美元现金收益率对 BTC 估值形成压力。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            f"semantic.{metric_id}.not_restrictive",
            "利率未处于明显限制性区间，单独方向贡献有限。",
        )
    if metric_id in {"options_iv", "options_rv"} and current is not None:
        if current > 70:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * 0.65,
                f"semantic.{metric_id}.vol_stress",
                "波动率处于高位，代表风险溢价和不确定性上升。",
            )
        if current < 35:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "neutral",
                0.0,
                f"semantic.{metric_id}.low_vol_watch",
                "波动率偏低代表风险溢价收敛，但也可能酝酿突破，作为观察项处理。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            f"semantic.{metric_id}.normal",
            "波动率处于常态区间，未形成单独方向信号。",
        )
    if metric_id == "put_call_ratio" and current is not None:
        if current > 1.2:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bearish",
                -weight * min((current - 1.0), 0.8),
                "semantic.put_call.protection_elevated",
                "Put/Call 比率偏高，说明保护性需求或下行担忧较强。",
            )
        if current < 0.7:
            return _semantic_result(
                metric_id,
                module_id,
                current,
                "bullish",
                weight * 0.2,
                "semantic.put_call.call_demand",
                "Put/Call 比率偏低，期权需求更偏向上行敞口。",
            )
        return _semantic_result(
            metric_id,
            module_id,
            current,
            "neutral",
            0.0,
            "semantic.put_call.normal",
            "Put/Call 比率处于常态区间，方向贡献有限。",
        )
    return None


def _semantic_result(
    metric_id: str,
    module_id: str,
    current: float | None,
    direction: str,
    score: float,
    rule_id: str,
    reason: str,
    warning: str | None = None,
    *,
    signal_type: str | None = None,
    risk_score: float | None = None,
    event_risk_score: float | None = None,
    flow_direction_score: float | None = None,
    flow_momentum_score: float | None = None,
    flow_state: str | None = None,
    aggressive_flow_state: str | None = None,
    crowding_state: str | None = None,
    leverage_risk_score: float | None = None,
    derivatives_confirmation_score: float | None = None,
    funding_state: str | None = None,
    crowding_signal: str | None = None,
    direction_contribution: str | None = None,
    trend_confirmation: str | None = None,
    oi_state: str | None = None,
    oi_confirmation: str | None = None,
    oi_trend_signal: str | None = None,
    positioning_signal: str | None = None,
    crowding_contribution: str | None = None,
    positioning_scope: str | None = None,
    valuation_state: str | None = None,
    price_trend_score: float | None = None,
    volume_confirmation_score: float | None = None,
    candle_structure_score: float | None = None,
    breakdown_risk_score: float | None = None,
    rebound_quality_score: float | None = None,
    selling_pressure_score: float | None = None,
    metric_self_direction: str | None = None,
    metric_self_score: float | None = None,
    module_composite_score: float | None = None,
    module_composite_direction: str | None = None,
    module_composite_state: str | None = None,
    kline_composite_contribution: float | None = None,
    kline_trend_state: str | None = None,
    kline_confirmation_status: str | None = None,
    price_response_state: str | None = None,
    price_response_confidence: float | None = None,
    flow_price_efficiency_state: str | None = None,
    price_response_source: str | None = None,
    volume_interpretation: str | None = None,
    candle_interpretation: str | None = None,
    thresholds_used: dict[str, Any] | None = None,
    component_metrics: list[str] | None = None,
) -> dict[str, Any]:
    if signal_type is None:
        signal_type = "direction_signal" if direction in {"bullish", "bearish"} else "regime_signal"
    result = {
        "metric_score": round(score, 4),
        "direction": direction,
        "semantic_rule_id": rule_id,
        "semantic_warning": warning,
        "metric_explanation": (
            f"{module_id} - {metric_id}: {reason} Current value is "
            f"{current if current is not None else 'unavailable'}; semantic direction is {direction}."
        ),
        "score_reason": (
            f"{reason} Rule {rule_id} produced metric_score={round(score, 4)}."
            + (f" Warning: {warning}" if warning else "")
        ),
        "signal_type": signal_type,
    }
    optional_fields = {
        "risk_score": risk_score,
        "event_risk_score": event_risk_score,
        "flow_direction_score": flow_direction_score,
        "flow_momentum_score": flow_momentum_score,
        "flow_state": flow_state,
        "aggressive_flow_state": aggressive_flow_state,
        "crowding_state": crowding_state,
        "leverage_risk_score": leverage_risk_score,
        "derivatives_confirmation_score": derivatives_confirmation_score,
        "funding_state": funding_state,
        "crowding_signal": crowding_signal,
        "direction_contribution": direction_contribution,
        "trend_confirmation": trend_confirmation,
        "oi_state": oi_state,
        "oi_confirmation": oi_confirmation,
        "oi_trend_signal": oi_trend_signal,
        "positioning_signal": positioning_signal,
        "crowding_contribution": crowding_contribution,
        "positioning_scope": positioning_scope,
        "valuation_state": valuation_state,
        "price_trend_score": price_trend_score,
        "volume_confirmation_score": volume_confirmation_score,
        "candle_structure_score": candle_structure_score,
        "breakdown_risk_score": breakdown_risk_score,
        "rebound_quality_score": rebound_quality_score,
        "selling_pressure_score": selling_pressure_score,
        "metric_self_direction": metric_self_direction,
        "metric_self_score": metric_self_score,
        "module_composite_score": module_composite_score,
        "module_composite_direction": module_composite_direction,
        "module_composite_state": module_composite_state,
        "kline_composite_contribution": kline_composite_contribution,
        "kline_trend_state": kline_trend_state,
        "kline_confirmation_status": kline_confirmation_status,
        "price_response_state": price_response_state,
        "price_response_confidence": price_response_confidence,
        "flow_price_efficiency_state": flow_price_efficiency_state,
        "price_response_source": price_response_source,
        "volume_interpretation": volume_interpretation,
        "candle_interpretation": candle_interpretation,
        "thresholds_used": thresholds_used,
        "component_metrics": component_metrics,
    }
    for key, value in optional_fields.items():
        if value is not None:
            result[key] = value
    return result


def _safe_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _near_zero(value: float | None, threshold: float = 1e-12) -> bool:
    return value is not None and abs(value) <= threshold


def _module_explanation(
    module_id: str,
    module_score: float,
    module_direction: str,
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> str:
    pos = ", ".join(item["metric_id"] for item in _top_scored_items(positive, True, 3)) or "无"
    neg = ", ".join(item["metric_id"] for item in _top_scored_items(negative, False, 3)) or "无"
    boundary = (
        "；不可用指标包括 " + ", ".join(item["metric_id"] for item in unavailable[:3])
        if unavailable
        else ""
    )
    return (
        f"{module_id} 板块总分为 {module_score}，方向为 {module_direction}。"
        f"主要正分来自 {pos}，主要负分来自 {neg}{boundary}。"
    )


def detect_anomalies(
    run_id: str | None = None,
    metric_ids: list[str] | None = None,
    limit: int = 120,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    run_id = run_id or _generate_p3_run_id()
    selected = metric_ids or list(KEY_METRICS)
    written = 0
    skipped: list[dict[str, Any]] = []
    with db.session() as session:
        for metric_id in selected:
            window = historical_window(
                metric_id,
                limit=limit,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
                db=db,
            )
            if not window or not window.get("source_id"):
                skipped.append({"metric_id": metric_id, "reason": "no_window"})
                continue
            rows = _metric_rows(session, metric_id, str(window["source_id"]), limit, run_mode)
            if len(rows) < 3:
                skipped.append({"metric_id": metric_id, "reason": "not_enough_samples"})
                continue
            anomaly = _anomaly_payload(metric_id, rows, window, collect_run_id)
            if not anomaly:
                continue
            session.add(
                schema.FeatureValue(
                    run_id=run_id,
                    module_id=ANOMALY_MODULE_ID,
                    feature_id=f"{metric_id}.anomaly",
                    value=anomaly["severity_score"],
                    metadata_json=anomaly,
                )
            )
            written += 1
    return {
        "run_id": run_id,
        "written": written,
        "skipped": skipped,
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "historical_fallback": historical_fallback,
    }


def detect_divergences(
    run_id: str | None = None,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    run_id = run_id or _generate_p3_run_id()
    specs = [
        ("price_vs_fund_flow", ("etf_net_flow", "etf_flow_7d", "stablecoin_supply")),
        ("price_vs_leverage", ("btc_funding_rate", "btc_open_interest", "futures_basis")),
        ("price_vs_macro", ("dxy_proxy", "vix", "sp500", "gold", "wti_oil")),
        ("price_vs_onchain", ("mvrv_zscore", "nupl", "sopr", "sth_cost_basis")),
    ]
    price = _window(
        "btc_price",
        db,
        run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
    ) or _window(
        "btc_1h_close",
        db,
        run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
    )
    if not price:
        return {"run_id": run_id, "written": 0, "skipped": [{"reason": "no_price_window"}]}

    written = 0
    skipped: list[dict[str, Any]] = []
    with db.session() as session:
        for divergence_type, metrics in specs:
            signals = [
                item
                for metric_id in metrics
                if (
                    item := _divergence_metric(
                        metric_id,
                        price,
                        db,
                        run_mode,
                        collect_run_id=collect_run_id,
                        historical_fallback=historical_fallback,
                    )
                )
                is not None
            ]
            if not signals:
                skipped.append({"type": divergence_type, "reason": "no_counter_metrics"})
                continue
            score = sum(item["score"] for item in signals)
            severity = _candidate_level(abs(score), max(item["quality"] for item in signals), False)
            payload = {
                "divergence_id": f"{divergence_type}-{run_id}",
                "type": divergence_type,
                "direction": "bearish_divergence" if score < 0 else "bullish_divergence",
                "severity_candidate": severity,
                "metric_id": price["metric_id"],
                "price_metric": price["metric_id"],
                "source_id": price.get("source_id"),
                "source_run_id": price.get("source_run_id"),
                "price_source_run_id": price.get("source_run_id"),
                "collect_run_id": collect_run_id,
                "feature_run_scope": _combined_feature_run_scope([price, *signals]),
                "current_run_has_value": price.get("current_run_has_value", False)
                and all(item.get("current_run_has_value") for item in signals),
                "fallback_age_seconds": max(
                    [item.get("fallback_age_seconds") or 0.0 for item in [price, *signals]] or [0.0]
                ),
                "fallback_reason": _combined_fallback_reason([price, *signals]),
                "same_run_coverage_score": _same_run_score([price, *signals]),
                "price_change": _window_change(price),
                "metrics": signals,
                "data_quality": {
                    "min_quality": min(item["quality"] for item in signals),
                    "conflict_count": sum(1 for item in signals if item["conflict"]),
                },
                "run_mode": run_mode,
                "non_production": run_mode != "live",
            }
            session.add(
                schema.FeatureValue(
                    run_id=run_id,
                    module_id=DIVERGENCE_MODULE_ID,
                    feature_id=f"{divergence_type}.divergence",
                    value=round(score, 4),
                    metadata_json=payload,
                )
            )
            written += 1
    return {
        "run_id": run_id,
        "written": written,
        "skipped": skipped,
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "historical_fallback": historical_fallback,
    }


def check_module_invalidations(
    run_id: str | None = None,
    run_mode: str = "live",
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    run_id = run_id or _generate_p3_run_id()
    latest_outputs = _module_outputs_for_run(db, run_id)
    written = 0
    with db.session() as session:
        for module in RADAR_MODULES:
            output = latest_outputs.get(module.module_id)
            for condition in ("data_quality", "source_conflict"):
                condition_id = f"{module.module_id}_{condition}_invalidation"
                _upsert_condition(
                    session,
                    condition_id=condition_id,
                    scope="module",
                    module_id=module.module_id,
                    description=f"{module.module_id} {condition} invalidation",
                    severity="medium",
                )
                status, distance, evidence = _module_condition_status(output, condition)
                session.add(
                    schema.InvalidationEvent(
                        condition_id=condition_id,
                        run_id=run_id,
                        status=status,
                        action=_module_action(status),
                        payload={
                            "scope": "module",
                            "module_id": module.module_id,
                            "trigger_distance": distance,
                            "evidence": evidence,
                            "reason_code": evidence.get("reason_code"),
                            "severity": evidence.get("severity"),
                            "affected_metrics": evidence.get("affected_metrics", []),
                            "direction_scope": evidence.get("module_signal", "unknown"),
                            "source_run_id": evidence.get("source_run_id"),
                            "quality_impact": evidence.get("quality_impact"),
                            "publish_impact": evidence.get("publish_impact"),
                            "run_mode": run_mode,
                            "non_production": run_mode != "live",
                        },
                    )
                )
                written += 1
    return {"run_id": run_id, "written": written, "run_mode": run_mode}


def check_global_invalidations(
    run_id: str | None = None,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    run_id = run_id or _generate_p3_run_id()
    specs = (
        ("bullish_state_invalidation", "global"),
        ("bearish_state_invalidation", "global"),
        ("data_quality_invalidation", "global"),
        ("event_state_invalidation", "global"),
        ("run_mode_integrity_invalidation", "global"),
    )
    written = 0
    run_mode_risk = _run_mode_risk(db, collect_run_id=collect_run_id)
    latest_outputs = _module_outputs_for_run(db, run_id)
    with db.session() as session:
        module_events = session.scalars(
            select(schema.InvalidationEvent)
            .where(schema.InvalidationEvent.run_id == run_id)
            .order_by(schema.InvalidationEvent.created_at.desc())
        ).all()
        triggered_modules = [event for event in module_events if event.status == "triggered"]
        near_modules = [event for event in module_events if event.status == "near_trigger"]
        data_quality = _latest_data_quality(session)
        event_risk = _event_risk_score(db, run_id=run_id)
        event_risk_details = _event_risk_details(db, run_id)
        for condition_id, scope in specs:
            _upsert_condition(
                session,
                condition_id=condition_id,
                scope=scope,
                module_id=None,
                description=f"{condition_id} global invalidation",
                severity="high",
            )
            status = _global_status(
                condition_id,
                triggered_modules,
                near_modules,
                data_quality,
                event_risk,
                run_mode_risk,
                latest_outputs,
            )
            session.add(
                schema.InvalidationEvent(
                    condition_id=condition_id,
                    run_id=run_id,
                    status=status,
                    action=_global_action(condition_id, status),
                    payload={
                        "scope": "global",
                        "triggered_module_count": len(triggered_modules),
                        "near_module_count": len(near_modules),
                        "data_quality": data_quality,
                        "event_risk": event_risk,
                        "event_risk_details": event_risk_details,
                        "run_mode_risk": run_mode_risk,
                        "collect_run_id": collect_run_id,
                        "reason_code": _global_reason_code(condition_id, status),
                        "severity": "high" if status == "triggered" else "medium",
                        "direction_scope": _global_direction_scope(condition_id),
                        "publish_impact": _global_action(condition_id, status),
                        "run_mode": run_mode,
                        "non_production": run_mode != "live",
                    },
                )
            )
            written += 1
    return {"run_id": run_id, "written": written, "run_mode": run_mode}


def detect_event_windows(
    run_id: str | None = None,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    run_id = run_id or _generate_p3_run_id()
    written = 0
    skipped: list[dict[str, Any]] = []
    with db.session() as session:
        for metric_id, event_type in EVENT_COUNTDOWN_METRICS.items():
            window = _window(
                metric_id,
                db,
                run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
            )
            if not window or window.get("current") is None:
                skipped.append({"event_type": event_type, "reason": "no_countdown"})
                continue
            days = float(window["current"])
            signed_window = _window(
                EVENT_SIGNED_DISTANCE_METRICS[metric_id],
                db,
                run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
            )
            signed_days = (
                float(signed_window["current"])
                if signed_window and signed_window.get("current") is not None
                else days
            )
            event_window, level, risk_lock = _event_window(signed_days)
            event_phase = _event_phase(signed_days)
            source_trace = _macro_event_source_trace(session, event_type, collect_run_id, run_mode)
            event_summary = _event_summary(
                event_type=event_type,
                window=event_window,
                level=level,
                risk_lock=risk_lock,
                days_until=days,
                signed_days=signed_days,
                event_phase=event_phase,
                run_id=run_id,
                run_mode=run_mode,
                db=db,
            )
            daily_watch = _daily_watch_payload(
                session=session,
                event_type=event_type,
                current_run_id=run_id,
                signed_days=signed_days,
                source_trace=source_trace,
                event_summary=event_summary,
            )
            payload = {
                "event_id": f"{event_type.lower()}-{run_id}",
                "event_type": event_type,
                "metric_id": metric_id,
                "signed_metric_id": EVENT_SIGNED_DISTANCE_METRICS[metric_id],
                "days_until": days,
                "signed_days": signed_days,
                "event_phase": event_phase,
                "window": event_window,
                "alert_level": level,
                "risk_lock": risk_lock,
                "window_action": _event_window_action(event_window, risk_lock),
                "event_datetime": source_trace.get("event_datetime"),
                "event_name": source_trace.get("event_name"),
                "source_id": window.get("source_id"),
                "source_run_id": window.get("source_run_id"),
                "collect_run_id": collect_run_id,
                "feature_run_scope": window.get("feature_run_scope", "unspecified_history"),
                "current_run_has_value": window.get("current_run_has_value", False),
                "fallback_age_seconds": window.get("fallback_age_seconds"),
                "fallback_reason": window.get("fallback_reason"),
                "same_run_coverage_score": 1.0
                if window.get("feature_run_scope") == "current_run"
                else 0.0,
                "quality_score": window.get("effective_quality_score"),
                "action": [
                    "reduce_strong_direction_publish",
                    "require_post_event_review",
                ]
                if risk_lock
                else ["monitor"],
                "event_summary": event_summary,
                "daily_watch": daily_watch,
                "source_trace": source_trace,
                "run_mode": run_mode,
                "non_production": run_mode != "live",
            }
            session.add(
                schema.FeatureValue(
                    run_id=run_id,
                    module_id=EVENT_MODULE_ID,
                    feature_id=f"{metric_id}.event_window",
                    value=signed_days,
                    metadata_json=payload,
                )
            )
            written += 1
    return {
        "run_id": run_id,
        "written": written,
        "skipped": skipped,
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "historical_fallback": historical_fallback,
    }


def generate_algorithm_alerts(
    run_id: str | None = None,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    run_id = run_id or _generate_p3_run_id()
    candidates = _alert_candidates(run_id, run_mode, collect_run_id, db)
    written = 0
    updated = 0
    with db.session() as session:
        for candidate in candidates:
            alert_id = _stable_alert_id(candidate)
            existing = session.scalar(
                select(schema.AlgorithmAlert).where(schema.AlgorithmAlert.alert_id == alert_id)
            )
            cooldown_until = datetime.now(UTC) + timedelta(
                minutes=_cooldown_minutes(candidate["level"])
            )
            if existing is None:
                session.add(
                    schema.AlgorithmAlert(
                        alert_id=alert_id,
                        run_id=run_id,
                        level=candidate["level"],
                        state="active",
                        title=candidate["title"],
                        summary=candidate["summary"],
                        evidence_count=candidate["evidence_count"],
                        cooldown_until=cooldown_until,
                    )
                )
                event_type = "created"
                written += 1
            else:
                previous_level = existing.level
                existing.run_id = run_id
                existing.level = candidate["level"]
                existing.state = _lifecycle_state(previous_level, candidate["level"])
                existing.summary = candidate["summary"]
                existing.evidence_count = candidate["evidence_count"]
                existing.cooldown_until = cooldown_until
                event_type = existing.state
                updated += 1
            session.add(
                schema.AlertEvent(
                    alert_id=alert_id,
                    event_type=event_type,
                    payload=candidate,
                )
            )
    return {
        "run_id": run_id,
        "created": written,
        "updated": updated,
        "candidates": len(candidates),
        "run_mode": run_mode,
    }


def _metric_rows(
    session: Session,
    metric_id: str,
    source_id: str,
    limit: int,
    run_mode: str,
) -> list[schema.MetricValue]:
    filters = [
        schema.MetricValue.metric_id == metric_id,
        schema.MetricValue.source_id == source_id,
    ]
    if run_mode != "all":
        filters.append(schema.MetricValue.run_mode == run_mode)
    rows = session.scalars(
        select(schema.MetricValue)
        .where(*filters)
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def _anomaly_payload(
    metric_id: str,
    rows: list[schema.MetricValue],
    window: dict[str, Any],
    collect_run_id: str | None,
) -> dict[str, Any] | None:
    values = [float(row.value) for row in rows]
    current = values[-1]
    baseline = values[:-1]
    if len(baseline) < 2:
        return None
    mean = sum(baseline) / len(baseline)
    variance = sum((item - mean) ** 2 for item in baseline) / len(baseline)
    std = math.sqrt(variance)
    zscore = 0.0 if std == 0 else (current - mean) / std
    percentile = sum(1 for item in values if item <= current) / len(values)
    velocity = _safe_change(values[-2], current)
    quality = float(window.get("effective_quality_score") or window.get("quality_score") or 0.0)
    conflict = bool(window.get("conflict", {}).get("detected"))
    anomaly_type = _anomaly_type(zscore, percentile, velocity, window)
    if not anomaly_type:
        return None
    severity_score = min(max(abs(zscore) / 4, abs(velocity or 0) * 5, percentile), 1.0)
    return {
        "metric_id": metric_id,
        "source_id": window.get("source_id"),
        "source_run_id": window.get("source_run_id") or rows[-1].run_id,
        "collect_run_id": collect_run_id,
        "feature_run_scope": window.get("feature_run_scope", "unspecified_history"),
        "current_run_has_value": window.get("current_run_has_value", False),
        "fallback_age_seconds": window.get("fallback_age_seconds"),
        "fallback_reason": window.get("fallback_reason"),
        "same_run_coverage_score": 1.0 if window.get("feature_run_scope") == "current_run" else 0.0,
        "anomaly_type": anomaly_type,
        "severity": _candidate_level(severity_score, quality, conflict),
        "severity_score": round(severity_score, 4),
        "zscore": round(zscore, 4),
        "percentile": round(percentile, 4),
        "velocity": velocity,
        "freshness_status": window.get("freshness_status"),
        "collection_freshness_status": window.get("collection_freshness_status"),
        "quality_score": quality,
        "source_conflict_present": conflict,
        "run_mode": window.get("run_mode", "live"),
        "non_production": window.get("run_mode", "live") != "live",
        "evidence": {
            "current": current,
            "baseline_mean": mean,
            "sample_count": len(values),
            "selected_reason": window.get("selected_reason"),
            "conflict": window.get("conflict"),
        },
    }


def _anomaly_type(
    zscore: float,
    percentile: float,
    velocity: float | None,
    window: dict[str, Any],
) -> str | None:
    if window.get("collection_freshness_status") == "expired":
        return "freshness_anomaly"
    if abs(zscore) >= 1.5:
        return "zscore_spike"
    if percentile >= 0.9 or percentile <= 0.1:
        return "percentile_extreme"
    if velocity is not None and abs(velocity) >= 0.03:
        return "velocity_shock"
    return None


def _divergence_metric(
    metric_id: str,
    price: dict[str, Any],
    db: Database,
    run_mode: str,
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
) -> dict[str, Any] | None:
    other = _window(
        metric_id,
        db,
        run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
    )
    if not other:
        return None
    price_change = _window_change(price)
    other_change = _window_change(other)
    if price_change is None or other_change is None:
        return None
    score = 0.0
    if metric_id in {"btc_funding_rate", "btc_open_interest", "futures_basis"}:
        if price_change >= -0.01 and other_change > 0:
            score = -min(abs(other_change) * 5 + abs(price_change), 1.0)
    elif metric_id in {"dxy_proxy", "vix", "wti_oil"}:
        if price_change > 0 and other_change > 0:
            score = -min(abs(other_change) * 4, 1.0)
    elif metric_id in {"sp500", "etf_net_flow", "etf_flow_7d", "stablecoin_supply"}:
        if other_change > 0 and price_change <= 0:
            score = min(abs(other_change) * 4, 1.0)
    elif metric_id in {"mvrv_zscore", "nupl", "sopr", "sth_cost_basis"}:
        if price_change < 0 and other_change < 0:
            score = -min(abs(other_change) * 4 + abs(price_change), 1.0)
    if score == 0:
        return None
    return {
        "metric_id": metric_id,
        "source_id": other.get("source_id"),
        "source_run_id": other.get("source_run_id"),
        "collect_run_id": collect_run_id,
        "feature_run_scope": other.get("feature_run_scope", "unspecified_history"),
        "current_run_has_value": other.get("current_run_has_value", False),
        "fallback_age_seconds": other.get("fallback_age_seconds"),
        "fallback_reason": other.get("fallback_reason"),
        "same_run_coverage_score": 1.0 if other.get("feature_run_scope") == "current_run" else 0.0,
        "change": other_change,
        "score": round(score, 4),
        "quality": float(other.get("effective_quality_score") or other.get("quality_score") or 0.0),
        "conflict": bool(other.get("conflict", {}).get("detected")),
    }


def _module_condition_status(
    output: dict[str, Any] | None,
    condition: str,
) -> tuple[str, float, dict[str, Any]]:
    if output is None:
        return (
            "near_trigger",
            0.65,
            {
                "reason": "missing_module_output",
                "reason_code": "missing_module_output",
                "affected_metrics": [],
                "severity": "medium",
                "quality_impact": "reduce_confidence",
                "publish_impact": "reduce_confidence",
            },
        )
    invalidation = output.get("invalidation_signals", {})
    common = {
        "module_signal": output.get("signal"),
        "module_strength": output.get("strength"),
        "module_confidence": output.get("confidence"),
        "provider_required_metrics": invalidation.get("provider_required_metrics", []),
        "context_unavailable_metrics": invalidation.get("context_unavailable_metrics", []),
        "source_run_id": output.get("run_id"),
        "collect_run_id": output.get("collect_run_id"),
        "historical_fallback": output.get("historical_fallback"),
    }
    if condition == "data_quality":
        quality = output.get("data_quality")
        features = output.get("features", [])
        fallback_metrics = [
            item.get("metric_id")
            for item in features
            if item.get("feature_run_scope") == "historical_fallback"
        ]
        quality_detail = output.get("evidence_summary", {}).get("quality_explanation", {})
        same_run_coverage = float(quality_detail.get("same_run_coverage_score") or 1.0)
        expired_metrics = invalidation.get("expired_metrics", [])
        stale_metrics = invalidation.get("stale_metrics", [])
        business_lagging = invalidation.get("business_lagging_metrics", [])
        missing_metrics = invalidation.get("missing_metrics", [])
        if same_run_coverage < 0.5:
            return (
                "triggered",
                1.0,
                {
                    **common,
                    "data_quality": quality,
                    "same_run_coverage_score": same_run_coverage,
                    "historical_fallback_feature_count": len(fallback_metrics),
                    "historical_fallback_metrics": fallback_metrics,
                    "reason_code": "low_same_run_coverage",
                    "affected_metrics": fallback_metrics,
                    "severity": "high",
                    "quality_impact": "downgrade_module_signal",
                    "publish_impact": "block_critical_publish",
                },
            )
        if same_run_coverage < 0.8 or fallback_metrics:
            return (
                "near_trigger",
                0.8,
                {
                    **common,
                    "data_quality": quality,
                    "same_run_coverage_score": same_run_coverage,
                    "historical_fallback_feature_count": len(fallback_metrics),
                    "historical_fallback_metrics": fallback_metrics,
                    "reason_code": "historical_fallback_dependency",
                    "affected_metrics": fallback_metrics,
                    "severity": "medium",
                    "quality_impact": "reduce_confidence",
                    "publish_impact": "reduce_confidence",
                },
            )
        if quality == "low" or expired_metrics:
            return (
                "triggered",
                1.0,
                {
                    **common,
                    "data_quality": quality,
                    "expired_metrics": expired_metrics,
                    "stale_metrics": stale_metrics,
                    "business_lagging_metrics": business_lagging,
                    "missing_metrics": missing_metrics,
                    "reason_code": "expired_or_low_quality",
                    "affected_metrics": expired_metrics or missing_metrics,
                    "severity": "high",
                    "quality_impact": "downgrade_module_signal",
                    "publish_impact": "downgrade_module_signal",
                },
            )
        if stale_metrics or business_lagging or missing_metrics:
            affected = stale_metrics or business_lagging or missing_metrics
            return (
                "near_trigger",
                0.75,
                {
                    **common,
                    "data_quality": quality,
                    "stale_metrics": stale_metrics,
                    "business_lagging_metrics": business_lagging,
                    "missing_metrics": missing_metrics,
                    "reason_code": _data_quality_reason(
                        stale_metrics,
                        business_lagging,
                        missing_metrics,
                    ),
                    "affected_metrics": affected,
                    "severity": "medium",
                    "quality_impact": "reduce_confidence",
                    "publish_impact": "reduce_confidence",
                },
            )
        if quality == "medium" or invalidation.get("low_coverage"):
            return (
                "near_trigger",
                0.7,
                {
                    **common,
                    "data_quality": quality,
                    "low_coverage": bool(invalidation.get("low_coverage")),
                    "reason_code": "medium_quality_or_low_coverage",
                    "affected_metrics": missing_metrics,
                    "severity": "medium",
                    "quality_impact": "reduce_confidence",
                    "publish_impact": "reduce_confidence",
                },
            )
        return (
            "not_triggered",
            0.2,
            {
                **common,
                "data_quality": quality,
                "reason_code": "quality_ok",
                "affected_metrics": [],
                "severity": "info",
                "quality_impact": "none",
                "publish_impact": "monitor",
            },
        )
    conflicts = output.get("conflicting_evidence", {}).get("source_conflicts", [])
    suppressed = _suppressed_conflicts(output)
    if conflicts:
        return (
            "triggered",
            min(1.0, 0.6 + len(conflicts) * 0.2),
            {
                **common,
                "source_conflicts": conflicts,
                "suppressed_conflicts": suppressed,
                "reason_code": "true_source_conflict",
                "affected_metrics": [
                    item.get("metric_id")
                    for item in conflicts
                    if isinstance(item, dict) and item.get("metric_id")
                ],
                "severity": "high",
                "quality_impact": "downgrade_module_signal",
                "publish_impact": "downgrade_module_signal",
            },
        )
    return (
        "not_triggered",
        0.1,
        {
            **common,
            "source_conflicts": [],
            "suppressed_conflicts": suppressed,
            "reason_code": "no_true_source_conflict",
            "affected_metrics": [],
            "severity": "info",
            "quality_impact": "none",
            "publish_impact": "monitor",
        },
    )


def _data_quality_reason(
    stale_metrics: list[str],
    business_lagging: list[str],
    missing_metrics: list[str],
) -> str:
    if stale_metrics:
        return "stale_core_metrics"
    if business_lagging:
        return "business_lagging_core_metrics"
    if missing_metrics:
        return "missing_core_metrics"
    return "quality_watch"


def _suppressed_conflicts(output: dict[str, Any]) -> list[dict[str, Any]]:
    suppressed: list[dict[str, Any]] = []
    for feature in output.get("features", []):
        conflict = feature.get("conflict") or {}
        suppressed.extend(conflict.get("suppressed_items") or [])
    return suppressed


def _upsert_condition(
    session: Session,
    condition_id: str,
    scope: str,
    module_id: str | None,
    description: str,
    severity: str,
) -> None:
    existing = session.scalar(
        select(schema.InvalidationCondition).where(
            schema.InvalidationCondition.condition_id == condition_id
        )
    )
    if existing is not None:
        return
    session.add(
        schema.InvalidationCondition(
            condition_id=condition_id,
            scope=scope,
            module_id=module_id,
            description=description,
            threshold_json={"version": 1},
            severity=severity,
        )
    )


def _alert_candidates(
    run_id: str,
    run_mode: str,
    collect_run_id: str | None,
    db: Database,
) -> list[dict[str, Any]]:
    run_mode_risk = _run_mode_risk(db, collect_run_id=collect_run_id)
    with db.session() as session:
        anomalies = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == ANOMALY_MODULE_ID,
            )
        ).all()
        divergences = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == DIVERGENCE_MODULE_ID,
            )
        ).all()
        invalidations = session.scalars(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == run_id,
                schema.InvalidationEvent.status.in_(["triggered", "near_trigger"]),
            )
        ).all()
        events = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == EVENT_MODULE_ID,
            )
        ).all()

    candidates: list[dict[str, Any]] = []
    evidence_count = len(anomalies) + len(divergences) + len(invalidations)
    if evidence_count:
        highest = _highest_level(
            [item.metadata_json.get("severity", "info") for item in anomalies]
            + [item.metadata_json.get("severity_candidate", "info") for item in divergences]
            + [_invalidation_level(item.status) for item in invalidations]
        )
        level = _cap_level(highest, evidence_count)
        critical_blocked_by: list[str] = []
        if level == "critical" and run_mode_risk["production_blocker"]:
            level = "warning"
            critical_blocked_by.append("run_mode_mixed_history")
        summary = (
            f"异常 {len(anomalies)} 项，背离 {len(divergences)} 项，反证 {len(invalidations)} 项。"
        )
        candidates.append(
            {
                "category": "market_algorithm",
                "level": level,
                "title": "P3 算法风险信号",
                "summary": summary,
                "evidence_count": evidence_count,
                "evidence_refs": _feature_refs(anomalies + divergences)
                + _invalidation_refs(invalidations),
                "run_mode": run_mode,
                "non_production": run_mode != "live",
                "critical_blocked_by": critical_blocked_by,
                "run_mode_risk": run_mode_risk,
            }
        )
    for event in events:
        payload = event.metadata_json
        if payload.get("alert_level") in {"watch", "warning", "critical"}:
            event_summary = payload.get("event_summary", {})
            daily_watch = payload.get("daily_watch", {})
            candidates.append(
                {
                    "category": f"event_{payload['event_type'].lower()}",
                    "level": payload["alert_level"],
                    "title": f"{payload['event_type']} 事件窗口 {payload['window']}",
                    "summary": event_summary.get("headline")
                    or (
                        f"{payload['event_type']} signed_days="
                        f"{payload.get('signed_days', payload['days_until'])}，"
                        f"risk_lock={payload['risk_lock']}，"
                        f"daily_watch={daily_watch.get('change_summary', 'n/a')}"
                    ),
                    "evidence_count": 1,
                    "evidence_refs": [payload],
                    "run_mode": run_mode,
                    "non_production": run_mode != "live",
                    "critical_blocked_by": [],
                }
            )
    return candidates


def _event_window(days: float) -> tuple[str, str, bool]:
    if days < -3:
        return "outside", "info", False
    if days < -1:
        return "T+3", "watch", False
    if days < 0:
        return "T+1", "watch", True
    if days <= 0.5:
        return "T-0", "warning", True
    if days <= 1:
        return "T-1", "warning", True
    if days <= 3:
        return "T-3", "watch", True
    if days <= 7:
        return "T-7", "info", False
    return "outside", "info", False


def _event_phase(signed_days: float) -> str:
    if signed_days < -0.5:
        return "post_event"
    if signed_days <= 0.5:
        return "event_day"
    return "pre_event"


def _event_window_action(window: str, risk_lock: bool) -> list[str]:
    actions = {
        "T-7": ["start_monitoring"],
        "T-3": ["reduce_direction_confidence"],
        "T-1": ["pre_event_risk_lock", "reduce_strong_direction_publish"],
        "T-0": ["event_day_risk_lock", "block_critical_publish"],
        "T+1": ["post_event_reaction_check", "require_post_event_review"],
        "T+3": ["post_event_review"],
    }.get(window, ["monitor"])
    if risk_lock and "reduce_strong_direction_publish" not in actions:
        actions.append("reduce_strong_direction_publish")
    return actions


def _macro_event_source_trace(
    session: Session,
    event_type: str,
    collect_run_id: str | None,
    run_mode: str,
) -> dict[str, Any]:
    query = select(schema.RawObservation).where(
        schema.RawObservation.source_id == "official-macro-event-calendar",
        schema.RawObservation.mode == run_mode,
    )
    if collect_run_id:
        current = session.scalar(
            query.where(schema.RawObservation.run_id == collect_run_id).order_by(
                schema.RawObservation.observed_at.desc()
            )
        )
        if current is not None:
            return _macro_event_trace_from_raw(current, event_type)
    row = session.scalar(query.order_by(schema.RawObservation.observed_at.desc()))
    return _macro_event_trace_from_raw(row, event_type) if row else {}


def _macro_event_trace_from_raw(
    row: schema.RawObservation,
    event_type: str,
) -> dict[str, Any]:
    payload = row.raw_payload or {}
    event_key = event_type.lower()
    now = row.observed_at if row.observed_at.tzinfo else row.observed_at.replace(tzinfo=UTC)
    events = [
        event
        for event in payload.get("events", [])
        if str(event.get("event_type", "")).lower() == event_key
    ]
    nearest = _nearest_raw_event(events, now)
    resolution = payload.get("source_resolution", {})
    source_resolution = resolution.get(event_key) or resolution.get("bls") or {}
    return {
        "raw_observation_id": row.id,
        "raw_run_id": row.run_id,
        "raw_payload_hash": row.payload_hash,
        "source_resolution": source_resolution,
        "source_resolution_status": source_resolution.get("status"),
        "fallback_used": bool(source_resolution.get("fallback_used")),
        "event_datetime": nearest.get("datetime") if nearest else None,
        "event_name": nearest.get("name") if nearest else None,
        "event_source": nearest.get("source") if nearest else None,
    }


def _nearest_raw_event(events: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    parsed: list[tuple[float, dict[str, Any]]] = []
    for event in events:
        event_datetime = _parse_event_datetime(event.get("datetime"))
        if event_datetime is None:
            continue
        parsed.append((abs((event_datetime - now).total_seconds()), event))
    if not parsed:
        return None
    return sorted(parsed, key=lambda item: item[0])[0][1]


def _parse_event_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _event_summary(
    event_type: str,
    window: str,
    level: str,
    risk_lock: bool,
    days_until: float,
    signed_days: float,
    event_phase: str,
    run_id: str,
    run_mode: str,
    db: Database,
) -> dict[str, Any]:
    data_points = {
        metric_id: _event_data_point(metric_id, db, run_mode)
        for metric_id in (
            "macro_surprise_score",
            "aggregate_macro_surprise",
            "macro_surprise_event_count",
            "fed_speech_risk",
            "fed_speech_scheduled_risk",
            "fomc_event_risk",
            "fomc_blackout_active",
        )
    }
    event_policy = _event_policy_snapshot(db, run_id)
    publish_impact = _publish_impact(window, risk_lock, data_points)
    return {
        "headline": (
            f"{event_type} {window} {event_phase}: "
            f"signed_days={round(signed_days, 2)}, publish_impact={publish_impact}"
        ),
        "data_points": data_points,
        "event_policy_signal": event_policy.get("signal"),
        "event_policy_confidence": event_policy.get("confidence"),
        "interpretation": {
            "risk_direction": _event_risk_direction(data_points, risk_lock),
            "confidence_impact": (
                "reduce_confidence" if window in {"T-3", "T-1", "T-0", "T+1"} else "monitor"
            ),
            "publish_impact": publish_impact,
        },
        "actions": _event_window_action(window, risk_lock),
        "days_until": days_until,
        "signed_days": signed_days,
        "event_phase": event_phase,
        "alert_level": level,
        "risk_lock": risk_lock,
    }


def _event_data_point(metric_id: str, db: Database, run_mode: str) -> dict[str, Any]:
    window = _window(metric_id, db, run_mode=run_mode, historical_fallback=True)
    if not window:
        return {"available": False}
    return {
        "available": window.get("current") is not None,
        "value": window.get("current"),
        "source_id": window.get("source_id"),
        "source_run_id": window.get("source_run_id"),
        "feature_run_scope": window.get("feature_run_scope"),
        "quality_score": window.get("effective_quality_score"),
    }


def _event_policy_snapshot(db: Database, run_id: str) -> dict[str, Any]:
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == run_id,
                schema.ModuleJsonOutput.module_id == "event_policy",
            )
        )
    return row.payload if row else {}


def _publish_impact(
    window: str,
    risk_lock: bool,
    data_points: dict[str, dict[str, Any]],
) -> str:
    macro_risk = max(
        abs(float(item.get("value") or 0))
        for key, item in data_points.items()
        if key
        in {
            "macro_surprise_score",
            "aggregate_macro_surprise",
            "fed_speech_risk",
            "fomc_event_risk",
        }
    )
    if window == "T-0" and macro_risk >= 0.75:
        return "block_critical_publish"
    if risk_lock or window in {"T-1", "T-0", "T+1"}:
        return "block_publish_strong_direction"
    if window in {"T-7", "T-3", "T+3"}:
        return "monitor_with_summary"
    return "monitor"


def _event_risk_direction(
    data_points: dict[str, dict[str, Any]],
    risk_lock: bool,
) -> str:
    if risk_lock:
        return "event_compression"
    fed_risk = float(data_points.get("fed_speech_risk", {}).get("value") or 0)
    macro_surprise = float(data_points.get("macro_surprise_score", {}).get("value") or 0)
    if max(abs(fed_risk), abs(macro_surprise)) >= 0.35:
        return "macro_policy_watch"
    return "neutral_watch"


def _daily_watch_payload(
    session: Session,
    event_type: str,
    current_run_id: str,
    signed_days: float,
    source_trace: dict[str, Any],
    event_summary: dict[str, Any],
) -> dict[str, Any]:
    active = -3 <= signed_days <= 7
    previous = _previous_event_feature(session, event_type, current_run_id)
    changed_fields: list[dict[str, Any]] = []
    if previous is not None:
        previous_payload = previous.metadata_json or {}
        comparable = {
            "event_datetime": source_trace.get("event_datetime"),
            "signed_days": round(signed_days, 2),
            "source_resolution.status": source_trace.get("source_resolution_status"),
            "fallback_used": source_trace.get("fallback_used"),
            "macro_surprise_score": _summary_value(event_summary, "macro_surprise_score"),
            "aggregate_macro_surprise": _summary_value(event_summary, "aggregate_macro_surprise"),
            "macro_surprise_event_count": _summary_value(
                event_summary,
                "macro_surprise_event_count",
            ),
            "fed_speech_risk": _summary_value(event_summary, "fed_speech_risk"),
            "fed_speech_scheduled_risk": _summary_value(event_summary, "fed_speech_scheduled_risk"),
            "fomc_blackout_active": _summary_value(event_summary, "fomc_blackout_active"),
        }
        previous_summary = previous_payload.get("event_summary", {})
        previous_trace = previous_payload.get("source_trace", {})
        previous_values = {
            "event_datetime": previous_trace.get("event_datetime"),
            "signed_days": round(float(previous_payload.get("signed_days") or 0), 2),
            "source_resolution.status": previous_trace.get("source_resolution_status"),
            "fallback_used": previous_trace.get("fallback_used"),
            "macro_surprise_score": _summary_value(previous_summary, "macro_surprise_score"),
            "aggregate_macro_surprise": _summary_value(
                previous_summary,
                "aggregate_macro_surprise",
            ),
            "macro_surprise_event_count": _summary_value(
                previous_summary,
                "macro_surprise_event_count",
            ),
            "fed_speech_risk": _summary_value(previous_summary, "fed_speech_risk"),
            "fed_speech_scheduled_risk": _summary_value(
                previous_summary,
                "fed_speech_scheduled_risk",
            ),
            "fomc_blackout_active": _summary_value(previous_summary, "fomc_blackout_active"),
        }
        for field, current_value in comparable.items():
            previous_value = previous_values.get(field)
            if current_value != previous_value:
                changed_fields.append(
                    {"field": field, "previous": previous_value, "current": current_value}
                )
    return {
        "active": active,
        "watch_reason": "pre_event_monitoring" if signed_days >= 0 else "post_event_review",
        "previous_run_id": previous.run_id if previous else None,
        "current_run_id": current_run_id,
        "changed_fields": changed_fields,
        "change_summary": "changed" if changed_fields else "no_material_change",
    }


def _previous_event_feature(
    session: Session,
    event_type: str,
    current_run_id: str,
) -> schema.FeatureValue | None:
    return session.scalar(
        select(schema.FeatureValue)
        .where(
            schema.FeatureValue.module_id == EVENT_MODULE_ID,
            schema.FeatureValue.run_id != current_run_id,
            schema.FeatureValue.metadata_json["event_type"].as_string() == event_type,
        )
        .order_by(schema.FeatureValue.created_at.desc())
    )


def _summary_value(summary: dict[str, Any], metric_id: str) -> Any:
    return (summary.get("data_points", {}).get(metric_id) or {}).get("value")


def _window(
    metric_id: str,
    db: Database,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
) -> dict[str, Any] | None:
    return historical_window(
        metric_id,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )


def _combined_feature_run_scope(items: list[dict[str, Any]]) -> str:
    scopes = {str(item.get("feature_run_scope") or "missing") for item in items}
    if "historical_fallback" in scopes:
        return "historical_fallback"
    if scopes == {"current_run"}:
        return "current_run"
    if "provider_required" in scopes:
        return "provider_required"
    return "missing" if "missing" in scopes else "unspecified_history"


def _combined_fallback_reason(items: list[dict[str, Any]]) -> str | None:
    reasons = [str(item.get("fallback_reason")) for item in items if item.get("fallback_reason")]
    return ",".join(sorted(set(reasons))) if reasons else None


def _same_run_score(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    current = sum(1 for item in items if item.get("feature_run_scope") == "current_run")
    return round(current / len(items), 4)


def _window_change(window: dict[str, Any]) -> float | None:
    if window.get("change_24h") is not None:
        return float(window["change_24h"])
    current = window.get("current")
    previous = window.get("previous")
    if current is None or previous in {None, 0}:
        return None
    return (float(current) - float(previous)) / abs(float(previous))


def _safe_change(previous: float, current: float) -> float | None:
    if previous == 0:
        return None
    return (current - previous) / abs(previous)


def _candidate_level(score: float, quality: float, conflict: bool) -> str:
    if quality < 0.45:
        return "info"
    if quality < 0.6 or conflict:
        return "watch"
    if score >= 0.85 and quality >= 0.75:
        return "critical_candidate"
    if score >= 0.55:
        return "warning_candidate"
    return "watch"


def _module_outputs_for_run(db: Database, run_id: str) -> dict[str, dict[str, Any]]:
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.run_id == run_id)
            .order_by(schema.ModuleJsonOutput.created_at.desc())
        ).all()
    outputs: dict[str, dict[str, Any]] = {}
    for row in rows:
        outputs.setdefault(row.module_id, row.payload)
    return outputs


def _latest_data_quality(session: Session) -> dict[str, Any]:
    row = session.scalar(
        select(schema.DataQualitySnapshot).order_by(schema.DataQualitySnapshot.created_at.desc())
    )
    if row is None:
        return {"status": "unknown", "score": 0.0}
    return {"status": row.status, "score": row.score, "payload": row.payload}


def _event_risk_score(db: Database, run_id: str | None = None) -> float:
    scores = []
    for metric_id in ("macro_surprise_score", "fed_speech_risk", "fomc_event_risk"):
        window = _window(metric_id, db)
        if window and window.get("current") is not None:
            scores.append(abs(float(window["current"])))
    if run_id:
        for detail in _event_risk_details(db, run_id):
            scores.append(float(detail["risk_score"]))
    return max(scores) if scores else 0.0


def _event_risk_details(db: Database, run_id: str) -> list[dict[str, Any]]:
    with db.session() as session:
        rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == EVENT_MODULE_ID,
            )
        ).all()
    details: list[dict[str, Any]] = []
    for row in rows:
        payload = row.metadata_json or {}
        window = payload.get("window")
        risk_score = 0.0
        if payload.get("risk_lock"):
            risk_score = 0.7
        if window == "T-0":
            risk_score = max(risk_score, 0.8)
        elif window in {"T-1", "T+1"}:
            risk_score = max(risk_score, 0.7)
        elif window in {"T-3", "T-7", "T+3"}:
            risk_score = max(risk_score, 0.35)
        details.append(
            {
                "event_type": payload.get("event_type"),
                "window": window,
                "signed_days": payload.get("signed_days"),
                "risk_lock": payload.get("risk_lock"),
                "risk_score": risk_score,
                "publish_impact": payload.get("event_summary", {})
                .get("interpretation", {})
                .get("publish_impact"),
            }
        )
    return details


def _global_status(
    condition_id: str,
    triggered_modules: list[schema.InvalidationEvent],
    near_modules: list[schema.InvalidationEvent],
    data_quality: dict[str, Any],
    event_risk: float,
    run_mode_risk: dict[str, Any],
    latest_outputs: dict[str, dict[str, Any]],
) -> str:
    if condition_id == "run_mode_integrity_invalidation":
        if run_mode_risk["production_blocker"]:
            return "triggered"
        return "not_triggered"
    if condition_id == "data_quality_invalidation":
        if data_quality.get("status") == "critical":
            return "triggered"
        if data_quality.get("status") in {"warning", "unknown"}:
            return "near_trigger"
    if condition_id == "event_state_invalidation":
        if event_risk >= 0.75:
            return "triggered"
        if event_risk >= 0.35:
            return "near_trigger"
    if condition_id in {"bullish_state_invalidation", "bearish_state_invalidation"}:
        direction = "bearish" if condition_id == "bullish_state_invalidation" else "bullish"
        matched = _directional_invalidation_events(
            triggered_modules,
            near_modules,
            latest_outputs,
            direction,
        )
        triggered_count = sum(1 for item in matched if item.status == "triggered")
        if triggered_count >= 2:
            return "triggered"
        if triggered_count or len(matched) >= 2:
            return "near_trigger"
        return "not_triggered"
    if len(triggered_modules) >= 2:
        return "triggered"
    if triggered_modules or len(near_modules) >= 2:
        return "near_trigger"
    return "not_triggered"


def _directional_invalidation_events(
    triggered_modules: list[schema.InvalidationEvent],
    near_modules: list[schema.InvalidationEvent],
    latest_outputs: dict[str, dict[str, Any]],
    direction: str,
) -> list[schema.InvalidationEvent]:
    rows = triggered_modules + near_modules
    matched: list[schema.InvalidationEvent] = []
    for row in rows:
        module_id = row.payload.get("module_id")
        output = latest_outputs.get(module_id or "")
        signal = row.payload.get("evidence", {}).get("module_signal") or (
            output.get("signal") if output else None
        )
        if signal == direction:
            matched.append(row)
    return matched


def _module_action(status: str) -> str:
    return {
        "triggered": "downgrade_module_signal",
        "near_trigger": "reduce_confidence",
        "not_triggered": "monitor",
    }.get(status, "monitor")


def _global_action(condition_id: str, status: str) -> str:
    if status == "triggered":
        if condition_id == "run_mode_integrity_invalidation":
            return "block_critical_publish"
        if condition_id == "event_state_invalidation":
            return "trigger_run_once_review"
        return "force_llm_debate"
    if status == "near_trigger":
        return "block_publish_strong_direction"
    return "monitor"


def _global_reason_code(condition_id: str, status: str) -> str:
    if status == "not_triggered":
        return "global_condition_clear"
    return {
        "bullish_state_invalidation": "bearish_evidence_against_bullish_state",
        "bearish_state_invalidation": "bullish_evidence_against_bearish_state",
        "data_quality_invalidation": "global_data_quality_risk",
        "event_state_invalidation": "macro_event_risk",
        "run_mode_integrity_invalidation": "run_mode_mixed_history",
    }.get(condition_id, "global_invalidation")


def _global_direction_scope(condition_id: str) -> str:
    return {
        "bullish_state_invalidation": "bullish",
        "bearish_state_invalidation": "bearish",
        "data_quality_invalidation": "all",
        "event_state_invalidation": "all",
        "run_mode_integrity_invalidation": "all",
    }.get(condition_id, "all")


def _invalidation_level(status: str) -> str:
    return "warning" if status == "triggered" else "watch"


def _highest_level(levels: list[str]) -> str:
    rank = {
        "info": 0,
        "watch": 1,
        "warning_candidate": 2,
        "warning": 2,
        "critical_candidate": 3,
        "critical": 3,
    }
    reverse = {0: "info", 1: "watch", 2: "warning", 3: "critical"}
    return reverse[max((rank.get(level, 0) for level in levels), default=0)]


def _cap_level(level: str, evidence_count: int) -> str:
    if level == "critical" and evidence_count < 3:
        return "warning"
    if level == "warning" and evidence_count < 2:
        return "watch"
    return level


def _feature_refs(rows: list[schema.FeatureValue]) -> list[dict[str, Any]]:
    return [
        {
            "feature_id": row.feature_id,
            "module_id": row.module_id,
            "metric_id": row.metadata_json.get("metric_id"),
            "source_id": row.metadata_json.get("source_id"),
        }
        for row in rows
    ]


def _invalidation_refs(rows: list[schema.InvalidationEvent]) -> list[dict[str, Any]]:
    return [
        {
            "condition_id": row.condition_id,
            "status": row.status,
            "action": row.action,
            "module_id": row.payload.get("module_id"),
        }
        for row in rows
    ]


def _stable_alert_id(candidate: dict[str, Any]) -> str:
    return f"alert-{candidate['category']}"


def _run_mode_risk(db: Database, collect_run_id: str | None = None) -> dict[str, Any]:
    with db.session() as session:
        current_counts, current_mixed = _metric_run_mode_scope(session, collect_run_id)
        history_counts, history_mixed = _metric_run_mode_scope(session, None)
    current_blocker = bool(
        current_mixed
        or current_counts.get("mock", 0)
        or current_counts.get("test", 0)
        or current_counts.get("unknown", 0)
    )
    history_warning = bool(
        history_mixed
        or history_counts.get("mock", 0)
        or history_counts.get("test", 0)
        or history_counts.get("unknown", 0)
    )
    return {
        "scope": "current_run" if collect_run_id else "database_history",
        "collect_run_id": collect_run_id,
        "counts": current_counts,
        "mixed_metric_ids_count": len(current_mixed),
        "unknown_metric_values": current_counts.get("unknown", 0),
        "production_blocker": current_blocker,
        "current_run_counts": current_counts,
        "current_run_mixed_metric_ids": [metric_id for metric_id, _ in current_mixed],
        "current_run_mixed_metric_ids_count": len(current_mixed),
        "database_history_counts": history_counts,
        "database_history_mixed_metric_ids": [metric_id for metric_id, _ in history_mixed],
        "database_history_mixed_metric_ids_count": len(history_mixed),
        "history_contamination_warning": history_warning,
    }


def _metric_run_mode_scope(
    session: Session,
    collect_run_id: str | None,
) -> tuple[dict[str, int], list[Any]]:
    query = select(schema.MetricValue.run_mode, func.count())
    mixed_query = select(
        schema.MetricValue.metric_id,
        func.count(func.distinct(schema.MetricValue.run_mode)),
    )
    if collect_run_id:
        query = query.where(schema.MetricValue.run_id == collect_run_id)
        mixed_query = mixed_query.where(schema.MetricValue.run_id == collect_run_id)
    rows = session.execute(query.group_by(schema.MetricValue.run_mode)).all()
    counts = {str(mode or "unknown"): count for mode, count in rows}
    mixed = session.execute(
        mixed_query.group_by(schema.MetricValue.metric_id).having(
            func.count(func.distinct(schema.MetricValue.run_mode)) > 1
        )
    ).all()
    return counts, mixed


def _cooldown_minutes(level: str) -> int:
    return {"info": 30, "watch": 60, "warning": 120, "critical": 240}.get(level, 60)


def _lifecycle_state(previous_level: str, new_level: str) -> str:
    rank = {"info": 0, "watch": 1, "warning": 2, "critical": 3}
    if rank.get(new_level, 0) > rank.get(previous_level, 0):
        return "escalated"
    if rank.get(new_level, 0) < rank.get(previous_level, 0):
        return "downgraded"
    return "cooling"


def _generate_p3_run_id() -> str:
    return f"p3-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def p3_summary(db: Database = database) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        return {
            "feature_values": session.scalar(select(func.count()).select_from(schema.FeatureValue)),
            "algorithm_alerts": session.scalar(
                select(func.count()).select_from(schema.AlgorithmAlert)
            ),
            "alert_events": session.scalar(select(func.count()).select_from(schema.AlertEvent)),
            "invalidation_events": session.scalar(
                select(func.count()).select_from(schema.InvalidationEvent)
            ),
        }
