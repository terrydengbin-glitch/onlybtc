from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlybtc.calibration.thresholds import build_state_alert_threshold_recommendation

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_JSON = ROOT / "reports" / "btc-4h-1d-direct-trend-evaluation-report.json"
REPORT_JSON = ROOT / "reports" / "p7-c02-state-alert-threshold-calibration-report.json"
REPORT_MD = ROOT / "reports" / "p7-c02-state-alert-threshold-calibration-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate(evaluation_path: Path = EVALUATION_JSON) -> dict[str, Any]:
    evaluation = _load_json(evaluation_path)
    report = build_state_alert_threshold_recommendation(evaluation)
    report["input_path"] = str(evaluation_path)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _render_markdown(report: dict[str, Any]) -> str:
    evaluation = report["input_evaluation"]
    lines = [
        "# P7-C02 State & Alert Threshold Calibration Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- input_path: `{report.get('input_path')}`",
        f"- evaluation_status: `{evaluation['overall_status']}`",
        f"- sample_count: `{evaluation['sample_count']}`",
        "",
        "## Guardrails",
        "",
        *[f"- {item}" for item in report["guardrails"]],
        "",
        "## Adjustments",
        "",
    ]
    adjustments = report.get("adjustments") or []
    if adjustments:
        lines.extend(["| scope | key | base | recommended | delta | reason |", "|---|---|---:|---:|---:|---|"])
        for item in adjustments:
            lines.append(
                "| {scope} | {key} | {base} | {recommended} | {delta} | {reason} |".format(
                    scope=item["scope"],
                    key=item["key"],
                    base=_display(item.get("base")),
                    recommended=_display(item.get("recommended")),
                    delta=_display(item.get("delta")),
                    reason=item["reason"],
                )
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Calibration Buckets",
            "",
            "| bucket | count | success_rate | expected |",
            "|---|---:|---:|---:|",
        ]
    )
    for bucket in evaluation.get("calibration_buckets") or []:
        lines.append(
            "| {bucket} | {count} | {success_rate} | {expected} |".format(
                bucket=bucket["bucket"],
                count=bucket["count"],
                success_rate=_display(bucket.get("success_rate")),
                expected=_display(bucket.get("expected")),
            )
        )
    lines.extend(["", "## Evidence Gaps", ""])
    gaps = report.get("evidence_gaps") or []
    if gaps:
        lines.extend(f"- {item['scope']}: {item['reason']}" for item in gaps)
    else:
        lines.append("- none")
    lines.extend(["", "## Thresholds", ""])
    for scope in ("p4_state_machine", "p4_alerts", "direct_trend"):
        lines.extend(
            [
                f"### {scope}",
                "",
                "| key | base | recommended |",
                "|---|---:|---:|",
            ]
        )
        base_values = report["base_thresholds"][scope]
        recommended_values = report["recommended_thresholds"][scope]
        for key in sorted(base_values):
            lines.append(f"| {key} | {_display(base_values[key])} | {_display(recommended_values[key])} |")
        lines.append("")
    caps = report["recommended_thresholds"].get("direct_trend_confidence_caps") or {}
    lines.extend(["## Confidence Caps", ""])
    if caps:
        lines.extend(["| bucket | cap |", "|---|---:|"])
        lines.extend(f"| {bucket} | {_display(cap)} |" for bucket, cap in sorted(caps.items()))
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Rollback",
            "",
            "- type: `restore_base_thresholds`",
            "- source: production constants remain unchanged by this report.",
            "",
            "## Notes",
            "",
            "- This report is recommendation-only.",
            "- It keeps warning sensitivity unless P7-C08 validates a production change.",
            "- It does not emit trading advice or bypass state machine gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def _display(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


if __name__ == "__main__":
    main()
