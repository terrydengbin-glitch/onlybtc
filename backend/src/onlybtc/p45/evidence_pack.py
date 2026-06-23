from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select

from onlybtc.algorithms.p3 import SCORED_METRIC_MODULE_ID, SCORED_RADAR_MODULE_ID
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p45.boundary import ANALYST_MODULES
from onlybtc.p45.explanations import build_metric_brief, catalog_coverage

P45_EVIDENCE_PACK_MODULE_ID = "p45_analyst_evidence_pack"
P45_EVIDENCE_PACK_SCHEMA_VERSION = "p45.evidence_pack.v1"


def build_p45_scored_evidence_pack(
    p3_run_id: str | None = None,
    pack_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        p3_run_id = p3_run_id or _latest_p3_scored_run_id(session)
        if p3_run_id is None:
            raise ValueError("No P3 scored evidence run found.")

        pack_id = pack_id or _generate_pack_id()
        metric_rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == p3_run_id,
                schema.FeatureValue.module_id == SCORED_METRIC_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
        module_rows = session.scalars(
            select(schema.FeatureValue)
            .where(
                schema.FeatureValue.run_id == p3_run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
            )
            .order_by(schema.FeatureValue.feature_id)
        ).all()
        if not metric_rows or not module_rows:
            raise ValueError(f"P3 run {p3_run_id} has no scored evidence.")

        metrics = [dict(row.metadata_json or {}) for row in metric_rows]
        modules = [dict(row.metadata_json or {}) for row in module_rows]
        result = _pack_payload(pack_id, p3_run_id, metrics, modules)
        session.add(
            schema.ModuleJsonOutput(
                run_id=pack_id,
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version=P45_EVIDENCE_PACK_SCHEMA_VERSION,
                payload=result,
            )
        )
        return result


def _pack_payload(
    pack_id: str,
    p3_run_id: str,
    metrics: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    module_by_id = {item["radar_module"]: item for item in modules}
    collect_run_id = _first_present(metrics, "collect_run_id") or _first_present(
        modules, "collect_run_id"
    )
    p2_radar_run_id = _first_present(metrics, "p2_radar_run_id") or _first_present(
        modules, "p2_radar_run_id"
    )
    analysts = [
        _analyst_pack(analyst_id, module_ids, metrics, module_by_id)
        for analyst_id, module_ids in ANALYST_MODULES.items()
    ]
    return {
        "schema_version": P45_EVIDENCE_PACK_SCHEMA_VERSION,
        "pack_id": pack_id,
        "p3_run_id": p3_run_id,
        "p2_radar_run_id": p2_radar_run_id,
        "collect_run_id": collect_run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "source_layer": "p3_scored_evidence",
        "analysts": analysts,
        "summary": {
            "analyst_count": len(analysts),
            "radar_module_count": len(modules),
            "metric_evidence_count": len(metrics),
            "positive": _bucket_count(metrics, "positive"),
            "negative": _bucket_count(metrics, "negative"),
            "zero": _bucket_count(metrics, "zero"),
            "unavailable": _bucket_count(metrics, "unavailable"),
            "data_boundary_count": sum(
                len(item.get("data_boundary") or []) for item in modules
            ),
            "metric_explanation_catalog": catalog_coverage(),
        },
    }


def _analyst_pack(
    analyst_id: str,
    module_ids: tuple[str, ...],
    metrics: list[dict[str, Any]],
    module_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    modules = []
    for module_id in module_ids:
        module = dict(module_by_id.get(module_id, {}))
        module_metrics = sorted(
            [
                _metric_pack_item(item)
                for item in metrics
                if item.get("radar_module") == module_id
            ],
            key=lambda item: str(item.get("evidence_id") or item.get("metric_id")),
        )
        module["metrics"] = module_metrics
        modules.append(module)
    analyst_metrics = [metric for module in modules for metric in module["metrics"]]
    return {
        "analyst_id": analyst_id,
        "radar_modules": list(module_ids),
        "module_count": len(modules),
        "metric_count": len(analyst_metrics),
        "positive": _bucket_count(analyst_metrics, "positive"),
        "negative": _bucket_count(analyst_metrics, "negative"),
        "zero": _bucket_count(analyst_metrics, "zero"),
        "unavailable": _bucket_count(analyst_metrics, "unavailable"),
        "modules": modules,
        "data_boundary": [
            boundary
            for module in modules
            for boundary in module.get("data_boundary", [])
        ],
    }


def _metric_pack_item(item: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "evidence_id",
        "radar_module",
        "metric_id",
        "metric_name",
        "source_id",
        "source_run_id",
        "value",
        "direction",
        "base_direction",
        "metric_score",
        "metric_effective_score",
        "base_metric_score",
        "score_bucket",
        "score_bucket_v2",
        "zero_reason_type",
        "zero_reason",
        "decision_zero",
        "weight",
        "quality_score",
        "freshness_weight",
        "horizon_weight",
        "duplicate_adjustment",
        "horizon_tags",
        "duplicate_group_id",
        "module_weight",
        "source_ts",
        "collected_at",
        "freshness_minutes",
        "stale_after_minutes",
        "is_stale",
        "freshness_status",
        "business_recency_status",
        "semantic_rule_id",
        "semantic_warning",
        "signal_type",
        "risk_score",
        "event_risk_score",
        "flow_direction_score",
        "flow_momentum_score",
        "flow_state",
        "marginal_state",
        "marginal_direction",
        "crowding_state",
        "funding_state",
        "crowding_signal",
        "direction_contribution",
        "trend_confirmation",
        "oi_state",
        "oi_confirmation",
        "oi_trend_signal",
        "positioning_signal",
        "crowding_contribution",
        "positioning_scope",
        "leverage_risk_score",
        "derivatives_confirmation_score",
        "valuation_state",
        "price_trend_score",
        "volume_confirmation_score",
        "candle_structure_score",
        "breakdown_risk_score",
        "rebound_quality_score",
        "selling_pressure_score",
        "metric_self_direction",
        "metric_self_score",
        "module_composite_score",
        "module_composite_direction",
        "module_composite_state",
        "kline_composite_contribution",
        "kline_trend_state",
        "kline_confirmation_status",
        "price_response_state",
        "price_response_confidence",
        "flow_price_efficiency_state",
        "price_response_source",
        "volume_interpretation",
        "candle_interpretation",
        "thresholds_used",
        "component_metrics",
        "metric_explanation",
        "score_reason",
        "history_context",
        "run_scope",
        "fallback_used",
        "fallback_reason",
        "available",
        "evidence_tier",
        "role",
        "affects_signal",
        "affects_confidence",
        "driver_eligible",
        "run_mode",
        "collect_run_id",
        "p2_radar_run_id",
        "p3_run_id",
    )
    result = {key: item.get(key) for key in keep}
    result["p45_metric_brief"] = build_metric_brief(item)
    return result


def _latest_p3_scored_run_id(session) -> str | None:
    return session.scalar(
        select(schema.FeatureValue.run_id)
        .where(schema.FeatureValue.module_id == SCORED_METRIC_MODULE_ID)
        .group_by(schema.FeatureValue.run_id)
        .having(func.count(schema.FeatureValue.id) > 0)
        .order_by(func.max(schema.FeatureValue.created_at).desc())
        .limit(1)
    )


def _bucket_count(items: list[dict[str, Any]], bucket: str) -> int:
    return sum(1 for item in items if item.get("score_bucket") == bucket)


def _first_present(items: list[dict[str, Any]], key: str) -> Any:
    return next((item.get(key) for item in items if item.get(key)), None)


def _generate_pack_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"p45pack-{stamp}-{uuid4().hex[:6]}"
