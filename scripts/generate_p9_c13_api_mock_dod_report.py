from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from onlybtc.api.app import app
from onlybtc.api.mock_fixtures import p9_c13_mock_scenarios

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p9-c13-api-mock-dod-report.json"
REPORT_MD = ROOT / "reports" / "p9-c13-api-mock-dod-report.md"
REPORT_HTML = ROOT / "reports" / "p9-c13-api-mock-dod-report.html"
OPENAPI_JSON = ROOT / "reports" / "p9-c13-openapi-snapshot.json"
DTO_JSON = ROOT / "reports" / "p9-c13-frontend-dto-snapshot.json"

REQUIRED_OPENAPI_PATHS = [
    "/api/p45/dashboard/latest",
    "/api/p45/overview/latest",
    "/api/p45/radar-modules/latest",
    "/api/p45/radar-modules/{module_id}",
    "/api/p45/evidence",
    "/api/p45/articles/latest",
    "/api/p45/llm/latest",
    "/api/p45/invalidation/latest",
    "/api/data-quality/latest",
    "/api/p45/runs/latest",
    "/api/p45/history/{final_run_id}",
    "/api/events",
    "/api/p45/run-full-with-llm",
    "/api/mock/p9-c13/scenarios",
]
REQUIRED_MOCK_SCENARIOS = {
    "normal_run",
    "contract_warning_run",
    "llm_completed_run",
    "llm_completed_with_llm_errors_run",
    "data_quality_degraded_run",
    "historical_replay_run",
    "legacy_p4_reference_run",
}


def main() -> None:
    payload = generate()
    print(payload["json_path"])
    print(payload["md_path"])
    print(payload["html_path"])


def generate() -> dict[str, Any]:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    openapi = app.openapi()
    dto_snapshot = _frontend_dto_snapshot()
    scenarios = p9_c13_mock_scenarios()
    checks = _checks(openapi, dto_snapshot, scenarios)
    report = {
        "schema_version": "p9.c13.api_mock_dod_report.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "required_openapi_paths": REQUIRED_OPENAPI_PATHS,
        "mock_scenario_ids": [item["scenario_id"] for item in scenarios],
        "frontend_dto_snapshot_path": str(DTO_JSON),
        "openapi_snapshot_path": str(OPENAPI_JSON),
        "p9_dod_checklist": _dod_checklist(checks),
        "mock_server": {
            "endpoint": "/api/mock/p9-c13/scenarios",
            "mode": "contract_fixture",
            "scenario_count": len(scenarios),
        },
    }
    OPENAPI_JSON.write_text(json.dumps(openapi, ensure_ascii=False, indent=2), encoding="utf-8")
    DTO_JSON.write_text(json.dumps(dto_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(_render_markdown(report), encoding="utf-8")
    REPORT_HTML.write_text(_render_html(report), encoding="utf-8")
    return {
        **report,
        "json_path": str(REPORT_JSON),
        "md_path": str(REPORT_MD),
        "html_path": str(REPORT_HTML),
    }


def _checks(
    openapi: dict[str, Any],
    dto_snapshot: dict[str, Any],
    scenarios: list[dict[str, Any]],
) -> dict[str, bool]:
    openapi_paths = set((openapi.get("paths") or {}).keys())
    scenario_ids = {str(item.get("scenario_id")) for item in scenarios}
    dto_endpoints = set(dto_snapshot["endpoints"])
    return {
        "required_openapi_paths_present": set(REQUIRED_OPENAPI_PATHS) <= openapi_paths,
        "frontend_p45_endpoints_present": {
            "/api/p45/dashboard/latest",
            "/api/p45/overview/latest",
            "/api/p45/evidence",
            "/api/p45/runs/latest",
            "/api/p45/run-full-with-llm",
        }
        <= dto_endpoints,
        "mock_scenarios_present": REQUIRED_MOCK_SCENARIOS <= scenario_ids,
        "mock_scenarios_use_report_v2": all(
            (item.get("payload") or {}).get("schema_version") == "p45.research_report.v2"
            for item in scenarios
        ),
        "mock_scenarios_redacted": not _contains_secret_text(scenarios),
        "error_contract_exposed": "ApiClientError" in dto_snapshot["type_names"],
        "sse_contract_exposed": "/api/events" in openapi_paths,
        "api_security_mock_route_exposed": "/api/mock/p9-c13/scenarios" in openapi_paths,
        "path_resolver_report_paths": str(REPORT_JSON).endswith("reports\\p9-c13-api-mock-dod-report.json")
        or str(REPORT_JSON).endswith("reports/p9-c13-api-mock-dod-report.json"),
    }


def _frontend_dto_snapshot() -> dict[str, Any]:
    api_ts = ROOT / "frontend" / "src" / "api.ts"
    text = api_ts.read_text(encoding="utf-8")
    endpoints = sorted(set(re.findall(r"['\"`](/api/[A-Za-z0-9_./?=&{}:-]+)", text)))
    type_names = sorted(set(re.findall(r"export (?:type|class) ([A-Za-z0-9_]+)", text)))
    return {
        "schema_version": "p9.c13.frontend_dto_snapshot.v1",
        "source_path": str(api_ts),
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
        "type_names": type_names,
    }


def _dod_checklist(checks: dict[str, bool]) -> list[dict[str, Any]]:
    mapping = {
        "required_openapi_paths_present": "All P5 page APIs are present in OpenAPI.",
        "frontend_p45_endpoints_present": "Frontend DTO layer references P45 page APIs.",
        "mock_scenarios_present": "Required API mock scenarios are available.",
        "mock_scenarios_use_report_v2": "Mock fixtures use P4.5 Report v2.",
        "mock_scenarios_redacted": "Mock fixtures do not expose plaintext secrets.",
        "error_contract_exposed": "Frontend error DTO contract is present.",
        "sse_contract_exposed": "Realtime SSE endpoint is present.",
        "api_security_mock_route_exposed": "P9-C13 API mock endpoint is present.",
        "path_resolver_report_paths": "Reports are written under the project reports directory.",
    }
    return [
        {
            "check_id": check_id,
            "status": "PASS" if passed else "FAIL",
            "description": mapping[check_id],
        }
        for check_id, passed in checks.items()
    ]


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# P9-C13 API Mock / DoD Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- overall_status: `{report['overall_status']}`",
        f"- mock_endpoint: `{report['mock_server']['endpoint']}`",
        f"- openapi_snapshot: `{report['openapi_snapshot_path']}`",
        f"- frontend_dto_snapshot: `{report['frontend_dto_snapshot_path']}`",
        "",
        "## Checks",
        "",
        "| status | check | description |",
        "|---|---|---|",
    ]
    for item in report["p9_dod_checklist"]:
        lines.append(f"| {item['status']} | {item['check_id']} | {item['description']} |")
    lines.extend(["", "## Mock Scenarios", ""])
    for scenario_id in report["mock_scenario_ids"]:
        lines.append(f"- `{scenario_id}`")
    return "\n".join(lines) + "\n"


def _render_html(report: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><td>{item['status']}</td><td>{item['check_id']}</td><td>{item['description']}</td></tr>"
        for item in report["p9_dod_checklist"]
    )
    scenarios = "".join(f"<li>{scenario_id}</li>" for scenario_id in report["mock_scenario_ids"])
    return (
        "<html><body>"
        "<h1>P9-C13 API Mock / DoD Report</h1>"
        f"<p>Status: <strong>{report['overall_status']}</strong></p>"
        f"<p>Mock endpoint: <code>{report['mock_server']['endpoint']}</code></p>"
        "<table><thead><tr><th>Status</th><th>Check</th><th>Description</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"<h2>Mock Scenarios</h2><ul>{scenarios}</ul>"
        "</body></html>"
    )


def _contains_secret_text(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False).lower()
    forbidden = ("raw-secret", "raw-token", "plain-secret", "api_key=", "authorization: bearer")
    return any(item in text for item in forbidden)


if __name__ == "__main__":
    main()
