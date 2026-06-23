from sqlalchemy import select

from onlybtc.api import p45_dashboard
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID, run_p45_final_writer
from onlybtc.p45.timescale_judge import build_btc_timescale_judge, build_btc_timescale_judge_v22
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID


def test_timescale_judge_outputs_four_horizons_and_blocks_4h_confirmed() -> None:
    judge = build_btc_timescale_judge(
        btc_trend_cockpit=None,
        modules=[
            _module("kline_orderflow", "bullish", 0.90, "confirmed_signal", 90),
            _module("trade_structure_flow", "bullish", 0.80, "confirmed_signal", 85),
            _module("derivatives_crowding", "bullish", 0.60, "confirmed_signal", 80),
        ],
        contract_validation={"status": "passed"},
        data_quality={"metric_count": 3},
    )

    assert judge["schema_version"] == "p45.btc_timescale_judge.v2.1"
    assert set(judge["horizons"]) == {"4h", "24h", "3d", "7d"}
    assert judge["horizons"]["4h"]["signal_stage"] != "confirmed_signal"
    assert judge["cross_horizon"]["headline_stage"] != "confirmed"


def test_timescale_judge_requires_acceptance_for_24h_confirmation() -> None:
    judge = build_btc_timescale_judge(
        btc_trend_cockpit=None,
        modules=[
            _module("kline_orderflow", "bearish", -0.80, "confirmed_signal", 80),
            _module("trade_structure_flow", "bearish", -0.80, "confirmed_signal", 75),
            _module("derivatives_crowding", "bearish", -0.70, "confirmed_signal", 70),
            _module("fund_flow", "bearish", -0.60, "confirmed_signal", 70),
        ],
        contract_validation={"status": "passed"},
        data_quality={"metric_count": 4},
    )

    h24 = judge["horizons"]["24h"]
    assert h24["direction"] == "neutral" or h24["acceptance"]["state"] in {"rejected", "fragile"}
    assert h24["signal_stage"] != "confirmed_signal"


def test_timescale_judge_confirms_when_24h_and_3d_align_and_accept() -> None:
    judge = build_btc_timescale_judge(
        btc_trend_cockpit=None,
        modules=[
            _module("kline_orderflow", "bearish", -0.70, "confirmed_signal", -85),
            _module("trade_structure_flow", "bearish", -0.70, "confirmed_signal", -80),
            _module("derivatives_crowding", "bearish", -0.65, "confirmed_signal", -78),
            _module("fund_flow", "bearish", -0.70, "confirmed_signal", -82),
            _module("macro_radar", "bearish", -0.60, "confirmed_signal", -70),
            _module("treasury_credit", "bearish", -0.55, "confirmed_signal", -65),
        ],
        contract_validation={"status": "passed"},
        data_quality={"metric_count": 6},
    )

    assert judge["horizons"]["24h"]["acceptance"]["state"] == "accepted"
    assert judge["horizons"]["3d"]["acceptance"]["state"] == "accepted"
    assert judge["cross_horizon"]["headline_direction"] == "bearish"
    assert judge["cross_horizon"]["headline_stage"] == "confirmed"


def test_timescale_judge_keeps_7d_as_regime_context() -> None:
    judge = build_btc_timescale_judge(
        btc_trend_cockpit=None,
        modules=[
            _module("onchain_valuation", "bullish", 0.90, "confirmed_signal", 90),
            _module("btc_adoption", "bullish", 0.80, "confirmed_signal", 80),
        ],
        contract_validation={"status": "passed"},
        data_quality={"metric_count": 2},
    )

    assert judge["horizons"]["7d"]["evidence"]["regime_only"]
    assert judge["cross_horizon"]["headline_stage"] != "confirmed"


def test_timescale_judge_v22_uses_direct_state_and_caps_event_trust() -> None:
    legacy = build_btc_timescale_judge(
        btc_trend_cockpit=None,
        modules=[_module("kline_orderflow", "bullish", 0.70, "confirmed_signal", 80)],
        contract_validation={"status": "passed"},
        data_quality={"metric_count": 1},
    )
    direct_state = {
        "state_run_id": "state-test",
        "evidence_run_id": "evidence-test",
        "registry_run_id": "registry-test",
        "asof_ts": "2026-06-22T00:00:00+00:00",
        "source_fresh": True,
        "freshness_summary": {"missing_evidence": [], "stale_evidence": []},
        "horizons": {
            "4h": {
                "state": "event_distorted",
                "direction": "bullish",
                "direction_score": 82.0,
                "acceptance_score": 70.0,
                "trust_score": 45.0,
                "display_score": 36.9,
                "radar_context_bias": 20.0,
                "conflict_score": 0.0,
                "event_trust_cap": 45.0,
                "freshness_summary": {"missing_evidence": [], "stale_evidence": []},
                "semantic_flags": [],
                "evidence": [
                    {
                        "feature_id": "btc_direct_trend.price_structure.btc_return_4h",
                        "role": "trigger_eligible",
                        "score": 0.82,
                        "value": 0.82,
                        "freshness_state": "fresh",
                        "source_asof_ts": "2026-06-22T00:00:00+00:00",
                    }
                ],
            },
            "1d": {
                "state": "trend_building",
                "direction": "bullish",
                "direction_score": 50.0,
                "acceptance_score": 30.0,
                "trust_score": 45.0,
                "display_score": 22.5,
                "radar_context_bias": 0.0,
                "conflict_score": 0.0,
                "event_trust_cap": 45.0,
                "freshness_summary": {"missing_evidence": [], "stale_evidence": []},
                "semantic_flags": [],
                "evidence": [],
            },
        },
    }

    judge = build_btc_timescale_judge_v22(
        direct_trend_state=direct_state,
        legacy_judge=legacy,
        modules=[_module("kline_orderflow", "bullish", 0.70, "confirmed_signal", 80)],
    )

    assert judge["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert judge["fallback_schema_version"] == "p45.btc_timescale_judge.v2.1"
    assert judge["horizons"]["4h"]["direction_score"] == 82.0
    assert judge["horizons"]["4h"]["trust_score"] == 45.0
    assert judge["horizons"]["4h"]["radar_context"]["bias"] == 15.0
    assert judge["horizons"]["4h"]["event_trust"]["policy"] == "trust_cap_only_no_direction_delta"


def test_final_writer_persists_and_api_passthroughs_timescale_judge(tmp_path) -> None:
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

    assert result["btc_timescale_judge"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert result["btc_timescale_judge_v21"]["schema_version"] == "p45.btc_timescale_judge.v2.1"
    assert result["btc_timescale_replay_snapshot"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert result["btc_timescale_replay_snapshot"]["run_id"] == "final-test"
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID,
            )
        )
    assert row is not None
    assert row.payload["btc_timescale_judge"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert row.payload["btc_timescale_judge_v21"]["schema_version"] == "p45.btc_timescale_judge.v2.1"
    assert row.payload["btc_timescale_replay_snapshot"]["snapshot_id"]

    dashboard = p45_dashboard.latest_dashboard(db=db)
    overview = p45_dashboard.latest_overview(db=db)
    history = p45_dashboard.history("final-test", db=db)

    assert dashboard["btc_timescale_judge"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert overview["btc_timescale_judge"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert history is not None
    assert history["btc_timescale_judge"]["schema_version"] == "p45.btc_timescale_judge.v2.2"


def _module(module: str, direction: str, score: float, stage: str, response: float) -> dict:
    return {
        "radar_module": module,
        "module_score": score,
        "module_effective_score": score,
        "module_direction": direction,
        "module_effective_direction": direction,
        "module_quality_score": 0.9,
        "signal_stage": stage,
        "btc_implication": "trend_confirmed",
        "scores": {"btc_response_score": response},
        "support_drivers": [f"{module}_support"] if direction == "bullish" else [],
        "pressure_drivers": [f"{module}_pressure"] if direction == "bearish" else [],
    }


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
                    _module("kline_orderflow", "bullish", 0.46, "confirmed_signal", 78),
                    _module("trade_structure_flow", "bullish", 0.42, "confirmed_signal", 75),
                    _module("fund_flow", "bullish", 0.28, "confirmed_signal", 70),
                    _module("macro_radar", "bullish", 0.25, "confirmed_signal", 60),
                ],
            }
        ],
    }
