from __future__ import annotations

import html
import json
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from onlybtc.db.repositories import EventWatchtowerRepository
from onlybtc.db.session import database
from onlybtc.event_window import event_watchtower_daemon

from generate_event_window_market_shock_regression_audit import (
    generate as generate_market_shock_regression,
)
from generate_event_window_shock_fast_lane_audit_html import generate as generate_shock_audit
from generate_event_window_source_audit_html import generate as generate_source_audit
from generate_event_window_state_overlay_llm_audit_html import generate as generate_state_audit


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_HTML = ROOT / "reports" / "event-window-audit-bundle-summary.html"
SUMMARY_JSON = ROOT / "reports" / "event-window-audit-bundle-summary.json"


def main() -> None:
    result = run_bundle()
    print(result["summary_html"])
    print(result["summary_json"])
    if result["overall_status"] != "PASS":
        raise SystemExit(1)


def run_bundle() -> dict[str, Any]:
    previous_scheduler_enabled = getattr(event_watchtower_daemon, "_scheduler_enabled", True)
    event_watchtower_daemon._scheduler_enabled = False
    try:
        payload = event_watchtower_daemon.collect_once(
            manual_full_sweep=True,
            trigger="audit_bundle_full_sweep",
        )
        reports = [
            generate_source_audit(deepcopy(payload)),
            generate_state_audit(deepcopy(payload)),
            generate_shock_audit(deepcopy(payload)),
        ]
        regression_report = generate_market_shock_regression()
        expected_snapshot = str(payload.get("snapshot_id") or "")
        expected_asof = str(payload.get("asof_ts") or "")
        summary = _build_summary(
            reports=reports,
            regression_report=regression_report,
            expected_snapshot=expected_snapshot,
            expected_asof=expected_asof,
        )
        return _write_summary(summary)
    finally:
        event_watchtower_daemon._scheduler_enabled = previous_scheduler_enabled


def evaluate_latest_bundle() -> dict[str, Any]:
    if not SUMMARY_JSON.exists():
        return _write_summary(
            {
                "schema_version": "p7.event_window.audit_bundle.v1",
                "generated_at": datetime.now(UTC).isoformat(),
                "overall_status": "FAIL",
                "freshness_verdict": "MISSING",
                "failure_reason": "audit bundle summary json not found",
                "summary_html": str(SUMMARY_HTML),
                "summary_json": str(SUMMARY_JSON),
            }
        )
    existing = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
    summary = _build_summary(
        reports=list(existing.get("reports") or []),
        regression_report=existing.get("regression_report") or {},
        expected_snapshot=str(existing.get("snapshot_id") or ""),
        expected_asof=str(existing.get("asof_ts") or ""),
        generated_at=str(existing.get("generated_at") or datetime.now(UTC).isoformat()),
        checked_at=datetime.now(UTC).isoformat(),
    )
    return _write_summary(summary)


def _build_summary(
    *,
    reports: list[dict[str, Any]],
    regression_report: dict[str, Any],
    expected_snapshot: str,
    expected_asof: str,
    generated_at: str | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    snapshot_ids = {str(item.get("snapshot_id") or "") for item in reports}
    asof_values = {str(item.get("asof_ts") or "") for item in reports}
    sqlite_latest = _sqlite_latest_snapshot_meta()
    snapshot_consistent = snapshot_ids == {expected_snapshot}
    asof_consistent = asof_values == {expected_asof}
    freshness_verdict = _freshness_verdict(
        expected_snapshot=expected_snapshot,
        expected_asof=expected_asof,
        sqlite_latest=sqlite_latest,
        snapshot_consistent=snapshot_consistent,
        asof_consistent=asof_consistent,
    )
    regression_pass = regression_report.get("overall_status") in {None, "PASS"}
    overall_status = "PASS" if freshness_verdict == "PASS" and regression_pass else freshness_verdict
    if overall_status not in {"PASS", "STALE"}:
        overall_status = "FAIL"
    return {
        "schema_version": "p7.event_window.audit_bundle.v1",
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "checked_at": checked_at,
        "overall_status": overall_status,
        "freshness_verdict": freshness_verdict,
        "snapshot_id": expected_snapshot,
        "asof_ts": expected_asof,
        "sqlite_latest_snapshot_id": sqlite_latest.get("snapshot_id"),
        "sqlite_latest_asof_ts": sqlite_latest.get("asof_ts"),
        "reports": reports,
        "report_file_meta": [_report_file_meta(item) for item in reports],
        "regression_report": regression_report,
        "snapshot_id_consistent": snapshot_consistent,
        "asof_ts_consistent": asof_consistent,
        "sqlite_latest_consistent": (
            sqlite_latest.get("snapshot_id") == expected_snapshot
            and sqlite_latest.get("asof_ts") == expected_asof
        ),
        "summary_html": str(SUMMARY_HTML),
        "summary_json": str(SUMMARY_JSON),
    }


def _write_summary(summary: dict[str, Any]) -> dict[str, Any]:
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_HTML.write_text(_render_summary(summary), encoding="utf-8")
    return summary


def _sqlite_latest_snapshot_meta() -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        latest = EventWatchtowerRepository(session).latest_snapshot() or {}
    return {"snapshot_id": latest.get("snapshot_id"), "asof_ts": latest.get("asof_ts")}


def _report_file_meta(item: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(item.get("html_path") or item.get("path") or ""))
    if not path.exists():
        return {
            "report": item.get("report"),
            "path": str(path),
            "exists": False,
            "last_write_time": None,
            "size_bytes": 0,
        }
    stat = path.stat()
    return {
        "report": item.get("report"),
        "path": str(path),
        "exists": True,
        "last_write_time": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "size_bytes": stat.st_size,
    }


def _freshness_verdict(
    *,
    expected_snapshot: str,
    expected_asof: str,
    sqlite_latest: dict[str, Any],
    snapshot_consistent: bool,
    asof_consistent: bool,
) -> str:
    if not expected_snapshot or not expected_asof:
        return "FAIL"
    if not snapshot_consistent or not asof_consistent:
        return "FAIL"
    if sqlite_latest.get("snapshot_id") != expected_snapshot or sqlite_latest.get("asof_ts") != expected_asof:
        return "STALE"
    return "PASS"


def _render_summary(summary: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><td>{_e(item.get('report'))}</td><td>{_e(item.get('snapshot_id'))}</td>"
        f"<td>{_e(item.get('asof_ts'))}</td><td>{_e(item.get('html_path') or item.get('path'))}</td>"
        f"<td>{_e(item.get('overall_status', 'n/a'))}</td></tr>"
        for item in summary.get("reports", [])
    )
    file_rows = "\n".join(
        f"<tr><td>{_e(item.get('report'))}</td><td>{_e(item.get('exists'))}</td>"
        f"<td>{_e(item.get('last_write_time'))}</td><td>{_e(item.get('size_bytes'))}</td>"
        f"<td>{_e(item.get('path'))}</td></tr>"
        for item in summary.get("report_file_meta", [])
    )
    regression = summary.get("regression_report") or {}
    status = str(summary.get("overall_status") or "")
    tone = "ok" if status == "PASS" else ("warn" if status == "STALE" else "bad")
    regression_tone = "ok" if regression.get("overall_status") == "PASS" else "bad"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Event Window Audit Bundle Summary</title>
  <style>
    body {{ margin:0; background:#07131c; color:#dbeafe; font-family:Inter, Arial, "Microsoft YaHei", sans-serif; }}
    main {{ max-width:1200px; margin:0 auto; padding:28px; }}
    .hero {{ border:1px solid #24455c; background:#0d2030; border-radius:12px; padding:18px; }}
    .pill {{ display:inline-flex; border:1px solid #24455c; border-radius:999px; padding:5px 10px; color:#bae6fd; margin-right:8px; }}
    .ok {{ color:#22d3b6; border-color:#22d3b6; }}
    .warn {{ color:#fbbf24; border-color:#fbbf24; }}
    .bad {{ color:#fb7185; border-color:#fb7185; }}
    table {{ width:100%; margin-top:18px; border-collapse:collapse; background:#0d2030; }}
    th, td {{ border:1px solid #24455c; padding:9px; text-align:left; vertical-align:top; }}
    th {{ color:#bae6fd; }}
    code {{ color:#fef3c7; }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <span class="pill {tone}">{_e(summary.get("overall_status"))}</span>
    <span class="pill {tone}">freshness {_e(summary.get("freshness_verdict"))}</span>
    <h1>Event Window HTML 1/2/3 同源 Snapshot 审计</h1>
    <p>HTML snapshot <code>{_e(summary.get("snapshot_id"))}</code> · asof <code>{_e(summary.get("asof_ts"))}</code></p>
    <p>SQLite latest <code>{_e(summary.get("sqlite_latest_snapshot_id"))}</code> · asof <code>{_e(summary.get("sqlite_latest_asof_ts"))}</code></p>
    <p>结论：HTML 1/2/3 必须来自同一次 manual full sweep，并且必须与 SQLite latest snapshot 一致；否则本页标记 STALE 或 FAIL。</p>
  </section>
  <table>
    <thead><tr><th>report</th><th>snapshot_id</th><th>asof_ts</th><th>path</th><th>status</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <table>
    <thead><tr><th>report</th><th>exists</th><th>last_write_time</th><th>size_bytes</th><th>path</th></tr></thead>
    <tbody>{file_rows}</tbody>
  </table>
  <section class="hero" style="margin-top:18px">
    <span class="pill {regression_tone}">{_e(regression.get('overall_status'))}</span>
    <h2>Market Shock 漏报回归摘要</h2>
    <p>HTML <code>{_e(regression.get('html_path'))}</code></p>
    <p>JSON <code>{_e(regression.get('json_path'))}</code></p>
  </section>
</main>
</body>
</html>"""


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


if __name__ == "__main__":
    main()
