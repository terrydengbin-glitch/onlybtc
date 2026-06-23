from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.audit.p1_c22 import run_p1_c22_audit
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.registry import METRIC_DEFINITIONS
from onlybtc.sources.service import collect_sources

P2_HTML_FILENAME = "p2-radar-quality-report.html"


async def run_p2_full_chain_audit(
    collect_live: bool = True,
    run_mode: str = "live",
    db: Database = database,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    collection_result = (
        await collect_sources(mode=SourceMode.LIVE, db=db) if collect_live else None
    )
    collect_run_id = collection_result.get("run_id") if collection_result else None
    p1_result = await run_p1_c22_audit(
        collect_live=collect_live,
        collection_result=collection_result,
        run_diagnostic_radar=False,
        db=db,
    )
    radar_result = analyze_radars(
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        historical_fallback=True,
        db=db,
    )
    context = _build_p2_context(
        started_at=started_at,
        p1_result=p1_result,
        radar_result=radar_result,
        run_mode=run_mode,
        collect_run_id=collect_run_id,
        db=db,
    )
    report_dir = paths.project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = _write_report(report_dir / P2_HTML_FILENAME, _html_report(context))
    return {
        "status": "completed",
        "p1_c22_html_path": _p1_html_path(p1_result),
        "p2_radar_run_id": radar_result["run_id"],
        "collect_run_id": collect_run_id,
        "p2_html_path": str(html_path),
        "module_count": len(context["module_rows"]),
        "low_quality_modules": [
            row["module_id"] for row in context["module_rows"] if row["data_quality"] != "high"
        ],
        "missing_metric_count": sum(len(row["missing_metrics"]) for row in context["module_rows"]),
        "provider_required_count": sum(
            len(row["provider_required_metrics"]) for row in context["module_rows"]
        ),
        "uncovered_metric_count": context["coverage"]["uncovered_metric_count"],
        "run_scope": context["run_scope"],
        "sqlite_checks": context["sqlite_checks"],
    }


def run_p2_full_chain_audit_sync(
    collect_live: bool = True,
    run_mode: str = "live",
) -> dict[str, Any]:
    return asyncio.run(run_p2_full_chain_audit(collect_live=collect_live, run_mode=run_mode))


def _build_p2_context(
    started_at: datetime,
    p1_result: dict[str, Any],
    radar_result: dict[str, Any],
    run_mode: str,
    collect_run_id: str | None,
    db: Database,
) -> dict[str, Any]:
    run_id = str(radar_result["run_id"])
    with db.session() as session:
        module_outputs = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.run_id == run_id)
            .order_by(schema.ModuleJsonOutput.module_id)
        ).all()
        radar_count = session.scalar(
            select(func.count())
            .select_from(schema.RadarOutput)
            .where(schema.RadarOutput.run_id == run_id)
        ) or 0
        module_json_count = len(module_outputs)
        feature_count = session.scalar(
            select(func.count())
            .select_from(schema.FeatureValue)
            .where(schema.FeatureValue.run_id == run_id)
        ) or 0
    module_rows = [_module_row(output.payload) for output in module_outputs]
    expected_feature_count = sum(len(module.metrics) for module in RADAR_MODULES)
    coverage = _radar_metric_coverage()
    run_scope = _run_scope_summary(module_rows)
    return {
        "started_at": started_at,
        "completed_at": datetime.now(UTC),
        "run_mode": run_mode,
        "collect_run_id": collect_run_id,
        "p1_result": p1_result,
        "p1_html_path": _p1_html_path(p1_result),
        "radar_result": radar_result,
        "module_rows": module_rows,
        "coverage": coverage,
        "run_scope": run_scope,
        "sqlite_checks": {
            "radar_outputs": radar_count,
            "module_json_outputs": module_json_count,
            "feature_values": feature_count,
            "expected_modules": len(RADAR_MODULES),
            "expected_features": expected_feature_count,
            "radar_outputs_ok": radar_count == len(RADAR_MODULES),
            "module_json_outputs_ok": module_json_count == len(RADAR_MODULES),
            "feature_values_ok": feature_count >= expected_feature_count,
        },
    }


def _module_row(payload: dict[str, Any]) -> dict[str, Any]:
    quality = payload.get("evidence_summary", {}).get("quality_explanation", {})
    invalidation = payload.get("invalidation_signals", {})
    features = payload.get("features", [])
    run_scope_counts = _feature_scope_counts(features)
    return {
        "module_id": payload.get("module_id", ""),
        "signal": payload.get("signal", ""),
        "strength": payload.get("strength", ""),
        "confidence": payload.get("confidence", ""),
        "data_quality": payload.get("data_quality", ""),
        "coverage_score": quality.get("coverage_score", ""),
        "raw_coverage_score": quality.get("raw_coverage_score", ""),
        "overall_score": quality.get("overall_score", ""),
        "source_quality_score": quality.get("source_quality_score", ""),
        "main_discount_reasons": quality.get("main_discount_reasons", []),
        "missing_metrics": invalidation.get("missing_metrics", []),
        "provider_required_metrics": invalidation.get("provider_required_metrics", []),
        "stale_metrics": invalidation.get("stale_metrics", []),
        "expired_metrics": invalidation.get("expired_metrics", []),
        "business_lagging_metrics": invalidation.get("business_lagging_metrics", []),
        "feature_count": len(features),
        "current_run_feature_count": run_scope_counts["current_run"],
        "historical_fallback_feature_count": run_scope_counts["historical_fallback"],
        "provider_required_feature_count": run_scope_counts["provider_required"],
        "missing_feature_count": run_scope_counts["missing"],
        "same_run_coverage_score": quality.get("same_run_coverage_score", ""),
        "features": features,
    }


def _html_report(context: dict[str, Any]) -> str:
    module_headers = [
        "module_id",
        "signal",
        "strength",
        "confidence",
        "data_quality",
        "overall_score",
        "coverage_score",
        "raw_coverage_score",
        "source_quality_score",
        "same_run_coverage_score",
        "current_run_feature_count",
        "historical_fallback_feature_count",
        "missing_metrics",
        "provider_required_metrics",
        "main_discount_reasons",
    ]
    feature_headers = [
        "module_id",
        "metric_id",
        "role",
        "available",
        "source_id",
        "quality_score",
        "horizon_tags",
        "module_weight",
        "duplicate_group_id",
        "duplicate_policy",
        "duplicate_group_max_weight",
        "evidence_tier",
        "affects_signal",
        "affects_confidence",
        "affects_risk_flags",
        "quality_blocking",
        "collection_freshness_status",
        "business_recency_status",
        "source_run_id",
        "feature_run_scope",
        "current_run_has_value",
        "fallback_age_seconds",
        "fallback_reason",
    ]
    feature_rows = [
        {
            "module_id": module["module_id"],
            **feature,
        }
        for module in context["module_rows"]
        for feature in module["features"]
    ]
    checks = context["sqlite_checks"]
    coverage = context["coverage"]
    run_scope = context["run_scope"]
    status_class = "ok" if all(
        checks[key]
        for key in ("radar_outputs_ok", "module_json_outputs_ok", "feature_values_ok")
    ) and coverage["uncovered_metric_count"] == 0 else "warn"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>P2 Radar Quality Report</title>
  <style>
    body {{ margin: 0; background: #08131c; color: #dbeafe; font-family: Arial, sans-serif; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ color: #f8fafc; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #1e3a4f; background: #0d1f2d; border-radius: 8px; padding: 14px; }}
    .value {{ font-size: 24px; font-weight: 700; color: #67e8f9; }}
    .ok {{ color: #86efac; }}
    .warn {{ color: #fde68a; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
    th, td {{
      border-bottom: 1px solid #1e3a4f;
      padding: 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: #bae6fd; background: #0b1a26; position: sticky; top: 0; }}
    code {{ color: #fef3c7; }}
  </style>
</head>
<body>
<main>
  <h1>P2 Radar Quality Report</h1>
  <p>
    Started: {escape(str(context["started_at"].isoformat()))} ·
    Completed: {escape(str(context["completed_at"].isoformat()))} ·
    Run mode: <code>{escape(str(context["run_mode"]))}</code>
  </p>
  <div class="grid">
    {_card("P1-C22 HTML", context["p1_html_path"] or "-")}
    {_card("Collect run", context["collect_run_id"] or "-")}
    {_card("P2 radar run", context["radar_result"]["run_id"])}
    {_card("Modules", str(len(context["module_rows"])))}
    {_card(
        "Uncovered metrics",
        str(coverage["uncovered_metric_count"]),
        "ok" if coverage["uncovered_metric_count"] == 0 else "warn",
    )}
    {_card("SQLite checks", "PASS" if status_class == "ok" else "WARN", status_class)}
  </div>

  <h2>Metric Coverage</h2>
  {_table(["check", "value"], _coverage_check_rows(coverage))}

  <h2>Run Contract</h2>
  {_table(["check", "value"], _run_scope_check_rows(run_scope))}

  <h2>Uncovered Metric Definitions</h2>
  {_table(["metric_id", "source_id", "group_name", "higher_is"], coverage["uncovered_metric_rows"])}

  <h2>Radar Planned / Provider Required</h2>
  {_table(["metric_id", "modules", "evidence_tier"], coverage["radar_without_definition_rows"])}

  <h2>SQLite Contract</h2>
  {_table(["check", "value"], _sqlite_check_rows(checks))}

  <h2>Module Quality</h2>
  {_table(module_headers, context["module_rows"])}

  <h2>Feature Quality</h2>
  {_table(feature_headers, feature_rows)}
</main>
</body>
</html>
"""


def _card(label: str, value: str, css_class: str = "") -> str:
    return (
        '<div class="card">'
        f"<div>{escape(label)}</div>"
        f'<div class="value {escape(css_class)}">{escape(str(value))}</div>'
        "</div>"
    )


def _sqlite_check_rows(checks: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"check": key, "value": value} for key, value in checks.items()]


def _coverage_check_rows(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"check": key, "value": value}
        for key, value in coverage.items()
        if key.endswith("_count")
    ]


def _run_scope_check_rows(run_scope: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"check": key, "value": value} for key, value in run_scope.items()]


def _run_scope_summary(module_rows: list[dict[str, Any]]) -> dict[str, Any]:
    features = [feature for module in module_rows for feature in module["features"]]
    counts = _feature_scope_counts(features)
    quality_relevant = [
        feature for feature in features if feature.get("quality_blocking")
    ]
    current_quality = [
        feature
        for feature in quality_relevant
        if feature.get("feature_run_scope") == "current_run"
    ]
    same_run_score = (
        len(current_quality) / len(quality_relevant)
        if quality_relevant
        else 0.0
    )
    return {
        "current_run_feature_count": counts["current_run"],
        "historical_fallback_feature_count": counts["historical_fallback"],
        "provider_required_feature_count": counts["provider_required"],
        "missing_feature_count": counts["missing"],
        "same_run_coverage_score": round(same_run_score, 4),
        "historical_fallback_risk": counts["historical_fallback"] > 0,
    }


def _feature_scope_counts(features: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "current_run": 0,
        "historical_fallback": 0,
        "provider_required": 0,
        "missing": 0,
    }
    for feature in features:
        scope = str(feature.get("feature_run_scope") or "missing")
        if scope in counts:
            counts[scope] += 1
        elif scope == "unspecified_history":
            counts["historical_fallback"] += 1
        else:
            counts["missing"] += 1
    return counts


def _radar_metric_coverage() -> dict[str, Any]:
    metric_definitions = {metric.metric_id: metric for metric in METRIC_DEFINITIONS}
    radar_modules_by_metric: dict[str, list[str]] = {}
    for module in RADAR_MODULES:
        for rule in module.metrics:
            radar_modules_by_metric.setdefault(rule.metric_id, []).append(module.module_id)
    radar_metrics = set(radar_modules_by_metric)
    uncovered = sorted(set(metric_definitions) - radar_metrics)
    radar_without_definition = sorted(radar_metrics - set(metric_definitions))
    provider_required = {"whale_flow", "miner_flow", "hibor", "regulatory_event_score"}
    return {
        "metric_definitions_count": len(metric_definitions),
        "radar_metric_slot_count": sum(len(module.metrics) for module in RADAR_MODULES),
        "radar_unique_metric_count": len(radar_metrics),
        "radar_covered_metric_count": len(set(metric_definitions) & radar_metrics),
        "uncovered_metric_count": len(uncovered),
        "radar_without_definition_count": len(radar_without_definition),
        "uncovered_metric_rows": [
            {
                "metric_id": metric_id,
                "source_id": metric_definitions[metric_id].source_id,
                "group_name": metric_definitions[metric_id].group_name,
                "higher_is": metric_definitions[metric_id].higher_is,
            }
            for metric_id in uncovered
        ],
        "radar_without_definition_rows": [
            {
                "metric_id": metric_id,
                "modules": radar_modules_by_metric[metric_id],
                "evidence_tier": "provider_required"
                if metric_id in provider_required
                else "planned",
            }
            for metric_id in radar_without_definition
        ],
    }


def _table(headers: list[str], rows: list[dict[str, Any]]) -> str:
    if not rows:
        rows = [{header: "-" for header in headers}]
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>"
        + "".join(f"<td>{_format_cell(row.get(header, ''))}</td>" for header in headers)
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _format_cell(value: Any) -> str:
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value) or "-")
    if isinstance(value, dict):
        return escape(str(value))
    return escape(str(value))


def _p1_html_path(p1_result: dict[str, Any]) -> str:
    for key, value in p1_result.items():
        if "HTML" in str(key) and isinstance(value, str) and value.endswith(".html"):
            return value
    report_paths = next(
        (value for value in p1_result.values() if isinstance(value, dict)),
        {},
    )
    html_path = report_paths.get("html") if isinstance(report_paths, dict) else None
    return str(html_path or "")


def _write_report(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path
