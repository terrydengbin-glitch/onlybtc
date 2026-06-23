from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from onlybtc.governance.prompt_registry import build_prompt_registry_report

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p7-c03-prompt-version-management-report.json"
REPORT_MD = ROOT / "reports" / "p7-c03-prompt-version-management-report.md"


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])


def generate() -> dict[str, Any]:
    report = build_prompt_registry_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    return {**report, "json_path": str(REPORT_JSON), "md_path": str(REPORT_MD)}


def _render_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    lines = [
        "# P7-C03 Prompt Version Management Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- applied_to_production: `{report['applied_to_production']}`",
        f"- entry_count: `{report['entry_count']}`",
        f"- validation_passed: `{coverage['validation_passed']}`",
        "",
        "## Guardrails",
        "",
        *[f"- {item}" for item in report["guardrails"]],
        "",
        "## Coverage",
        "",
        f"- p45_mainline: `{len(coverage['p45_mainline_prompt_ids'])}`",
        f"- legacy_compat: `{len(coverage['legacy_compat_prompt_ids'])}`",
        "",
        "## Entries",
        "",
        "| prompt_id | version | scope | status | hash | schema |",
        "|---|---|---|---|---|---|",
    ]
    for entry in report["entries"]:
        lines.append(
            "| {prompt_id} | {version} | {scope} | {status} | `{hash}` | {schema} |".format(
                prompt_id=entry["prompt_id"],
                version=entry["prompt_version"],
                scope=entry["runtime_scope"],
                status=entry["status"],
                hash=entry["content_hash"][:16],
                schema=entry["output_schema"],
            )
        )
    lines.extend(["", "## Validation Failures", ""])
    failures = coverage.get("failures") or []
    if failures:
        lines.extend(f"- {item['prompt_id']}: {item['reason']}" for item in failures)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This registry is audit-only and does not modify live prompt text.",
            "- P4 entries are registered as legacy compatibility surfaces.",
            "- P4.5 research and analyst writer prompts are registered as current mainline surfaces.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
