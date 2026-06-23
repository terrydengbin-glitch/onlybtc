from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
API_BASE = "http://127.0.0.1:8118"
GITHUB_RUNS_URL = (
    "https://api.github.com/repos/terrydengbin-glitch/onlybtc/actions/runs"
    "?branch=main&per_page=1"
)


@dataclass(frozen=True)
class OutputSpec:
    task_id: str
    name: str
    markdown: str
    json_name: str
    html_name: str | None = None


OUTPUTS = {
    "P12-C02": OutputSpec(
        "P12-C02",
        "Business Chain Contract Audit",
        "p12-business-chain-contract-audit.md",
        "p12-business-chain-contract-audit.json",
    ),
    "P12-C03": OutputSpec(
        "P12-C03",
        "Dashboard / P45 UI-API Contract Audit",
        "p12-dashboard-ui-api-contract-audit.md",
        "p12-dashboard-ui-api-contract-audit.json",
    ),
    "P12-C04": OutputSpec(
        "P12-C04",
        "Radar Runtime / Module Score Full-chain Audit",
        "p12-radar-runtime-module-score-audit.md",
        "p12-radar-runtime-module-score-audit.json",
        "p12-radar-runtime-module-score-audit.html",
    ),
    "P12-C05": OutputSpec(
        "P12-C05",
        "Event Window / Event Watchtower Full-chain Audit",
        "p12-event-window-watchtower-audit.md",
        "p12-event-window-watchtower-audit.json",
        "p12-event-window-watchtower-audit.html",
    ),
    "P12-C06": OutputSpec(
        "P12-C06",
        "Data Source / Settings / Provider Governance Audit",
        "p12-data-source-settings-provider-governance-audit.md",
        "p12-data-source-settings-provider-governance-audit.json",
    ),
    "P12-C07": OutputSpec(
        "P12-C07",
        "SQLite / API / Report Lineage Release Acceptance Audit",
        "p12-system-release-acceptance-report.md",
        "p12-system-release-acceptance-report.json",
        "p12-system-release-acceptance-report.html",
    ),
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _http_json(path_or_url: str, timeout: float = 8.0) -> dict[str, Any]:
    url = path_or_url if path_or_url.startswith("http") else f"{API_BASE}{path_or_url}"
    started = datetime.now(UTC)
    request = Request(url, headers={"User-Agent": "onlybtc-p12-audit/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
            try:
                payload: Any = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                payload = {"raw": raw.decode("utf-8", errors="replace")[:500]}
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "elapsed_ms": elapsed_ms,
                "url": url,
                "payload": payload,
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        return {
            "ok": False,
            "status_code": exc.code,
            "elapsed_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
            "url": url,
            "error": body or str(exc),
        }
    except (TimeoutError, URLError, OSError) as exc:
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": int((datetime.now(UTC) - started).total_seconds() * 1000),
            "url": url,
            "error": str(exc),
        }


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            text=True,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except subprocess.CalledProcessError as exc:
        return exc.output.strip()


def _normalize_route(path: str) -> str:
    path = path.strip()
    path = path.split("${queryString", 1)[0]
    path = path.split("?", 1)[0]
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    path = re.sub(r"\{[^}/]+\}", "{param}", path)
    path = re.sub(r"/+", "/", path)
    return path.rstrip("/") or "/"


def _backend_routes() -> list[str]:
    api_dir = ROOT / "backend" / "src" / "onlybtc" / "api"
    routes: set[str] = set()
    route_pattern = re.compile(r"@(?:app|router)\.(?:get|post|put|delete|patch)\(\s*['\"]([^'\"]+)")
    prefix_pattern = re.compile(r"APIRouter\(\s*prefix=['\"]([^'\"]+)")
    for path in api_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        prefix = ""
        match = prefix_pattern.search(text)
        if match:
            prefix = match.group(1)
        for route in route_pattern.findall(text):
            full = route if route.startswith("/api/") else f"{prefix}{route}"
            routes.add(_normalize_route(full))
    return sorted(routes)


def _frontend_endpoints() -> list[str]:
    path = ROOT / "frontend" / "src" / "api.ts"
    text = path.read_text(encoding="utf-8", errors="replace")
    endpoints: set[str] = set()
    for match in re.finditer(r"(?:getJson|postJson|postJsonBody)<[^>]+>\(\s*([`'])(/api/.*?)(?:\1|`)", text, re.S):
        raw = match.group(2).replace("\n", "").replace("\r", "")
        endpoints.add(_normalize_route(raw))
    return sorted(endpoints)


def _missing_frontend_contracts(frontend: list[str], backend: list[str]) -> list[str]:
    backend_set = set(backend)
    missing = []
    for endpoint in frontend:
        if endpoint not in backend_set:
            missing.append(endpoint)
    return sorted(missing)


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    payload = result.get("payload")
    return payload if isinstance(payload, dict) else {}


def _list_from(payload: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    for value in payload.values():
        if isinstance(value, list):
            return value
    return []


def _deep_get(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_value(data: dict[str, Any], keys: list[tuple[str, ...]]) -> Any:
    for path in keys:
        value = _deep_get(data, *path)
        if value not in (None, "", [], {}):
            return value
    return None


def _endpoint_matrix(paths: list[str]) -> dict[str, dict[str, Any]]:
    return {path: _http_json(path) for path in paths}


def _issue(severity: str, area: str, finding: str, recommendation: str) -> dict[str, str]:
    return {
        "severity": severity,
        "area": area,
        "finding": finding,
        "recommendation": recommendation,
    }


def _status_from_issues(issues: list[dict[str, str]]) -> str:
    if any(item["severity"] == "blocking" for item in issues):
        return "FAIL"
    if any(item["severity"] == "warning" for item in issues):
        return "PARTIAL PASS"
    return "PASS"


def _collect_context() -> dict[str, Any]:
    p45_paths = [
        "/api/health",
        "/api/db/health",
        "/api/p45/dashboard/latest",
        "/api/p45/overview/latest",
        "/api/p45/radar-modules/latest",
        "/api/p45/evidence?limit=40",
        "/api/p45/articles/latest",
        "/api/p45/llm/latest",
        "/api/p45/analysts/latest",
        "/api/p45/invalidation/latest",
        "/api/data-quality/latest",
        "/api/p45/runs/latest",
        "/api/p45/audit-reports/latest",
    ]
    radar_paths = [
        "/api/radar-runtime/daemon/status",
        "/api/radar-runtime/daemon/health",
        "/api/radar-runtime/modules/latest",
        "/api/radar-runtime/cockpit/latest",
    ]
    event_paths = [
        "/api/event-window/latest",
        "/api/event-window/active",
        "/api/event-window/calendar?limit=30",
        "/api/event-window/timeline?limit=100",
        "/api/event-window/alerts?limit=30",
        "/api/event-window/sources/status",
        "/api/event-window/sources/fetches?limit=40",
        "/api/event-window/daemon/status",
        "/api/event-window/daemon/health",
        "/api/event-window/market-probe/latest",
        "/api/event-window/shock-lane/latest",
    ]
    settings_paths = [
        "/api/settings",
        "/api/settings/runtime",
        "/api/settings/data-sources",
        "/api/settings/paths",
        "/api/settings/providers/health",
        "/api/settings/providers/glassnode/entitlement/latest",
        "/api/settings/audit?limit=20",
    ]
    backend_routes = _backend_routes()
    frontend_endpoints = _frontend_endpoints()
    return {
        "generated_at": _now(),
        "api_base": API_BASE,
        "p45": _endpoint_matrix(p45_paths),
        "radar": _endpoint_matrix(radar_paths),
        "event": _endpoint_matrix(event_paths),
        "settings": _endpoint_matrix(settings_paths),
        "routes": {
            "backend": backend_routes,
            "frontend": frontend_endpoints,
            "frontend_without_backend": _missing_frontend_contracts(frontend_endpoints, backend_routes),
        },
        "git": {
            "status_short": _git(["status", "-sb"]),
            "head": _git(["rev-parse", "--short", "HEAD"]),
            "branch": _git(["branch", "--show-current"]),
            "remote": _git(["remote", "get-url", "origin"]),
        },
        "github_actions": _http_json(GITHUB_RUNS_URL, timeout=15.0),
    }


def _business_chain_report(ctx: dict[str, Any]) -> dict[str, Any]:
    dashboard_result = ctx["p45"]["/api/p45/dashboard/latest"]
    dashboard = _payload(dashboard_result)
    lineage = dashboard.get("run_lineage") if isinstance(dashboard.get("run_lineage"), dict) else {}
    issues: list[dict[str, str]] = []
    required = [
        "/api/health",
        "/api/p45/dashboard/latest",
        "/api/p45/radar-modules/latest",
        "/api/p45/evidence?limit=40",
        "/api/p45/audit-reports/latest",
    ]
    for path in required:
        if not ctx["p45"][path]["ok"]:
            issues.append(_issue("blocking", "api", f"{path} is not reachable", "Repair API before treating dashboard data as current."))
    matrix = [
        {
            "chain_step": "collect",
            "required_fields": ["collect_run_id", "source_id", "source_ts", "collected_at"],
            "observed": {"collect_run_id": lineage.get("collect_run_id")},
            "contract_status": "present" if lineage.get("collect_run_id") else "missing_or_pending",
        },
        {
            "chain_step": "p2_radar",
            "required_fields": ["p2_radar_run_id", "module_id", "module_score"],
            "observed": {"p2_radar_run_id": lineage.get("p2_radar_run_id")},
            "contract_status": "present" if lineage.get("p2_radar_run_id") else "missing_or_pending",
        },
        {
            "chain_step": "p3",
            "required_fields": ["p3_run_id", "accepted_status"],
            "observed": {"p3_run_id": lineage.get("p3_run_id")},
            "contract_status": "present" if lineage.get("p3_run_id") else "missing_or_pending",
        },
        {
            "chain_step": "p45_pack",
            "required_fields": ["pack_id", "evidence_id", "final_run_id"],
            "observed": {
                "pack_id": lineage.get("pack_id") or dashboard.get("pack_id"),
                "final_run_id": lineage.get("final_run_id") or dashboard.get("final_run_id"),
            },
            "contract_status": "present"
            if lineage.get("pack_id") and (lineage.get("final_run_id") or dashboard.get("final_run_id"))
            else "missing_or_pending",
        },
        {
            "chain_step": "dashboard",
            "required_fields": ["final_view", "decision_card", "run_lineage"],
            "observed": {
                "final_view": dashboard.get("final_view"),
                "decision_direction": _deep_get(dashboard, "decision_card", "direction"),
            },
            "contract_status": "present" if dashboard.get("decision_card") and dashboard.get("run_lineage") else "missing_or_pending",
        },
    ]
    if any(row["contract_status"] != "present" for row in matrix):
        issues.append(_issue("warning", "lineage", "Some business-chain lineage fields are missing or pending.", "Keep pending/stale labels visible in Dashboard and drilldowns."))
    radar_payload = _payload(ctx["radar"]["/api/radar-runtime/daemon/status"])
    runtime_lineage = _first_value(radar_payload, [("last_snapshot_id",), ("daemon", "last_snapshot_id")])
    final_run_id = lineage.get("final_run_id") or dashboard.get("final_run_id")
    app_vue = (ROOT / "frontend" / "src" / "App.vue").read_text(encoding="utf-8", errors="replace")
    freshness_ui_separated = (
        "frozen final lineage" in app_vue
        and "Live Runtime Freshness" in app_vue
        and "live radar heartbeat" in app_vue
    )
    if final_run_id and runtime_lineage and str(final_run_id).split("-")[1:2] != str(runtime_lineage).split("-")[1:2]:
        issues.append(_issue(
            "info" if freshness_ui_separated else "warning",
            "freshness",
            "P4.5 final lineage and live radar runtime snapshot may be from different runtime moments.",
            "Surface final-run frozen lineage separately from live runtime freshness.",
        ))
    return {
        "schema_version": "p12.c02.business_chain_contract_audit.v1",
        "task_id": "P12-C02",
        "generated_at": ctx["generated_at"],
        "overall_status": _status_from_issues(issues),
        "latest_lineage": lineage,
        "business_chain_matrix": matrix,
        "endpoint_summary": {path: {k: v for k, v in result.items() if k != "payload"} for path, result in ctx["p45"].items()},
        "freshness_ui_separated": freshness_ui_separated,
        "issues": issues,
        "follow_up_cards": [
            {
                "candidate": "P12-F01",
                "title": "Frozen Final Lineage vs Live Runtime Freshness UI Label Hardening",
                "needed": any(item["area"] == "freshness" for item in issues),
            }
        ],
    }


def _dashboard_report(ctx: dict[str, Any]) -> dict[str, Any]:
    dashboard = _payload(ctx["p45"]["/api/p45/dashboard/latest"])
    missing = ctx["routes"]["frontend_without_backend"]
    source_action_gaps = [path for path in missing if path.startswith("/api/sources/")]
    issues: list[dict[str, str]] = []
    if not ctx["p45"]["/api/p45/dashboard/latest"]["ok"]:
        issues.append(_issue("blocking", "dashboard_api", "P45 dashboard latest endpoint is unavailable.", "Repair latest endpoint before UI acceptance."))
    if source_action_gaps:
        issues.append(_issue(
            "warning",
            "ui_api_contract",
            "Frontend references source action/detail endpoints that are not implemented by backend.",
            "Create backend endpoints or disable/hide these UI actions until contracts exist.",
        ))
    mapping = [
        {"ui_area": "BTC decision card", "api": "/api/p45/dashboard/latest", "fields": ["final_view", "decision_card", "trade_permission"], "status": "mapped"},
        {"ui_area": "Run lineage side panel", "api": "/api/p45/dashboard/latest", "fields": ["run_lineage.final_run_id", "run_lineage.pack_id"], "status": "mapped"},
        {"ui_area": "Radar panels", "api": "/api/p45/radar-modules/latest + /api/radar-runtime/modules/latest", "fields": ["module_id", "score", "freshness"], "status": "mapped"},
        {"ui_area": "Event window", "api": "/api/event-window/latest + timeline/calendar/alerts", "fields": ["event_id", "source_id", "event_time", "market_probe_status"], "status": "mapped"},
        {"ui_area": "Settings/data source actions", "api": "/api/settings/* + /api/sources/*", "fields": ["source_id", "enabled", "provider", "auth_state"], "status": "partial" if source_action_gaps else "mapped"},
    ]
    return {
        "schema_version": "p12.c03.dashboard_ui_api_contract_audit.v1",
        "task_id": "P12-C03",
        "generated_at": ctx["generated_at"],
        "overall_status": _status_from_issues(issues),
        "dashboard_latest": {
            "final_run_id": _first_value(dashboard, [("run_lineage", "final_run_id"), ("final_run_id",)]),
            "pack_id": _first_value(dashboard, [("run_lineage", "pack_id"), ("pack_id",)]),
            "final_view": dashboard.get("final_view"),
            "trade_permission": dashboard.get("trade_permission"),
        },
        "ui_api_mapping": mapping,
        "frontend_endpoint_count": len(ctx["routes"]["frontend"]),
        "backend_route_count": len(ctx["routes"]["backend"]),
        "frontend_without_backend": missing,
        "source_action_gaps": source_action_gaps,
        "api_error_contract": {
            "store_tracks_endpoint_and_status": True,
            "empty_data_must_not_be_rendered_as_api_error": True,
            "latest_run_must_use": "/api/p45/dashboard/latest",
        },
        "issues": issues,
        "follow_up_cards": [
            {
                "candidate": "P12-F02",
                "title": "Source Action Endpoint Contract Completion",
                "needed": bool(source_action_gaps),
            }
        ],
    }


def _radar_report(ctx: dict[str, Any]) -> dict[str, Any]:
    status = _payload(ctx["radar"]["/api/radar-runtime/daemon/status"])
    modules_payload = _payload(ctx["radar"]["/api/radar-runtime/modules/latest"])
    cockpit = _payload(ctx["radar"]["/api/radar-runtime/cockpit/latest"])
    modules = _list_from(modules_payload, "modules", "items", "snapshots")
    if not modules:
        modules = _list_from(status, "modules", "module_cadence", "next_due_modules")
    issues: list[dict[str, str]] = []
    for path, result in ctx["radar"].items():
        if not result["ok"]:
            issues.append(_issue("blocking", "radar_api", f"{path} is unavailable.", "Repair radar runtime API before module acceptance."))
    module_count = len(modules)
    if module_count and module_count != 14:
        issues.append(_issue("warning", "module_count", f"Radar returned {module_count} modules instead of expected 14.", "Verify module registry/runtime cadence coverage."))
    if not module_count:
        issues.append(_issue("blocking", "module_count", "Radar module list is empty.", "Regenerate radar runtime snapshots and inspect daemon logs."))
    runtime_fresh = _first_value(status, [("runtime_fresh",), ("daemon", "runtime_fresh")])
    source_fresh = _first_value(status, [("source_fresh",), ("daemon", "source_fresh")])
    if runtime_fresh is False or source_fresh is False:
        issues.append(_issue("warning", "freshness", f"Radar freshness runtime={runtime_fresh} source={source_fresh}.", "Keep degraded state visible and rerun source freshness repair if needed."))
    rows = []
    for item in modules[:50]:
        if isinstance(item, dict):
            rows.append({
                "module_id": item.get("module_id") or item.get("id"),
                "score": item.get("module_score") or item.get("score") or item.get("effective_score"),
                "direction": item.get("module_direction") or item.get("direction"),
                "freshness": item.get("freshness_state") or item.get("source_freshness") or item.get("last_status"),
                "snapshot_id": item.get("snapshot_id") or item.get("runtime_snapshot_id"),
            })
    return {
        "schema_version": "p12.c04.radar_runtime_module_score_audit.v1",
        "task_id": "P12-C04",
        "generated_at": ctx["generated_at"],
        "overall_status": _status_from_issues(issues),
        "daemon": {
            "status": _first_value(status, [("status",), ("daemon", "status"), ("raw_status",)]),
            "health_state": _first_value(status, [("health_state",), ("daemon", "health_state")]),
            "runtime_fresh": runtime_fresh,
            "source_fresh": source_fresh,
            "last_snapshot_id": _first_value(status, [("last_snapshot_id",), ("daemon", "last_snapshot_id")]),
            "sqlite_lock_state": _first_value(status, [("sqlite_lock_state",), ("daemon", "sqlite_lock_state")]),
        },
        "module_count": module_count,
        "module_audit_rows": rows,
        "cockpit_summary": {
            "schema_version": cockpit.get("schema_version"),
            "snapshot_id": cockpit.get("snapshot_id"),
            "direction": cockpit.get("direction") or cockpit.get("final_direction"),
            "score": cockpit.get("score") or cockpit.get("aggregate_score"),
        },
        "endpoint_summary": {path: {k: v for k, v in result.items() if k != "payload"} for path, result in ctx["radar"].items()},
        "issues": issues,
    }


def _event_report(ctx: dict[str, Any]) -> dict[str, Any]:
    daemon = _payload(ctx["event"]["/api/event-window/daemon/status"])
    calendar = _payload(ctx["event"]["/api/event-window/calendar?limit=30"])
    timeline = _payload(ctx["event"]["/api/event-window/timeline?limit=100"])
    alerts = _payload(ctx["event"]["/api/event-window/alerts?limit=30"])
    sources = _payload(ctx["event"]["/api/event-window/sources/status"])
    fetches = _payload(ctx["event"]["/api/event-window/sources/fetches?limit=40"])
    issues: list[dict[str, str]] = []
    for path, result in ctx["event"].items():
        if not result["ok"]:
            issues.append(_issue("blocking", "event_api", f"{path} returned {result.get('status_code') or 'no_status'}.", "Repair Event Window endpoint and preserve UI API error surfacing."))
    source_rows = _list_from(sources, "sources", "items")
    if not source_rows:
        issues.append(_issue("warning", "source_diagnostics", "Event source diagnostics returned no source rows.", "Confirm whether source diagnostics are intentionally empty or source fetch table is stale."))
    return {
        "schema_version": "p12.c05.event_window_watchtower_audit.v1",
        "task_id": "P12-C05",
        "generated_at": ctx["generated_at"],
        "overall_status": _status_from_issues(issues),
        "daemon": {
            "status": _first_value(daemon, [("status",), ("daemon", "status"), ("raw_status",)]),
            "health_state": _first_value(daemon, [("health_state",), ("daemon", "health_state")]),
            "runtime_code_version": _first_value(daemon, [("runtime_code_version",), ("daemon", "runtime_code_version")]),
            "last_snapshot_id": _first_value(daemon, [("last_snapshot_id",), ("daemon", "last_snapshot_id")]),
            "last_tick_age_sec": _first_value(daemon, [("last_tick_age_sec",), ("daemon", "last_tick_age_sec")]),
            "market_probe_age_sec": _first_value(daemon, [("market_probe_age_sec",), ("daemon", "market_probe_age_sec")]),
        },
        "event_counts": {
            "calendar": len(_list_from(calendar, "events", "items", "calendar")),
            "timeline": len(_list_from(timeline, "events", "items", "timeline")),
            "alerts": len(_list_from(alerts, "alerts", "items")),
            "sources": len(source_rows),
            "fetches": len(_list_from(fetches, "fetches", "items")),
        },
        "endpoint_summary": {path: {k: v for k, v in result.items() if k != "payload"} for path, result in ctx["event"].items()},
        "issues": issues,
        "follow_up_cards": [
            {
                "candidate": "P12-F03",
                "title": "Event Window Endpoint 500 Regression Repair",
                "needed": any(item["severity"] == "blocking" for item in issues),
            }
        ],
    }


def _settings_report(ctx: dict[str, Any]) -> dict[str, Any]:
    data_sources = _payload(ctx["settings"]["/api/settings/data-sources"])
    provider_health = _payload(ctx["settings"]["/api/settings/providers/health"])
    entitlement = _payload(ctx["settings"]["/api/settings/providers/glassnode/entitlement/latest"])
    issues: list[dict[str, str]] = []
    for path, result in ctx["settings"].items():
        if not result["ok"]:
            issues.append(_issue("blocking", "settings_api", f"{path} is unavailable.", "Repair settings/provider governance endpoint."))
    sources = _list_from(data_sources, "sources", "data_sources", "items")
    enabled_count = sum(1 for row in sources if isinstance(row, dict) and row.get("enabled") is True)
    fallback_count = sum(
        1 for row in sources
        if isinstance(row, dict) and (row.get("fallback_source_id") or row.get("fallback"))
    )
    freshness_count = sum(
        1 for row in sources
        if isinstance(row, dict) and (row.get("freshness_policy") or row.get("freshness"))
    )
    frontend_source_gaps = [
        path for path in ctx["routes"]["frontend_without_backend"] if path.startswith("/api/sources/")
    ]
    if frontend_source_gaps:
        issues.append(_issue(
            "warning",
            "source_governance_ui",
            "Source governance UI references source auth/retry/capture endpoints missing from backend.",
            "Add endpoint contracts or gate these controls by capability metadata.",
        ))
    text = json.dumps(ctx["settings"], ensure_ascii=False)
    secret_patterns = {
        "openai_style_token": r"\bsk-[A-Za-z0-9_-]{20,}\b",
        "long_bearer_token": r"\b[A-Za-z0-9_-]{48,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b",
        "api_key_assignment_value": r"(?i)\b(api[_-]?key|secret|token)\s*[=:]\s*['\"][^'\"*]{12,}['\"]",
    }
    secret_leak_markers = [
        name for name, pattern in secret_patterns.items() if re.search(pattern, text)
    ]
    if secret_leak_markers:
        issues.append(_issue("blocking", "secret_hygiene", f"Potential secret marker(s) in settings payload: {secret_leak_markers}", "Redact settings/provider payloads immediately."))
    return {
        "schema_version": "p12.c06.data_source_settings_provider_governance_audit.v1",
        "task_id": "P12-C06",
        "generated_at": ctx["generated_at"],
        "overall_status": _status_from_issues(issues),
        "source_governance_summary": {
            "source_count": len(sources),
            "enabled_count": enabled_count,
            "fallback_configured_count": fallback_count,
            "freshness_policy_count": freshness_count,
        },
        "provider_health_schema": provider_health.get("schema_version"),
        "glassnode_entitlement": {
            "schema_version": entitlement.get("schema_version"),
            "status": entitlement.get("status") or entitlement.get("entitlement_status"),
            "provider": entitlement.get("provider") or "glassnode",
        },
        "secret_hygiene": {
            "secret_markers_detected": secret_leak_markers,
            "payload_redaction_status": "pass" if not secret_leak_markers else "fail",
        },
        "endpoint_summary": {path: {k: v for k, v in result.items() if k != "payload"} for path, result in ctx["settings"].items()},
        "frontend_source_gaps": frontend_source_gaps,
        "issues": issues,
    }


def _release_report(ctx: dict[str, Any], child_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for task_id, report in child_reports.items():
        if report["overall_status"] == "FAIL":
            issues.append(_issue("blocking", task_id, f"{task_id} child audit failed.", "Resolve child audit blockers before release acceptance."))
        elif report["overall_status"] == "PARTIAL PASS":
            issues.append(_issue("warning", task_id, f"{task_id} child audit has warnings.", "Track follow-up cards and do not present as fully clean release."))
    git_status = ctx["git"]["status_short"]
    if "\n" in git_status or " M " in git_status or "??" in git_status:
        issues.append(_issue("warning", "git", "Working tree is not clean because P12 audit artifacts are in progress.", "Commit P12 artifacts after review if this baseline should be released."))
    github_payload = _payload(ctx["github_actions"])
    latest_run = {}
    runs = github_payload.get("workflow_runs") if isinstance(github_payload.get("workflow_runs"), list) else []
    if runs:
        latest_run = runs[0]
        if latest_run.get("conclusion") != "success":
            issues.append(_issue("blocking", "ci", f"Latest GitHub Actions conclusion is {latest_run.get('conclusion')}.", "Repair CI before release acceptance."))
    elif not ctx["github_actions"].get("ok"):
        issues.append(_issue("warning", "ci", "GitHub Actions latest run could not be queried.", "Check GitHub Actions manually before release."))
    report_inventory = []
    for spec in OUTPUTS.values():
        report_inventory.append({
            "task_id": spec.task_id,
            "json": str(REPORT_DIR / spec.json_name),
            "markdown": str(REPORT_DIR / spec.markdown),
            "html": str(REPORT_DIR / spec.html_name) if spec.html_name else None,
        })
    return {
        "schema_version": "p12.c07.system_release_acceptance.v1",
        "task_id": "P12-C07",
        "generated_at": ctx["generated_at"],
        "overall_status": _status_from_issues(issues),
        "child_status": {task_id: report["overall_status"] for task_id, report in child_reports.items()},
        "git": ctx["git"],
        "github_actions_latest": {
            "id": latest_run.get("id"),
            "status": latest_run.get("status"),
            "conclusion": latest_run.get("conclusion"),
            "html_url": latest_run.get("html_url"),
            "head_sha": latest_run.get("head_sha"),
        },
        "api_health": {path: {k: v for k, v in result.items() if k != "payload"} for group in ["p45", "radar", "event", "settings"] for path, result in ctx[group].items()},
        "report_inventory": report_inventory,
        "release_gate": {
            "clean_git_required": True,
            "ci_green_required": True,
            "smoke_green_required": True,
            "blocking_child_audits_allowed": False,
        },
        "issues": issues,
        "follow_up_cards": [
            {"candidate": "P12-F02", "title": "Source Action Endpoint Contract Completion", "needed": True},
            {"candidate": "P12-F04", "title": "P12 Audit Artifact Release Commit", "needed": bool(issues)},
        ],
    }


def _render_md(report: dict[str, Any], title: str) -> str:
    lines = [
        f"# {report['task_id']} / {title}",
        "",
        f"- status: `{report['overall_status']}`",
        f"- generated_at: `{report['generated_at']}`",
        f"- schema_version: `{report['schema_version']}`",
        "",
        "## Key Evidence",
        "",
    ]
    for key, value in report.items():
        if key in {"schema_version", "task_id", "generated_at", "overall_status", "issues"}:
            continue
        if key.endswith("_summary") or key in {
            "latest_lineage",
            "dashboard_latest",
            "daemon",
            "event_counts",
            "source_governance_summary",
            "child_status",
            "git",
            "github_actions_latest",
            "release_gate",
        }:
            lines.extend([f"### {key}", "", "```json", json.dumps(value, ensure_ascii=False, indent=2, default=_json_default), "```", ""])
    lines.extend(["## Issues", ""])
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(
                f"- `{issue['severity']}` / {issue['area']}: {issue['finding']} "
                f"Recommendation: {issue['recommendation']}"
            )
    else:
        lines.append("- No blocking or warning issues found.")
    lines.extend(["", "## Full JSON", "", f"See `{OUTPUTS[report['task_id']].json_name}`."])
    return "\n".join(lines) + "\n"


def _render_html(report: dict[str, Any], title: str) -> str:
    status_class = report["overall_status"].lower().replace(" ", "-")
    issues = "".join(
        f"<li><strong>{html.escape(issue['severity'])}</strong> / {html.escape(issue['area'])}: "
        f"{html.escape(issue['finding'])}<br><span>{html.escape(issue['recommendation'])}</span></li>"
        for issue in report["issues"]
    ) or "<li>No blocking or warning issues found.</li>"
    body = html.escape(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(report['task_id'])} {html.escape(title)}</title>
  <style>
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 32px; background: #09131a; color: #dbeafe; }}
    .card {{ border: 1px solid #24485c; border-radius: 8px; padding: 18px; margin-bottom: 18px; background: #0d1b24; }}
    .PASS {{ color: #34d399; }}
    .PARTIAL-PASS {{ color: #fbbf24; }}
    .FAIL {{ color: #fb7185; }}
    pre {{ overflow: auto; background: #071017; padding: 14px; border-radius: 6px; }}
    li {{ margin: 10px 0; }}
    span {{ color: #9fb7c8; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{html.escape(report['task_id'])} / {html.escape(title)}</h1>
    <h2 class="{html.escape(status_class.upper())}">{html.escape(report['overall_status'])}</h2>
    <p>generated_at: <code>{html.escape(report['generated_at'])}</code></p>
  </div>
  <div class="card"><h2>Issues</h2><ul>{issues}</ul></div>
  <div class="card"><h2>Full JSON</h2><pre>{body}</pre></div>
</body>
</html>
"""


def _write_report(report: dict[str, Any], spec: OutputSpec) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / spec.json_name).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    (REPORT_DIR / spec.markdown).write_text(_render_md(report, spec.name), encoding="utf-8")
    if spec.html_name:
        (REPORT_DIR / spec.html_name).write_text(_render_html(report, spec.name), encoding="utf-8")


def generate() -> dict[str, dict[str, Any]]:
    ctx = _collect_context()
    reports = {
        "P12-C02": _business_chain_report(ctx),
        "P12-C03": _dashboard_report(ctx),
        "P12-C04": _radar_report(ctx),
        "P12-C05": _event_report(ctx),
        "P12-C06": _settings_report(ctx),
    }
    reports["P12-C07"] = _release_report(ctx, reports)
    for task_id in ["P12-C02", "P12-C03", "P12-C04", "P12-C05", "P12-C06", "P12-C07"]:
        _write_report(reports[task_id], OUTPUTS[task_id])
    return reports


def main() -> int:
    reports = generate()
    summary = {task_id: report["overall_status"] for task_id, report in reports.items()}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
