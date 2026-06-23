from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from onlybtc.db import schema
from onlybtc.sources.models import HistoricalWindow, MetricSample


def enrich_metric_sample(
    session: Session,
    sample: MetricSample,
    run_mode: str = "live",
) -> MetricSample:
    previous = session.scalar(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == sample.metric_id,
            schema.MetricValue.source_id == sample.source_id,
            schema.MetricValue.run_mode == run_mode,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(1)
    )
    if previous is None:
        return sample
    if previous.value == 0:
        change_24h = None
    else:
        change_24h = (sample.value - previous.value) / abs(previous.value)
    sample.previous_value = previous.value
    sample.change_24h = change_24h
    return sample


def build_historical_window(samples: Iterable[schema.MetricValue]) -> HistoricalWindow | None:
    ordered = sorted(samples, key=lambda item: item.ts)
    if not ordered:
        return None
    current = ordered[-1]
    previous = ordered[-2] if len(ordered) >= 2 else None
    values_30d = [item.value for item in ordered[-30:]]
    ma_30d = sum(values_30d) / len(values_30d)
    return HistoricalWindow(
        metric_id=current.metric_id,
        source_id=current.source_id,
        current=current.value,
        previous=previous.value if previous else None,
        change_24h=current.change_24h,
        change_7d=current.change_7d,
        ma_30d=ma_30d,
        quality_score=current.quality_score,
        is_fallback=current.is_fallback,
        run_mode=current.run_mode,
        sample_count=len(ordered),
        observed_at=current.ts,
        collected_at=current.updated_at or current.created_at,
        source_run_id=current.run_id,
    )


def quality_status(
    score: float,
    latency_ms: int | None = None,
    freshness_status: str | None = None,
) -> str:
    if score < 0.5:
        return "error"
    if freshness_status == "expired":
        return "stale"
    if score < 0.7:
        return "warning"
    if freshness_status == "stale":
        return "stale"
    if latency_ms is not None and latency_ms > 15 * 60 * 1000:
        return "stale"
    return "healthy"
