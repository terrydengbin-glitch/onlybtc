from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlybtc.governance.playwright_stability import build_playwright_stability_report

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p7-c05-playwright-stability-report.json"
REPORT_MD = ROOT / "reports" / "p7-c05-playwright-stability-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate() -> dict[str, Any]:
    report = build_playwright_stability_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def _render_markdown(report: dict[str, Any]) -> str:
    source_count = len(report.get("playwright_sources") or [])
    providers = report.get("provider_auth") or []
    lines = [
        "# P7-C05 Playwright Stability Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- alert_count: `{report['alert_count']}`",
        f"- playwright_source_count: `{source_count}`",
        f"- provider_count: `{len(providers)}`",
        "",
        "## Artifact Policy",
        "",
        f"- playwright_artifacts_ignored: `{report['artifact_policy']['playwright_artifacts_ignored']}`",
        f"- auth_dir: `{report['artifact_policy']['auth_dir']}`",
        f"- storage_state_reported_as_path_only: `{report['artifact_policy']['storage_state_reported_as_path_only']}`",
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
    lines.extend(["", "## Provider Auth", ""])
    if providers:
        lines.extend(["| provider | configured | verified | sensitive_fields | message |", "|---|---:|---:|---:|---|"])
        for provider in providers:
            lines.append(
                "| {provider} | {configured} | {verified} | {sensitive} | {message} |".format(
                    provider=provider["provider_id"],
                    configured=provider["configured"],
                    verified=provider["verified"],
                    sensitive=provider["status_has_sensitive_fields"],
                    message=str(provider["message"]).replace("|", "/"),
                )
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Playwright Sources", ""])
    lines.extend(["| source | group | method | fallback | profile_required |", "|---|---|---|---|---:|"])
    for source in report.get("playwright_sources") or []:
        lines.append(
            "| {source} | {group} | {method} | {fallback} | {profile} |".format(
                source=source["source_id"],
                group=source["group_name"],
                method=source["method"],
                fallback=source.get("fallback_source_id") or "-",
                profile=source["requires_human_verified_profile"],
            )
        )
    lines.extend(["", "## Recent Health Events", ""])
    events = report.get("recent_playwright_health_events") or []
    if events:
        lines.extend(["| source | status | category | quality | message |", "|---|---|---|---:|---|"])
        for event in events[:30]:
            lines.append(
                "| {source} | {status} | {category} | {quality} | {message} |".format(
                    source=event["source_id"],
                    status=event["status"],
                    category=event["failure_category"],
                    quality=event["quality_score"],
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
            "- This report is audit-only and does not open Playwright.",
            "- Storage state content is never embedded in the report.",
            "- Unverified provider auth degrades to warning rather than blocking global collection.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
