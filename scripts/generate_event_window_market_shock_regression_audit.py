from __future__ import annotations

import html
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
BACKEND_SRC = ROOT / "backend" / "src"
for path in (ROOT, BACKEND_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from onlybtc.event_window.connectors.shock_lane import collect_shock_fast_lane
from onlybtc.event_window.watchtower import _overlay_from_state, _state_from_inputs
from onlybtc.db.session import database
from onlybtc.db.repositories import EventWatchtowerRepository

HTML_PATH = ROOT / "reports" / "event-window-market-shock-regression-audit.html"
JSON_PATH = ROOT / "reports" / "event-window-market-shock-regression-audit.json"


def main() -> None:
    result = generate()
    print(result["html_path"])
    print(result["json_path"])
    if result["overall_status"] != "PASS":
        raise SystemExit(1)


def generate(
    *,
    html_path: Path = HTML_PATH,
    json_path: Path = JSON_PATH,
) -> dict[str, Any]:
    now = datetime(2026, 5, 28, 10, 0, tzinfo=UTC)
    cases = [_crash_case(now), _normal_noise_case(now), _rally_case(now)]
    results = [_run_case(case, now) for case in cases]
    runtime = _runtime_observation()
    failures = [item for item in results if not item["passed"]]
    if not runtime.get("latest_market_probe_id"):
        failures.append({"case_id": "latest_market_probe_missing"})
    summary = {
        "schema_version": "p7.event_window.market_shock_regression.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_status": "PASS" if not failures else "FAIL",
        "failures": [item["case_id"] for item in failures],
        "cases": results,
        "runtime_observation": runtime,
        "audit_focus": [
            "5m-only shock detector would miss sustained 1h/4h/24h drawdown.",
            "Market shock may change emergency overlay and ordinary radar trust.",
            "Market shock does not directly change BTC score.",
        ],
        "html_path": str(html_path),
        "json_path": str(json_path),
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(summary), encoding="utf-8")
    return summary


def _crash_case(now: datetime) -> dict[str, Any]:
    return {
        "case_id": "sustained_5h_crash_regression",
        "description": "Synthetic reproduction of a large multi-hour selloff with weak 5m impulse.",
        "expected_state": "sustained_drawdown_high_alert",
        "expected_overlay": "watch_only",
        "expected_detected": True,
        "previous_5m_only_would_detect": False,
        "market_probe": {
            "market_probe_id": "synthetic-market-probe-crash",
            "schema_version": "p1.event_window.market_probe.v1",
            "collected_at": now.isoformat(),
            "source": "synthetic_regression",
            "symbol": "BTCUSDT",
            "price": 100000.0,
            "returns": {
                "5m": -0.002084,
                "15m": -0.0042,
                "1h": -0.013857,
                "4h": -0.016001,
                "24h": -0.032041,
            },
            "return_zscores": {
                "5m": 0.62,
                "15m": 1.1,
                "1h": 2.35,
                "4h": 2.1,
                "24h": 1.8,
            },
            "data_quality_flags": [],
            "source_lineage": [
                {
                    "source_id": "synthetic_binance_market_probe",
                    "source_tier": "market_live",
                    "status": "ok",
                }
            ],
        },
    }


def _normal_noise_case(now: datetime) -> dict[str, Any]:
    return {
        "case_id": "normal_noise_no_alert",
        "description": "Small moves should stay quiet.",
        "expected_state": "calendar_monitor",
        "expected_overlay": "none",
        "expected_detected": False,
        "previous_5m_only_would_detect": False,
        "market_probe": {
            "market_probe_id": "synthetic-market-probe-noise",
            "collected_at": now.isoformat(),
            "source": "synthetic_regression",
            "symbol": "BTCUSDT",
            "returns": {"5m": -0.0005, "15m": 0.0007, "1h": -0.001, "4h": 0.002, "24h": -0.006},
            "return_zscores": {"5m": 0.2, "15m": 0.3, "1h": 0.4, "4h": 0.4, "24h": 0.5},
            "data_quality_flags": [],
            "source_lineage": [{"source_id": "synthetic_binance_market_probe", "source_tier": "market_live", "status": "ok"}],
        },
    }


def _rally_case(now: datetime) -> dict[str, Any]:
    return {
        "case_id": "sustained_rally_guard",
        "description": "Large upside shock should be classified as rally, not drawdown.",
        "expected_state": "sustained_rally_high_alert",
        "expected_overlay": "watch_only",
        "expected_detected": True,
        "previous_5m_only_would_detect": False,
        "market_probe": {
            "market_probe_id": "synthetic-market-probe-rally",
            "collected_at": now.isoformat(),
            "source": "synthetic_regression",
            "symbol": "BTCUSDT",
            "returns": {"5m": 0.002, "15m": 0.004, "1h": 0.012, "4h": 0.022, "24h": 0.034},
            "return_zscores": {"5m": 0.7, "15m": 1.0, "1h": 1.9, "4h": 2.4, "24h": 1.8},
            "data_quality_flags": [],
            "source_lineage": [{"source_id": "synthetic_binance_market_probe", "source_tier": "market_live", "status": "ok"}],
        },
    }


def _run_case(case: dict[str, Any], now: datetime) -> dict[str, Any]:
    shock_result = collect_shock_fast_lane(now, official_text_items=[], market_probe=case["market_probe"])
    shocks = list(shock_result.get("shock_items") or [])
    active_event = {
        "event_id": "synthetic-monitor",
        "event_type": "PCE",
        "title": "Synthetic monitor event",
        "release_time": (now + timedelta(days=3)).isoformat(),
        "phase": "calendar_awareness",
    }
    quality = {"overall_source_mode": "live", "data_quality_flags": []}
    state = _state_from_inputs(now, active_event, shocks, True, "running", quality)
    overlay = _overlay_from_state(state)
    detected = bool(shocks)
    previous_would_detect = abs(float(case["market_probe"]["returns"].get("5m") or 0.0)) >= 0.03
    passed = (
        detected is bool(case["expected_detected"])
        and state.get("event_window_state") == case["expected_state"]
        and overlay.get("trade_permission_modifier") == case["expected_overlay"]
        and overlay.get("direct_score_impact") is None
        and previous_would_detect is bool(case["previous_5m_only_would_detect"])
    )
    return {
        "case_id": case["case_id"],
        "description": case["description"],
        "passed": passed,
        "expected_state": case["expected_state"],
        "actual_state": state.get("event_window_state"),
        "expected_overlay": case["expected_overlay"],
        "actual_overlay": overlay.get("trade_permission_modifier"),
        "detected": detected,
        "shock_count": len(shocks),
        "previous_5m_only_would_detect": previous_would_detect,
        "direct_score_impact": False,
        "state": state,
        "overlay": overlay,
        "shock": shocks[0] if shocks else {},
        "returns": case["market_probe"]["returns"],
    }


def _runtime_observation() -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        repo = EventWatchtowerRepository(session)
        latest = repo.latest_snapshot() or {}
        latest_probe = repo.latest_market_probe() or {}
    daemon = latest.get("daemon") or {}
    return {
        "latest_snapshot_id": latest.get("snapshot_id"),
        "latest_asof_ts": latest.get("asof_ts"),
        "daemon_status": daemon.get("status"),
        "runtime_code_version": daemon.get("runtime_code_version"),
        "last_market_probe_at": daemon.get("last_market_probe_at"),
        "latest_market_probe_id": latest_probe.get("market_probe_id"),
        "market_probe_source": latest_probe.get("source"),
        "market_probe_hash": latest_probe.get("payload_hash"),
        "market_probe_lineage": latest_probe.get("source_lineage") or [],
        "latest_shock_summary": (latest.get("shock_fast_lane") or {}).get("summary"),
        "direct_score_impact": latest.get("direct_score_impact"),
    }


def _render_html(summary: dict[str, Any]) -> str:
    rows = "\n".join(_case_card(item) for item in summary["cases"])
    tone = "ok" if summary["overall_status"] == "PASS" else "bad"
    runtime = summary.get("runtime_observation") or {}
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Event Window Market Shock Regression Audit</title>
  <style>
    body {{ margin:0; background:#07131c; color:#dbeafe; font-family:Inter, Arial, "Microsoft YaHei", sans-serif; }}
    main {{ max-width:1280px; margin:0 auto; padding:28px; }}
    .hero, .card {{ border:1px solid #24455c; background:#0d2030; border-radius:12px; padding:18px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:14px; margin-top:16px; }}
    .pill {{ display:inline-flex; border:1px solid #24455c; border-radius:999px; padding:5px 10px; color:#bae6fd; }}
    .ok {{ color:#22d3b6; border-color:#22d3b6; }}
    .bad {{ color:#fb7185; border-color:#fb7185; }}
    .warn {{ color:#fbbf24; border-color:#fbbf24; }}
    code {{ color:#fef3c7; }}
    pre {{ overflow:auto; max-height:260px; padding:12px; border-radius:8px; background:#06131d; color:#cfe4ef; }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <span class="pill {tone}">{_e(summary["overall_status"])}</span>
    <h1>Event Window 暴跌漏报回归审计</h1>
    <p>重点验证：独立 Binance Market Probe + Shock Fast Lane 多窗口判定能捕捉 1h/4h/24h 持续冲击，不再只看 5m。</p>
    <p>生成时间 <code>{_e(summary["generated_at"])}</code></p>
    <p>最新 snapshot <code>{_e(runtime.get("latest_snapshot_id"))}</code> · probe <code>{_e(runtime.get("latest_market_probe_id"))}</code> · runtime <code>{_e(runtime.get("runtime_code_version"))}</code></p>
    <p>最新冲击摘要：{_e(runtime.get("latest_shock_summary"))}</p>
  </section>
  <section class="grid">{rows}</section>
</main>
</body>
</html>"""


def _case_card(item: dict[str, Any]) -> str:
    tone = "ok" if item["passed"] else "bad"
    previous = "会漏报" if not item["previous_5m_only_would_detect"] else "会触发"
    return f"""<article class="card">
  <span class="pill {tone}">{_e('PASS' if item['passed'] else 'FAIL')}</span>
  <h2>{_e(item['case_id'])}</h2>
  <p>{_e(item['description'])}</p>
  <p>状态：<code>{_e(item['actual_state'])}</code> / overlay <code>{_e(item['actual_overlay'])}</code></p>
  <p>旧 5m-only 逻辑：<span class="pill warn">{_e(previous)}</span></p>
  <pre>{_e(json.dumps({'returns': item['returns'], 'shock': item['shock']}, ensure_ascii=False, indent=2))}</pre>
</article>"""


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


if __name__ == "__main__":
    main()
