from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from onlybtc.api import p45_dashboard
from onlybtc.api.radar_runtime import cockpit_latest
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.direct_trend.evidence import BTC_DIRECT_TREND_EVIDENCE_MODULE_ID
from onlybtc.direct_trend.registry import direct_evidence_registry
from onlybtc.direct_trend.replay import list_timescale_judge_replays, replay_timescale_judge
from onlybtc.direct_trend.state_machine import BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID

REPORT_NAME = "btc-4h-1d-direct-trend-audit-report"
SCHEMA_VERSION = "p7.c30.btc_direct_trend_audit.v1"
TARGET_SCHEMA = "p45.btc_timescale_judge.v2.2"
TARGET_HORIZONS = ("4h", "1d")


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _status_rank(status: str) -> int:
    return {"PASS": 0, "PARTIAL": 1, "FAIL": 2}.get(status, 2)


def _merge_status(values: list[str]) -> str:
    return max(values or ["PASS"], key=_status_rank)


def _get_path(payload: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(part)
    return default if current is None else current


def _latest_module_payload(session: Any, module_id: str) -> dict[str, Any]:
    row = session.scalar(
        select(schema.ModuleJsonOutput)
        .where(schema.ModuleJsonOutput.module_id == module_id)
        .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
        .limit(1)
    )
    if row is None:
        return {}
    return {
        "run_id": row.run_id,
        "schema_version": row.schema_version,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "payload": row.payload,
    }


def _latest_feature_rows(session: Any) -> dict[str, schema.FeatureValue]:
    rows = session.scalars(
        select(schema.FeatureValue)
        .where(schema.FeatureValue.module_id == BTC_DIRECT_TREND_EVIDENCE_MODULE_ID)
        .order_by(schema.FeatureValue.created_at.desc(), schema.FeatureValue.id.desc())
    ).all()
    latest: dict[str, schema.FeatureValue] = {}
    for row in rows:
        latest.setdefault(row.feature_id, row)
    return latest


def _horizon_evidence_map(judge: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for horizon in TARGET_HORIZONS:
        direct_evidence = _get_path(judge, f"horizons.{horizon}.direct_evidence", {})
        if not isinstance(direct_evidence, dict):
            continue
        for category, metrics in direct_evidence.items():
            if not isinstance(metrics, dict):
                continue
            for metric_name, payload in metrics.items():
                feature_id = f"btc_direct_trend.{category}.{metric_name}"
                found[(horizon, feature_id)] = payload if isinstance(payload, dict) else {}
    return found


def _matrix_rows(
    *,
    session: Any,
    judge: dict[str, Any],
    api_snapshot_id: str,
    sqlite_snapshot_id: str,
    ui_contract_ok: bool,
) -> list[dict[str, Any]]:
    registry = direct_evidence_registry()
    latest_features = _latest_feature_rows(session)
    consumed = _horizon_evidence_map(judge)
    rows: list[dict[str, Any]] = []
    for feature_id, entry in registry.items():
        for horizon in entry.horizons:
            if horizon not in TARGET_HORIZONS:
                continue
            feature = latest_features.get(feature_id)
            metadata = feature.metadata_json if feature is not None else {}
            source_id = metadata.get("source_id") or (metadata.get("source_health") or {}).get("source_id")
            consumed_payload = consumed.get((horizon, feature_id))
            if feature is None:
                gap_status = "missing"
            elif feature_id not in registry:
                gap_status = "gap"
            elif consumed_payload is None:
                gap_status = "gap"
            elif metadata.get("freshness_state") not in {"fresh", "legacy_unknown"}:
                gap_status = "stale"
            elif _get_path(judge, f"horizons.{horizon}.fallback_used", False):
                gap_status = "fallback"
            else:
                gap_status = "pass"
            rows.append(
                {
                    "metric_id": feature_id,
                    "source_id": source_id or "",
                    "source_asof_ts": metadata.get("source_asof_ts") or "",
                    "derived_at": metadata.get("derived_at") or "",
                    "registry_role": entry.role,
                    "used_by_horizon": horizon,
                    "state_machine_input": consumed_payload is not None,
                    "p45_output_path": (
                        f"btc_timescale_judge.horizons.{horizon}.direct_evidence."
                        f"{feature_id.removeprefix('btc_direct_trend.')}"
                    ),
                    "sqlite_snapshot_id": sqlite_snapshot_id,
                    "api_snapshot_id": api_snapshot_id,
                    "ui_rendered_field": "horizonDirectEvidenceText / horizonEventTrustCap" if ui_contract_ok else "",
                    "freshness_state": metadata.get("freshness_state") or "",
                    "gap_status": gap_status,
                }
            )
    return rows


def _frontend_checks(project_root: Path) -> list[dict[str, Any]]:
    checks = [
        {
            "check_id": "vue-reads-v22-timescale-judge",
            "file": "frontend/src/App.vue",
            "patterns": ["btcTimescaleJudge", "directTrendApi", "normalizeTimescaleHorizon"],
        },
        {
            "check_id": "vue-renders-direct-chain",
            "file": "frontend/src/App.vue",
            "patterns": [
                "horizonDirectEvidenceText",
                "horizonRadarContext",
                "horizonBtcAcceptance",
                "horizonEventTrustCap",
                "horizonConfirmationRules",
                "horizonInvalidationRules",
            ],
        },
        {
            "check_id": "vue-renders-event-phase",
            "file": "frontend/src/App.vue",
            "patterns": ["horizonEventPhase", "pre_event", "post_event_unconfirmed", "post_event_accepted"],
        },
        {
            "check_id": "vue-shows-freshness-fallback",
            "file": "frontend/src/App.vue",
            "patterns": ["horizonFreshnessBadges", "source_fresh", "runtime_fresh", "fallback_used"],
        },
    ]
    results: list[dict[str, Any]] = []
    for check in checks:
        path = project_root / check["file"]
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [pattern for pattern in check["patterns"] if pattern not in text]
        results.append({**check, "status": "PASS" if not missing else "FAIL", "missing_patterns": missing})
    return results


def _core_checks(
    *,
    judge: dict[str, Any],
    dashboard: dict[str, Any],
    cockpit: dict[str, Any],
    replay: dict[str, Any],
    state_payload: dict[str, Any],
    matrix: list[dict[str, Any]],
    ui_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    direct_api = dashboard.get("direct_trend_api") or {}
    dashboard_snapshot = direct_api.get("snapshot_id")
    replay_snapshot = replay.get("snapshot_id")
    cockpit_snapshot = (cockpit.get("direct_trend_api") or {}).get("snapshot_id")
    p8_payload = replay.get("payload") or {}
    checks = [
        {
            "check_id": "p45-schema-v22",
            "status": "PASS" if judge.get("schema_version") == TARGET_SCHEMA else "FAIL",
            "detail": judge.get("schema_version"),
        },
        {
            "check_id": "p3-state-machine-present",
            "status": "PASS" if state_payload.get("schema_version") else "FAIL",
            "detail": state_payload.get("state_run_id"),
        },
        {
            "check_id": "4h-1d-direct-evidence-present",
            "status": "PASS"
            if all(_get_path(judge, f"horizons.{h}.direct_evidence", {}) for h in TARGET_HORIZONS)
            else "FAIL",
            "detail": {h: bool(_get_path(judge, f"horizons.{h}.direct_evidence", {})) for h in TARGET_HORIZONS},
        },
        {
            "check_id": "scores-exposed",
            "status": "PASS"
            if all(
                _get_path(judge, f"horizons.{h}.{field}") is not None
                for h in TARGET_HORIZONS
                for field in ("direction_score", "acceptance_score", "trust_score", "display_score")
            )
            else "FAIL",
            "detail": "direction / acceptance / trust / display",
        },
        {
            "check_id": "event-overlay-trust-only",
            "status": "PASS" if _event_overlay_trust_only(judge) else "FAIL",
            "detail": "event_overlay_context roles are trust/quality gates; event_trust policy is trust cap",
        },
        {
            "check_id": "radar-context-not-direct-score",
            "status": "PASS" if _radar_context_is_context(judge) else "FAIL",
            "detail": "radar_context policy confirm_conflict_degrade_only / legacy_context",
        },
        {
            "check_id": "sqlite-api-snapshot-consistency",
            "status": "PASS"
            if dashboard_snapshot == replay_snapshot == p8_payload.get("snapshot_id") == cockpit_snapshot
            else "FAIL",
            "detail": {
                "dashboard": dashboard_snapshot,
                "sqlite_replay": replay_snapshot,
                "p8_payload": p8_payload.get("snapshot_id"),
                "cockpit": cockpit_snapshot,
            },
        },
        {
            "check_id": "api-freshness-explicit",
            "status": "PASS"
            if direct_api.get("source_fresh") is not None and direct_api.get("runtime_fresh") is not None
            else "FAIL",
            "detail": {
                "source_fresh": direct_api.get("source_fresh"),
                "runtime_fresh": direct_api.get("runtime_fresh"),
                "fallback_used": direct_api.get("fallback_used"),
            },
        },
        {
            "check_id": "ui-static-contract",
            "status": _merge_status([check["status"] for check in ui_checks]),
            "detail": {check["check_id"]: check["status"] for check in ui_checks},
        },
        {
            "check_id": "lineage-matrix-no-fail-gaps",
            "status": "PASS"
            if all(row["gap_status"] in {"pass", "fallback"} for row in matrix)
            else "FAIL",
            "detail": {
                status: sum(1 for row in matrix if row["gap_status"] == status)
                for status in sorted({row["gap_status"] for row in matrix})
            },
        },
    ]
    return checks


def _event_overlay_trust_only(judge: dict[str, Any]) -> bool:
    registry = direct_evidence_registry()
    event_entries_ok = all(
        not entry.affects_direction and entry.role in {"trust_cap", "quality_gate"}
        for feature_id, entry in registry.items()
        if ".event_overlay_context." in feature_id
    )
    policies_ok = all(
        str(_get_path(judge, f"horizons.{h}.event_trust.policy", "")).startswith("trust_cap")
        or not _get_path(judge, f"horizons.{h}.event_trust", {})
        for h in TARGET_HORIZONS
    )
    return event_entries_ok and policies_ok


def _radar_context_is_context(judge: dict[str, Any]) -> bool:
    allowed = {"confirm_conflict_degrade_only", "legacy_context", ""}
    return all(str(_get_path(judge, f"horizons.{h}.radar_context.policy", "")) in allowed for h in TARGET_HORIZONS)


def _evaluation_summary(replay_count: int) -> dict[str, Any]:
    enough = replay_count >= 30
    return {
        "status": "PASS" if enough else "PARTIAL",
        "sample_count": replay_count,
        "methodology": "walk-forward/purged split required; random K-fold forbidden",
        "metrics": {
            "rank_ic": None,
            "auc_f1_trend_accepted": None,
            "precision_top_decile": None,
            "whipsaw_rate": None,
            "false_breakout_reduction": None,
            "lead_time": None,
            "confidence_calibration": None,
            "event_window_robustness": None,
        },
        "reason": (
            "insufficient historical v2.2 replay snapshots for leakage-safe evaluation"
            if not enough
            else "sufficient snapshots available for evaluation runner"
        ),
    }


def _v21_v22_comparison(judge: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    views = dashboard.get("horizon_views") or {}
    h1d = _get_path(judge, "horizons.1d", {})
    h4 = _get_path(judge, "horizons.4h", {})
    return {
        "baseline": "btc_timescale_judge.v2.1 module average / horizon_views",
        "candidate": "btc_timescale_judge.v2.2 direct evidence + radar context",
        "legacy_24h_direction": _get_path(views, "h24.direction", _get_path(views, "24h.direction")),
        "v22_4h": {
            "state": h4.get("state") if isinstance(h4, dict) else None,
            "direction_score": h4.get("direction_score") if isinstance(h4, dict) else None,
            "acceptance_score": h4.get("acceptance_score") if isinstance(h4, dict) else None,
            "trust_score": h4.get("trust_score") if isinstance(h4, dict) else None,
        },
        "v22_1d": {
            "state": h1d.get("state") if isinstance(h1d, dict) else None,
            "direction_score": h1d.get("direction_score") if isinstance(h1d, dict) else None,
            "acceptance_score": h1d.get("acceptance_score") if isinstance(h1d, dict) else None,
            "trust_score": h1d.get("trust_score") if isinstance(h1d, dict) else None,
        },
        "conclusion": (
            "v2.2 separates direct direction evidence, BTC acceptance, trust caps, "
            "and radar context; module average is retained only as context/fallback."
        ),
    }


def generate(
    *,
    db: Database = database,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    db.init_schema()
    dashboard = p45_dashboard.latest_dashboard(db=db)
    overview = p45_dashboard.latest_overview(db=db)
    cockpit = cockpit_latest()
    replay = replay_timescale_judge(latest=True, db=db) or {}
    judge = dashboard.get("btc_timescale_judge") or {}
    replays = list_timescale_judge_replays(limit=200, db=db)
    with db.session() as session:
        state = _latest_module_payload(session, BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID)
        ui_checks = _frontend_checks(paths.project_root)
        ui_ok = _merge_status([check["status"] for check in ui_checks]) == "PASS"
        matrix = _matrix_rows(
            session=session,
            judge=judge,
            api_snapshot_id=str((dashboard.get("direct_trend_api") or {}).get("snapshot_id") or ""),
            sqlite_snapshot_id=str(replay.get("snapshot_id") or ""),
            ui_contract_ok=ui_ok,
        )
    core_checks = _core_checks(
        judge=judge,
        dashboard=dashboard,
        cockpit=cockpit,
        replay=replay,
        state_payload=state.get("payload") or {},
        matrix=matrix,
        ui_checks=ui_checks,
    )
    evaluation = _evaluation_summary(len([item for item in replays if item.get("schema_version") == TARGET_SCHEMA]))
    comparison = _v21_v22_comparison(judge, dashboard)
    overall = _merge_status([check["status"] for check in core_checks] + [evaluation["status"]])
    now = datetime.now(UTC).isoformat()
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "overall_status": overall,
        "core_checks": core_checks,
        "ui_checks": ui_checks,
        "lineage_matrix": matrix,
        "evaluation": evaluation,
        "v21_v22_comparison": comparison,
        "latest": {
            "final_run_id": _get_path(dashboard, "run_lineage.final_run_id"),
            "dashboard_snapshot_id": _get_path(dashboard, "direct_trend_api.snapshot_id"),
            "sqlite_snapshot_id": replay.get("snapshot_id"),
            "cockpit_snapshot_id": _get_path(cockpit, "direct_trend_api.snapshot_id"),
            "overview_schema": (overview.get("btc_timescale_judge") or {}).get("schema_version"),
        },
    }
    report_dir = output_dir or paths.project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = report_dir / f"{REPORT_NAME}.html"
    md_path = report_dir / f"{REPORT_NAME}.md"
    json_path = report_dir / f"{REPORT_NAME}.json"
    html_path.write_text(_render_html(report), encoding="utf-8")
    md_path.write_text(_render_md(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**report, "html_path": str(html_path), "md_path": str(md_path), "json_path": str(json_path)}


def _render_html(report: dict[str, Any]) -> str:
    check_rows = "\n".join(
        f"<tr><td>{_esc(item['check_id'])}</td><td class='{_esc(str(item['status']).lower())}'>{_esc(item['status'])}</td>"
        f"<td><pre>{_esc(json.dumps(item.get('detail'), ensure_ascii=False, indent=2))}</pre></td></tr>"
        for item in report["core_checks"]
    )
    matrix_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(row['metric_id'])}</td><td>{_esc(row['source_id'])}</td>"
        f"<td>{_esc(row['used_by_horizon'])}</td><td>{_esc(row['registry_role'])}</td>"
        f"<td>{_esc(row['freshness_state'])}</td><td class='{_esc(row['gap_status'])}'>{_esc(row['gap_status'])}</td>"
        f"<td>{_esc(row['source_asof_ts'])}</td><td>{_esc(row['derived_at'])}</td>"
        f"<td>{_esc(row['p45_output_path'])}</td><td>{_esc(row['ui_rendered_field'])}</td>"
        "</tr>"
        for row in report["lineage_matrix"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>BTC 4H/1D Direct Trend Audit</title>
  <style>
    body {{ margin:0; background:#06131d; color:#d8f3ff; font-family:Inter,Arial,sans-serif; }}
    main {{ padding:24px; }}
    .card {{ border:1px solid #1d4254; border-radius:10px; background:#0b2130; padding:16px; margin-bottom:16px; }}
    .pass {{ color:#24e0c4; }} .partial,.fallback,.stale {{ color:#ffc928; }} .fail,.gap,.missing {{ color:#ff6b75; }}
    .meta-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }}
    .meta-item {{ border:1px solid #173244; border-radius:8px; padding:10px; background:#071a27; }}
    .meta-label {{ color:#7fa9bd; font-size:12px; text-transform:uppercase; }}
    .meta-value {{ font-weight:700; margin-top:4px; overflow-wrap:anywhere; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th,td {{ border-bottom:1px solid #173244; padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; color:#a9c7d8; margin:0; }}
  </style>
</head>
<body>
<main>
  <h1>BTC 4H/1D Direct Trend Full Chain Audit</h1>
  <section class="card">
    <h2 class="{_esc(str(report['overall_status']).lower())}">{_esc(report['overall_status'])}</h2>
    <div class="meta-grid">
      <div class="meta-item"><div class="meta-label">generated_at</div><div class="meta-value">{_esc(report['generated_at'])}</div></div>
      <div class="meta-item"><div class="meta-label">final_run_id</div><div class="meta-value">{_esc(report['latest'].get('final_run_id'))}</div></div>
      <div class="meta-item"><div class="meta-label">dashboard_snapshot</div><div class="meta-value">{_esc(report['latest'].get('dashboard_snapshot_id'))}</div></div>
      <div class="meta-item"><div class="meta-label">sqlite_snapshot</div><div class="meta-value">{_esc(report['latest'].get('sqlite_snapshot_id'))}</div></div>
      <div class="meta-item"><div class="meta-label">cockpit_snapshot</div><div class="meta-value">{_esc(report['latest'].get('cockpit_snapshot_id'))}</div></div>
    </div>
  </section>
  <section class="card"><h2>Core Checks</h2><table><thead><tr><th>check</th><th>status</th><th>detail</th></tr></thead><tbody>{check_rows}</tbody></table></section>
  <section class="card"><h2>Lineage Matrix</h2><table><thead><tr><th>metric_id</th><th>source_id</th><th>horizon</th><th>role</th><th>freshness</th><th>gap</th><th>source_asof</th><th>derived_at</th><th>P4.5 path</th><th>UI field</th></tr></thead><tbody>{matrix_rows}</tbody></table></section>
  <section class="card"><h2>Evaluation</h2><pre>{_esc(json.dumps(report['evaluation'], ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>v2.1 vs v2.2</h2><pre>{_esc(json.dumps(report['v21_v22_comparison'], ensure_ascii=False, indent=2))}</pre></section>
</main>
</body>
</html>"""


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# BTC 4H/1D Direct Trend Full Chain Audit",
        f"- status: {report['overall_status']}",
        f"- generated_at: {report['generated_at']}",
        f"- final_run_id: {report['latest'].get('final_run_id')}",
        f"- dashboard_snapshot_id: {report['latest'].get('dashboard_snapshot_id')}",
        f"- sqlite_snapshot_id: {report['latest'].get('sqlite_snapshot_id')}",
        f"- cockpit_snapshot_id: {report['latest'].get('cockpit_snapshot_id')}",
        "",
        "## Core Checks",
    ]
    for check in report["core_checks"]:
        lines.append(f"- {check['status']} `{check['check_id']}`: {json.dumps(check.get('detail'), ensure_ascii=False)}")
    lines.extend(
        [
            "",
            "## Evaluation",
            f"- status: {report['evaluation']['status']}",
            f"- sample_count: {report['evaluation']['sample_count']}",
            f"- reason: {report['evaluation']['reason']}",
            "",
            "## v2.1 vs v2.2",
            f"- baseline: {report['v21_v22_comparison']['baseline']}",
            f"- candidate: {report['v21_v22_comparison']['candidate']}",
            f"- conclusion: {report['v21_v22_comparison']['conclusion']}",
            "",
            "## Lineage Matrix",
            "| metric_id | source_id | horizon | role | freshness | gap_status |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in report["lineage_matrix"]:
        lines.append(
            f"| {row['metric_id']} | {row['source_id']} | {row['used_by_horizon']} | "
            f"{row['registry_role']} | {row['freshness_state']} | {row['gap_status']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
