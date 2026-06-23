from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from onlybtc.core.paths import paths
from onlybtc.db.repositories import RadarRuntimeRepository
from onlybtc.db.session import Database, database


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def generate_radar_runtime_audit_report(
    *,
    db: Database = database,
    refresh_mode: str = "manual",
    output_dir: Path | None = None,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        repo = RadarRuntimeRepository(session)
        runtime = repo.latest_runtime_snapshot() or {}
        modules = runtime.get("modules") if isinstance(runtime.get("modules"), list) else []
        if not modules:
            modules = repo.latest_module_snapshots()
        scheduler = repo.scheduler_state()
    health = runtime.get("health") or {}
    expected = int(health.get("expected_module_count") or 14)
    module_count = len(modules)
    pass_runtime = bool(runtime.get("schema_version") == "p45.radar_runtime.v1")
    pass_modules = module_count >= min(expected, 14)
    pass_scheduler = len(scheduler) >= min(expected, 14)
    pass_health = health.get("health_state") == "healthy" and health.get("source_fresh") is not False
    overall = "PASS" if pass_runtime and pass_modules and pass_scheduler and pass_health else "PARTIAL"
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    runtime_asof = _parse_dt(runtime.get("asof_ts"))
    snapshot_age_sec = int((now_dt - runtime_asof).total_seconds()) if runtime_asof else None
    runtime_snapshot_id = runtime.get("runtime_snapshot_id")
    report = {
        "generated_at": now,
        "html_refresh_mode": refresh_mode,
        "overall_status": overall,
        "checks": {
            "runtime_snapshot": pass_runtime,
            "module_snapshots": pass_modules,
            "scheduler_state": pass_scheduler,
            "runtime_health": pass_health,
        },
        "runtime_snapshot_id": runtime_snapshot_id,
        "runtime_asof_ts": runtime.get("asof_ts"),
        "snapshot_age_sec": snapshot_age_sec,
        "daemon_health_state": health.get("health_state"),
        "health": health,
        "module_count": module_count,
        "fresh_module_count": int(health.get("fresh_module_count") or 0),
        "stale_module_count": int(health.get("stale_module_count") or 0),
        "runtime_fresh": bool(health.get("runtime_fresh")),
        "source_fresh": bool(health.get("source_fresh")),
        "source_freshness_state": health.get("source_freshness_state"),
        "scheduler_count": len(scheduler),
    }
    report_dir = output_dir or paths.project_root / "reports"
    html_path = report_dir / "radar-runtime-audit-report.html"
    md_path = report_dir / "radar-runtime-audit-report.md"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        f"<tr><td>{_esc(item.get('module_name'))}</td><td>{_esc(item.get('cadence_group'))}</td>"
        f"<td>{_esc(item.get('freshness_state'))}</td><td>{_esc(item.get('participation_policy'))}</td>"
        f"<td>{_esc((item.get('source_freshness') or {}).get('state'))}</td>"
        f"<td>{_esc((item.get('source_freshness') or {}).get('expired_feature_count'))}</td>"
        f"<td>{_esc((item.get('source_freshness') or {}).get('stale_feature_count'))}</td>"
        f"<td>{_esc(item.get('module_direction'))}</td><td>{_esc(item.get('module_score'))}</td>"
        f"<td>{_esc(item.get('signal_stage'))}</td><td>{_esc(item.get('score_source'))}</td>"
        f"<td>{_esc(item.get('age_sec'))}</td></tr>"
        for item in sorted(modules, key=lambda row: str(row.get("module_name")))
    )
    runtime_cockpit = runtime.get("btc_runtime_cockpit") or {}
    source_refresh_gate = runtime.get("last_source_refresh_gate") or {}
    contribution_rows = "\n".join(
        f"<tr><td>{_esc(item.get('module_name'))}</td><td>{_esc(item.get('layer'))}</td>"
        f"<td>{_esc(item.get('effective_direction'))}</td><td>{_esc(item.get('signal_stage'))}</td>"
        f"<td>{_esc(item.get('module_score'))}</td><td>{_esc(item.get('accepted_status'))}</td>"
        f"<td>{_esc(item.get('contribution'))}</td></tr>"
        for item in runtime_cockpit.get("module_contributions") or []
    )
    metadata = {
        "generated_at": now,
        "html_refresh_mode": refresh_mode,
        "runtime_snapshot_id": runtime_snapshot_id,
        "runtime_asof_ts": runtime.get("asof_ts"),
        "snapshot_age_sec": snapshot_age_sec,
        "daemon_health_state": health.get("health_state"),
        "module_count": module_count,
        "fresh_module_count": report["fresh_module_count"],
        "stale_module_count": report["stale_module_count"],
        "runtime_fresh": report["runtime_fresh"],
        "source_fresh": report["source_fresh"],
        "source_freshness_state": report["source_freshness_state"],
    }
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Radar Runtime Audit</title>
  <style>
    body {{ margin:0; background:#06131d; color:#d8f3ff; font-family:Inter,Arial,sans-serif; }}
    main {{ padding:24px; }}
    .card {{ border:1px solid #1d4254; border-radius:10px; background:#0b2130; padding:16px; margin-bottom:16px; }}
    .pass {{ color:#24e0c4; }} .partial {{ color:#ffc928; }} .fail {{ color:#ff6b75; }}
    .meta-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }}
    .meta-item {{ border:1px solid #173244; border-radius:8px; padding:10px; background:#071a27; }}
    .meta-label {{ color:#7fa9bd; font-size:12px; text-transform:uppercase; }}
    .meta-value {{ font-weight:700; margin-top:4px; overflow-wrap:anywhere; }}
    table {{ border-collapse:collapse; width:100%; }}
    th,td {{ border-bottom:1px solid #173244; padding:8px; text-align:left; }}
    pre {{ white-space:pre-wrap; color:#a9c7d8; }}
  </style>
</head>
<body>
<main>
  <h1>Radar Runtime Audit</h1>
  <section class="card">
    <h2 class="{overall.lower()}">{overall}</h2>
    <div class="meta-grid">
      <div class="meta-item"><div class="meta-label">generated_at</div><div class="meta-value">{_esc(now)}</div></div>
      <div class="meta-item"><div class="meta-label">html_refresh_mode</div><div class="meta-value">{_esc(refresh_mode)}</div></div>
      <div class="meta-item"><div class="meta-label">runtime_snapshot_id</div><div class="meta-value">{_esc(runtime_snapshot_id)}</div></div>
      <div class="meta-item"><div class="meta-label">runtime_asof_ts</div><div class="meta-value">{_esc(runtime.get('asof_ts'))}</div></div>
      <div class="meta-item"><div class="meta-label">snapshot_age_sec</div><div class="meta-value">{_esc(snapshot_age_sec)}</div></div>
      <div class="meta-item"><div class="meta-label">daemon_health_state</div><div class="meta-value">{_esc(health.get('health_state'))}</div></div>
      <div class="meta-item"><div class="meta-label">runtime_fresh</div><div class="meta-value">{_esc(health.get('runtime_fresh'))}</div></div>
      <div class="meta-item"><div class="meta-label">source_fresh</div><div class="meta-value">{_esc(health.get('source_fresh'))}</div></div>
      <div class="meta-item"><div class="meta-label">source_freshness_state</div><div class="meta-value">{_esc(health.get('source_freshness_state'))}</div></div>
    </div>
    <p>Modules {module_count}/{expected} · scheduler {len(scheduler)}/{expected}</p>
  </section>
  <section class="card"><h2>Audit Metadata</h2><pre>{_esc(json.dumps(metadata, ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Health</h2><pre>{_esc(json.dumps(health, ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Source Refresh Gate Summary</h2><pre>{_esc(json.dumps(source_refresh_gate, ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Runtime Cockpit</h2><pre>{_esc(json.dumps(runtime_cockpit, ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Module Freshness & Score Source</h2>
    <table><thead><tr><th>module</th><th>group</th><th>runtime freshness</th><th>policy</th><th>source freshness</th><th>expired features</th><th>stale features</th><th>direction</th><th>score</th><th>stage</th><th>score source</th><th>age</th></tr></thead><tbody>{rows}</tbody></table>
  </section>
  <section class="card"><h2>Source Group Mapping</h2><pre>{_esc(json.dumps({str(item.get('module_name')): {'source_group_id': item.get('source_group_id'), 'source_refresh_status': item.get('source_refresh_status')} for item in modules}, ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Source Freshness Samples</h2><pre>{_esc(json.dumps({str(item.get('module_name')): (item.get('source_freshness') or {}).get('sample') for item in modules}, ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Context-only Stale Samples</h2><pre>{_esc(json.dumps({str(item.get('module_name')): (item.get('source_freshness') or {}).get('context_only_stale_sample') for item in modules}, ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Runtime Contribution Bridge</h2>
    <table><thead><tr><th>module</th><th>layer</th><th>direction</th><th>stage</th><th>score</th><th>acceptance</th><th>contribution</th></tr></thead><tbody>{contribution_rows}</tbody></table>
  </section>
</main>
</body>
</html>"""
    html_path.write_text(html_doc, encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Radar Runtime Audit",
                f"- status: {overall}",
                f"- generated_at: {now}",
                f"- html_refresh_mode: {refresh_mode}",
                f"- runtime_snapshot_id: {runtime_snapshot_id}",
                f"- runtime_asof_ts: {runtime.get('asof_ts')}",
                f"- snapshot_age_sec: {snapshot_age_sec}",
                f"- modules: {module_count}/{expected}",
                f"- scheduler: {len(scheduler)}/{expected}",
                f"- runtime_fresh: {health.get('runtime_fresh')}",
                f"- source_fresh: {health.get('source_fresh')}",
                f"- source_freshness_state: {health.get('source_freshness_state')}",
            ]
        ),
        encoding="utf-8",
    )
    return {**report, "html_path": str(html_path), "md_path": str(md_path)}
