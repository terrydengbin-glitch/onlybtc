from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.sources.service import historical_window

BTC_DIRECT_TREND_EVIDENCE_MODULE_ID = "btc_direct_trend_evidence"
SCHEMA_VERSION = "p1.c75.direct_evidence.v1"


@dataclass(frozen=True)
class DirectMetricSpec:
    category: str
    feature_name: str
    metric_id: str
    cadence_group: str
    stale_after_sec: int
    source_id: str | None = None
    limit: int = 120
    value_scale: float = 1.0


DIRECT_METRICS: tuple[DirectMetricSpec, ...] = (
    DirectMetricSpec("price_structure", "btc_return_4h", "btc_return_4h", "fast_4h", 75 * 60),
    DirectMetricSpec("price_structure", "btc_return_24h", "btc_return_24h", "fast_1d", 75 * 60),
    DirectMetricSpec(
        "orderflow_acceptance",
        "taker_buy_sell_ratio",
        "taker_buy_sell_ratio",
        "fast_5m",
        30 * 60,
        source_id="binance-btcusdt-taker-buy-sell-ratio",
    ),
    DirectMetricSpec(
        "derivatives_positioning",
        "oi_impulse_z_15m",
        "oi_impulse_z_15m",
        "fast_15m",
        30 * 60,
    ),
    DirectMetricSpec(
        "derivatives_positioning",
        "oi_impulse_z_1h",
        "oi_impulse_z_1h",
        "fast_1h",
        75 * 60,
    ),
    DirectMetricSpec(
        "derivatives_positioning",
        "oi_impulse_z_4h",
        "oi_impulse_z_4h",
        "fast_4h",
        75 * 60,
    ),
    DirectMetricSpec(
        "derivatives_positioning",
        "funding_rate_8h_equiv_z",
        "funding_rate_8h_equiv_z",
        "funding_8h",
        10 * 60 * 60,
        source_id="binance-btcusdt-funding",
    ),
    DirectMetricSpec(
        "derivatives_positioning",
        "funding_acceleration_z_24h",
        "funding_acceleration_z_24h",
        "funding_8h",
        10 * 60 * 60,
        source_id="binance-btcusdt-funding",
    ),
    DirectMetricSpec(
        "derivatives_positioning",
        "liquidation_followthrough_score",
        "liquidation_followthrough_score",
        "fast_15m",
        30 * 60,
    ),
    DirectMetricSpec(
        "derivatives_positioning",
        "liquidation_absorption_score",
        "liquidation_absorption_score",
        "fast_15m",
        30 * 60,
    ),
    DirectMetricSpec(
        "btc_residual_cross_asset",
        "expected_return_24h",
        "btc_expected_return_24h",
        "slow_macro_daily",
        36 * 60 * 60,
    ),
    DirectMetricSpec(
        "btc_residual_cross_asset",
        "residual_24h",
        "btc_residual_24h",
        "slow_macro_daily",
        36 * 60 * 60,
    ),
    DirectMetricSpec(
        "btc_residual_cross_asset",
        "residual_z",
        "btc_residual_z_60d",
        "slow_macro_daily",
        36 * 60 * 60,
    ),
)


def build_btc_direct_trend_evidence(
    run_id: str | None = None,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = True,
    db: Database = database,
) -> dict[str, Any]:
    """Build P1-C75 direct trend evidence rows for the BTC 4H/1D mainline."""

    db.init_schema()
    run_id = run_id or _generate_run_id()
    derived_at = datetime.now(UTC)
    rows: list[schema.FeatureValue] = []
    skipped: list[dict[str, str]] = []

    with db.session() as session:
        session.execute(
            delete(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
            )
        )
        for spec in DIRECT_METRICS:
            window = _window(
                spec.metric_id,
                source_id=spec.source_id,
                limit=spec.limit,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
                db=db,
            )
            if window is None:
                skipped.append({"feature_name": spec.feature_name, "reason": "missing_window"})
                rows.append(_missing_feature(run_id, spec, derived_at, run_mode, collect_run_id))
                continue
            value = _safe_float(window.get("current"))
            rows.append(
                _feature_row(
                    run_id=run_id,
                    category=spec.category,
                    feature_name=spec.feature_name,
                    value=value,
                    derived_at=derived_at,
                    run_mode=run_mode,
                    collect_run_id=collect_run_id,
                    window=window,
                    cadence_group=spec.cadence_group,
                    stale_after_sec=spec.stale_after_sec,
                    upstream_metric_ids=[spec.metric_id],
                    extra_metadata={
                        "source_metric_id": spec.metric_id,
                        "normalization": _normalization_from_window(value, window),
                    },
                )
            )

        rows.extend(
            _derived_orderflow_rows(
                session=session,
                run_id=run_id,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
                derived_at=derived_at,
                db=db,
            )
        )
        rows.append(
            _price_oi_interaction_row(
                run_id=run_id,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
                derived_at=derived_at,
                db=db,
            )
        )
        rows.append(
            _residual_semantic_row(
                run_id=run_id,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
                derived_at=derived_at,
                db=db,
            )
        )
        rows.extend(
            _event_context_rows(
                run_id=run_id,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
                derived_at=derived_at,
                db=db,
            )
        )
        session.add_all(rows)

    category_counts: dict[str, int] = {}
    freshness_counts: dict[str, int] = {}
    for row in rows:
        metadata = row.metadata_json or {}
        category = str(metadata.get("category", "unknown"))
        freshness_state = str(metadata.get("freshness_state", "unknown"))
        category_counts[category] = category_counts.get(category, 0) + 1
        freshness_counts[freshness_state] = freshness_counts.get(freshness_state, 0) + 1

    return {
        "status": "completed",
        "run_id": run_id,
        "module_id": BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
        "schema_version": SCHEMA_VERSION,
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "written": len(rows),
        "category_counts": category_counts,
        "freshness_counts": freshness_counts,
        "skipped": skipped,
    }


def _derived_orderflow_rows(
    session: Any,
    run_id: str,
    run_mode: str,
    collect_run_id: str | None,
    historical_fallback: bool,
    derived_at: datetime,
    db: Database,
) -> list[schema.FeatureValue]:
    ratio_window = _window(
        "taker_buy_sell_ratio",
        source_id="binance-btcusdt-taker-buy-sell-ratio",
        limit=120,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    volume_window = _window(
        "exchange_spot_volume",
        source_id="binance-btcusdt",
        limit=120,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    ratio = _safe_float(ratio_window.get("current") if ratio_window else None)
    quote_volume = _safe_float(volume_window.get("current") if volume_window else None)
    taker_delta_quote = _taker_delta_quote(ratio, quote_volume)
    ratio_rows = _metric_rows(
        session,
        "taker_buy_sell_ratio",
        "binance-btcusdt-taker-buy-sell-ratio",
        run_mode,
        limit=60,
    )
    deltas = [
        item
        for item in (
            _taker_delta_quote(_safe_float(row.value), quote_volume) for row in ratio_rows
        )
        if item is not None
    ]
    cvd_slope_z = _cvd_slope_z(deltas)
    lineage_window = _merge_windows([ratio_window, volume_window])
    common = {
        "implementation_detail": "derived_from_binance_taker_ratio_and_quote_volume",
        "limitations": [
            "quote_volume is a coarse notional proxy",
            "not full OFI/MLOFI; no diff depth or local book is claimed",
        ],
    }
    return [
        _feature_row(
            run_id=run_id,
            category="orderflow_acceptance",
            feature_name="taker_delta_quote",
            value=taker_delta_quote,
            derived_at=derived_at,
            run_mode=run_mode,
            collect_run_id=collect_run_id,
            window=lineage_window,
            cadence_group="fast_5m",
            stale_after_sec=30 * 60,
            upstream_metric_ids=["taker_buy_sell_ratio", "exchange_spot_volume"],
            extra_metadata={**common, "normalization": _normalization_from_values(taker_delta_quote, deltas)},
        ),
        _feature_row(
            run_id=run_id,
            category="orderflow_acceptance",
            feature_name="cvd_slope_z",
            value=cvd_slope_z,
            derived_at=derived_at,
            run_mode=run_mode,
            collect_run_id=collect_run_id,
            window=lineage_window,
            cadence_group="fast_5m",
            stale_after_sec=30 * 60,
            upstream_metric_ids=["taker_buy_sell_ratio", "exchange_spot_volume"],
            extra_metadata={
                **common,
                "normalization": {"method": "cvd_slope_robust_z", "sample_count": len(deltas)},
            },
        ),
    ]


def _price_oi_interaction_row(
    run_id: str,
    run_mode: str,
    collect_run_id: str | None,
    historical_fallback: bool,
    derived_at: datetime,
    db: Database,
) -> schema.FeatureValue:
    price = _window("btc_return_4h", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    oi = _window("oi_impulse_z_4h", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    taker = _window(
        "taker_buy_sell_ratio",
        source_id="binance-btcusdt-taker-buy-sell-ratio",
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )
    price_value = _safe_float(price.get("current") if price else None)
    oi_value = _safe_float(oi.get("current") if oi else None)
    taker_value = _safe_float(taker.get("current") if taker else None)
    state, score = _price_oi_state(price_value, oi_value, taker_value)
    return _feature_row(
        run_id=run_id,
        category="derivatives_positioning",
        feature_name="price_oi_interaction_state",
        value=score,
        derived_at=derived_at,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        window=_merge_windows([price, oi, taker]),
        cadence_group="fast_4h",
        stale_after_sec=75 * 60,
        upstream_metric_ids=["btc_return_4h", "oi_impulse_z_4h", "taker_buy_sell_ratio"],
        extra_metadata={
            "semantic_state": state,
            "inputs": {
                "btc_return_4h": price_value,
                "oi_impulse_z_4h": oi_value,
                "taker_buy_sell_ratio": taker_value,
            },
        },
    )


def _residual_semantic_row(
    run_id: str,
    run_mode: str,
    collect_run_id: str | None,
    historical_fallback: bool,
    derived_at: datetime,
    db: Database,
) -> schema.FeatureValue:
    expected = _window("btc_expected_return_24h", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    residual = _window("btc_residual_24h", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    residual_z = _window("btc_residual_z_60d", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    expected_value = _safe_float(expected.get("current") if expected else None)
    residual_value = _safe_float(residual.get("current") if residual else None)
    residual_z_value = _safe_float(residual_z.get("current") if residual_z else None)
    semantic = _residual_semantic(expected_value, residual_value, residual_z_value)
    return _feature_row(
        run_id=run_id,
        category="btc_residual_cross_asset",
        feature_name="residual_semantic",
        value=residual_z_value,
        derived_at=derived_at,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        window=_merge_windows([expected, residual, residual_z]),
        cadence_group="slow_macro_daily",
        stale_after_sec=36 * 60 * 60,
        upstream_metric_ids=["btc_expected_return_24h", "btc_residual_24h", "btc_residual_z_60d"],
        extra_metadata={
            "semantic_state": semantic,
            "inputs": {
                "expected_return_24h": expected_value,
                "residual_24h": residual_value,
                "residual_z": residual_z_value,
            },
        },
    )


def _event_context_rows(
    run_id: str,
    run_mode: str,
    collect_run_id: str | None,
    historical_fallback: bool,
    derived_at: datetime,
    db: Database,
) -> list[schema.FeatureValue]:
    event_windows = [
        _window(metric, run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
        for metric in ("cpi_hours_until", "fomc_hours_until", "pce_hours_until", "nfp_hours_until")
    ]
    risk_window = _window("fomc_event_risk", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    surprise_window = _window("macro_surprise_score", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    btc_1h_window = _window("btc_return_1h", run_mode=run_mode, collect_run_id=collect_run_id, historical_fallback=historical_fallback, db=db)
    active_hours = [
        abs(value)
        for value in (_safe_float(window.get("current") if window else None) for window in event_windows)
        if value is not None
    ]
    nearest_event_hours = min(active_hours) if active_hours else None
    event_risk = max(0.0, min(_safe_float(risk_window.get("current") if risk_window else None) or 0.0, 1.0))
    macro_surprise = _safe_float(surprise_window.get("current") if surprise_window else None)
    btc_1h = _safe_float(btc_1h_window.get("current") if btc_1h_window else None)
    emergency_level = _event_emergency_level(nearest_event_hours, event_risk)
    event_trust_cap = max(0.35, 1.0 - emergency_level * 0.25 - event_risk * 0.25)
    ordinary_radar_trust = max(0.25, min(1.0, event_trust_cap + 0.15))
    trade_permission_modifier = max(0.0, min(1.0, event_trust_cap - 0.1 * event_risk))
    reaction_state, reaction_score = _post_event_reaction_state(macro_surprise, btc_1h)
    lineage = _merge_windows([*event_windows, risk_window, surprise_window, btc_1h_window])
    base_extra = {
        "nearest_event_hours": nearest_event_hours,
        "event_risk": event_risk,
        "event_direction_policy": "context_only_until_btc_reaction_validation",
    }
    values = {
        "emergency_level": float(emergency_level),
        "ordinary_radar_trust": ordinary_radar_trust,
        "trade_permission_modifier": trade_permission_modifier,
        "event_trust_cap": event_trust_cap,
        "post_event_reaction_state": reaction_score,
    }
    return [
        _feature_row(
            run_id=run_id,
            category="event_overlay_context",
            feature_name=feature_name,
            value=value,
            derived_at=derived_at,
            run_mode=run_mode,
            collect_run_id=collect_run_id,
            window=lineage,
            cadence_group="event_context",
            stale_after_sec=6 * 60 * 60,
            upstream_metric_ids=[
                "cpi_hours_until",
                "fomc_hours_until",
                "pce_hours_until",
                "nfp_hours_until",
                "fomc_event_risk",
                "macro_surprise_score",
                "btc_return_1h",
            ],
            extra_metadata={
                **base_extra,
                "semantic_state": reaction_state if feature_name == "post_event_reaction_state" else None,
            },
        )
        for feature_name, value in values.items()
    ]


def _feature_row(
    run_id: str,
    category: str,
    feature_name: str,
    value: float | None,
    derived_at: datetime,
    run_mode: str,
    collect_run_id: str | None,
    window: dict[str, Any] | None,
    cadence_group: str,
    stale_after_sec: int,
    upstream_metric_ids: list[str],
    extra_metadata: dict[str, Any] | None = None,
) -> schema.FeatureValue:
    source_asof_ts = _window_ts(window)
    collected_at = _window_collected_at(window)
    valid_until = _valid_until(collected_at, derived_at, stale_after_sec)
    freshness_state = _freshness_state(window)
    source_health = _source_health(window)
    feature_score = _feature_score(value, extra_metadata)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "category": category,
        "feature_name": feature_name,
        "snapshot_id": f"{run_id}:{category}:{feature_name}",
        "metric_id": f"btc_direct_trend.{category}.{feature_name}",
        "source_id": source_health.get("source_id") if source_health else None,
        "source_asof_ts": source_asof_ts,
        "collected_at": _iso(collected_at),
        "derived_at": derived_at.isoformat(),
        "valid_until": valid_until.isoformat(),
        "cadence_group": cadence_group,
        "stale_after_sec": stale_after_sec,
        "freshness_state": freshness_state,
        "source_health": source_health,
        "source_tier": _source_tier(cadence_group),
        "upstream_metric_ids": upstream_metric_ids,
        "upstream_source_ids": _upstream_source_ids(window),
        "feature_score": feature_score,
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "non_production": run_mode != "live",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return schema.FeatureValue(
        run_id=run_id,
        module_id=BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
        feature_id=f"btc_direct_trend.{category}.{feature_name}",
        value=value,
        metadata_json=metadata,
    )


def _missing_feature(
    run_id: str,
    spec: DirectMetricSpec,
    derived_at: datetime,
    run_mode: str,
    collect_run_id: str | None,
) -> schema.FeatureValue:
    return _feature_row(
        run_id=run_id,
        category=spec.category,
        feature_name=spec.feature_name,
        value=None,
        derived_at=derived_at,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        window=None,
        cadence_group=spec.cadence_group,
        stale_after_sec=spec.stale_after_sec,
        upstream_metric_ids=[spec.metric_id],
        extra_metadata={"source_metric_id": spec.metric_id, "missing_reason": "no_historical_window"},
    )


def _window(
    metric_id: str,
    source_id: str | None = None,
    limit: int = 120,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = True,
    db: Database = database,
) -> dict[str, Any] | None:
    return historical_window(
        metric_id=metric_id,
        source_id=source_id,
        limit=limit,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=historical_fallback,
        db=db,
    )


def _metric_rows(
    session: Any,
    metric_id: str,
    source_id: str,
    run_mode: str,
    limit: int,
) -> list[schema.MetricValue]:
    filters = [
        schema.MetricValue.metric_id == metric_id,
        schema.MetricValue.source_id == source_id,
    ]
    if run_mode != "all":
        filters.append(schema.MetricValue.run_mode == run_mode)
    rows = session.scalars(
        select(schema.MetricValue).where(*filters).order_by(schema.MetricValue.ts.desc()).limit(limit)
    ).all()
    return list(reversed(rows))


def _normalization_from_window(value: float | None, window: dict[str, Any]) -> dict[str, Any]:
    values = [
        _safe_float(candidate.get("current"))
        for candidate in window.get("candidates", [])
        if isinstance(candidate, dict)
    ]
    values = [item for item in values if item is not None]
    return _normalization_from_values(value, values)


def _normalization_from_values(value: float | None, values: Iterable[float]) -> dict[str, Any]:
    sample = [item for item in values if item is not None and math.isfinite(item)]
    robust_z = _robust_z(value, sample)
    return {
        "method": "robust_z_tanh",
        "robust_z": robust_z,
        "feature_score": _score_from_z(robust_z),
        "sample_count": len(sample),
    }


def _robust_z(value: float | None, values: list[float]) -> float | None:
    if value is None or len(values) < 5:
        return None
    center = median(values)
    deviations = [abs(item - center) for item in values]
    mad = median(deviations)
    if mad == 0:
        return 0.0
    return max(-4.0, min(4.0, (value - center) / (1.4826 * mad)))


def _score_from_z(value: float | None) -> float | None:
    if value is None:
        return None
    return math.tanh(value / 2.0)


def _feature_score(value: float | None, metadata: dict[str, Any] | None) -> float | None:
    normalization = (metadata or {}).get("normalization")
    if isinstance(normalization, dict):
        score = _safe_float(normalization.get("feature_score"))
        if score is not None:
            return score
        robust = _safe_float(normalization.get("robust_z"))
        if robust is not None:
            return _score_from_z(robust)
    if value is None:
        return None
    if abs(value) <= 4.0:
        return math.tanh(value / 2.0)
    return math.tanh(value / max(abs(value), 1.0))


def _taker_delta_quote(ratio: float | None, quote_volume: float | None) -> float | None:
    if ratio is None or quote_volume is None or ratio <= 0:
        return None
    return ((ratio - 1.0) / (ratio + 1.0)) * quote_volume


def _cvd_slope_z(deltas: list[float]) -> float | None:
    if len(deltas) < 5:
        return None
    cumulative: list[float] = []
    running = 0.0
    for delta in deltas:
        running += delta
        cumulative.append(running)
    recent = cumulative[-5:]
    slope = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    historical_slopes = [
        (cumulative[index] - cumulative[index - 4]) / 4
        for index in range(4, len(cumulative))
    ]
    return _robust_z(slope, historical_slopes)


def _price_oi_state(
    price_return: float | None,
    oi_impulse: float | None,
    taker_ratio: float | None,
) -> tuple[str, float | None]:
    if price_return is None or oi_impulse is None:
        return "insufficient_data", None
    price_up = price_return > 0
    oi_up = oi_impulse > 0
    taker_buy = taker_ratio is not None and taker_ratio > 1.02
    taker_sell = taker_ratio is not None and taker_ratio < 0.98
    if price_up and oi_up and taker_buy:
        return "aggressive_long_building", 0.8
    if price_up and not oi_up:
        return "short_covering_rally", 0.45
    if not price_up and oi_up and taker_sell:
        return "aggressive_short_building", -0.8
    if not price_up and not oi_up:
        return "deleveraging_drop", -0.45
    return "mixed_positioning", 0.0


def _residual_semantic(
    expected_return: float | None,
    residual: float | None,
    residual_z: float | None,
) -> str:
    signal = residual_z if residual_z is not None else residual
    if expected_return is None or signal is None:
        return "insufficient_data"
    if expected_return < 0 and signal > 0:
        return "external_pressure_down_but_btc_resilient"
    if expected_return > 0 and signal < 0:
        return "external_support_up_but_btc_underperforming"
    if expected_return > 0 and abs(signal) < 0.25:
        return "risk_assets_up_but_btc_not_following"
    if expected_return < 0 and signal >= 0:
        return "risk_assets_down_but_btc_absorbing"
    return "aligned_with_cross_asset_pressure"


def _event_emergency_level(nearest_event_hours: float | None, event_risk: float) -> int:
    if event_risk >= 0.75 or (nearest_event_hours is not None and nearest_event_hours <= 2):
        return 2
    if event_risk >= 0.35 or (nearest_event_hours is not None and nearest_event_hours <= 24):
        return 1
    return 0


def _post_event_reaction_state(
    macro_surprise: float | None,
    btc_return_1h: float | None,
) -> tuple[str, float]:
    if macro_surprise is None or btc_return_1h is None:
        return "unconfirmed", 0.0
    if macro_surprise > 0 and btc_return_1h < 0:
        return "bearish_macro_pressure_accepted", -0.5
    if macro_surprise > 0 and btc_return_1h >= 0:
        return "bearish_macro_pressure_absorbed", 0.35
    if macro_surprise < 0 and btc_return_1h > 0:
        return "supportive_macro_reaction_accepted", 0.5
    if macro_surprise < 0 and btc_return_1h <= 0:
        return "supportive_macro_reaction_rejected", -0.35
    return "neutral_reaction", 0.0


def _merge_windows(windows: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    valid = [window for window in windows if window]
    if not valid:
        return None
    selected = max(valid, key=lambda item: _parse_dt(item.get("collected_at")) or datetime.min.replace(tzinfo=UTC))
    source_ids = sorted({str(window.get("source_id")) for window in valid if window.get("source_id")})
    freshness_states = [_freshness_state(window) for window in valid]
    freshness_state = "fresh" if all(item == "fresh" for item in freshness_states) else "partial"
    upstream_metric_ids = sorted({str(window.get("metric_id")) for window in valid if window.get("metric_id")})
    merged = dict(selected)
    merged.update(
        {
            "source_id": ",".join(source_ids),
            "metric_id": ",".join(upstream_metric_ids),
            "freshness_status": selected.get("freshness_status", "unknown"),
            "merged_freshness_state": freshness_state,
            "merged_windows": [
                {
                    "metric_id": window.get("metric_id"),
                    "source_id": window.get("source_id"),
                    "freshness_status": window.get("freshness_status"),
                    "business_recency_status": window.get("business_recency_status"),
                    "source_ts": window.get("source_ts"),
                    "collected_at": window.get("collected_at"),
                }
                for window in valid
            ],
        }
    )
    return merged


def _freshness_state(window: dict[str, Any] | None) -> str:
    if not window:
        return "missing"
    merged = window.get("merged_freshness_state")
    if merged:
        return str(merged)
    source_status = window.get("freshness_status")
    business_status = window.get("business_recency_status")
    if source_status in {"missing"}:
        return "missing"
    if source_status in {"stale", "expired"} or business_status in {"outdated", "provider_stale_suspect"}:
        return "stale"
    if business_status in {"lagging"}:
        return "partial"
    return "fresh"


def _source_health(window: dict[str, Any] | None) -> dict[str, Any]:
    if not window:
        return {
            "source_id": None,
            "freshness_status": "missing",
            "business_recency_status": "missing",
            "effective_quality_score": None,
        }
    return {
        "source_id": window.get("source_id"),
        "metric_id": window.get("metric_id"),
        "source_run_id": window.get("source_run_id"),
        "freshness_status": window.get("freshness_status"),
        "collection_freshness_status": window.get("collection_freshness_status"),
        "business_recency_status": window.get("business_recency_status"),
        "quality_score": window.get("quality_score"),
        "effective_quality_score": window.get("effective_quality_score"),
        "age_seconds": window.get("age_seconds"),
        "business_age_seconds": window.get("business_age_seconds"),
        "selected_reason": window.get("selected_reason"),
        "feature_run_scope": window.get("feature_run_scope"),
        "merged_windows": window.get("merged_windows", []),
    }


def _window_ts(window: dict[str, Any] | None) -> str | None:
    if not window:
        return None
    source_ts = window.get("source_ts")
    if source_ts:
        return str(source_ts)
    observed = window.get("observed_at")
    return str(observed) if observed else None


def _window_collected_at(window: dict[str, Any] | None) -> datetime | None:
    if not window:
        return None
    return _parse_dt(window.get("collected_at"))


def _valid_until(collected_at: datetime | None, derived_at: datetime, stale_after_sec: int) -> datetime:
    anchor = collected_at or derived_at
    return anchor + timedelta(seconds=stale_after_sec)


def _upstream_source_ids(window: dict[str, Any] | None) -> list[str]:
    if not window:
        return []
    merged = window.get("merged_windows")
    if isinstance(merged, list):
        return sorted(
            {
                str(item.get("source_id"))
                for item in merged
                if isinstance(item, dict) and item.get("source_id")
            }
        )
    source_id = window.get("source_id")
    return [str(source_id)] if source_id else []


def _source_tier(cadence_group: str) -> str:
    if cadence_group.startswith("fast") or cadence_group.startswith("funding"):
        return "fast_direct"
    if cadence_group.startswith("slow"):
        return "slow_context"
    if cadence_group.startswith("event"):
        return "event_context"
    return "derived"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            return None
    return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _generate_run_id() -> str:
    return f"p1c75-direct-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
