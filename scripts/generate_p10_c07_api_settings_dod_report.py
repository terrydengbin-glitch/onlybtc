from __future__ import annotations

import asyncio
import html
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "p10-c07-api-settings-dod-report.json"
REPORT_MD = ROOT / "reports" / "p10-c07-api-settings-dod-report.md"
REPORT_HTML = ROOT / "reports" / "p10-c07-api-settings-dod-report.html"
API_BASE = "http://127.0.0.1:8118"
FRONTEND_BASE = "http://127.0.0.1:5188"


def _bootstrap_imports() -> None:
    import sys

    backend_src = ROOT / "backend" / "src"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))


async def _provider_probe_checks(settings_cls, provider_health_module) -> dict[str, Any]:
    class SuccessClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            return httpx.Response(200, json={"data": []})

    class FailureClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            raise httpx.HTTPError("api_key=mock-deepseek-secret")

    original = provider_health_module.httpx.AsyncClient
    try:
        provider_health_module.httpx.AsyncClient = SuccessClient
        success = await provider_health_module.test_provider_health(
            "deepseek",
            settings_cls(_env_file=None, deepseek_api_key="mock-deepseek-secret"),
        )
        provider_health_module.httpx.AsyncClient = FailureClient
        failure = await provider_health_module.test_provider_health(
            "deepseek",
            settings_cls(_env_file=None, deepseek_api_key="mock-deepseek-secret"),
        )
    finally:
        provider_health_module.httpx.AsyncClient = original
    return {
        "success_status": success.get("status"),
        "failure_status": failure.get("status"),
        "redaction_passed": "mock-deepseek-secret" not in f"{success}{failure}",
    }


def _http_json(path: str) -> dict[str, Any]:
    try:
        with urlopen(f"{API_BASE}{path}", timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"reachable": False, "error": str(exc)}
    return {"reachable": True, "payload": payload}


def _http_status(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=8) as response:
            return {"reachable": True, "status": int(response.status)}
    except (OSError, URLError, TimeoutError) as exc:
        return {"reachable": False, "error": str(exc)}


def build_report() -> dict[str, Any]:
    _bootstrap_imports()
    from onlybtc.core.config import Settings
    from onlybtc.core.env_writer import write_env_updates
    from onlybtc.core.llm_routing import llm_routing_payload
    from onlybtc.core.provider_registry import provider_registry_payload
    from onlybtc.core.settings_audit import (
        record_settings_audit_event,
        settings_audit_summary,
    )
    import onlybtc.core.provider_health as provider_health

    with tempfile.TemporaryDirectory(prefix="onlybtc-p10-c07-") as tmp:
        project_root = Path(tmp)
        env_path = project_root / ".env"
        env_path.write_text("# P10-C07 mock env\nONLYBTC_UNKNOWN_FLAG=keep\n", encoding="utf-8")
        write_result = write_env_updates(
            {
                "ONLYBTC_FRED_API_KEY": "mock-fred-secret",
                "ONLYBTC_DEEPSEEK_API_KEY": "mock-deepseek-secret",
            },
            project_root=project_root,
        )
        settings = Settings(_env_file=env_path)
        provider_payload = provider_registry_payload(settings)
        routing_payload = llm_routing_payload(settings)
        audit_event = record_settings_audit_event(
            action="env_update",
            env_keys=write_result["updated_keys"],
            backup_path=str(write_result["backup_path"]),
            operation_counts=write_result["operation_counts"],
            project_root=project_root,
        )
        audit_payload = settings_audit_summary(project_root=project_root)
        provider_probe = asyncio.run(_provider_probe_checks(Settings, provider_health))
        unknown_env_preserved = "ONLYBTC_UNKNOWN_FLAG=keep" in env_path.read_text(
            encoding="utf-8"
        )

    providers = {item["provider_id"]: item for item in provider_payload["providers"]}
    frontend_app = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8")
    frontend_api = (ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")
    checks = {
        "mock_fred_key_masked": providers["fred"]["configured"]
        and providers["fred"]["masked_value"] == "moc***ret",
        "mock_llm_key_in_registry": providers["deepseek"]["configured"],
        "mock_llm_key_in_routing": "deepseek" in routing_payload["available_providers"],
        "provider_success_failure_covered": provider_probe["success_status"] == "healthy"
        and provider_probe["failure_status"] == "failed",
        "provider_probe_redacted": provider_probe["redaction_passed"],
        "audit_event_recorded": audit_payload["event_count"] == 1 and audit_event["redacted"],
        "unknown_env_preserved": unknown_env_preserved,
        "frontend_settings_mock_wired": all(
            token in frontend_app or token in frontend_api
            for token in (
                "updateSettingsEnv",
                "testProviderHealth",
                "getSettingsAudit",
                "Recent Key Audit",
                "Provider Readiness",
            )
        ),
    }
    endpoint_checks = {
        "/api/settings": _http_json("/api/settings"),
        "/api/settings/audit": _http_json("/api/settings/audit?limit=5"),
        "/api/settings/llm-routing": _http_json("/api/settings/llm-routing"),
        "/api/settings/providers/health": _http_json("/api/settings/providers/health"),
        "frontend": _http_status(FRONTEND_BASE),
    }
    runtime_checks = {
        "settings_schema": (
            endpoint_checks["/api/settings"].get("payload", {}).get("schema_version")
            if endpoint_checks["/api/settings"].get("reachable")
            else None
        ),
        "audit_schema": (
            endpoint_checks["/api/settings/audit"].get("payload", {}).get("schema_version")
            if endpoint_checks["/api/settings/audit"].get("reachable")
            else None
        ),
        "llm_routing_schema": (
            endpoint_checks["/api/settings/llm-routing"].get("payload", {}).get("schema_version")
            if endpoint_checks["/api/settings/llm-routing"].get("reachable")
            else None
        ),
        "provider_health_schema": (
            endpoint_checks["/api/settings/providers/health"]
            .get("payload", {})
            .get("schema_version")
            if endpoint_checks["/api/settings/providers/health"].get("reachable")
            else None
        ),
        "frontend_reachable": endpoint_checks["frontend"].get("reachable") is True,
    }
    passed = all(checks.values()) and all(
        item.get("reachable") is True for item in endpoint_checks.values()
    )
    return {
        "schema_version": "p10.c07.api_settings_dod_report.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed" if passed else "failed",
        "checks": checks,
        "provider_probe": provider_probe,
        "runtime_checks": runtime_checks,
        "endpoint_checks": endpoint_checks,
        "mock_contract": {
            "provider_registry_schema": provider_payload["schema_version"],
            "llm_routing_schema": routing_payload["schema_version"],
            "settings_audit_schema": audit_payload["schema_version"],
            "write_operation_counts": write_result["operation_counts"],
            "audit_action_counts": audit_payload["action_counts"],
        },
        "guardrails": [
            "mock_env_only",
            "no_plaintext_secret_values",
            "provider_success_and_failure_paths_covered",
            "frontend_settings_controls_wired",
            "p10_blocks_real_paid_provider_usage_until_dod_passes",
        ],
    }


def write_reports(report: dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [
        "# P10-C07 API Settings DoD Report",
        "",
        f"- status: {report['status']}",
        f"- generated_at: {report['generated_at']}",
        f"- schema_version: {report['schema_version']}",
        "",
        "## Checks",
    ]
    for key, value in report["checks"].items():
        rows.append(f"- {'PASS' if value else 'FAIL'} {key}")
    rows.extend(["", "## Runtime Checks"])
    for key, value in report["runtime_checks"].items():
        rows.append(f"- {key}: {value}")
    rows.extend(["", "## Guardrails"])
    for item in report["guardrails"]:
        rows.append(f"- {item}")
    REPORT_MD.write_text("\n".join(rows) + "\n", encoding="utf-8")
    html_body = "<html><body><h1>P10-C07 API Settings DoD Report</h1>"
    html_body += f"<p>Status: <strong>{html.escape(str(report['status']))}</strong></p>"
    html_body += "<h2>Checks</h2><ul>"
    for key, value in report["checks"].items():
        html_body += f"<li>{'PASS' if value else 'FAIL'} {html.escape(key)}</li>"
    html_body += "</ul><h2>Runtime</h2><pre>"
    html_body += html.escape(json.dumps(report["runtime_checks"], ensure_ascii=False, indent=2))
    html_body += "</pre></body></html>"
    REPORT_HTML.write_text(html_body, encoding="utf-8")


def main() -> int:
    report = build_report()
    write_reports(report)
    print(json.dumps({"status": report["status"], "json": str(REPORT_JSON)}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
