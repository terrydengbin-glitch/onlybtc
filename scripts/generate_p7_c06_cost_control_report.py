from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlybtc.governance.cost_controls import build_cost_control_report

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p7-c06-cost-control-cache-rate-limit-report.json"
REPORT_MD = ROOT / "reports" / "p7-c06-cost-control-cache-rate-limit-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate() -> dict[str, Any]:
    report = build_cost_control_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def _render_markdown(report: dict[str, Any]) -> str:
    config = report["config"]
    lines = [
        "# P7-C06 Cost Control / Cache / Rate Limit Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- alert_count: `{report['alert_count']}`",
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
                    reason=str(alert["reason"]).replace("|", "/"),
                    action=alert["recommended_action"],
                )
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Config Summary",
            "",
            f"- source_collection: `{json.dumps(config['source_collection'], ensure_ascii=False)}`",
            f"- fred_throttle: `{json.dumps(config['fred_throttle'], ensure_ascii=False)}`",
            f"- p4_llm_budget: `{json.dumps(config['p4_llm_budget'], ensure_ascii=False)}`",
            f"- p45_research_budget: `{json.dumps(config['p45_research_budget'], ensure_ascii=False)}`",
            "",
            "## Cache",
            "",
            f"- path: `{report['cache']['path']}`",
            f"- exists: `{report['cache']['exists']}`",
            f"- file_count: `{report['cache']['file_count']}`",
            f"- total_bytes: `{report['cache']['total_bytes']}`",
            "",
            "## Rate Limit Events",
            "",
        ]
    )
    events = report.get("recent_rate_limit_events") or []
    if events:
        lines.extend(["| source | current | limit | utilization | reset_at |", "|---|---:|---:|---:|---|"])
        for event in events[:30]:
            lines.append(
                f"| {event['source_id']} | {event['current']} | {event['limit']} | {event['utilization']} | {event['reset_at']} |"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Fallback Summary",
            "",
            f"- fallback_event_count: `{report['fallback_summary']['fallback_event_count']}`",
            "",
            "## Notes",
            "",
            "- This report is audit-only and does not modify runtime settings.",
            "- P4 has explicit call and token budget guards.",
            "- P4.5 research timeout/retry exists, but explicit call/token budget is reported as a governance gap until configured.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
