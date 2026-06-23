from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlybtc.governance.provider_permissions import build_provider_permission_report

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p7-c07-provider-permission-source-onboarding-report.json"
REPORT_MD = ROOT / "reports" / "p7-c07-provider-permission-source-onboarding-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate() -> dict[str, Any]:
    report = build_provider_permission_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def _render_markdown(report: dict[str, Any]) -> str:
    onboarding = report["source_onboarding"]
    lines = [
        "# P7-C07 Provider Permission / Source Onboarding Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- alert_count: `{report['alert_count']}`",
        f"- source_count: `{onboarding['source_count']}`",
        f"- login_required_count: `{onboarding['login_required_count']}`",
        f"- sensitive_scan_passed: `{report['sensitive_scan']['passed']}`",
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
    lines.extend(["", "## Provider Matrix", ""])
    lines.extend(["| provider | auth_method | configured | verified | permission | allowed | exposed |", "|---|---|---:|---:|---|---|---:|"])
    for row in report["provider_matrix"]:
        allowed = row.get("allowed_metrics")
        if isinstance(allowed, list):
            allowed_text = f"{len(allowed)} metrics"
        else:
            allowed_text = str(allowed)
        lines.append(
            "| {provider} | {method} | {configured} | {verified} | {permission} | {allowed} | {exposed} |".format(
                provider=row["provider_id"],
                method=row["auth_method"],
                configured=row["configured"],
                verified=row["verified"],
                permission=row["permission_level"],
                allowed=allowed_text,
                exposed=row["secret_value_exposed"],
            )
        )
    lines.extend(
        [
            "",
            "## Onboarding Checklist",
            "",
            *[f"- {item}" for item in onboarding["new_source_checklist"]],
            "",
            "## Filesystem Safety",
            "",
            f"- env_file_ignored: `{report['filesystem_safety']['env_file_ignored']}`",
            f"- env_wildcard_ignored: `{report['filesystem_safety']['env_wildcard_ignored']}`",
            f"- playwright_artifacts_ignored: `{report['filesystem_safety']['playwright_artifacts_ignored']}`",
            "",
            "## Provider Locked Policy",
            "",
            f"- metric_status: `{report['provider_locked_policy']['metric_status']}`",
            f"- missing_reason: `{report['provider_locked_policy']['missing_reason']}`",
            f"- forbidden_behavior: `{report['provider_locked_policy']['forbidden_behavior']}`",
            "",
            "## Notes",
            "",
            "- This report is audit-only and does not read secret values.",
            "- Provider permission status is safe for Source Detail / Data Quality display.",
            "- Login/session providers must be stricter than public API providers.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
