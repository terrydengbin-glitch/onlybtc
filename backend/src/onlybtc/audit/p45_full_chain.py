from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select

from onlybtc.audit.p3_full_chain import run_p3_full_chain_audit
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p45.evidence_pack import build_p45_scored_evidence_pack
from onlybtc.p45.final_writer import run_p45_final_writer
from onlybtc.p45.html_report import run_p45_html_report
from onlybtc.p45.llm_analyst_writer import run_p45_llm_analyst_writers
from onlybtc.p45.llm_research_writer import run_p45_llm_research_writer
from onlybtc.p45.writer import run_p45_analyst_writers


async def run_p45_full_chain_audit(
    collect_live: bool = True,
    run_mode: str = "live",
    runtime_mode: str = "deterministic",
    db: Database = database,
) -> dict[str, Any]:
    p3_result = await run_p3_full_chain_audit(
        collect_live=collect_live,
        run_mode=run_mode,
        db=db,
    )
    pack = build_p45_scored_evidence_pack(
        p3_run_id=p3_result["p3_run_id"],
        db=db,
    )
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
    html_report = run_p45_html_report(
        final_run_id=final_article["final_run_id"],
        db=db,
    )
    return {
        "status": "completed",
        "run_mode": run_mode,
        "runtime_mode": runtime_mode,
        "p1_c22_html_path": p3_result["p1_c22_html_path"],
        "p2_html_path": p3_result["p2_html_path"],
        "p3_html_path": p3_result["p3_html_path"],
        "p45_html_path": html_report["html_path"],
        "collect_run_id": p3_result["collect_run_id"],
        "p2_radar_run_id": p3_result["p2_radar_run_id"],
        "p3_run_id": p3_result["p3_run_id"],
        "pack_id": pack["pack_id"],
        "article_run_id": analyst_articles["article_run_id"],
        "final_run_id": final_article["final_run_id"],
        "core_view": final_article["core_view"],
        "summary": {
            "p3": p3_result.get("pipeline_summary", {}),
            "pack": pack.get("summary", {}),
            "articles": analyst_articles.get("summary", {}),
            "final": final_article.get("summary", {}),
        },
    }


def run_p45_full_chain_audit_sync(
    collect_live: bool = True,
    run_mode: str = "live",
    runtime_mode: str = "deterministic",
) -> dict[str, Any]:
    return asyncio.run(
        run_p45_full_chain_audit(
            collect_live=collect_live,
            run_mode=run_mode,
            runtime_mode=runtime_mode,
        )
    )


async def run_p45_full_chain_with_llm_audit(
    collect_live: bool = True,
    run_mode: str = "live",
    runtime_mode: str = "deterministic",
    llm_runtime_mode: str = "llm",
    skip_llm: bool = False,
    skip_research_llm: bool = False,
    skip_analyst_llm: bool = False,
    refresh_html: bool = True,
    db: Database = database,
) -> dict[str, Any]:
    deterministic = await run_p45_full_chain_audit(
        collect_live=collect_live,
        run_mode=run_mode,
        runtime_mode=runtime_mode,
        db=db,
    )
    final_run_id = str(deterministic["final_run_id"])
    pack_id = str(deterministic["pack_id"])

    research_result: dict[str, Any] | None = None
    analyst_result: dict[str, Any] | None = None
    llm_errors: list[dict[str, Any]] = []

    if not skip_llm and not skip_research_llm:
        try:
            research_result = run_p45_llm_research_writer(
                final_run_id=final_run_id,
                runtime_mode=llm_runtime_mode,
                db=db,
            )
            if research_result.get("status") != "completed":
                llm_errors.append(
                    {
                        "stage": "llm_research",
                        "run_id": research_result.get("llm_research_run_id"),
                        "error": research_result.get("error") or "not completed",
                    }
                )
        except Exception as exc:
            llm_errors.append(
                {
                    "stage": "llm_research",
                    "run_id": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    if not skip_llm and not skip_analyst_llm:
        try:
            analyst_result = run_p45_llm_analyst_writers(
                pack_id=pack_id,
                runtime_mode=llm_runtime_mode,
                db=db,
            )
            failed_count = int(analyst_result.get("summary", {}).get("failed_count") or 0)
            if failed_count:
                llm_errors.append(
                    {
                        "stage": "llm_analysts",
                        "run_id": analyst_result.get("llm_analyst_run_id"),
                        "error": f"{failed_count} analyst article(s) failed",
                    }
                )
        except Exception as exc:
            llm_errors.append(
                {
                    "stage": "llm_analysts",
                    "run_id": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    html_report = (
        run_p45_html_report(final_run_id=final_run_id, db=db)
        if refresh_html
        else {"status": "skipped", "html_path": deterministic.get("p45_html_path")}
    )
    final_payload = _load_module_payload(
        db=db,
        run_id=final_run_id,
        module_id="p45_final_article",
    )
    contract_validation = (final_payload or {}).get("contract_validation") or {}
    llm_summary = _llm_summary(research_result, analyst_result, skip_llm)
    status = "completed" if not llm_errors else "completed_with_llm_errors"

    return {
        "status": status,
        "run_mode": run_mode,
        "runtime_mode": runtime_mode,
        "llm_runtime_mode": llm_runtime_mode,
        "skip_llm": skip_llm,
        "collect_run_id": deterministic["collect_run_id"],
        "p2_radar_run_id": deterministic["p2_radar_run_id"],
        "p3_run_id": deterministic["p3_run_id"],
        "pack_id": pack_id,
        "article_run_id": deterministic["article_run_id"],
        "final_run_id": final_run_id,
        "llm_research_run_id": (research_result or {}).get("llm_research_run_id"),
        "llm_analyst_run_id": (analyst_result or {}).get("llm_analyst_run_id"),
        "llm_provider": _first_non_empty(
            (research_result or {}).get("provider"),
            (analyst_result or {}).get("provider"),
        ),
        "llm_model": _first_non_empty(
            (research_result or {}).get("model"),
            _first_analyst_model(analyst_result),
        ),
        "reports": {
            "p1": deterministic["p1_c22_html_path"],
            "p2": deterministic["p2_html_path"],
            "p3": deterministic["p3_html_path"],
            "p45": html_report.get("html_path") or deterministic.get("p45_html_path"),
        },
        "contract_validation": {
            "status": contract_validation.get("status"),
            "errors": contract_validation.get("errors", []),
            "warnings": contract_validation.get("warnings", []),
        },
        "llm_summary": llm_summary,
        "lineage_check": {
            "research_final_run_id_matches": (
                skip_llm
                or skip_research_llm
                or (research_result or {}).get("final_run_id") == final_run_id
            ),
            "analyst_pack_id_matches": (
                skip_llm
                or skip_analyst_llm
                or (analyst_result or {}).get("pack_id") == pack_id
            ),
            "html_refreshed": html_report.get("status") == "completed",
        },
        "llm_errors": llm_errors,
        "deterministic_summary": deterministic.get("summary", {}),
    }


def run_p45_full_chain_with_llm_audit_sync(
    collect_live: bool = True,
    run_mode: str = "live",
    runtime_mode: str = "deterministic",
    llm_runtime_mode: str = "llm",
    skip_llm: bool = False,
    skip_research_llm: bool = False,
    skip_analyst_llm: bool = False,
    refresh_html: bool = True,
) -> dict[str, Any]:
    return asyncio.run(
        run_p45_full_chain_with_llm_audit(
            collect_live=collect_live,
            run_mode=run_mode,
            runtime_mode=runtime_mode,
            llm_runtime_mode=llm_runtime_mode,
            skip_llm=skip_llm,
            skip_research_llm=skip_research_llm,
            skip_analyst_llm=skip_analyst_llm,
            refresh_html=refresh_html,
        )
    )


def _load_module_payload(
    db: Database,
    run_id: str,
    module_id: str,
) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(
                schema.ModuleJsonOutput.run_id == run_id,
                schema.ModuleJsonOutput.module_id == module_id,
            )
            .order_by(schema.ModuleJsonOutput.created_at.desc())
            .limit(1)
        )
        return row.payload if row else None


def _llm_summary(
    research_result: dict[str, Any] | None,
    analyst_result: dict[str, Any] | None,
    skip_llm: bool,
) -> dict[str, Any]:
    analyst_summary = (analyst_result or {}).get("summary") or {}
    research_latency = int((research_result or {}).get("latency_ms") or 0)
    analyst_latencies = [
        int(item.get("latency_ms") or 0)
        for item in (analyst_result or {}).get("analyst_articles", [])
    ]
    analyst_total_latency = sum(analyst_latencies)
    return {
        "research_status": "skipped" if skip_llm else (research_result or {}).get("status"),
        "analyst_completed_count": analyst_summary.get("completed_count", 0),
        "analyst_failed_count": analyst_summary.get("failed_count", 0),
        "radar_modules_covered": len(analyst_summary.get("radar_modules_covered", [])),
        "llm_provider": _first_non_empty(
            (research_result or {}).get("provider"),
            (analyst_result or {}).get("provider"),
        ),
        "llm_model": _first_non_empty(
            (research_result or {}).get("model"),
            _first_analyst_model(analyst_result),
        ),
        "llm_research_latency_ms": research_latency,
        "llm_analyst_total_latency_ms": analyst_total_latency,
        "llm_total_latency_ms": research_latency + analyst_total_latency,
        "analyst_latencies_ms": {
            str(item.get("analyst_id")): int(item.get("latency_ms") or 0)
            for item in (analyst_result or {}).get("analyst_articles", [])
            if item.get("analyst_id")
        },
        "analyst_statuses": {
            str(item.get("analyst_id")): {
                "status": item.get("status"),
                "error": item.get("error"),
                "latency_ms": item.get("latency_ms"),
                "provider": item.get("provider"),
                "model": item.get("model"),
            }
            for item in (analyst_result or {}).get("analyst_articles", [])
            if item.get("analyst_id")
        },
    }


def _first_analyst_model(analyst_result: dict[str, Any] | None) -> str | None:
    for item in (analyst_result or {}).get("analyst_articles", []):
        if item.get("model"):
            return str(item["model"])
    return None


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value:
            return value
    return None
