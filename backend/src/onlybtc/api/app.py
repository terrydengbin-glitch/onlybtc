from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Thread
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from onlybtc.api import event_window, mock, p45_dashboard, p45_jobs, radar_runtime
from onlybtc.api.contracts import (
    http_exception_handler,
    ok_response,
    unhandled_exception_handler,
    validation_exception_handler,
)
from onlybtc.api.security import api_security_middleware
from onlybtc.audit.p45_full_chain import run_p45_full_chain_with_llm_audit
from onlybtc.core.config import get_settings, reload_settings
from onlybtc.core.env_writer import write_env_updates
from onlybtc.core.glassnode_entitlement import (
    latest_glassnode_entitlement_report,
    run_glassnode_entitlement_audit,
    write_glassnode_entitlement_report,
)
from onlybtc.core.llm_routing import llm_routing_payload
from onlybtc.core.logging import configure_logging
from onlybtc.core.paths import paths
from onlybtc.core.provider_health import (
    provider_health_snapshot,
    test_all_provider_health,
    test_provider_health,
)
from onlybtc.core.settings_audit import (
    record_settings_audit_event,
    settings_audit_summary,
)
from onlybtc.core.settings_contract import (
    settings_data_sources_payload,
    settings_paths_payload,
    settings_runtime_payload,
)
from onlybtc.db import schema
from onlybtc.db.maintenance import backup_database, export_schema_sql
from onlybtc.db.repositories import PageQueryRepository
from onlybtc.db.seed import seed_demo_data
from onlybtc.db.session import database
from onlybtc.domain.models import SystemHealth
from onlybtc.event_window import event_watchtower_daemon
from onlybtc.p6.alert_quality import (
    alert_history as p6_alert_history_payload,
)
from onlybtc.p6.alert_quality import (
    alert_quality as p6_alert_quality_payload,
)
from onlybtc.p6.article_pipeline import (
    article_history as p6_article_history_payload,
)
from onlybtc.p6.article_pipeline import (
    get_manual_article,
    latest_manual_article,
    manual_generate_article,
    replay_article_snapshot,
)
from onlybtc.p6.dod import latest_p6_dod_report, run_p6_dod_mock
from onlybtc.p6.module_effectiveness import module_effectiveness as p6_module_effectiveness_payload
from onlybtc.p6.outcome_tracking import outcome_tracking as p6_outcome_tracking_payload
from onlybtc.p45.evidence_pack import build_p45_scored_evidence_pack
from onlybtc.p45.final_writer import run_p45_final_writer
from onlybtc.p45.html_report import run_p45_html_report
from onlybtc.p45.llm_analyst_writer import run_p45_llm_analyst_writers
from onlybtc.p45.llm_research_writer import run_p45_llm_research_writer
from onlybtc.p45.writer import run_p45_analyst_writers
from onlybtc.pipeline.run_once import get_persisted_run, latest_persisted_run, run_once_mock
from onlybtc.radar_runtime.daemon import radar_runtime_daemon
from onlybtc.radars.service import analyze_radars, latest_radar_outputs
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources, historical_window, source_health_summary

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="onlyBTC API", version="0.1.0")
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(event_window.router)
app.include_router(radar_runtime.router)
app.include_router(mock.router)
app.middleware("http")(api_security_middleware)

reports_dir = paths.project_root / "reports"
reports_dir.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=reports_dir, html=False), name="reports")


class SettingsEnvUpdateRequest(BaseModel):
    updates: dict[str, str] = Field(default_factory=dict)


@app.on_event("startup")
def start_event_watchtower_daemon() -> None:
    _start_daemon_bootstrap_thread()


def _start_daemon_bootstrap_thread() -> Thread:
    thread = Thread(
        target=_bootstrap_runtime_daemons,
        name="onlybtc-api-daemon-bootstrap",
        daemon=True,
    )
    thread.start()
    return thread


def _bootstrap_runtime_daemons(
    starters: tuple[Callable[..., dict[str, object]], ...] | None = None,
) -> None:
    for starter in starters or (
        event_watchtower_daemon.start,
        radar_runtime_daemon.start,
    ):
        try:
            starter(auto=True)
        except Exception:
            logger.exception("Runtime daemon bootstrap failed")


@app.get("/api/health", response_model=SystemHealth)
def health() -> SystemHealth:
    settings = get_settings()
    return SystemHealth(environment=settings.environment)


@app.get("/api/system/paths")
def system_paths() -> dict[str, str]:
    return paths.as_dict()


@app.get("/api/dashboard/status")
def dashboard_status() -> dict[str, object]:
    settings = get_settings()
    latest_run = latest_persisted_run()
    return {
        "app": settings.app_name,
        "system": "online",
        "data_quality": "sqlite_ready",
        "current_state": "p0_foundation",
        "latest_run": latest_run.model_dump(mode="json") if latest_run else None,
    }


@app.get("/api/dashboard/current")
def dashboard_current() -> dict[str, object] | None:
    database.init_schema()
    with database.session() as session:
        return PageQueryRepository(session).dashboard_current()


@app.post("/api/run-once")
async def trigger_run_once() -> dict[str, object]:
    run = await run_once_mock()
    return {
        **run.model_dump(mode="json"),
        "run_entrypoint": "legacy_mock",
        "deprecated": True,
        "production_entrypoint": "/api/p45/run-full-with-llm/jobs",
    }


@app.get("/api/runs/latest")
def latest_run() -> dict[str, object] | None:
    run = latest_persisted_run()
    return run.model_dump(mode="json") if run else None


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    run = get_persisted_run(run_id)
    if run is None:
        history = p45_dashboard.history(run_id)
        if history is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return history
    return run.model_dump(mode="json")


@app.get("/api/runs/{run_id}/audit-reports")
def get_run_audit_reports(run_id: str) -> dict[str, object]:
    return p45_dashboard.audit_reports(run_id=run_id)


@app.get("/api/db/health")
def database_health() -> dict[str, object]:
    database.init_schema()
    with database.session() as session:
        counts = PageQueryRepository(session).table_counts()
    return {
        "status": "healthy",
        "sqlite_db_path": str(database.db_path),
        "journal_mode": database.pragma("journal_mode"),
        "foreign_keys": database.pragma("foreign_keys"),
        "table_count": len(counts),
        "counts": counts,
    }


@app.post("/api/db/seed-demo")
def seed_demo() -> dict[str, object]:
    return seed_demo_data()


@app.post("/api/db/backup")
def backup_db() -> dict[str, str]:
    return {"backup_path": str(backup_database())}


@app.post("/api/db/export-schema")
def export_schema() -> dict[str, str]:
    return {"schema_path": str(export_schema_sql())}


@app.post("/api/sources/collect")
async def collect_source_data(mode: SourceMode = SourceMode.MOCK) -> dict[str, object]:
    return await collect_sources(mode=mode)


@app.get("/api/sources/health")
def sources_health() -> dict[str, object]:
    return source_health_summary()


@app.get("/api/sources/{source_id}")
def source_detail(source_id: str) -> dict[str, object]:
    result = p45_dashboard.source_detail(source_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


@app.get("/api/metrics/{metric_id}/window")
def metric_window(
    metric_id: str,
    source_id: str | None = None,
    run_mode: str = "live",
) -> dict[str, object] | None:
    return historical_window(metric_id=metric_id, source_id=source_id, run_mode=run_mode)


@app.get("/api/macro/events/upcoming")
def macro_events_upcoming() -> dict[str, object]:
    database.init_schema()
    with database.session() as session:
        raw = session.scalars(
            select(schema.RawObservation)
            .where(schema.RawObservation.source_id == "official-macro-event-calendar")
            .order_by(schema.RawObservation.observed_at.desc())
            .limit(1)
        ).first()
    if raw is None:
        return {"events": []}
    return {"events": raw.raw_payload.get("events", [])}


@app.get("/api/macro/events/{event_id}")
def macro_event_detail(event_id: str) -> dict[str, object]:
    database.init_schema()
    with database.session() as session:
        rows = session.scalars(
            select(schema.RawObservation)
            .where(schema.RawObservation.source_id.in_([
                "official-macro-event-calendar",
                "fxstreet-economic-calendar",
            ]))
            .order_by(schema.RawObservation.observed_at.desc())
            .limit(10)
        ).all()
    for raw in rows:
        candidates = raw.raw_payload.get("events", []) + raw.raw_payload.get("scored_events", [])
        for item in candidates:
            candidate_id = (
                item.get("event_id")
                or item.get("event_type")
                or str(item.get("event_name", "")).lower().replace(" ", "_")
            )
            if str(candidate_id).lower() == event_id.lower():
                return {"event": item, "source_id": raw.source_id}
    raise HTTPException(status_code=404, detail="Macro event not found")


@app.get("/api/macro/surprise/latest")
def macro_surprise_latest() -> dict[str, object]:
    database.init_schema()
    metric_ids = {
        "macro_surprise_score",
        "aggregate_macro_surprise",
        "macro_surprise_event_count",
    }
    with database.session() as session:
        rows = session.scalars(
            select(schema.MetricValue)
            .where(schema.MetricValue.metric_id.in_(metric_ids))
            .order_by(schema.MetricValue.ts.desc())
            .limit(10)
        ).all()
        raw = session.scalars(
            select(schema.RawObservation)
            .where(schema.RawObservation.source_id == "fxstreet-economic-calendar")
            .order_by(schema.RawObservation.observed_at.desc())
            .limit(1)
        ).first()
    latest_by_metric: dict[str, dict[str, object]] = {}
    for row in rows:
        latest_by_metric.setdefault(
            row.metric_id,
            {
                "metric_id": row.metric_id,
                "value": row.value,
                "quality_score": row.quality_score,
                "ts": row.ts.isoformat(),
            },
        )
    return {
        "metrics": latest_by_metric,
        "scored_events": raw.raw_payload.get("scored_events", []) if raw else [],
    }


@app.get("/api/macro/surprise/history")
def macro_surprise_history(days: int = 180) -> dict[str, object]:
    database.init_schema()
    limit = max(min(days, 365), 1) * 4
    with database.session() as session:
        rows = session.scalars(
            select(schema.MetricValue)
            .where(schema.MetricValue.metric_id == "macro_surprise_score")
            .order_by(schema.MetricValue.ts.desc())
            .limit(limit)
        ).all()
    return {
        "metric_id": "macro_surprise_score",
        "items": [
            {
                "ts": row.ts.isoformat(),
                "value": row.value,
                "quality_score": row.quality_score,
                "source_id": row.source_id,
            }
            for row in rows
        ],
    }


@app.get("/api/fed/speeches/latest")
def fed_speeches_latest() -> dict[str, object]:
    database.init_schema()
    with database.session() as session:
        rows = session.scalars(
            select(schema.RawObservation)
            .where(
                schema.RawObservation.source_id.in_(
                    ["fed-rss-all-speeches", "fed-rss-all-testimony"]
                )
            )
            .order_by(schema.RawObservation.observed_at.desc())
            .limit(5)
        ).all()
    return {
        "events": [
            {
                "source_id": row.source_id,
                "observed_at": row.observed_at.isoformat(),
                "latest_event": row.raw_payload.get("latest_event"),
                "score": row.raw_payload.get("score"),
                "status": row.status,
                "error_message": row.error_message,
            }
            for row in rows
        ]
    }


@app.get("/api/fed/speeches/upcoming")
def fed_speeches_upcoming() -> dict[str, object]:
    database.init_schema()
    with database.session() as session:
        raw = session.scalars(
            select(schema.RawObservation)
            .where(schema.RawObservation.source_id == "fed-calendar")
            .order_by(schema.RawObservation.observed_at.desc())
            .limit(1)
        ).first()
    if raw is None:
        return {"events": [], "next_event": None}
    return {
        "events": raw.raw_payload.get("events", []),
        "next_event": raw.raw_payload.get("next_event"),
        "status": raw.status,
        "error_message": raw.error_message,
    }


@app.get("/api/fed/speech-risk/latest")
def fed_speech_risk_latest() -> dict[str, object]:
    database.init_schema()
    metric_ids = {
        "fed_speaker_weight",
        "fed_speech_hawkish_score",
        "fed_speech_dovish_score",
        "fed_speech_content_risk",
        "fed_speech_risk",
        "fed_speech_scheduled_risk",
        "next_fed_speech_hours_until",
        "fomc_blackout_active",
        "fomc_event_risk",
    }
    with database.session() as session:
        rows = session.scalars(
            select(schema.MetricValue)
            .where(schema.MetricValue.metric_id.in_(metric_ids))
            .order_by(schema.MetricValue.ts.desc())
            .limit(40)
        ).all()
    latest_by_metric: dict[str, dict[str, object]] = {}
    for row in rows:
        latest_by_metric.setdefault(
            row.metric_id,
            {
                "metric_id": row.metric_id,
                "source_id": row.source_id,
                "value": row.value,
                "quality_score": row.quality_score,
                "ts": row.ts.isoformat(),
            },
        )
    return {"metrics": latest_by_metric}


@app.get("/api/fed/blackout")
def fed_blackout_latest() -> dict[str, object]:
    database.init_schema()
    with database.session() as session:
        raw = session.scalars(
            select(schema.RawObservation)
            .where(schema.RawObservation.source_id == "fed-fomc-blackout-calendar")
            .order_by(schema.RawObservation.observed_at.desc())
            .limit(1)
        ).first()
    return raw.raw_payload if raw else {"active": False, "fomc_event_risk": None}


@app.post("/api/radars/analyze")
def analyze_radar_modules(
    module_ids: list[str] | None = None,
    run_mode: str = "live",
) -> dict[str, object]:
    return analyze_radars(module_ids=module_ids, run_mode=run_mode)


@app.get("/api/radars/latest")
def radar_outputs_latest() -> list[dict[str, object]]:
    return latest_radar_outputs()


@app.get("/api/p3/alerts/latest")
def p3_alerts_latest() -> dict[str, object]:
    return p45_dashboard.latest_alerts()


@app.get("/api/p3/events/latest")
def p3_events_latest() -> dict[str, object]:
    return p45_dashboard.latest_events()


@app.get("/api/p45/dashboard/latest")
def p45_dashboard_latest() -> dict[str, object]:
    return p45_dashboard.latest_dashboard()


@app.get("/api/p45/overview/latest")
def p45_overview_latest() -> dict[str, object]:
    return p45_dashboard.latest_overview()


@app.get("/api/p45/radar-modules/latest")
def p45_radar_modules_latest() -> dict[str, object]:
    return p45_dashboard.latest_radar_modules()


@app.get("/api/p45/radar-modules/{module_id}")
def p45_radar_module_detail(module_id: str) -> dict[str, object]:
    result = p45_dashboard.radar_module_detail(module_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Radar module not found")
    return result


@app.get("/api/p45/evidence")
def p45_evidence_latest(
    module_id: str | None = None,
    metric_id: str | None = None,
    limit: int = 500,
) -> dict[str, object]:
    return p45_dashboard.latest_evidence(
        module_id=module_id,
        metric_id=metric_id,
        limit=limit,
    )


@app.get("/api/p45/evidence/{evidence_id}")
def p45_evidence_detail(
    evidence_id: str,
    final_run_id: str | None = None,
    pack_id: str | None = None,
    allow_stale_fallback: bool = False,
) -> dict[str, object]:
    result = p45_dashboard.evidence_detail(
        evidence_id,
        final_run_id=final_run_id,
        pack_id=pack_id,
        allow_stale_fallback=allow_stale_fallback,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return result


@app.get("/api/p45/articles/latest")
def p45_articles_latest() -> dict[str, object]:
    return p45_dashboard.latest_articles()


@app.get("/api/p45/articles/history")
def p45_article_history(limit: int = 20) -> dict[str, object]:
    return p45_dashboard.article_history(limit=limit)


@app.get("/api/p45/llm/latest")
def p45_llm_latest() -> dict[str, object]:
    return p45_dashboard.latest_llm()


@app.get("/api/p45/analysts/latest")
def p45_analysts_latest() -> dict[str, object]:
    return p45_dashboard.latest_analysts()


@app.get("/api/p45/invalidation/latest")
def p45_invalidation_latest() -> dict[str, object]:
    return p45_dashboard.latest_invalidation()


@app.get("/api/data-quality/latest")
def p45_data_quality_latest() -> dict[str, object]:
    return p45_dashboard.latest_data_quality()


@app.get("/api/p45/runs/latest")
def p45_runs_latest() -> dict[str, object]:
    return p45_dashboard.latest_runs()


@app.post("/api/p45/run-full-with-llm/jobs")
async def p45_run_full_with_llm_job(
    run_mode: str = "live",
    runtime_mode: str = "deterministic",
    llm_runtime_mode: str = "llm",
    execution_profile: str | None = None,
    skip_llm: bool = False,
    skip_research_llm: bool = False,
    skip_analyst_llm: bool = False,
    refresh_html: bool = True,
) -> dict[str, object]:
    return ok_response(
        p45_jobs.start_full_chain_job(
            run_mode=run_mode,
            runtime_mode=runtime_mode,
            llm_runtime_mode=llm_runtime_mode,
            execution_profile=execution_profile,
            skip_llm=skip_llm,
            skip_research_llm=skip_research_llm,
            skip_analyst_llm=skip_analyst_llm,
            refresh_html=refresh_html,
        ),
        schema_version="p45.run_full_job.v1",
    )


@app.get("/api/p45/run-full-with-llm/jobs/latest")
def p45_run_full_with_llm_latest_job() -> dict[str, object]:
    result = p45_jobs.latest_job()
    if result is None:
        return ok_response(
            {"status": "missing", "job_run_id": None, "stages": []},
            schema_version="p45.run_full_job.v1",
        )
    return ok_response(result, schema_version="p45.run_full_job.v1")


@app.get("/api/p45/run-full-with-llm/jobs/{job_run_id}")
def p45_run_full_with_llm_job_status(job_run_id: str) -> dict[str, object]:
    result = p45_jobs.job_status(job_run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="P4.5 full chain job not found")
    return ok_response(result, schema_version="p45.run_full_job.v1")


@app.get("/api/events")
async def event_stream(
    request: Request,
    once: bool = False,
    interval_sec: float = 2.0,
) -> StreamingResponse:
    async def generate() -> Any:
        while True:
            payload = _event_stream_snapshot()
            yield _sse_event("p45_run_update", payload)
            if once or await request.is_disconnected():
                break
            await asyncio.sleep(max(1.0, min(interval_sec, 30.0)))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _event_stream_snapshot() -> dict[str, Any]:
    job = p45_jobs.latest_job() or {}
    runs = p45_dashboard.latest_runs()
    data_quality = p45_dashboard.latest_data_quality()
    alerts = p45_dashboard.latest_alerts()
    run_lineage = job.get("run_lineage") or runs.get("run_lineage") or runs.get("latest") or {}
    audit_reports = job.get("audit_reports") or runs.get("audit_reports") or {}
    reports = audit_reports.get("reports", []) if isinstance(audit_reports, dict) else []
    llm_errors = job.get("llm_errors") or (job.get("result") or {}).get("llm_errors") or []
    return {
        "schema_version": "p9.c10.events.v1",
        "event_id": f"evt-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
        "event_type": "p45_run_update",
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": job.get("job_run_id") or job.get("run_id") or run_lineage.get("final_run_id"),
        "current_stage": job.get("current_stage")
        or (runs.get("progress") or {}).get("current_stage"),
        "lineage": run_lineage,
        "status": job.get("status") or runs.get("run_status") or runs.get("status"),
        "error": (job.get("result") or {}).get("error"),
        "report_paths": {
            str(item.get("phase") or item.get("report_type") or item.get("filename")): (
                item.get("url") or item.get("relative_path")
            )
            for item in reports
            if isinstance(item, dict)
        },
        "llm_latency_summary": {
            "llm_status": job.get("llm_status"),
            "llm_enabled": job.get("llm_enabled"),
            "llm_errors": llm_errors,
        },
        "job": job,
        "data_quality": {
            "status": data_quality.get("status"),
            "contract_status": (data_quality.get("contract_validation") or {}).get("status"),
            "source_health": data_quality.get("source_health") or {},
        },
        "alerts": {
            "status": alerts.get("status"),
            "count": alerts.get("count", 0),
        },
        "recoverable": True,
    }


@app.get("/api/p45/history")
def p45_history_list(limit: int = 50) -> dict[str, object]:
    return p45_dashboard.history_list(limit=limit)


@app.get("/api/p45/history/{final_run_id}")
def p45_history_detail(final_run_id: str) -> dict[str, object]:
    result = p45_dashboard.history(final_run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="P4.5 run not found")
    return result


@app.get("/api/p45/audit-reports/latest")
def p45_audit_reports_latest() -> dict[str, object]:
    return p45_dashboard.audit_reports()


@app.post("/api/p6/articles/generate")
def p6_article_generate(final_run_id: str | None = None) -> dict[str, object]:
    try:
        return manual_generate_article(final_run_id=final_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/p6/articles/latest")
def p6_article_latest() -> dict[str, object]:
    result = latest_manual_article()
    if result is None:
        raise HTTPException(status_code=404, detail="P6 article snapshot not found")
    return result


@app.get("/api/p6/articles/history")
def p6_article_history(limit: int = 50) -> dict[str, object]:
    return p6_article_history_payload(limit=limit)


@app.get("/api/p6/articles/replay/{article_snapshot_id}")
def p6_article_replay(article_snapshot_id: str) -> dict[str, object]:
    result = replay_article_snapshot(article_snapshot_id)
    if result is None:
        raise HTTPException(status_code=404, detail="P6 article snapshot not found")
    return result


@app.get("/api/p6/articles/{article_snapshot_id}")
def p6_article_detail(article_snapshot_id: str) -> dict[str, object]:
    result = get_manual_article(article_snapshot_id)
    if result is None:
        raise HTTPException(status_code=404, detail="P6 article snapshot not found")
    return result


@app.get("/api/p6/alerts/history")
def p6_alert_history(limit: int = 100, alert_id: str | None = None) -> dict[str, object]:
    return p6_alert_history_payload(limit=limit, alert_id=alert_id)


@app.get("/api/p6/alerts/quality")
def p6_alert_quality(limit: int = 100, alert_id: str | None = None) -> dict[str, object]:
    return p6_alert_quality_payload(limit=limit, alert_id=alert_id)


@app.get("/api/p6/outcomes/track")
def p6_outcome_tracking(
    article_snapshot_id: str | None = None,
    limit: int = 50,
    run_mode: str = "live",
) -> dict[str, object]:
    return p6_outcome_tracking_payload(
        article_snapshot_id=article_snapshot_id,
        limit=limit,
        run_mode=run_mode,
    )


@app.get("/api/p6/modules/effectiveness")
def p6_module_effectiveness(
    article_snapshot_id: str | None = None,
    limit: int = 50,
    run_mode: str = "live",
) -> dict[str, object]:
    return p6_module_effectiveness_payload(
        article_snapshot_id=article_snapshot_id,
        limit=limit,
        run_mode=run_mode,
    )


@app.post("/api/p6/dod/mock-run")
def p6_dod_mock_run(
    article_snapshot_id: str | None = None,
    run_mode: str = "live",
    write_scores: bool = True,
) -> dict[str, object]:
    return run_p6_dod_mock(
        article_snapshot_id=article_snapshot_id,
        run_mode=run_mode,
        write_scores=write_scores,
    )


@app.get("/api/p6/dod/latest")
def p6_dod_latest() -> dict[str, object]:
    result = latest_p6_dod_report()
    if result is None:
        raise HTTPException(status_code=404, detail="P6 DoD report not found")
    return result


@app.get("/api/settings")
def settings_summary() -> dict[str, object]:
    return p45_dashboard.settings_summary()


@app.post("/api/settings/reload")
def settings_reload() -> dict[str, object]:
    reload_settings()
    return p45_dashboard.settings_summary()


@app.post("/api/settings/env")
def settings_env_update(request: SettingsEnvUpdateRequest) -> dict[str, object]:
    try:
        update_result = write_env_updates(request.updates)
    except ValueError as exc:
        record_settings_audit_event(
            action="env_update_rejected",
            env_keys=list(request.updates.keys()),
            status="failed",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    reload_settings()
    audit_event = record_settings_audit_event(
        action="env_update",
        env_keys=list(request.updates.keys()),
        status="success",
        backup_path=str(update_result.get("backup_path") or ""),
        operation_counts=update_result.get("operation_counts")
        if isinstance(update_result.get("operation_counts"), dict)
        else {},
    )
    return {
        **update_result,
        "audit_event": audit_event,
        "settings": p45_dashboard.settings_summary(),
    }


@app.get("/api/settings/audit")
def settings_key_audit(limit: int = 20) -> dict[str, object]:
    return settings_audit_summary(limit=max(1, min(limit, 100)))


@app.get("/api/settings/runtime")
def settings_runtime() -> dict[str, object]:
    return settings_runtime_payload()


@app.get("/api/settings/data-sources")
def settings_data_sources() -> dict[str, object]:
    return settings_data_sources_payload()


@app.get("/api/settings/paths")
def settings_paths() -> dict[str, object]:
    return settings_paths_payload()


@app.get("/api/settings/providers/health")
def settings_provider_health() -> dict[str, object]:
    return provider_health_snapshot()


@app.get("/api/settings/providers/glassnode/entitlement/latest")
def settings_glassnode_entitlement_latest() -> dict[str, object]:
    result = latest_glassnode_entitlement_report()
    if result is None:
        raise HTTPException(status_code=404, detail="Glassnode entitlement report not found")
    return result


@app.post("/api/settings/providers/glassnode/entitlement/audit")
async def settings_glassnode_entitlement_audit(mode: str = "dry_run") -> dict[str, object]:
    try:
        report = await run_glassnode_entitlement_audit(mode=mode)
    except ValueError as exc:
        record_settings_audit_event(
            action="glassnode_entitlement_audit",
            env_keys=[],
            provider_ids=["glassnode"],
            status="failed",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    written = write_glassnode_entitlement_report(report)
    record_settings_audit_event(
        action="glassnode_entitlement_audit",
        env_keys=[],
        provider_ids=["glassnode"],
        status=str(written.get("overall_status") or "completed"),
    )
    return written


@app.get("/api/settings/llm-routing")
def settings_llm_routing() -> dict[str, object]:
    return llm_routing_payload()


@app.post("/api/settings/providers/health/test-all")
async def settings_provider_health_test_all() -> dict[str, object]:
    result = await test_all_provider_health()
    provider_ids = [
        str(item.get("provider_id") or "")
        for item in result.get("items", [])
        if isinstance(item, dict)
    ]
    record_settings_audit_event(
        action="tested",
        env_keys=[],
        provider_ids=provider_ids,
        status="success",
    )
    return result


@app.post("/api/settings/providers/{provider_id}/test")
async def settings_provider_health_test(provider_id: str) -> dict[str, object]:
    try:
        result = await test_provider_health(provider_id)
    except ValueError as exc:
        record_settings_audit_event(
            action="tested",
            env_keys=[],
            provider_ids=[provider_id],
            status="failed",
            error_message=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_settings_audit_event(
        action="tested",
        env_keys=[],
        provider_ids=[provider_id],
        status=str(result.get("status") or "completed"),
        error_message=str(result.get("error_message") or ""),
    )
    return result


@app.post("/api/p45/run-full-with-llm")
async def p45_run_full_with_llm(
    run_mode: str = "live",
    runtime_mode: str = "deterministic",
    llm_runtime_mode: str = "llm",
    skip_llm: bool = False,
    skip_research_llm: bool = False,
    skip_analyst_llm: bool = False,
    refresh_html: bool = True,
) -> dict[str, object]:
    result = await run_p45_full_chain_with_llm_audit(
        collect_live=run_mode == "live",
        run_mode=run_mode,
        runtime_mode=runtime_mode,
        llm_runtime_mode=llm_runtime_mode,
        skip_llm=skip_llm,
        skip_research_llm=skip_research_llm,
        skip_analyst_llm=skip_analyst_llm,
        refresh_html=refresh_html,
    )
    return ok_response(
        result,
        schema_version="p45.run_full_with_llm.v1",
        run_lineage={
            "collect_run_id": result.get("collect_run_id"),
            "p2_radar_run_id": result.get("p2_radar_run_id"),
            "p3_run_id": result.get("p3_run_id"),
            "pack_id": result.get("pack_id"),
            "article_run_id": result.get("article_run_id"),
            "final_run_id": result.get("final_run_id"),
            "llm_research_run_id": result.get("llm_research_run_id"),
            "llm_analyst_run_id": result.get("llm_analyst_run_id"),
            "run_mode": result.get("run_mode"),
            "runtime_mode": result.get("runtime_mode"),
            "llm_runtime_mode": result.get("llm_runtime_mode"),
        },
    )


@app.post("/api/p45/evidence-pack")
def p45_evidence_pack(
    p3_run_id: str | None = None,
    pack_id: str | None = None,
) -> dict[str, object]:
    return build_p45_scored_evidence_pack(p3_run_id=p3_run_id, pack_id=pack_id)


@app.post("/api/p45/analyst-articles")
def p45_analyst_articles(
    pack_id: str | None = None,
    article_run_id: str | None = None,
    runtime_mode: str = "deterministic",
) -> dict[str, object]:
    return run_p45_analyst_writers(
        pack_id=pack_id,
        article_run_id=article_run_id,
        runtime_mode=runtime_mode,
    )


@app.post("/api/p45/final-article")
def p45_final_article(
    article_run_id: str | None = None,
    final_run_id: str | None = None,
    runtime_mode: str = "deterministic",
) -> dict[str, object]:
    return run_p45_final_writer(
        article_run_id=article_run_id,
        final_run_id=final_run_id,
        runtime_mode=runtime_mode,
    )


@app.post("/api/p45/html-report")
def p45_html_report(final_run_id: str | None = None) -> dict[str, object]:
    return run_p45_html_report(final_run_id=final_run_id)


@app.post("/api/p45/llm-research-writer")
def p45_llm_research_writer(
    final_run_id: str | None = None,
    research_run_id: str | None = None,
    runtime_mode: str = "llm",
    provider_name: str | None = None,
    refresh_html: bool = True,
) -> dict[str, object]:
    result = run_p45_llm_research_writer(
        final_run_id=final_run_id,
        research_run_id=research_run_id,
        runtime_mode=runtime_mode,
        provider_name=provider_name,
    )
    if refresh_html:
        result = {
            **result,
            "html_report": run_p45_html_report(final_run_id=result.get("final_run_id")),
        }
    return result


@app.post("/api/p45/llm-analyst-writers")
def p45_llm_analyst_writers(
    pack_id: str | None = None,
    analyst_run_id: str | None = None,
    runtime_mode: str = "llm",
    provider_name: str | None = None,
    refresh_html: bool = True,
) -> dict[str, object]:
    result = run_p45_llm_analyst_writers(
        pack_id=pack_id,
        analyst_run_id=analyst_run_id,
        runtime_mode=runtime_mode,
        provider_name=provider_name,
    )
    if refresh_html:
        result = {**result, "html_report": run_p45_html_report()}
    return result
