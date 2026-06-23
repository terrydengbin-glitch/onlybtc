from __future__ import annotations

import html
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.db import schema
from onlybtc.db.session import database
from onlybtc.event_window import event_watchtower_daemon

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "event-window-source-audit-report.html"


def main() -> None:
    result = generate()
    print(result["path"])


def generate(
    payload: dict[str, Any] | None = None,
    *,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    payload = payload or event_watchtower_daemon.collect_once()
    db_counts = _db_counts()
    report_path.write_text(_render(payload, db_counts), encoding="utf-8")
    return {
        "path": str(report_path),
        "snapshot_id": payload.get("snapshot_id"),
        "asof_ts": payload.get("asof_ts"),
        "report": "source_audit",
    }


def _db_counts() -> dict[str, int]:
    database.init_schema()
    tables = {
        "event_watchtower_snapshots": schema.EventWatchtowerSnapshot,
        "event_calendar_items": schema.EventCalendarItem,
        "event_expectation_snapshots": schema.EventExpectationSnapshot,
        "event_official_text_items": schema.EventOfficialTextItem,
        "event_llm_analyses": schema.EventLlmAnalysis,
        "event_shock_lane_items": schema.EventShockLaneItem,
        "event_post_reaction_snapshots": schema.EventPostReactionSnapshot,
        "event_alerts": schema.EventAlert,
        "event_source_fetches": schema.EventSourceFetch,
    }
    with database.session() as session:
        return {
            name: int(session.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in tables.items()
        }


def _render(payload: dict[str, Any], db_counts: dict[str, int]) -> str:
    state = payload.get("state") or {}
    active = payload.get("active_event") or {}
    dq = payload.get("data_quality") or {}
    source_quality = dq.get("source_quality") or {}
    functional_live = bool(source_quality.get("functional_live", dq.get("functional_live")))
    blocked = bool(source_quality.get("blocked", dq.get("blocked")))
    confidence_note = source_quality.get("confidence_note") or dq.get("confidence_note") or ""
    provider_confidence = dq.get("provider_confidence") or {}
    expectation = payload.get("expectation_monitor") or {}
    secondary = expectation.get("secondary_calendar_mesh") or {}
    prediction = expectation.get("prediction_market_odds") or {}
    fetches = payload.get("source_fetches") or []
    calendar = payload.get("calendar_items") or []
    source_lineage = payload.get("source_lineage") or []
    generated = datetime.now(UTC).isoformat()
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Event Window Source Audit</title>
  <style>
    :root {{
      --bg: #07131c;
      --panel: #0d2030;
      --panel2: #10293a;
      --line: #24455c;
      --text: #dbeafe;
      --muted: #8fb3c7;
      --cyan: #22d3ee;
      --green: #22d3b6;
      --yellow: #fbbf24;
      --red: #fb7185;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px),
        var(--bg);
      background-size: 32px 32px;
      color: var(--text);
      font-family: Inter, Arial, "Microsoft YaHei", sans-serif;
    }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 28px; }}
    h1, h2, h3 {{ margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ margin-top: 26px; color: #f8fafc; font-size: 20px; }}
    p {{ color: var(--muted); line-height: 1.55; }}
    code {{ color: #fef3c7; }}
    .hero {{
      border: 1px solid rgba(34, 211, 238, .24);
      background: linear-gradient(135deg, rgba(13,32,48,.94), rgba(9,22,32,.88));
      border-radius: 12px;
      padding: 22px;
      box-shadow: 0 16px 60px rgba(0,0,0,.28);
    }}
    .hero-row {{ display: flex; justify-content: space-between; gap: 20px; align-items: start; }}
    .pill {{
      display: inline-flex;
      border: 1px solid rgba(143,179,199,.24);
      border-radius: 999px;
      padding: 5px 10px;
      color: #bae6fd;
      background: rgba(8,24,36,.74);
      font-size: 12px;
      margin: 4px 4px 0 0;
    }}
    .pill.ok {{ color: var(--green); border-color: rgba(34,211,182,.35); }}
    .pill.warn {{ color: var(--yellow); border-color: rgba(251,191,36,.4); }}
    .pill.bad {{ color: var(--red); border-color: rgba(251,113,133,.42); }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .grid.three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .card {{
      border: 1px solid rgba(143,179,199,.18);
      background: rgba(13,32,48,.82);
      border-radius: 10px;
      padding: 14px;
      min-width: 0;
    }}
    .card small {{ color: var(--muted); display: block; }}
    .value {{ font-size: 24px; color: var(--cyan); font-weight: 800; margin-top: 4px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 13px;
      background: rgba(8,24,36,.62);
      border: 1px solid rgba(143,179,199,.14);
      border-radius: 10px;
      overflow: hidden;
    }}
    th, td {{
      border-bottom: 1px solid rgba(143,179,199,.14);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: #bae6fd; background: rgba(11,26,38,.94); }}
    tr:last-child td {{ border-bottom: 0; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; }}
    .status-success, .status-fallback_used {{ color: var(--green); }}
    .status-partial {{ color: var(--yellow); }}
    .status-failed {{ color: var(--red); }}
    .note {{
      border-left: 3px solid var(--yellow);
      background: rgba(251,191,36,.08);
      padding: 12px 14px;
      border-radius: 8px;
      margin-top: 14px;
    }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <div class="hero-row">
      <div>
        <span class="pill">Event Window v3.2</span>
        <span class="pill">Source Audit</span>
        <h1>预警 / 事件窗口 · 数据源审计</h1>
        <p>
          Generated: <code>{_e(generated)}</code> · Snapshot:
          <code>{_e(payload.get("snapshot_id"))}</code> · Schema:
          <code>{_e(payload.get("schema_version"))}</code>
        </p>
      </div>
      <div>
        <span class="pill {_tone_class(state.get("emergency_level"))}">
          emergency {_e(state.get("emergency_level", "none"))}
        </span>
        <span class="pill">state {_e(state.get("event_window_state", "-"))}</span>
      </div>
    </div>
    <div class="grid" style="margin-top:16px">
      {_metric("Active event", f'{active.get("event_type", "-")} / {active.get("title", "-")}')}
      {_metric("Source mode", source_quality.get("overall_source_mode", dq.get("overall_source_mode", "-")))}
      {_metric("Functional live", functional_live)}
      {_metric("Blocked", blocked)}
      {_metric("Calendar confidence", provider_confidence.get("calendar_confidence", "-"))}
      {_metric("Consensus confidence", provider_confidence.get("consensus_confidence", "-"))}
      {_metric("Nowcast confidence", provider_confidence.get("nowcast_confidence", "-"))}
      {_metric("Prediction confidence", provider_confidence.get("prediction_market_confidence", "-"))}
      {_metric("Fetch attempts", len(fetches))}
      {_metric("Calendar items", len(calendar))}
    </div>
    <div class="note">
      <strong>partial_live = functional live:</strong>
      partial/live source gaps are capability-scoped. They do not stop the daemon,
      Shock Fast Lane, emergency overlay, or floating alert unless
      <code>blocked=true</code>. {_e(confidence_note)}
    </div>
  </section>

  <h2>SQLite 历史落盘确认</h2>
  <p>
    结论：这些信息已经存在 SQLite，用于历史回顾和 replay。完整 payload 存在
    <code>event_watchtower_snapshots.payload_json</code>；单次抓取 lineage 存在
    <code>event_source_fetches.payload_json</code>；日历、预期、Fed 文本、LLM 分析、
    shock、post-event reaction、alert 都有独立表。
  </p>
  <div class="grid three">
    {"".join(_metric(name, count) for name, count in db_counts.items())}
  </div>

  <h2>Provider Confidence</h2>
  <table>
    <thead><tr><th>field</th><th>value</th></tr></thead>
    <tbody>
      {_kv_rows(provider_confidence)}
    </tbody>
  </table>

  <h2>Source Quality</h2>
  <table>
    <thead><tr><th>field</th><th>value</th></tr></thead>
    <tbody>
      {_kv_rows(source_quality)}
    </tbody>
  </table>

  <h2>Expectation / Secondary / Prediction</h2>
  <div class="grid three">
    {_metric("Nowcast", expectation.get("nowcast", "-"))}
    {_metric("Consensus status", expectation.get("consensus_status", "-"))}
    {_metric("Secondary calendar", secondary.get("secondary_calendar_status", "-"))}
    {_metric("Secondary consensus", secondary.get("consensus_status", "-"))}
    {_metric("Actual fast", secondary.get("actual_fast_status", "-"))}
    {_metric("Disabled providers", len(secondary.get("disabled_providers") or []))}
    {_metric("Prediction status", prediction.get("status", "-"))}
    {_metric("Prediction markets", prediction.get("market_count", "-"))}
  </div>
  <div class="note">
    非官方源只能触发 watch / high alert / proxy 风险，不会伪装成官方 actual、official consensus
    或 CME FedWatch probability。
  </div>

  <h2>Secondary Provider Replacement Mesh</h2>
  <table>
    <thead>
      <tr>
        <th>provider</th><th>tier</th><th>status</th><th>replacement</th>
        <th>replacement_for</th><th>disabled_reason</th><th>fallback</th>
        <th>throttle</th><th>cache</th><th>next_allowed</th><th>values</th>
      </tr>
    </thead>
    <tbody>
      {_secondary_provider_rows(secondary.get("providers") or [])}
    </tbody>
  </table>

  <h2>Source Fetch Lineage</h2>
  <table>
    <thead>
      <tr>
        <th>source_id</th><th>tier</th><th>status</th><th>http</th>
        <th>parsed</th><th>fallback</th><th>throttle</th><th>cache</th>
        <th>next_allowed</th><th>blocked</th><th>source_group</th><th>skip_reason</th>
        <th>error / endpoint</th>
      </tr>
    </thead>
    <tbody>
      {_fetch_rows(fetches)}
    </tbody>
  </table>

  <h2>Upcoming Calendar Items</h2>
  <table>
    <thead><tr><th>event</th><th>title</th><th>release_time</th><th>tier</th><th>provider</th></tr></thead>
    <tbody>
      {_calendar_rows(calendar)}
    </tbody>
  </table>

  <h2>Configured Source Lineage</h2>
  <table>
    <thead><tr><th>source_id</th><th>tier</th><th>role</th><th>url</th></tr></thead>
    <tbody>
      {_lineage_rows(source_lineage)}
    </tbody>
  </table>
</main>
</body>
</html>
"""


def _metric(label: str, value: Any) -> str:
    return (
        '<div class="card">'
        f"<small>{_e(label)}</small>"
        f'<div class="value">{_e(value)}</div>'
        "</div>"
    )


def _kv_rows(payload: dict[str, Any]) -> str:
    if not payload:
        return "<tr><td>-</td><td>-</td></tr>"
    return "\n".join(
        f"<tr><td>{_e(key)}</td><td class=\"mono\">{_e(value)}</td></tr>"
        for key, value in payload.items()
    )


def _fetch_rows(fetches: list[dict[str, Any]]) -> str:
    rows = []
    for item in fetches:
        status = str(item.get("status") or "")
        error = item.get("error_message") or item.get("error_code") or item.get("endpoint_url")
        rows.append(
            "<tr>"
            f"<td class=\"mono\">{_e(item.get('source_id'))}</td>"
            f"<td>{_e(item.get('source_tier'))}</td>"
            f"<td class=\"status-{_e(status)}\">{_e(status)}</td>"
            f"<td>{_e(item.get('http_status'))}</td>"
            f"<td>{_e(item.get('parsed_item_count'))}</td>"
            f"<td>{_e(item.get('fallback_used'))}</td>"
            f"<td>{_e(item.get('throttle_status'))}</td>"
            f"<td>{_e(item.get('cache_status'))}</td>"
            f"<td class=\"mono\">{_e(item.get('next_allowed_at'))}</td>"
            f"<td>{_e(item.get('blocked_reason'))}</td>"
            f"<td>{_e(item.get('source_group'))}</td>"
            f"<td>{_e(item.get('skip_reason'))}</td>"
            f"<td class=\"mono\">{_e(error)}</td>"
            "</tr>"
        )
    return "\n".join(rows) or "<tr><td colspan=\"13\">-</td></tr>"


def _secondary_provider_rows(providers: list[dict[str, Any]]) -> str:
    rows = []
    for item in providers:
        values = item.get("values") or {}
        rows.append(
            "<tr>"
            f"<td class=\"mono\">{_e(item.get('provider'))}</td>"
            f"<td>{_e(item.get('source_tier'))}</td>"
            f"<td class=\"status-{_e(item.get('status'))}\">{_e(item.get('status'))}</td>"
            f"<td class=\"mono\">{_e(item.get('replacement'))}</td>"
            f"<td class=\"mono\">{_e(item.get('replacement_for'))}</td>"
            f"<td>{_e(item.get('disabled_reason'))}</td>"
            f"<td>{_e(item.get('fallback_used'))}</td>"
            f"<td>{_e(item.get('throttle_status'))}</td>"
            f"<td>{_e(item.get('cache_status'))}</td>"
            f"<td class=\"mono\">{_e(item.get('next_allowed_at'))}</td>"
            f"<td class=\"mono\">{_e(values)}</td>"
            "</tr>"
        )
    return "\n".join(rows) or "<tr><td colspan=\"11\">-</td></tr>"


def _calendar_rows(calendar: list[dict[str, Any]]) -> str:
    rows = []
    for item in calendar[:40]:
        rows.append(
            "<tr>"
            f"<td>{_e(item.get('event_type'))}</td>"
            f"<td>{_e(item.get('title'))}</td>"
            f"<td class=\"mono\">{_e(item.get('release_time'))}</td>"
            f"<td>{_e(item.get('source_tier'))}</td>"
            f"<td>{_e(item.get('provider') or item.get('source_name'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or "<tr><td colspan=\"5\">-</td></tr>"


def _lineage_rows(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td class=\"mono\">{_e(item.get('source_id'))}</td>"
            f"<td>{_e(item.get('source_tier'))}</td>"
            f"<td>{_e(item.get('role'))}</td>"
            f"<td class=\"mono\">{_e(item.get('url'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or "<tr><td colspan=\"4\">-</td></tr>"


def _tone_class(level: Any) -> str:
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
