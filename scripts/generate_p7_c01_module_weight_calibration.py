from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlybtc.api import p45_dashboard
from onlybtc.calibration.module_weights import (
    PROFILE_MULTIPLIERS,
    build_module_weight_recommendation,
    build_profile_weights,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p7-c01-module-weight-calibration-report.json"
REPORT_MD = ROOT / "reports" / "p7-c01-module-weight-calibration-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate(profile: str | None = None) -> dict[str, Any]:
    modules = _latest_modules()
    recommendation = build_module_weight_recommendation(modules, profile=profile)
    report = {
        **recommendation,
        "latest_module_count": len(modules),
        "available_profiles": sorted(PROFILE_MULTIPLIERS),
        "profile_matrix": {
            name: build_profile_weights(name, recommendation["base_weights"])
            for name in sorted(PROFILE_MULTIPLIERS)
        },
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def _latest_modules() -> list[dict[str, Any]]:
    try:
        dashboard = p45_dashboard.latest_dashboard()
    except Exception:
        return []
    modules = dashboard.get("modules") or dashboard.get("radar_modules") or []
    return [dict(item) for item in modules if isinstance(item, dict)]


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# P7-C01 Module Weight Calibration Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- selected_profile: `{report['selected_profile']}`",
        f"- profile_reason: `{report['profile_reason']}`",
        f"- confidence_discount: `{report['confidence_discount']}`",
        f"- latest_module_count: `{report['latest_module_count']}`",
        "",
        "## Guardrails",
        "",
        *[f"- {item}" for item in report["guardrails"]],
        "",
        "## Recommended Weights",
        "",
        "| module | base | profile | recommended | delta_vs_base |",
        "|---|---:|---:|---:|---:|",
    ]
    base = report["base_weights"]
    profile = report["profile_weights"]
    recommended = report["recommended_weights"]
    for module_id in sorted(recommended):
        delta = float(recommended[module_id]) - float(base.get(module_id, 0))
        lines.append(
            "| {module} | {base:.6f} | {profile:.6f} | {recommended:.6f} | {delta:+.6f} |".format(
                module=module_id,
                base=float(base.get(module_id, 0)),
                profile=float(profile.get(module_id, 0)),
                recommended=float(recommended[module_id]),
                delta=delta,
            )
        )
    lines.extend(
        [
            "",
            "## Quality Discounts",
            "",
        ]
    )
    discounts = report.get("quality_discounts") or []
    if discounts:
        lines.extend(
            [
                "| module | quality | multiplier | reason |",
                "|---|---:|---:|---|",
            ]
        )
        for item in discounts:
            lines.append(
                f"| {item['module_id']} | {item['quality']} | {item['applied_multiplier']} | {item['reason']} |"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Rollback",
            "",
            "- type: `restore_base_registry_weights`",
            "- source: `onlybtc.radars.registry.MODULE_WEIGHTS`",
            "",
            "## Notes",
            "",
            "- This report is recommendation-only.",
            "- It does not modify production registry weights.",
            "- It does not bypass state machine, invalidation, warning level, or data quality gates.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
