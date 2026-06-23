from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "ui-references/p5-dashboard-high-fidelity.html",
    "ui-references/p5-subpages-high-fidelity.html",
    "tasks/ui/p5-dashboard-ui-prototype.md",
    "tasks/ui/p5-dashboard-acceptance-matrix.md",
    "tasks/P5/p5-c26-dashboard像素级还原fastapi契约与页面验收矩阵.md",
    "frontend/src/api.ts",
    "frontend/src/store.ts",
    "frontend/src/App.vue",
]

REQUIRED_API_METHODS = [
    "getP45DashboardLatest",
    "getP45OverviewLatest",
    "getP45RadarModulesLatest",
    "getP45RadarModule",
    "getP45Evidence",
    "getP45EvidenceItem",
    "getP45ArticlesLatest",
    "getP45ArticleHistory",
    "getP45AnalystsLatest",
    "getP45LlmLatest",
    "getP45InvalidationLatest",
    "getDataQualityLatest",
    "getP3AlertsLatest",
    "getP45RunsLatest",
    "getP45AuditReportsLatest",
    "getRunAuditReports",
    "getP45History",
    "getSettings",
    "runP45FullWithLlm",
]

REQUIRED_ENDPOINTS = [
    "/api/p45/dashboard/latest",
    "/api/p45/overview/latest",
    "/api/p45/radar-modules/latest",
    "/api/p45/radar-modules/",
    "/api/p45/articles/history",
    "/api/p3/alerts/latest",
    "/api/p3/events/latest",
    "/api/p45/invalidation/latest",
    "/api/data-quality/latest",
    "/api/p45/audit-reports/latest",
    "/api/p45/runs/latest",
    "/api/p45/run-full-with-llm",
    "/reports/",
]

REQUIRED_RAIL_LABELS = ["拓扑", "雷达", "证据", "预警", "质检", "日志", "回放", "设置"]

REQUIRED_SCREENSHOTS = [
    "screenshots/p5-dashboard-1440.png",
    "screenshots/p5-dashboard-1920.png",
    "screenshots/p5-dashboard-mobile.png",
]

FORBIDDEN_TRADING_TERMS = ["买入", "卖出", "开仓", "止损", "止盈", "杠杆", "仓位"]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assert_true(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        assert_true((ROOT / rel).exists(), f"missing required file: {rel}", errors)

    api_ts = read("frontend/src/api.ts")
    store_ts = read("frontend/src/store.ts")
    app_vue = read("frontend/src/App.vue")
    task_card = read("tasks/P5/p5-c26-dashboard像素级还原fastapi契约与页面验收矩阵.md")
    matrix = read("tasks/ui/p5-dashboard-acceptance-matrix.md")

    for method in REQUIRED_API_METHODS:
        assert_true(method in api_ts or method in store_ts, f"missing api/store method: {method}", errors)

    for endpoint in REQUIRED_ENDPOINTS:
        assert_true(endpoint in api_ts or endpoint in task_card, f"missing endpoint contract: {endpoint}", errors)

    for label in REQUIRED_RAIL_LABELS:
        assert_true(label in app_vue and label in matrix, f"missing rail label: {label}", errors)

    assert_true("fetch(" not in app_vue, "App.vue must not contain raw fetch()", errors)
    assert_true("import { api }" not in app_vue, "App.vue must not import api directly", errors)
    assert_true("isHistorical" in store_ts, "store must guard History Replay from latest refresh", errors)
    assert_true("ApiClientError" in api_ts, "api client must expose endpoint-level error context", errors)
    assert_true("onlybtc:p5:radar-layout:v1" in app_vue, "Radar layout must persist to localStorage", errors)
    assert_true("Reset Layout" in app_vue, "Radar topology must expose Reset Layout control", errors)
    assert_true("dynamicLinks" in app_vue and "linkPath(" in app_vue, "Radar links must be generated dynamically", errors)
    assert_true("@pointerdown" in app_vue and "clampAwayFromBtc" in app_vue, "Radar nodes must support bounded drag", errors)
    assert_true(".link.neutral" in read("frontend/src/styles.css"), "Neutral radar modules must have visible links", errors)
    assert_true("repelByActiveNode" in app_vue, "Dragging one radar node must dynamically move nearby nodes", errors)
    assert_true("moduleReadableSummary" in app_vue and "moduleAuditMeta" in app_vue, "Radar nodes must separate readable summary from audit meta", errors)
    assert_true("scaleByDistance" in task_card or "scaleByDistance" in read("tasks/P5/p5-c03-雷达分组节点与数据源状态展示.md"), "P5-C03 must document distance scaling", errors)
    assert_true("eventWindowRows" in app_vue and "eventDailyWatch" in app_vue, "Dashboard must render P3 event window daily watch cards", errors)
    assert_true("halvingStats" in app_vue and "btc_halving_estimated_days" in app_vue, "Dashboard must render BTC halving background metrics", errors)
    assert_true("cooldownText" in app_vue and "confirmationRules" in app_vue, "Dashboard alerts must show cooldown plus confirmation rules", errors)
    assert_true("metricLabelMap" in app_vue and "metricLabel(" in app_vue, "Horizon view must map metric ids to readable labels", errors)
    assert_true("support_drivers" in app_vue and "pressure_drivers" in app_vue and "dominant_drivers" in app_vue, "Horizon view must render support, pressure and dominant drivers", errors)
    assert_true("horizonWatchRules" in app_vue and "horizon-detail-card" in app_vue, "Overview must render detailed horizon watch rules", errors)
    assert_true("runAndOpenLogs" in app_vue and "runP45FullWithLlm" in store_ts + api_ts, "Run Full Chain must use P4.5 full chain API", errors)
    assert_true("stage-grid" in app_vue and "audit-report-grid" in app_vue, "Run Logs must render stages and audit report links", errors)
    assert_true("completed_with_llm_errors" in app_vue or "非阻塞降级" in app_vue, "Run Logs must explain non-blocking LLM degraded status", errors)
    assert_true("reportHref" in app_vue and "/reports/" in app_vue and ":8118" in app_vue, "Audit report buttons must open FastAPI-served report HTML", errors)

    for screenshot in REQUIRED_SCREENSHOTS:
        assert_true(screenshot in task_card and screenshot in matrix, f"missing screenshot contract: {screenshot}", errors)

    production_text = "\n".join([app_vue, matrix])
    for term in FORBIDDEN_TRADING_TERMS:
        # The matrix itself names forbidden terms; allow them only inside the forbidden section.
        if term in app_vue:
            errors.append(f"forbidden trading term appears in App.vue: {term}")

    nav_label_lengths = re.findall(r"\{ id: '[^']+', label: '([^']+)' \}", app_vue)
    for label in nav_label_lengths:
        if label in REQUIRED_RAIL_LABELS:
            assert_true(2 <= len(label) <= 4, f"rail label length out of range: {label}", errors)

    if errors:
        print("P5 dashboard contract validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("P5 dashboard contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
