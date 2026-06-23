from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.algorithms.p3 import EVENT_MODULE_ID
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.sources.registry import METRIC_DEFINITIONS

P4_RADAR_COVERAGE_HTML_FILENAME = "p4-radar-coverage-matrix.html"

ANALYST_MODULES: dict[str, tuple[str, ...]] = {
    "macro_event_analyst": (
        "macro_radar",
        "treasury_credit",
        "asia_risk",
        "event_policy",
    ),
    "liquidity_flow_analyst": (
        "dollar_liquidity",
        "fund_flow",
        "btc_adoption",
    ),
    "leverage_microstructure_analyst": (
        "derivatives_crowding",
        "trade_structure_flow",
        "options_volatility",
    ),
    "onchain_market_structure_analyst": (
        "onchain_valuation",
        "crypto_breadth",
        "btc_total_state",
        "kline_orderflow",
    ),
}


def run_p4_radar_coverage_audit(
    radar_run_id: str | None = None,
    p3_run_id: str | None = None,
    pack_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    radar_run_id = radar_run_id or _latest_complete_radar_run_id(db)
    if radar_run_id is None:
        raise RuntimeError("No complete P2 Radar run found")
    p3_run_id = p3_run_id or _latest_p3_event_run_id(db)
    context = _build_context(radar_run_id, p3_run_id, pack_id, db)
    report_dir = paths.project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = _write_report(report_dir / P4_RADAR_COVERAGE_HTML_FILENAME, _html_report(context))
    return {
        "status": "completed",
        "html_path": str(html_path),
        "radar_run_id": radar_run_id,
        "p3_run_id": p3_run_id,
        "pack_id": context["pack_id"],
        "radar_modules_consumed_count": context["summary"]["radar_modules_consumed_count"],
        "radar_module_total": context["summary"]["radar_module_total"],
        "radar_feature_items_expected": context["summary"]["radar_feature_items_expected"],
        "radar_feature_items_available": context["summary"]["radar_feature_items_available"],
        "signed_event_metrics_consumed_count": context["summary"][
            "signed_event_metrics_consumed_count"
        ],
        "uncovered_metric_count": context["summary"]["uncovered_metric_count"],
        "evidence_pack_status": context["summary"]["evidence_pack_status"],
        "evidence_pack_missing_feature_count": context["summary"][
            "evidence_pack_missing_feature_count"
        ],
    }


def _build_context(
    radar_run_id: str,
    p3_run_id: str | None,
    pack_id: str | None,
    db: Database,
) -> dict[str, Any]:
    module_rows = _module_outputs(db, radar_run_id)
    evidence_items = _evidence_items(db, pack_id)
    feature_evidence_keys = _feature_evidence_keys(evidence_items)
    source_layers = _evidence_source_layers(evidence_items)
    matrix_rows = []
    feature_rows = []
    module_ids = {module.module_id for module in RADAR_MODULES}
    module_to_analyst = _module_to_analyst()
    radar_metric_ids: set[str] = set()
    available_feature_count = 0
    expected_feature_count = 0
    missing_module_ids = sorted(module_ids - set(module_rows))

    for module in RADAR_MODULES:
        payload = module_rows.get(module.module_id, {})
        features = payload.get("features") or []
        features_by_metric = {
            str(item.get("metric_id")): item
            for item in features
            if isinstance(item, dict) and item.get("metric_id")
        }
        expected_metrics = [rule.metric_id for rule in module.metrics]
        radar_metric_ids.update(expected_metrics)
        expected_feature_count += len(expected_metrics)
        available_feature_count += len(features_by_metric)
        missing_features = sorted(set(expected_metrics) - set(features_by_metric))
        provider_required = sorted(
            item["metric_id"]
            for item in features
            if isinstance(item, dict) and item.get("feature_run_scope") == "provider_required"
        )
        evidence_missing = [
            metric_id
            for metric_id in expected_metrics
            if (module.module_id, metric_id) not in feature_evidence_keys
        ]
        matrix_rows.append(
            {
                "analyst": module_to_analyst.get(module.module_id, "unassigned"),
                "module_id": module.module_id,
                "module_present": module.module_id in module_rows,
                "expected_features": len(expected_metrics),
                "module_json_features": len(features_by_metric),
                "missing_features": missing_features,
                "provider_required": provider_required,
                "evidence_pack_missing": evidence_missing,
                "signal": payload.get("signal", ""),
                "confidence": payload.get("confidence", ""),
                "data_quality": payload.get("data_quality", ""),
            }
        )
        for metric_id in expected_metrics:
            feature = features_by_metric.get(metric_id, {})
            feature_rows.append(
                {
                    "analyst": module_to_analyst.get(module.module_id, "unassigned"),
                    "module_id": module.module_id,
                    "metric_id": metric_id,
                    "available": feature.get("available", False),
                    "role": feature.get("role", ""),
                    "evidence_tier": feature.get("evidence_tier", ""),
                    "affects_signal": feature.get("affects_signal", ""),
                    "affects_confidence": feature.get("affects_confidence", ""),
                    "affects_risk_flags": feature.get("affects_risk_flags", ""),
                    "feature_run_scope": feature.get("feature_run_scope", ""),
                    "source_id": feature.get("source_id", ""),
                    "source_run_id": feature.get("source_run_id", ""),
                    "in_evidence_pack": (module.module_id, metric_id) in feature_evidence_keys,
                }
            )

    metric_definitions = {metric.metric_id for metric in METRIC_DEFINITIONS}
    uncovered_metrics = sorted(metric_definitions - radar_metric_ids)
    signed_event_metrics = {
        "cpi_signed_days",
        "fomc_signed_days",
        "pce_signed_days",
        "nfp_signed_days",
    }
    p3_event_rows = _p3_event_rows(db, p3_run_id)
    summary = {
        "radar_run_id": radar_run_id,
        "p3_run_id": p3_run_id,
        "pack_id": pack_id or "",
        "radar_modules_consumed_count": len(module_rows),
        "radar_module_total": len(RADAR_MODULES),
        "missing_radar_modules": missing_module_ids,
        "radar_feature_items_expected": expected_feature_count,
        "radar_feature_items_available": available_feature_count,
        "metric_definitions_count": len(metric_definitions),
        "radar_unique_metric_count": len(radar_metric_ids),
        "uncovered_metric_count": len(uncovered_metrics),
        "uncovered_metrics": uncovered_metrics,
        "signed_event_metrics_consumed_count": len(signed_event_metrics & radar_metric_ids),
        "signed_event_metrics_total": len(signed_event_metrics),
        "p3_event_window_rows": len(p3_event_rows),
        "evidence_pack_status": "found" if evidence_items else "not_generated",
        "evidence_pack_item_count": len(evidence_items),
        "evidence_source_layers": source_layers,
        "analyst_history_evidence_count": source_layers.get("analyst_history", 0),
        "evidence_pack_missing_feature_count": sum(
            len(row["evidence_pack_missing"]) for row in matrix_rows
        ),
    }
    return {
        "generated_at": datetime.now(UTC),
        "summary": summary,
        "pack_id": pack_id,
        "matrix_rows": matrix_rows,
        "feature_rows": feature_rows,
        "p3_event_rows": p3_event_rows,
    }


def _latest_complete_radar_run_id(db: Database) -> str | None:
    with db.session() as session:
        rows = session.execute(
            select(
                schema.ModuleJsonOutput.run_id,
                func.count(func.distinct(schema.ModuleJsonOutput.module_id)).label("module_count"),
                func.max(schema.ModuleJsonOutput.created_at).label("latest_at"),
            )
            .group_by(schema.ModuleJsonOutput.run_id)
            .order_by(func.max(schema.ModuleJsonOutput.created_at).desc())
        ).all()
    for run_id, module_count, _latest_at in rows:
        if int(module_count) == len(RADAR_MODULES):
            return str(run_id)
    return str(rows[0][0]) if rows else None


def _latest_p3_event_run_id(db: Database) -> str | None:
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue.run_id)
            .where(schema.FeatureValue.module_id == EVENT_MODULE_ID)
            .order_by(schema.FeatureValue.created_at.desc())
        )
    return str(row) if row else None


def _module_outputs(db: Database, radar_run_id: str) -> dict[str, dict[str, Any]]:
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput).where(schema.ModuleJsonOutput.run_id == radar_run_id)
        ).all()
    return {row.module_id: row.payload for row in rows}


def _evidence_items(db: Database, pack_id: str | None) -> list[schema.EvidenceItem]:
    if not pack_id:
        return []
    with db.session() as session:
        return session.scalars(
            select(schema.EvidenceItem).where(schema.EvidenceItem.pack_id == pack_id)
        ).all()


def _feature_evidence_keys(rows: list[schema.EvidenceItem]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for row in rows:
        data = row.data or {}
        metric_id = data.get("metric_id")
        module_id = data.get("module_id") or row.module_id
        if metric_id and module_id:
            keys.add((str(module_id), str(metric_id)))
    return keys


def _evidence_source_layers(rows: list[schema.EvidenceItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        source_layer = str((row.data or {}).get("source_layer") or "unknown")
        counts[source_layer] = counts.get(source_layer, 0) + 1
    return counts


def _p3_event_rows(db: Database, p3_run_id: str | None) -> list[dict[str, Any]]:
    if not p3_run_id:
        return []
    with db.session() as session:
        rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == p3_run_id,
                schema.FeatureValue.module_id == EVENT_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
    result = []
    for row in rows:
        metadata = row.metadata_json or {}
        result.append(
            {
                "event_type": metadata.get("event_type"),
                "metric_id": metadata.get("metric_id"),
                "signed_days": _round(metadata.get("signed_days")),
                "event_phase": metadata.get("event_phase"),
                "window": metadata.get("window"),
                "daily_watch": metadata.get("daily_watch", {}).get("change_summary"),
                "publish_impact": metadata.get("event_summary", {})
                .get("interpretation", {})
                .get("publish_impact"),
            }
        )
    return result


def _module_to_analyst() -> dict[str, str]:
    return {
        module_id: analyst
        for analyst, module_ids in ANALYST_MODULES.items()
        for module_id in module_ids
    }


def _html_report(context: dict[str, Any]) -> str:
    summary = context["summary"]
    module_value = (
        f'{summary["radar_modules_consumed_count"]}/{summary["radar_module_total"]}'
    )
    module_ok = summary["radar_modules_consumed_count"] == summary["radar_module_total"]
    feature_value = (
        f'{summary["radar_feature_items_available"]}/'
        f'{summary["radar_feature_items_expected"]}'
    )
    feature_ok = (
        summary["radar_feature_items_available"]
        == summary["radar_feature_items_expected"]
    )
    signed_value = (
        f'{summary["signed_event_metrics_consumed_count"]}/'
        f'{summary["signed_event_metrics_total"]}'
    )
    signed_ok = (
        summary["signed_event_metrics_consumed_count"]
        == summary["signed_event_metrics_total"]
    )
    uncovered_value = summary["uncovered_metric_count"]
    uncovered_ok = summary["uncovered_metric_count"] == 0
    matrix_headers = [
        "analyst",
        "module_id",
        "module_present",
        "expected_features",
        "module_json_features",
        "missing_features",
        "provider_required",
        "evidence_pack_missing",
        "signal",
        "confidence",
        "data_quality",
    ]
    feature_headers = [
        "analyst",
        "module_id",
        "metric_id",
        "available",
        "role",
        "evidence_tier",
        "affects_signal",
        "affects_confidence",
        "affects_risk_flags",
        "feature_run_scope",
        "source_id",
        "source_run_id",
        "in_evidence_pack",
    ]
    event_headers = [
        "event_type",
        "metric_id",
        "signed_days",
        "event_phase",
        "window",
        "daily_watch",
        "publish_impact",
    ]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>P4 Radar Coverage Matrix</title>
  <style>
    body {{ margin: 0; background: #08131c; color: #dbeafe; font-family: Arial, sans-serif; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ color: #f8fafc; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #1e3a4f; background: #0d1f2d; border-radius: 8px; padding: 14px; }}
    .value {{ font-size: 20px; font-weight: 700; color: #67e8f9; overflow-wrap: anywhere; }}
    .warn {{ color: #fbbf24; }}
    .bad {{ color: #fb7185; }}
    .ok {{ color: #86efac; }}
    .table-wrap {{ width: 100%; overflow-x: auto; border: 1px solid #102c3e; border-radius: 6px; }}
    table {{ width: 100%; min-width: 1280px; border-collapse: collapse; font-size: 13px; }}
    th, td {{
      border-bottom: 1px solid #1e3a4f;
      padding: 8px;
      text-align: left;
      vertical-align: top;
      max-width: 280px;
      overflow-wrap: anywhere;
    }}
    th {{ color: #bae6fd; background: #0b1a26; position: sticky; top: 0; z-index: 1; }}
    code {{ color: #fef3c7; }}
  </style>
</head>
<body>
<main>
  <h1>P4 Radar Coverage Matrix</h1>
  <p>
    Generated: {escape(context["generated_at"].isoformat())} |
    Radar run: <code>{escape(str(summary["radar_run_id"]))}</code> |
    P3 run: <code>{escape(str(summary["p3_run_id"]))}</code>
  </p>
  <div class="grid">
    {_card("Radar Modules", module_value, module_ok)}
    {_card("Radar Features", feature_value, feature_ok)}
    {_card("Signed Events", signed_value, signed_ok)}
    {_card("Uncovered Metrics", uncovered_value, uncovered_ok)}
  </div>
  <h2>Summary</h2>
  {_table(["metric", "value"], _dict_rows(summary))}
  <h2>Analyst Coverage Matrix</h2>
  {_table(matrix_headers, context["matrix_rows"])}
  <h2>Feature Coverage</h2>
  {_table(feature_headers, context["feature_rows"])}
  <h2>P3 Event Evidence</h2>
  {_table(event_headers, context["p3_event_rows"])}
</main>
</body>
</html>
"""


def _card(label: str, value: Any, ok: bool) -> str:
    klass = "ok" if ok else "bad"
    return (
        '<div class="card">'
        f"<div>{escape(label)}</div>"
        f'<div class="value {klass}">{escape(str(value))}</div>'
        "</div>"
    )


def _dict_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"metric": key, "value": value} for key, value in payload.items()]


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
    return (
        '<div class="table-wrap">'
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        "</div>"
    )


def _format_cell(value: Any) -> str:
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value) or "-")
    if isinstance(value, dict):
        return escape(str(value))
    if isinstance(value, bool):
        return f'<span class="{"ok" if value else "bad"}">{value}</span>'
    return escape(str(value))


def _round(value: Any) -> Any:
    return round(float(value), 4) if isinstance(value, int | float) else value


def _write_report(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path
