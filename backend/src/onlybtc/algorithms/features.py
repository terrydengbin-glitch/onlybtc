from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.sources.registry import METRIC_DEFINITIONS
from onlybtc.sources.service import historical_window

MODULE_ID = "p3_feature_engine"


def calculate_p3_features(
    metric_ids: list[str] | None = None,
    run_id: str | None = None,
    limit: int = 120,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any]:
    """Calculate P3 base features from selected P1 historical windows."""

    db.init_schema()
    run_id = run_id or _generate_feature_run_id()
    selected_metric_ids = _selected_metric_ids(metric_ids)
    written = 0
    calculated_metrics = 0
    skipped: list[dict[str, Any]] = []

    with db.session() as session:
        for metric_id in selected_metric_ids:
            window = historical_window(
                metric_id=metric_id,
                limit=limit,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
                db=db,
            )
            if not window or not window.get("source_id"):
                skipped.append({"metric_id": metric_id, "reason": "no_historical_window"})
                continue

            source_id = str(window["source_id"])
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
            rows = list(reversed(rows))
            if not rows:
                skipped.append({"metric_id": metric_id, "reason": "no_metric_values"})
                continue

            feature_rows = _feature_rows(
                run_id,
                metric_id,
                source_id,
                rows,
                window,
                limit,
                run_mode,
                collect_run_id,
            )
            session.add_all(feature_rows)
            written += len(feature_rows)
            calculated_metrics += 1

    return {
        "状态": "完成",
        "run_id": run_id,
        "指标数量": len(selected_metric_ids),
        "已计算指标": calculated_metrics,
        "写入特征数": written,
        "跳过数量": len(skipped),
        "跳过": skipped,
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "historical_fallback": historical_fallback,
        "non_production": run_mode != "live",
    }


def _selected_metric_ids(metric_ids: list[str] | None) -> list[str]:
    if metric_ids:
        return list(dict.fromkeys(metric_ids))
    return list(dict.fromkeys(metric.metric_id for metric in METRIC_DEFINITIONS))


def _feature_rows(
    run_id: str,
    metric_id: str,
    source_id: str,
    rows: list[schema.MetricValue],
    window: dict[str, Any],
    limit: int,
    run_mode: str,
    collect_run_id: str | None,
) -> list[schema.FeatureValue]:
    values = [float(row.value) for row in rows if row.value is not None]
    latest = rows[-1]
    latest_ts = _ensure_utc(latest.ts)
    quality = _safe_float(window.get("effective_quality_score"), latest.quality_score)
    change_window = _relative_change(values[0], values[-1]) if len(values) >= 2 else None
    features = {
        "latest_value": values[-1] if values else None,
        "change_latest": _latest_change(rows),
        "change_window": change_window,
        "ma_7": _mean(values[-7:]),
        "ma_30": _mean(values[-30:]),
        "volatility": _return_volatility(values),
        "slope_per_hour": _slope_per_hour(rows),
        "freshness_weighted_change": (
            change_window * quality if change_window is not None and quality is not None else None
        ),
        "sample_count": float(len(values)),
    }
    metadata_base = {
        "metric_id": metric_id,
        "source_id": source_id,
        "source_run_id": window.get("source_run_id") or latest.run_id,
        "collect_run_id": collect_run_id,
        "feature_run_scope": window.get("feature_run_scope", "unspecified_history"),
        "current_run_has_value": window.get("current_run_has_value", False),
        "fallback_age_seconds": window.get("fallback_age_seconds"),
        "fallback_reason": window.get("fallback_reason"),
        "same_run_coverage_score": 1.0
        if window.get("feature_run_scope") == "current_run"
        else 0.0,
        "latest_ts": latest_ts.isoformat(),
        "sample_count": len(values),
        "window_limit": limit,
        "quality_score": window.get("quality_score"),
        "effective_quality_score": quality,
        "source_freshness": window.get("freshness_status"),
        "collection_freshness_status": window.get("collection_freshness_status"),
        "business_recency": window.get("business_recency_status"),
        "freshness_policy": window.get("freshness_policy"),
        "selected_reason": window.get("selected_reason"),
        "candidates": window.get("candidates", []),
        "conflict": window.get("conflict", {"detected": False, "items": []}),
        "p3_quality_rule": _quality_rule(window),
        "run_mode": run_mode,
        "non_production": run_mode != "live",
    }
    return [
        schema.FeatureValue(
            run_id=run_id,
            module_id=MODULE_ID,
            feature_id=f"{metric_id}.{feature_name}",
            value=value,
            metadata_json={**metadata_base, "feature_name": feature_name},
        )
        for feature_name, value in features.items()
    ]


def _latest_change(rows: list[schema.MetricValue]) -> float | None:
    latest = rows[-1]
    if latest.previous_value is not None:
        return _relative_change(float(latest.previous_value), float(latest.value))
    if len(rows) < 2:
        return None
    return _relative_change(float(rows[-2].value), float(latest.value))


def _relative_change(start: float, end: float) -> float | None:
    if start == 0:
        return None
    return (end - start) / abs(start)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _return_volatility(values: list[float]) -> float | None:
    returns = [
        change
        for previous, current in zip(values, values[1:], strict=False)
        if (change := _relative_change(previous, current)) is not None
    ]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / len(returns)
    return math.sqrt(variance)


def _slope_per_hour(rows: list[schema.MetricValue]) -> float | None:
    if len(rows) < 2:
        return None
    first = rows[0]
    latest = rows[-1]
    elapsed_hours = (
        _ensure_utc(latest.ts) - _ensure_utc(first.ts)
    ).total_seconds() / 3600
    if elapsed_hours <= 0 or first.value == 0:
        return None
    return ((float(latest.value) - float(first.value)) / abs(float(first.value))) / elapsed_hours


def _quality_rule(window: dict[str, Any]) -> str:
    freshness = window.get("freshness_status")
    business = window.get("business_recency_status")
    if freshness == "expired":
        return "evidence_only_no_sensitive_trigger"
    if freshness == "stale":
        return "watch_or_info_only"
    if business in {"outdated", "provider_stale_suspect"}:
        return "reduced_short_term_sensitivity"
    return "normal"


def _safe_float(value: Any, fallback: float | None = None) -> float | None:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _generate_feature_run_id() -> str:
    return f"feature-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
