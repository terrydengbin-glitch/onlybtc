from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.registry import METRIC_DEFINITIONS, SOURCE_CONFIGS
from onlybtc.sources.service import (
    collect_sources,
    historical_window,
    source_health_summary,
)

REPORT_FILENAMES = {
    "summary": "p1-c22-真实数据全链路验收报告.md",
    "metrics": "p1-c22-指标参数清单.md",
    "issues": "p1-c22-失败数据源与问题清单.md",
    "html": "p1-c22-真实数据全链路验收报告.html",
}

FIELD_LABELS = {
    "metric_id": "指标参数名",
    "display_name": "指标显示名",
    "source_id": "数据源 ID",
    "source_name": "数据源名称",
    "source_group": "所属分组",
    "radar_module": "所属雷达",
    "source_update_frequency": "源数据更新频率",
    "local_refresh_policy": "本地采集频率",
    "source_form": "数据形式",
    "value_unit": "单位",
    "higher_is": "数值升高含义",
    "quality_score": "质量分",
    "collection_freshness_status": "采集新鲜度",
    "business_recency_status": "业务时间状态",
    "collection_age_seconds": "距本次采集秒数",
    "business_age_seconds": "距源数据时间秒数",
    "source_ts": "源数据业务时间",
    "collected_at": "本地采集时间",
    "freshness_minutes": "采集新鲜度分钟",
    "stale_after_minutes": "过期阈值分钟",
    "is_stale": "是否偏旧/过期",
    "freshness_policy": "新鲜度策略",
    "importance": "重要程度",
    "arbitration_role": "多源仲裁角色",
    "conflict_status": "多源冲突",
    "sqlite_status": "SQLite 状态",
    "radar_consumed": "Radar 是否消费",
    "notes": "备注",
    "module_id": "雷达模块",
    "signal": "信号",
    "strength": "强度",
    "confidence": "置信度",
    "data_quality": "数据质量",
    "table": "数据表",
    "count": "数量",
    "failure_reason": "失败原因",
    "detail": "详情",
    "impact": "影响",
    "fallback_or_proxy": "Fallback / 代理",
    "next_action": "下一步",
    "type": "问题类型",
    "scope": "影响范围",
}

VALUE_LABELS = {
    "expected_lag": "expected lag",
    "fresh": "新鲜",
    "stale": "偏旧",
    "expired": "过期",
    "missing": "缺失",
    "current": "正常",
    "lagging": "滞后",
    "outdated": "过旧",
    "provider_stale_suspect": "provider suspect",
    "unknown": "未知",
    "high": "高",
    "medium": "中",
    "low": "低",
    "stored": "已写入",
    "partial": "历史有值/本轮未产出",
    "yes": "是",
    "no": "否",
    "selected": "主源",
    "fallback": "备用源",
    "cross_check": "交叉验证",
    "single_source": "单一来源",
    "not_selected": "未选中",
    "not_candidate": "非候选源",
    "none": "无",
    "bullish": "偏多",
    "bearish": "偏空",
    "mixed": "混合",
    "healthy": "健康",
    "warning": "警告",
    "critical": "严重",
    "error": "错误",
    "source_conflict": "多源冲突",
    "radar_quality": "雷达质量偏低",
    "collection_freshness": "采集新鲜度",
    "business_recency": "业务时间状态",
    "missing_metrics": "指标缺失",
    "partial_current_run": "本轮部分未产出",
    "collection_failures": "采集失败",
    "registry_drift": "注册表漂移",
    "event_countdown": "事件倒计时",
    "proxy": "代理指标",
    "llm_scored": "LLM 评分",
    "self_calculated": "自计算",
    "raw_source": "源数据",
    "bearish_for_btc": "对 BTC 偏空",
    "bullish_for_btc": "对 BTC 偏多",
    "neutral": "中性",
}

BUSINESS_RECENCY_STATUS_ORDER = (
    "current",
    "expected_lag",
    "lagging",
    "outdated",
    "provider_stale_suspect",
    "unknown",
)


async def run_p1_c22_audit(
    collect_live: bool = True,
    source_ids: list[str] | None = None,
    collection_result: dict[str, Any] | None = None,
    radar_result: dict[str, Any] | None = None,
    run_diagnostic_radar: bool = True,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    started_at = datetime.now(UTC)
    if collect_live and collection_result is None:
        collection_result = await collect_sources(
            mode=SourceMode.LIVE,
            source_ids=source_ids,
            db=db,
        )
    if radar_result is None:
        radar_result = (
            analyze_radars(db=db)
            if run_diagnostic_radar
            else {"run_id": None, "analyzed": 0, "modules": []}
        )
    context = _build_context(
        started_at=started_at,
        collection_result=collection_result,
        radar_result=radar_result,
        source_ids=source_ids,
        db=db,
    )
    report_dir = paths.project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "summary": _write_report(
            report_dir / REPORT_FILENAMES["summary"],
            _summary_report(context),
        ),
        "metrics": _write_report(
            report_dir / REPORT_FILENAMES["metrics"],
            _metrics_report(context),
        ),
        "issues": _write_report(report_dir / REPORT_FILENAMES["issues"], _issues_report(context)),
        "html": _write_report(
            report_dir / REPORT_FILENAMES["html"],
            _html_report(context),
        ),
    }
    return {
        "状态": "完成",
        "报告语言": "中文",
        "HTML输出": "已生成",
        "HTML报告路径": str(outputs["html"]),
        "是否执行真实采集": collect_live,
        "采集run_id": context["collect_run_id"],
        "雷达run_id": context["radar_run_id"],
        "P1诊断雷达run_id": context["radar_run_id"],
        "报告路径": {key: str(path) for key, path in outputs.items()},
        "数据源数量": len(context["sources"]),
        "指标数量": len(context["metric_rows"]),
        "失败数量": len(context["failures"]),
        "问题数量": len(context["problems"]),
    }


def run_p1_c22_audit_sync(
    collect_live: bool = True,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    return asyncio.run(run_p1_c22_audit(collect_live=collect_live, source_ids=source_ids))


def _build_context(
    started_at: datetime,
    collection_result: dict[str, Any] | None,
    radar_result: dict[str, Any],
    source_ids: list[str] | None,
    db: Database,
) -> dict[str, Any]:
    collect_run_id = (
        collection_result.get("run_id")
        if collection_result
        else _latest_collect_run_id(
            db,
            run_mode="live",
            min_source_count=None if source_ids else _full_collect_min_source_count(),
        )
    )
    radar_metric_map = _radar_metric_map()
    current_run_metric_by_key = _latest_metric_by_key(db, run_id=collect_run_id)
    any_metric_by_key = _latest_metric_by_key(db, run_mode="live")
    source_health = source_health_summary(db)
    source_health_by_id = {
        item["source_id"]: item for item in source_health.get("events", [])
    }
    metric_rows = [
        _metric_row(
            metric,
            radar_metric_map,
            current_run_metric_by_key,
            any_metric_by_key,
            db,
        )
        for metric in METRIC_DEFINITIONS
        if source_ids is None or metric.source_id in set(source_ids)
    ]
    failures = _failure_rows(collection_result, metric_rows, source_health_by_id, db)
    extra_db_sources = _extra_db_sources(db)
    run_mode_summary = _audit_run_mode_summary(db, current_run_id=collect_run_id)
    fallback_summary = _audit_fallback_summary(collection_result, db)
    problems = _problem_rows(
        metric_rows,
        failures,
        radar_result,
        extra_db_sources,
        run_mode_summary,
    )
    return {
        "started_at": started_at,
        "completed_at": datetime.now(UTC),
        "collection_result": collection_result,
        "collect_run_id": collect_run_id,
        "radar_result": radar_result,
        "radar_run_id": radar_result["run_id"],
        "source_ids": source_ids,
        "sources": SOURCE_CONFIGS,
        "metric_rows": metric_rows,
        "failures": failures,
        "problems": problems,
        "table_counts": _table_counts(db),
        "source_health": source_health,
        "extra_db_sources": extra_db_sources,
        "run_mode_summary": run_mode_summary,
        "fallback_summary": fallback_summary,
    }


def _metric_row(
    metric: Any,
    radar_metric_map: dict[str, list[str]],
    current_run_metric_by_key: dict[tuple[str, str], schema.MetricValue],
    any_metric_by_key: dict[tuple[str, str], schema.MetricValue],
    db: Database,
) -> dict[str, Any]:
    source = _source_by_id(metric.source_id)
    window = historical_window(metric.metric_id, db=db)
    source_window = historical_window(metric.metric_id, source_id=metric.source_id, db=db)
    metric_key = (metric.metric_id, metric.source_id)
    current_run_value = current_run_metric_by_key.get(metric_key)
    any_value = any_metric_by_key.get(metric_key)
    radar_modules = radar_metric_map.get(metric.metric_id, [])
    conflict = window.get("conflict") if window else None
    conflict_status = _conflict_status(conflict)
    sqlite_status = "stored" if current_run_value else "partial" if any_value else "missing"
    radar_consumed = (
        "yes" if radar_modules and window and window.get("current") is not None else "no"
    )
    return {
        "metric_id": metric.metric_id,
        "display_name": metric.name,
        "source_id": metric.source_id,
        "source_name": source.name if source else "",
        "source_group": source.group_name if source else metric.group_name,
        "radar_module": ", ".join(radar_modules) if radar_modules else "-",
        "source_update_frequency": _source_update_frequency(source, metric.metric_id),
        "local_refresh_policy": _local_refresh_policy(source),
        "source_form": _source_form(source, metric.metric_id),
        "value_unit": metric.unit or "",
        "higher_is": metric.higher_is,
        "quality_score": _fmt_float(
            source_window.get("effective_quality_score") if source_window else None
        ),
        "freshness_status": source_window.get("freshness_status") if source_window else "missing",
        "collection_freshness_status": (
            source_window.get("collection_freshness_status") if source_window else "missing"
        ),
        "business_recency_status": (
            source_window.get("business_recency_status") if source_window else "unknown"
        ),
        "age_seconds": _fmt_float(source_window.get("age_seconds") if source_window else None),
        "collection_age_seconds": _fmt_float(
            source_window.get("collection_age_seconds") if source_window else None
        ),
        "business_age_seconds": _fmt_float(
            source_window.get("business_age_seconds") if source_window else None
        ),
        "source_ts": source_window.get("source_ts") if source_window else "",
        "collected_at": source_window.get("collected_at") if source_window else "",
        "freshness_minutes": _fmt_float(
            source_window.get("freshness_minutes") if source_window else None
        ),
        "stale_after_minutes": _fmt_float(
            source_window.get("stale_after_minutes") if source_window else None
        ),
        "is_stale": source_window.get("is_stale") if source_window else "",
        "expected_refresh_seconds": _fmt_float(
            source_window.get("expected_refresh_seconds") if source_window else None
        ),
        "freshness_policy": (
            (source_window.get("freshness_policy") or {}).get("cadence")
            if source_window
            else "unknown"
        ),
        "importance": _importance(metric.metric_id, radar_modules),
        "arbitration_role": _arbitration_role(metric.source_id, window),
        "conflict_status": conflict_status,
        "sqlite_status": sqlite_status,
        "radar_consumed": radar_consumed,
        "notes": _metric_notes(metric.metric_id, window, source_window),
    }


def _summary_report(context: dict[str, Any]) -> str:
    collection = context["collection_result"] or {}
    data_quality = collection.get("data_quality", {})
    freshness_counts = data_quality.get("payload", {}).get("freshness_counts", {})
    business_recency_counts = _business_recency_counts_from_metric_rows(
        context["metric_rows"]
    )
    lines = [
        "# P1-C22 真实数据全链路验收报告",
        "",
        f"- 执行开始：{context['started_at'].isoformat()}",
        f"- 执行完成：{context['completed_at'].isoformat()}",
        f"- 采集 run_id：{context['collect_run_id'] or '未执行 live 采集'}",
        f"- P1 诊断 Radar run_id：{context['radar_run_id'] or '未执行'}",
        f"- 数据源数量：{len(context['sources'])}",
        f"- 指标数量：{len(context['metric_rows'])}",
        f"- 失败/缺失项：{len(context['failures'])}",
        "",
        "## 执行命令",
        "",
        "```powershell",
        "..\\.venv\\Scripts\\python.exe -m onlybtc.cli p1-c22-audit",
        "```",
        "",
        "## 采集结果",
        "",
        f"- 已采集数据源：{collection.get('collected', '-')}",
        f"- 采集错误数：{len(collection.get('errors', [])) if collection else '-'}",
        f"- 数据质量分：{data_quality.get('score', '-')}",
        f"- 数据质量状态：{_zh(data_quality.get('status', '-'))}",
        f"- 采集新鲜度：{_zh_counts(freshness_counts)}",
        f"- 业务时间状态：{_zh_counts(business_recency_counts)}",
        f"- Run Mode 混用风险：{_production_blocker_label(context['run_mode_summary'])}",
        f"- Fallback/警告源数量：{context['fallback_summary'].get('warning_source_count', 0)}",
        "",
        "## SQLite 写入统计",
        "",
        _markdown_table(
            ["table", "count"],
            [[key, value] for key, value in context["table_counts"].items()],
            translate=True,
        ),
        "",
        "## Radar 消费结果",
        "",
        _markdown_table(
            ["module_id", "signal", "strength", "confidence", "data_quality"],
            [
                [
                    item["module_id"],
                    item["signal"],
                    item["strength"],
                    item["confidence"],
                    item["data_quality"],
                ]
                for item in context["radar_result"].get("modules", [])
            ],
            translate=True,
        ),
        "",
        "## Run Mode 混用风险",
        "",
        _markdown_table(
            ["type", "count"],
            [
                ["current_run_id", context["run_mode_summary"].get("current_run_id") or "-"],
                [
                    "current_run_live_only",
                    context["run_mode_summary"].get("current_run_live_only", False),
                ],
                [
                    "current_run_live_count",
                    context["run_mode_summary"].get("current_run_live_count", 0),
                ],
                [
                    "current_run_mock_count",
                    context["run_mode_summary"].get("current_run_mock_count", 0),
                ],
                [
                    "current_run_test_count",
                    context["run_mode_summary"].get("current_run_test_count", 0),
                ],
                [
                    "current_run_unknown_count",
                    context["run_mode_summary"].get("current_run_unknown_count", 0),
                ],
                ["default_query_scope", context["run_mode_summary"].get("default_query_scope")],
                ["live_metric_values", context["run_mode_summary"].get("live_metric_values", 0)],
                ["mock_metric_values", context["run_mode_summary"].get("mock_metric_values", 0)],
                ["test_metric_values", context["run_mode_summary"].get("test_metric_values", 0)],
                [
                    "unknown_metric_values",
                    context["run_mode_summary"].get("unknown_metric_values", 0),
                ],
                ["mixed_metric_ids", len(context["run_mode_summary"].get("mixed_metric_ids", []))],
            ],
        ),
        "",
        "## Fallback / 默认数据使用清单",
        "",
        _markdown_table(
            ["type", "count"],
            [
                [
                    "fallback_event_count",
                    context["fallback_summary"].get("fallback_event_count", 0),
                ],
                [
                    "warning_source_count",
                    context["fallback_summary"].get("warning_source_count", 0),
                ],
                [
                    "http_403_sources",
                    ", ".join(context["fallback_summary"].get("http_403_sources", [])) or "-",
                ],
            ],
        ),
        "",
        "## 链路结论",
        "",
        _chain_conclusion(context),
    ]
    return "\n".join(lines) + "\n"


def _metrics_report(context: dict[str, Any]) -> str:
    headers = [
        "metric_id",
        "display_name",
        "source_id",
        "source_group",
        "radar_module",
        "source_update_frequency",
        "local_refresh_policy",
        "source_form",
        "value_unit",
        "higher_is",
        "quality_score",
        "collection_freshness_status",
        "business_recency_status",
        "source_ts",
        "collected_at",
        "freshness_minutes",
        "stale_after_minutes",
        "is_stale",
        "collection_age_seconds",
        "business_age_seconds",
        "freshness_policy",
        "importance",
        "arbitration_role",
        "conflict_status",
        "sqlite_status",
        "radar_consumed",
        "notes",
    ]
    return (
        "# P1-C22 指标参数清单\n\n"
        + _markdown_table(
            headers,
            [[row.get(header, "") for header in headers] for row in context["metric_rows"]],
            translate=True,
        )
        + "\n"
    )


def _issues_report(context: dict[str, Any]) -> str:
    failure_headers = [
        "metric_id",
        "source_id",
        "radar_module",
        "failure_reason",
        "detail",
        "impact",
        "fallback_or_proxy",
        "next_action",
    ]
    problem_headers = ["type", "scope", "detail", "impact", "next_action"]
    return (
        "# P1-C22 失败数据源与问题清单\n\n"
        "## 失败/缺失数据\n\n"
        + _markdown_table(
            failure_headers,
            [[row.get(header, "") for header in failure_headers] for row in context["failures"]],
            translate=True,
        )
        + "\n\n## 当前问题清单\n\n"
        + _markdown_table(
            problem_headers,
            [[row.get(header, "") for header in problem_headers] for row in context["problems"]],
            translate=True,
        )
        + "\n"
    )


def _failure_rows(
    collection_result: dict[str, Any] | None,
    metric_rows: list[dict[str, Any]],
    source_health_by_id: dict[str, dict[str, Any]],
    db: Database,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for error in (collection_result or {}).get("errors", []):
        source_id = error["source_id"]
        source = _source_by_id(source_id)
        for metric_id in source.metrics if source else ["-"]:
            rows.append(
                {
                    "metric_id": metric_id,
                    "source_id": source_id,
                    "radar_module": _radar_metric_map().get(metric_id, ["-"])[0],
                    "failure_reason": _failure_reason(str(error.get("error", "")), source),
                    "detail": str(error.get("error", ""))[:180],
                    "impact": _impact_for_metric(metric_id),
                    "fallback_or_proxy": _fallback_or_proxy(source),
                    "next_action": _next_action(str(error.get("error", "")), source),
                }
            )
    for metric in metric_rows:
        if metric["sqlite_status"] in {"missing", "partial"}:
            source = _source_by_id(metric["source_id"])
            health = source_health_by_id.get(metric["source_id"], {})
            detail = (
                "No metric_values row for current collect run; previous data exists."
                if metric["sqlite_status"] == "partial"
                else "No metric_values row found."
            )
            rows.append(
                {
                    "metric_id": metric["metric_id"],
                    "source_id": metric["source_id"],
                    "radar_module": metric["radar_module"],
                    "failure_reason": _missing_failure_reason(source, metric["sqlite_status"]),
                    "detail": (
                        detail
                        if metric["sqlite_status"] == "partial"
                        else health.get("message") or detail
                    ),
                    "impact": metric["importance"],
                    "fallback_or_proxy": _fallback_or_proxy(source),
                    "next_action": _missing_metric_action(source, metric["metric_id"]),
                }
            )
    return _dedupe_failures(rows)


def _problem_rows(
    metric_rows: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    radar_result: dict[str, Any],
    extra_db_sources: list[str],
    run_mode_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    stale_count = sum(
        1 for row in metric_rows if row["collection_freshness_status"] == "stale"
    )
    expired_count = sum(
        1 for row in metric_rows if row["collection_freshness_status"] == "expired"
    )
    business_problem_rows = [
        row
        for row in metric_rows
        if row["business_recency_status"] in {"lagging", "outdated", "provider_stale_suspect"}
    ]
    lagging_count = len(business_problem_rows)
    missing_count = sum(1 for row in metric_rows if row["sqlite_status"] == "missing")
    partial_count = sum(1 for row in metric_rows if row["sqlite_status"] == "partial")
    conflict_count = sum(1 for row in metric_rows if row["conflict_status"] != "none")
    low_quality_modules = [
        item["module_id"]
        for item in radar_result.get("modules", [])
        if item.get("data_quality") != "high"
    ]
    if missing_count:
        rows.append(
            {
                "type": "missing_metrics",
                "scope": "P1/P2",
                "detail": f"{missing_count} 个指标没有写入 metric_values。",
                "impact": "high",
                "next_action": "优先修复高重要度缺失指标，然后复跑 P1-C22。",
            }
        )
    if partial_count:
        rows.append(
            {
                "type": "partial_current_run",
                "scope": "P1/P8",
                "detail": f"{partial_count} 个指标有历史值，但本轮没有产出。",
                "impact": "medium",
                "next_action": "检查本轮真实采集的解析器或公式输出。",
            }
        )
    if stale_count or expired_count:
        rows.append(
            {
                "type": "collection_freshness",
                "scope": "P1/P8",
                "detail": f"偏旧={stale_count}，过期={expired_count}。",
                "impact": "medium",
                "next_action": "检查采集频率、source health 事件与采集任务状态。",
            }
        )
    if lagging_count:
        sample = "; ".join(
            (
                f"{row['metric_id']}({row['source_id']}, "
                f"{row['business_recency_status']}, ts={row['source_ts'] or '-'})"
            )
            for row in business_problem_rows[:8]
        )
        rows.append(
            {
                "type": "business_recency",
                "scope": "P1/P2",
                "detail": (
                    f"{lagging_count} 个指标业务时间超过 provider 预期节奏，"
                    f"需核对源更新或 fallback。样例：{sample}"
                ),
                "impact": "low",
                "next_action": (
                    "核对 source_ts、provider 发布节奏和替代源；expected_lag 不进入问题清单。"
                ),
            }
        )
    if conflict_count:
        rows.append(
            {
                "type": "source_conflict",
                "scope": "P1/P2/P5",
                "detail": f"{conflict_count} 个指标存在多源数值冲突。",
                "impact": "medium",
                "next_action": (
                    "在 Evidence / Radar Detail 展示冲突，并继续校准主源优先级。"
                ),
            }
        )
    if failures:
        rows.append(
            {
                "type": "collection_failures",
                "scope": "P1",
                "detail": f"{len(failures)} 个指标-数据源组合采集失败或缺失。",
                "impact": "high",
                "next_action": "检查失败表，并拆分为 P1 数据源修复任务。",
            }
        )
    if low_quality_modules:
        rows.append(
            {
                "type": "radar_quality",
                "scope": "P2",
                "detail": ", ".join(low_quality_modules),
                "impact": "medium",
                "next_action": "检查这些雷达模块的缺口指标、代理指标和质量扣分原因。",
            }
        )
    if extra_db_sources:
        rows.append(
            {
                "type": "registry_drift",
                "scope": "P1/P8",
                "detail": f"SQLite 存在不在 SOURCE_CONFIGS 中的旧数据源：{extra_db_sources}。",
                "impact": "medium",
                "next_action": "执行 source registry reconciliation 或归档旧数据源。",
            }
        )
    current_run = run_mode_summary.get("current_run") or {}
    history = run_mode_summary.get("history") or {}
    if current_run and not current_run.get("current_run_live_only", True):
        rows.append(
            {
                "type": "run_mode_current_scope",
                "scope": "P1/P8/P3",
                "detail": (
                    "当前生产 collect run 非 live-only："
                    f"live={current_run.get('current_run_live_count', 0)}，"
                    f"mock={current_run.get('current_run_mock_count', 0)}，"
                    f"test={current_run.get('current_run_test_count', 0)}，"
                    f"unknown={current_run.get('current_run_unknown_count', 0)}。"
                ),
                "impact": "high",
                "next_action": "阻断生产链路，先隔离当前 run 的非 live 数据后再评分。",
            }
        )
    if history.get("historical_mixed"):
        rows.append(
            {
                "type": "run_mode_mixed_history",
                "scope": "P1/P8/P3",
                "detail": (
                    "历史库存在 live/mock/test/unknown 混用；当前生产窗口已按 live-only 过滤，"
                    "不污染当前 run。"
                ),
                "impact": "medium",
                "next_action": (
                    "保留为历史风险提示；History Replay 如需混合样本必须显式使用 run_mode=all。"
                ),
            }
        )
    if not rows and not run_mode_summary.get("production_blocker"):
        rows.append(
            {
                "type": "none",
                "scope": "global",
                "detail": "本次审计没有发现阻断问题。",
                "impact": "low",
                "next_action": "可以继续进入下一个 phase gate。",
            }
        )
    return rows


def _radar_metric_map() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for module in RADAR_MODULES:
        for rule in module.metrics:
            mapping[rule.metric_id].append(module.module_id)
    return dict(mapping)


def _full_collect_min_source_count() -> int:
    return max(1, int(len(SOURCE_CONFIGS) * 0.8))


def _latest_collect_run_id(
    db: Database,
    run_mode: str = "live",
    min_source_count: int | None = None,
) -> str | None:
    with db.session() as session:
        query = (
            select(
                schema.SourceRun.run_id,
                func.count(schema.SourceRun.source_id).label("source_count"),
            )
            .where(schema.SourceRun.mode == run_mode)
            .group_by(schema.SourceRun.run_id)
            .order_by(func.max(schema.SourceRun.started_at).desc())
            .limit(1)
        )
        if min_source_count is not None:
            query = query.having(func.count(schema.SourceRun.source_id) >= min_source_count)
        source_run = session.execute(query).first()
        if source_run:
            return str(source_run.run_id)
        return session.scalar(
            select(schema.DataQualitySnapshot.run_id)
            .where(schema.DataQualitySnapshot.run_id.like("collect-%"))
            .order_by(schema.DataQualitySnapshot.created_at.desc())
            .limit(1)
        )


def _latest_metric_by_key(
    db: Database,
    run_id: str | None = None,
    run_mode: str = "live",
) -> dict[tuple[str, str], schema.MetricValue]:
    with db.session() as session:
        query = select(schema.MetricValue)
        if run_id:
            query = query.where(schema.MetricValue.run_id == run_id)
        elif run_mode != "all":
            query = query.where(schema.MetricValue.run_mode == run_mode)
        rows = session.scalars(query.order_by(schema.MetricValue.ts.desc())).all()
    latest: dict[tuple[str, str], schema.MetricValue] = {}
    for row in rows:
        latest.setdefault((row.metric_id, row.source_id), row)
    return latest


def _table_counts(db: Database) -> dict[str, int]:
    tables = [
        schema.Source,
        schema.SourceRun,
        schema.RawObservation,
        schema.NormalizedMetric,
        schema.MetricValue,
        schema.SourceHealthEvent,
        schema.DataQualitySnapshot,
        schema.RadarOutput,
        schema.FeatureValue,
        schema.ModuleJsonOutput,
    ]
    with db.session() as session:
        return {
            table.__tablename__: session.scalar(select(func.count()).select_from(table)) or 0
            for table in tables
        }


def _extra_db_sources(db: Database) -> list[str]:
    registry_sources = {source.source_id for source in SOURCE_CONFIGS}
    with db.session() as session:
        rows = session.scalars(select(schema.Source)).all()
    db_sources = {
        row.source_id
        for row in rows
        if not bool((row.metadata_json or {}).get("archived"))
    }
    return sorted(db_sources - registry_sources)


def _source_by_id(source_id: str | None) -> Any | None:
    if source_id is None:
        return None
    return next((source for source in SOURCE_CONFIGS if source.source_id == source_id), None)


def _source_update_frequency(source: Any | None, metric_id: str) -> str:
    if source is None:
        return "未知"
    if "days_until" in metric_id:
        return "官方日历，按事件排期不定期更新"
    if source.method == "fred_api":
        return "FRED 序列，按指标日更/周更/月更"
    if source.method in {"rest", "websocket_sample"}:
        return "交易所近实时市场数据"
    if source.method == "community_csv":
        return "社区 CSV，通常日更"
    if source.method in {"rss_official_text_score", "official_calendar"}:
        return "官方发布或事件型更新"
    if source.method.startswith("playwright"):
        return "公开页面快照，频率取决于 provider 页面"
    return source.metadata.get("source_update_frequency", "provider 定义")


def _local_refresh_policy(source: Any | None) -> str:
    if source is None:
        return "默认"
    minutes = source.metadata.get("refresh_minutes")
    return f"{minutes} 分钟" if minutes else "默认 10 分钟"


def _source_form(source: Any | None, metric_id: str) -> str:
    if "days_until" in metric_id:
        return "event_countdown"
    if "proxy" in metric_id:
        return "proxy"
    if source and source.method in {"rss_official_text_score"}:
        return "llm_scored"
    if source and source.method in {"official_calendar", "html_parse_with_calendar_fallback"}:
        return "event_countdown"
    if metric_id in {
        "realized_price",
        "stablecoin_buying_power_proxy",
        "aggregate_macro_surprise",
        "macro_surprise_score",
        "fed_speech_risk",
        "fed_speech_content_risk",
        "fed_speech_scheduled_risk",
    }:
        return "self_calculated"
    return "raw_source"


def _importance(metric_id: str, radar_modules: list[str]) -> str:
    high = {
        "btc_price",
        "btc_1h_close",
        "dxy_proxy",
        "vix",
        "treasury_10y",
        "real_yield_10y",
        "fed_balance_sheet",
        "bank_reserves",
        "tga",
        "on_rrp",
        "etf_net_flow",
        "btc_funding_rate",
        "btc_open_interest",
        "liquidation_long_usd",
        "liquidation_short_usd",
        "exchange_balance_delta_1d_proxy",
        "stablecoin_supply",
        "mvrv_zscore",
        "realized_price",
        "sth_cost_basis",
        "lth_cost_basis",
        "macro_surprise_score",
        "fed_speech_risk",
        "cpi_days_until",
        "fomc_days_until",
        "pce_days_until",
        "nfp_days_until",
    }
    if metric_id in high:
        return "high"
    if radar_modules:
        return "medium"
    return "low"


def _arbitration_role(source_id: str, window: dict[str, Any] | None) -> str:
    if not window:
        return "missing"
    candidates = window.get("candidates", [])
    if not candidates:
        return "single_source" if window.get("source_id") == source_id else "not_selected"
    for candidate in candidates:
        if candidate["source_id"] == source_id:
            return candidate["role"]
    return "not_candidate"


def _conflict_status(conflict: dict[str, Any] | None) -> str:
    if not conflict or not conflict.get("detected"):
        return "none"
    severities = [item["severity"] for item in conflict.get("items", [])]
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"


def _metric_notes(
    metric_id: str,
    window: dict[str, Any] | None,
    source_window: dict[str, Any] | None,
) -> str:
    notes: list[str] = []
    if window and window.get("selected_reason"):
        notes.append(_zh_note(str(window["selected_reason"])))
    if source_window is None:
        notes.append("该数据源指标缺失")
    if "proxy" in metric_id:
        notes.append("代理指标，不按精确指标处理")
    return "; ".join(notes)


def _failure_reason(error: str, source: Any | None) -> str:
    text = error.lower()
    if "api key" in text or "unauthorized" in text or "401" in text:
        return "missing_api_key"
    if "login" in text:
        return "login_required"
    if "captcha" in text or "bot" in text or "403" in text:
        return "anti_bot_or_captcha"
    if "429" in text or "rate" in text:
        return "rate_limited"
    if "parse" in text or "selector" in text:
        return "parse_failed"
    if source and source.method.startswith("playwright"):
        return "parse_failed"
    return "source_unavailable"


def _next_action(error: str, source: Any | None) -> str:
    reason = _failure_reason(error, source)
    return {
        "missing_api_key": "Add provider key in .env or Settings.",
        "login_required": "Refresh persistent browser profile and rerun.",
        "anti_bot_or_captcha": "Use fallback source or manual provider session.",
        "rate_limited": "Back off cadence and add rate-limit state.",
        "parse_failed": "Update parser selector or network extraction rule.",
        "source_unavailable": "Retry later and verify provider status.",
    }.get(reason, "Investigate source failure.")


def _missing_metric_action(source: Any | None, metric_id: str) -> str:
    if "proxy" in metric_id:
        return "Verify proxy formula and label it clearly in Radar/Evidence."
    if source and source.fallback_source_id:
        return f"Check fallback source {source.fallback_source_id}."
    if source and source.method.startswith("playwright"):
        return "Run visible Playwright once, check page/login/selector."
    return "Check source implementation and parser output."


def _missing_failure_reason(source: Any | None, sqlite_status: str) -> str:
    if sqlite_status == "partial":
        if source and ("parse" in source.method or source.method.startswith("playwright")):
            return "parse_failed"
        return "not_implemented"
    return "not_implemented" if source else "source_unavailable"


def _fallback_or_proxy(source: Any | None) -> str:
    if source and source.fallback_source_id:
        return str(source.fallback_source_id)
    return "-"


def _impact_for_metric(metric_id: str) -> str:
    return _importance(metric_id, _radar_metric_map().get(metric_id, []))


def _dedupe_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = (row["metric_id"], row["source_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _chain_conclusion(context: dict[str, Any]) -> str:
    if context["failures"] or context["problems"]:
        return (
            "链路已执行并生成可审计结果，但仍存在失败/缺失/质量问题。"
            "需要按问题清单拆分修复后重新跑 P1-C22。"
        )
    return "链路完整打通，当前未发现阻断问题。"


def _html_report(context: dict[str, Any]) -> str:
    collection = context["collection_result"] or {}
    data_quality = collection.get("data_quality", {})
    payload = data_quality.get("payload", {})
    business_recency_counts = _business_recency_counts_from_metric_rows(
        context["metric_rows"]
    )
    radar_rows = [
        [
            item["module_id"],
            item["signal"],
            item["strength"],
            item["confidence"],
            item["data_quality"],
        ]
        for item in context["radar_result"].get("modules", [])
    ]
    metric_headers = [
        "metric_id",
        "display_name",
        "source_id",
        "source_group",
        "radar_module",
        "source_update_frequency",
        "source_form",
        "quality_score",
        "collection_freshness_status",
        "business_recency_status",
        "freshness_policy",
        "importance",
        "arbitration_role",
        "conflict_status",
        "sqlite_status",
        "radar_consumed",
        "notes",
    ]
    failure_headers = [
        "metric_id",
        "source_id",
        "radar_module",
        "failure_reason",
        "detail",
        "impact",
        "fallback_or_proxy",
        "next_action",
    ]
    problem_headers = ["type", "scope", "detail", "impact", "next_action"]
    problem_table = _html_table(
        problem_headers,
        [[row.get(h, "") for h in problem_headers] for row in context["problems"]],
    )
    failure_table = _html_table(
        failure_headers,
        [[row.get(h, "") for h in failure_headers] for row in context["failures"]],
    )
    radar_table = _html_table(
        ["module_id", "signal", "strength", "confidence", "data_quality"],
        radar_rows,
    )
    sqlite_table = _html_table(
        ["table", "count"],
        [[key, value] for key, value in context["table_counts"].items()],
    )
    metric_table = _html_table(
        metric_headers,
        [[row.get(h, "") for h in metric_headers] for row in context["metric_rows"]],
    )
    problem_note = "这里列出仍需关注的问题；非阻断项会保留，方便后续任务继续跟踪。"
    metric_note = (
        f"共 {len(context['metric_rows'])} 个指标。"
        "采集新鲜度和业务时间状态已分开展示。"
    )
    run_mode_table = _html_table(
        ["type", "count"],
        [
            ["current_run_id", context["run_mode_summary"].get("current_run_id") or "-"],
            [
                "current_run_live_only",
                context["run_mode_summary"].get("current_run_live_only", False),
            ],
            [
                "current_run_live_count",
                context["run_mode_summary"].get("current_run_live_count", 0),
            ],
            [
                "current_run_mock_count",
                context["run_mode_summary"].get("current_run_mock_count", 0),
            ],
            [
                "current_run_test_count",
                context["run_mode_summary"].get("current_run_test_count", 0),
            ],
            [
                "current_run_unknown_count",
                context["run_mode_summary"].get("current_run_unknown_count", 0),
            ],
            ["default_query_scope", context["run_mode_summary"].get("default_query_scope")],
            ["live_metric_values", context["run_mode_summary"].get("live_metric_values", 0)],
            ["mock_metric_values", context["run_mode_summary"].get("mock_metric_values", 0)],
            ["test_metric_values", context["run_mode_summary"].get("test_metric_values", 0)],
            [
                "unknown_metric_values",
                context["run_mode_summary"].get("unknown_metric_values", 0),
            ],
            ["mixed_metric_ids", len(context["run_mode_summary"].get("mixed_metric_ids", []))],
        ],
    )
    fallback_table = _html_table(
        ["type", "count"],
        [
            ["fallback_event_count", context["fallback_summary"].get("fallback_event_count", 0)],
            ["warning_source_count", context["fallback_summary"].get("warning_source_count", 0)],
            [
                "fredgraph_csv_fallback_count",
                context["fallback_summary"].get("fredgraph_csv_fallback_count", 0),
            ],
            [
                "fred_batch_group_count",
                context["fallback_summary"].get("fred_batch_group_count", 0),
            ],
            [
                "fallback_sources",
                ", ".join(context["fallback_summary"].get("fallback_sources", [])) or "-",
            ],
            [
                "http_403_sources",
                ", ".join(context["fallback_summary"].get("http_403_sources", [])) or "-",
            ],
        ],
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>P1-C22 真实数据全链路验收报告</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #071019;
      --panel: #0d1b26;
      --panel-2: #102333;
      --line: #284257;
      --text: #d8e7f0;
      --muted: #8aa3b5;
      --green: #40d6a3;
      --yellow: #f5b84b;
      --red: #ff675f;
      --cyan: #54c7ec;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      padding: 18px 24px;
      background: rgba(7, 16, 25, 0.94);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(10px);
    }}
    h1 {{ margin: 0 0 6px; font-size: 22px; }}
    h2 {{ margin: 26px 0 12px; font-size: 18px; }}
    main {{ padding: 18px 24px 40px; }}
    .muted {{ color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 16px 0;
    }}
    .card {{
      background: linear-gradient(180deg, var(--panel-2), var(--panel));
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .card .label {{ color: var(--muted); font-size: 12px; }}
    .card .value {{ margin-top: 8px; font-size: 22px; font-weight: 700; }}
    .ok {{ color: var(--green); }}
    .warn {{ color: var(--yellow); }}
    .bad {{ color: var(--red); }}
    .info {{ color: var(--cyan); }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      margin-bottom: 18px;
      max-height: 720px;
    }}
    table {{ border-collapse: collapse; width: 100%; min-width: 980px; }}
    th, td {{
      border-bottom: 1px solid rgba(40, 66, 87, 0.75);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      white-space: nowrap;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #102333;
      color: #cfe4f2;
      z-index: 1;
    }}
    td:last-child {{ white-space: normal; min-width: 260px; }}
    .pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: rgba(84, 199, 236, 0.12);
      border: 1px solid rgba(84, 199, 236, 0.32);
    }}
    .section-note {{
      color: var(--muted);
      margin: -6px 0 10px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>P1-C22 真实数据全链路验收报告</h1>
    <div class="muted">
      采集 run_id：{_e(context["collect_run_id"] or "未执行")} ·
      P1 诊断 Radar run_id：{_e(context["radar_run_id"] or "未执行")} ·
      完成时间：{_e(context["completed_at"].isoformat())}
    </div>
  </header>
  <main>
    <section class="grid">
      {_html_card("数据源数量", len(context["sources"]))}
      {_html_card("指标数量", len(context["metric_rows"]))}
      {_html_card("失败/缺失", len(context["failures"]), "bad" if context["failures"] else "ok")}
      {_html_card("问题数量", len(context["problems"]))}
      {_html_card("数据质量分", data_quality.get("score", "-"), "ok")}
      {_html_card("数据质量状态", _zh(data_quality.get("status", "-")), "ok")}
    </section>

    <section class="grid">
      {_html_card("采集新鲜度", _zh_counts(payload.get("freshness_counts", {})), "info")}
      {_html_card("业务时间状态", _zh_counts(business_recency_counts), "info")}
      {_html_card("已采集数据源", collection.get("collected", "-"))}
      {_html_card("采集错误数", len(collection.get("errors", [])) if collection else "-")}
    </section>

    <h2>当前问题清单</h2>
    <div class="section-note">{_e(problem_note)}</div>
    {problem_table}

    <h2>Run Mode 混用风险</h2>
    {run_mode_table}

    <h2>Fallback / 默认数据使用清单</h2>
    {fallback_table}

    <h2>失败/缺失数据</h2>
    {failure_table}

    <h2>Radar 消费结果</h2>
    {radar_table}

    <h2>SQLite 写入统计</h2>
    {sqlite_table}

    <h2>指标参数清单</h2>
    <div class="section-note">{_e(metric_note)}</div>
    {metric_table}
  </main>
</body>
</html>
"""


def _html_card(label: str, value: Any, tone: str = "") -> str:
    return (
        '<div class="card">'
        f'<div class="label">{_e(label)}</div>'
        f'<div class="value {tone}">{_e(value)}</div>'
        '</div>'
    )


def _html_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["-" for _ in headers]]
    head = "".join(f"<th>{_e(_label(header))}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = []
        for header, value in zip(headers, row, strict=False):
            rendered = _zh_for_field(header, value)
            if header in {
                "collection_freshness_status",
                "business_recency_status",
                "data_quality",
                "impact",
                "conflict_status",
                "sqlite_status",
            }:
                rendered = f'<span class="pill">{_e(rendered)}</span>'
            else:
                rendered = _e(rendered)
            cells.append(f"<td>{rendered}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


def _markdown_table(
    headers: list[str],
    rows: list[list[Any]],
    translate: bool = False,
) -> str:
    if not rows:
        rows = [["-" for _ in headers]]
    display_headers = [_label(header) if translate else header for header in headers]
    lines = [
        "| " + " | ".join(display_headers) + " |",
        "| " + " | ".join("---" for _ in display_headers) + " |",
    ]
    for row in rows:
        values = [
            _zh_for_field(header, value) if translate else value
            for header, value in zip(headers, row, strict=False)
        ]
        lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    return "\n".join(lines)


def _label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _zh(value: Any) -> str:
    if isinstance(value, dict):
        return _zh_counts(value)
    text = "" if value is None else str(value)
    return VALUE_LABELS.get(text, text)


def _zh_counts(values: dict[str, Any]) -> str:
    if not values:
        return "-"
    return "，".join(f"{_zh(key)}={value}" for key, value in values.items())


def _business_recency_counts_from_metric_rows(
    metric_rows: list[dict[str, Any]],
) -> dict[str, int]:
    counts = {status: 0 for status in BUSINESS_RECENCY_STATUS_ORDER}
    for row in metric_rows:
        status = str(row.get("business_recency_status") or "unknown")
        if status not in counts:
            counts["unknown"] += 1
            continue
        counts[status] += 1
    return counts


def _zh_for_field(field: str, value: Any) -> str:
    if field == "notes":
        return _zh_note(str(value))
    if field in {
        "signal",
        "data_quality",
        "impact",
        "importance",
        "collection_freshness_status",
        "business_recency_status",
        "arbitration_role",
        "conflict_status",
        "sqlite_status",
        "radar_consumed",
        "type",
        "source_form",
        "higher_is",
    }:
        return _zh(value)
    return "" if value is None else str(value)


def _zh_note(note: str) -> str:
    replacements = {
        "freshness=": "采集新鲜度=",
        "business_recency=": "业务时间状态=",
        "effective_quality=": "有效质量分=",
        "priority=": "优先级=",
        "policy=": "策略=",
        "fresh": "新鲜",
        "stale": "偏旧",
        "expired": "过期",
        "current": "正常",
        "lagging": "滞后",
        "outdated": "过旧",
        "provider_stale_suspect": "provider 旧快照疑似",
        "proxy metric; do not treat as exact": "代理指标，不按精确指标处理",
        "source metric missing": "该数据源指标缺失",
    }
    text = note
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")[:240]


def _e(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _fmt_float(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _write_report(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _audit_run_mode_summary(db: Database, current_run_id: str | None = None) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        rows = session.execute(
            select(schema.MetricValue.run_mode, func.count()).group_by(schema.MetricValue.run_mode)
        ).all()
        counts = {str(mode or "unknown"): count for mode, count in rows}
        current_rows = []
        if current_run_id:
            current_rows = session.execute(
                select(schema.MetricValue.run_mode, func.count())
                .where(schema.MetricValue.run_id == current_run_id)
                .group_by(schema.MetricValue.run_mode)
            ).all()
        mixed_rows = session.execute(
            select(
                schema.MetricValue.metric_id,
                func.count(func.distinct(schema.MetricValue.run_mode)),
            )
            .group_by(schema.MetricValue.metric_id)
            .having(func.count(func.distinct(schema.MetricValue.run_mode)) > 1)
        ).all()
    current_counts = {str(mode or "unknown"): count for mode, count in current_rows}
    current_non_live_count = (
        current_counts.get("mock", 0)
        + current_counts.get("test", 0)
        + current_counts.get("unknown", 0)
    )
    historical_mixed = bool(
        mixed_rows
        or counts.get("mock", 0)
        or counts.get("test", 0)
        or counts.get("unknown", 0)
    )
    return {
        "live_metric_values": counts.get("live", 0),
        "mock_metric_values": counts.get("mock", 0),
        "test_metric_values": counts.get("test", 0),
        "unknown_metric_values": counts.get("unknown", 0),
        "mixed_metric_ids": [metric_id for metric_id, _ in mixed_rows],
        "current_run_id": current_run_id,
        "current_run_live_count": current_counts.get("live", 0),
        "current_run_mock_count": current_counts.get("mock", 0),
        "current_run_test_count": current_counts.get("test", 0),
        "current_run_unknown_count": current_counts.get("unknown", 0),
        "current_run_live_only": bool(current_run_id) and current_non_live_count == 0,
        "historical_mixed": historical_mixed,
        "production_blocker": current_non_live_count > 0,
        "current_run": {
            "current_run_id": current_run_id,
            "current_run_live_count": current_counts.get("live", 0),
            "current_run_mock_count": current_counts.get("mock", 0),
            "current_run_test_count": current_counts.get("test", 0),
            "current_run_unknown_count": current_counts.get("unknown", 0),
            "current_run_live_only": bool(current_run_id) and current_non_live_count == 0,
            "status": "passed" if current_non_live_count == 0 else "failed",
        },
        "history": {
            "live_metric_values": counts.get("live", 0),
            "mock_metric_values": counts.get("mock", 0),
            "test_metric_values": counts.get("test", 0),
            "unknown_metric_values": counts.get("unknown", 0),
            "mixed_metric_ids": [metric_id for metric_id, _ in mixed_rows],
            "mixed_metric_id_count": len(mixed_rows),
            "historical_mixed": historical_mixed,
            "status": "warning" if historical_mixed else "passed",
        },
        "default_query_scope": "live_only",
    }


def _audit_fallback_summary(
    collection_result: dict[str, Any] | None,
    db: Database,
) -> dict[str, Any]:
    warnings = collection_result.get("warnings", []) if collection_result else []
    run_id = collection_result.get("run_id") if collection_result else None
    db.init_schema()
    with db.session() as session:
        fallback_count = session.scalar(select(func.count()).select_from(schema.FallbackEvent)) or 0
        warning_rows = session.scalars(
            select(schema.SourceHealthEvent)
            .where(schema.SourceHealthEvent.status.in_(["warning", "error", "stale"]))
            .order_by(schema.SourceHealthEvent.created_at.desc())
            .limit(100)
        ).all()
        raw_rows = []
        if run_id:
            raw_rows = session.scalars(
                select(schema.RawObservation).where(schema.RawObservation.run_id == run_id)
            ).all()
    fallback_sources = sorted(
        {
            row.source_id
            for row in raw_rows
            if isinstance(row.raw_payload, dict)
            and (
                row.raw_payload.get("fallback_used")
                or row.raw_payload.get("fallback_provider")
            )
        }
    )
    fredgraph_count = sum(
        1
        for row in raw_rows
        if isinstance(row.raw_payload, dict)
        and row.raw_payload.get("fallback_provider") == "fredgraph_csv"
    )
    fred_batch_groups = sorted(
        {
            str(row.raw_payload.get("batch_group"))
            for row in raw_rows
            if isinstance(row.raw_payload, dict)
            and row.source_id.startswith("fred-")
            and row.raw_payload.get("batch_group")
        }
    )
    http_403_sources = sorted(
        {
            item["source_id"]
            for item in warnings
            if "403" in str(item.get("message", ""))
            or "forbidden" in str(item.get("message", "")).lower()
        }
        | {
            row.source_id
            for row in warning_rows
            if "403" in (row.message or "") or "forbidden" in (row.message or "").lower()
        }
    )
    return {
        "fallback_event_count": fallback_count,
        "warning_source_count": len(
            {row.source_id for row in warning_rows}
            | {item["source_id"] for item in warnings}
        ),
        "http_403_sources": http_403_sources,
        "fallback_sources": fallback_sources,
        "fredgraph_csv_fallback_count": fredgraph_count,
        "fred_batch_group_count": len(fred_batch_groups),
        "fred_batch_groups": fred_batch_groups,
        "warnings": warnings,
    }


def _production_blocker_label(summary: dict[str, Any]) -> str:
    if summary.get("production_blocker"):
        return "当前 run 存在，需要先隔离"
    if summary.get("historical_mixed"):
        return "仅历史风险，不污染当前 run"
    return "未发现"
