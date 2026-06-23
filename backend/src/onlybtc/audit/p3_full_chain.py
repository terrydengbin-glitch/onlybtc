from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.algorithms.p3 import (
    ANOMALY_MODULE_ID,
    DIVERGENCE_MODULE_ID,
    EVENT_MODULE_ID,
    SCORED_METRIC_MODULE_ID,
    SCORED_RADAR_MODULE_ID,
    run_p3_pipeline,
)
from onlybtc.audit.p2_full_chain import run_p2_full_chain_audit
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database

P3_HTML_FILENAME = "p3-algorithm-audit-report.html"
FEATURE_ENGINE_MODULE_ID = "p3_feature_engine"


async def run_p3_full_chain_audit(
    collect_live: bool = True,
    run_mode: str = "live",
    db: Database = database,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    p2_result = await run_p2_full_chain_audit(
        collect_live=collect_live,
        run_mode=run_mode,
        db=db,
    )
    p3_result = run_p3_pipeline(
        run_mode=run_mode,
        collect_run_id=p2_result.get("collect_run_id"),
        p2_radar_run_id=p2_result.get("p2_radar_run_id"),
        historical_fallback=True,
        db=db,
    )
    context = _build_context(
        started_at=started_at,
        p2_result=p2_result,
        p3_result=p3_result,
        run_mode=run_mode,
        db=db,
    )
    report_dir = paths.project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = _write_report(report_dir / P3_HTML_FILENAME, _html_report(context))
    return {
        "status": "completed",
        "p1_c22_html_path": p2_result["p1_c22_html_path"],
        "p2_html_path": p2_result["p2_html_path"],
        "p3_html_path": str(html_path),
        "p2_radar_run_id": p2_result["p2_radar_run_id"],
        "collect_run_id": p2_result.get("collect_run_id"),
        "p3_run_id": p3_result["run_id"],
        "run_mode": run_mode,
        "non_production": run_mode != "live",
        "sqlite_checks": context["sqlite_checks"],
        "pipeline_summary": context["pipeline_summary"],
    }


def run_p3_full_chain_audit_sync(
    collect_live: bool = True,
    run_mode: str = "live",
) -> dict[str, Any]:
    return asyncio.run(run_p3_full_chain_audit(collect_live=collect_live, run_mode=run_mode))


def _build_context(
    started_at: datetime,
    p2_result: dict[str, Any],
    p3_result: dict[str, Any],
    run_mode: str,
    db: Database,
) -> dict[str, Any]:
    run_id = str(p3_result["run_id"])
    with db.session() as session:
        feature_counts = dict(
            session.execute(
                select(schema.FeatureValue.module_id, func.count())
                .where(schema.FeatureValue.run_id == run_id)
                .group_by(schema.FeatureValue.module_id)
            ).all()
        )
        invalidation_events = session.scalars(
            select(schema.InvalidationEvent)
            .where(schema.InvalidationEvent.run_id == run_id)
            .order_by(schema.InvalidationEvent.condition_id)
        ).all()
        anomaly_rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == ANOMALY_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
        divergence_rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == DIVERGENCE_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
        event_window_rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == EVENT_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
        scored_metric_rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_METRIC_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
        scored_module_rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
        alert_events = session.scalars(
            select(schema.AlertEvent)
            .where(
                schema.AlertEvent.created_at >= started_at,
                schema.AlertEvent.payload["run_mode"].as_string() == run_mode,
            )
            .order_by(schema.AlertEvent.created_at.desc())
            .limit(20)
        ).all()
        latest_alerts = session.scalars(
            select(schema.AlgorithmAlert)
            .where(schema.AlgorithmAlert.run_id == run_id)
            .order_by(schema.AlgorithmAlert.updated_at.desc())
            .limit(20)
        ).all()
        run_scope_rows = session.scalars(
            select(schema.FeatureValue).where(schema.FeatureValue.run_id == run_id)
        ).all()

    skipped = p3_result.get("anomalies", {}).get("skipped", [])
    not_enough_samples = [
        item["metric_id"] for item in skipped if item.get("reason") == "not_enough_samples"
    ]
    sqlite_checks = {
        "p3_feature_rows": feature_counts.get(FEATURE_ENGINE_MODULE_ID, 0),
        "scored_metric_rows": feature_counts.get(SCORED_METRIC_MODULE_ID, 0),
        "scored_radar_module_rows": feature_counts.get(SCORED_RADAR_MODULE_ID, 0),
        "anomaly_rows": feature_counts.get(ANOMALY_MODULE_ID, 0),
        "divergence_rows": feature_counts.get(DIVERGENCE_MODULE_ID, 0),
        "event_window_rows": feature_counts.get(EVENT_MODULE_ID, 0),
        "invalidation_events": len(invalidation_events),
        "latest_alerts": len(latest_alerts),
        "recent_alert_events": len(alert_events),
        "features_ok": feature_counts.get(FEATURE_ENGINE_MODULE_ID, 0) > 0,
        "scored_evidence_ok": feature_counts.get(SCORED_METRIC_MODULE_ID, 0) > 0
        and feature_counts.get(SCORED_RADAR_MODULE_ID, 0) > 0,
        "invalidations_ok": len(invalidation_events) > 0,
        "run_mode": run_mode,
        "non_production": run_mode != "live",
    }
    return {
        "started_at": started_at,
        "completed_at": datetime.now(UTC),
        "run_mode": run_mode,
        "p2_result": p2_result,
        "p3_result": p3_result,
        "pipeline_summary": _pipeline_summary(p3_result, len(not_enough_samples)),
        "run_scope": _run_scope_summary(run_scope_rows),
        "sqlite_checks": sqlite_checks,
        "not_enough_samples": not_enough_samples,
        "anomaly_rows": [_feature_row(row) for row in anomaly_rows],
        "divergence_rows": [_feature_row(row) for row in divergence_rows],
        "event_window_rows": [_feature_row(row) for row in event_window_rows],
        "scored_metric_rows": [_scored_metric_row(row) for row in scored_metric_rows],
        "scored_module_rows": [_scored_module_row(row) for row in scored_module_rows],
        "p45_precheck_rows": _p45_precheck_rows(scored_metric_rows, scored_module_rows),
        "invalidation_rows": [_invalidation_row(row) for row in invalidation_events],
        "alert_rows": [_alert_row(row) for row in latest_alerts],
        "alert_event_rows": [_alert_event_row(row) for row in alert_events],
    }


def _pipeline_summary(p3_result: dict[str, Any], not_enough_count: int) -> dict[str, Any]:
    features = p3_result.get("features", {})
    feature_numbers = [
        value
        for value in features.values()
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    alerts = p3_result.get("alerts", {})
    return {
        "run_id": p3_result.get("run_id"),
        "run_mode": p3_result.get("run_mode"),
        "collect_run_id": p3_result.get("collect_run_id"),
        "p2_radar_run_id": p3_result.get("p2_radar_run_id"),
        "historical_fallback": p3_result.get("historical_fallback"),
        "non_production": p3_result.get("non_production"),
        "metric_count": _number_at(feature_numbers, 0),
        "calculated_metric_count": _number_at(feature_numbers, 1),
        "feature_rows_written": _number_at(feature_numbers, 2),
        "anomaly_count": p3_result.get("anomalies", {}).get("written", 0),
        "divergence_count": p3_result.get("divergences", {}).get("written", 0),
        "module_invalidation_count": p3_result.get("module_invalidations", {}).get("written", 0),
        "global_invalidation_count": p3_result.get("global_invalidations", {}).get("written", 0),
        "event_window_count": p3_result.get("event_windows", {}).get("written", 0),
        "alert_candidates": alerts.get("candidates", 0),
        "alerts_created": alerts.get("created", 0),
        "alerts_updated": alerts.get("updated", 0),
        "not_enough_samples": not_enough_count,
    }


def _number_at(values: list[int], index: int) -> int | str:
    return values[index] if index < len(values) else ""


def _invalidation_row(row: schema.InvalidationEvent) -> dict[str, Any]:
    return {
        "condition_id": row.condition_id,
        "status": row.status,
        "action": row.action,
        "scope": row.payload.get("scope"),
        "module_id": row.payload.get("module_id", ""),
        "reason_code": row.payload.get("reason_code", ""),
        "affected_metrics": row.payload.get("affected_metrics", []),
        "direction_scope": row.payload.get("direction_scope", ""),
        "quality_impact": row.payload.get("quality_impact", ""),
        "publish_impact": row.payload.get("publish_impact", ""),
        "run_mode": row.payload.get("run_mode"),
        "non_production": row.payload.get("non_production"),
    }


def _feature_row(row: schema.FeatureValue) -> dict[str, Any]:
    metadata = row.metadata_json or {}
    evidence = metadata.get("evidence", {})
    return {
        "feature_id": row.feature_id,
        "value": _round_value(row.value),
        "metric_id": metadata.get("metric_id", ""),
        "source_id": metadata.get("source_id", ""),
        "source_run_id": metadata.get("source_run_id", ""),
        "feature_run_scope": metadata.get("feature_run_scope", ""),
        "fallback_reason": metadata.get("fallback_reason", ""),
        "type": metadata.get("anomaly_type")
        or metadata.get("type")
        or metadata.get("event_type", ""),
        "direction": metadata.get("direction", ""),
        "severity": metadata.get("severity") or metadata.get("severity_candidate", ""),
        "zscore": _round_value(metadata.get("zscore", "")),
        "percentile": _round_value(metadata.get("percentile", "")),
        "days_until": _round_value(metadata.get("days_until", "")),
        "signed_days": _round_value(metadata.get("signed_days", "")),
        "event_phase": metadata.get("event_phase", ""),
        "window_action": metadata.get("window_action", ""),
        "publish_impact": metadata.get("event_summary", {})
        .get("interpretation", {})
        .get("publish_impact", ""),
        "event_summary": metadata.get("event_summary", {}).get("headline", ""),
        "daily_watch": metadata.get("daily_watch", {}).get("change_summary", ""),
        "changed_fields": metadata.get("daily_watch", {}).get("changed_fields", []),
        "source_resolution": metadata.get("source_trace", {}).get(
            "source_resolution_status", ""
        ),
        "fallback_used": metadata.get("source_trace", {}).get("fallback_used", ""),
        "current": _round_value(evidence.get("current", "")),
        "quality_score": _round_value(metadata.get("quality_score", "")),
    }


def _scored_metric_row(row: schema.FeatureValue) -> dict[str, Any]:
    metadata = row.metadata_json or {}
    return {
        "evidence_id": metadata.get("evidence_id"),
        "radar_module": metadata.get("radar_module"),
        "metric_id": metadata.get("metric_id"),
        "source_id": metadata.get("source_id"),
        "value": _round_value(metadata.get("value")),
        "metric_score": _round_value(metadata.get("metric_score")),
        "metric_effective_score": _round_value(metadata.get("metric_effective_score")),
        "base_metric_score": _round_value(metadata.get("base_metric_score")),
        "score_bucket": metadata.get("score_bucket"),
        "score_bucket_v2": metadata.get("score_bucket_v2"),
        "zero_reason_type": metadata.get("zero_reason_type"),
        "decision_zero": metadata.get("decision_zero"),
        "direction": metadata.get("direction"),
        "base_direction": metadata.get("base_direction"),
        "freshness_weight": _round_value(metadata.get("freshness_weight")),
        "horizon_weight": _round_value(metadata.get("horizon_weight")),
        "duplicate_adjustment": _round_value(metadata.get("duplicate_adjustment")),
        "horizon_tags": metadata.get("horizon_tags", []),
        "duplicate_group_id": metadata.get("duplicate_group_id"),
        "module_weight": _round_value(metadata.get("module_weight")),
        "semantic_rule_id": metadata.get("semantic_rule_id"),
        "semantic_warning": metadata.get("semantic_warning"),
        "signal_type": metadata.get("signal_type"),
        "risk_score": _round_value(metadata.get("risk_score")),
        "event_risk_score": _round_value(metadata.get("event_risk_score")),
        "flow_state": metadata.get("flow_state"),
        "flow_direction_score": _round_value(metadata.get("flow_direction_score")),
        "flow_momentum_score": _round_value(metadata.get("flow_momentum_score")),
        "crowding_state": metadata.get("crowding_state"),
        "leverage_risk_score": _round_value(metadata.get("leverage_risk_score")),
        "derivatives_confirmation_score": _round_value(
            metadata.get("derivatives_confirmation_score")
        ),
        "valuation_state": metadata.get("valuation_state"),
        "thresholds_used": metadata.get("thresholds_used"),
        "component_metrics": metadata.get("component_metrics"),
        "quality_score": _round_value(metadata.get("quality_score")),
        "metric_explanation": metadata.get("metric_explanation"),
        "score_reason": metadata.get("score_reason"),
        "run_scope": metadata.get("run_scope"),
        "fallback_used": metadata.get("fallback_used"),
    }


def _scored_module_row(row: schema.FeatureValue) -> dict[str, Any]:
    metadata = row.metadata_json or {}
    return {
        "radar_module": metadata.get("radar_module"),
        "module_score": _round_value(metadata.get("module_score")),
        "module_effective_score": _round_value(metadata.get("module_effective_score")),
        "module_raw_score": _round_value(metadata.get("module_raw_score")),
        "module_final_score": _round_value(metadata.get("module_final_score")),
        "module_direction": metadata.get("module_direction"),
        "module_effective_direction": metadata.get("module_effective_direction"),
        "module_strength": _round_value(metadata.get("module_strength")),
        "module_effective_strength": _round_value(metadata.get("module_effective_strength")),
        "module_confidence": _round_value(metadata.get("module_confidence")),
        "source_module_confidence": _round_value(metadata.get("source_module_confidence")),
        "module_quality_score": _round_value(metadata.get("module_quality_score")),
        "coverage_score": _round_value(metadata.get("coverage_score")),
        "conflict_score": _round_value(metadata.get("conflict_score")),
        "freshness_factor": _round_value(metadata.get("freshness_factor")),
        "freshness_score": _round_value(metadata.get("freshness_score")),
        "quality_score": _round_value(metadata.get("quality_score")),
        "conflict_penalty": _round_value(metadata.get("conflict_penalty")),
        "raw_effective_conflict": metadata.get("raw_effective_conflict"),
        "module_state": metadata.get("module_state"),
        "direction_score": _round_value(metadata.get("direction_score")),
        "risk_score": _round_value(metadata.get("risk_score")),
        "confidence_score": _round_value(metadata.get("confidence_score")),
        "trend_state": metadata.get("trend_state"),
        "trend_state_reason": metadata.get("trend_state_reason"),
        "module_semantic_profile": metadata.get("module_semantic_profile"),
        "score_bucket": metadata.get("score_bucket"),
        "decision_zero_metric_ratio": _round_value(metadata.get("decision_zero_metric_ratio")),
        "rule_gap_zero_ratio": _round_value(metadata.get("rule_gap_zero_ratio")),
        "context_zero_ratio": _round_value(metadata.get("context_zero_ratio")),
        "neutral_confirmed_ratio": _round_value(metadata.get("neutral_confirmed_ratio")),
        "combo_required_ratio": _round_value(metadata.get("combo_required_ratio")),
        "zero_breakdown": metadata.get("zero_breakdown"),
        "positive_metric_count": metadata.get("positive_metric_count"),
        "negative_metric_count": metadata.get("negative_metric_count"),
        "zero_metric_count": metadata.get("zero_metric_count"),
        "unavailable_metric_count": metadata.get("unavailable_metric_count"),
        "top_positive_evidence_ids": metadata.get("top_positive_evidence_ids", []),
        "top_negative_evidence_ids": metadata.get("top_negative_evidence_ids", []),
        "top_positive": metadata.get("top_positive", []),
        "top_negative": metadata.get("top_negative", []),
        "top_contributors": metadata.get("top_contributors", []),
        "module_explanation": metadata.get("module_explanation"),
        "data_boundary": metadata.get("data_boundary", []),
    }


P45_ANALYST_MODULES = {
    "macro_event_analyst": (
        "macro_radar",
        "treasury_credit",
        "asia_risk",
        "event_policy",
    ),
    "liquidity_flow_analyst": ("dollar_liquidity", "fund_flow", "crypto_breadth"),
    "microstructure_analyst": (
        "kline_orderflow",
        "derivatives_crowding",
        "trade_structure_flow",
        "options_volatility",
    ),
    "onchain_structure_analyst": (
        "btc_total_state",
        "btc_adoption",
        "onchain_valuation",
    ),
}


def _p45_precheck_rows(
    metric_rows: list[schema.FeatureValue],
    module_rows: list[schema.FeatureValue],
) -> list[dict[str, Any]]:
    metrics = [row.metadata_json or {} for row in metric_rows]
    modules = [row.metadata_json or {} for row in module_rows]
    result = []
    for analyst_id, module_ids in P45_ANALYST_MODULES.items():
        analyst_metrics = [
            item for item in metrics if item.get("radar_module") in set(module_ids)
        ]
        analyst_modules = [
            item for item in modules if item.get("radar_module") in set(module_ids)
        ]
        result.append(
            {
                "analyst_id": analyst_id,
                "modules": ", ".join(module_ids),
                "module_count": len(analyst_modules),
                "metric_count": len(analyst_metrics),
                "positive": _bucket_count(analyst_metrics, "positive"),
                "negative": _bucket_count(analyst_metrics, "negative"),
                "zero": _bucket_count(analyst_metrics, "zero"),
                "unavailable": _bucket_count(analyst_metrics, "unavailable"),
                "missing_module_explanation": [
                    item.get("radar_module")
                    for item in analyst_modules
                    if not item.get("module_explanation")
                ],
                "missing_metric_explanation": [
                    item.get("metric_id")
                    for item in analyst_metrics
                    if not item.get("metric_explanation")
                ][:12],
            }
        )
    return result


def _bucket_count(items: list[dict[str, Any]], bucket: str) -> int:
    return sum(1 for item in items if item.get("score_bucket") == bucket)


def _run_scope_summary(rows: list[schema.FeatureValue]) -> dict[str, Any]:
    counts = {
        "current_run_feature_count": 0,
        "historical_fallback_feature_count": 0,
        "provider_required_feature_count": 0,
        "missing_feature_count": 0,
    }
    scoped_count = 0
    for row in rows:
        scope = str((row.metadata_json or {}).get("feature_run_scope") or "")
        if not scope:
            continue
        scoped_count += 1
        if scope == "current_run":
            counts["current_run_feature_count"] += 1
        elif scope == "historical_fallback":
            counts["historical_fallback_feature_count"] += 1
        elif scope == "provider_required":
            counts["provider_required_feature_count"] += 1
        else:
            counts["missing_feature_count"] += 1
    same_run_score = (
        counts["current_run_feature_count"] / scoped_count if scoped_count else 0.0
    )
    return {
        **counts,
        "scoped_feature_count": scoped_count,
        "same_run_coverage_score": round(same_run_score, 4),
        "historical_fallback_risk": counts["historical_fallback_feature_count"] > 0,
    }


def _round_value(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def _alert_row(row: schema.AlgorithmAlert) -> dict[str, Any]:
    return {
        "alert_id": row.alert_id,
        "run_id": row.run_id,
        "level": row.level,
        "state": row.state,
        "evidence_count": row.evidence_count,
        "summary": row.summary,
    }


def _alert_event_row(row: schema.AlertEvent) -> dict[str, Any]:
    return {
        "alert_id": row.alert_id,
        "event_type": row.event_type,
        "level": row.payload.get("level"),
        "run_mode": row.payload.get("run_mode"),
        "non_production": row.payload.get("non_production"),
        "evidence_count": row.payload.get("evidence_count"),
    }


def _html_report(context: dict[str, Any]) -> str:
    p2_result = context["p2_result"]
    summary_headers = ["metric", "value"]
    invalidation_headers = [
        "condition_id",
        "status",
        "action",
        "scope",
        "module_id",
        "reason_code",
        "affected_metrics",
        "direction_scope",
        "quality_impact",
        "publish_impact",
        "run_mode",
        "non_production",
    ]
    alert_headers = ["alert_id", "run_id", "level", "state", "evidence_count", "summary"]
    alert_event_headers = [
        "alert_id",
        "event_type",
        "level",
        "run_mode",
        "non_production",
        "evidence_count",
    ]
    feature_headers = [
        "feature_id",
        "value",
        "metric_id",
        "source_id",
        "source_run_id",
        "feature_run_scope",
        "fallback_reason",
        "type",
        "direction",
        "severity",
        "zscore",
        "percentile",
        "days_until",
        "signed_days",
        "event_phase",
        "window_action",
        "publish_impact",
        "event_summary",
        "daily_watch",
        "changed_fields",
        "source_resolution",
        "fallback_used",
        "current",
        "quality_score",
    ]
    scored_module_headers = [
        "radar_module",
        "module_score",
        "module_effective_score",
        "module_raw_score",
        "module_final_score",
        "module_direction",
        "module_effective_direction",
        "module_strength",
        "module_effective_strength",
        "module_confidence",
        "source_module_confidence",
        "module_quality_score",
        "coverage_score",
        "conflict_score",
        "freshness_factor",
        "freshness_score",
        "quality_score",
        "conflict_penalty",
        "raw_effective_conflict",
        "module_state",
        "direction_score",
        "risk_score",
        "confidence_score",
        "trend_state",
        "trend_state_reason",
        "module_semantic_profile",
        "score_bucket",
        "decision_zero_metric_ratio",
        "rule_gap_zero_ratio",
        "context_zero_ratio",
        "neutral_confirmed_ratio",
        "combo_required_ratio",
        "zero_breakdown",
        "positive_metric_count",
        "negative_metric_count",
        "zero_metric_count",
        "unavailable_metric_count",
        "top_positive_evidence_ids",
        "top_negative_evidence_ids",
        "top_positive",
        "top_negative",
        "top_contributors",
        "module_explanation",
        "data_boundary",
    ]
    scored_metric_headers = [
        "evidence_id",
        "radar_module",
        "metric_id",
        "source_id",
        "value",
        "metric_score",
        "metric_effective_score",
        "base_metric_score",
        "score_bucket",
        "score_bucket_v2",
        "zero_reason_type",
        "decision_zero",
        "direction",
        "base_direction",
        "freshness_weight",
        "horizon_weight",
        "duplicate_adjustment",
        "horizon_tags",
        "duplicate_group_id",
        "module_weight",
        "semantic_rule_id",
        "semantic_warning",
        "signal_type",
        "risk_score",
        "event_risk_score",
        "flow_state",
        "flow_direction_score",
        "flow_momentum_score",
        "crowding_state",
        "leverage_risk_score",
        "derivatives_confirmation_score",
        "valuation_state",
        "thresholds_used",
        "component_metrics",
        "quality_score",
        "metric_explanation",
        "score_reason",
        "run_scope",
        "fallback_used",
    ]
    p45_headers = [
        "analyst_id",
        "modules",
        "module_count",
        "metric_count",
        "positive",
        "negative",
        "zero",
        "unavailable",
        "missing_module_explanation",
        "missing_metric_explanation",
    ]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>P3 Algorithm Audit Report</title>
  <style>
    body {{ margin: 0; background: #08131c; color: #dbeafe; font-family: Arial, sans-serif; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ color: #f8fafc; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #1e3a4f; background: #0d1f2d; border-radius: 8px; padding: 14px; }}
    .value {{ font-size: 20px; font-weight: 700; color: #67e8f9; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #1e3a4f; padding: 8px; text-align: left; }}
    th, td {{ vertical-align: top; max-width: 240px; overflow-wrap: anywhere; }}
    th {{ color: #bae6fd; background: #0b1a26; position: sticky; top: 0; z-index: 1; }}
    .table-wrap {{ width: 100%; overflow-x: auto; border: 1px solid #102c3e; border-radius: 6px; }}
    .table-wrap table {{ min-width: 1320px; margin-top: 0; }}
    .kv-list {{ margin: 0; padding-left: 14px; list-style: none; }}
    .kv-list li {{ margin: 0 0 6px; line-height: 1.35; }}
    .kv-field {{ color: #bae6fd; font-weight: 700; display: block; }}
    .kv-change {{ color: #dbeafe; }}
    .muted {{ color: #94a3b8; }}
    code {{ color: #fef3c7; }}
  </style>
</head>
<body>
<main>
  <h1>P3 Algorithm Audit Report</h1>
  <p>
    Started: {escape(context["started_at"].isoformat())} |
    Completed: {escape(context["completed_at"].isoformat())} |
    Run mode: <code>{escape(str(context["run_mode"]))}</code>
  </p>
  <div class="grid">
    {_card("P1-C22 HTML", p2_result.get("p1_c22_html_path", "-"))}
    {_card("P2 Radar HTML", p2_result.get("p2_html_path", "-"))}
    {_card("P3 run", context["p3_result"].get("run_id", "-"))}
  </div>

  <h2>Pipeline Summary</h2>
  {_table(summary_headers, _dict_rows(context["pipeline_summary"]))}

  <h2>Run Lineage</h2>
  {_table(summary_headers, _dict_rows({
      "collect_run_id": p2_result.get("collect_run_id"),
      "p2_radar_run_id": p2_result.get("p2_radar_run_id"),
      "p3_run_id": context["p3_result"].get("run_id"),
  }))}

  <h2>Run Scope Summary</h2>
  {_table(summary_headers, _dict_rows(context["run_scope"]))}

  <h2>SQLite Contract</h2>
  {_table(summary_headers, _dict_rows(context["sqlite_checks"]))}

  <h2>Scored Radar Modules</h2>
  {_table(scored_module_headers, context["scored_module_rows"])}

  <h2>Scored Metric Evidence</h2>
  {_table(scored_metric_headers, context["scored_metric_rows"])}

  <h2>P4.5 Analyst Input Precheck</h2>
  {_table(p45_headers, context["p45_precheck_rows"])}

  <h2>Not Enough Samples</h2>
  {_table(["metric_id"], [{"metric_id": item} for item in context["not_enough_samples"]])}

  <h2>Anomaly Details</h2>
  {_table(feature_headers, context["anomaly_rows"])}

  <h2>Divergence Details</h2>
  {_table(feature_headers, context["divergence_rows"])}

  <h2>Event Window Summary</h2>
  <h2>Event Window Details</h2>
  {_table(feature_headers, context["event_window_rows"])}

  <h2>Invalidation Events</h2>
  {_table(invalidation_headers, context["invalidation_rows"])}

  <h2>Latest Algorithm Alerts</h2>
  {_table(alert_headers, context["alert_rows"])}

  <h2>Recent Alert Events</h2>
  {_table(alert_event_headers, context["alert_event_rows"])}
</main>
</body>
</html>
"""


def _card(label: str, value: Any) -> str:
    return (
        '<div class="card">'
        f"<div>{escape(label)}</div>"
        f'<div class="value">{escape(str(value))}</div>'
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
        if value and all(isinstance(item, dict) for item in value):
            return _format_dict_list(value)
        return escape(", ".join(str(item) for item in value) or "-")
    if isinstance(value, dict):
        return _format_dict(value)
    return escape(str(value))


def _format_dict_list(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        field = escape(str(item.get("field", "")))
        previous = _compact_value(item.get("previous"))
        current = _compact_value(item.get("current"))
        if field:
            rows.append(
                "<li>"
                f'<span class="kv-field">{field}</span>'
                f'<span class="kv-change"><span class="muted">prev:</span> {previous}<br />'
                f'<span class="muted">now:</span> {current}</span>'
                "</li>"
            )
        else:
            rows.append(f"<li>{_format_dict(item)}</li>")
    return f'<ul class="kv-list">{"".join(rows)}</ul>' if rows else "-"


def _format_dict(item: dict[str, Any]) -> str:
    rows = [
        "<li>"
        f'<span class="kv-field">{escape(str(key))}</span>'
        f'<span class="kv-change">{_compact_value(value)}</span>'
        "</li>"
        for key, value in item.items()
    ]
    return f'<ul class="kv-list">{"".join(rows)}</ul>' if rows else "-"


def _compact_value(value: Any) -> str:
    if value is None or value == "":
        return '<span class="muted">-</span>'
    if isinstance(value, float):
        return escape(str(round(value, 4)))
    return escape(str(value))


def _write_report(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path
