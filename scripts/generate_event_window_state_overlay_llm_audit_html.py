from __future__ import annotations

import html
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.db import schema
from onlybtc.db.repositories import EventWatchtowerRepository
from onlybtc.db.session import database
from onlybtc.event_window import event_watchtower_daemon
from onlybtc.event_window.speech_analyzer import analyze_fed_texts, boundary_audit
from onlybtc.event_window.watchtower import _overlay_from_state, _state_from_inputs

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "reports" / "event-window-state-overlay-llm-audit-report.html"
MD_PATH = ROOT / "reports" / "p7-c16-event-window-state-overlay-llm-audit.md"

STATE_PRIORITY = {
    "data_quality_blocked": 100,
    "unscheduled_shock_confirmed": 95,
    "event_lock": 90,
    "release_surprise": 85,
    "policy_repricing_shock": 80,
    "fed_tone_shift": 75,
    "pre_event_high_alert": 70,
    "expectation_drift_watch": 55,
    "post_event_followthrough": 52,
    "post_event_absorbed": 51,
    "post_event_reaction_check": 50,
    "expectation_build": 40,
    "calendar_monitor": 20,
    "event_neutral": 0,
}

ALLOWED_OVERLAY_KEYS = {
    "trade_permission_modifier",
    "confidence_cap",
    "volatility_warning",
    "ordinary_radar_trust",
}

FORBIDDEN_SCORE_KEYS = {
    "btc_score",
    "btc_module_score",
    "module_score",
    "radar_score",
    "cockpit_score",
    "timescale_score",
    "btc_direction",
}


def main() -> None:
    result = generate()
    print(result["html_path"])
    print(result["md_path"])


def generate(
    payload: dict[str, Any] | None = None,
    *,
    html_path: Path = HTML_PATH,
    md_path: Path = MD_PATH,
) -> dict[str, Any]:
    payload = payload or event_watchtower_daemon.collect_once()
    payload = _attach_deepseek_or_degraded_analysis(payload)
    verdict = _audit_payload(payload)
    cases = _synthetic_state_cases()
    db_counts = _db_counts()
    html_path.write_text(_render_html(payload, verdict, cases, db_counts), encoding="utf-8")
    md_path.write_text(_render_md(payload, verdict, cases, db_counts), encoding="utf-8")
    return {
        "html_path": str(html_path),
        "md_path": str(md_path),
        "snapshot_id": payload.get("snapshot_id"),
        "asof_ts": payload.get("asof_ts"),
        "report": "state_overlay_llm_audit",
        "overall_status": verdict.get("overall_status"),
    }


def _attach_deepseek_or_degraded_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    texts = list(payload.get("official_text_items") or [])
    analyses = analyze_fed_texts(texts, _parse_dt(payload.get("asof_ts")), use_deepseek=True)
    if analyses:
        payload["llm_analyses"] = analyses
        payload["fed_speech_monitor"] = _speech_monitor(analyses)
        database.init_schema()
        with database.session() as session:
            EventWatchtowerRepository(session).save_snapshot(payload)
    return payload


def _audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    state = payload.get("state") or {}
    overlay = payload.get("overlay") or {}
    analyses = list(payload.get("llm_analyses") or [])
    llm_audit = boundary_audit(analyses)
    state_name = str(state.get("event_window_state") or "")
    state_priority = int(state.get("state_priority") or -1)
    expected_priority = STATE_PRIORITY.get(state_name)
    priority_pass = expected_priority is None or state_priority <= expected_priority
    if state_name in {"data_quality_blocked", "unscheduled_shock_confirmed", "event_lock"}:
        priority_pass = state_priority == expected_priority
    overlay_keys = set(overlay)
    forbidden_keys = overlay_keys & FORBIDDEN_SCORE_KEYS
    allowed_only = not forbidden_keys and overlay_keys <= ALLOWED_OVERLAY_KEYS
    direct_score_pass = payload.get("direct_score_impact") is False
    sqlite_snapshot = _sqlite_snapshot_by_id(str(payload.get("snapshot_id") or ""))
    api_sqlite_pass = bool(
        sqlite_snapshot
        and sqlite_snapshot.get("snapshot_id") == payload.get("snapshot_id")
        and (sqlite_snapshot.get("state") or {}).get("event_window_state") == state_name
    )
    failures = []
    if not priority_pass:
        failures.append("state_priority_mismatch")
    if not allowed_only:
        failures.append("overlay_forbidden_score_or_extra_key")
    if not direct_score_pass:
        failures.append("direct_score_impact_not_false")
    if not llm_audit["boundary_passed"]:
        failures.append("llm_boundary_violation")
    if not api_sqlite_pass:
        failures.append("sqlite_snapshot_id_mismatch")
    return {
        "schema_version": "p7.event_window.state_overlay_llm_audit.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "state_priority": {
            "state": state_name,
            "observed": state_priority,
            "expected_cap": expected_priority,
            "passed": priority_pass,
        },
        "overlay_boundary": {
            "keys": sorted(overlay_keys),
            "allowed_keys": sorted(ALLOWED_OVERLAY_KEYS),
            "forbidden_keys": sorted(forbidden_keys),
            "passed": allowed_only,
            "direct_score_impact_false": direct_score_pass,
        },
        "llm_boundary": llm_audit,
        "sqlite_consistency": {
            "comparison_mode": "by_snapshot_id",
            "sqlite_snapshot_id": (sqlite_snapshot or {}).get("snapshot_id"),
            "payload_snapshot_id": payload.get("snapshot_id"),
            "failure_reason": "" if api_sqlite_pass else "snapshot_id_not_found_or_state_mismatch",
            "passed": api_sqlite_pass,
        },
    }


def _synthetic_state_cases() -> list[dict[str, Any]]:
    now = datetime(2026, 5, 28, 8, 0, tzinfo=UTC)
    active_high = {
        "event_id": "case-pce-high",
        "event_type": "PCE",
        "title": "Personal Income and Outlays",
        "release_time": (now + timedelta(hours=10)).isoformat(),
        "phase": "high_alert",
    }
    active_lock = dict(active_high, phase="event_lock")
    base_quality = {
        "overall_source_mode": "live",
        "data_quality_flags": [],
    }
    cases = [
        (
            "daemon paused blocks",
            _state_from_inputs(now, active_high, [], False, "paused_by_user", base_quality),
            "data_quality_blocked",
        ),
        (
            "critical shock overrides calendar",
            _state_from_inputs(
                now,
                active_high,
                [{"emergency_level": "critical", "shock_type": "official_policy_shock"}],
                True,
                "running",
                base_quality,
            ),
            "unscheduled_shock_confirmed",
        ),
        (
            "event lock stays critical",
            _state_from_inputs(now, active_lock, [], True, "running", base_quality),
            "event_lock",
        ),
        (
            "fallback high alert capped to watch",
            _state_from_inputs(
                now,
                active_high,
                [],
                True,
                "running",
                {"overall_source_mode": "fallback", "data_quality_flags": []},
            ),
            "pre_event_high_alert",
        ),
    ]
    rows = []
    for label, state, expected in cases:
        overlay = _overlay_from_state(state)
        passed = state.get("event_window_state") == expected
        if label.startswith("fallback"):
            passed = passed and state.get("emergency_level") == "watch"
        rows.append(
            {
                "label": label,
                "expected": expected,
                "observed": state.get("event_window_state"),
                "priority": state.get("state_priority"),
                "emergency_level": state.get("emergency_level"),
                "overlay_modifier": overlay.get("trade_permission_modifier"),
                "passed": passed,
            }
        )
    return rows


def _db_counts() -> dict[str, int]:
    database.init_schema()
    tables = {
        "event_watchtower_snapshots": schema.EventWatchtowerSnapshot,
        "event_official_text_items": schema.EventOfficialTextItem,
        "event_llm_analyses": schema.EventLlmAnalysis,
        "event_source_fetches": schema.EventSourceFetch,
    }
    with database.session() as session:
        return {
            name: int(session.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in tables.items()
        }


def _latest_sqlite_snapshot() -> dict[str, Any] | None:
    database.init_schema()
    with database.session() as session:
        return EventWatchtowerRepository(session).latest_snapshot()


def _sqlite_snapshot_by_id(snapshot_id: str) -> dict[str, Any] | None:
    if not snapshot_id:
        return None
    database.init_schema()
    with database.session() as session:
        return EventWatchtowerRepository(session).snapshot_by_id(snapshot_id)


def _render_html(
    payload: dict[str, Any],
    verdict: dict[str, Any],
    cases: list[dict[str, Any]],
    db_counts: dict[str, int],
) -> str:
    state = payload.get("state") or {}
    overlay = payload.get("overlay") or {}
    speech = payload.get("fed_speech_monitor") or {}
    analyses = payload.get("llm_analyses") or []
    status_class = "ok" if verdict["overall_status"] == "PASS" else "bad"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Event Window State / Overlay / LLM Audit</title>
  <style>
    :root {{
      --bg:#07131c; --panel:#0d2030; --line:#24455c; --text:#dbeafe;
      --muted:#8fb3c7; --cyan:#22d3ee; --green:#22d3b6; --yellow:#fbbf24; --red:#fb7185;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; color:var(--text); font-family:Inter, Arial, "Microsoft YaHei", sans-serif;
      background:linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px), var(--bg);
      background-size:32px 32px;
    }}
    main {{ max-width:1440px; margin:0 auto; padding:28px; }}
    h1 {{ margin:0; font-size:30px; }}
    h2 {{ margin:26px 0 10px; font-size:20px; }}
    p {{ color:var(--muted); line-height:1.55; }}
    .hero, .card {{ border:1px solid rgba(143,179,199,.18); background:rgba(13,32,48,.86); border-radius:12px; padding:16px; }}
    .hero {{ border-color:rgba(34,211,238,.25); box-shadow:0 16px 60px rgba(0,0,0,.28); }}
    .row {{ display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .grid.three {{ grid-template-columns:repeat(3,minmax(0,1fr)); }}
    .pill {{ display:inline-flex; border:1px solid rgba(143,179,199,.24); border-radius:999px; padding:5px 10px; color:#bae6fd; background:rgba(8,24,36,.74); font-size:12px; margin:4px 4px 0 0; }}
    .pill.ok {{ color:var(--green); border-color:rgba(34,211,182,.38); }}
    .pill.warn {{ color:var(--yellow); border-color:rgba(251,191,36,.42); }}
    .pill.bad {{ color:var(--red); border-color:rgba(251,113,133,.45); }}
    small {{ color:var(--muted); display:block; }}
    .value {{ font-size:24px; color:var(--cyan); font-weight:800; margin-top:4px; word-break:break-word; }}
    table {{ width:100%; border-collapse:collapse; margin-top:12px; font-size:13px; background:rgba(8,24,36,.62); border:1px solid rgba(143,179,199,.14); border-radius:10px; overflow:hidden; }}
    th, td {{ border-bottom:1px solid rgba(143,179,199,.14); padding:9px 10px; text-align:left; vertical-align:top; }}
    th {{ color:#bae6fd; background:rgba(11,26,38,.94); }}
    tr:last-child td {{ border-bottom:0; }}
    code, .mono {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:12px; color:#fef3c7; }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <div class="row">
      <div>
        <span class="pill">Event Window v3</span>
        <span class="pill">P7-C16</span>
        <span class="pill {status_class}">{_e(verdict["overall_status"])}</span>
        <h1>Event Window 状态机 / Overlay / LLM 审计</h1>
        <p>Generated <code>{_e(verdict["generated_at"])}</code> · Snapshot <code>{_e(payload.get("snapshot_id"))}</code></p>
      </div>
      <div>
        <span class="pill {_level_class(state.get("emergency_level"))}">state {_e(state.get("event_window_state"))}</span>
        <span class="pill">overlay {_e(overlay.get("trade_permission_modifier"))}</span>
      </div>
    </div>
    <div class="grid" style="margin-top:16px">
      {_metric("State priority", verdict["state_priority"].get("observed"))}
      {_metric("Emergency", state.get("emergency_level"))}
      {_metric("Radar trust", overlay.get("ordinary_radar_trust"))}
      {_metric("Direct score impact", payload.get("direct_score_impact"))}
      {_metric("LLM provider", speech.get("llm_provider"))}
      {_metric("LLM status", speech.get("llm_status"))}
      {_metric("Tone", speech.get("tone"))}
      {_metric("Tone confidence", speech.get("tone_confidence"))}
    </div>
  </section>

  <h2>Verdict</h2>
  <div class="grid three">
    {_metric("State priority pass", verdict["state_priority"].get("passed"))}
    {_metric("Overlay boundary pass", verdict["overlay_boundary"].get("passed"))}
    {_metric("LLM boundary pass", verdict["llm_boundary"].get("boundary_passed"))}
    {_metric("SQLite consistency", verdict["sqlite_consistency"].get("passed"))}
    {_metric("DeepSeek items", verdict["llm_boundary"].get("deepseek_items"))}
    {_metric("Degraded items", verdict["llm_boundary"].get("degraded_items"))}
  </div>

  <h2>State Priority Regression Cases</h2>
  <table>
    <thead><tr><th>case</th><th>expected</th><th>observed</th><th>priority</th><th>level</th><th>overlay</th><th>pass</th></tr></thead>
    <tbody>{_case_rows(cases)}</tbody>
  </table>

  <h2>Emergency Overlay Boundary</h2>
  <table><tbody>{_kv_rows(verdict["overlay_boundary"])}</tbody></table>

  <h2>LLM / Fed Speech Analyzer Boundary</h2>
  <p>LLM 只允许输出 tone / relevance / confidence / summary；不得输出 BTC 多空分数，不得直接触发交易权限。</p>
  <table><tbody>{_kv_rows(verdict["llm_boundary"])}</tbody></table>
  <table>
    <thead><tr><th>analysis_id</th><th>provider</th><th>status</th><th>tone</th><th>confidence</th><th>relevance</th><th>boundary</th><th>summary</th></tr></thead>
    <tbody>{_analysis_rows(analyses)}</tbody>
  </table>

  <h2>API / SQLite Consistency</h2>
  <div class="grid">
    {"".join(_metric(name, count) for name, count in db_counts.items())}
  </div>
  <table><tbody>{_kv_rows(verdict["sqlite_consistency"])}</tbody></table>
</main>
</body>
</html>"""


def _render_md(
    payload: dict[str, Any],
    verdict: dict[str, Any],
    cases: list[dict[str, Any]],
    db_counts: dict[str, int],
) -> str:
    state = payload.get("state") or {}
    overlay = payload.get("overlay") or {}
    return "\n".join(
        [
            "# P7-C16 / Event Window State Overlay LLM Audit",
            "",
            f"- Status: {verdict['overall_status']}",
            f"- Snapshot: {payload.get('snapshot_id')}",
            f"- State: {state.get('event_window_state')} / {state.get('emergency_level')}",
            f"- Overlay: {overlay.get('trade_permission_modifier')} / trust {overlay.get('ordinary_radar_trust')}",
            f"- direct_score_impact: {payload.get('direct_score_impact')}",
            f"- Failures: {', '.join(verdict['failures']) or 'none'}",
            "",
            "## Checks",
            "",
            f"- State priority passed: {verdict['state_priority']['passed']}",
            f"- Overlay boundary passed: {verdict['overlay_boundary']['passed']}",
            f"- LLM boundary passed: {verdict['llm_boundary']['boundary_passed']}",
            f"- SQLite consistency passed: {verdict['sqlite_consistency']['passed']}",
            "",
            "## Regression Cases",
            "",
            *[
                f"- {case['label']}: {case['observed']} level={case['emergency_level']} pass={case['passed']}"
                for case in cases
            ],
            "",
            "## SQLite Counts",
            "",
            *[f"- {name}: {count}" for name, count in db_counts.items()],
        ]
    )


def _metric(label: str, value: Any) -> str:
    return (
        '<div class="card">'
        f"<small>{_e(label)}</small>"
        f'<div class="value">{_e(value)}</div>'
        "</div>"
    )


def _case_rows(cases: list[dict[str, Any]]) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{_e(case['label'])}</td>"
        f"<td>{_e(case['expected'])}</td>"
        f"<td>{_e(case['observed'])}</td>"
        f"<td>{_e(case['priority'])}</td>"
        f"<td>{_e(case['emergency_level'])}</td>"
        f"<td>{_e(case['overlay_modifier'])}</td>"
        f"<td>{_e(case['passed'])}</td>"
        "</tr>"
        for case in cases
    )


def _analysis_rows(items: list[dict[str, Any]]) -> str:
    return "\n".join(
        "<tr>"
        f"<td class=\"mono\">{_e(item.get('analysis_id'))}</td>"
        f"<td>{_e(item.get('llm_provider'))}</td>"
        f"<td>{_e(item.get('llm_status'))}</td>"
        f"<td>{_e(item.get('tone'))}</td>"
        f"<td>{_e(item.get('tone_confidence'))}</td>"
        f"<td>{_e(item.get('policy_relevance'))}</td>"
        f"<td>{_e(item.get('btc_direction_boundary_pass'))}</td>"
        f"<td>{_e(item.get('summary') or item.get('llm_error'))}</td>"
        "</tr>"
        for item in items
    ) or "<tr><td colspan=\"8\">-</td></tr>"


def _kv_rows(payload: dict[str, Any]) -> str:
    return "\n".join(
        f"<tr><th>{_e(key)}</th><td class=\"mono\">{_e(value)}</td></tr>"
        for key, value in payload.items()
    )


def _speech_monitor(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    latest = analyses[0] if analyses else {}
    return {
        "latest_item_ts": latest.get("analyzed_at", ""),
        "speaker": latest.get("speaker", ""),
        "speaker_weight": latest.get("speaker_weight", 0),
        "tone": latest.get("tone", "not_policy_relevant"),
        "tone_confidence": latest.get("tone_confidence", 0),
        "policy_relevance": latest.get("policy_relevance", "low"),
        "tone_shift_vs_baseline": bool(latest.get("tone_shift_vs_baseline")),
        "requires_human_review": bool(latest.get("requires_human_review")),
        "llm_provider": latest.get("llm_provider", "deterministic"),
        "llm_model": latest.get("llm_model", ""),
        "llm_status": latest.get("llm_status", "not_requested"),
        "llm_error": latest.get("llm_error", ""),
        "summary": latest.get("summary", ""),
        "btc_direction_boundary_pass": bool(latest.get("btc_direction_boundary_pass", True)),
    }


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if value:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return datetime.now(UTC)


def _level_class(level: Any) -> str:
    text = str(level or "").lower()
    if text in {"critical", "high"}:
        return "bad"
    if text in {"watch", "medium"}:
        return "warn"
    return "ok"


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else "-"))


if __name__ == "__main__":
    main()
