from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import (
    P45_EVIDENCE_PACK_MODULE_ID,
    build_p45_scored_evidence_pack,
)


def test_p45_scored_evidence_pack_splits_four_analysts(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        for module_id, score in (
            ("macro_radar", 0.2),
            ("fund_flow", -0.3),
            ("trade_structure_flow", 0.4),
            ("onchain_valuation", 0.1),
        ):
            session.add(
                schema.FeatureValue(
                    run_id="p3-test",
                    module_id="p3_scored_radar_module",
                    feature_id=f"{module_id}.scored_module",
                    value=score,
                    metadata_json=_module(module_id, score),
                )
            )
            session.add(
                schema.FeatureValue(
                    run_id="p3-test",
                    module_id="p3_scored_metric_evidence",
                    feature_id=f"{module_id}.metric.scored",
                    value=score,
                    metadata_json=_metric(module_id, f"{module_id}_metric", score),
                )
            )

    result = build_p45_scored_evidence_pack(p3_run_id="p3-test", pack_id="pack-test", db=db)

    assert result["pack_id"] == "pack-test"
    assert result["p3_run_id"] == "p3-test"
    assert result["summary"]["analyst_count"] == 4
    assert result["summary"]["metric_evidence_count"] == 4
    analysts = {item["analyst_id"]: item for item in result["analysts"]}
    assert analysts["macro_event_analyst"]["metric_count"] == 1
    assert analysts["liquidity_flow_analyst"]["metric_count"] == 1
    assert analysts["microstructure_analyst"]["metric_count"] == 1
    assert analysts["onchain_structure_analyst"]["metric_count"] == 1
    evidence = analysts["fund_flow" if False else "liquidity_flow_analyst"]["modules"][1][
        "metrics"
    ][0]
    assert evidence["evidence_id"].startswith("ev-fund_flow")
    assert evidence["semantic_rule_id"] == "semantic.test"
    assert "p45_metric_brief" in evidence
    assert result["summary"]["metric_explanation_catalog"]["missing_metric_ids"] == []

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "pack-test",
                schema.ModuleJsonOutput.module_id == P45_EVIDENCE_PACK_MODULE_ID,
            )
        )

    assert row is not None
    assert row.payload["summary"]["analyst_count"] == 4


def _module(module_id: str, score: float) -> dict:
    return {
        "radar_module": module_id,
        "module_score": score,
        "module_direction": "bullish" if score > 0 else "bearish",
        "module_strength": abs(score),
        "module_confidence": 0.8,
        "module_quality_score": 0.9,
        "score_bucket": "positive" if score > 0 else "negative",
        "positive_metric_count": 1 if score > 0 else 0,
        "negative_metric_count": 0 if score > 0 else 1,
        "zero_metric_count": 0,
        "unavailable_metric_count": 0,
        "module_explanation": f"{module_id} explanation",
        "data_boundary": [],
        "metric_items": [f"ev-{module_id}"],
        "collect_run_id": "collect-test",
        "p2_radar_run_id": "radar-test",
    }


def _metric(module_id: str, metric_id: str, score: float) -> dict:
    return {
        "evidence_id": f"ev-{module_id}-{metric_id}",
        "radar_module": module_id,
        "metric_id": metric_id,
        "metric_name": metric_id,
        "source_id": "source-test",
        "source_run_id": "collect-test-source",
        "value": 1.0,
        "direction": "bullish" if score > 0 else "bearish",
        "base_direction": "neutral",
        "metric_score": score,
        "base_metric_score": 0.0,
        "score_bucket": "positive" if score > 0 else "negative",
        "weight": 0.1,
        "quality_score": 0.9,
        "freshness_status": "fresh",
        "business_recency_status": "current",
        "semantic_rule_id": "semantic.test",
        "semantic_warning": None,
        "metric_explanation": "metric explanation",
        "score_reason": "score reason",
        "history_context": {},
        "run_scope": "current_run",
        "fallback_used": False,
        "fallback_reason": None,
        "available": True,
        "evidence_tier": "primary",
        "role": "primary_signal",
        "affects_signal": True,
        "run_mode": "live",
        "collect_run_id": "collect-test",
        "p2_radar_run_id": "radar-test",
        "p3_run_id": "p3-test",
    }
