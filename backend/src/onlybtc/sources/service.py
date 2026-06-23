from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from onlybtc.core.config import Settings, get_settings
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.sources.clients import make_client, payload_hash
from onlybtc.sources.models import (
    CollectionResult,
    HistoricalWindow,
    MetricSample,
    SourceConfig,
    SourceKind,
    SourceMode,
    SourceStatus,
)
from onlybtc.sources.normalization import (
    build_historical_window,
    enrich_metric_sample,
    quality_status,
)
from onlybtc.sources.registry import METRIC_DEFINITIONS, SOURCE_CONFIGS


async def collect_sources(
    mode: SourceMode = SourceMode.MOCK,
    source_ids: list[str] | None = None,
    run_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    settings = get_settings()
    run_id = run_id or _generate_collect_run_id()
    selected_sources = [
        source
        for source in SOURCE_CONFIGS
        if (source_ids is None or source.source_id in source_ids)
        and _is_collectable_config_source(source)
    ]
    semaphores = _collection_semaphores(settings)
    fred_queue_indices: dict[str, int] = {}
    fred_index = 0
    for source in selected_sources:
        if source.kind == SourceKind.FRED:
            fred_queue_indices[source.source_id] = fred_index
            fred_index += 1
    results = await asyncio.gather(
        *[
            _collect_source_with_retry(
                source=source,
                mode=mode,
                semaphore=semaphores[_source_concurrency_group(source)],
                queue_index=fred_queue_indices.get(source.source_id),
                max_retries=settings.source_max_retries,
                retry_backoff_seconds=settings.source_retry_backoff_seconds,
            )
            for source in selected_sources
        ],
        return_exceptions=True,
    )

    collected: list[CollectionResult] = []
    errors: list[dict[str, str]] = []
    for source, result in zip(selected_sources, results, strict=True):
        if isinstance(result, Exception):
            error_message = _format_exception(result)
            errors.append(
                {
                    "source_id": source.source_id,
                    "error": error_message,
                    "error_type": result.__class__.__name__,
                    "category": _error_category(result, error_message),
                }
            )
            collected.append(_error_result(source, result))
        else:
            if result.raw.status == SourceStatus.ERROR:
                errors.append(
                    {
                        "source_id": source.source_id,
                        "error": result.raw.error_message or "source returned error",
                        "error_type": str(
                            result.raw.payload.get("error_type", "SourceError")
                            if isinstance(result.raw.payload, dict)
                            else "SourceError"
                        ),
                        "category": str(
                            result.raw.payload.get("error_category", "source_error")
                            if isinstance(result.raw.payload, dict)
                            else "source_error"
                        ),
                    }
                )
            collected.append(result)

    with db.session() as session:
        ensure_source_registry(session)
        for result in collected:
            persist_collection_result(session, result, run_id=run_id, mode=mode.value)
        session.flush()
        session.info.pop("_metric_value_keys", None)
        _backfill_dollar_liquidity_derived_metrics(session, run_id, mode.value)
        _backfill_treasury_credit_derived_metrics(session, run_id, mode.value)
        _backfill_fund_flow_derived_metrics(session, run_id, mode.value)
        _backfill_onchain_valuation_derived_metrics(session, run_id, mode.value)
        _backfill_btc_adoption_derived_metrics(session, run_id, mode.value)
        _backfill_asia_risk_derived_metrics(session, run_id, mode.value)
        session.flush()
        gate = _collect_gate(
            selected_sources=selected_sources,
            collected=collected,
            metric_count=sum(len(result.metrics) for result in collected),
            settings=settings,
        )
        snapshot = write_data_quality_snapshot(session, run_id=run_id)
        snapshot["payload"]["collect_gate"] = gate
        snapshot_row = session.scalar(
            select(schema.DataQualitySnapshot).where(schema.DataQualitySnapshot.run_id == run_id)
        )
        if snapshot_row is not None:
            snapshot_row.payload = snapshot["payload"]
        session.flush()
        counts = _source_counts(session)
    return {
        "run_id": run_id,
        "mode": mode,
        "collected": len(collected),
        "errors": errors,
        "warnings": _collection_warnings(collected),
        "data_quality": snapshot,
        "collect_gate": gate,
        "counts": counts,
    }


_CRITICAL_SOURCE_IDS = {
    "binance-btcusdt",
    "binance-btcusdt-kline-1h",
    "binance-btcusdt-funding",
    "binance-btcusdt-open-interest",
    "binance-btcusdt-global-long-short-account-ratio",
    "binance-btcusdt-top-long-short-account-ratio",
    "binance-btcusdt-top-long-short-position-ratio",
    "binance-btcusdt-taker-buy-sell-ratio",
    "coingecko-global",
    "official-macro-event-calendar",
}


def _collection_semaphores(settings: Settings) -> dict[str, asyncio.Semaphore]:
    return {
        "playwright": asyncio.Semaphore(settings.source_playwright_concurrency),
        "official": asyncio.Semaphore(settings.source_official_concurrency),
        "fred": asyncio.Semaphore(settings.source_fred_concurrency),
        "http": asyncio.Semaphore(settings.source_http_concurrency),
    }


def _source_concurrency_group(source: SourceConfig) -> str:
    if source.kind == SourceKind.FRED:
        return "fred"
    if source.kind == SourceKind.PLAYWRIGHT:
        return "playwright"
    if source.kind == SourceKind.OFFICIAL and source.method not in {"websocket_sample"}:
        return "official"
    return "http"


def _is_critical_source(source: SourceConfig) -> bool:
    return (
        source.source_id in _CRITICAL_SOURCE_IDS
        or source.kind == SourceKind.FRED
        or bool(source.metadata.get("critical_source"))
    )


async def _collect_source_with_retry(
    source: SourceConfig,
    mode: SourceMode,
    semaphore: asyncio.Semaphore,
    queue_index: int | None,
    max_retries: int,
    retry_backoff_seconds: float,
) -> CollectionResult:
    attempts: list[dict[str, Any]] = []
    attempt_count = max_retries + 1 if _is_critical_source(source) else 1
    last_exception: Exception | None = None
    queue_meta = await _source_queue_delay(source, queue_index)
    async with semaphore:
        for attempt in range(1, attempt_count + 1):
            started = datetime.now(UTC)
            try:
                result = await make_client(source, mode).collect()
                attempts.append(
                    {
                        "attempt": attempt,
                        "status": result.raw.status.value,
                        "latency_ms": result.raw.latency_ms,
                        "duration_ms": _duration_ms(started),
                    }
                )
                result = _attach_attempts(result, attempts)
                result = _attach_queue_metadata(result, queue_meta)
                if result.raw.status != SourceStatus.ERROR or attempt >= attempt_count:
                    return result
            except Exception as exc:  # noqa: BLE001 - collection diagnostics keep raw type.
                last_exception = exc
                message = _format_exception(exc)
                attempts.append(
                    {
                        "attempt": attempt,
                        "status": SourceStatus.ERROR.value,
                        "error_type": exc.__class__.__name__,
                        "error_category": _error_category(exc, message),
                        "error_message": message,
                        "duration_ms": _duration_ms(started),
                    }
                )
                if attempt >= attempt_count:
                    break
            if retry_backoff_seconds:
                await asyncio.sleep(retry_backoff_seconds * attempt)

    if last_exception is not None:
        return _attach_queue_metadata(
            _error_result(source, last_exception, attempts=attempts),
            queue_meta,
        )
    return _attach_queue_metadata(
        _error_result(
            source,
            RuntimeError("source returned error after retry attempts"),
            attempts=attempts,
        ),
        queue_meta,
    )


async def _source_queue_delay(source: SourceConfig, queue_index: int | None) -> dict[str, Any]:
    if source.kind != SourceKind.FRED or queue_index is None:
        return {}
    settings = get_settings()
    batch_size = max(int(settings.source_fred_batch_size), 1)
    batch_index = queue_index // batch_size
    slot_index = queue_index % batch_size
    delay_ms = (
        batch_index * int(settings.source_fred_inter_batch_delay_ms)
        + (slot_index % max(int(settings.source_fred_concurrency), 1))
        * int(settings.source_fred_per_request_jitter_ms)
    )
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)
    return {
        "provider_group": "fred",
        "batch_group": f"fred-batch-{batch_index}",
        "queue_index": queue_index,
        "batch_index": batch_index,
        "slot_index": slot_index,
        "queue_delay_ms": delay_ms,
        "throttle_status": "delayed" if delay_ms > 0 else "immediate",
    }


def _attach_attempts(result: CollectionResult, attempts: list[dict[str, Any]]) -> CollectionResult:
    payload = dict(result.raw.payload or {})
    payload["collect_attempts"] = attempts
    payload["attempt_count"] = len(attempts)
    if result.raw.status == SourceStatus.ERROR:
        payload.setdefault("error_type", "SourceError")
        payload.setdefault("error_category", "source_error")
        if not result.raw.error_message:
            result.raw.error_message = "SourceError: empty source error message"
    result.raw.payload = payload
    return result


def _attach_queue_metadata(result: CollectionResult, queue_meta: dict[str, Any]) -> CollectionResult:
    if not queue_meta:
        return result
    payload = dict(result.raw.payload or {})
    payload["source_queue"] = queue_meta
    payload.setdefault("batch_group", queue_meta.get("batch_group"))
    payload.setdefault("throttle_status", queue_meta.get("throttle_status"))
    result.raw.payload = payload
    return result


def _duration_ms(started: datetime) -> int:
    return int((datetime.now(UTC) - started).total_seconds() * 1000)


def _format_exception(error: Exception) -> str:
    message = str(error).strip()
    if not message:
        message = "empty exception message"
    return f"{error.__class__.__name__}: {message}"


def _error_category(error: Exception, message: str) -> str:
    text = f"{error.__class__.__name__} {message}".lower()
    if "429" in text or "too many requests" in text or "rate" in text:
        return "rate_limited"
    if "403" in text or "forbidden" in text or "access denied" in text:
        return "access_denied"
    if "timeout" in text:
        return "timeout"
    if "connect" in text or "network" in text:
        return "network"
    if "5xx" in text or "500" in text or "502" in text or "503" in text or "504" in text:
        return "server_error"
    return "exception"


def _collect_gate(
    selected_sources: list[SourceConfig],
    collected: list[CollectionResult],
    metric_count: int,
    settings: Settings,
) -> dict[str, Any]:
    failed_results = [item for item in collected if item.raw.status == SourceStatus.ERROR]
    warning_results = [item for item in collected if item.raw.status == SourceStatus.WARNING]
    healthy_results = [item for item in collected if item.raw.status == SourceStatus.HEALTHY]
    critical_failures = [
        item.source.source_id for item in failed_results if _is_critical_source(item.source)
    ]
    reasons: list[str] = []
    if critical_failures:
        reasons.append(f"critical_source_failure:{','.join(sorted(critical_failures))}")
    if len(failed_results) > settings.source_failure_gate_threshold:
        reasons.append(
            "source_failure_count_high:"
            f"{len(failed_results)}>{settings.source_failure_gate_threshold}"
        )
    if metric_count < settings.source_min_current_metrics and len(selected_sources) > 1:
        reasons.append(
            "current_run_metric_count_low:"
            f"{metric_count}<{settings.source_min_current_metrics}"
        )
    status = "failed" if reasons else "passed"
    if status == "passed" and warning_results:
        status = "warning"
    return {
        "collect_gate_status": status,
        "collect_gate_reasons": reasons,
        "source_attempted_count": len(selected_sources),
        "source_success_count": len(healthy_results),
        "source_warning_count": len(warning_results),
        "source_failure_count": len(failed_results),
        "critical_source_failure_count": len(critical_failures),
        "critical_source_failures": sorted(critical_failures),
        "current_run_metric_count": metric_count,
        "expected_min_current_metrics": settings.source_min_current_metrics,
        "failure_gate_threshold": settings.source_failure_gate_threshold,
    }


def ensure_source_registry(session: Session) -> None:
    active_source_ids = {source.source_id for source in SOURCE_CONFIGS}
    for source in SOURCE_CONFIGS:
        existing = session.scalar(
            select(schema.Source).where(schema.Source.source_id == source.source_id)
        )
        metadata = {**source.metadata, "archived": False}
        if existing is None:
            session.add(
                schema.Source(
                    source_id=source.source_id,
                    name=source.name,
                    group_name=source.group_name,
                    method=source.method,
                    priority=source.priority,
                    status="healthy",
                    fallback_source_id=source.fallback_source_id,
                    metadata_json=metadata,
                )
            )
        else:
            existing.name = source.name
            existing.group_name = source.group_name
            existing.method = source.method
            existing.fallback_source_id = source.fallback_source_id
            existing.priority = source.priority
            existing.status = "healthy"
            existing.metadata_json = metadata
    reconcile_source_registry(session, active_source_ids)
    session.flush()

    for metric in METRIC_DEFINITIONS:
        existing_metric = session.scalar(
            select(schema.NormalizedMetric).where(
                schema.NormalizedMetric.metric_id == metric.metric_id
            )
        )
        if existing_metric is None:
            session.add(
                schema.NormalizedMetric(
                    metric_id=metric.metric_id,
                    source_id=metric.source_id,
                    name=metric.name,
                    unit=metric.unit,
                    group_name=metric.group_name,
                    higher_is=metric.higher_is,
                )
            )
    session.flush()


def reconcile_source_registry(
    session: Session,
    active_source_ids: set[str] | None = None,
) -> list[str]:
    active_source_ids = active_source_ids or {source.source_id for source in SOURCE_CONFIGS}
    archived: list[str] = []
    rows = session.scalars(select(schema.Source)).all()
    now = datetime.now(UTC).isoformat()
    for row in rows:
        if row.source_id in active_source_ids:
            continue
        metadata = dict(row.metadata_json or {})
        if metadata.get("archived") is True:
            archived.append(row.source_id)
            continue
        metadata.update(
            {
                "archived": True,
                "archived_at": now,
                "archive_reason": "not_in_source_configs",
            }
        )
        row.metadata_json = metadata
        row.status = "archived"
        archived.append(row.source_id)
        session.add(
            schema.SourceHealthEvent(
                source_id=row.source_id,
                status="archived",
                quality_score=0.0,
                message="source archived: not_in_source_configs",
            )
        )
    return sorted(archived)


def persist_collection_result(
    session: Session,
    result: CollectionResult,
    run_id: str | None = None,
    mode: str = "unknown",
) -> None:
    source_status = result.raw.status.value
    error_message = result.raw.error_message
    if result.source.source_id.startswith("binance-btcusdt-kline-") and result.source.source_id != "binance-btcusdt-kline-1d-rv":
        expected_metrics = set(result.source.metrics)
        actual_metrics = {sample.metric_id for sample in result.metrics}
        missing_metrics = sorted(expected_metrics - actual_metrics)
        raw_klines = result.raw.payload.get("klines") if isinstance(result.raw.payload, dict) else None
        kline_count = len(raw_klines) if isinstance(raw_klines, list) else None
        if missing_metrics:
            source_status = SourceStatus.WARNING.value
            guard_message = (
                "insufficient_kline_metric_chain "
                f"expected={len(expected_metrics)} actual={len(actual_metrics)} "
                f"missing={','.join(missing_metrics)}"
            )
            if kline_count is not None:
                guard_message = f"{guard_message} raw_kline_count={kline_count}"
            error_message = f"{error_message}; {guard_message}" if error_message else guard_message
    session.add(
        schema.SourceRun(
            run_id=run_id,
            source_id=result.source.source_id,
            mode=mode,
            status=source_status,
            started_at=result.raw.observed_at,
            completed_at=datetime.now(UTC),
            latency_ms=result.raw.latency_ms,
            error_message=error_message,
        )
    )
    session.add(
        schema.RawObservation(
            run_id=run_id,
            source_id=result.source.source_id,
            mode=mode,
            observed_at=result.raw.observed_at,
            raw_payload=result.raw.payload,
            payload_hash=payload_hash(result.raw.payload),
        )
    )

    raw_quality = _result_quality(result)
    observed_at = max((sample.ts for sample in result.metrics), default=result.raw.observed_at)
    collected_at = datetime.now(UTC)
    freshness = compute_collection_freshness(result.source, collected_at)
    business_recency = compute_business_recency(result.source, observed_at)
    quality = _apply_freshness_discount(raw_quality, freshness)
    status = quality_status(quality, result.raw.latency_ms, freshness["freshness_status"])
    health_message = _freshness_message(freshness, error_message, business_recency)
    session.add(
        schema.SourceHealthEvent(
            source_id=result.source.source_id,
            status=status,
            quality_score=quality,
            latency_ms=result.raw.latency_ms,
            message=health_message,
        )
    )

    enriched_samples: list[MetricSample] = []
    for sample in result.metrics:
        enriched = _upsert_metric_sample(session, run_id, mode, sample)
        enriched_samples.append(enriched)
        for derived in _btc_total_state_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _crypto_breadth_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _options_volatility_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _macro_radar_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _treasury_credit_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _dollar_liquidity_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _fund_flow_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _onchain_valuation_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _btc_adoption_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _asia_risk_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
    for enriched in enriched_samples:
        for derived in _dollar_liquidity_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _treasury_credit_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _fund_flow_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _onchain_valuation_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _btc_adoption_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)
        for derived in _asia_risk_derived_samples(session, enriched, mode):
            _upsert_metric_sample(session, run_id, mode, derived)

    if (
        result.raw.status in {SourceStatus.ERROR, SourceStatus.WARNING}
        and result.source.fallback_source_id
    ):
        session.add(
            schema.FallbackEvent(
                source_id=result.source.source_id,
                fallback_source_id=result.source.fallback_source_id,
                reason=result.raw.error_message or f"source status: {result.raw.status}",
                discount=0.35,
            )
        )


def historical_window(
    metric_id: str,
    source_id: str | None = None,
    limit: int = 90,
    run_mode: str = "live",
    collect_run_id: str | None = None,
    historical_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        if source_id:
            rows, feature_run_scope = _metric_rows_for_scope(
                session=session,
                metric_id=metric_id,
                source_id=source_id,
                limit=limit,
                run_mode=run_mode,
                collect_run_id=collect_run_id,
                historical_fallback=historical_fallback,
            )
            scoped_rows = _rows_for_collect_run_window(rows, collect_run_id, limit)
            window = _build_source_window(scoped_rows)
            if window:
                _annotate_window_run_scope(
                    window,
                    feature_run_scope=feature_run_scope,
                    collect_run_id=collect_run_id,
                    current_run_has_value=feature_run_scope == "current_run",
                )
            return window.model_dump(mode="json") if window else None

        rows, feature_run_scope = _metric_rows_for_scope(
            session=session,
            metric_id=metric_id,
            source_id=None,
            limit=max(limit * 12, limit),
            run_mode=run_mode,
            collect_run_id=collect_run_id,
            historical_fallback=historical_fallback,
        )
        rows_by_source: dict[str, list[schema.MetricValue]] = defaultdict(list)
        for row in rows:
            rows_by_source[row.source_id].append(row)

        windows = [
            window
            for source_rows in rows_by_source.values()
            if (
                window := _build_source_window(
                    _rows_for_collect_run_window(source_rows, collect_run_id, limit)
                )
            )
            is not None
        ]
        if not windows:
            return None
        current_run_sources = {
            row.source_id for row in rows if collect_run_id and row.run_id == collect_run_id
        }
        for window in windows:
            window_scope = (
                "current_run"
                if window.source_id in current_run_sources
                else "historical_fallback"
                if collect_run_id and historical_fallback
                else feature_run_scope
            )
            _annotate_window_run_scope(
                window,
                feature_run_scope=window_scope,
                collect_run_id=collect_run_id,
                current_run_has_value=window.source_id in current_run_sources,
            )
        selected = max(windows, key=_window_arbitration_key)
        candidates = [_window_candidate(window, window is selected) for window in windows]
        selected.candidates = sorted(
            candidates,
            key=lambda item: (
                -_freshness_rank(item["freshness_status"]),
                -(item["effective_quality_score"] or 0.0),
                item["source_priority"],
            ),
        )
        selected.conflict = _source_conflict(selected, windows)
        selected.selected_reason = _selected_reason(selected)
        return selected.model_dump(mode="json")


def source_health_summary(db: Database = database) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        events = session.scalars(
            select(schema.SourceHealthEvent)
            .order_by(schema.SourceHealthEvent.created_at.desc())
            .limit(50)
        ).all()
        return {
            "events": [
                {
                    "source_id": event.source_id,
                    "status": event.status,
                    "quality_score": event.quality_score,
                    "latency_ms": event.latency_ms,
                    "message": event.message,
                    "created_at": event.created_at.isoformat(),
                    **_source_freshness_summary(session, event.source_id),
                }
                for event in events
            ]
        }


def write_data_quality_snapshot(
    session: Session,
    run_id: str | None = None,
) -> dict[str, Any]:
    all_sources = session.scalars(select(schema.Source)).all()
    sources = [
        source
        for source in all_sources
        if not _is_archived_db_source(source) and _is_collectable_db_source(source)
    ]
    archived_sources = [
        source.source_id for source in all_sources if _is_archived_db_source(source)
    ]
    summaries = [_source_freshness_summary(session, source.source_id) for source in sources]
    health_rows = [
        _latest_source_health(session, source.source_id) for source in sources
    ]
    health_rows = [row for row in health_rows if row is not None]
    health_by_source = {row.source_id: row for row in health_rows}
    source_count = len(sources)
    freshness_counts = {
        status: sum(1 for item in summaries if item["freshness_status"] == status)
        for status in ("fresh", "stale", "expired", "missing")
    }
    business_recency_statuses = (
        "current",
        "expected_lag",
        "lagging",
        "outdated",
        "provider_stale_suspect",
        "unknown",
    )
    business_recency_counts = {
        status: sum(1 for item in summaries if item["business_recency_status"] == status)
        for status in business_recency_statuses
    }
    quality_values = [
        health_by_source[source.source_id].quality_score
        for source in sources
        if source.source_id in health_by_source
    ]
    avg_quality = (
        sum(quality_values) / len(quality_values)
        if quality_values
        else 0.0
    )
    freshness_score = (
        (
            freshness_counts["fresh"]
            + freshness_counts["stale"] * 0.65
            + freshness_counts["expired"] * 0.25
        )
        / source_count
        if source_count
        else 0.0
    )
    score = round(avg_quality * 0.65 + freshness_score * 0.35, 4)
    status = "critical" if score < 0.5 else "warning" if score < 0.75 else "healthy"
    snapshot_run_id = run_id or f"data-quality-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    payload = {
        "source_count": source_count,
        "avg_quality_score": round(avg_quality, 4),
        "freshness_score": round(freshness_score, 4),
        "freshness_counts": freshness_counts,
        "business_recency_counts": business_recency_counts,
        "stale_sources": [
            item for item in summaries if item["freshness_status"] in {"stale", "expired"}
        ],
        "business_lagging_sources": [
            item
            for item in summaries
            if item["business_recency_status"]
            in {"lagging", "outdated", "provider_stale_suspect"}
        ],
        "missing_sources": [item for item in summaries if item["freshness_status"] == "missing"],
        "archived_sources": archived_sources,
        "registry_drift_count": len(archived_sources),
        "run_mode_summary": _run_mode_summary(session, current_run_id=snapshot_run_id),
        "fallback_summary": _fallback_summary(session),
    }
    session.add(
        schema.DataQualitySnapshot(
            run_id=snapshot_run_id,
            score=score,
            status=status,
            payload=payload,
        )
    )
    return {"run_id": snapshot_run_id, "score": score, "status": status, "payload": payload}


def compute_freshness(
    source: SourceConfig | None,
    observed_at: datetime | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    return compute_collection_freshness(source, observed_at, now)


def compute_collection_freshness(
    source: SourceConfig | None,
    collected_at: datetime | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    policy = _freshness_policy(source)
    expected_seconds = float(policy["expected_update_seconds"])
    if collected_at is None:
        return {
            "age_seconds": None,
            "freshness_minutes": None,
            "expected_refresh_seconds": expected_seconds,
            "stale_after_seconds": float(policy["collection_stale_after_seconds"]),
            "stale_after_minutes": round(
                float(policy["collection_stale_after_seconds"]) / 60.0,
                4,
            ),
            "is_stale": None,
            "freshness_status": "missing",
            "freshness_discount": -1.0,
            "freshness_policy": policy,
        }
    collected = _ensure_utc(collected_at)
    age_seconds = max((now - collected).total_seconds(), 0.0)
    stale_after = float(policy["collection_stale_after_seconds"])
    expired_after = float(policy["collection_expired_after_seconds"])
    if age_seconds > expired_after:
        status = "expired"
        discount = -0.35
    elif age_seconds > stale_after:
        status = "stale"
        discount = -0.15
    else:
        status = "fresh"
        discount = 0.0
    return {
        "age_seconds": round(age_seconds, 3),
        "freshness_minutes": round(age_seconds / 60.0, 4),
        "expected_refresh_seconds": expected_seconds,
        "stale_after_seconds": stale_after,
        "stale_after_minutes": round(stale_after / 60.0, 4),
        "is_stale": status in {"stale", "expired"},
        "freshness_status": status,
        "freshness_discount": discount,
        "freshness_policy": policy,
    }


def compute_business_recency(
    source: SourceConfig | None,
    observed_at: datetime | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    policy = _freshness_policy(source)
    expected_seconds = float(policy["expected_update_seconds"])
    if observed_at is None:
        return {
            "age_seconds": None,
            "business_age_minutes": None,
            "expected_refresh_seconds": expected_seconds,
            "business_recency_status": "unknown",
            "business_recency_discount": -0.1,
            "freshness_policy": policy,
        }
    observed = _ensure_utc(observed_at)
    age_seconds = max((now - observed).total_seconds(), 0.0)
    expected_lag_after = float(
        policy.get("business_expected_lag_after_seconds", policy["business_lagging_after_seconds"])
    )
    lagging_after = float(policy["business_lagging_after_seconds"])
    outdated_after = float(policy["business_outdated_after_seconds"])
    if _is_fx_proxy_provider_stale_suspect(source, age_seconds):
        status = "provider_stale_suspect"
        discount = -0.05
    elif age_seconds > outdated_after:
        status = "outdated"
        discount = -0.1
    elif age_seconds > lagging_after:
        status = "lagging"
        discount = -0.03
    elif age_seconds > expected_lag_after:
        status = "expected_lag"
        discount = 0.0
    else:
        status = "current"
        discount = 0.0
    return {
        "age_seconds": round(age_seconds, 3),
        "business_age_minutes": round(age_seconds / 60.0, 4),
        "expected_refresh_seconds": expected_seconds,
        "business_recency_status": status,
        "business_recency_discount": discount,
        "freshness_policy": policy,
    }


def _is_fx_proxy_provider_stale_suspect(
    source: SourceConfig | None,
    age_seconds: float,
) -> bool:
    if source is None:
        return False
    if source.source_id not in {"fred-usdjpy", "fred-usdcnh-proxy"}:
        return False
    # FX proxy providers should update on business days. Once the business
    # timestamp is more than a week behind, treat a successful scrape as a
    # provider-side stale snapshot rather than a clean expected lag.
    return age_seconds > 7 * 24 * 60 * 60


def _build_source_window(rows: list[schema.MetricValue]) -> HistoricalWindow | None:
    window = build_historical_window(rows)
    if window is None:
        return None
    source = _source_by_id(str(window.source_id)) if window.source_id else None
    observed_at = rows[0].ts if rows else None
    collected_at = (rows[0].updated_at or rows[0].created_at) if rows else None
    freshness = compute_collection_freshness(source, collected_at)
    business_recency = compute_business_recency(source, observed_at)
    window.age_seconds = freshness["age_seconds"]
    window.freshness_minutes = freshness["freshness_minutes"]
    window.stale_after_minutes = freshness["stale_after_minutes"]
    window.is_stale = freshness["is_stale"]
    window.expected_refresh_seconds = freshness["expected_refresh_seconds"]
    window.freshness_status = freshness["freshness_status"]
    window.freshness_discount = freshness["freshness_discount"]
    window.collection_age_seconds = freshness["age_seconds"]
    window.collection_freshness_status = freshness["freshness_status"]
    window.collection_freshness_discount = freshness["freshness_discount"]
    window.business_age_seconds = business_recency["age_seconds"]
    window.business_recency_status = business_recency["business_recency_status"]
    window.business_recency_discount = business_recency["business_recency_discount"]
    window.freshness_policy = business_recency["freshness_policy"]
    window.source_ts = observed_at.isoformat() if observed_at else None
    window.quality_score = _metric_source_quality(
        window.metric_id,
        str(window.source_id) if window.source_id else None,
        window.quality_score,
    )
    window.effective_quality_score = _apply_freshness_discount(
        window.quality_score,
        freshness,
    )
    return window


def _metric_rows_for_scope(
    session: Session,
    metric_id: str,
    source_id: str | None,
    limit: int,
    run_mode: str,
    collect_run_id: str | None,
    historical_fallback: bool,
) -> tuple[list[schema.MetricValue], str]:
    base_filters = [schema.MetricValue.metric_id == metric_id]
    if source_id:
        base_filters.append(schema.MetricValue.source_id == source_id)
    if run_mode != "all":
        base_filters.append(schema.MetricValue.run_mode == run_mode)

    if collect_run_id:
        current_rows = session.scalars(
            select(schema.MetricValue)
            .where(*base_filters, schema.MetricValue.run_id == collect_run_id)
            .order_by(schema.MetricValue.ts.desc())
            .limit(limit)
        ).all()
        if current_rows:
            historical_rows = session.scalars(
                select(schema.MetricValue)
                .where(*base_filters, schema.MetricValue.run_id != collect_run_id)
                .order_by(schema.MetricValue.ts.desc())
                .limit(limit)
            ).all()
            return [*current_rows, *historical_rows], "current_run"
        if not historical_fallback:
            return [], "missing"

    rows = session.scalars(
        select(schema.MetricValue)
        .where(*base_filters)
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    if rows:
        return rows, "historical_fallback" if collect_run_id else "unspecified_history"
    return [], "missing"


def _rows_for_collect_run_window(
    rows: list[schema.MetricValue],
    collect_run_id: str | None,
    limit: int,
) -> list[schema.MetricValue]:
    if not collect_run_id:
        return rows[:limit]
    current_rows = [row for row in rows if row.run_id == collect_run_id]
    if not current_rows:
        return rows[:limit]
    current_latest_ts = max(row.ts for row in current_rows)
    historical_rows = [
        row
        for row in rows
        if row.run_id != collect_run_id and row.ts < current_latest_ts
    ]
    scoped_rows = [*current_rows, *historical_rows]
    scoped_rows.sort(key=lambda row: row.ts, reverse=True)
    return scoped_rows[:limit]


def _annotate_window_run_scope(
    window: HistoricalWindow,
    feature_run_scope: str,
    collect_run_id: str | None,
    current_run_has_value: bool,
) -> None:
    fallback_age_seconds = None
    fallback_reason = None
    if collect_run_id and feature_run_scope == "historical_fallback":
        fallback_reason = "missing_current_collect_run_metric"
        if window.collected_at:
            fallback_age_seconds = max(
                (datetime.now(UTC) - _ensure_utc(window.collected_at)).total_seconds(),
                0.0,
            )
    window.feature_run_scope = feature_run_scope
    window.current_run_has_value = current_run_has_value
    window.fallback_age_seconds = (
        round(fallback_age_seconds, 3) if fallback_age_seconds is not None else None
    )
    window.fallback_reason = fallback_reason


def _window_arbitration_key(window: HistoricalWindow) -> tuple[int, int, int, float, float]:
    return (
        _freshness_rank(window.freshness_status),
        -_metric_source_priority(window.metric_id, window.source_id),
        _business_recency_rank(window.business_recency_status),
        float(window.effective_quality_score or 0.0),
        _latest_timestamp_score(window),
    )


def _window_candidate(window: HistoricalWindow, selected: bool) -> dict[str, Any]:
    return {
        "metric_id": window.metric_id,
        "source_id": window.source_id,
        "source_run_id": window.source_run_id,
        "source_ts": window.source_ts,
        "collected_at": window.collected_at.isoformat() if window.collected_at else None,
        "feature_run_scope": window.feature_run_scope,
        "current_run_has_value": window.current_run_has_value,
        "fallback_age_seconds": window.fallback_age_seconds,
        "fallback_reason": window.fallback_reason,
        "role": _candidate_role(window, selected),
        "value": window.current,
        "quality_score": window.quality_score,
        "effective_quality_score": window.effective_quality_score,
        "freshness_status": window.freshness_status,
        "collection_freshness_status": window.collection_freshness_status,
        "business_recency_status": window.business_recency_status,
        "freshness_policy": window.freshness_policy,
        "freshness_minutes": window.freshness_minutes,
        "stale_after_minutes": window.stale_after_minutes,
        "is_stale": window.is_stale,
        "source_priority": _metric_source_priority(window.metric_id, window.source_id),
        "is_fallback": window.is_fallback,
        "sample_count": window.sample_count,
    }


def _candidate_role(window: HistoricalWindow, selected: bool) -> str:
    if selected:
        return "selected"
    if window.freshness_status in {"fresh", "stale"}:
        return "fallback"
    return "cross_check"


def _source_conflict(
    selected: HistoricalWindow,
    windows: list[HistoricalWindow],
) -> dict[str, Any]:
    conflicts: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    selected_value = selected.current
    if selected_value in {None, 0}:
        return {"detected": False, "items": [], "suppressed_items": []}
    for window in windows:
        if window is selected or window.current is None:
            continue
        if window.freshness_status not in {"fresh", "stale"}:
            continue
        relative_diff = abs(float(window.current) - float(selected_value)) / abs(
            float(selected_value)
        )
        if relative_diff <= 0.02:
            continue
        conflict_type = _conflict_type(selected, window)
        suppressed_reason = _suppressed_conflict_reason(selected, window, conflict_type)
        if suppressed_reason:
            suppressed.append(
                {
                    "metric_id": selected.metric_id,
                    "primary_source": selected.source_id,
                    "conflicting_source": window.source_id,
                    "primary_value": selected_value,
                    "conflicting_value": window.current,
                    "relative_diff": round(relative_diff, 6),
                    "severity": _conflict_severity(relative_diff),
                    "type": conflict_type,
                    "suppressed_reason": suppressed_reason,
                    "user_action_required": False,
                }
            )
            continue
        conflicts.append(
            {
                "metric_id": selected.metric_id,
                "primary_source": selected.source_id,
                "conflicting_source": window.source_id,
                "primary_value": selected_value,
                "conflicting_value": window.current,
                "relative_diff": round(relative_diff, 6),
                "severity": _conflict_severity(relative_diff),
                "type": conflict_type,
                "user_action_required": False,
            }
        )
    return {
        "detected": bool(conflicts),
        "items": sorted(conflicts, key=lambda item: item["relative_diff"], reverse=True),
        "suppressed_items": sorted(
            suppressed,
            key=lambda item: item["relative_diff"],
            reverse=True,
        ),
    }


def _selected_reason(window: HistoricalWindow) -> str:
    return (
        f"freshness={window.freshness_status}; "
        f"business_recency={window.business_recency_status}; "
        f"effective_quality={window.effective_quality_score}; "
        f"priority={_metric_source_priority(window.metric_id, window.source_id)}; "
        f"policy={window.freshness_policy.get('cadence', 'unknown')}"
    )


def _freshness_rank(status: str | None) -> int:
    return {"fresh": 3, "stale": 2, "expired": 1, "missing": 0}.get(status or "missing", 0)


def _business_recency_rank(status: str | None) -> int:
    return {
        "current": 4,
        "expected_lag": 3,
        "lagging": 2,
        "provider_stale_suspect": 2,
        "outdated": 1,
        "unknown": 0,
    }.get(status or "unknown", 0)


def _source_priority(source_id: str | None) -> int:
    source = _source_by_id(source_id) if source_id else None
    return source.priority if source else 100


def _metric_source_priority(metric_id: str | None, source_id: str | None) -> int:
    override = _metric_source_override(metric_id, source_id)
    if "priority" in override:
        return int(override["priority"])
    return _source_priority(source_id)


def _latest_timestamp_score(window: HistoricalWindow) -> float:
    if window.age_seconds is None:
        return 0.0
    return -float(window.age_seconds)


def _conflict_severity(relative_diff: float) -> str:
    if relative_diff > 0.1:
        return "high"
    if relative_diff > 0.05:
        return "medium"
    return "low"


def _conflict_type(selected: HistoricalWindow, conflicting: HistoricalWindow) -> str:
    if selected.metric_id in {
        "lightning_capacity_btc",
        "lightning_channel_count",
        "lightning_node_count",
    }:
        return "definition_conflict"
    if selected.metric_id in _FED_TEXT_STREAM_METRICS and {
        selected.source_id,
        conflicting.source_id,
    } <= {"fed-rss-all-speeches", "fed-rss-all-testimony"}:
        return "event_stream_difference"
    if selected.business_recency_status != conflicting.business_recency_status:
        return "update_lag"
    return "value_conflict"


def _suppressed_conflict_reason(
    selected: HistoricalWindow,
    conflicting: HistoricalWindow,
    conflict_type: str,
) -> str | None:
    metric_id = str(selected.metric_id or "")
    source_pair = {str(selected.source_id or ""), str(conflicting.source_id or "")}
    if metric_id in _DEFINITION_VARIANT_METRICS:
        return "definition_variant_cross_check"
    if metric_id in _FED_TEXT_STREAM_METRICS and source_pair <= {
        "fed-rss-all-speeches",
        "fed-rss-all-testimony",
    }:
        return "event_stream_cross_check"
    if metric_id in {"wti_oil", "brent_oil", "dxy_proxy", "jgb_10y"}:
        return "primary_fallback_reference_delta"
    if metric_id == "jgb_10y" and float(conflicting.current or 0.0) <= 0.0:
        return "invalid_zero_cross_check"
    if conflict_type == "definition_conflict":
        return "definition_variant_cross_check"
    return None


def _error_result(
    source: SourceConfig,
    error: Exception,
    attempts: list[dict[str, Any]] | None = None,
) -> CollectionResult:
    message = _format_exception(error)
    return CollectionResult(
        source=source,
        raw={
            "source_id": source.source_id,
            "payload": {
                "error": message,
                "error_type": error.__class__.__name__,
                "error_category": _error_category(error, message),
                "collect_attempts": attempts or [],
                "attempt_count": len(attempts or []),
            },
            "status": SourceStatus.ERROR,
            "error_message": message,
        },
        metrics=[],
    )


def _generate_collect_run_id() -> str:
    return f"collect-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"


def _result_quality(result: CollectionResult) -> float:
    if result.raw.status == SourceStatus.ERROR:
        return 0.0
    if not result.metrics:
        return 0.45
    return min(metric.quality_score for metric in result.metrics)


def _upsert_metric_sample(
    session: Any,
    run_id: str,
    mode: SourceMode,
    sample: MetricSample,
) -> MetricSample:
    enriched = enrich_metric_sample(session, sample, run_mode=mode)
    metric_key = (enriched.metric_id, enriched.source_id, str(mode), enriched.ts)
    pending_metric_keys = session.info.setdefault("_metric_value_keys", set())
    if metric_key in pending_metric_keys:
        return enriched
    existing_value = session.scalar(
        select(schema.MetricValue).where(
            schema.MetricValue.metric_id == enriched.metric_id,
            schema.MetricValue.source_id == enriched.source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts == enriched.ts,
        )
    )
    if existing_value is None:
        session.add(
            schema.MetricValue(
                run_id=run_id,
                run_mode=mode,
                metric_id=enriched.metric_id,
                source_id=enriched.source_id,
                ts=enriched.ts,
                timeframe=enriched.timeframe,
                is_fallback=enriched.is_fallback,
                value=enriched.value,
                previous_value=enriched.previous_value,
                change_24h=enriched.change_24h,
                change_7d=enriched.change_7d,
                ma_30d=enriched.ma_30d,
                quality_score=enriched.quality_score,
            )
        )
        pending_metric_keys.add(metric_key)
    else:
        existing_value.value = enriched.value
        existing_value.timeframe = enriched.timeframe
        existing_value.is_fallback = enriched.is_fallback
        existing_value.previous_value = enriched.previous_value
        existing_value.change_24h = enriched.change_24h
        existing_value.change_7d = enriched.change_7d
        existing_value.ma_30d = enriched.ma_30d
        existing_value.quality_score = enriched.quality_score
        existing_value.run_id = run_id or existing_value.run_id
        existing_value.run_mode = mode
        pending_metric_keys.add(metric_key)
    return enriched


def _btc_total_state_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    if sample.metric_id != "btc_open_interest":
        return []
    changes = {
        "btc_oi_change_1h_pct": _metric_change_since(session, sample, mode, hours=1),
        "btc_oi_change_4h_pct": _metric_change_since(session, sample, mode, hours=4),
        "btc_oi_change_24h_pct": _metric_change_since(session, sample, mode, hours=24),
        "btc_oi_zscore": _metric_zscore(session, sample, mode, limit=30),
    }
    return [
        MetricSample(
            metric_id=metric_id,
            source_id=sample.source_id,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in changes.items()
    ]


def _metric_change_since(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
    hours: int,
) -> float:
    target_ts = sample.ts - timedelta(hours=hours)
    row = session.scalar(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == sample.metric_id,
            schema.MetricValue.source_id == sample.source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts <= target_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(1)
    )
    if row is None or not row.value:
        row = session.scalar(
            select(schema.MetricValue)
            .where(
                schema.MetricValue.metric_id == sample.metric_id,
                schema.MetricValue.source_id == sample.source_id,
                schema.MetricValue.run_mode == mode,
                schema.MetricValue.ts < sample.ts,
            )
            .order_by(schema.MetricValue.ts.desc())
            .limit(1)
        )
    if row is None or not row.value:
        return 0.0
    return (sample.value - row.value) / abs(row.value)


def _metric_point_change_since(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
    hours: int,
) -> float:
    target_ts = sample.ts - timedelta(hours=hours)
    row = session.scalar(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == sample.metric_id,
            schema.MetricValue.source_id == sample.source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts <= target_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(1)
    )
    if row is None or row.value is None:
        row = session.scalar(
            select(schema.MetricValue)
            .where(
                schema.MetricValue.metric_id == sample.metric_id,
                schema.MetricValue.source_id == sample.source_id,
                schema.MetricValue.run_mode == mode,
                schema.MetricValue.ts < sample.ts,
            )
            .order_by(schema.MetricValue.ts.desc())
            .limit(1)
        )
    if row is None or row.value is None:
        return 0.0
    return sample.value - row.value


def _metric_value_at_or_before(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    target_ts: datetime,
    *,
    source_id: str | None = None,
    before_ts: datetime | None = None,
) -> float | None:
    filters = [
        schema.MetricValue.metric_id == metric_id,
        schema.MetricValue.run_mode == mode,
        schema.MetricValue.ts <= target_ts,
    ]
    if source_id is not None:
        filters.append(schema.MetricValue.source_id == source_id)
    if before_ts is not None:
        filters.append(schema.MetricValue.ts < before_ts)
    row = session.scalar(
        select(schema.MetricValue)
        .where(*filters)
        .order_by(schema.MetricValue.ts.desc())
        .limit(1)
    )
    if row is None or row.value is None:
        return None
    return float(row.value)


def _yield_curve_2s10s_change_bps(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
    hours: int = 24,
) -> float | None:
    current_2y = _latest_metric_value(session, "treasury_2y", mode)
    if current_2y is None:
        return None
    target_ts = sample.ts - timedelta(hours=hours)
    previous_10y = _metric_value_at_or_before(
        session,
        "treasury_10y",
        mode,
        target_ts,
        source_id=sample.source_id,
        before_ts=sample.ts,
    )
    previous_2y = _metric_value_at_or_before(
        session,
        "treasury_2y",
        mode,
        target_ts,
        before_ts=sample.ts,
    )
    if previous_10y is None or previous_2y is None:
        return None
    current_curve = sample.value - current_2y
    previous_curve = previous_10y - previous_2y
    return (current_curve - previous_curve) * 100.0


def _metric_zscore(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
    limit: int,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == sample.metric_id,
            schema.MetricValue.source_id == sample.source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < sample.ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    values = [row.value for row in rows if row.value is not None]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = variance ** 0.5
    return (sample.value - mean) / std if std > 0 else 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(min(value, upper), lower)


def _metric_zscore_for_value(
    session: Any,
    metric_id: str,
    source_id: str,
    mode: SourceMode,
    current_value: float,
    before_ts: datetime,
    limit: int,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.source_id == source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    values = [float(row.value) for row in rows if row.value is not None]
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = variance ** 0.5
    return (current_value - mean) / std if std > 0 else 0.0


def _metric_percentile_for_value(
    session: Any,
    metric_id: str,
    source_id: str,
    mode: SourceMode,
    current_value: float,
    before_ts: datetime,
    limit: int,
) -> float | None:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.source_id == source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    values = sorted(float(row.value) for row in rows if row.value is not None)
    if len(values) < 20:
        return None
    below_or_equal = sum(1 for value in values if value <= current_value)
    return below_or_equal / len(values)


def _metric_rolling_sum(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
    limit: int,
    *,
    before_ts: datetime | None = None,
) -> float:
    cutoff = before_ts or sample.ts + timedelta(microseconds=1)
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == sample.metric_id,
            schema.MetricValue.source_id == sample.source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < cutoff,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    values = [float(row.value) for row in rows if row.value is not None]
    if before_ts is None and not any(row.ts == sample.ts for row in rows):
        values.insert(0, float(sample.value))
    return sum(values[:limit])


def _metric_rolling_sum_for_metric(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    ts: datetime,
    limit: int,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts <= ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    return sum(float(row.value) for row in rows if row.value is not None)


def _previous_metric_value(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> float | None:
    return _metric_value_at_or_before(
        session,
        sample.metric_id,
        mode,
        sample.ts,
        source_id=sample.source_id,
        before_ts=sample.ts,
    )


def _metric_abs_quantile(
    session: Any,
    metric_id: str,
    source_id: str,
    mode: SourceMode,
    before_ts: datetime,
    limit: int,
    quantile: float,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.source_id == source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    values = sorted(abs(float(row.value)) for row in rows if row.value is not None)
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * quantile))))
    return values[index]


def _metric_sign_streak(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
    *,
    positive: bool,
) -> int:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == sample.metric_id,
            schema.MetricValue.source_id == sample.source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts <= sample.ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(30)
    ).all()
    streak = 0
    for row in rows:
        value = float(row.value)
        if (positive and value > 0) or (not positive and value < 0):
            streak += 1
            continue
        break
    return streak


def _current_metric_values_by_source(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    ts: datetime,
) -> dict[str, float]:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts <= ts,
            schema.MetricValue.ts >= ts - timedelta(hours=36),
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(20)
    ).all()
    values: dict[str, float] = {}
    for row in rows:
        if row.source_id not in values and row.value is not None:
            values[row.source_id] = float(row.value)
    return values


def _current_source_count(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    ts: datetime,
) -> int:
    return len(_current_metric_values_by_source(session, metric_id, mode, ts))


def _current_source_diff_pct(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    ts: datetime,
) -> float:
    values = list(_current_metric_values_by_source(session, metric_id, mode, ts).values())
    if len(values) < 2:
        return 0.0
    denominator = max(sum(abs(value) for value in values) / len(values), 1.0)
    return (max(values) - min(values)) / denominator


def _metric_change_for_metric(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    ts: datetime,
    *,
    hours: int,
) -> float:
    current = _latest_metric_value(session, metric_id, mode)
    previous = _metric_value_at_or_before(
        session,
        metric_id,
        mode,
        ts - timedelta(hours=hours),
        before_ts=ts,
    )
    if current is None or previous in (None, 0):
        return 0.0
    return (float(current) - float(previous)) / abs(float(previous))


def _metric_change_zscore_for_metric(
    session: Any,
    metric_id: str,
    source_id: str,
    mode: SourceMode,
    current_change: float,
    before_ts: datetime,
    *,
    hours: int,
    limit: int,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.source_id == source_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    values: list[float] = []
    for row in rows:
        previous = _metric_value_at_or_before(
            session,
            metric_id,
            mode,
            row.ts - timedelta(hours=hours),
            source_id=source_id,
            before_ts=row.ts,
        )
        if previous in (None, 0):
            continue
        values.append((float(row.value) - float(previous)) / abs(float(previous)))
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    std = variance ** 0.5
    return (current_change - mean) / std if std > 0 else 0.0


def _value_change_against_previous_scalar(
    *,
    current: float,
    previous: float | None,
) -> float:
    if previous is None:
        return 0.0
    return current - float(previous)


def _latest_metric_row(
    session: Any,
    metric_id: str,
    mode: SourceMode,
) -> schema.MetricValue | None:
    return session.scalar(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.run_mode == mode,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(1)
    )


def _sample_from_latest_row(
    session: Any,
    metric_id: str,
    mode: SourceMode,
) -> MetricSample | None:
    row = _latest_metric_row(session, metric_id, mode)
    if row is None:
        return None
    return MetricSample(
        metric_id=row.metric_id,
        source_id=row.source_id,
        ts=row.ts,
        value=row.value,
        timeframe=row.timeframe,
        quality_score=row.quality_score,
    )


def _metric_rolling_average_for_metric(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    before_ts: datetime,
    *,
    limit: int,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts <= before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    values = [float(row.value) for row in rows if row.value is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _usd_liquidity_billions(metric_id: str, value: float | None) -> float | None:
    if value is None:
        return None
    if metric_id in {"fed_balance_sheet", "bank_reserves", "tga"}:
        return float(value) / 1000.0
    return float(value)


def _latest_usd_liquidity_bil(
    session: Any,
    metric_id: str,
    mode: SourceMode,
) -> float | None:
    return _usd_liquidity_billions(metric_id, _latest_metric_value(session, metric_id, mode))


def _usd_liquidity_value_at_or_before(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    target_ts: datetime,
) -> float | None:
    return _usd_liquidity_billions(
        metric_id,
        _metric_value_at_or_before(session, metric_id, mode, target_ts),
    )


def _net_liquidity_proxy_at(
    session: Any,
    mode: SourceMode,
    target_ts: datetime | None = None,
) -> float | None:
    if target_ts is None:
        fed = _latest_usd_liquidity_bil(session, "fed_balance_sheet", mode)
        tga = _latest_usd_liquidity_bil(session, "tga", mode)
        rrp = _latest_usd_liquidity_bil(session, "on_rrp", mode)
    else:
        fed = _usd_liquidity_value_at_or_before(session, "fed_balance_sheet", mode, target_ts)
        tga = _usd_liquidity_value_at_or_before(session, "tga", mode, target_ts)
        rrp = _usd_liquidity_value_at_or_before(session, "on_rrp", mode, target_ts)
    if fed is None or tga is None or rrp is None:
        return None
    return fed - tga - rrp


def _dollar_liquidity_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    derived_source = "dollar-liquidity-derived"
    source_metrics = {"fed_balance_sheet", "bank_reserves", "on_rrp", "sofr", "iorb", "tga", "btc_price"}
    if sample.metric_id not in source_metrics:
        return []

    changes: dict[str, float] = {}

    if sample.metric_id in {"fed_balance_sheet", "tga", "on_rrp", "bank_reserves"}:
        net = _net_liquidity_proxy_at(session, mode)
        if net is not None:
            changes["net_liquidity_proxy_bil"] = net
            net_1w = _net_liquidity_proxy_at(session, mode, sample.ts - timedelta(days=7))
            net_4w = _net_liquidity_proxy_at(session, mode, sample.ts - timedelta(days=28))
            if net_1w is not None:
                change_1w = net - net_1w
                changes["net_liquidity_change_1w_bil"] = change_1w
                changes["liquidity_impulse_z"] = _metric_zscore_for_value(
                    session,
                    "net_liquidity_change_1w_bil",
                    derived_source,
                    mode,
                    change_1w,
                    sample.ts,
                    52,
                )
                previous_net_1w = _net_liquidity_proxy_at(session, mode, sample.ts - timedelta(days=14))
                if previous_net_1w is not None:
                    changes["liquidity_acceleration"] = change_1w - (net_1w - previous_net_1w)
                else:
                    changes["liquidity_acceleration"] = 0.0
            else:
                changes["net_liquidity_change_1w_bil"] = 0.0
                changes["liquidity_impulse_z"] = 0.0
                changes["liquidity_acceleration"] = 0.0
            if net_4w is not None:
                changes["net_liquidity_change_4w_bil"] = net - net_4w
            else:
                changes["net_liquidity_change_4w_bil"] = 0.0

        reserves = _latest_usd_liquidity_bil(session, "bank_reserves", mode)
        reserves_1w = _usd_liquidity_value_at_or_before(
            session, "bank_reserves", mode, sample.ts - timedelta(days=7)
        )
        if reserves is not None and reserves_1w is not None:
            changes["reserve_change_1w_bil"] = reserves - reserves_1w
        elif reserves is not None:
            changes["reserve_change_1w_bil"] = 0.0

        tga = _latest_usd_liquidity_bil(session, "tga", mode)
        tga_1w = _usd_liquidity_value_at_or_before(session, "tga", mode, sample.ts - timedelta(days=7))
        if tga is not None and tga_1w is not None:
            changes["tga_change_1w_bil"] = tga - tga_1w
        elif tga is not None:
            changes["tga_change_1w_bil"] = 0.0

        rrp = _latest_usd_liquidity_bil(session, "on_rrp", mode)
        if rrp is not None:
            changes["rrp_depleted"] = 1.0 if rrp < 50.0 else 0.0

    if sample.metric_id in {"sofr", "iorb"}:
        sofr = _latest_metric_value(session, "sofr", mode)
        iorb = _latest_metric_value(session, "iorb", mode)
        if sofr is not None and iorb is not None:
            spread = (float(sofr) - float(iorb)) * 100.0
            changes["sofr_iorb_spread_bps"] = spread
            changes["funding_stress_z"] = _metric_zscore_for_value(
                session,
                "sofr_iorb_spread_bps",
                derived_source,
                mode,
                spread,
                sample.ts,
                252,
            )
        if sample.metric_id == "sofr":
            changes["sofr_jump_1d_bps"] = _metric_point_change_since(
                session, sample, mode, hours=24
            ) * 100.0

    if sample.metric_id == "btc_price":
        btc_1d = _metric_change_since(session, sample, mode, hours=24)
        btc_5d = _metric_change_since(session, sample, mode, hours=24 * 5)
        btc_20d = _metric_change_since(session, sample, mode, hours=24 * 20)
        changes["btc_1d_return"] = btc_1d
        changes["btc_5d_return"] = btc_5d
        changes["btc_20d_return"] = btc_20d
        liquidity_change = _latest_metric_value(session, "net_liquidity_change_1w_bil", mode) or 0.0
        expected = _clamp(liquidity_change / 1000.0, -0.08, 0.08)
        changes["btc_vs_liquidity_residual"] = btc_5d - expected

    return [
        MetricSample(
            metric_id=metric_id,
            source_id=derived_source,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in changes.items()
    ]


def _treasury_credit_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    derived_source = "treasury-credit-derived"
    source_metrics = {
        "treasury_2y",
        "treasury_10y",
        "treasury_30y",
        "real_yield_10y",
        "breakeven_10y",
        "hy_spread",
        "ig_oas",
        "btc_price",
        "btc_return_24h",
    }
    if sample.metric_id not in source_metrics:
        return []

    changes: dict[str, float] = {}

    if sample.metric_id in {"treasury_2y", "treasury_10y", "treasury_30y", "real_yield_10y", "breakeven_10y", "hy_spread"}:
        metric_prefix = {
            "treasury_2y": "treasury_2y",
            "treasury_10y": "treasury_10y",
            "treasury_30y": "treasury_30y",
            "real_yield_10y": "real_yield_10y",
            "breakeven_10y": "breakeven_10y",
            "hy_spread": "hy_oas",
        }[sample.metric_id]
        if sample.metric_id != "treasury_30y":
            changes[f"{metric_prefix}_change_1d_bps"] = _metric_point_change_since(
                session, sample, mode, hours=24
            ) * 100.0
        changes[f"{metric_prefix}_change_3d_bps" if sample.metric_id != "hy_spread" else "hy_oas_change_5d_bps"] = (
            _metric_point_change_since(
                session,
                sample,
                mode,
                hours=72 if sample.metric_id != "hy_spread" else 24 * 5,
            )
            * 100.0
        )
        if sample.metric_id in {"treasury_2y", "treasury_10y", "real_yield_10y", "hy_spread"}:
            z_key = {
                "treasury_2y": "treasury_2y_z_60d",
                "treasury_10y": "treasury_10y_z_60d",
                "real_yield_10y": "real_yield_10y_z_60d",
                "hy_spread": "hy_oas_z_60d",
            }[sample.metric_id]
            changes[z_key] = _metric_zscore(session, sample, mode, limit=60)
        if sample.metric_id == "hy_spread":
            percentile = _metric_percentile_for_value(
                session,
                sample.metric_id,
                sample.source_id,
                mode,
                sample.value,
                sample.ts,
                252,
            )
            if percentile is not None:
                changes["hy_oas_percentile_252d"] = percentile

    treasury_2y = _latest_metric_value(session, "treasury_2y", mode)
    treasury_10y = _latest_metric_value(session, "treasury_10y", mode)
    treasury_30y = _latest_metric_value(session, "treasury_30y", mode)
    if treasury_2y is not None and treasury_10y is not None:
        changes["yield_curve_2s10s_bps"] = (float(treasury_10y) - float(treasury_2y)) * 100.0
        curve_1d = _curve_change_bps_since(
            session,
            mode,
            short_metric="treasury_2y",
            long_metric="treasury_10y",
            current_short=float(treasury_2y),
            current_long=float(treasury_10y),
            sample_ts=sample.ts,
            hours=24,
        )
        curve_5d = _curve_change_bps_since(
            session,
            mode,
            short_metric="treasury_2y",
            long_metric="treasury_10y",
            current_short=float(treasury_2y),
            current_long=float(treasury_10y),
            sample_ts=sample.ts,
            hours=24 * 5,
        )
        if curve_1d is not None:
            changes["curve_2s10s_change_1d_bps"] = curve_1d
        if curve_5d is not None:
            changes["curve_2s10s_change_5d_bps"] = curve_5d
    if treasury_10y is not None and treasury_30y is not None:
        changes["yield_curve_10s30s_bps"] = (float(treasury_30y) - float(treasury_10y)) * 100.0

    if sample.metric_id in {"btc_price", "btc_return_24h"}:
        btc_return_24h = _latest_metric_value(session, "btc_return_24h", mode)
        if btc_return_24h is None and sample.metric_id == "btc_price":
            btc_return_24h = _metric_change_since(session, sample, mode, hours=24)
        nasdaq_return = _latest_metric_value(session, "nasdaq_return_24h_pct", mode) or 0.0
        spx_return = _latest_metric_value(session, "sp500_return_24h_pct", mode) or 0.0
        real_yield_change = _latest_metric_value(session, "real_yield_10y_change_1d_bps", mode) or 0.0
        dxy_change = _latest_metric_value(session, "dxy_change_24h_pct", mode) or 0.0
        hy_change_5d = _latest_metric_value(session, "hy_oas_change_5d_bps", mode) or 0.0
        expected = (
            0.75 * float(nasdaq_return)
            + 0.35 * float(spx_return)
            - 0.00025 * float(real_yield_change)
            - 0.50 * float(dxy_change)
        )
        btc_return = float(btc_return_24h or 0.0)
        residual = btc_return - expected
        changes["btc_expected_return_24h"] = expected
        changes["btc_residual_24h"] = residual
        changes["btc_vs_rates_residual_24h"] = btc_return + 0.00025 * float(real_yield_change)
        btc_3d = _latest_metric_value(session, "btc_return_3d_pct", mode)
        if btc_3d is None and sample.metric_id == "btc_price":
            btc_3d = _metric_change_since(session, sample, mode, hours=72)
        changes["btc_vs_credit_residual_3d"] = float(btc_3d or 0.0) + 0.00015 * float(hy_change_5d)
        changes["btc_residual_z_60d"] = _metric_zscore_for_value(
            session,
            "btc_residual_24h",
            derived_source,
            mode,
            residual,
            sample.ts,
            60,
        )

    return [
        MetricSample(
            metric_id=metric_id,
            source_id=derived_source,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in changes.items()
    ]


def _curve_change_bps_since(
    session: Any,
    mode: SourceMode,
    *,
    short_metric: str,
    long_metric: str,
    current_short: float,
    current_long: float,
    sample_ts: datetime,
    hours: int,
) -> float | None:
    target_ts = sample_ts - timedelta(hours=hours)
    previous_short = _metric_value_at_or_before(session, short_metric, mode, target_ts, before_ts=sample_ts)
    previous_long = _metric_value_at_or_before(session, long_metric, mode, target_ts, before_ts=sample_ts)
    if previous_short is None or previous_long is None:
        return None
    return ((current_long - current_short) - (previous_long - previous_short)) * 100.0


def _backfill_dollar_liquidity_derived_metrics(
    session: Any,
    run_id: str,
    mode: SourceMode,
) -> None:
    source_metrics = ("fed_balance_sheet", "bank_reserves", "on_rrp", "sofr", "iorb", "tga", "btc_price")
    for metric_id in source_metrics:
        row = _latest_metric_row(session, metric_id, mode)
        if row is None:
            continue
        sample = MetricSample(
            metric_id=row.metric_id,
            source_id=row.source_id,
            ts=row.ts,
            value=row.value,
            timeframe=row.timeframe,
            quality_score=row.quality_score,
        )
        for derived in _dollar_liquidity_derived_samples(session, sample, mode):
            _upsert_metric_sample(session, run_id, mode, derived)


def _backfill_treasury_credit_derived_metrics(
    session: Any,
    run_id: str,
    mode: SourceMode,
) -> None:
    source_metrics = (
        "treasury_2y",
        "treasury_10y",
        "treasury_30y",
        "real_yield_10y",
        "breakeven_10y",
        "hy_spread",
        "ig_oas",
        "btc_price",
        "btc_return_24h",
    )
    for metric_id in source_metrics:
        row = _latest_metric_row(session, metric_id, mode)
        if row is None:
            continue
        sample = MetricSample(
            metric_id=row.metric_id,
            source_id=row.source_id,
            ts=row.ts,
            value=row.value,
            timeframe=row.timeframe,
            quality_score=row.quality_score,
        )
        for derived in _treasury_credit_derived_samples(session, sample, mode):
            _upsert_metric_sample(session, run_id, mode, derived)


def _backfill_fund_flow_derived_metrics(
    session: Any,
    run_id: str,
    mode: SourceMode,
) -> None:
    source_metrics = (
        "etf_net_flow",
        "etf_flow_7d",
        "stablecoin_supply",
        "stablecoin_buying_power_proxy",
        "exchange_balance_delta_1d_proxy",
        "btc_price",
        "btc_return_4h",
        "btc_return_24h",
        "exchange_spot_volume",
    )
    for metric_id in source_metrics:
        row = _latest_metric_row(session, metric_id, mode)
        if row is None:
            continue
        sample = MetricSample(
            metric_id=row.metric_id,
            source_id=row.source_id,
            ts=row.ts,
            value=row.value,
            timeframe=row.timeframe,
            quality_score=row.quality_score,
        )
        for derived in _fund_flow_derived_samples(session, sample, mode):
            _upsert_metric_sample(session, run_id, mode, derived)


def _backfill_onchain_valuation_derived_metrics(
    session: Any,
    run_id: str,
    mode: SourceMode,
) -> None:
    source_metrics = (
        "btc_price",
        "btc_return_24h",
        "mvrv_zscore",
        "nupl",
        "sopr",
        "realized_price",
        "cap_real_usd",
        "supply_current",
        "sth_cost_basis",
        "lth_cost_basis",
        "btc_hashrate",
    )
    for metric_id in source_metrics:
        row = _latest_metric_row(session, metric_id, mode)
        if row is None:
            continue
        sample = MetricSample(
            metric_id=row.metric_id,
            source_id=row.source_id,
            ts=row.ts,
            value=row.value,
            timeframe=row.timeframe,
            quality_score=row.quality_score,
        )
        for derived in _onchain_valuation_derived_samples(session, sample, mode):
            _upsert_metric_sample(session, run_id, mode, derived)


def _backfill_btc_adoption_derived_metrics(
    session: Any,
    run_id: str,
    mode: SourceMode,
) -> None:
    source_metrics = (
        "active_addresses",
        "transaction_count",
        "transfer_volume_adjusted_usd",
        "btc_price",
        "supply_current",
        "btc_return_4h",
        "btc_return_24h",
        "btc_hashrate",
        "hashrate_90d_ehs",
        "hash_price_usd",
        "avg_fees_per_block_btc",
        "fees_vs_reward_pct",
        "mempool_tx_count",
        "mempool_vsize_mb",
        "mempool_min_fee_rate_sat_vb",
        "lightning_capacity_btc",
        "lightning_node_count",
        "lightning_channel_count",
        "bitcoin_reachable_nodes",
    )
    for metric_id in source_metrics:
        row = _latest_metric_row(session, metric_id, mode)
        if row is None:
            continue
        sample = MetricSample(
            metric_id=row.metric_id,
            source_id=row.source_id,
            ts=row.ts,
            value=row.value,
            timeframe=row.timeframe,
            quality_score=row.quality_score,
        )
        for derived in _btc_adoption_derived_samples(session, sample, mode):
            _upsert_metric_sample(session, run_id, mode, derived)


def _backfill_asia_risk_derived_metrics(
    session: Any,
    run_id: str,
    mode: SourceMode,
) -> None:
    source_metrics = (
        "btc_price",
        "btc_return_4h",
        "btc_return_24h",
        "btc_4h_return_pct",
        "btc_24h_return_pct",
        "btc_1h_close",
        "btc_1h_high",
        "btc_1h_low",
        "btc_1h_volume",
        "usdjpy",
        "usdcnh",
        "jgb_10y",
        "nikkei",
        "topix",
        "hang_seng_tech",
        "hibor",
        "korea_premium_index",
        "hk_btc_etf_flow",
    )
    for metric_id in source_metrics:
        row = _latest_metric_row(session, metric_id, mode)
        if row is None:
            continue
        sample = MetricSample(
            metric_id=row.metric_id,
            source_id=row.source_id,
            ts=row.ts,
            value=row.value,
            timeframe=row.timeframe,
            quality_score=row.quality_score,
        )
        for derived in _asia_risk_derived_samples(session, sample, mode):
            _upsert_metric_sample(session, run_id, mode, derived)


def _crypto_breadth_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    derived_source = "crypto-breadth-derived"
    changes: dict[str, float] = {}

    if sample.metric_id == "btc_price":
        changes["btc_return_3d_pct"] = _metric_change_since(session, sample, mode, hours=72)
        changes["btc_vol_adjusted_return_24h_z"] = _metric_zscore(session, sample, mode, limit=30)
    elif sample.metric_id == "btc_return_24h":
        changes["btc_return_24h_pct"] = sample.value
    elif sample.metric_id == "top50_strength":
        changes["top50_advance_pct_24h"] = sample.value
        changes["top50_advance_pct_3d"] = _metric_point_change_since(
            session, sample, mode, hours=72
        )
        changes["top50_ad_line_7d_slope"] = _metric_point_change_since(
            session, sample, mode, hours=168
        )
    elif sample.metric_id == "total_market_cap":
        changes["total_return_24h_pct"] = _metric_change_since(
            session, sample, mode, hours=24
        )
    elif sample.metric_id == "total2_market_cap":
        total2_return_24h = _metric_change_since(session, sample, mode, hours=24)
        changes["total2_return_24h_pct"] = total2_return_24h
        changes["total2_return_3d_pct"] = _metric_change_since(session, sample, mode, hours=72)
        btc_return = _latest_metric_value(session, "btc_return_24h", mode)
        if btc_return is None:
            btc_return = _latest_metric_value(session, "btc_24h_return_pct", mode)
        changes["total2_vs_btc_return_24h_pct"] = total2_return_24h - float(btc_return or 0.0)
    elif sample.metric_id == "btc_dominance":
        changes["btc_dominance_change_24h_pp"] = _metric_point_change_since(
            session, sample, mode, hours=24
        )
        changes["btc_dominance_change_3d_pp"] = _metric_point_change_since(
            session, sample, mode, hours=72
        )
    elif sample.metric_id == "eth_btc":
        changes["eth_btc_return_24h_pct"] = _metric_change_since(
            session, sample, mode, hours=24
        )
        changes["eth_btc_return_3d_pct"] = _metric_change_since(
            session, sample, mode, hours=72
        )
    elif sample.metric_id == "sector_heat":
        changes["sector_heat_change_24h"] = _metric_point_change_since(
            session, sample, mode, hours=24
        )
        changes["overheat_penalty"] = max((sample.value - 80.0) / 100.0, 0.0)

    return [
        MetricSample(
            metric_id=metric_id,
            source_id=derived_source,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in changes.items()
    ]


def _macro_radar_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    derived_source = "macro-radar-derived"
    changes: dict[str, float] = {}

    if sample.metric_id == "nasdaq":
        changes["nasdaq_return_24h_pct"] = _metric_change_since(
            session, sample, mode, hours=24
        )
    elif sample.metric_id == "sp500":
        changes["sp500_return_24h_pct"] = _metric_change_since(
            session, sample, mode, hours=24
        )
    elif sample.metric_id == "russell_2000":
        changes["russell_return_24h_pct"] = _metric_change_since(
            session, sample, mode, hours=24
        )
    elif sample.metric_id == "treasury_2y":
        change = _metric_point_change_since(session, sample, mode, hours=24) * 100.0
        changes["us2y_change_1d_bps"] = change
        changes["rates_impulse_z"] = _metric_zscore(session, sample, mode, limit=60)
    elif sample.metric_id == "treasury_10y":
        changes["us10y_change_1d_bps"] = (
            _metric_point_change_since(session, sample, mode, hours=24) * 100.0
        )
        changes["us10y_change_3d_bps"] = (
            _metric_point_change_since(session, sample, mode, hours=72) * 100.0
        )
        curve_change = _yield_curve_2s10s_change_bps(session, sample, mode, hours=24)
        if curve_change is not None:
            changes["yield_curve_2s10s_change_bps"] = curve_change
    elif sample.metric_id == "real_yield_10y":
        changes["real_yield_change_1d_bps"] = (
            _metric_point_change_since(session, sample, mode, hours=24) * 100.0
        )
    elif sample.metric_id == "dxy_proxy":
        changes["dxy_change_1h_pct"] = _metric_change_since(session, sample, mode, hours=1)
        changes["dxy_change_4h_pct"] = _metric_change_since(session, sample, mode, hours=4)
        changes["dxy_change_24h_pct"] = _metric_change_since(
            session, sample, mode, hours=24
        )
        changes["dxy_impulse_z"] = _metric_zscore(session, sample, mode, limit=60)
    elif sample.metric_id == "vix":
        changes["vix_change_1d_pct"] = _metric_change_since(session, sample, mode, hours=24)
        changes["vix_change_3d_pct"] = _metric_change_since(session, sample, mode, hours=72)
        changes["vix_zscore_60d"] = _metric_zscore(session, sample, mode, limit=60)
        changes["vix_impulse_z"] = _metric_zscore(session, sample, mode, limit=30)
    elif sample.metric_id == "ofr_fsi":
        changes["ofr_fsi_change_1d"] = _metric_point_change_since(
            session, sample, mode, hours=24
        )
        changes["ofr_fsi_zscore_252d"] = _metric_zscore(session, sample, mode, limit=252)
    elif sample.metric_id in {"btc_return_1h", "btc_return_4h", "btc_return_24h"}:
        if sample.metric_id == "btc_return_1h":
            changes["btc_return_1h_pct"] = sample.value
        elif sample.metric_id == "btc_return_4h":
            changes["btc_return_4h_pct"] = sample.value
        elif sample.metric_id == "btc_return_24h":
            changes["btc_return_24h_pct"] = sample.value

    if sample.metric_id == "sp500":
        btc_return = _latest_metric_value(session, "btc_return_24h", mode)
        if btc_return is None:
            btc_return = _latest_metric_value(session, "btc_24h_return_pct", mode)
        ndx_return = _latest_metric_value(session, "nasdaq_return_24h_pct", mode)
        spx_return = _latest_metric_value(session, "sp500_return_24h_pct", mode)
        if changes.get("sp500_return_24h_pct") is not None:
            spx_return = changes["sp500_return_24h_pct"]
        if btc_return is not None and ndx_return is not None:
            changes["btc_vs_ndx_relative_return"] = float(btc_return) - float(ndx_return)
        if btc_return is not None and spx_return is not None:
            changes["btc_vs_spx_relative_return"] = float(btc_return) - float(spx_return)
        if btc_return is not None and (ndx_return is not None or spx_return is not None):
            macro_beta = 0.0
            macro_weight = 0.0
            if ndx_return is not None:
                macro_beta += 1.25 * float(ndx_return)
                macro_weight += 1.0
            if spx_return is not None:
                macro_beta += 1.0 * float(spx_return)
                macro_weight += 1.0
            expected = macro_beta / macro_weight if macro_weight else 0.0
            changes["btc_beta_residual"] = float(btc_return) - expected
            changes["btc_macro_follow_through"] = 1.0 if float(btc_return) * expected > 0 else 0.0

    if sample.metric_id == "russell_2000":
        ndx = _latest_metric_value(session, "nasdaq_return_24h_pct", mode)
        spx = _latest_metric_value(session, "sp500_return_24h_pct", mode)
        rut = _latest_metric_value(session, "russell_return_24h_pct", mode)
        if changes.get("russell_return_24h_pct") is not None:
            rut = changes["russell_return_24h_pct"]
        equity_returns = [value for value in (ndx, spx, rut) if value is not None]
        if equity_returns:
            positive = sum(1 for value in equity_returns if float(value) > 0)
            changes["equity_breadth_score"] = positive / len(equity_returns)

    return [
        MetricSample(
            metric_id=metric_id,
            source_id=derived_source,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in changes.items()
    ]


def _fund_flow_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    derived_source = "fund-flow-derived"
    changes: dict[str, float] = {}

    if sample.metric_id == "etf_net_flow":
        changes.update(_fund_flow_etf_derived_values(session, sample, mode))
    elif sample.metric_id in {"stablecoin_supply", "stablecoin_buying_power_proxy"}:
        changes.update(_fund_flow_stablecoin_derived_values(session, sample, mode))
    elif sample.metric_id == "exchange_balance_delta_1d_proxy":
        changes.update(_fund_flow_exchange_supply_values(session, sample, mode))
    elif sample.metric_id in {
        "btc_price",
        "btc_return_4h",
        "btc_return_24h",
        "exchange_spot_volume",
    }:
        changes.update(_fund_flow_btc_response_values(session, sample, mode))

    return [
        MetricSample(
            metric_id=metric_id,
            source_id=derived_source,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in changes.items()
        if value is not None
    ]


def _btc_adoption_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    source_metrics = {
        "active_addresses",
        "transaction_count",
        "transfer_volume_adjusted_usd",
        "btc_price",
        "supply_current",
        "btc_return_4h",
        "btc_return_24h",
        "btc_hashrate",
        "hashrate_90d_ehs",
        "hash_price_usd",
        "avg_fees_per_block_btc",
        "fees_vs_reward_pct",
        "mempool_tx_count",
        "mempool_vsize_mb",
        "mempool_min_fee_rate_sat_vb",
        "lightning_capacity_btc",
        "lightning_node_count",
        "lightning_channel_count",
        "bitcoin_reachable_nodes",
    }
    if sample.metric_id not in source_metrics:
        return []

    values = _btc_adoption_derived_values(session, sample, mode)
    return [
        MetricSample(
            metric_id=metric_id,
            source_id="btc-adoption-derived",
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in values.items()
        if value is not None
    ]


def _asia_risk_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    source_metrics = {
        "btc_price",
        "btc_return_4h",
        "btc_return_24h",
        "btc_4h_return_pct",
        "btc_24h_return_pct",
        "btc_1h_close",
        "btc_1h_high",
        "btc_1h_low",
        "btc_1h_volume",
        "usdjpy",
        "usdcnh",
        "jgb_10y",
        "nikkei",
        "topix",
        "hang_seng_tech",
        "hibor",
        "korea_premium_index",
        "hk_btc_etf_flow",
    }
    if sample.metric_id not in source_metrics:
        return []
    values = _asia_risk_derived_values(session, sample, mode)
    return [
        MetricSample(
            metric_id=metric_id,
            source_id="asia-risk-derived",
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in values.items()
        if value is not None
    ]


def _asia_risk_derived_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> dict[str, float]:
    values: dict[str, float] = {}
    btc_4h = float(
        _latest_metric_value(session, "btc_return_4h", mode)
        or _latest_metric_value(session, "btc_4h_return_pct", mode)
        or _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=4)
        or 0.0
    )
    btc_8h = _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=8)
    btc_24h = float(
        _latest_metric_value(session, "btc_return_24h", mode)
        or _latest_metric_value(session, "btc_24h_return_pct", mode)
        or _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=24)
        or 0.0
    )
    btc_price = float(_latest_metric_value(session, "btc_price", mode) or 0.0)
    btc_1h_close = float(_latest_metric_value(session, "btc_1h_close", mode) or btc_price or 0.0)
    btc_1h_high = float(_latest_metric_value(session, "btc_1h_high", mode) or btc_1h_close or 0.0)
    btc_1h_low = float(_latest_metric_value(session, "btc_1h_low", mode) or btc_1h_close or 0.0)
    btc_1h_volume = float(_latest_metric_value(session, "btc_1h_volume", mode) or 0.0)

    return_4h_z = _metric_zscore_for_value(
        session, "asia_session_btc_return_4h", "asia-risk-derived", mode, btc_4h, sample.ts, limit=30
    )
    return_8h_z = _metric_zscore_for_value(
        session, "asia_session_btc_return_8h", "asia-risk-derived", mode, btc_8h, sample.ts, limit=30
    )
    realized_vol = abs(btc_4h) + abs(btc_8h) * 0.5
    realized_vol_z = _metric_zscore_for_value(
        session,
        "asia_session_btc_realized_vol_z_30d",
        "asia-risk-derived",
        mode,
        realized_vol,
        sample.ts,
        limit=30,
    )
    downside_vol = realized_vol if btc_8h < 0 or btc_24h < 0 else 0.0
    downside_vol_z = _metric_zscore_for_value(
        session,
        "asia_session_downside_vol_z_30d",
        "asia-risk-derived",
        mode,
        downside_vol,
        sample.ts,
        limit=30,
    )
    volume_z = _metric_zscore_for_value(
        session,
        "btc_1h_volume",
        "binance-btcusdt-kline-1h",
        mode,
        btc_1h_volume,
        sample.ts,
        limit=30,
    )
    range_width = max(btc_1h_high - btc_1h_low, abs(btc_1h_close) * 0.0001, 1.0)
    range_position = _clamp((btc_1h_close - btc_1h_low) / range_width, 0.0, 1.0)
    vwap_distance = btc_4h
    vwap_distance_z = _metric_zscore_for_value(
        session,
        "asia_session_vwap_distance_z",
        "asia-risk-derived",
        mode,
        vwap_distance,
        sample.ts,
        limit=30,
    )
    high_break = 1.0 if _latest_metric_value(session, "btc_breakout_24h_high", mode) else 0.0
    low_break = 1.0 if _latest_metric_value(session, "btc_breakdown_24h_low", mode) else 0.0
    asia_trend_score = _clamp(
        30.0 * return_8h_z
        + 20.0 * vwap_distance_z
        + 40.0 * (range_position - 0.5)
        + 10.0 * volume_z * (1.0 if btc_8h >= 0 else -1.0),
        -100.0,
        100.0,
    )

    usdjpy_return_4h = _metric_change_for_metric(session, "usdjpy", mode, sample.ts, hours=4)
    usdjpy_return_24h = _metric_change_for_metric(session, "usdjpy", mode, sample.ts, hours=24)
    usdjpy_return_z = _metric_zscore_for_value(
        session, "usdjpy_return_24h", "asia-risk-derived", mode, usdjpy_return_24h, sample.ts, limit=60
    )
    jpy_strength_shock_z = _metric_zscore_for_value(
        session, "jpy_strength_shock_z", "asia-risk-derived", mode, -usdjpy_return_24h, sample.ts, limit=60
    )
    jgb_change = _metric_change_for_metric(session, "jgb_10y", mode, sample.ts, hours=24)
    jgb_yield_shock_z = _metric_zscore_for_value(
        session, "jgb_yield_shock_z", "asia-risk-derived", mode, jgb_change, sample.ts, limit=60
    )
    nikkei_return = _metric_change_for_metric(session, "nikkei", mode, sample.ts, hours=24)
    nikkei_downside_z = _metric_zscore_for_value(
        session, "nikkei_downside_z", "asia-risk-derived", mode, -nikkei_return, sample.ts, limit=60
    )
    jpy_carry_pressure = _clamp(
        100.0
        * (
            0.40 * max(0.0, jpy_strength_shock_z)
            + 0.25 * max(0.0, nikkei_downside_z)
            + 0.20 * max(0.0, jgb_yield_shock_z)
            + 0.15 * max(0.0, realized_vol_z)
        )
        / 2.5,
        0.0,
        100.0,
    )

    usdcnh_return_4h = _metric_change_for_metric(session, "usdcnh", mode, sample.ts, hours=4)
    usdcnh_return_24h = _metric_change_for_metric(session, "usdcnh", mode, sample.ts, hours=24)
    usdcnh_return_z = _metric_zscore_for_value(
        session, "usdcnh_return_24h", "asia-risk-derived", mode, usdcnh_return_24h, sample.ts, limit=60
    )
    hstech_return = _metric_change_for_metric(session, "hang_seng_tech", mode, sample.ts, hours=24)
    hstech_downside_z = _metric_zscore_for_value(
        session, "hstech_downside_z", "asia-risk-derived", mode, -hstech_return, sample.ts, limit=60
    )
    hsi_return = _metric_change_for_metric(session, "topix", mode, sample.ts, hours=24)
    hsi_downside_z = _metric_zscore_for_value(
        session, "hsi_downside_z", "asia-risk-derived", mode, -hsi_return, sample.ts, limit=60
    )
    cnh_pressure = _clamp(
        100.0
        * (
            0.45 * max(0.0, usdcnh_return_z)
            + 0.30 * max(0.0, hstech_downside_z)
            + 0.15 * max(0.0, hsi_downside_z)
            + 0.10 * max(0.0, downside_vol_z)
        )
        / 2.5,
        0.0,
        100.0,
    )
    equity_downside_pressure = _clamp(
        100.0 * (0.55 * max(0.0, nikkei_downside_z) + 0.45 * max(0.0, hstech_downside_z)) / 2.5,
        0.0,
        100.0,
    )
    hibor_stress = max(0.0, _metric_change_for_metric(session, "hibor", mode, sample.ts, hours=24)) * 100.0
    risk_off_pressure = _clamp(
        0.35 * jpy_carry_pressure
        + 0.30 * cnh_pressure
        + 0.20 * equity_downside_pressure
        + 0.15 * _clamp(hibor_stress, 0.0, 100.0),
        0.0,
        100.0,
    )

    korea_premium = float(_latest_metric_value(session, "korea_premium_index", mode) or 0.0)
    korea_premium_z = _metric_zscore_for_value(
        session, "korea_premium_index", "asia-risk-derived", mode, korea_premium, sample.ts, limit=90
    )
    korea_premium_change_24h = _metric_change_for_metric(session, "korea_premium_index", mode, sample.ts, hours=24)
    korea_premium_change_24h_z = _metric_zscore_for_value(
        session,
        "korea_premium_change_24h_z",
        "asia-risk-derived",
        mode,
        korea_premium_change_24h,
        sample.ts,
        limit=90,
    )
    korea_premium_change_3d = _metric_change_for_metric(session, "korea_premium_index", mode, sample.ts, hours=72)
    korea_premium_change_3d_z = _metric_zscore_for_value(
        session, "korea_premium_change_3d_z", "asia-risk-derived", mode, korea_premium_change_3d, sample.ts, limit=90
    )
    if korea_premium_change_24h_z <= -1.5 and btc_24h <= 0:
        premium_state = -2.0
    elif korea_premium_z >= 2.0 and btc_24h <= 0:
        premium_state = -1.0
    elif korea_premium_z >= 2.0:
        premium_state = 2.0
    elif 0.3 <= korea_premium_z <= 1.5 and btc_24h > 0 and volume_z > 0:
        premium_state = 1.0
    elif korea_premium_z < -0.5:
        premium_state = -0.5
    else:
        premium_state = 0.0
    hk_etf_flow = float(_latest_metric_value(session, "hk_btc_etf_flow", mode) or 0.0)
    hk_etf_flow_1d_z = _metric_zscore_for_value(
        session, "hk_btc_etf_flow", "asia-risk-derived", mode, hk_etf_flow, sample.ts, limit=60
    )
    hk_etf_flow_5d = _metric_rolling_sum_for_metric(session, "hk_btc_etf_flow", mode, sample.ts, limit=5)
    hk_etf_flow_5d_z = _metric_zscore_for_value(
        session, "hk_btc_etf_flow_5d_z", "asia-risk-derived", mode, hk_etf_flow_5d, sample.ts, limit=60
    )
    premium_score = 45.0 if premium_state == 1.0 else 20.0 if premium_state == 2.0 else -35.0 if premium_state < 0 else 0.0
    regional_demand_score = _clamp(
        0.40 * premium_score + 0.35 * (20.0 * hk_etf_flow_5d_z) + 0.25 * (20.0 * volume_z),
        -100.0,
        100.0,
    )
    expected = _clamp(
        0.00025 * asia_trend_score
        + 0.00015 * regional_demand_score
        - 0.00020 * risk_off_pressure,
        -0.08,
        0.08,
    )
    residual = btc_24h - expected
    residual_z = _metric_zscore_for_value(
        session, "asia_risk_residual_24h", "asia-risk-derived", mode, residual, sample.ts, limit=90
    )
    btc_response_score = _clamp(
        35.0 * residual_z + 0.35 * asia_trend_score + (12.0 if low_break <= 0 and btc_8h >= 0 else -12.0 if low_break >= 1 else 0.0),
        -100.0,
        100.0,
    )
    values.update(
        {
            "asia_session_btc_return_4h": btc_4h,
            "asia_session_btc_return_8h": btc_8h,
            "asia_session_btc_return_24h": btc_24h,
            "asia_session_btc_return_4h_z": return_4h_z,
            "asia_session_btc_return_8h_z": return_8h_z,
            "asia_session_btc_volume_z_30d": volume_z,
            "asia_session_btc_realized_vol_z_30d": realized_vol_z,
            "asia_session_downside_vol_z_30d": downside_vol_z,
            "asia_session_high_break_flag": high_break,
            "asia_session_low_break_flag": low_break,
            "asia_session_vwap_distance_z": vwap_distance_z,
            "asia_session_range_position": range_position,
            "asia_vs_us_session_return_spread": btc_8h - (btc_24h - btc_8h),
            "asia_vs_eu_us_volume_share": _clamp(abs(volume_z) / 5.0, 0.0, 1.0),
            "asia_session_trend_score": asia_trend_score,
            "usdjpy_return_4h": usdjpy_return_4h,
            "usdjpy_return_24h": usdjpy_return_24h,
            "usdjpy_return_z_60d": usdjpy_return_z,
            "jpy_strength_shock_z": jpy_strength_shock_z,
            "jgb_yield_shock_z": jgb_yield_shock_z,
            "nikkei_downside_z": nikkei_downside_z,
            "jpy_carry_unwind_pressure": jpy_carry_pressure,
            "usdcnh_return_4h": usdcnh_return_4h,
            "usdcnh_return_24h": usdcnh_return_24h,
            "usdcnh_return_z_60d": usdcnh_return_z,
            "hstech_return_1d": hstech_return,
            "hsi_return_1d": hsi_return,
            "cnh_devaluation_pressure": cnh_pressure,
            "asia_equity_downside_pressure": equity_downside_pressure,
            "risk_off_pressure_score": risk_off_pressure,
            "korea_premium_index": korea_premium,
            "korea_premium_z_90d": korea_premium_z,
            "korea_premium_change_24h_z": korea_premium_change_24h_z,
            "korea_premium_change_3d_z": korea_premium_change_3d_z,
            "korea_premium_state": premium_state,
            "hk_btc_etf_flow_1d_z": hk_etf_flow_1d_z,
            "hk_btc_etf_flow_5d_z": hk_etf_flow_5d_z,
            "regional_demand_score": regional_demand_score,
            "asia_expected_btc_return_24h": expected,
            "asia_risk_residual_24h": residual,
            "asia_risk_residual_z_90d": residual_z,
            "btc_response_score": btc_response_score,
        }
    )
    return values


def _btc_adoption_derived_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> dict[str, float]:
    values: dict[str, float] = {}
    active = _latest_metric_value(session, "active_addresses", mode)
    tx_count = _latest_metric_value(session, "transaction_count", mode)
    transfer_usd = _latest_metric_value(session, "transfer_volume_adjusted_usd", mode)
    btc_price = _latest_metric_value(session, "btc_price", mode)
    supply = _latest_metric_value(session, "supply_current", mode)
    btc_4h = float(_latest_metric_value(session, "btc_return_4h", mode) or 0.0)
    btc_24h = float(_latest_metric_value(session, "btc_return_24h", mode) or 0.0)

    if active is not None:
        active_sample = _sample_from_latest_row(session, "active_addresses", mode)
        if active_sample is not None:
            values["active_entities_or_addresses_z_30d"] = _metric_zscore(session, active_sample, mode, limit=30)
            values["active_entities_or_addresses_z_60d"] = _metric_zscore(session, active_sample, mode, limit=60)
            values["active_entities_or_addresses_change_7d_pct"] = _metric_change_for_metric(
                session, "active_addresses", mode, sample.ts, hours=168
            )
    if tx_count is not None:
        tx_sample = _sample_from_latest_row(session, "transaction_count", mode)
        if tx_sample is not None:
            values["transaction_count_z_30d"] = _metric_zscore(session, tx_sample, mode, limit=30)
            values["transaction_count_z_60d"] = _metric_zscore(session, tx_sample, mode, limit=60)
            values["transaction_count_change_7d_pct"] = _metric_change_for_metric(
                session, "transaction_count", mode, sample.ts, hours=168
            )
    if active not in (None, 0) and tx_count is not None:
        tx_per_active = float(tx_count) / abs(float(active))
        values["tx_per_active_entity"] = tx_per_active
        values["tx_per_active_entity_z_60d"] = _metric_zscore_for_value(
            session,
            "tx_per_active_entity",
            "btc-adoption-derived",
            mode,
            tx_per_active,
            sample.ts,
            limit=60,
        )

    if transfer_usd is not None:
        transfer_sample = _sample_from_latest_row(session, "transfer_volume_adjusted_usd", mode)
        if transfer_sample is not None:
            values["transfer_volume_adjusted_usd_z_30d"] = _metric_zscore(
                session, transfer_sample, mode, limit=30
            )
            values["transfer_volume_adjusted_usd_z_60d"] = _metric_zscore(
                session, transfer_sample, mode, limit=60
            )
            values["transfer_volume_adjusted_usd_change_7d_pct"] = _metric_change_for_metric(
                session, "transfer_volume_adjusted_usd", mode, sample.ts, hours=168
            )
        if tx_count not in (None, 0):
            values["transfer_volume_per_tx"] = float(transfer_usd) / abs(float(tx_count))
        if active not in (None, 0):
            values["transfer_volume_per_active_entity"] = float(transfer_usd) / abs(float(active))
            values["settlement_velocity_z_60d"] = _metric_zscore_for_value(
                session,
                "transfer_volume_per_active_entity",
                "btc-adoption-derived",
                mode,
                values["transfer_volume_per_active_entity"],
                sample.ts,
                limit=60,
            )
        if btc_price is not None and supply is not None and float(transfer_usd) > 0:
            nvt = (float(btc_price) * float(supply)) / float(transfer_usd)
            values["nvt_proxy"] = nvt
            values["nvt_proxy_z_180d"] = _metric_zscore_for_value(
                session, "nvt_proxy", "btc-adoption-derived", mode, nvt, sample.ts, limit=180
            )
            previous_nvt = _metric_value_at_or_before(
                session,
                "nvt_proxy",
                mode,
                sample.ts - timedelta(days=7),
                source_id="btc-adoption-derived",
                before_ts=sample.ts,
            )
            values["nvt_proxy_change_7d"] = _value_change_against_previous_scalar(
                current=nvt,
                previous=previous_nvt,
            )

    tx_z = values.get("transaction_count_z_60d", 0.0)
    transfer_z = values.get("transfer_volume_adjusted_usd_z_60d", 0.0)
    tx_per_active_z = values.get("tx_per_active_entity_z_60d", 0.0)

    fee_pressure_inputs = []
    for metric_id in ("avg_fees_per_block_btc", "fees_vs_reward_pct", "mempool_min_fee_rate_sat_vb"):
        metric_sample = _sample_from_latest_row(session, metric_id, mode)
        if metric_sample is not None:
            fee_pressure_inputs.append(_metric_zscore(session, metric_sample, mode, limit=60))
    fee_pressure = sum(fee_pressure_inputs) / len(fee_pressure_inputs) if fee_pressure_inputs else 0.0
    values["fee_pressure_z_60d"] = fee_pressure
    values["fee_pressure_z_30d"] = fee_pressure
    values["avg_fee_rate_24h"] = float(_latest_metric_value(session, "mempool_min_fee_rate_sat_vb", mode) or 0.0)
    values["avg_fee_rate_1h"] = values["avg_fee_rate_24h"]
    values["mempool_min_fee_rate"] = values["avg_fee_rate_24h"]
    values["mempool_tx_count_adoption"] = float(_latest_metric_value(session, "mempool_tx_count", mode) or 0.0)
    values["mempool_vsize"] = float(_latest_metric_value(session, "mempool_vsize_mb", mode) or 0.0)
    mempool_sample = _sample_from_latest_row(session, "mempool_vsize_mb", mode)
    if mempool_sample is not None:
        values["mempool_vsize_z_30d"] = _metric_zscore(session, mempool_sample, mode, limit=30)
    values["fees_vs_reward_pct_adoption"] = float(_latest_metric_value(session, "fees_vs_reward_pct", mode) or 0.0)
    values["congestion_without_settlement_flag"] = (
        1.0 if fee_pressure >= 1.5 and values.get("transfer_volume_adjusted_usd_z_60d", 0.0) <= 0.0 else 0.0
    )
    values["activity_spike_flag"] = (
        1.0
        if (tx_z >= 2.0 and transfer_z <= 0.0) or (tx_per_active_z >= 2.5 and fee_pressure >= 1.5)
        else 0.0
    )

    hashrate_metric = "hashrate_90d_ehs" if _latest_metric_value(session, "hashrate_90d_ehs", mode) is not None else "btc_hashrate"
    hashrate_sample = _sample_from_latest_row(session, hashrate_metric, mode)
    if hashrate_sample is not None:
        values["hashrate_14d_ma"] = _metric_rolling_average_for_metric(
            session, hashrate_metric, mode, sample.ts, limit=14
        )
        current_ma = values["hashrate_14d_ma"]
        previous_ma = _metric_rolling_average_for_metric(
            session, hashrate_metric, mode, sample.ts - timedelta(days=7), limit=14
        )
        hashrate_change_7d = _value_change_against_previous_scalar(
            current=current_ma,
            previous=previous_ma,
        )
        if abs(hashrate_change_7d) > 5.0:
            hashrate_change_7d = 0.0
        values["hashrate_14d_ma_change_7d_pct"] = _clamp(hashrate_change_7d, -0.25, 0.25)
        values["hashrate_z_90d"] = _metric_zscore(session, hashrate_sample, mode, limit=90)
    hashprice_sample = _sample_from_latest_row(session, "hash_price_usd", mode)
    if hashprice_sample is not None:
        values["hashprice_z_90d"] = _metric_zscore(session, hashprice_sample, mode, limit=90)
    else:
        values["hashprice_z_90d"] = float(_latest_metric_value(session, "hashprice_z", mode) or 0.0)
    values["miner_revenue_z_90d"] = _clamp(
        values.get("hashrate_z_90d", 0.0) + values.get("hashprice_z_90d", 0.0),
        -5.0,
        5.0,
    )
    values["miner_security_pressure_proxy"] = (
        1.0
        if values.get("hashrate_14d_ma_change_7d_pct", 0.0) < -0.03
        and values.get("hashprice_z_90d", 0.0) <= -1.0
        else 0.0
    )

    lightning_capacity = _latest_metric_value(session, "lightning_capacity_btc", mode)
    lightning_nodes = _latest_metric_value(session, "lightning_node_count", mode)
    lightning_channels = _latest_metric_value(session, "lightning_channel_count", mode)
    if lightning_capacity is not None:
        values["lightning_capacity_change_30d_pct"] = _metric_change_for_metric(
            session, "lightning_capacity_btc", mode, sample.ts, hours=720
        )
    if lightning_nodes is not None:
        values["lightning_node_count_change_30d_pct"] = _metric_change_for_metric(
            session, "lightning_node_count", mode, sample.ts, hours=720
        )
    if lightning_channels is not None:
        values["lightning_channel_count_change_30d_pct"] = _metric_change_for_metric(
            session, "lightning_channel_count", mode, sample.ts, hours=720
        )
    if lightning_capacity is not None and lightning_channels not in (None, 0):
        values["lightning_capacity_per_channel"] = float(lightning_capacity) / abs(float(lightning_channels))
    values["lightning_public_network_health_score"] = _clamp(
        100.0
        * (
            0.4 * values.get("lightning_capacity_change_30d_pct", 0.0)
            + 0.3 * values.get("lightning_node_count_change_30d_pct", 0.0)
            + 0.3 * values.get("lightning_channel_count_change_30d_pct", 0.0)
        ),
        -100.0,
        100.0,
    )
    if _latest_metric_value(session, "bitcoin_reachable_nodes", mode) is not None:
        values["bitcoin_reachable_nodes_change_30d_pct"] = _metric_change_for_metric(
            session, "bitcoin_reachable_nodes", mode, sample.ts, hours=720
        )

    settlement_basis = _clamp(35.0 * transfer_z - 25.0 * values.get("nvt_proxy_change_7d", 0.0) + 12.0 * values.get("settlement_velocity_z_60d", 0.0), -100.0, 100.0)
    activity_basis = _clamp(22.0 * values.get("active_entities_or_addresses_z_60d", 0.0) + 18.0 * tx_z + 20.0 * transfer_z, -100.0, 100.0)
    fee_basis = _clamp(24.0 * fee_pressure + 10.0 * values.get("mempool_vsize_z_30d", 0.0), -100.0, 100.0)
    nvt_improvement = _clamp(-70.0 * values.get("nvt_proxy_change_7d", 0.0) - 18.0 * values.get("nvt_proxy_z_180d", 0.0), -100.0, 100.0)
    expected = _clamp(
        0.00035 * settlement_basis
        + 0.00025 * activity_basis
        + 0.00020 * fee_basis
        + 0.00020 * nvt_improvement,
        -0.08,
        0.08,
    )
    residual = btc_24h - expected
    values.update(
        {
            "adoption_btc_return_4h": btc_4h,
            "adoption_btc_return_24h": btc_24h,
            "adoption_btc_return_3d": _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=72),
            "adoption_btc_return_7d": _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=168),
            "adoption_expected_return_24h": expected,
            "adoption_residual_24h": residual,
            "adoption_residual_z_90d": _metric_zscore_for_value(
                session,
                "adoption_residual_24h",
                "btc-adoption-derived",
                mode,
                residual,
                sample.ts,
                limit=90,
            ),
            "price_acceptance_score": _clamp(45.0 * residual + 18.0 * (1.0 if btc_24h > 0 else -1.0 if btc_24h < 0 else 0.0), -100.0, 100.0),
        }
    )
    return values


def _fund_flow_etf_derived_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> dict[str, float]:
    current = float(sample.value)
    flow_2d = _metric_rolling_sum(session, sample, mode, limit=2)
    flow_3d = _metric_rolling_sum(session, sample, mode, limit=3)
    flow_5d = _metric_rolling_sum(session, sample, mode, limit=5)
    flow_7d = _metric_rolling_sum(session, sample, mode, limit=7)
    flow_20d = _metric_rolling_sum(session, sample, mode, limit=20)
    previous_flow_3d = _metric_rolling_sum(
        session, sample, mode, limit=3, before_ts=sample.ts
    )
    previous_value = _previous_metric_value(session, sample, mode)
    rolling_abs_median = _metric_abs_quantile(
        session, sample.metric_id, sample.source_id, mode, sample.ts, limit=60, quantile=0.5
    )
    rolling_abs_p90 = _metric_abs_quantile(
        session, sample.metric_id, sample.source_id, mode, sample.ts, limit=120, quantile=0.9
    )
    z_1d = _metric_zscore(session, sample, mode, limit=60)
    z_3d = _metric_zscore_for_value(
        session, sample.metric_id, sample.source_id, mode, flow_3d, sample.ts, limit=60
    )
    z_7d = _metric_zscore_for_value(
        session, sample.metric_id, sample.source_id, mode, flow_7d, sample.ts, limit=60
    )
    reversal = (
        previous_value is not None
        and current * previous_value < 0
        and abs(current) > rolling_abs_median
    )
    shock = abs(z_1d) >= 2.0 or abs(current) >= rolling_abs_p90
    return {
        "etf_net_flow_usd": current,
        "etf_flow_2d_usd": flow_2d,
        "etf_flow_3d_usd": flow_3d,
        "etf_flow_5d_usd": flow_5d,
        "etf_flow_7d_usd": flow_7d,
        "etf_flow_20d_usd": flow_20d,
        "etf_flow_1d_z_60d": z_1d,
        "etf_flow_3d_z_60d": z_3d,
        "etf_flow_7d_z_60d": z_7d,
        "etf_inflow_streak_days": float(_metric_sign_streak(session, sample, mode, positive=True)),
        "etf_outflow_streak_days": float(_metric_sign_streak(session, sample, mode, positive=False)),
        "etf_flow_acceleration_3d": flow_3d - previous_flow_3d,
        "etf_flow_reversal_2d": 1.0 if reversal else 0.0,
        "etf_flow_shock_flag": 1.0 if shock else 0.0,
        "etf_flow_data_source_count": float(_current_source_count(session, "etf_net_flow", mode, sample.ts)),
        "etf_flow_cross_source_diff_pct": _current_source_diff_pct(
            session, "etf_net_flow", mode, sample.ts
        ),
    }


def _fund_flow_stablecoin_derived_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> dict[str, float]:
    supply = (
        float(sample.value)
        if sample.metric_id == "stablecoin_supply"
        else float(_latest_metric_value(session, "stablecoin_supply", mode) or 0.0)
    )
    change_1d = _metric_change_for_metric(session, "stablecoin_supply", mode, sample.ts, hours=24)
    change_7d = _metric_change_for_metric(session, "stablecoin_supply", mode, sample.ts, hours=168)
    change_30d = _metric_change_for_metric(session, "stablecoin_supply", mode, sample.ts, hours=720)
    supply_source = _latest_metric_row(session, "stablecoin_supply", mode)
    supply_source_id = supply_source.source_id if supply_source is not None else sample.source_id
    supply_ts = supply_source.ts if supply_source is not None else sample.ts
    btc_price = _latest_metric_value(session, "btc_price", mode)
    btc_supply = _latest_metric_value(session, "supply_current", mode)
    if btc_price is not None and btc_supply is not None and supply:
        ssr = (float(btc_price) * float(btc_supply)) / supply
    else:
        buying_power = _latest_metric_value(session, "stablecoin_buying_power_proxy", mode)
        ssr = 1.0 / float(buying_power) if buying_power else 0.0
    ssr_7d = _value_change_against_previous_scalar(
        current=ssr,
        previous=_metric_value_at_or_before(session, "ssr", mode, sample.ts - timedelta(days=7)),
    )
    regime = 1.0 if change_7d > 0 and change_30d > 0 and ssr <= 0 else 0.0
    if change_7d > 0 and change_30d > 0:
        regime = 1.0
    elif change_7d < 0 and change_30d <= 0:
        regime = -1.0
    return {
        "stablecoin_total_mcap": supply,
        "stablecoin_mcap_change_1d": change_1d,
        "stablecoin_mcap_change_7d": change_7d,
        "stablecoin_mcap_change_30d": change_30d,
        "stablecoin_mcap_z_60d": _metric_zscore_for_value(
            session, "stablecoin_supply", supply_source_id, mode, supply, supply_ts, limit=60
        ),
        "stablecoin_mcap_change_7d_z_120d": _metric_change_zscore_for_metric(
            session,
            "stablecoin_supply",
            supply_source_id,
            mode,
            change_7d,
            supply_ts,
            hours=168,
            limit=120,
        ),
        "stablecoin_mcap_change_30d_z_180d": _metric_change_zscore_for_metric(
            session,
            "stablecoin_supply",
            supply_source_id,
            mode,
            change_30d,
            supply_ts,
            hours=720,
            limit=180,
        ),
        "ssr": ssr,
        "ssr_z_180d": _metric_zscore_for_value(
            session, "ssr", "fund-flow-derived", mode, ssr, sample.ts, limit=180
        ),
        "ssr_change_7d": ssr_7d,
        "stablecoin_liquidity_regime": regime,
    }


def _fund_flow_exchange_supply_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> dict[str, float]:
    netflow_1d = float(sample.value)
    netflow_7d = _metric_rolling_sum(session, sample, mode, limit=7)
    z_60 = _metric_zscore(session, sample, mode, limit=60)
    z_180 = _metric_zscore(session, sample, mode, limit=180)
    large_single_transfer = abs(z_60) >= 2.0 and abs(netflow_1d) >= max(abs(netflow_7d) * 0.75, 1.0)
    return {
        "btc_exchange_balance_change_1d": netflow_1d,
        "btc_exchange_balance_change_7d": netflow_7d,
        "btc_exchange_netflow_1d": netflow_1d,
        "btc_exchange_netflow_7d": netflow_7d,
        "btc_exchange_netflow_z_60d": z_60,
        "btc_exchange_netflow_z_180d": z_180,
        "large_single_transfer_flag": 1.0 if large_single_transfer else 0.0,
        "internal_transfer_risk_flag": 1.0 if large_single_transfer else 0.0,
        "exchange_metric_revision_risk": 1.0 if abs(z_60) >= 2.0 else 0.0,
        "exchange_flow_confirmed": 0.0 if large_single_transfer else 1.0,
    }


def _fund_flow_btc_response_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> dict[str, float]:
    btc_4h = _latest_metric_value(session, "btc_return_4h", mode) or 0.0
    btc_24h = _latest_metric_value(session, "btc_return_24h", mode) or 0.0
    btc_12h = _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=12)
    btc_3d = _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=72)
    etf_1d_z = _latest_metric_value(session, "etf_flow_1d_z_60d", mode) or 0.0
    etf_3d_z = _latest_metric_value(session, "etf_flow_3d_z_60d", mode) or 0.0
    stable_z = _latest_metric_value(session, "stablecoin_mcap_change_7d_z_120d", mode) or 0.0
    exchange_z = _latest_metric_value(session, "btc_exchange_netflow_z_60d", mode) or 0.0
    etf_1d_z = _clamp(float(etf_1d_z), -2.5, 2.5)
    etf_3d_z = _clamp(float(etf_3d_z), -2.5, 2.5)
    stable_z = _clamp(float(stable_z), -2.5, 2.5)
    exchange_z = _clamp(float(exchange_z), -2.5, 2.5)
    expected = _clamp(
        (0.0025 * etf_1d_z)
        + (0.0035 * etf_3d_z)
        + (0.0015 * stable_z)
        - (0.002 * exchange_z),
        -0.08,
        0.08,
    )
    residual = float(btc_24h) - expected
    volume = _latest_metric_value(session, "exchange_spot_volume", mode)
    volume_z = 0.0
    if volume is not None:
        volume_row = _latest_metric_row(session, "exchange_spot_volume", mode)
        if volume_row is not None:
            volume_z = _metric_zscore(session, MetricSample(
                metric_id=volume_row.metric_id,
                source_id=volume_row.source_id,
                ts=volume_row.ts,
                value=volume_row.value,
                timeframe=volume_row.timeframe,
                quality_score=volume_row.quality_score,
            ), mode, limit=24)
    return {
        "btc_return_12h": btc_12h,
        "btc_return_3d": btc_3d,
        "btc_volume_z_24h": volume_z,
        "btc_realized_vol_24h": abs(float(btc_24h)),
        "btc_realized_vol_7d": abs(btc_3d),
        "fund_flow_expected_return_24h": expected,
        "fund_flow_residual_24h": residual,
        "fund_flow_residual_z_60d": _metric_zscore_for_value(
            session, "fund_flow_residual_24h", "fund-flow-derived", mode, residual, sample.ts, limit=60
        ),
    }


def _onchain_valuation_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    source_metrics = {
        "btc_price",
        "btc_return_24h",
        "mvrv_zscore",
        "nupl",
        "sopr",
        "realized_price",
        "cap_real_usd",
        "supply_current",
        "sth_cost_basis",
        "lth_cost_basis",
        "btc_hashrate",
    }
    if sample.metric_id not in source_metrics:
        return []

    derived_source = "onchain-valuation-derived"
    values = _onchain_valuation_derived_values(session, sample, mode)
    return [
        MetricSample(
            metric_id=metric_id,
            source_id=derived_source,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in values.items()
        if value is not None
    ]


def _onchain_valuation_derived_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> dict[str, float]:
    btc_price = _latest_metric_value(session, "btc_price", mode)
    btc_return_24h = _latest_metric_value(session, "btc_return_24h", mode) or 0.0
    realized_price = _latest_metric_value(session, "realized_price", mode)
    sth_cost_basis = _latest_metric_value(session, "sth_cost_basis", mode)
    lth_cost_basis = _latest_metric_value(session, "lth_cost_basis", mode)
    cap_real = _latest_metric_value(session, "cap_real_usd", mode)
    supply = _latest_metric_value(session, "supply_current", mode)
    sopr = _latest_metric_value(session, "sopr", mode)
    mvrv_zscore = _latest_metric_value(session, "mvrv_zscore", mode)
    nupl = _latest_metric_value(session, "nupl", mode)
    hashrate = _latest_metric_value(session, "btc_hashrate", mode)

    values: dict[str, float] = {}
    if btc_price is not None and supply is not None and supply > 0:
        market_cap = float(btc_price) * float(supply)
        values["onchain_market_cap_usd"] = market_cap
        if cap_real is not None and cap_real > 0:
            values["mvrv_ratio"] = market_cap / float(cap_real)
            values["nupl_proxy"] = (market_cap - float(cap_real)) / market_cap if market_cap else 0.0
            values["mvrv_zscore_proxy"] = _metric_zscore_for_value(
                session,
                "onchain_market_cap_usd",
                "onchain-valuation-derived",
                mode,
                market_cap - float(cap_real),
                sample.ts,
                limit=1460,
            )
        if realized_price is None and cap_real is not None:
            values["realized_price_derived"] = float(cap_real) / float(supply)

    if btc_price is not None and realized_price:
        values["btc_vs_realized_price_pct"] = (float(btc_price) - float(realized_price)) / abs(float(realized_price))
    if btc_price is not None and sth_cost_basis:
        sth_distance = (float(btc_price) - float(sth_cost_basis)) / abs(float(sth_cost_basis))
        vol_14d = _metric_pct_change_std_for_metric(session, "btc_price", mode, sample.ts, hours=24, limit=14)
        if vol_14d <= 0:
            vol_14d = abs(float(btc_return_24h))
        sth_band_pct = _clamp(max(0.012, vol_14d * 0.35), 0.012, 0.035)
        values.update(
            {
                "btc_vs_sth_cost_basis_pct": sth_distance,
                "btc_vs_sth_cost_basis_z_365d": _metric_zscore_for_value(
                    session,
                    "btc_vs_sth_cost_basis_pct",
                    "onchain-valuation-derived",
                    mode,
                    sth_distance,
                    sample.ts,
                    limit=365,
                ),
                "sth_cost_basis_distance_change_24h": _value_change_against_previous_scalar(
                    current=sth_distance,
                    previous=_metric_value_at_or_before(
                        session,
                        "btc_vs_sth_cost_basis_pct",
                        mode,
                        sample.ts - timedelta(hours=24),
                        source_id="onchain-valuation-derived",
                        before_ts=sample.ts,
                    ),
                ),
                "btc_14d_realized_vol": vol_14d,
                "sth_band_pct": sth_band_pct,
                "sth_upper_band": float(sth_cost_basis) * (1.0 + sth_band_pct),
                "sth_lower_band": float(sth_cost_basis) * (1.0 - sth_band_pct),
                "sth_cost_basis_reclaim_flag": 1.0 if float(btc_price) > float(sth_cost_basis) * (1.0 + sth_band_pct) else 0.0,
                "sth_cost_basis_rejection_flag": 1.0 if abs(sth_distance) <= sth_band_pct and float(btc_return_24h) <= 0 else 0.0,
                "cost_basis_cluster_state": _cost_basis_cluster_state_value(
                    float(btc_price), realized_price, sth_cost_basis, lth_cost_basis, sth_band_pct
                ),
            }
        )
    if btc_price is not None and lth_cost_basis:
        values["btc_vs_lth_cost_basis_pct"] = (float(btc_price) - float(lth_cost_basis)) / abs(float(lth_cost_basis))

    if mvrv_zscore is not None:
        values["mvrv_zscore_change_7d"] = _value_change_against_previous_scalar(
            current=float(mvrv_zscore),
            previous=_metric_value_at_or_before(session, "mvrv_zscore", mode, sample.ts - timedelta(days=7), before_ts=sample.ts),
        )
        values["mvrv_zscore_z_365d"] = _metric_zscore_for_value(
            session, "mvrv_zscore", "playwright-glassnode-asset-overview", mode, float(mvrv_zscore), sample.ts, limit=365
        )
    if nupl is not None:
        values["nupl_change_7d"] = _value_change_against_previous_scalar(
            current=float(nupl),
            previous=_metric_value_at_or_before(session, "nupl", mode, sample.ts - timedelta(days=7), before_ts=sample.ts),
        )
        values["nupl_z_365d"] = _metric_zscore_for_value(
            session, "nupl", "playwright-glassnode-asset-overview", mode, float(nupl), sample.ts, limit=365
        )
    if sopr is not None:
        values["sopr_change_1d"] = _value_change_against_previous_scalar(
            current=float(sopr),
            previous=_metric_value_at_or_before(session, "sopr", mode, sample.ts - timedelta(hours=24), before_ts=sample.ts),
        )
        values["sopr_z_90d"] = _metric_zscore_for_value(
            session, "sopr", "playwright-glassnode-sopr", mode, float(sopr), sample.ts, limit=90
        )
        previous_sopr = _metric_value_at_or_before(session, "sopr", mode, sample.ts - timedelta(hours=24), before_ts=sample.ts)
        values["sopr_above_1_streak_days"] = float(_metric_threshold_streak(session, "sopr", mode, sample.ts, above=True, threshold=1.0))
        values["sopr_below_1_streak_days"] = float(_metric_threshold_streak(session, "sopr", mode, sample.ts, above=False, threshold=1.0))
        cross = 0.0
        if previous_sopr is not None and previous_sopr <= 1.0 < float(sopr):
            cross = 1.0
        elif previous_sopr is not None and previous_sopr >= 1.0 > float(sopr):
            cross = -1.0
        values["sopr_cross_1_direction"] = cross

    if cap_real is not None:
        values["realized_cap_change_7d_pct"] = _metric_change_for_metric(session, "cap_real_usd", mode, sample.ts, hours=168)
        values["realized_cap_change_30d_pct"] = _metric_change_for_metric(session, "cap_real_usd", mode, sample.ts, hours=720)
        cap_row = _latest_metric_row(session, "cap_real_usd", mode)
        source_id = cap_row.source_id if cap_row is not None else "coinmetrics-community-btc-csv"
        values["realized_cap_impulse_z_180d"] = _metric_change_zscore_for_metric(
            session,
            "cap_real_usd",
            source_id,
            mode,
            values["realized_cap_change_7d_pct"],
            sample.ts,
            hours=168,
            limit=180,
        )

    if btc_price is not None and hashrate:
        issuance_usd = _approx_btc_daily_issuance(sample.ts) * float(btc_price)
        values["daily_issuance_usd_proxy"] = issuance_usd
        values["puell_multiple_proxy"] = _puell_multiple_proxy(session, issuance_usd, sample.ts, mode)
        hashprice = issuance_usd / float(hashrate) if float(hashrate) else 0.0
        values["hashprice_proxy"] = hashprice
        values["hashprice_z"] = _metric_zscore_for_value(
            session, "hashprice_proxy", "onchain-valuation-derived", mode, hashprice, sample.ts, limit=180
        )
        values["miner_pressure_proxy"] = _clamp((values["puell_multiple_proxy"] - 1.0) + values["hashprice_z"] * 0.25, -3.0, 3.0)

    values["whale_pressure_proxy"] = float(_latest_metric_value(session, "large_single_transfer_flag", mode) or 0.0)
    values.update(_onchain_btc_response_values(session, sample, mode, values))
    return values


def _onchain_btc_response_values(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
    derived_values: dict[str, float],
) -> dict[str, float]:
    btc_24h = float(_latest_metric_value(session, "btc_return_24h", mode) or 0.0)
    btc_4h = float(_latest_metric_value(session, "btc_return_4h", mode) or 0.0)
    btc_3d = _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=72)
    btc_7d = _metric_change_for_metric(session, "btc_price", mode, sample.ts, hours=168)
    sth_distance = derived_values.get("btc_vs_sth_cost_basis_pct") or _latest_metric_value(
        session, "btc_vs_sth_cost_basis_pct", mode
    ) or 0.0
    sopr_z = derived_values.get("sopr_z_90d") or _latest_metric_value(session, "sopr_z_90d", mode) or 0.0
    cap_impulse = derived_values.get("realized_cap_impulse_z_180d") or _latest_metric_value(
        session, "realized_cap_impulse_z_180d", mode
    ) or 0.0
    mvrv_z = _latest_metric_value(session, "mvrv_zscore_z_365d", mode) or 0.0
    expected = _clamp(
        (0.010 * _clamp(float(sth_distance), -0.2, 0.2))
        + (0.003 * _clamp(float(sopr_z), -2.5, 2.5))
        + (0.004 * _clamp(float(cap_impulse), -2.5, 2.5))
        - (0.002 * max(float(mvrv_z) - 1.0, 0.0)),
        -0.08,
        0.08,
    )
    residual = btc_24h - expected
    return {
        "onchain_btc_return_4h": btc_4h,
        "onchain_btc_return_24h": btc_24h,
        "onchain_btc_return_3d": btc_3d,
        "onchain_btc_return_7d": btc_7d,
        "onchain_expected_return_24h": expected,
        "onchain_residual_24h": residual,
        "onchain_residual_z_90d": _metric_zscore_for_value(
            session, "onchain_residual_24h", "onchain-valuation-derived", mode, residual, sample.ts, limit=90
        ),
    }


def _metric_pct_change_std_for_metric(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    before_ts: datetime,
    *,
    hours: int,
    limit: int,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    changes: list[float] = []
    for row in rows:
        previous = _metric_value_at_or_before(
            session,
            metric_id,
            mode,
            row.ts - timedelta(hours=hours),
            before_ts=row.ts,
        )
        if previous in (None, 0):
            continue
        changes.append((float(row.value) - float(previous)) / abs(float(previous)))
    if len(changes) < 2:
        return 0.0
    mean = sum(changes) / len(changes)
    variance = sum((value - mean) ** 2 for value in changes) / len(changes)
    return variance ** 0.5


def _metric_threshold_streak(
    session: Any,
    metric_id: str,
    mode: SourceMode,
    before_ts: datetime,
    *,
    above: bool,
    threshold: float,
    limit: int = 30,
) -> int:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts <= before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(limit)
    ).all()
    streak = 0
    for row in rows:
        if row.value is None:
            break
        value = float(row.value)
        if (above and value >= threshold) or ((not above) and value < threshold):
            streak += 1
            continue
        break
    return streak


def _cost_basis_cluster_state_value(
    btc_price: float,
    realized_price: float | None,
    sth_cost_basis: float | None,
    lth_cost_basis: float | None,
    band_pct: float,
) -> float:
    levels = [value for value in (realized_price, sth_cost_basis, lth_cost_basis) if value]
    if not levels:
        return 0.0
    near_count = sum(1 for level in levels if abs(btc_price - float(level)) / abs(float(level)) <= band_pct)
    if near_count >= 2:
        return 2.0
    if near_count == 1:
        return 1.0
    return 0.0


def _approx_btc_daily_issuance(ts: datetime) -> float:
    # Current subsidy epoch after the April 2024 halving: 3.125 BTC * ~144 blocks/day.
    if ts.replace(tzinfo=UTC) >= datetime(2024, 4, 20, tzinfo=UTC):
        return 450.0
    return 900.0


def _puell_multiple_proxy(
    session: Any,
    issuance_usd: float,
    before_ts: datetime,
    mode: SourceMode,
) -> float:
    rows = session.scalars(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == "daily_issuance_usd_proxy",
            schema.MetricValue.source_id == "onchain-valuation-derived",
            schema.MetricValue.run_mode == mode,
            schema.MetricValue.ts < before_ts,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(365)
    ).all()
    values = [float(row.value) for row in rows if row.value is not None]
    if len(values) < 30:
        return 1.0
    baseline = sum(values) / len(values)
    return issuance_usd / baseline if baseline else 1.0


def _options_volatility_derived_samples(
    session: Any,
    sample: MetricSample,
    mode: SourceMode,
) -> list[MetricSample]:
    derived_source = "deribit-btc-options"
    option_metrics = {
        "options_iv",
        "options_rv",
        "put_call_ratio",
        "options_skew",
        "options_expiry_notional",
        "max_pain_distance",
        "gamma_wall_proxy_distance",
    }
    if sample.metric_id not in option_metrics:
        return []

    values: dict[str, float] = {}
    for metric_id in option_metrics:
        latest = _latest_metric_value(session, metric_id, mode)
        if latest is not None:
            values[metric_id] = latest

    changes: dict[str, float] = {}
    if sample.metric_id == "options_iv":
        changes["iv_change_1d"] = _metric_change_since(session, sample, mode, hours=24)
    elif sample.metric_id == "options_rv":
        changes["rv_change_1d"] = _metric_change_since(session, sample, mode, hours=24)
    elif sample.metric_id == "put_call_ratio":
        changes["put_call_ratio_change_1d"] = _metric_change_since(
            session, sample, mode, hours=24
        )
        changes["put_call_ratio_z"] = _metric_zscore(session, sample, mode, limit=30)
    elif sample.metric_id == "options_expiry_notional":
        changes["expiry_notional_z"] = _metric_zscore(session, sample, mode, limit=30)

    if sample.metric_id == "options_iv" and "options_iv" in values and "options_rv" in values:
        rv = values["options_rv"]
        changes["iv_rv_spread"] = values["options_iv"] - rv
        changes["iv_rv_ratio"] = values["options_iv"] / rv if rv else 0.0
    if sample.metric_id == "options_skew" and "options_skew" in values:
        changes["options_skew_abs"] = abs(values["options_skew"])
    if sample.metric_id == "max_pain_distance" and "max_pain_distance" in values:
        changes["max_pain_distance_pct"] = abs(values["max_pain_distance"])
    if sample.metric_id == "gamma_wall_proxy_distance" and "gamma_wall_proxy_distance" in values:
        changes["gamma_wall_distance_pct"] = abs(values["gamma_wall_proxy_distance"])

    return [
        MetricSample(
            metric_id=metric_id,
            source_id=derived_source,
            ts=sample.ts,
            value=value,
            timeframe=sample.timeframe,
            quality_score=sample.quality_score,
        )
        for metric_id, value in changes.items()
    ]


def _latest_metric_value(
    session: Any,
    metric_id: str,
    mode: SourceMode,
) -> float | None:
    row = session.scalar(
        select(schema.MetricValue)
        .where(
            schema.MetricValue.metric_id == metric_id,
            schema.MetricValue.run_mode == mode,
        )
        .order_by(schema.MetricValue.ts.desc())
        .limit(1)
    )
    return float(row.value) if row is not None and row.value is not None else None


def _apply_freshness_discount(quality: float, freshness: dict[str, Any]) -> float:
    return max(min(quality + float(freshness.get("freshness_discount") or 0.0), 1.0), 0.0)


def _freshness_message(
    freshness: dict[str, Any],
    error_message: str | None = None,
    business_recency: dict[str, Any] | None = None,
) -> str:
    message = (
        f"collection_freshness={freshness['freshness_status']} "
        f"collection_age_seconds={freshness['age_seconds']} "
        f"expected_seconds={freshness['expected_refresh_seconds']}"
    )
    if business_recency:
        message = (
            f"{message} "
            f"business_recency={business_recency['business_recency_status']} "
            f"business_age_seconds={business_recency['age_seconds']}"
        )
    return f"{message}; {error_message}" if error_message else message


def _source_freshness_summary(session: Session, source_id: str) -> dict[str, Any]:
    source = _source_by_id(source_id)
    latest_metric = session.scalar(
        select(schema.MetricValue)
        .where(schema.MetricValue.source_id == source_id)
        .order_by(schema.MetricValue.ts.desc())
        .limit(1)
    )
    latest_raw = session.scalar(
        select(schema.RawObservation)
        .where(schema.RawObservation.source_id == source_id)
        .order_by(schema.RawObservation.observed_at.desc())
        .limit(1)
    )
    if latest_metric:
        observed_at = latest_metric.ts
        collected_at = latest_metric.updated_at or latest_metric.created_at
    elif latest_raw:
        observed_at = latest_raw.observed_at
        collected_at = latest_raw.updated_at or latest_raw.created_at
    else:
        observed_at = None
        collected_at = None
    freshness = compute_collection_freshness(source, collected_at)
    business_recency = compute_business_recency(source, observed_at)
    return {
        "source_id": source_id,
        **freshness,
        "collection_freshness_status": freshness["freshness_status"],
        "collection_age_seconds": freshness["age_seconds"],
        "business_recency_status": business_recency["business_recency_status"],
        "business_age_seconds": business_recency["age_seconds"],
        "freshness_policy": business_recency["freshness_policy"],
        "last_collected_at": collected_at.isoformat() if collected_at else None,
        "last_observed_at": observed_at.isoformat() if observed_at else None,
    }


def _is_archived_db_source(source: schema.Source) -> bool:
    return bool((source.metadata_json or {}).get("archived"))


def _is_collectable_config_source(source: SourceConfig) -> bool:
    return bool(source.metadata.get("collectable", True))


def _is_collectable_db_source(source: schema.Source) -> bool:
    return bool((source.metadata_json or {}).get("collectable", True))


def _latest_source_health(session: Session, source_id: str) -> schema.SourceHealthEvent | None:
    return session.scalar(
        select(schema.SourceHealthEvent)
        .where(schema.SourceHealthEvent.source_id == source_id)
        .order_by(schema.SourceHealthEvent.created_at.desc())
        .limit(1)
    )


def _source_by_id(source_id: str) -> SourceConfig | None:
    return next((source for source in SOURCE_CONFIGS if source.source_id == source_id), None)


def _expected_refresh_seconds(source: SourceConfig | None) -> float:
    return float(_freshness_policy(source)["expected_update_seconds"])


def _metadata_seconds(
    source: SourceConfig | None,
    key: str,
    default: float,
) -> float:
    if source is not None and key in source.metadata:
        return float(source.metadata[key]) * 60
    return default


def _freshness_policy(source: SourceConfig | None) -> dict[str, Any]:
    settings = get_settings()
    if source is None:
        base = {
            "cadence": "intraday",
            "expected_update_seconds": float(settings.default_refresh_seconds),
            "collection_stale_after_seconds": float(settings.default_refresh_seconds) * 1.5,
            "collection_expired_after_seconds": float(settings.default_refresh_seconds) * 6,
            "business_expected_lag_after_seconds": float(settings.default_refresh_seconds) * 1.5,
            "business_lagging_after_seconds": float(settings.default_refresh_seconds) * 1.5,
            "business_outdated_after_seconds": float(settings.default_refresh_seconds) * 6,
            "business_calendar": "24x7",
        }
        return base

    if "freshness_policy" in source.metadata:
        return _normalize_policy(source.metadata["freshness_policy"])

    cadence = "intraday"
    expected = (
        float(source.metadata.get("refresh_minutes", settings.default_refresh_seconds / 60))
        * 60
    )
    collection_stale = expected * 1.5
    collection_expired = expected * 6
    business_expected_lag = collection_stale
    business_lagging = collection_stale
    business_outdated = collection_expired
    calendar = "24x7"

    if source.source_id == "mempool-lightning-network-stats":
        cadence = "intraday"
        expected = 10 * 60
        collection_stale = 20 * 60
        collection_expired = 60 * 60
        business_expected_lag = 2 * 60 * 60
        business_lagging = 2 * 60 * 60
        business_outdated = 6 * 60 * 60
    elif source.kind == SourceKind.FRED:
        cadence = "daily"
        expected = 24 * 60 * 60
        collection_stale = 36 * 60 * 60
        collection_expired = 96 * 60 * 60
        business_expected_lag = 4 * 24 * 60 * 60
        business_lagging = 7 * 24 * 60 * 60
        business_outdated = 14 * 24 * 60 * 60
        calendar = "us_business_day"
        if source.metrics and source.metrics[0] in {"fed_balance_sheet", "tga"}:
            cadence = "weekly"
            expected = 7 * 24 * 60 * 60
            business_expected_lag = 7 * 24 * 60 * 60
            business_lagging = 10 * 24 * 60 * 60
            business_outdated = 21 * 24 * 60 * 60
    elif (
        source.method in {"community_csv", "official_api"}
        and source.group_name in {"btc_adoption", "onchain_valuation", "fund_flow"}
    ):
        cadence = "daily"
        expected = 24 * 60 * 60
        collection_stale = 36 * 60 * 60
        collection_expired = 96 * 60 * 60
        business_expected_lag = 2 * 24 * 60 * 60
        business_lagging = 4 * 24 * 60 * 60
        business_outdated = 10 * 24 * 60 * 60
    elif source.method in {
        "rss_official_text_score",
        "official_calendar",
        "html_parse_with_calendar_fallback",
    }:
        cadence = "event"
        expected = 24 * 60 * 60
        collection_stale = 36 * 60 * 60
        collection_expired = 96 * 60 * 60
        business_expected_lag = 7 * 24 * 60 * 60
        business_lagging = 30 * 24 * 60 * 60
        business_outdated = 90 * 24 * 60 * 60
        calendar = "event_time"
    elif source.kind == SourceKind.PLAYWRIGHT:
        cadence = "page_snapshot"
        expected = float(source.metadata.get("refresh_minutes", 60)) * 60
        collection_stale = max(expected * 2, 2 * 60 * 60)
        collection_expired = max(expected * 8, 12 * 60 * 60)
        business_expected_lag = 2 * 24 * 60 * 60
        business_lagging = 7 * 24 * 60 * 60
        business_outdated = 30 * 24 * 60 * 60
    elif source.kind in {SourceKind.EXCHANGE, SourceKind.BITCOIN}:
        cadence = "intraday"
        expected = (
            float(source.metadata.get("refresh_minutes", settings.default_refresh_seconds / 60))
            * 60
        )
        collection_stale = expected * 1.5
        collection_expired = expected * 6
        business_expected_lag = collection_stale
        business_lagging = collection_stale
        business_outdated = collection_expired

    return _normalize_policy(
        {
            "cadence": cadence,
            "expected_update_seconds": expected,
            "collection_stale_after_seconds": _metadata_seconds(
                source,
                "stale_after_minutes",
                collection_stale,
            ),
            "collection_expired_after_seconds": _metadata_seconds(
                source,
                "expired_after_minutes",
                collection_expired,
            ),
            "business_lagging_after_seconds": source.metadata.get(
                "business_lagging_after_seconds",
                business_lagging,
            ),
            "business_expected_lag_after_seconds": source.metadata.get(
                "business_expected_lag_after_seconds",
                business_expected_lag,
            ),
            "business_outdated_after_seconds": source.metadata.get(
                "business_outdated_after_seconds",
                business_outdated,
            ),
            "business_calendar": source.metadata.get("business_calendar", calendar),
        }
    )


def _normalize_policy(policy: dict[str, Any]) -> dict[str, Any]:
    expected = float(policy.get("expected_update_seconds", get_settings().default_refresh_seconds))
    return {
        "cadence": str(policy.get("cadence", "intraday")),
        "expected_update_seconds": expected,
        "collection_stale_after_seconds": float(
            policy.get("collection_stale_after_seconds", expected * 1.5)
        ),
        "collection_expired_after_seconds": float(
            policy.get("collection_expired_after_seconds", expected * 6)
        ),
        "business_lagging_after_seconds": float(
            policy.get("business_lagging_after_seconds", expected * 1.5)
        ),
        "business_expected_lag_after_seconds": float(
            policy.get(
                "business_expected_lag_after_seconds",
                policy.get("business_lagging_after_seconds", expected * 1.5),
            )
        ),
        "business_outdated_after_seconds": float(
            policy.get("business_outdated_after_seconds", expected * 6)
        ),
        "business_calendar": str(policy.get("business_calendar", "24x7")),
    }


_METRIC_SOURCE_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "dxy_proxy": {
        "playwright-tradingview-dxy": {"quality_score": 0.78, "priority": 20},
        "fred-dxy": {"quality_score": 0.70, "priority": 80},
    },
    "sp500": {
        "playwright-tradingview-sp500": {"quality_score": 0.78, "priority": 20},
        "fred-sp500": {"quality_score": 0.70, "priority": 80},
    },
    "dow_jones": {
        "playwright-tradingview-dow-jones": {"quality_score": 0.78, "priority": 20},
        "fred-dow-jones": {"quality_score": 0.70, "priority": 80},
    },
    "wti_oil": {
        "playwright-tradingview-wti-oil": {"quality_score": 0.78, "priority": 20},
        "fred-wti-oil": {"quality_score": 0.70, "priority": 80},
    },
    "brent_oil": {
        "playwright-tradingview-brent-oil": {"quality_score": 0.78, "priority": 20},
        "fred-brent-oil": {"quality_score": 0.70, "priority": 80},
    },
    "jgb_10y": {
        "playwright-tradingview-jgb-10y": {"quality_score": 0.72, "priority": 20},
        "fred-jgb-10y": {"quality_score": 0.70, "priority": 80},
    },
    "usdjpy": {
        "playwright-tradingview-usdjpy": {"quality_score": 0.78, "priority": 20},
        "fred-usdjpy": {"quality_score": 0.70, "priority": 80},
    },
    "usdcnh": {
        "playwright-tradingview-usdcnh": {"quality_score": 0.78, "priority": 20},
        "fred-usdcnh-proxy": {"quality_score": 0.70, "priority": 80},
    },
    "lightning_capacity_btc": {
        "mempool-lightning-network-stats": {"quality_score": 0.90, "priority": 20},
        "clarkmoody-dashboard": {"quality_score": 0.82, "priority": 40},
    },
    "lightning_channel_count": {
        "mempool-lightning-network-stats": {"quality_score": 0.90, "priority": 20},
        "clarkmoody-dashboard": {"quality_score": 0.82, "priority": 40},
    },
    "lightning_node_count": {
        "mempool-lightning-network-stats": {"quality_score": 0.90, "priority": 20},
        "clarkmoody-dashboard": {"quality_score": 0.82, "priority": 40},
    },
}


_DEFINITION_VARIANT_METRICS = {
    "active_addresses",
    "lightning_capacity_btc",
    "lightning_channel_count",
    "lightning_node_count",
}

_FED_TEXT_STREAM_METRICS = {
    "fed_speaker_weight",
    "fed_speech_hawkish_score",
    "fed_speech_dovish_score",
    "fed_speech_content_risk",
    "fed_speech_risk",
}


def _metric_source_override(metric_id: str | None, source_id: str | None) -> dict[str, Any]:
    if not metric_id or not source_id:
        return {}
    return _METRIC_SOURCE_OVERRIDES.get(metric_id, {}).get(source_id, {})


def _metric_source_quality(
    metric_id: str | None,
    source_id: str | None,
    default: float,
) -> float:
    override = _metric_source_override(metric_id, source_id)
    if "quality_score" in override:
        return float(override["quality_score"])
    return default


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _source_counts(session: Session) -> dict[str, int]:
    tables = [
        schema.Source,
        schema.SourceRun,
        schema.RawObservation,
        schema.NormalizedMetric,
        schema.MetricValue,
        schema.SourceHealthEvent,
        schema.DataQualitySnapshot,
        schema.FallbackEvent,
    ]
    return {
        table.__tablename__: session.scalar(select(func.count()).select_from(table)) or 0
        for table in tables
    }


def _collection_warnings(results: list[CollectionResult]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for result in results:
        payload_errors = (
            result.raw.payload.get("errors")
            if isinstance(result.raw.payload, dict)
            else None
        )
        has_warning_status = result.raw.status in {SourceStatus.WARNING, SourceStatus.ERROR}
        if has_warning_status or result.raw.error_message:
            warnings.append(
                {
                    "source_id": result.source.source_id,
                    "status": result.raw.status.value,
                    "message": result.raw.error_message or str(payload_errors or ""),
                }
            )
        elif payload_errors:
            warnings.append(
                {
                    "source_id": result.source.source_id,
                    "status": "warning",
                    "message": str(payload_errors),
                }
            )
    return warnings


def _run_mode_summary(session: Session, current_run_id: str | None = None) -> dict[str, Any]:
    history_counts = _run_mode_counts(session)
    history_mixed_metric_ids = _mixed_metric_ids(session)
    current_counts = _run_mode_counts(session, run_id=current_run_id) if current_run_id else {}
    current_mixed_metric_ids = _mixed_metric_ids(session, run_id=current_run_id) if current_run_id else []
    current_non_live = sum(
        current_counts.get(mode, 0) for mode in ("mock", "test", "unknown")
    )
    history_non_live = sum(
        history_counts.get(mode, 0) for mode in ("mock", "test", "unknown")
    )
    production_blocker = bool(current_non_live or current_mixed_metric_ids)
    return {
        "current_run_id": current_run_id,
        "current_run": {
            "run_id": current_run_id,
            "live_metric_values": current_counts.get("live", 0),
            "mock_metric_values": current_counts.get("mock", 0),
            "test_metric_values": current_counts.get("test", 0),
            "unknown_metric_values": current_counts.get("unknown", 0),
            "mixed_metric_ids": current_mixed_metric_ids,
            "non_live_metric_values": current_non_live,
            "production_blocker": production_blocker,
        },
        "history": {
            "live_metric_values": history_counts.get("live", 0),
            "mock_metric_values": history_counts.get("mock", 0),
            "test_metric_values": history_counts.get("test", 0),
            "unknown_metric_values": history_counts.get("unknown", 0),
            "mixed_metric_ids": history_mixed_metric_ids,
            "non_live_metric_values": history_non_live,
            "history_contamination_warning": bool(history_non_live or history_mixed_metric_ids),
        },
        "default_query_scope": "live_only",
        "history_replay_all_requires_explicit_run_mode": True,
        "history_contamination_warning": bool(history_non_live or history_mixed_metric_ids),
        "live_metric_values": history_counts.get("live", 0),
        "mock_metric_values": history_counts.get("mock", 0),
        "test_metric_values": history_counts.get("test", 0),
        "unknown_metric_values": history_counts.get("unknown", 0),
        "mixed_metric_ids": history_mixed_metric_ids,
        "current_run_mixed_metric_ids": current_mixed_metric_ids,
        "production_blocker": production_blocker,
    }


def _run_mode_counts(session: Session, run_id: str | None = None) -> dict[str, int]:
    statement = select(schema.MetricValue.run_mode, func.count()).group_by(schema.MetricValue.run_mode)
    if run_id is not None:
        statement = statement.where(schema.MetricValue.run_id == run_id)
    rows = session.execute(statement).all()
    return {str(mode or "unknown"): int(count) for mode, count in rows}


def _mixed_metric_ids(session: Session, run_id: str | None = None) -> list[str]:
    statement = (
        select(schema.MetricValue.metric_id, func.count(func.distinct(schema.MetricValue.run_mode)))
        .group_by(schema.MetricValue.metric_id)
        .having(func.count(func.distinct(schema.MetricValue.run_mode)) > 1)
    )
    if run_id is not None:
        statement = statement.where(schema.MetricValue.run_id == run_id)
    rows = session.execute(statement).all()
    return [metric_id for metric_id, _ in rows]


def _fallback_summary(session: Session) -> dict[str, Any]:
    fallback_event_count = session.scalar(
        select(func.count()).select_from(schema.FallbackEvent)
    ) or 0
    warning_rows = session.scalars(
        select(schema.SourceHealthEvent)
        .where(schema.SourceHealthEvent.status.in_(["warning", "error", "stale"]))
        .order_by(schema.SourceHealthEvent.created_at.desc())
        .limit(100)
    ).all()
    http_403_sources = sorted(
        {
            row.source_id
            for row in warning_rows
            if "403" in (row.message or "") or "forbidden" in (row.message or "").lower()
        }
    )
    return {
        "fallback_event_count": fallback_event_count,
        "warning_source_count": len({row.source_id for row in warning_rows}),
        "http_403_sources": http_403_sources,
        "warning_sources": sorted({row.source_id for row in warning_rows}),
    }
