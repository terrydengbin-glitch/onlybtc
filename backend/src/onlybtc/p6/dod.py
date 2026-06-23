from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p6.alert_quality import alert_quality
from onlybtc.p6.article_pipeline import (
    article_history,
    latest_manual_article,
    replay_article_snapshot,
)
from onlybtc.p6.module_effectiveness import module_effectiveness
from onlybtc.p6.outcome_tracking import outcome_tracking

P6_DOD_REPORT_SCHEMA_VERSION = "p6.dod_report.v1"
P6_DOD_REPORT_JSON = "p6-dod-report.json"
P6_DOD_REPORT_MD = "p6-dod-report.md"


def run_p6_dod_mock(
    *,
    article_snapshot_id: str | None = None,
    run_mode: str = "live",
    write_scores: bool = True,
    db: Database = database,
) -> dict[str, Any]:
    article = _resolve_article(article_snapshot_id=article_snapshot_id, db=db)
    resolved_article_id = str((article or {}).get("article_snapshot_id") or "")
    final_run_id = str((article or {}).get("final_run_id") or "")
    history = article_history(limit=20, db=db)
    replay = replay_article_snapshot(resolved_article_id, db=db) if resolved_article_id else None
    alerts = alert_quality(limit=100, db=db)
    outcomes = outcome_tracking(
        article_snapshot_id=resolved_article_id or article_snapshot_id,
        run_mode=run_mode,
        db=db,
    )
    modules = module_effectiveness(
        article_snapshot_id=resolved_article_id or article_snapshot_id,
        run_mode=run_mode,
        db=db,
    )
    checks = _checks(
        article=article,
        history=history,
        replay=replay,
        alerts=alerts,
        outcomes=outcomes,
        modules=modules,
    )
    replay_writes: list[dict[str, Any]] = []
    calibration_writes: list[dict[str, Any]] = []
    if write_scores and final_run_id:
        replay_writes = _write_replay_scores(final_run_id, outcomes, db=db)
        calibration_writes = _write_calibration_note(final_run_id, modules, checks, db=db)
    report = {
        "schema_version": P6_DOD_REPORT_SCHEMA_VERSION,
        "status": _overall_status(checks),
        "created_at": datetime.now(UTC).isoformat(),
        "article_snapshot_id": resolved_article_id or None,
        "final_run_id": final_run_id or None,
        "checks": checks,
        "artifacts": {
            "article_history": _artifact_summary(history),
            "article_replay": _artifact_summary(replay or {}),
            "alert_quality": _artifact_summary(alerts),
            "outcome_tracking": _artifact_summary(outcomes),
            "module_effectiveness": _artifact_summary(modules),
        },
        "replay_scores_written": replay_writes,
        "calibration_notes_written": calibration_writes,
        "dod_boundary": {
            "read_only_replay": True,
            "production_weight_mutation": False,
            "mutates_final_view": False,
            "trading_advice": False,
        },
    }
    report_paths = _write_reports(report)
    return {
        **report,
        "report_paths": report_paths,
    }


def latest_p6_dod_report() -> dict[str, Any] | None:
    path = paths.project_root / "reports" / P6_DOD_REPORT_JSON
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_article(
    *,
    article_snapshot_id: str | None,
    db: Database,
) -> dict[str, Any] | None:
    if article_snapshot_id:
        replay = replay_article_snapshot(article_snapshot_id, db=db)
        return dict((replay or {}).get("article") or {}) if replay else None
    latest = latest_manual_article(db=db)
    return dict((latest or {}).get("article") or {}) if latest else None


def _checks(
    *,
    article: dict[str, Any] | None,
    history: dict[str, Any],
    replay: dict[str, Any] | None,
    alerts: dict[str, Any],
    outcomes: dict[str, Any],
    modules: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _check(
            "article_snapshot_available",
            bool(article),
            "P6 article snapshot is available.",
        ),
        _check(
            "article_citations_traceable",
            bool(((article or {}).get("quality_gate") or {}).get("checks", {}).get("citations_traceable")),
            "Article citations are traceable to evidence ids.",
        ),
        _check(
            "article_history_available",
            int(history.get("count") or 0) > 0,
            "P6 article history returns snapshots.",
        ),
        _check(
            "history_replay_frozen",
            bool((replay or {}).get("history_mode", {}).get("historical_payload_frozen"))
            and (replay or {}).get("history_mode", {}).get("uses_latest_runtime_state") is False,
            "History replay is frozen and does not use latest runtime state.",
        ),
        _check(
            "alert_quality_available",
            alerts.get("status") in {"passed", "warning", "ok", "empty"},
            "Alert quality layer is queryable.",
            warning=alerts.get("status") == "empty",
        ),
        _check(
            "outcome_tracking_available",
            outcomes.get("status") in {"ok", "empty"},
            "Outcome tracking layer is queryable.",
            warning=outcomes.get("status") == "empty",
        ),
        _check(
            "module_effectiveness_available",
            modules.get("status") in {"ok", "warning", "insufficient", "empty"},
            "Module effectiveness layer is queryable.",
            warning=modules.get("status") in {"insufficient", "empty"},
        ),
        _check(
            "no_trading_advice_boundary",
            modules.get("trading_advice") is False
            and outcomes.get("tracking_policy", {}).get("trading_advice") is False,
            "P6 DoD artifacts do not provide trading advice.",
        ),
        _check(
            "no_production_weight_mutation",
            modules.get("mutates_module_weights") is False,
            "P6 scoring does not mutate module weights.",
        ),
    ]


def _check(
    check_id: str,
    passed: bool,
    description: str,
    *,
    warning: bool = False,
) -> dict[str, Any]:
    status = "passed" if passed and not warning else "warning" if passed else "failed"
    return {
        "check_id": check_id,
        "status": status,
        "passed": bool(passed),
        "description": description,
    }


def _overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status")) for item in checks}
    if "failed" in statuses:
        return "failed"
    if "warning" in statuses:
        return "warning"
    return "passed"


def _artifact_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "count": payload.get("count"),
    }


def _write_replay_scores(
    final_run_id: str,
    outcomes: dict[str, Any],
    *,
    db: Database,
) -> list[dict[str, Any]]:
    items = outcomes.get("items") or []
    if not items:
        return []
    first = items[0]
    horizons = (first or {}).get("horizons") or {}
    written: list[dict[str, Any]] = []
    db.init_schema()
    with db.session() as session:
        for horizon, payload in horizons.items():
            if not isinstance(payload, dict) or payload.get("status") != "observed":
                continue
            existing = session.scalar(
                select(schema.ReplayScore)
                .where(
                    schema.ReplayScore.snapshot_id == final_run_id,
                    schema.ReplayScore.horizon == str(horizon),
                )
                .limit(1)
            )
            score = _score_from_alignment(str(payload.get("directional_alignment") or ""))
            if existing is None:
                session.add(
                    schema.ReplayScore(
                        snapshot_id=final_run_id,
                        horizon=str(horizon),
                        result_pct=payload.get("return_pct"),
                        score=score,
                        payload={
                            **payload,
                            "source": "p6_dod_mock",
                            "production_weight_mutation": False,
                        },
                    )
                )
                action = "inserted"
            else:
                action = "existing"
            written.append(
                {
                    "snapshot_id": final_run_id,
                    "horizon": str(horizon),
                    "score": score,
                    "action": action,
                }
            )
    return written


def _write_calibration_note(
    final_run_id: str,
    modules: dict[str, Any],
    checks: list[dict[str, Any]],
    *,
    db: Database,
) -> list[dict[str, Any]]:
    note = "P6 DoD mock replay completed; keep production module weights unchanged."
    payload = {
        "source": "p6_dod_mock",
        "module_effectiveness_status": modules.get("status"),
        "failed_checks": [
            item.get("check_id")
            for item in checks
            if item.get("status") == "failed"
        ],
        "production_weight_mutation": False,
    }
    db.init_schema()
    with db.session() as session:
        existing = session.scalar(
            select(schema.CalibrationNote)
            .where(
                schema.CalibrationNote.target == final_run_id,
                schema.CalibrationNote.note == note,
            )
            .limit(1)
        )
        if existing is None:
            session.add(
                schema.CalibrationNote(
                    target=final_run_id,
                    note=note,
                    payload=payload,
                )
            )
            action = "inserted"
        else:
            action = "existing"
    return [{"target": final_run_id, "action": action, "production_weight_mutation": False}]


def _score_from_alignment(alignment: str) -> float:
    if alignment in {"aligned", "neutral_observed"}:
        return 1.0
    if alignment in {"pending", "unknown"}:
        return 0.5
    return 0.0


def _write_reports(report: dict[str, Any]) -> dict[str, str]:
    reports_dir = paths.project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / P6_DOD_REPORT_JSON
    md_path = reports_dir / P6_DOD_REPORT_MD
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "json_url": f"/reports/{P6_DOD_REPORT_JSON}",
        "markdown_url": f"/reports/{P6_DOD_REPORT_MD}",
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# P6 DoD Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- status: `{report['status']}`",
        f"- article_snapshot_id: `{report.get('article_snapshot_id')}`",
        f"- final_run_id: `{report.get('final_run_id')}`",
        "",
        "## Checks",
        "",
    ]
    for item in report.get("checks") or []:
        lines.append(f"- `{item['status']}` {item['check_id']}: {item['description']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- trading_advice: `false`",
            "- production_weight_mutation: `false`",
            "- mutates_final_view: `false`",
            "",
        ]
    )
    return "\n".join(lines)
