from sqlalchemy import select

from onlybtc.api import p45_dashboard
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID, run_p45_final_writer
from onlybtc.p45.invalidation_workbench import build_invalidation_workbench
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID


def test_workbench_without_btc_response_cannot_trigger() -> None:
    workbench = build_invalidation_workbench(
        btc_trend_cockpit={
            "schema_version": "p45.btc_trend_cockpit.v2",
            "headline_state": "neutral",
            "btc_direction": "neutral",
            "scores": {"trend_acceptance_score": 42, "support_score": 0.2, "pressure_score": 0.2},
            "module_signals": [
                {
                    "module_name": "fund_flow",
                    "layer": "confirmation",
                    "effective_direction": "bearish",
                    "raw_direction": "bearish",
                    "signal_stage": "confirmed_signal",
                    "module_score": -0.5,
                    "contribution": -0.2,
                    "accepted_status": "unknown",
                    "quality_status": "passed",
                    "btc_implication": "institutional_demand_drag",
                }
            ],
        },
        modules=[],
        contract_validation={"status": "passed"},
        data_quality={},
    )

    assert workbench["schema_version"] == "p45.invalidation_workbench.v2"
    assert workbench["validation_state"] == "watching"
    assert not workbench["triggered_rules"]
    assert workbench["armed_rules"]


def test_workbench_blocks_on_contract_failure() -> None:
    workbench = build_invalidation_workbench(
        btc_trend_cockpit={
            "schema_version": "p45.btc_trend_cockpit.v2",
            "headline_state": "neutral",
            "btc_direction": "neutral",
            "scores": {"trend_acceptance_score": 80, "support_score": 0.8, "pressure_score": 0.0},
            "module_signals": [],
        },
        modules=[],
        contract_validation={"status": "failed"},
        data_quality={},
    )

    assert workbench["validation_state"] == "blocked"
    assert workbench["blocked_rules"]


def test_workbench_marks_context_accepted_as_trigger_ineligible() -> None:
    workbench = build_invalidation_workbench(
        btc_trend_cockpit={
            "schema_version": "p45.btc_trend_cockpit.v2",
            "headline_state": "neutral",
            "btc_direction": "neutral",
            "scores": {"trend_acceptance_score": 54, "support_score": 0.1, "pressure_score": 0.6},
            "module_signals": [
                {
                    "module_name": "btc_adoption",
                    "layer": "regime",
                    "effective_direction": "bearish",
                    "raw_direction": "neutral",
                    "signal_stage": "none",
                    "contribution": -0.04,
                    "accepted_status": "accepted",
                    "quality_status": "passed",
                    "btc_implication": "neutral",
                    "btc_response_score": -55,
                    "residual": -0.7,
                },
                {
                    "module_name": "trade_structure_flow",
                    "layer": "fast",
                    "effective_direction": "bearish",
                    "raw_direction": "bearish",
                    "signal_stage": "conflict",
                    "contribution": -0.05,
                    "accepted_status": "accepted",
                    "quality_status": "passed",
                    "btc_implication": "upside_squeeze_failed",
                    "btc_response_score": -80,
                },
            ],
        },
        modules=[],
        contract_validation={"status": "passed"},
        data_quality={},
    )

    matrix = {item["module_id"]: item for item in workbench["module_evidence_matrix"]}
    assert matrix["btc_adoption"]["evidence_state"] == "accepted_context"
    assert matrix["btc_adoption"]["evidence_weight_status"] == "context"
    assert matrix["btc_adoption"]["trigger_eligible"] is False
    assert matrix["trade_structure_flow"]["evidence_state"] == "accepted"
    assert matrix["trade_structure_flow"]["evidence_weight_status"] == "full"
    assert matrix["trade_structure_flow"]["trigger_eligible"] is True
    assert not workbench["triggered_rules"]


def test_workbench_quality_flagged_accepted_is_discounted() -> None:
    workbench = build_invalidation_workbench(
        btc_trend_cockpit={
            "schema_version": "p45.btc_trend_cockpit.v2",
            "headline_state": "neutral",
            "btc_direction": "neutral",
            "scores": {"trend_acceptance_score": 62, "support_score": 0.1, "pressure_score": 0.6},
            "module_signals": [
                {
                    "module_name": "fund_flow",
                    "layer": "confirmation",
                    "effective_direction": "bearish",
                    "raw_direction": "bearish",
                    "signal_stage": "confirmed_signal",
                    "contribution": -0.2,
                    "accepted_status": "accepted",
                    "quality_status": "passed",
                    "btc_implication": "institutional_demand_drag",
                    "btc_response_score": -40,
                    "residual": -0.3,
                    "data_quality_flags": ["etf_single_source"],
                },
                {
                    "module_name": "trade_structure_flow",
                    "layer": "fast",
                    "effective_direction": "bearish",
                    "raw_direction": "bearish",
                    "signal_stage": "confirmed_signal",
                    "contribution": -0.3,
                    "accepted_status": "accepted",
                    "quality_status": "passed",
                    "btc_implication": "downside_liquidity_stress_confirmed",
                    "btc_response_score": -70,
                },
            ],
        },
        modules=[],
        contract_validation={"status": "passed"},
        data_quality={},
    )

    matrix = {item["module_id"]: item for item in workbench["module_evidence_matrix"]}
    assert matrix["fund_flow"]["evidence_state"] == "quality_discounted"
    assert matrix["fund_flow"]["evidence_weight_status"] == "discounted"
    assert matrix["fund_flow"]["trigger_eligible"] is False
    assert matrix["trade_structure_flow"]["trigger_eligible"] is True
    assert not workbench["triggered_rules"]


def test_final_writer_persists_and_api_passthroughs_workbench(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    assert result["invalidation_workbench"]["schema_version"] == "p45.invalidation_workbench.v2"
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID,
            )
        )
    assert row is not None
    assert row.payload["invalidation_workbench"]["schema_version"] == "p45.invalidation_workbench.v2"

    invalidation = p45_dashboard.latest_invalidation(db=db)
    history = p45_dashboard.history("final-test", db=db)

    assert invalidation["schema_version"] == "p45.invalidation_workbench.v2"
    assert invalidation["validation_state"] in {"confirmed", "watching", "refuted", "conflict", "blocked"}
    assert history is not None
    assert history["invalidation_workbench"]["schema_version"] == "p45.invalidation_workbench.v2"


def _analyst_payload() -> dict:
    return {
        "article_run_id": "articles-test",
        "pack_id": "pack-test",
        "analyst_articles": [
            {
                "analyst_id": "macro",
                "title": "Macro",
                "direction_view": "neutral",
                "score_summary": {},
                "key_positive_evidence_ids": [],
                "key_negative_evidence_ids": [],
                "neutral_watch_evidence_ids": [],
                "data_boundary": [],
            }
            for _ in range(4)
        ],
    }


def _pack_payload() -> dict:
    modules = [
        _module("kline_orderflow", "bullish", 0.46, "upside_trend_confirmed", 78, 1.2),
        _module("trade_structure_flow", "bullish", 0.42, "spot_led_trend_confirmed", 75, 0.9),
        _module("fund_flow", "bullish", 0.28, "trend_confirmed", 70, 0.6),
        _module("macro_radar", "bullish", 0.25, "trend_confirmed", 60, 0.4),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [{"analyst_id": "test", "modules": modules}],
    }


def _module(module: str, direction: str, score: float, implication: str, response: float, residual: float) -> dict:
    return {
        "radar_module": module,
        "module_score": score,
        "module_effective_score": score,
        "module_direction": direction,
        "module_effective_direction": direction,
        "module_quality_score": 0.9,
        "signal_stage": "confirmed_signal",
        "btc_implication": implication,
        "scores": {"btc_response_score": response},
        "btc_residual_24h": residual,
        "support_drivers": [f"{module}_support"],
        "pressure_drivers": [],
        "metrics": [_metric(module, f"{module}_metric", score)],
    }


def _metric(module: str, metric: str, score: float) -> dict:
    return {
        "evidence_id": f"p3-score-test-{module}-{metric}",
        "radar_module": module,
        "metric_id": metric,
        "metric_effective_score": score,
        "quality_score": 0.9,
        "horizon_tags": ["h24"],
        "driver_eligible": True,
    }
