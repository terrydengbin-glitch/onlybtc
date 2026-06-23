from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_BASE = "http://127.0.0.1:8118"
FRONTEND_BASE = "http://127.0.0.1:5188"

PAGE_IDS = [
    "topology",
    "overview",
    "radar",
    "evidence",
    "article",
    "alerts",
    "invalidation",
    "quality",
    "source",
    "conflict",
    "logs",
    "history",
    "settings",
]

CORE_ENDPOINTS = [
    "/api/p45/dashboard/latest",
    "/api/p45/overview/latest",
    "/api/p45/radar-modules/latest",
    "/api/p45/articles/latest",
    "/api/p45/articles/history",
    "/api/p45/analysts/latest",
    "/api/p45/llm/latest",
    "/api/p45/invalidation/latest",
    "/api/data-quality/latest",
    "/api/p3/alerts/latest",
    "/api/p3/events/latest",
    "/api/p45/runs/latest",
    "/api/p45/audit-reports/latest",
    "/api/settings",
]


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def warn(self, condition: bool, message: str) -> None:
        if not condition:
            self.warnings.append(message)


def fetch(path: str, *, method: str = "GET") -> tuple[int, bytes]:
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    request = Request(url, method=method, headers={"Accept": "application/json,text/html,*/*"})
    with urlopen(request, timeout=20) as response:
        return int(response.status), response.read()


def get_json(path: str) -> dict:
    status, body = fetch(path)
    if status >= 400:
        raise RuntimeError(f"{path} returned HTTP {status}")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} did not return an object")
    return payload


def http_exists(path_or_url: str) -> bool:
    try:
        status, _ = fetch(path_or_url, method="HEAD")
        return 200 <= status < 400
    except HTTPError as err:
        if err.code == 405:
            status, _ = fetch(path_or_url)
            return 200 <= status < 400
        return False
    except (TimeoutError, URLError):
        return False


def report_url(report: dict) -> str:
    relative = str(report.get("relative_path") or report.get("filename") or "")
    parts = [part for part in relative.replace("\\", "/").split("/") if part]
    if "reports" in parts:
        parts = parts[parts.index("reports") + 1 :]
    if not parts:
        return str(report.get("file_url") or "")
    return f"{API_BASE}/reports/" + "/".join(quote(part) for part in parts)


def status_ok(payload: dict) -> bool:
    return str(payload.get("status", "")).lower() in {"ok", "passed", "completed"}


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate_api_contract(v: Validation) -> dict[str, dict]:
    payloads: dict[str, dict] = {}
    for endpoint in CORE_ENDPOINTS:
        try:
            payloads[endpoint] = get_json(endpoint)
        except Exception as exc:  # noqa: BLE001 - surface all endpoint failures in one report.
            v.errors.append(f"{endpoint} failed: {exc}")

    if v.errors:
        return payloads

    dashboard = payloads["/api/p45/dashboard/latest"]
    overview = payloads["/api/p45/overview/latest"]
    radar = payloads["/api/p45/radar-modules/latest"]
    articles = payloads["/api/p45/articles/latest"]
    article_history = payloads["/api/p45/articles/history"]
    invalidation = payloads["/api/p45/invalidation/latest"]
    runs = payloads["/api/p45/runs/latest"]
    reports = payloads["/api/p45/audit-reports/latest"]
    settings = payloads["/api/settings"]

    for endpoint, payload in payloads.items():
        v.require(status_ok(payload), f"{endpoint} status is not ok")
        v.require("schema_version" in payload, f"{endpoint} missing schema_version")

    lineage = dashboard.get("run_lineage") or {}
    final_run_id = str(lineage.get("final_run_id") or runs.get("latest", {}).get("final_run_id") or "")
    v.require(bool(final_run_id), "dashboard/runs missing final_run_id")
    v.require(overview.get("final_view") == dashboard.get("final_view"), "overview final_view differs from dashboard")
    v.require(isinstance(dashboard.get("decision_card"), dict), "dashboard missing decision_card")
    v.require(isinstance(dashboard.get("aggregation_audit"), dict), "dashboard missing aggregation_audit")
    v.require(isinstance(dashboard.get("horizon_views"), dict), "dashboard missing horizon_views")
    v.require(isinstance(dashboard.get("contract_validation"), dict), "dashboard missing contract_validation")
    v.require(isinstance(dashboard.get("data_quality"), dict), "dashboard missing data_quality")

    modules = radar.get("modules") or radar.get("radar_modules") or []
    v.require(len(modules) >= 14, f"radar module count too low: {len(modules)}")
    first_module = modules[0] if modules else {}
    module_id = str(first_module.get("radar_module") or first_module.get("module_id") or "")
    v.require(bool(module_id), "first radar module missing module id")
    if module_id:
        detail = get_json(f"/api/p45/radar-modules/{quote(module_id)}")
        v.require(status_ok(detail), "radar detail status is not ok")
        v.require("module" in detail and "metrics" in detail, "radar detail missing module/metrics")

    evidence = get_json("/api/p45/evidence?limit=200")
    items = evidence.get("items") or []
    v.require(len(items) >= 20, f"evidence item count too low: {len(items)}")
    first_evidence = items[0] if items else {}
    evidence_id = str(first_evidence.get("evidence_id") or "")
    source_id = str(first_evidence.get("source_id") or "")
    v.require(bool(evidence_id), "first evidence missing evidence_id")
    v.require(bool(source_id), "first evidence missing source_id")
    if evidence_id:
        detail = get_json(f"/api/p45/evidence/{quote(evidence_id)}")
        v.require(status_ok(detail), "evidence detail status is not ok")
        v.require("evidence" in detail, "evidence detail missing evidence object")
    if source_id:
        detail = get_json(f"/api/sources/{quote(source_id)}")
        v.require(status_ok(detail), "source detail status is not ok")
        v.require("source" in detail and "runs" in detail and "metrics" in detail, "source detail missing source/runs/metrics")

    v.require(bool(articles.get("publish_article")), "articles missing publish_article")
    v.require(bool(articles.get("research_article") or articles.get("deterministic_article")), "articles missing research article")
    v.require(bool(articles.get("llm_research")), "articles missing llm_research appendix")
    v.require(bool(articles.get("llm_analyst_articles") or articles.get("analyst_articles")), "articles missing analyst articles")
    v.require(len(article_history.get("items") or []) >= 1, "article history missing snapshots")
    publish_body = str((articles.get("publish_article") or {}).get("body") or "")
    v.require("$BTC" in publish_body, "publish article missing $BTC")
    forbidden = ["p3-score", "run_id", "schema_version", "@{", "System.Object"]
    for token in forbidden:
        v.require(token not in publish_body, f"publish article leaks internal token: {token}")

    v.require(len(invalidation.get("invalidation_rules") or []) >= 3, "invalidation rules count too low")
    v.require(len(invalidation.get("confirmation_rules") or []) >= 1, "confirmation rules missing")
    v.require(len(runs.get("stages") or []) >= 5, "run stages count too low")
    v.require(len(reports.get("reports") or []) >= 4, "audit report count too low")
    v.require(bool(settings.get("llm")), "settings missing llm block")

    if final_run_id:
        history = get_json(f"/api/p45/history/{quote(final_run_id)}")
        v.require(status_ok(history), "history replay status is not ok")
        v.require("final" in history and "audit_reports" in history, "history replay missing final/audit_reports")

    phases = {str(report.get("phase")) for report in reports.get("reports") or []}
    for phase in ["p1", "p2", "p3", "p45"]:
        v.require(phase in phases, f"audit reports missing {phase}")
    for report in reports.get("reports") or []:
        url = report_url(report)
        v.require(url.startswith(f"{API_BASE}/reports/"), f"report URL is not FastAPI static URL: {url}")
        v.require(http_exists(url), f"report URL is not reachable: {url}")

    return payloads


def validate_frontend_contract(v: Validation) -> None:
    app_vue = read_text("frontend/src/App.vue")
    store_ts = read_text("frontend/src/store.ts")
    api_ts = read_text("frontend/src/api.ts")

    for page_id in PAGE_IDS:
        v.require(page_id in app_vue, f"App.vue missing page id: {page_id}")
    v.require("validPageIds" in app_vue and "URLSearchParams" in app_vue, "App.vue missing direct page query support")
    v.require("loadRadarDetail" in store_ts and "getP45RadarModule" in api_ts, "radar detail API path not wired")
    v.require("loadEvidenceDetail" in store_ts and "getP45EvidenceItem" in api_ts, "evidence detail API path not wired")
    v.require("loadSourceDetail" in store_ts and "getSourceDetail" in api_ts, "source detail API path not wired")
    v.require("loadHistory" in store_ts and "getP45History" in api_ts, "history replay API path not wired")
    v.require("runFullChain" in store_ts and "runP45FullWithLlm" in api_ts, "Run Full Chain API path not wired")
    v.require("reportHref" in app_vue and "/reports/" in app_vue and ":8118" in app_vue, "report buttons must open FastAPI report HTML")
    v.require("activePage === 'article'" in app_vue and "LLM Research Appendix" in app_vue, "article page missing LLM appendix section")
    v.require("Article Center" in app_vue and "History Snapshots" in app_vue, "article page missing article center/history snapshots")
    v.require("Evidence Citations" in app_vue and "openArticleCitation" in app_vue, "article page missing evidence citation jump")
    v.require("Evidence Workbench" in app_vue and "filteredEvidenceItems" in app_vue, "evidence page missing workbench/filter wiring")
    v.require("Source & Freshness" in app_vue and "evidenceRunLineage" in app_vue, "evidence page missing source freshness/run lineage")
    v.require("Horizon & Duplicate" in app_vue and "History Context" in app_vue, "evidence page missing horizon duplicate/history context")
    v.require("Open Source Detail" in app_vue and "openSourceDetail" in app_vue, "evidence page missing source detail jump")
    v.require("Key Drivers / Conflicting Evidence" in app_vue and "overviewSupportDrivers" in app_vue, "overview page missing key driver detail")
    v.require("Confidence Explanation" in app_vue and "overviewScoreNormalization" in app_vue, "overview page missing confidence explanation")
    v.require("What Would Change The View" in app_vue and "overviewWatchRows" in app_vue, "overview page missing view-change rules")
    v.require("Run Lineage" in app_vue and "overviewRunLineage" in app_vue, "overview page missing run lineage")
    v.require("activePage === 'logs'" in app_vue and "stage-grid" in app_vue, "run logs page missing stage grid")
    v.require("activePage === 'history'" in app_vue and "isHistorical" in store_ts, "history replay page missing frozen context")
    v.require("<h2>Settings</h2>" in app_vue and "getSettings" in api_ts, "settings page missing API wiring")


def validate_frontend_pages(v: Validation) -> None:
    try:
        status, body = fetch(FRONTEND_BASE)
    except Exception as exc:  # noqa: BLE001
        v.errors.append(f"frontend root is not reachable: {exc}")
        return
    v.require(status == 200, f"frontend root returned HTTP {status}")
    html = body.decode("utf-8", errors="ignore")
    v.require("id=\"app\"" in html, "frontend root missing Vue app container")

    for page_id in PAGE_IDS:
        url = f"{FRONTEND_BASE}/?page={quote(page_id)}"
        v.require(http_exists(url), f"frontend page route not reachable: {url}")


def main() -> int:
    v = Validation()
    validate_api_contract(v)
    validate_frontend_contract(v)
    validate_frontend_pages(v)

    if v.warnings:
        print("P5 page DoD warnings:")
        for warning in v.warnings:
            print(f"- {warning}")

    if v.errors:
        print("P5 page DoD validation failed:")
        for error in v.errors:
            print(f"- {error}")
        return 1

    print("P5 page DoD validation passed.")
    print(f"- API base: {API_BASE}")
    print(f"- Frontend base: {FRONTEND_BASE}")
    print(f"- Checked pages: {', '.join(PAGE_IDS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
