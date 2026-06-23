from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from onlybtc.governance.p7_production_gate import build_p7_production_gate_report

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_p7_c01_module_weight_calibration import generate as generate_c01
from scripts.generate_p7_c02_state_alert_threshold_calibration import generate as generate_c02
from scripts.generate_p7_c03_prompt_version_report import generate as generate_c03
from scripts.generate_p7_c04_source_health_monitor_report import generate as generate_c04
from scripts.generate_p7_c05_playwright_stability_report import generate as generate_c05
from scripts.generate_p7_c06_cost_control_report import generate as generate_c06
from scripts.generate_p7_c07_provider_permission_report import generate as generate_c07

REPORT_JSON = ROOT / "reports" / "p7-c08-production-gate-report.json"
REPORT_MD = ROOT / "reports" / "p7-c08-production-gate-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate(
    *,
    report_json: Path = REPORT_JSON,
    report_md: Path = REPORT_MD,
    child_reports: dict[str, dict[str, Any]] | None = None,
    refresh_children: bool = True,
) -> dict[str, Any]:
    if refresh_children and child_reports is None:
        _refresh_child_reports()
    report = build_p7_production_gate_report(
        report_dir=report_json.parent,
        child_reports=child_reports,
    )
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(report_json), "md_path": str(report_md)}


def _refresh_child_reports() -> None:
    for generator in (
        generate_c01,
        generate_c02,
        generate_c03,
        generate_c04,
        generate_c05,
        generate_c06,
        generate_c07,
    ):
        generator()


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# P7-C08 Production Gate Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- production_apply_allowed: `{report['production_apply_allowed']}`",
        f"- manual_gate_release_allowed: `{report['manual_gate_release_allowed']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- alert_count: `{report['alert_count']}`",
        f"- accepted_warning_count: `{report['accepted_warning_count']}`",
        f"- blocking_warning_count: `{report['blocking_warning_count']}`",
        "",
        "## Guardrails",
        "",
        *[f"- {item}" for item in report["guardrails"]],
        "",
        "## Child Reports",
        "",
        "| task | capability | present | status | applied | source_alerts | missing_fields |",
        "|---|---|---:|---|---:|---:|---|",
    ]
    for child in report["child_reports"]:
        lines.append(
            "| {task} | {capability} | {present} | {status} | {applied} | {alerts} | {missing} |".format(
                task=child["task_id"],
                capability=child["capability"],
                present=child["present"],
                status=child["status"],
                applied=child["applied_to_production"],
                alerts=child.get("source_alert_count", len(child.get("alerts") or [])),
                missing=",".join(child.get("missing_fields") or []) or "-",
            )
        )
    lines.extend(["", "## Alerts", ""])
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
    manual = report.get("manual_acceptance") or {}
    lines.extend(["", "## Manual Acceptance", ""])
    lines.extend(
        [
            f"- release_policy: `{manual.get('release_policy')}`",
            f"- accepted_warning_count: `{manual.get('accepted_warning_count', 0)}`",
            f"- blocking_warning_count: `{manual.get('blocking_warning_count', 0)}`",
            "",
        ]
    )
    items = manual.get("items") or []
    if items:
        lines.extend(
            [
                "| task | classification | alert_id | reason | release_condition |",
                "|---|---|---|---|---|",
            ]
        )
        for item in items:
            lines.append(
                "| {task} | {classification} | {alert_id} | {reason} | {condition} |".format(
                    task=item.get("task_id"),
                    classification=item.get("classification"),
                    alert_id=item.get("alert_id"),
                    reason=str(item.get("reason")).replace("|", "/"),
                    condition=str(item.get("release_condition")).replace("|", "/"),
                )
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Production Mock Scenarios",
            "",
            "| scenario | task | status | mock_signal | expected_behavior |",
            "|---|---|---|---|---|",
        ]
    )
    for scenario in report["production_mock_scenarios"]:
        lines.append(
            "| {scenario} | {task} | {status} | {signal} | {behavior} |".format(
                scenario=scenario["scenario_id"],
                task=scenario["task_id"],
                status=scenario["status"],
                signal=scenario["mock_signal"],
                behavior=scenario["expected_behavior"],
            )
        )
    lines.extend(["", "## DoD Checks", ""])
    lines.extend(["| check | status |", "|---|---|"])
    for check in report["dod_checks"]:
        lines.append(f"| {check['check_id']} | {check['status']} |")
    lines.extend(
        [
            "",
            "## Rollout Checklist",
            "",
            *[f"- {item}" for item in report["rollout_checklist"]],
            "",
            "## Rollback Checklist",
            "",
            *[f"- {item}" for item in report["rollback_checklist"]],
            "",
            "## Notes",
            "",
            "- This report is a production gate only.",
            "- It does not apply any calibration recommendation.",
            "- `production_apply_allowed=false` means real long-running production should stay blocked until failed checks are repaired.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
