from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlybtc.governance.source_health import build_source_health_monitor_report

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p7-c04-source-health-monitor-report.json"
REPORT_MD = ROOT / "reports" / "p7-c04-source-health-monitor-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate() -> dict[str, Any]:
    report = build_source_health_monitor_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def _render_markdown(report: dict[str, Any]) -> str:
    quality = report["latest_data_quality"]
    policy = report["downstream_policy"]
    lines = [
        "# P7-C04 Source Health Monitor Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- alert_count: `{report['alert_count']}`",
        f"- data_quality_run_id: `{quality.get('run_id')}`",
        f"- data_quality_score: `{quality.get('score')}`",
        f"- data_quality_status: `{quality.get('status')}`",
        "",
        "## Downstream Policy",
        "",
        f"- dashboard_badge: `{policy['dashboard_badge']}`",
        f"- participation_policy: `{policy['participation_policy']}`",
        f"- publish_gate_recommendation: `{policy['publish_gate_recommendation']}`",
        "",
        "## Guardrails",
        "",
        *[f"- {item}" for item in report["guardrails"]],
        "",
        "## Alerts",
        "",
    ]
    alerts = report.get("alerts") or []
    if alerts:
        lines.extend(["| level | scope | alert_id | reason | action |", "|---|---|---|---|---|"])
        for alert in alerts:
            lines.append(
                "| {level} | {scope} | {alert_id} | {reason} | {action} |".format(
                    level=alert["level"],
                    scope=alert["scope"],
                    alert_id=alert["alert_id"],
                    reason=alert["reason"],
                    action=alert["recommended_action"],
                )
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Data Quality Summary",
            "",
            f"- source_count: `{quality.get('source_count')}`",
            f"- freshness_counts: `{json.dumps(quality.get('freshness_counts'), ensure_ascii=False)}`",
            f"- business_recency_counts: `{json.dumps(quality.get('business_recency_counts'), ensure_ascii=False)}`",
            f"- stale_sources: `{json.dumps(_source_ids(quality.get('stale_sources')), ensure_ascii=False)}`",
            f"- business_lagging_sources: `{json.dumps(_source_ids(quality.get('business_lagging_sources')), ensure_ascii=False)}`",
            f"- missing_sources: `{json.dumps(_source_ids(quality.get('missing_sources')), ensure_ascii=False)}`",
            f"- fallback_summary: `{json.dumps(_compact_fallback_summary(quality.get('fallback_summary')), ensure_ascii=False)}`",
            f"- run_mode_summary: `{json.dumps(_compact_run_mode_summary(quality.get('run_mode_summary')), ensure_ascii=False)}`",
            "",
            "## Recent Source Events",
            "",
        ]
    )
    events = report.get("recent_source_events") or []
    if events:
        lines.extend(["| source | status | quality | latency_ms | message |", "|---|---|---:|---:|---|"])
        for event in events[:30]:
            lines.append(
                "| {source} | {status} | {quality} | {latency} | {message} |".format(
                    source=event["source_id"],
                    status=event["status"],
                    quality=event["quality_score"],
                    latency=event.get("latency_ms"),
                    message=str(event.get("message") or "-").replace("|", "/"),
                )
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This report is monitoring-only.",
            "- It does not collect sources or modify source registry state.",
            "- It does not emit trading advice or bypass state machine gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def _compact_fallback_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    return {
        "fallback_event_count": summary.get("fallback_event_count", 0),
        "warning_source_count": summary.get("warning_source_count", 0),
        "http_403_sources": summary.get("http_403_sources") or [],
        "warning_sources": summary.get("warning_sources") or [],
    }


def _source_ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [
        str(item.get("source_id"))
        for item in items
        if isinstance(item, dict) and item.get("source_id")
    ][:30]


def _compact_run_mode_summary(summary: Any) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    mixed = summary.get("mixed_metric_ids") or []
    return {
        "live_metric_values": summary.get("live_metric_values", 0),
        "mock_metric_values": summary.get("mock_metric_values", 0),
        "test_metric_values": summary.get("test_metric_values", 0),
        "unknown_metric_values": summary.get("unknown_metric_values", 0),
        "mixed_metric_count": len(mixed),
        "mixed_metric_examples": mixed[:10],
        "production_blocker": bool(summary.get("production_blocker")),
    }


if __name__ == "__main__":
    main()
