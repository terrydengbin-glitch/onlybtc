from __future__ import annotations

import asyncio

import typer
import uvicorn
from rich.console import Console

from onlybtc.algorithms.features import calculate_p3_features
from onlybtc.algorithms.p3 import (
    check_global_invalidations,
    check_module_invalidations,
    detect_anomalies,
    detect_divergences,
    detect_event_windows,
    generate_algorithm_alerts,
    p3_summary,
    run_p3_pipeline,
)
from onlybtc.audit.p1_c22 import run_p1_c22_audit_sync
from onlybtc.audit.p2_full_chain import run_p2_full_chain_audit_sync
from onlybtc.audit.p3_full_chain import run_p3_full_chain_audit_sync
from onlybtc.audit.p4_dod import run_p4_dod_check
from onlybtc.audit.p4_full_chain import run_p4_full_chain_audit_sync
from onlybtc.audit.p4_radar_coverage import run_p4_radar_coverage_audit
from onlybtc.audit.p45_full_chain import (
    run_p45_full_chain_audit_sync,
    run_p45_full_chain_with_llm_audit_sync,
)
from onlybtc.core.config import get_settings
from onlybtc.core.logging import configure_logging
from onlybtc.core.paths import paths
from onlybtc.db.maintenance import (
    archive_non_live_metric_values,
    backup_database,
    export_schema_sql,
    run_mode_audit,
    vacuum_database,
)
from onlybtc.db.repositories import PageQueryRepository
from onlybtc.db.seed import seed_demo_data
from onlybtc.db.session import database
from onlybtc.direct_trend.evidence import build_btc_direct_trend_evidence
from onlybtc.direct_trend.registry import build_direct_evidence_registry
from onlybtc.direct_trend.replay import list_timescale_judge_replays, replay_timescale_judge
from onlybtc.direct_trend.state_machine import build_direct_trend_state_machine
from onlybtc.p4.adversarial_review import run_adversarial_review
from onlybtc.p4.analyst_executor import run_analyst_agents
from onlybtc.p4.cross_exam import run_cross_examination
from onlybtc.p4.cross_exam_revision import run_cross_exam_revisions
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.p4.final_controller import build_final_controller_json
from onlybtc.p4.judge import run_judge_synthesis
from onlybtc.p4.rule_baseline import build_rule_baseline
from onlybtc.p4.state_machine import run_state_machine
from onlybtc.p45.evidence_pack import build_p45_scored_evidence_pack
from onlybtc.p45.final_writer import run_p45_final_writer
from onlybtc.p45.html_report import run_p45_html_report
from onlybtc.p45.llm_analyst_writer import run_p45_llm_analyst_writers
from onlybtc.p45.llm_research_writer import run_p45_llm_research_writer
from onlybtc.p45.writer import run_p45_analyst_writers
from onlybtc.pipeline.run_once import run_once_mock
from onlybtc.radars.service import analyze_radars, latest_radar_outputs
from onlybtc.sources.models import SourceMode
from onlybtc.sources.provider_auth import (
    auth_status,
    bootstrap_provider_login,
    verify_provider_login,
)
from onlybtc.sources.service import collect_sources, historical_window, source_health_summary

app = typer.Typer(help="onlyBTC command line")
console = Console()
SOURCE_MODE_OPTION = typer.Option(SourceMode.MOCK, help="mock or live")
SOURCE_ID_OPTION = typer.Option(None, help="collect only selected source id")
METRIC_ID_OPTION = typer.Option(None, "--metric-id", help="metric id to calculate")
FEATURE_LIMIT_OPTION = typer.Option(120, help="historical sample limit per metric")
RUN_MODE_OPTION = typer.Option("live", help="live, mock, test, or all")


@app.callback()
def main() -> None:
    configure_logging()


@app.command()
def health() -> None:
    settings = get_settings()
    paths.ensure_directories()
    console.print(
        {
            "app": settings.app_name,
            "environment": settings.environment,
            "status": "healthy",
        }
    )


@app.command("show-paths")
def show_paths() -> None:
    paths.ensure_directories()
    console.print(paths.as_dict())


@app.command("db-init")
def db_init() -> None:
    database.init_schema()
    console.print(
        {
            "status": "initialized",
            "sqlite_db_path": str(database.db_path),
            "journal_mode": database.pragma("journal_mode"),
            "foreign_keys": database.pragma("foreign_keys"),
        }
    )


@app.command("db-seed")
def db_seed() -> None:
    console.print(seed_demo_data())


@app.command("db-health")
def db_health() -> None:
    database.init_schema()
    with database.session() as session:
        counts = PageQueryRepository(session).table_counts()
    console.print(
        {
            "sqlite_db_path": str(database.db_path),
            "table_count": len(counts),
            "counts": counts,
        }
    )


@app.command("db-backup")
def db_backup() -> None:
    console.print({"backup_path": str(backup_database())})


@app.command("db-vacuum")
def db_vacuum() -> None:
    vacuum_database()
    console.print({"status": "vacuumed"})


@app.command("db-export-schema")
def db_export_schema() -> None:
    console.print({"schema_path": str(export_schema_sql())})


@app.command("db-run-mode-audit")
def db_run_mode_audit() -> None:
    console.print(run_mode_audit())


@app.command("db-archive-non-live")
def db_archive_non_live() -> None:
    console.print(archive_non_live_metric_values())


@app.command("collect-sources")
def collect_sources_command(
    mode: SourceMode = SOURCE_MODE_OPTION,
    source_id: list[str] | None = SOURCE_ID_OPTION,
) -> None:
    console.print(asyncio.run(collect_sources(mode=mode, source_ids=source_id)))


@app.command("sources-health")
def sources_health_command() -> None:
    console.print(source_health_summary())


@app.command("provider-login")
def provider_login_command(
    provider_id: str = typer.Argument(..., help="provider id, e.g. glassnode"),
    timeout_seconds: int = typer.Option(600, help="seconds to wait for manual login"),
    manual_confirm: bool = typer.Option(
        False,
        help="press Enter in terminal instead of auto-detect",
    ),
) -> None:
    result = asyncio.run(bootstrap_provider_login(provider_id, timeout_seconds, manual_confirm))
    console.print(result)


@app.command("provider-auth-status")
def provider_auth_status_command(
    provider_id: str = typer.Argument(..., help="provider id, e.g. glassnode"),
    verify: bool = typer.Option(False, help="open provider with saved session and verify login"),
) -> None:
    result = asyncio.run(verify_provider_login(provider_id)) if verify else auth_status(provider_id)
    console.print(result)


@app.command("metric-window")
def metric_window_command(
    metric_id: str,
    source_id: str | None = None,
    run_mode: str = RUN_MODE_OPTION,
) -> None:
    console.print(historical_window(metric_id=metric_id, source_id=source_id, run_mode=run_mode))


@app.command("analyze-radars")
def analyze_radars_command(
    module_id: list[str] | None = None,
    run_mode: str = RUN_MODE_OPTION,
) -> None:
    console.print(analyze_radars(module_ids=module_id, run_mode=run_mode))


@app.command("latest-radars")
def latest_radars_command() -> None:
    console.print(latest_radar_outputs())


@app.command("p3-features")
def p3_features_command(
    metric_id: list[str] | None = METRIC_ID_OPTION,
    limit: int = FEATURE_LIMIT_OPTION,
    run_mode: str = RUN_MODE_OPTION,
) -> None:
    console.print(calculate_p3_features(metric_ids=metric_id, limit=limit, run_mode=run_mode))


@app.command("btc-direct-trend-evidence")
def btc_direct_trend_evidence_command(
    run_mode: str = RUN_MODE_OPTION,
    collect_run_id: str | None = typer.Option(None, "--collect-run-id", help="scope to a collect run"),
    historical_fallback: bool = typer.Option(
        True,
        help="allow historical fallback when collect-run metrics are absent",
    ),
) -> None:
    console.print(
        build_btc_direct_trend_evidence(
            run_mode=run_mode,
            collect_run_id=collect_run_id,
            historical_fallback=historical_fallback,
        )
    )


@app.command("btc-direct-evidence-registry")
def btc_direct_evidence_registry_command(
    evidence_run_id: str | None = typer.Option(
        None,
        "--evidence-run-id",
        help="P1 direct evidence run id; defaults to latest",
    ),
) -> None:
    console.print(build_direct_evidence_registry(evidence_run_id=evidence_run_id))


@app.command("btc-direct-trend-state")
def btc_direct_trend_state_command(
    evidence_run_id: str | None = typer.Option(None, "--evidence-run-id", help="P1 evidence run id"),
    registry_run_id: str | None = typer.Option(None, "--registry-run-id", help="P2 registry run id"),
) -> None:
    console.print(
        build_direct_trend_state_machine(
            evidence_run_id=evidence_run_id,
            registry_run_id=registry_run_id,
        )
    )


@app.command("btc-timescale-replay")
def btc_timescale_replay_command(
    run_id: str | None = typer.Option(None, "--run-id", help="P4.5 final run id"),
    snapshot_id: str | None = typer.Option(None, "--snapshot-id", help="timescale snapshot id"),
    asof_ts: str | None = typer.Option(None, "--asof-ts", help="replay latest snapshot at or before timestamp"),
    limit: int | None = typer.Option(None, "--limit", help="list recent replay snapshots"),
) -> None:
    if limit is not None:
        console.print(list_timescale_judge_replays(limit=limit))
        return
    console.print(
        replay_timescale_judge(
            run_id=run_id,
            snapshot_id=snapshot_id,
            asof_ts=asof_ts,
            latest=not any([run_id, snapshot_id, asof_ts]),
        )
    )


@app.command("p3-run")
def p3_run_command(
    metric_id: list[str] | None = METRIC_ID_OPTION,
    run_mode: str = RUN_MODE_OPTION,
) -> None:
    console.print(run_p3_pipeline(metric_ids=metric_id, run_mode=run_mode))


@app.command("p3-anomalies")
def p3_anomalies_command(
    metric_id: list[str] | None = METRIC_ID_OPTION,
    run_mode: str = RUN_MODE_OPTION,
) -> None:
    console.print(detect_anomalies(metric_ids=metric_id, run_mode=run_mode))


@app.command("p3-divergences")
def p3_divergences_command(run_mode: str = RUN_MODE_OPTION) -> None:
    console.print(detect_divergences(run_mode=run_mode))


@app.command("p3-invalidations")
def p3_invalidations_command(run_mode: str = RUN_MODE_OPTION) -> None:
    module_result = check_module_invalidations(run_mode=run_mode)
    global_result = check_global_invalidations(
        run_id=module_result["run_id"],
        run_mode=run_mode,
    )
    console.print({"module": module_result, "global": global_result})


@app.command("p3-event-windows")
def p3_event_windows_command(run_mode: str = RUN_MODE_OPTION) -> None:
    console.print(detect_event_windows(run_mode=run_mode))


@app.command("p3-alerts")
def p3_alerts_command(run_mode: str = RUN_MODE_OPTION) -> None:
    console.print(generate_algorithm_alerts(run_mode=run_mode))


@app.command("p3-summary")
def p3_summary_command() -> None:
    console.print(p3_summary())


@app.command("p1-c22-audit")
def p1_c22_audit_command(
    collect_live: bool = typer.Option(True, help="run live source collection before audit"),
    source_id: list[str] | None = SOURCE_ID_OPTION,
) -> None:
    console.print(run_p1_c22_audit_sync(collect_live=collect_live, source_ids=source_id))


@app.command("p2-full-audit")
def p2_full_audit_command(
    collect_live: bool = typer.Option(True, help="run P1-C22 live collection first"),
    run_mode: str = RUN_MODE_OPTION,
) -> None:
    console.print(run_p2_full_chain_audit_sync(collect_live=collect_live, run_mode=run_mode))


@app.command("p3-full-audit")
def p3_full_audit_command(
    collect_live: bool = typer.Option(True, help="run P1/P2 live chain first"),
    run_mode: str = RUN_MODE_OPTION,
) -> None:
    console.print(run_p3_full_chain_audit_sync(collect_live=collect_live, run_mode=run_mode))


@app.command("p4-full-audit")
def p4_full_audit_command(
    collect_live: bool = typer.Option(True, help="run P1/P2/P3 live chain first"),
    run_mode: str = RUN_MODE_OPTION,
    runtime_mode: str = typer.Option("mock", help="P4 agent runtime mode"),
    article_runtime_mode: str = typer.Option("mock", help="P4 article writer runtime: mock or llm"),
) -> None:
    console.print(
        run_p4_full_chain_audit_sync(
            collect_live=collect_live,
            run_mode=run_mode,
            runtime_mode=runtime_mode,
            article_runtime_mode=article_runtime_mode,
        )
    )


@app.command("p45-full-audit")
def p45_full_audit_command(
    collect_live: bool = typer.Option(True, help="run P1/P2/P3 live chain first"),
    run_mode: str = RUN_MODE_OPTION,
    runtime_mode: str = typer.Option("deterministic", help="P4.5 writer runtime mode"),
) -> None:
    console.print(
        run_p45_full_chain_audit_sync(
            collect_live=collect_live,
            run_mode=run_mode,
            runtime_mode=runtime_mode,
        )
    )


@app.command("p45-full-audit-with-llm")
def p45_full_audit_with_llm_command(
    collect_live: bool = typer.Option(True, help="run P1/P2/P3 live chain first"),
    run_mode: str = RUN_MODE_OPTION,
    runtime_mode: str = typer.Option("deterministic", help="P4.5 writer runtime mode"),
    llm_runtime_mode: str = typer.Option("llm", help="P4.5 LLM writer runtime mode"),
    skip_llm: bool = typer.Option(False, help="skip both LLM research and analyst writers"),
    skip_research_llm: bool = typer.Option(False, help="skip LLM research writer only"),
    skip_analyst_llm: bool = typer.Option(False, help="skip four analyst LLM writers only"),
    refresh_html: bool = typer.Option(True, help="refresh final P4.5 HTML after all stages"),
) -> None:
    console.print(
        run_p45_full_chain_with_llm_audit_sync(
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


@app.command("p45-build-evidence-pack")
def p45_build_evidence_pack_command(
    p3_run_id: str | None = typer.Option(None, help="P3 scored evidence run id"),
    pack_id: str | None = typer.Option(None, help="P4.5 evidence pack id"),
) -> None:
    console.print(build_p45_scored_evidence_pack(p3_run_id=p3_run_id, pack_id=pack_id))


@app.command("p45-run-analysts")
def p45_run_analysts_command(
    pack_id: str | None = typer.Option(None, help="P4.5 evidence pack id"),
    article_run_id: str | None = typer.Option(None, help="P4.5 analyst article run id"),
    runtime_mode: str = typer.Option("deterministic", help="P4.5 writer runtime mode"),
) -> None:
    console.print(
        run_p45_analyst_writers(
            pack_id=pack_id,
            article_run_id=article_run_id,
            runtime_mode=runtime_mode,
        )
    )


@app.command("p45-final-writer")
def p45_final_writer_command(
    article_run_id: str | None = typer.Option(None, help="P4.5 analyst article run id"),
    final_run_id: str | None = typer.Option(None, help="P4.5 final article run id"),
    runtime_mode: str = typer.Option("deterministic", help="P4.5 writer runtime mode"),
) -> None:
    console.print(
        run_p45_final_writer(
            article_run_id=article_run_id,
            final_run_id=final_run_id,
            runtime_mode=runtime_mode,
        )
    )


@app.command("p45-html-report")
def p45_html_report_command(
    final_run_id: str | None = typer.Option(None, help="P4.5 final article run id"),
) -> None:
    console.print(run_p45_html_report(final_run_id=final_run_id))


@app.command("p45-llm-research-writer")
def p45_llm_research_writer_command(
    final_run_id: str | None = typer.Option(None, help="P4.5 final article run id"),
    research_run_id: str | None = typer.Option(None, help="P4.5 LLM research run id"),
    runtime_mode: str = typer.Option("llm", help="runtime mode: llm or mock"),
    provider_name: str | None = typer.Option(None, help="provider name override"),
    refresh_html: bool = typer.Option(True, help="append result to P4.5 HTML report"),
) -> None:
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
    console.print(result)


@app.command("p45-llm-analyst-writers")
def p45_llm_analyst_writers_command(
    pack_id: str | None = typer.Option(None, help="P4.5 evidence pack id"),
    analyst_run_id: str | None = typer.Option(None, help="P4.5 LLM analyst run id"),
    runtime_mode: str = typer.Option("llm", help="runtime mode: llm or mock"),
    provider_name: str | None = typer.Option(None, help="provider name override"),
    refresh_html: bool = typer.Option(True, help="append result to P4.5 HTML report"),
) -> None:
    result = run_p45_llm_analyst_writers(
        pack_id=pack_id,
        analyst_run_id=analyst_run_id,
        runtime_mode=runtime_mode,
        provider_name=provider_name,
    )
    if refresh_html:
        result = {
            **result,
            "html_report": run_p45_html_report(),
        }
    console.print(result)


@app.command("p4-dod-check")
def p4_dod_check_command() -> None:
    console.print(run_p4_dod_check())


@app.command("p4-radar-coverage")
def p4_radar_coverage_command(
    radar_run_id: str | None = typer.Option(None, help="P2 Radar run id"),
    p3_run_id: str | None = typer.Option(None, help="P3 run id"),
    pack_id: str | None = typer.Option(None, help="P4 evidence pack id"),
) -> None:
    console.print(
        run_p4_radar_coverage_audit(
            radar_run_id=radar_run_id,
            p3_run_id=p3_run_id,
            pack_id=pack_id,
        )
    )


@app.command("p4-build-evidence-pack")
def p4_build_evidence_pack_command(
    radar_run_id: str | None = typer.Option(None, help="P2 Radar run id"),
    p3_run_id: str | None = typer.Option(None, help="P3 run id"),
    pack_id: str | None = typer.Option(None, help="P4 evidence pack id"),
    history_limit: int = typer.Option(3, help="previous votes per analyst"),
) -> None:
    console.print(
        build_p4_evidence_pack(
            radar_run_id=radar_run_id,
            p3_run_id=p3_run_id,
            pack_id=pack_id,
            history_limit=history_limit,
        )
    )


@app.command("p4-run-analysts")
def p4_run_analysts_command(
    pack_id: str | None = typer.Option(None, help="P4 evidence pack id"),
    debate_id: str | None = typer.Option(None, help="LLM debate id"),
    runtime_mode: str = typer.Option("mock", help="runtime mode: mock"),
) -> None:
    console.print(
        run_analyst_agents(
            pack_id=pack_id,
            debate_id=debate_id,
            runtime_mode=runtime_mode,  # type: ignore[arg-type]
        )
    )


@app.command("p4-rule-baseline")
def p4_rule_baseline_command(
    pack_id: str | None = typer.Option(None, help="P4 evidence pack id"),
) -> None:
    console.print(build_rule_baseline(pack_id=pack_id))


@app.command("p4-state-machine")
def p4_state_machine_command(
    pack_id: str | None = typer.Option(None, help="P4 evidence pack id"),
) -> None:
    console.print(run_state_machine(pack_id=pack_id))


@app.command("p4-cross-exam")
def p4_cross_exam_command(
    debate_id: str = typer.Option(..., help="LLM debate id"),
    pack_id: str | None = typer.Option(None, help="P4 evidence pack id"),
) -> None:
    console.print(run_cross_examination(debate_id=debate_id, pack_id=pack_id))


@app.command("p4-cross-exam-revisions")
def p4_cross_exam_revisions_command(
    debate_id: str = typer.Option(..., help="LLM debate id"),
) -> None:
    console.print(run_cross_exam_revisions(debate_id=debate_id))


@app.command("p4-judge-synthesis")
def p4_judge_synthesis_command(
    debate_id: str = typer.Option(..., help="LLM debate id"),
    pack_id: str | None = typer.Option(None, help="P4 evidence pack id"),
) -> None:
    console.print(run_judge_synthesis(debate_id=debate_id, pack_id=pack_id))


@app.command("p4-adversarial-review")
def p4_adversarial_review_command(
    debate_id: str = typer.Option(..., help="LLM debate id"),
    judge_synthesis_id: str | None = typer.Option(None, help="P4 judge synthesis id"),
) -> None:
    console.print(
        run_adversarial_review(
            debate_id=debate_id,
            judge_synthesis_id=judge_synthesis_id,
        )
    )


@app.command("p4-final-controller")
def p4_final_controller_command(
    debate_id: str = typer.Option(..., help="LLM debate id"),
    judge_synthesis_id: str | None = typer.Option(None, help="P4 judge synthesis id"),
) -> None:
    console.print(
        build_final_controller_json(
            debate_id=debate_id,
            judge_synthesis_id=judge_synthesis_id,
        )
    )


@app.command("run-once")
def run_once() -> None:
    run = asyncio.run(run_once_mock(delay_seconds=0))
    console.print(run.model_dump(mode="json"))


@app.command()
def serve(
    host: str | None = typer.Option(None, help="API host"),
    port: int | None = typer.Option(None, help="API port"),
) -> None:
    settings = get_settings()
    uvicorn.run(
        "onlybtc.api.app:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    app()
