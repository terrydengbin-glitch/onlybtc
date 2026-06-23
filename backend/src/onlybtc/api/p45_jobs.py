from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from onlybtc.api import p45_dashboard
from onlybtc.audit.p3_full_chain import run_p3_full_chain_audit
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p6.article_pipeline import generate_auto_article_snapshot
from onlybtc.p45.evidence_pack import build_p45_scored_evidence_pack
from onlybtc.p45.final_writer import run_p45_final_writer
from onlybtc.p45.html_report import run_p45_html_report
from onlybtc.p45.llm_analyst_writer import run_p45_llm_analyst_writers
from onlybtc.p45.llm_research_writer import run_p45_llm_research_writer
from onlybtc.p45.writer import run_p45_analyst_writers

STAGES: list[tuple[str, str]] = [
    ("p1_collect", "P1 collect"),
    ("p2_radar", "P2 radar"),
    ("p3_scoring", "P3 scoring"),
    ("p45_final", "P4.5 final"),
    ("p45_llm_research", "P4.5 LLM research"),
    ("p45_llm_analysts", "P4.5 analyst LLM"),
    ("audit_reports", "Audit reports"),
]

ACTIVE_STATUSES = {"queued", "running"}
FULL_WITH_LLM_PROFILE = "full_with_llm"
FAST_DETERMINISTIC_PROFILE = "fast_deterministic"
VALID_EXECUTION_PROFILES = {FULL_WITH_LLM_PROFILE, FAST_DETERMINISTIC_PROFILE}


def start_full_chain_job(
    *,
    run_mode: str = "live",
    runtime_mode: str = "deterministic",
    llm_runtime_mode: str = "llm",
    execution_profile: str | None = None,
    skip_llm: bool = False,
    skip_research_llm: bool = False,
    skip_analyst_llm: bool = False,
    refresh_html: bool = True,
    db: Database = database,
) -> dict[str, Any]:
    options = _resolve_execution_options(
        execution_profile=execution_profile,
        skip_llm=skip_llm,
        skip_research_llm=skip_research_llm,
        skip_analyst_llm=skip_analyst_llm,
    )
    job_run_id = f"p45job-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    _init_job(
        job_run_id,
        {
            "run_mode": run_mode,
            "runtime_mode": runtime_mode,
            "llm_runtime_mode": llm_runtime_mode,
            **options,
            "refresh_html": refresh_html,
        },
        db=db,
    )
    asyncio.create_task(
        _run_full_chain_job(
            job_run_id=job_run_id,
            run_mode=run_mode,
            runtime_mode=runtime_mode,
            llm_runtime_mode=llm_runtime_mode,
            execution_profile=str(options["execution_profile"]),
            skip_llm=bool(options["skip_llm"]),
            skip_research_llm=bool(options["skip_research_llm"]),
            skip_analyst_llm=bool(options["skip_analyst_llm"]),
            refresh_html=refresh_html,
            db=db,
        )
    )
    return job_status(job_run_id, db=db) or {"job_run_id": job_run_id, "status": "queued"}


def job_status(job_run_id: str, db: Database = database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.Run).where(schema.Run.run_id == job_run_id).limit(1)
        )
        if row is None:
            return None
        stages = session.scalars(
            select(schema.RunStage)
            .where(schema.RunStage.run_id == job_run_id)
            .order_by(schema.RunStage.id)
        ).all()
        logs = session.scalars(
            select(schema.RunLog)
            .where(schema.RunLog.run_id == job_run_id)
            .order_by(schema.RunLog.created_at.desc(), schema.RunLog.id.desc())
            .limit(20)
        ).all()

    result = _latest_result(logs)
    params = _latest_params(logs)
    stages_payload = [_stage_payload(stage) for stage in stages]
    p45_final_stage = next((stage for stage in stages if stage.stage_name == "p45_final"), None)
    llm_research_stage = next((stage for stage in stages if stage.stage_name == "p45_llm_research"), None)
    llm_analyst_stage = next((stage for stage in stages if stage.stage_name == "p45_llm_analysts"), None)
    skip_llm = bool(result.get("skip_llm", params.get("skip_llm", False)))
    execution_options = _resolve_execution_options(
        execution_profile=str(result.get("execution_profile") or params.get("execution_profile") or ""),
        skip_llm=skip_llm,
        skip_research_llm=bool(result.get("skip_research_llm", params.get("skip_research_llm", False))),
        skip_analyst_llm=bool(result.get("skip_analyst_llm", params.get("skip_analyst_llm", False))),
    )
    execution_profile = str(execution_options["execution_profile"])
    llm_enabled = not bool(execution_options["skip_llm"])
    decision_ready = bool(result.get("final_run_id")) or p45_final_stage is not None and p45_final_stage.status == "completed"
    llm_status = _llm_status(llm_enabled, llm_research_stage, llm_analyst_stage)
    return {
        "job_run_id": row.run_id,
        "run_id": row.run_id,
        "status": row.status,
        "current_stage": row.current_stage,
        "execution_profile": execution_profile,
        "decision_ready": decision_ready,
        "deterministic_ready_at": _iso(p45_final_stage.completed_at) if p45_final_stage else None,
        "llm_enabled": llm_enabled,
        "llm_status": llm_status,
        "started_at": _iso(row.started_at or row.created_at),
        "completed_at": _iso(row.completed_at),
        "updated_at": _iso(row.updated_at),
        "run_lineage": result.get("run_lineage", {}),
        "result": result.get("result", {}),
        "stages": stages_payload,
        "logs": [_log_payload(log) for log in logs],
        "llm_errors": result.get("result", {}).get("llm_errors", []),
        "audit_reports": p45_dashboard.audit_reports(
            run_id=str(result.get("run_lineage", {}).get("final_run_id") or "")
        ),
    }


def latest_job(db: Database = database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        active = session.scalar(
            select(schema.Run)
            .where(
                schema.Run.trigger == "p45_full_chain",
                schema.Run.status.in_(ACTIVE_STATUSES),
            )
            .order_by(schema.Run.created_at.desc())
            .limit(1)
        )
        if active:
            return job_status(active.run_id, db=db)
        latest = session.scalar(
            select(schema.Run)
            .where(schema.Run.trigger == "p45_full_chain")
            .order_by(schema.Run.created_at.desc())
            .limit(1)
        )
        return job_status(latest.run_id, db=db) if latest else None


async def _run_full_chain_job(
    *,
    job_run_id: str,
    run_mode: str,
    runtime_mode: str,
    llm_runtime_mode: str,
    execution_profile: str,
    skip_llm: bool,
    skip_research_llm: bool,
    skip_analyst_llm: bool,
    refresh_html: bool,
    db: Database,
) -> None:
    result: dict[str, Any] = {}
    llm_errors: list[dict[str, Any]] = []
    try:
        _set_stage(job_run_id, "p1_collect", "running", "Running P1/P2/P3 full chain.", db=db)
        p3_result = await run_p3_full_chain_audit(
            collect_live=run_mode == "live",
            run_mode=run_mode,
            db=db,
        )
        _set_stage(job_run_id, "p1_collect", "completed", p3_result.get("collect_run_id"), db=db)
        _set_stage(job_run_id, "p2_radar", "completed", p3_result.get("p2_radar_run_id"), db=db)
        _set_stage(job_run_id, "p3_scoring", "completed", p3_result.get("p3_run_id"), db=db)

        _set_stage(job_run_id, "p45_final", "running", "Building P4.5 deterministic final.", db=db)
        pack = build_p45_scored_evidence_pack(p3_run_id=p3_result["p3_run_id"], db=db)
        analyst_articles = run_p45_analyst_writers(
            pack_id=pack["pack_id"],
            runtime_mode=runtime_mode,
            db=db,
        )
        final_article = run_p45_final_writer(
            article_run_id=analyst_articles["article_run_id"],
            runtime_mode=runtime_mode,
            db=db,
        )
        html_report = run_p45_html_report(final_run_id=final_article["final_run_id"], db=db)
        final_run_id = str(final_article["final_run_id"])
        pack_id = str(pack["pack_id"])
        p6_article = generate_auto_article_snapshot(final_run_id=final_run_id, db=db)
        result.update(
            {
                "status": "completed",
                "execution_profile": execution_profile,
                "decision_ready": True,
                "llm_enabled": not skip_llm,
                "skip_llm": skip_llm,
                "skip_research_llm": skip_research_llm,
                "skip_analyst_llm": skip_analyst_llm,
                "run_mode": run_mode,
                "runtime_mode": runtime_mode,
                "llm_runtime_mode": llm_runtime_mode,
                "collect_run_id": p3_result["collect_run_id"],
                "p2_radar_run_id": p3_result["p2_radar_run_id"],
                "p3_run_id": p3_result["p3_run_id"],
                "pack_id": pack_id,
                "article_run_id": analyst_articles["article_run_id"],
                "final_run_id": final_run_id,
                "p6_article_snapshot_id": p6_article.get("article_snapshot_id"),
                "reports": {
                    "p1": p3_result["p1_c22_html_path"],
                    "p2": p3_result["p2_html_path"],
                    "p3": p3_result["p3_html_path"],
                    "p45": html_report.get("html_path"),
                },
            }
        )
        _set_stage(job_run_id, "p45_final", "completed", final_run_id, db=db)
        _checkpoint_job(job_run_id, result, stage_name="p45_final", db=db)

        if skip_llm or skip_research_llm:
            _set_stage(job_run_id, "p45_llm_research", "skipped", "skipped_by_execution_profile", db=db)
        else:
            _set_stage(job_run_id, "p45_llm_research", "running", "Running LLM research writer.", db=db)
            try:
                research = run_p45_llm_research_writer(
                    final_run_id=final_run_id,
                    runtime_mode=llm_runtime_mode,
                    db=db,
                )
                result["llm_research_run_id"] = research.get("llm_research_run_id")
                _set_stage(
                    job_run_id,
                    "p45_llm_research",
                    "completed" if research.get("status") == "completed" else "failed",
                    research.get("llm_research_run_id") or research.get("error"),
                    db=db,
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                llm_errors.append({"stage": "llm_research", "error": f"{type(exc).__name__}: {exc}"})
                _set_stage(job_run_id, "p45_llm_research", "failed", str(exc), db=db)

        if skip_llm or skip_analyst_llm:
            _set_stage(job_run_id, "p45_llm_analysts", "skipped", "skipped_by_execution_profile", db=db)
        else:
            _set_stage(job_run_id, "p45_llm_analysts", "running", "Running analyst LLM writers.", db=db)
            try:
                analysts = run_p45_llm_analyst_writers(
                    pack_id=pack_id,
                    runtime_mode=llm_runtime_mode,
                    db=db,
                )
                result["llm_analyst_run_id"] = analysts.get("llm_analyst_run_id")
                failed = int(analysts.get("summary", {}).get("failed_count") or 0)
                if failed:
                    llm_errors.append({"stage": "llm_analysts", "error": f"{failed} analyst article(s) failed"})
                _set_stage(
                    job_run_id,
                    "p45_llm_analysts",
                    "completed" if not failed else "failed",
                    analysts.get("llm_analyst_run_id"),
                    db=db,
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                llm_errors.append({"stage": "llm_analysts", "error": f"{type(exc).__name__}: {exc}"})
                _set_stage(job_run_id, "p45_llm_analysts", "failed", str(exc), db=db)

        if refresh_html:
            _set_stage(job_run_id, "audit_reports", "running", "Refreshing P4.5 HTML.", db=db)
            html_report = run_p45_html_report(final_run_id=final_run_id, db=db)
            result["reports"]["p45"] = html_report.get("html_path")
        _set_stage(job_run_id, "audit_reports", "completed", "reports refreshed", db=db)

        result["status"] = "completed" if not llm_errors else "completed_with_llm_errors"
        result["llm_errors"] = llm_errors
        _complete_job(job_run_id, "completed", result, db=db)
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        _complete_job(job_run_id, "failed", result, db=db)


def _init_job(job_run_id: str, params: dict[str, Any], db: Database) -> None:
    db.init_schema()
    now = datetime.now(UTC)
    with db.session() as session:
        session.add(
            schema.Run(
                run_id=job_run_id,
                trigger="p45_full_chain",
                status="queued",
                current_stage="queued",
                started_at=now,
            )
        )
        for stage_id, _label in STAGES:
            session.add(
                schema.RunStage(
                    run_id=job_run_id,
                    stage_name=stage_id,
                    status="pending",
                    detail="",
                )
            )
        session.add(
            schema.RunLog(
                run_id=job_run_id,
                stage_name="queued",
                level="INFO",
                message="P4.5 full chain job queued.",
                metadata_json={"params": params},
            )
        )


def _set_stage(
    job_run_id: str,
    stage_id: str,
    status: str,
    detail: Any = "",
    db: Database = database,
) -> None:
    db.init_schema()
    now = datetime.now(UTC)
    with db.session() as session:
        run = session.scalar(select(schema.Run).where(schema.Run.run_id == job_run_id).limit(1))
        if run:
            run.status = "running"
            run.current_stage = stage_id
        stage = session.scalar(
            select(schema.RunStage)
            .where(schema.RunStage.run_id == job_run_id, schema.RunStage.stage_name == stage_id)
            .limit(1)
        )
        if stage:
            stage.status = status
            stage.detail = str(detail or "")
            if status == "running" and stage.started_at is None:
                stage.started_at = now
            if status in {"completed", "failed", "skipped"}:
                stage.completed_at = now
                if stage.started_at is None:
                    stage.started_at = now
        session.add(
            schema.RunLog(
                run_id=job_run_id,
                stage_name=stage_id,
                level="ERROR" if status == "failed" else "INFO",
                message=f"{stage_id}: {status}",
                metadata_json={"detail": detail},
            )
        )


def _checkpoint_job(
    job_run_id: str,
    result: dict[str, Any],
    *,
    stage_name: str,
    db: Database,
) -> None:
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.RunLog(
                run_id=job_run_id,
                stage_name=stage_name,
                level="INFO",
                message=f"{stage_name}: checkpoint",
                metadata_json={
                    "result": result,
                    "run_lineage": _run_lineage_from_result(result),
                },
            )
        )


def _complete_job(job_run_id: str, status: str, result: dict[str, Any], db: Database) -> None:
    db.init_schema()
    now = datetime.now(UTC)
    with db.session() as session:
        run = session.scalar(select(schema.Run).where(schema.Run.run_id == job_run_id).limit(1))
        if run:
            run.status = status
            run.current_stage = "completed" if status == "completed" else "failed"
            run.completed_at = now
        session.add(
            schema.RunLog(
                run_id=job_run_id,
                stage_name="completed" if status == "completed" else "failed",
                level="INFO" if status == "completed" else "ERROR",
                message=f"P4.5 full chain job {status}.",
                metadata_json={
                    "result": result,
                    "run_lineage": _run_lineage_from_result(result),
                },
            )
        )


def _latest_result(logs: list[schema.RunLog]) -> dict[str, Any]:
    for log in logs:
        metadata = log.metadata_json or {}
        if "result" in metadata or "run_lineage" in metadata:
            return metadata
    return {}


def _latest_params(logs: list[schema.RunLog]) -> dict[str, Any]:
    for log in reversed(logs):
        metadata = log.metadata_json or {}
        params = metadata.get("params")
        if isinstance(params, dict):
            return params
    return {}


def _stage_payload(stage: schema.RunStage) -> dict[str, Any]:
    return {
        "stage_id": stage.stage_name,
        "label": dict(STAGES).get(stage.stage_name, stage.stage_name),
        "status": stage.status,
        "detail": stage.detail,
        "worker_id": stage.worker_id,
        "started_at": _iso(stage.started_at),
        "completed_at": _iso(stage.completed_at),
        "run_id": stage.detail if stage.status == "completed" else None,
    }


def _log_payload(log: schema.RunLog) -> dict[str, Any]:
    return {
        "stage_id": log.stage_name,
        "level": log.level,
        "message": log.message,
        "created_at": _iso(log.created_at),
        "metadata": log.metadata_json or {},
    }


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _resolve_execution_options(
    *,
    execution_profile: str | None,
    skip_llm: bool,
    skip_research_llm: bool,
    skip_analyst_llm: bool,
) -> dict[str, Any]:
    profile = (execution_profile or "").strip() or (
        FAST_DETERMINISTIC_PROFILE if skip_llm else FULL_WITH_LLM_PROFILE
    )
    if profile not in VALID_EXECUTION_PROFILES:
        profile = FULL_WITH_LLM_PROFILE
    if profile == FAST_DETERMINISTIC_PROFILE:
        skip_llm = True
        skip_research_llm = True
        skip_analyst_llm = True
    return {
        "execution_profile": profile,
        "skip_llm": skip_llm,
        "skip_research_llm": skip_research_llm or skip_llm,
        "skip_analyst_llm": skip_analyst_llm or skip_llm,
    }


def _llm_status(
    llm_enabled: bool,
    research_stage: schema.RunStage | None,
    analyst_stage: schema.RunStage | None,
) -> str:
    if not llm_enabled:
        return "skipped"
    statuses = [stage.status for stage in (research_stage, analyst_stage) if stage is not None]
    if any(status == "running" for status in statuses):
        return "running"
    if any(status == "failed" for status in statuses):
        return "failed"
    if statuses and all(status == "completed" for status in statuses):
        return "completed"
    return "pending"


def _run_lineage_from_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "execution_profile": result.get("execution_profile"),
    }
