from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.cockpit import build_btc_trend_cockpit, normalize_module_signals
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID, run_p45_final_writer
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID
from onlybtc.api import p45_dashboard


def test_btc_trend_cockpit_normalizes_modules_without_raw_metric_direction() -> None:
    signals = normalize_module_signals(
        [
            {
                "radar_module": "fund_flow",
                "module_direction": "bearish",
                "module_score": -0.42,
                "signal_stage": "confirmed_signal",
                "btc_implication": "internal_weakness",
                "scores": {"btc_response_score": -78},
                "support_drivers": ["etf_flow"],
                "pressure_drivers": ["btc_rejecting_flow"],
            }
        ]
    )

    assert signals[0]["module_name"] == "fund_flow"
    assert signals[0]["layer"] == "confirmation"
    assert signals[0]["accepted_status"] == "rejected"
    assert signals[0]["contribution"] > 0


def test_btc_trend_cockpit_single_pressure_module_cannot_confirm() -> None:
    cockpit = build_btc_trend_cockpit(
        [
            {
                "radar_module": "fund_flow",
                "module_direction": "bearish",
                "module_effective_direction": "bearish",
                "module_score": -0.80,
                "module_effective_score": -0.80,
                "signal_stage": "confirmed_signal",
                "btc_implication": "trend_confirmed",
                "scores": {"btc_response_score": -90},
            }
        ],
        contract_validation={"status": "passed"},
        data_quality={"metric_count": 1},
    )

    assert cockpit["headline_state"] != "confirmed_bearish"
    assert cockpit["scores"]["pressure_score"] > 0
    assert cockpit["schema_version"] == "p45.btc_trend_cockpit.v2"


def test_btc_trend_cockpit_blocks_on_contract_failure() -> None:
    cockpit = build_btc_trend_cockpit(
        [
            {
                "radar_module": "kline_orderflow",
                "module_direction": "bullish",
                "module_effective_direction": "bullish",
                "module_score": 0.50,
                "signal_stage": "confirmed_signal",
                "btc_implication": "trend_confirmed",
                "scores": {"btc_response_score": 80},
            }
        ],
        contract_validation={"status": "failed"},
        data_quality={"metric_count": 1},
    )

    assert cockpit["headline_state"] == "blocked"
    assert cockpit["trade_permission"] == "blocked"


def test_final_writer_persists_and_api_passthroughs_btc_trend_cockpit(tmp_path) -> None:
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

    assert result["btc_trend_cockpit"]["schema_version"] == "p45.btc_trend_cockpit.v2"
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID,
            )
        )
    assert row is not None
    assert row.payload["btc_trend_cockpit"]["schema_version"] == "p45.btc_trend_cockpit.v2"

    dashboard = p45_dashboard.latest_dashboard(db=db)
    overview = p45_dashboard.latest_overview(db=db)
    history = p45_dashboard.history("final-test", db=db)

    assert dashboard["btc_trend_cockpit"]["schema_version"] == "p45.btc_trend_cockpit.v2"
    assert overview["btc_trend_cockpit"]["schema_version"] == "p45.btc_trend_cockpit.v2"
    assert history is not None
    assert history["btc_trend_cockpit"]["schema_version"] == "p45.btc_trend_cockpit.v2"


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
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test",
                "modules": [
                    {
                        "radar_module": "kline_orderflow",
                        "module_score": 0.46,
                        "module_effective_score": 0.46,
                        "module_direction": "bullish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.9,
                        "signal_stage": "confirmed_signal",
                        "btc_implication": "upside_trend_confirmed",
                        "scores": {"btc_response_score": 78},
                        "support_drivers": ["vwap_acceptance"],
                        "pressure_drivers": [],
                        "metrics": [_metric("kline_orderflow", "flow_price_acceptance_15m", 0.2)],
                    },
                    {
                        "radar_module": "trade_structure_flow",
                        "module_score": 0.42,
                        "module_effective_score": 0.42,
                        "module_direction": "bullish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.9,
                        "signal_stage": "confirmed_signal",
                        "btc_implication": "spot_led_trend_confirmed",
                        "scores": {"price_acceptance_score": 75},
                        "support_drivers": ["spot_led_trend"],
                        "pressure_drivers": [],
                        "metrics": [_metric("trade_structure_flow", "price_acceptance_score", 0.2)],
                    },
                    {
                        "radar_module": "fund_flow",
                        "module_score": 0.28,
                        "module_effective_score": 0.28,
                        "module_direction": "bullish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.9,
                        "signal_stage": "confirmed_signal",
                        "btc_implication": "trend_confirmed",
                        "scores": {"btc_response_score": 70},
                        "support_drivers": ["etf_demand"],
                        "pressure_drivers": [],
                        "metrics": [_metric("fund_flow", "etf_flow_3d_usd", 0.2)],
                    },
                    {
                        "radar_module": "macro_radar",
                        "module_score": 0.25,
                        "module_effective_score": 0.25,
                        "module_direction": "bullish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.9,
                        "signal_stage": "confirmed_signal",
                        "btc_implication": "trend_confirmed",
                        "scores": {"btc_response_score": 60},
                        "support_drivers": ["macro_tailwind"],
                        "pressure_drivers": [],
                        "metrics": [_metric("macro_radar", "macro_impulse", 0.2)],
                    },
                ],
            }
        ],
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
