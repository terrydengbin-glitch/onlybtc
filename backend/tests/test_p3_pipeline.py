from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from onlybtc.algorithms.p3 import (
    SCORED_METRIC_MODULE_ID,
    SCORED_RADAR_MODULE_ID,
    build_scored_evidence,
    check_global_invalidations,
    check_module_invalidations,
    detect_event_windows,
    run_p3_pipeline,
)
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.service import ensure_source_registry, write_data_quality_snapshot


def test_p3_pipeline_writes_anomalies_divergences_invalidations_alerts_and_events(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        _add_series(
            session,
            "btc_price",
            "binance-btcusdt",
            now,
            [100.0, 100.2, 100.1, 100.0],
        )
        _add_series(
            session,
            "btc_funding_rate",
            "binance-btcusdt-funding",
            now,
            [0.0001, 0.00012, 0.00011, 0.0012],
        )
        _add_series(
            session,
            "btc_open_interest",
            "binance-btcusdt-open-interest",
            now,
            [1000.0, 1010.0, 1020.0, 1200.0],
        )
        _add_series(
            session,
            "etf_net_flow",
            "sosovalue-etf-flow",
            now,
            [100.0, 105.0, 108.0, 112.0],
        )
        _add_series(
            session,
            "cpi_days_until",
            "bls-calendar",
            now,
            [4.0, 3.0, 2.0, 1.0],
        )
        write_data_quality_snapshot(session, run_id="dq-p3-test")

    result = run_p3_pipeline(
        run_id="p3-test",
        metric_ids=[
            "btc_price",
            "btc_funding_rate",
            "btc_open_interest",
            "etf_net_flow",
            "cpi_days_until",
        ],
        db=db,
    )

    assert result["状态"] == "完成"
    assert result["anomalies"]["written"] >= 1
    assert result["divergences"]["written"] >= 1
    assert result["module_invalidations"]["written"] >= 2
    assert result["global_invalidations"]["written"] == 5
    assert result["event_windows"]["written"] >= 1
    assert result["alerts"]["created"] >= 1

    with db.session() as session:
        anomaly = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-test",
                schema.FeatureValue.module_id == "p3_anomaly_engine",
            )
        )
        divergence = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-test",
                schema.FeatureValue.module_id == "p3_divergence_engine",
            )
        )
        invalidation = session.scalar(
            select(schema.InvalidationEvent).where(schema.InvalidationEvent.run_id == "p3-test")
        )
        alert = session.scalar(select(schema.AlgorithmAlert))
        event = session.scalar(select(schema.AlertEvent))

    assert anomaly is not None
    assert anomaly.metadata_json["metric_id"] in {
        "btc_funding_rate",
        "btc_open_interest",
        "etf_net_flow",
    }
    assert divergence is not None
    assert "metrics" in divergence.metadata_json
    assert invalidation is not None
    assert invalidation.payload["scope"] in {"module", "global"}
    assert alert is not None
    assert alert.level in {"watch", "warning", "critical"}
    assert event is not None


def test_p3_alert_lifecycle_reuses_stable_alert_id(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        _add_series(
            session,
            "btc_price",
            "binance-btcusdt",
            now,
            [100.0, 100.2, 100.1, 100.0],
        )
        _add_series(
            session,
            "btc_funding_rate",
            "binance-btcusdt-funding",
            now,
            [0.0001, 0.00012, 0.00011, 0.0012],
        )
        write_data_quality_snapshot(session, run_id="dq-p3-test")

    run_p3_pipeline(
        run_id="p3-test-1",
        metric_ids=["btc_price", "btc_funding_rate"],
        db=db,
    )
    run_p3_pipeline(
        run_id="p3-test-2",
        metric_ids=["btc_price", "btc_funding_rate"],
        db=db,
    )

    with db.session() as session:
        alerts = session.scalars(select(schema.AlgorithmAlert)).all()
        events = session.scalars(select(schema.AlertEvent)).all()

    assert len(alerts) >= 1
    assert len({alert.alert_id for alert in alerts}) == len(alerts)
    assert len(events) >= len(alerts) + 1
    assert any(event.event_type in {"cooling", "escalated", "downgraded"} for event in events)


def test_p3_pipeline_live_mode_ignores_mock_history(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        _add_series(
            session,
            "btc_price",
            "binance-btcusdt",
            now,
            [100.0, 100.1, 100.2, 100.1],
            run_mode="live",
        )
        _add_series(
            session,
            "btc_funding_rate",
            "binance-btcusdt-funding",
            now,
            [0.0001, 0.00011, 0.00012, 0.00011],
            run_mode="live",
        )
        _add_series(
            session,
            "btc_price",
            "binance-btcusdt",
            now,
            [1000.0, 100.0, 2000.0, 50.0],
            run_mode="mock",
        )
        _add_series(
            session,
            "btc_funding_rate",
            "binance-btcusdt-funding",
            now,
            [0.01, -0.01, 0.02, -0.02],
            run_mode="mock",
        )

    result = run_p3_pipeline(
        run_id="p3-live-only-test",
        metric_ids=["btc_price", "btc_funding_rate"],
        run_mode="live",
        db=db,
    )

    assert result["run_mode"] == "live"
    with db.session() as session:
        features = session.scalars(
            select(schema.FeatureValue).where(schema.FeatureValue.run_id == "p3-live-only-test")
        ).all()

    p3_features = [row for row in features if row.module_id.startswith("p3_")]

    assert p3_features
    assert all(row.metadata_json["run_mode"] == "live" for row in p3_features)


def test_module_invalidations_use_same_run_radar_outputs(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        _add_series(
            session,
            "btc_price",
            "binance-btcusdt",
            now,
            [100.0, 100.1, 100.2, 100.3],
        )
        _add_series(
            session,
            "btc_funding_rate",
            "binance-btcusdt-funding",
            now,
            [0.0001, 0.00011, 0.00012, 0.00013],
        )

    analyze_radars(run_id="stale-radar-run", run_mode="mock", db=db)
    result = run_p3_pipeline(
        run_id="p3-same-run-test",
        metric_ids=["btc_price", "btc_funding_rate"],
        run_mode="live",
        db=db,
    )

    assert result["module_invalidations"]["written"] == 28
    with db.session() as session:
        events = session.scalars(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-same-run-test",
                schema.InvalidationEvent.payload["scope"].as_string() == "module",
            )
        ).all()
        p3_radar_rows = session.scalars(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "p3-same-run-test"
            )
        ).all()

    assert len(p3_radar_rows) == 14
    assert events
    assert all(event.payload["run_mode"] == "live" for event in events)


def test_module_invalidation_marks_business_lagging_as_near_trigger(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_module_outputs(
        db,
        "p3-business-lagging-test",
        {
            "trade_structure_flow": {
                "signal": "bullish",
                "invalidation_signals": {
                    "business_lagging_metrics": ["taker_buy_sell_ratio"],
                },
            }
        },
    )

    check_module_invalidations(run_id="p3-business-lagging-test", db=db)

    with db.session() as session:
        event = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-business-lagging-test",
                schema.InvalidationEvent.condition_id
                == "trade_structure_flow_data_quality_invalidation",
            )
        )

    assert event is not None
    assert event.status == "near_trigger"
    assert event.action == "reduce_confidence"
    assert event.payload["reason_code"] == "business_lagging_core_metrics"
    assert event.payload["affected_metrics"] == ["taker_buy_sell_ratio"]
    assert event.payload["evidence"]["reason_code"] == "business_lagging_core_metrics"
    assert event.payload["evidence"]["affected_metrics"] == ["taker_buy_sell_ratio"]


def test_provider_required_gap_does_not_trigger_module_invalidation(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_module_outputs(
        db,
        "p3-provider-required-test",
        {
            "onchain_valuation": {
                "invalidation_signals": {
                    "provider_required_metrics": ["whale_flow", "miner_flow"],
                },
            }
        },
    )

    check_module_invalidations(run_id="p3-provider-required-test", db=db)

    with db.session() as session:
        event = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-provider-required-test",
                schema.InvalidationEvent.condition_id
                == "onchain_valuation_data_quality_invalidation",
            )
        )

    assert event is not None
    assert event.status == "not_triggered"
    assert event.payload["evidence"]["provider_required_metrics"] == [
        "whale_flow",
        "miner_flow",
    ]


def test_scored_evidence_uses_btc_semantic_rules(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="p3-semantic-test",
                module_id="fund_flow",
                schema_version="1.0",
                payload={
                    "run_id": "p3-semantic-test",
                    "module_id": "fund_flow",
                    "signal": "bullish",
                    "strength": 0.5,
                    "confidence": 0.9,
                    "features": [
                        _feature("etf_net_flow", -100_000_000.0, 0.30, "bullish", 0.30),
                    ],
                    "evidence_summary": {"net_score": 0.30, "quality_explanation": {}},
                },
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="p3-semantic-test",
                module_id="event_policy",
                schema_version="1.0",
                payload={
                    "run_id": "p3-semantic-test",
                    "module_id": "event_policy",
                    "signal": "bearish",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": [
                        _feature("macro_surprise_score", 0.0, 0.04, "bearish", -0.04),
                    ],
                    "evidence_summary": {"net_score": -0.04, "quality_explanation": {}},
                },
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="p3-semantic-test",
                module_id="onchain_valuation",
                schema_version="1.0",
                payload={
                    "run_id": "p3-semantic-test",
                    "module_id": "onchain_valuation",
                    "signal": "bearish",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": [
                        _feature("mvrv_zscore", 0.8, 0.18, "bearish", -0.18),
                    ],
                    "evidence_summary": {"net_score": -0.18, "quality_explanation": {}},
                },
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="p3-semantic-test",
                module_id="treasury_credit",
                schema_version="1.0",
                payload={
                    "run_id": "p3-semantic-test",
                    "module_id": "treasury_credit",
                    "signal": "bullish",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": [
                        _feature("treasury_10y", 4.6, 0.20, "bullish", 0.02),
                    ],
                    "evidence_summary": {"net_score": 0.02, "quality_explanation": {}},
                },
            )
        )

    result = build_scored_evidence(run_id="p3-semantic-test", db=db)

    by_metric = {item["metric_id"]: item for item in result["metric_items"]}
    assert by_metric["etf_net_flow"]["direction"] == "bearish"
    assert by_metric["etf_net_flow"]["metric_score"] < 0
    assert by_metric["etf_net_flow"]["metric_effective_score"] < 0
    assert by_metric["etf_net_flow"]["freshness_weight"] == 1.0
    assert by_metric["etf_net_flow"]["horizon_weight"] == 1.0
    assert by_metric["etf_net_flow"]["duplicate_adjustment"] <= 1.0
    assert by_metric["etf_net_flow"]["horizon_tags"] == []
    assert by_metric["etf_net_flow"]["duplicate_group_id"] == "etf_net_flow"
    assert by_metric["etf_net_flow"]["semantic_rule_id"] == ("semantic.etf_flow.absolute_negative")
    assert by_metric["macro_surprise_score"]["direction"] == "neutral"
    assert by_metric["macro_surprise_score"]["metric_score"] == 0.0
    assert by_metric["macro_surprise_score"]["score_bucket_v2"] == "neutral_confirmed"
    assert by_metric["macro_surprise_score"]["decision_zero"] is False
    assert by_metric["mvrv_zscore"]["direction"] == "bullish"
    assert by_metric["mvrv_zscore"]["metric_score"] > 0
    assert by_metric["treasury_10y"]["direction"] == "bearish"
    assert by_metric["treasury_10y"]["metric_score"] < 0

    with db.session() as session:
        metric_rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-semantic-test",
                schema.FeatureValue.module_id == SCORED_METRIC_MODULE_ID,
            )
        ).all()
        module_rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-semantic-test",
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
            )
        ).all()

    assert len(metric_rows) == 4
    treasury = next(
        row for row in module_rows if row.metadata_json["radar_module"] == "treasury_credit"
    )
    assert treasury.metadata_json["module_score"] == 0.0
    assert "module_effective_score" in treasury.metadata_json
    assert treasury.metadata_json["module_effective_direction"] == "neutral"
    assert treasury.metadata_json["module_direction"] == "neutral"
    assert treasury.metadata_json["trend_state"] == "treasury_credit_neutral"
    assert treasury.metadata_json["coverage_score"] == 1.0
    assert "conflict_score" in treasury.metadata_json
    assert "freshness_score" in treasury.metadata_json
    assert "module_raw_score" in treasury.metadata_json
    assert "module_final_score" in treasury.metadata_json
    assert "module_state" in treasury.metadata_json
    assert "direction_score" in treasury.metadata_json
    assert "risk_score" in treasury.metadata_json
    assert "confidence_score" in treasury.metadata_json
    assert "trend_state" in treasury.metadata_json
    assert "trend_state_reason" in treasury.metadata_json
    assert treasury.metadata_json["top_contributors"]


def test_scored_evidence_applies_p3_c22_high_priority_rules(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    btc_price = _feature("btc_price", 105.0, 0.12, "bearish", -0.02)
    btc_price["change_24h"] = -0.02
    etf_flow = _feature("etf_net_flow", -100_000_000.0, 0.30, "bullish", 0.30)
    etf_flow["change_24h"] = 0.5
    cpi_days = _feature("cpi_days_until", 1.0, 0.18, "bearish", -0.18)
    oi = _feature("btc_open_interest", 1200.0, 0.5, "neutral", 0.0)
    oi["change_24h"] = 0.05
    funding = _feature("btc_funding_rate", 0.0001, 0.5, "neutral", 0.0)
    sth_cost = _feature("sth_cost_basis", 100.0, 0.15, "neutral", 0.0)

    with db.session() as session:
        for module_id, signal, features, net_score in (
            ("btc_total_state", "bearish", [btc_price], -0.02),
            ("fund_flow", "bullish", [etf_flow], 0.30),
            ("event_policy", "bearish", [cpi_days], -0.18),
            ("derivatives_crowding", "neutral", [oi, funding], 0.0),
            ("onchain_valuation", "neutral", [sth_cost], 0.0),
        ):
            session.add(
                schema.ModuleJsonOutput(
                    run_id="p3-c22-semantic-test",
                    module_id=module_id,
                    schema_version="1.0",
                    payload={
                        "run_id": "p3-c22-semantic-test",
                        "module_id": module_id,
                        "signal": signal,
                        "strength": 0.2,
                        "confidence": 0.9,
                        "features": features,
                        "evidence_summary": {
                            "net_score": net_score,
                            "quality_explanation": {},
                        },
                    },
                )
            )

    result = build_scored_evidence(run_id="p3-c22-semantic-test", db=db)
    by_metric = {item["metric_id"]: item for item in result["metric_items"]}

    assert by_metric["etf_net_flow"]["direction"] == "bearish"
    assert by_metric["etf_net_flow"]["flow_state"] == "bearish_but_improving"
    assert by_metric["etf_net_flow"]["flow_momentum_score"] > 0
    assert by_metric["cpi_days_until"]["direction"] == "neutral"
    assert by_metric["cpi_days_until"]["signal_type"] == "risk_signal"
    assert by_metric["cpi_days_until"]["event_risk_score"] == 1.0
    assert by_metric["cpi_days_until"]["score_bucket_v2"] == "context_only"
    assert by_metric["cpi_days_until"]["decision_zero"] is False
    assert by_metric["btc_open_interest"]["direction"] == "bearish"
    assert by_metric["btc_open_interest"]["crowding_state"] == "long_crowding_downside"
    assert by_metric["btc_open_interest"]["leverage_risk_score"] >= 0.75
    assert by_metric["sth_cost_basis"]["direction"] == "bullish"
    assert by_metric["sth_cost_basis"]["valuation_state"] == "above_sth_cost_basis"
    assert "thresholds_used" in by_metric["sth_cost_basis"]

    with db.session() as session:
        modules = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-c22-semantic-test",
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
            )
        ).all()
    by_module = {row.metadata_json["radar_module"]: row.metadata_json for row in modules}
    assert by_module["event_policy"]["semantic_profile_version"] == "p3.c43.event_policy.v2.1"
    assert by_module["event_policy"]["module_direction"] == "neutral"
    assert by_module["event_policy"]["module_score"] == 0
    assert by_module["event_policy"]["trend_state"] == "cpi_caution"
    assert by_module["event_policy"]["risk_score"] >= 60
    assert by_module["event_policy"]["zero_breakdown"]["context_zero_ratio"] == 1.0
    assert by_module["event_policy"]["decision_zero_metric_count"] == 0
    assert by_module["event_policy"]["event_risk_lock_level"] == "soft"
    assert by_module["event_policy"]["trade_gate"]["allow_add_position"] is False
    assert by_module["event_policy"]["trade_gate"]["allow_breakout_entry"] is False
    assert by_module["derivatives_crowding"]["trend_state"] in {
        "bearish_pressure",
        "conflict_no_trade",
    }
    assert by_module["derivatives_crowding"]["oi_funding_combo_applied"] is True
    assert by_module["fund_flow"]["direction_score"] < 0
    assert "fund_flow_absolute_direction" in by_module["fund_flow"]
    assert by_module["onchain_valuation"]["cost_basis_combo_applied"] is True


def test_kline_orderflow_volume_spike_down_is_bearish_pressure(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run_id = "p3-c29-kline-test"
    features = [
        _feature("btc_return_1h", -0.0115, 0.18, "bearish", -0.02),
        _feature("btc_return_4h", -0.02, 0.12, "bearish", -0.02),
        _feature("btc_return_24h", -0.055, 0.10, "bearish", -0.02),
        _feature("btc_drawdown_24h", -0.07, 0.08, "bearish", -0.01),
        _feature("btc_close_position_1h", 0.18, 0.14, "bearish", -0.02),
        _feature("btc_candle_body_pct_1h", 0.72, 0.06, "mixed", 0.0),
        _feature("btc_upper_wick_ratio_1h", 0.10, 0.06, "neutral", 0.0),
        _feature("btc_lower_wick_ratio_1h", 0.18, 0.06, "mixed", 0.0),
        _feature("btc_volume_zscore_1h", 3.2, 0.10, "neutral", 0.0),
        _feature("btc_breakdown_24h_low", 0.0, 0.06, "neutral", 0.0),
        _feature("btc_breakout_24h_high", 0.0, 0.06, "neutral", 0.0),
        _feature("btc_rebound_quality_1h", 0.0, 0.04, "neutral", 0.0),
        _feature("btc_down_volume_pressure", 0.015, 0.04, "bearish", -0.01),
        _feature("btc_1h_volume", 661.0, 0.0, "neutral", 0.0),
    ]
    for item in features:
        if item["metric_id"] in {"btc_volume_zscore_1h", "btc_1h_volume"}:
            item["role"] = "confirmation_factor"
            item["affects_signal"] = False

    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="kline_orderflow",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "kline_orderflow",
                    "signal": "bullish",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.2, "quality_explanation": {}},
                },
            )
        )

    result = build_scored_evidence(run_id=run_id, db=db)
    by_metric = {item["metric_id"]: item for item in result["metric_items"]}
    assert by_metric["btc_return_1h"]["kline_trend_state"] == "bearish_pressure"
    assert by_metric["btc_return_1h"]["metric_score"] < 0
    assert by_metric["btc_volume_zscore_1h"]["metric_score"] == 0
    assert by_metric["btc_volume_zscore_1h"]["score_bucket_v2"] == "context_only"

    with db.session() as session:
        module = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "kline_orderflow.scored_module",
            )
        )
    assert module is not None
    assert module.metadata_json["trend_state"] == "bearish_pressure"
    assert module.metadata_json["kline_trend_state"] == "bearish_pressure"
    assert "volume" in module.metadata_json["volume_interpretation"]


def test_derivatives_crowding_funding_mild_oi_flat_is_not_bullish(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run_id = "p3-c32-derivatives-test"
    funding = _feature("btc_funding_rate", 0.00006462, 0.5, "neutral", 0.0)
    funding["change_24h"] = -0.1
    oi = _feature("btc_open_interest", 102629.84, 0.5, "neutral", 0.0)
    oi["change_24h"] = 0.0

    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="derivatives_crowding",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "derivatives_crowding",
                    "signal": "neutral",
                    "strength": 0.2,
                    "confidence": 0.98,
                    "features": [funding, oi],
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )

    result = build_scored_evidence(run_id=run_id, db=db)
    by_metric = {item["metric_id"]: item for item in result["metric_items"]}
    funding_item = by_metric["btc_funding_rate"]
    oi_item = by_metric["btc_open_interest"]

    assert funding_item["direction"] == "neutral"
    assert funding_item["metric_score"] > 0
    assert funding_item["funding_state"] == "funding_mild"
    assert funding_item["crowding_signal"] == "not_hot"
    assert funding_item["direction_contribution"] == "mild_support"
    assert funding_item["trend_confirmation"] == "unconfirmed"
    assert oi_item["oi_state"] == "oi_flat"
    assert oi_item["oi_confirmation"] == "none"
    assert oi_item["oi_trend_signal"] == "unconfirmed"

    with db.session() as session:
        module = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "derivatives_crowding.scored_module",
            )
        )
    assert module is not None
    derivatives = module.metadata_json
    assert derivatives["module_effective_score"] < 0.10
    assert derivatives["module_effective_direction"] == "neutral"
    assert derivatives["module_effective_bias"] == "mild_support"
    assert derivatives["trend_direction"] == "neutral"
    assert derivatives["trend_state"] == "neutral_wait_confirm"
    assert derivatives["crowding_state"] == "not_crowded"
    assert derivatives["leverage_heat_state"] == "low_to_normal"
    assert derivatives["confirmation_state"] == "unconfirmed"
    funding_contributor = next(
        item
        for item in derivatives["top_contributors"]
        if item["metric_id"] == "btc_funding_rate"
    )
    assert funding_contributor["direction"] == "neutral"
    assert funding_contributor["contribution_side"] == "positive"
    assert funding_contributor["direction_contribution"] == "mild_support"
    assert funding_contributor["funding_state"] == "funding_mild"
    assert funding_contributor["crowding_signal"] == "not_hot"
    assert funding_contributor["trend_confirmation"] == "unconfirmed"


def test_btc_total_state_v2_combines_price_oi_and_funding_states(tmp_path: Path) -> None:
    cases = [
        ("up_oi_up_mild", 0.012, 0.010, 0.00008, "price_up_confirmed", "bullish", 0.35, "healthy_participation", "normal"),
        ("up_oi_down", 0.012, -0.010, 0.00008, "short_covering_bounce", "bullish", 0.18, "short_covering", "normal"),
        ("up_oi_up_extreme", 0.012, 0.010, 0.0012, "overheated_upside", "bullish", 0.20, "long_crowding", "extreme"),
        ("down_oi_up_positive", -0.012, 0.010, 0.0004, "long_crowding_downside", "bearish", -0.42, "long_crowding", "elevated"),
        ("down_oi_down", -0.012, -0.010, 0.00008, "deleveraging_downside", "bearish", -0.25, "deleveraging", "normal"),
        ("flat_oi_flat", 0.0005, 0.0004, 0.00008, "neutral_wait_confirm", "neutral", 0.0, "perp_neutral", "normal"),
        ("negative_funding_stable", 0.0005, 0.0004, -0.0002, "short_squeeze_potential", "neutral", 0.0, "short_crowding", "normal"),
    ]

    for suffix, price_change, oi_change, funding, state, direction, score, perp, risk in cases:
        module, metrics = _btc_total_scored_from_features(
            tmp_path,
            _btc_total_features(price_change=price_change, oi_change=oi_change, funding=funding),
            run_id=f"p3-c41-btc-total-{suffix}",
        )
        assert module["semantic_profile_version"] == "p3.c41.btc_total_state.v2"
        assert module["btc_short_term_state"] == state
        assert module["module_direction"] == direction
        assert module["module_score"] == score
        assert module["module_effective_score"] == score
        assert module["price_state"]["affects_direction"] is True
        assert module["perp_state"]["state"] == perp
        assert module["perp_state"]["risk_state"] == risk
        assert module["cycle_context"]["affects_direction"] is False
        assert module["audit_context"]["affects_direction"] is False
        for metric_id in (
            "btc_halving_estimated_days",
            "btc_halving_blocks_remaining",
            "btc_block_height",
        ):
            assert metrics[metric_id]["metric_score"] == 0.0
            assert metrics[metric_id]["metric_effective_score"] == 0.0
            assert metrics[metric_id]["driver_eligible"] is False
            assert metrics[metric_id]["score_bucket_v2"] == "context_only"
        driver_metrics = {
            driver.get("metric_id")
            for driver in module.get("support_drivers", []) + module.get("pressure_drivers", [])
        }
        assert "btc_halving_estimated_days" not in driver_metrics
        assert "btc_halving_blocks_remaining" not in driver_metrics
        assert "btc_block_height" not in driver_metrics


def test_derivatives_crowding_long_short_ratio_adds_positioning_semantics(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run_id = "p3-c34-long-short-ratio-test"
    funding = _feature("btc_funding_rate", 0.00035, 0.25, "neutral", 0.0)
    funding["change_24h"] = 0.1
    oi = _feature("btc_open_interest", 110000.0, 0.20, "neutral", 0.0)
    oi["change_24h"] = 0.08
    global_ratio = _feature(
        "btc_global_long_short_account_ratio",
        1.42,
        0.10,
        "neutral",
        0.0,
    )
    top_account_ratio = _feature(
        "btc_top_long_short_account_ratio",
        1.55,
        0.15,
        "neutral",
        0.0,
    )
    top_position_ratio = _feature(
        "btc_top_long_short_position_ratio",
        2.15,
        0.25,
        "neutral",
        0.0,
    )

    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="derivatives_crowding",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "derivatives_crowding",
                    "signal": "neutral",
                    "strength": 0.2,
                    "confidence": 0.98,
                    "features": [
                        funding,
                        oi,
                        global_ratio,
                        top_account_ratio,
                        top_position_ratio,
                    ],
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )

    result = build_scored_evidence(run_id=run_id, db=db)
    by_metric = {item["metric_id"]: item for item in result["metric_items"]}
    top_position = by_metric["btc_top_long_short_position_ratio"]

    assert top_position["direction"] == "neutral"
    assert top_position["metric_score"] < 0
    assert top_position["positioning_signal"] == "extreme_long"
    assert top_position["crowding_contribution"] == "mild_pressure"
    assert top_position["positioning_scope"] == "top_position"
    assert top_position["semantic_rule_id"] == "semantic.derivatives.long_short_positioning"

    with db.session() as session:
        module = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "derivatives_crowding.scored_module",
            )
        )
    assert module is not None
    derivatives = module.metadata_json
    assert derivatives["positioning_state"] == "long_skew"
    assert derivatives["top_positioning_state"] == "top_extreme_long"
    assert derivatives["top_trader_bias_state"] == "top_long_skew"
    assert derivatives["long_short_squeeze_risk"] == "long_squeeze_risk"
    assert derivatives["long_short_combo_applied"] is True
    assert derivatives["crowding_state"] == "long_crowded"
    assert derivatives["module_effective_direction"] != "bullish"


def test_kline_derived_metric_self_direction_stays_separate_from_composite_state(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run_id = "p3-c31-kline-self-direction"
    features = [
        _feature("btc_return_1h", -0.00023458478757365508, 0.18, "bearish", -0.01),
        _feature("btc_return_4h", 0.00976079820307496, 0.12, "bullish", 0.01),
        _feature("btc_return_24h", -0.01654616796146502, 0.10, "bearish", -0.01),
        _feature("btc_drawdown_24h", -0.020413076447731382, 0.08, "bearish", -0.01),
        _feature("btc_close_position_1h", 0.42350332594236273, 0.14, "bearish", -0.01),
        _feature("btc_candle_body_pct_1h", 0.06552106430153563, 0.06, "neutral", 0.0),
        _feature("btc_upper_wick_ratio_1h", 0.5109756097561017, 0.06, "bearish", -0.01),
        _feature("btc_lower_wick_ratio_1h", 0.42350332594236273, 0.06, "neutral", 0.0),
        _feature("btc_volume_zscore_1h", 0.038183047738014855, 0.10, "neutral", 0.0),
        _feature("btc_breakdown_24h_low", 0.0, 0.06, "neutral", 0.0),
        _feature("btc_breakout_24h_high", 0.0, 0.06, "neutral", 0.0),
        _feature("btc_rebound_quality_1h", 0.0, 0.04, "neutral", 0.0),
        _feature("btc_down_volume_pressure", 0.0000006851931128990567, 0.04, "bearish", -0.01),
    ]
    for item in features:
        if item["metric_id"] == "btc_volume_zscore_1h":
            item["role"] = "confirmation_factor"
            item["affects_signal"] = False

    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="kline_orderflow",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "kline_orderflow",
                    "signal": "bearish",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": -0.1, "quality_explanation": {}},
                },
            )
        )

    result = build_scored_evidence(run_id=run_id, db=db)
    by_metric = {item["metric_id"]: item for item in result["metric_items"]}

    assert by_metric["btc_return_1h"]["direction"] == "bearish"
    assert by_metric["btc_return_1h"]["metric_self_direction"] == "bearish"
    assert by_metric["btc_return_1h"]["metric_score"] < 0
    assert by_metric["btc_return_1h"]["module_composite_state"] == "neutral_wait_confirm"
    assert by_metric["btc_return_1h"]["module_composite_direction"] == "bullish"
    assert by_metric["btc_return_1h"]["kline_composite_contribution"] > 0
    assert by_metric["btc_return_24h"]["direction"] == "bearish"
    assert by_metric["btc_return_24h"]["metric_self_direction"] == "bearish"
    assert by_metric["btc_return_4h"]["direction"] == "bullish"
    assert by_metric["btc_return_4h"]["metric_self_direction"] == "bullish"
    assert "module composite state" in by_metric["btc_return_1h"]["score_reason"]


def test_kline_tiny_effective_score_stays_neutral(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run_id = "p3-c35-kline-deadband"
    features = [
        _feature("btc_return_1h", 0.0002, 0.18, "bullish", 0.0),
        _feature("btc_return_4h", 0.0, 0.12, "neutral", 0.0),
        _feature("btc_return_24h", 0.0, 0.10, "neutral", 0.0),
        _feature("btc_close_position_1h", 0.5, 0.14, "neutral", 0.0),
        _feature("btc_upper_wick_ratio_1h", 0.0, 0.06, "neutral", 0.0),
        _feature("btc_candle_body_pct_1h", 0.0, 0.06, "neutral", 0.0),
    ]
    for item in features:
        item["semantic_rule_id"] = "semantic.kline_orderflow.composite"
        item["kline_trend_state"] = "neutral_wait_confirm"
        item["module_composite_state"] = "neutral_wait_confirm"

    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="kline_orderflow",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "kline_orderflow",
                    "signal": "bullish",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.1, "quality_explanation": {}},
                },
            )
        )

    build_scored_evidence(run_id=run_id, db=db)

    with db.session() as session:
        module = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "kline_orderflow.scored_module",
            )
        )
    assert module is not None
    metadata = module.metadata_json
    assert 0 < metadata["module_effective_score"] < 0.05
    assert metadata["module_effective_direction"] == "neutral"
    assert metadata["module_effective_bias"] == "neutral"
    assert metadata["display_state"] == "neutral_wait_confirm"


def test_kline_wait_confirm_with_support_bias_does_not_confirm_bullish(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run_id = "p3-c36-kline-support-wait"
    features = [
        _feature("btc_return_1h", 0.006, 0.18, "bullish", 0.0),
        _feature("btc_return_4h", 0.012, 0.12, "bullish", 0.0),
        _feature("btc_return_24h", 0.024, 0.10, "bullish", 0.0),
        _feature("btc_close_position_1h", 0.62, 0.14, "bullish", 0.0),
        _feature("btc_candle_body_pct_1h", 0.24, 0.06, "bullish", 0.0),
        _feature("btc_upper_wick_ratio_1h", 0.08, 0.06, "neutral", 0.0),
        _feature("btc_lower_wick_ratio_1h", 0.10, 0.06, "neutral", 0.0),
        _feature("btc_volume_zscore_1h", 0.8, 0.10, "neutral", 0.0),
        _feature("btc_breakdown_24h_low", 0.0, 0.06, "neutral", 0.0),
        _feature("btc_breakout_24h_high", 0.0, 0.06, "neutral", 0.0),
    ]
    for item in features:
        if item["metric_id"] == "btc_volume_zscore_1h":
            item["role"] = "confirmation_factor"
            item["affects_signal"] = False

    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="kline_orderflow",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "kline_orderflow",
                    "signal": "bullish",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.2, "quality_explanation": {}},
                },
            )
        )

    build_scored_evidence(run_id=run_id, db=db)

    with db.session() as session:
        module = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "kline_orderflow.scored_module",
            )
        )
    assert module is not None
    metadata = module.metadata_json
    assert metadata["module_effective_score"] >= 0.12
    assert metadata["module_effective_direction"] == "bullish"
    assert metadata["module_effective_bias"] == "support"
    assert metadata["trend_state"] == "neutral_wait_confirm"
    assert metadata["display_state"] == "neutral_wait_confirm"
    assert "waits for confirmation" in metadata["display_summary"]


def test_kline_raw_ohlcv_does_not_fallback_to_bullish_radar_rule(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    run_id = "p3-c30-kline-raw-guard"
    features = [
        _feature("btc_1h_open", 74753.94, 0.2, "neutral", 0.0),
        _feature("btc_1h_high", 75262.86, 0.2, "bullish", 0.04),
        _feature("btc_1h_low", 74753.93, 0.2, "bullish", 0.04),
        _feature("btc_1h_close", 75213.9, 0.2, "bullish", 0.04),
        _feature("btc_1h_volume", 815.89, 0.25, "bullish", 0.25),
    ]

    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="kline_orderflow",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "kline_orderflow",
                    "signal": "bullish",
                    "strength": 0.5,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.37, "quality_explanation": {}},
                },
            )
        )

    result = build_scored_evidence(run_id=run_id, db=db)
    by_metric = {item["metric_id"]: item for item in result["metric_items"]}
    for metric_id in {"btc_1h_high", "btc_1h_low", "btc_1h_close", "btc_1h_volume"}:
        assert by_metric[metric_id]["metric_score"] == 0
        assert by_metric[metric_id]["score_bucket"] == "zero"
        assert by_metric[metric_id]["score_bucket_v2"] == "context_only"
        assert by_metric[metric_id]["semantic_rule_id"] == "semantic.kline.raw_context_only"

    with db.session() as session:
        module = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "kline_orderflow.scored_module",
            )
        )
    assert module is not None
    assert module.metadata_json["module_score"] == 0


def test_scored_evidence_adds_p3_c28_p1_module_semantic_profiles(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    module_features = {
        "options_volatility": [
            _feature("options_iv", 75.0, 0.2, "bearish", -0.08),
            _feature("put_call_ratio", 1.35, 0.2, "bearish", -0.07),
        ],
        "asia_risk": [
            _feature("usdcnh", 7.4, 0.18, "bearish", -0.04),
            _feature("jgb_10y", 1.3, 0.12, "bearish", -0.03),
        ],
        "crypto_breadth": [
            _feature("top50_strength", 0.65, 0.2, "bullish", 0.08),
            _feature("eth_btc", 0.03, 0.2, "bullish", 0.04),
        ],
        "trade_structure_flow": [
            _feature("taker_buy_sell_ratio", 1.4, 0.2, "bullish", 0.09),
            _feature("stablecoin_buying_power_proxy", 1.2, 0.08, "bullish", 0.04),
            _feature("liquidation_short_usd", 1000.0, 0.12, "bullish", 0.03),
        ],
        "btc_adoption": [
            _feature("active_addresses", 500_000.0, 0.25, "bullish", 0.05),
        ],
    }
    with db.session() as session:
        for module_id, features in module_features.items():
            session.add(
                schema.ModuleJsonOutput(
                    run_id="p3-c28-semantic-test",
                    module_id=module_id,
                    schema_version="1.0",
                    payload={
                        "run_id": "p3-c28-semantic-test",
                        "module_id": module_id,
                        "signal": "mixed",
                        "strength": 0.2,
                        "confidence": 0.9,
                        "features": features,
                        "evidence_summary": {
                            "net_score": sum(float(item["score"]) for item in features),
                            "quality_explanation": {},
                        },
                    },
                )
            )

    build_scored_evidence(run_id="p3-c28-semantic-test", db=db)
    with db.session() as session:
        modules = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-c28-semantic-test",
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
            )
        ).all()
    by_module = {row.metadata_json["radar_module"]: row.metadata_json for row in modules}
    assert (
        by_module["options_volatility"]["semantic_profile_version"]
        == "p3.c42.options_volatility.v2.1"
    )
    assert by_module["options_volatility"]["module_direction"] == "neutral"
    assert by_module["options_volatility"]["module_score"] == 0
    assert by_module["options_volatility"]["options_short_term_state"] == "data_quality_degraded"
    assert by_module["options_volatility"]["data_quality"]["state"] == "data_quality_degraded"
    assert by_module["asia_risk"]["asia_risk_composite"] == "risk_off"
    assert by_module["crypto_breadth"]["crypto_breadth_regime"] == "risk_expansion"
    assert by_module["trade_structure_flow"]["aggressive_flow_state"] == "strong_buying_pressure"
    assert by_module["btc_adoption"]["adoption_horizon_focus"] == "structural"


def test_crypto_breadth_neutral_wait_confirm_clamps_bullish_mismatch(tmp_path: Path) -> None:
    profile = _crypto_breadth_profile_from_values(
        tmp_path,
        "neutral-clamp",
        {
            "btc_return_24h_pct": 0.004,
            "top50_advance_pct_24h": 0.56,
            "total2_return_24h_pct": 0.0,
            "total2_vs_btc_return_24h_pct": -0.001,
            "eth_btc_return_24h_pct": 0.0,
            "sector_heat": 50.0,
        },
    )

    assert profile["crypto_breadth_state"] == "neutral_wait_confirm"
    assert profile["module_direction"] == "neutral"
    assert abs(profile["module_score"]) <= 0.08


def test_crypto_breadth_positive_fallback_upgrades_to_explainable_state(tmp_path: Path) -> None:
    profile = _crypto_breadth_profile_from_values(
        tmp_path,
        "positive-fallback",
        {
            "btc_return_24h_pct": 0.003,
            "top50_advance_pct_24h": 0.57,
            "total2_return_24h_pct": 0.006,
            "total2_vs_btc_return_24h_pct": 0.003,
            "eth_btc_return_24h_pct": 0.001,
            "sector_heat": 55.0,
        },
    )

    assert profile["module_score"] >= 0.12
    assert profile["crypto_breadth_state"] == "alt_beta_rotation"
    assert profile["module_direction"] == "bullish"


def test_macro_radar_relative_basis_classifies_btc_lagging_not_missing(tmp_path: Path) -> None:
    profile = _macro_radar_profile_from_values(
        tmp_path,
        "btc-lagging",
        {
            "btc_return_24h_pct": -0.001,
            "nasdaq_return_24h_pct": 0.004,
            "sp500_return_24h_pct": 0.003,
            "btc_beta_residual": -0.007029,
            "btc_vs_ndx_relative_return": -0.00775,
            "btc_vs_spx_relative_return": -0.00582,
        },
    )
    confirmation = profile["btc_relative_confirmation"]

    assert confirmation["state"] == "btc_lagging_macro"
    assert confirmation["missing_reason"] is None
    assert "BTC relative=btc_lagging_macro" in profile["summary"]


def test_macro_radar_relative_basis_classifies_resisting_macro_headwind(tmp_path: Path) -> None:
    profile = _macro_radar_profile_from_values(
        tmp_path,
        "btc-resisting-headwind",
        {
            "btc_return_24h_pct": 0.004,
            "nasdaq_return_24h_pct": -0.01,
            "sp500_return_24h_pct": -0.008,
            "us2y_change_1d_bps": 8.0,
            "us10y_change_1d_bps": 7.0,
            "real_yield_change_1d_bps": 6.0,
            "btc_beta_residual": 0.009,
            "btc_vs_ndx_relative_return": 0.014,
            "btc_vs_spx_relative_return": 0.012,
        },
    )
    confirmation = profile["btc_relative_confirmation"]

    assert confirmation["state"] == "btc_resisting_macro_headwind"
    assert confirmation["missing_reason"] is None


def test_macro_radar_relative_confirmation_missing_has_reason(tmp_path: Path) -> None:
    profile = _macro_radar_profile_from_values(
        tmp_path,
        "missing-relative",
        {
            "us2y_change_1d_bps": 2.0,
            "us10y_change_1d_bps": 1.0,
        },
    )
    confirmation = profile["btc_relative_confirmation"]

    assert confirmation["state"] == "missing"
    assert "btc_relative_basis_missing" in confirmation["missing_reason"]


def test_options_volatility_v21_state_matrix_and_direction_isolation(tmp_path: Path) -> None:
    cases = [
        (
            "vol_expansion",
            {
                "options_iv": 75.0,
                "options_rv": 55.0,
                "iv_change_1d": 0.10,
                "rv_change_1d": 0.05,
                "put_call_ratio": 0.9,
                "options_skew": 0.2,
                "options_expiry_notional": 1_000_000_000.0,
                "max_pain_distance": 0.05,
                "gamma_wall_proxy_distance": 0.05,
            },
            "vol_expansion_risk",
        ),
        (
            "pinning",
            {
                "options_iv": 35.0,
                "options_rv": 30.0,
                "iv_change_1d": -0.02,
                "rv_change_1d": -0.01,
                "put_call_ratio": 0.9,
                "options_skew": 0.1,
                "options_expiry_notional": 1_000_000_000.0,
                "expiry_days": 3.0,
                "max_pain_distance": 0.005,
                "gamma_wall_proxy_distance": 0.006,
            },
            "pinning_likely",
        ),
        (
            "protection",
            {
                "options_iv": 55.0,
                "options_rv": 50.0,
                "put_call_ratio": 1.35,
                "options_skew": 4.0,
                "options_expiry_notional": 1_000_000_000.0,
                "max_pain_distance": 0.05,
                "gamma_wall_proxy_distance": 0.05,
            },
            "downside_protection_bid",
        ),
        (
            "expiry_pinning",
            {
                "options_iv": 80.0,
                "options_rv": 60.0,
                "iv_change_1d": 0.10,
                "rv_change_1d": 0.05,
                "put_call_ratio": 0.9,
                "options_skew": 0.1,
                "options_expiry_notional": 12_000_000_000.0,
                "expiry_days": 2.0,
                "expiry_notional_z": 2.0,
                "max_pain_distance": 0.005,
                "gamma_wall_proxy_distance": 0.05,
            },
            "pinning_before_expiry_vol_after",
        ),
        (
            "far_wall_expansion",
            {
                "options_iv": 75.0,
                "options_rv": 55.0,
                "iv_change_1d": 0.10,
                "rv_change_1d": 0.05,
                "put_call_ratio": 0.9,
                "options_skew": 0.1,
                "options_expiry_notional": 1_000_000_000.0,
                "max_pain_distance": 0.05,
                "gamma_wall_proxy_distance": 0.05,
            },
            "vol_expansion_risk",
        ),
        (
            "tail_unknown_side",
            {
                "options_iv": 75.0,
                "options_rv": 55.0,
                "iv_change_1d": 0.10,
                "rv_change_1d": 0.05,
                "put_call_ratio": 0.9,
                "options_skew_abs": 9.0,
                "options_expiry_notional": 1_000_000_000.0,
                "max_pain_distance": 0.05,
                "gamma_wall_proxy_distance": 0.05,
            },
            "tail_risk_elevated",
        ),
        (
            "missing",
            {
                "options_iv": 75.0,
                "put_call_ratio": 1.2,
            },
            "data_quality_degraded",
        ),
        (
            "normal",
            {
                "options_iv": 50.0,
                "options_rv": 48.0,
                "iv_change_1d": 0.0,
                "rv_change_1d": 0.0,
                "put_call_ratio": 0.9,
                "options_skew": 0.1,
                "options_expiry_notional": 1_000_000_000.0,
                "max_pain_distance": 0.03,
                "gamma_wall_proxy_distance": 0.03,
            },
            "vol_neutral",
        ),
    ]
    for name, values, expected_state in cases:
        profile = _options_profile_from_values(tmp_path, name, values)
        assert profile["options_short_term_state"] == expected_state
        assert profile["module_direction"] == "neutral"
        assert profile["module_score"] == 0
        assert profile["module_effective_score"] == 0


def test_event_policy_v21_trade_gate_matrix_and_direction_isolation(tmp_path: Path) -> None:
    cpi_caution = _event_policy_module_from_values(
        tmp_path,
        "cpi-caution",
        {"cpi_hours_until": 18.0, "cpi_days_until": 0.75},
    )
    assert cpi_caution["semantic_profile_version"] == "p3.c43.event_policy.v2.1"
    assert cpi_caution["module_direction"] == "neutral"
    assert cpi_caution["module_score"] == 0
    assert cpi_caution["event_window_phase"] == "caution"
    assert cpi_caution["trade_gate"]["allow_new_position"] is True
    assert cpi_caution["trade_gate"]["allow_add_position"] is False
    assert cpi_caution["trade_gate"]["allow_breakout_entry"] is False

    cpi_lock = _event_policy_module_from_values(
        tmp_path,
        "cpi-lock",
        {"cpi_hours_until": 5.0, "cpi_days_until": 0.2},
    )
    assert cpi_lock["event_window_phase"] == "hard_lock"
    assert cpi_lock["event_risk_lock_level"] == "hard"
    assert cpi_lock["trade_gate"]["allow_new_position"] is False
    assert cpi_lock["trade_gate"]["reason_code"] == "WAIT_DATA_RELEASE"

    fomc_caution = _event_policy_module_from_values(
        tmp_path,
        "fomc-caution",
        {"fomc_hours_until": 36.0, "fomc_days_until": 1.5},
    )
    assert fomc_caution["dominant_event_type"] == "fomc"
    assert fomc_caution["event_window_phase"] == "caution"
    assert fomc_caution["trade_gate"]["position_size_multiplier"] == 0.5

    blackout_only = _event_policy_module_from_values(
        tmp_path,
        "blackout-only",
        {"fomc_blackout_active": 1.0, "fomc_hours_until": 240.0, "fomc_days_until": 10.0},
    )
    assert blackout_only["dominant_event_type"] == "blackout"
    assert blackout_only["event_window_phase"] == "neutral"
    assert blackout_only["trade_gate"]["allow_new_position"] is True

    overlap = _event_policy_module_from_values(
        tmp_path,
        "overlap",
        {
            "cpi_hours_until": 2.0,
            "cpi_days_until": 0.08,
            "fomc_hours_until": 10.0,
            "fomc_days_until": 0.4,
        },
    )
    assert overlap["dominant_event_type"] == "fomc"
    assert overlap["nearest_event_type"] == "cpi"
    assert overlap["event_window_phase"] == "hard_lock"


def test_dollar_liquidity_v21_state_machine_and_btc_response(tmp_path: Path) -> None:
    tailwind = _dollar_liquidity_profile_from_values(
        tmp_path,
        "tailwind-confirmed",
        {
            "fed_balance_sheet": 6_713_000.0,
            "tga": 781_000.0,
            "on_rrp": 965.0,
            "bank_reserves": 3_130_000.0,
            "net_liquidity_proxy_bil": 5931.0,
            "net_liquidity_change_1w_bil": 75.0,
            "net_liquidity_change_4w_bil": 140.0,
            "liquidity_impulse_z": 1.2,
            "liquidity_acceleration": 30.0,
            "reserve_change_1w_bil": 55.0,
            "tga_change_1w_bil": -60.0,
            "rrp_depleted": 1.0,
            "sofr": 3.51,
            "iorb": 3.65,
            "sofr_iorb_spread_bps": -14.0,
            "funding_stress_z": -0.5,
            "btc_5d_return": 0.04,
            "btc_vs_liquidity_residual": 0.01,
        },
    )
    assert tailwind["semantic_profile_version"] == "p3.c46.dollar_liquidity.v2.1"
    assert tailwind["dollar_liquidity_state"] == "liquidity_tailwind_confirmed"
    assert tailwind["module_direction"] == "bullish"
    assert tailwind["liquidity_level"]["rrp_depleted"] is True
    assert tailwind["btc_response_confirmation"]["state"] == "absorbing_tailwind"

    rejected = _dollar_liquidity_profile_from_values(
        tmp_path,
        "tailwind-rejected",
        {
            "net_liquidity_change_1w_bil": 80.0,
            "liquidity_impulse_z": 1.1,
            "reserve_change_1w_bil": 20.0,
            "tga_change_1w_bil": -10.0,
            "sofr_iorb_spread_bps": -5.0,
            "funding_stress_z": 0.0,
            "btc_5d_return": -0.02,
        },
    )
    assert rejected["dollar_liquidity_state"] == "liquidity_tailwind_rejected"
    assert rejected["module_direction"] == "neutral"
    assert rejected["btc_response_confirmation"]["state"] == "rejecting_tailwind"

    stress = _dollar_liquidity_profile_from_values(
        tmp_path,
        "funding-stress",
        {
            "net_liquidity_change_1w_bil": 10.0,
            "liquidity_impulse_z": 0.1,
            "reserve_change_1w_bil": 0.0,
            "tga_change_1w_bil": 0.0,
            "sofr_iorb_spread_bps": 22.0,
            "funding_stress_z": 1.8,
            "btc_5d_return": 0.01,
        },
    )
    assert stress["dollar_liquidity_state"] == "funding_stress_override"
    assert stress["module_direction"] == "bearish"
    assert stress["repo_funding_pressure"]["state"] == "stress"
    assert stress["risk_score"] >= 75


def test_treasury_credit_v21_warning_and_btc_residual_states(tmp_path: Path) -> None:
    warning = _treasury_credit_profile_from_values(
        tmp_path,
        "rates-warning",
        {
            "treasury_2y": 4.1,
            "treasury_10y": 4.55,
            "real_yield_10y": 2.1,
            "breakeven_10y": 2.4,
            "hy_spread": 2.8,
            "treasury_2y_change_1d_bps": 9.0,
            "real_yield_10y_change_1d_bps": 2.0,
            "hy_oas_change_5d_bps": 2.0,
            "btc_return_24h": 0.003,
            "btc_residual_24h": 0.001,
        },
    )
    assert warning["semantic_profile_version"] == "p3.c47.treasury_credit.v2.1"
    assert warning["treasury_credit_state"] == "rates_headwind_warning"
    assert warning["module_direction"] == "neutral"
    assert "rates_headwind" in warning["early_warning_flags"]

    resisting = _treasury_credit_profile_from_values(
        tmp_path,
        "btc-resisting",
        {
            "treasury_2y_change_1d_bps": 4.0,
            "real_yield_10y_change_1d_bps": 4.0,
            "hy_oas_change_5d_bps": 0.0,
            "btc_return_24h": 0.012,
            "btc_residual_24h": 0.006,
        },
    )
    assert resisting["treasury_credit_state"] == "btc_resisting_rates_headwind"
    assert resisting["btc_implication"] == "internal_strength"
    assert resisting["states"]["btc_response_confirmation"]["state"] == "btc_resisting_headwind"

    credit = _treasury_credit_profile_from_values(
        tmp_path,
        "credit-stress",
        {
            "hy_oas_change_5d_bps": 30.0,
            "hy_oas_z_60d": 2.2,
            "btc_return_24h": -0.018,
            "btc_residual_24h": -0.012,
            "vix_change_1d_pct": 0.12,
        },
    )
    assert credit["treasury_credit_state"] == "credit_stress_confirmed"
    assert credit["module_direction"] == "bearish"
    assert credit["risk_score"] >= 80


def test_fund_flow_v22_fast_warning_rejection_and_resilience_states(tmp_path: Path) -> None:
    warning = _fund_flow_profile_from_values(
        tmp_path,
        "warning",
        {
            "etf_net_flow_usd": -180_000_000.0,
            "etf_flow_1d_z_60d": -1.2,
            "etf_outflow_streak_days": 2.0,
            "btc_return_24h": 0.0,
            "fund_flow_residual_z_60d": -0.2,
        },
    )
    assert warning["semantic_profile_version"] == "p3.c50.fund_flow.v2.2"
    assert warning["fund_flow_state"] == "etf_outflow_warning"
    assert "etf_outflow_warning" in warning["early_warning_flags"]
    assert set(warning["states"]) == {
        "etf_demand",
        "stablecoin_liquidity",
        "exchange_supply",
        "btc_response_confirmation",
    }
    assert set(warning["scores"]) == {
        "etf_demand_score",
        "stablecoin_liquidity_score",
        "exchange_supply_score",
        "btc_response_score",
        "data_quality_penalty",
    }

    rejecting = _fund_flow_profile_from_values(
        tmp_path,
        "rejecting",
        {
            "etf_flow_3d_usd": 320_000_000.0,
            "stablecoin_mcap_change_7d": 0.02,
            "btc_return_24h": -0.01,
            "fund_flow_residual_z_60d": -1.3,
            "fund_flow_residual_24h": -0.018,
        },
    )
    assert rejecting["fund_flow_state"] == "btc_rejecting_flow_tailwind"
    assert rejecting["module_direction"] == "bearish"
    assert rejecting["btc_implication"] == "internal_weakness"

    resisting = _fund_flow_profile_from_values(
        tmp_path,
        "resisting",
        {
            "etf_flow_3d_usd": -180_000_000.0,
            "btc_exchange_netflow_z_60d": 1.2,
            "btc_return_24h": 0.012,
            "fund_flow_residual_z_60d": 1.4,
            "fund_flow_residual_24h": 0.016,
        },
    )
    assert resisting["fund_flow_state"] == "btc_resisting_flow_headwind"
    assert resisting["module_direction"] == "bullish"
    assert resisting["btc_implication"] == "internal_strength"


def test_trade_structure_flow_strong_buy_without_price_response_is_unconfirmed(
    tmp_path: Path,
) -> None:
    profile = _trade_structure_profile_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 1.3391, 0.40, "bullish", 0.08),
            _feature("stablecoin_buying_power_proxy", -200_000_000.0, 0.0, "bearish", 0.0),
            _feature("liquidation_long_usd", 10_000.0, 0.0, "neutral", 0.0),
            _feature("liquidation_short_usd", 12_000.0, 0.0, "neutral", 0.0),
            _feature("mempool_blocks_to_clear", 4.0, 0.0, "neutral", 0.0),
            _feature("mempool_min_fee_rate_sat_vb", 18.0, 0.0, "neutral", 0.0),
        ],
    )

    assert profile["aggressive_flow_state"] == "strong_buying_pressure"
    assert profile["price_response_state"] == "need_kline_confirmation"
    assert profile["trade_structure_state"] == "buy_pressure_unconfirmed"
    assert profile["module_effective_bias"] == "mild_support"
    assert profile["confirmation_state"] == "unconfirmed"
    assert profile["risk_state"] == "execution_friction"
    assert profile["stablecoin_liquidity_state"] == "liquidity_pressure"


def test_trade_structure_flow_detects_absorption_and_liquidation_events(
    tmp_path: Path,
) -> None:
    absorbed = _trade_structure_profile_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 1.42, 0.40, "bullish", 0.08),
            _feature("btc_return_5m", -0.001, 0.0, "bearish", 0.0),
            _feature("btc_close_position_5m", 0.42, 0.0, "bearish", 0.0),
        ],
        run_id="p3-c37-absorbed",
    )
    long_flush = _trade_structure_profile_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 0.82, 0.40, "bearish", -0.08),
            _feature("btc_return_5m", -0.006, 0.0, "bearish", 0.0),
            _feature("btc_close_position_5m", 0.20, 0.0, "bearish", 0.0),
            _feature("liquidation_long_usd", 4_000_000.0, 0.0, "neutral", 0.0),
            _feature("liquidation_short_usd", 400_000.0, 0.0, "neutral", 0.0),
        ],
        run_id="p3-c37-long-flush",
    )
    squeeze = _trade_structure_profile_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 1.25, 0.40, "bullish", 0.08),
            _feature("btc_return_5m", 0.007, 0.0, "bullish", 0.0),
            _feature("btc_close_position_5m", 0.82, 0.0, "bullish", 0.0),
            _feature("liquidation_long_usd", 300_000.0, 0.0, "neutral", 0.0),
            _feature("liquidation_short_usd", 3_000_000.0, 0.0, "neutral", 0.0),
        ],
        run_id="p3-c37-short-squeeze",
    )

    assert absorbed["trade_structure_state"] == "absorption_or_trapped_long"
    assert absorbed["confirmation_state"] == "unconfirmed"
    assert long_flush["trade_structure_state"] == "long_flush_panic_risk"
    assert long_flush["liquidation_data_quality"] == "snapshot_not_full_market_volume"
    assert squeeze["trade_structure_state"] == "short_squeeze_chase_risk"


def test_trade_structure_price_response_confirmation_layer(tmp_path: Path) -> None:
    upside_module, upside_metrics = _trade_structure_scored_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 1.35, 0.40, "bullish", 0.08),
            _feature("btc_return_5m", 0.003, 0.0, "neutral", 0.0),
            _feature("btc_return_15m", 0.005, 0.0, "neutral", 0.0),
            _feature("btc_close_position_5m", 0.64, 0.0, "neutral", 0.0),
            _feature("btc_flow_price_efficiency_5m", 0.03, 0.0, "neutral", 0.0),
        ],
        run_id="p3-c38-upside",
    )
    no_upside, _ = _trade_structure_scored_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 1.35, 0.40, "bullish", 0.08),
            _feature("btc_return_5m", -0.001, 0.0, "neutral", 0.0),
            _feature("btc_close_position_5m", 0.38, 0.0, "neutral", 0.0),
        ],
        run_id="p3-c38-no-upside",
    )
    rejected, _ = _trade_structure_scored_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 1.36, 0.40, "bullish", 0.08),
            _feature("btc_return_5m", 0.002, 0.0, "neutral", 0.0),
            _feature("btc_close_position_5m", 0.40, 0.0, "neutral", 0.0),
        ],
        run_id="p3-c38-rejected",
    )
    sell_absorbed, _ = _trade_structure_scored_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 0.62, 0.40, "bearish", -0.08),
            _feature("btc_return_5m", 0.001, 0.0, "neutral", 0.0),
            _feature("btc_close_position_5m", 0.58, 0.0, "neutral", 0.0),
        ],
        run_id="p3-c38-sell-absorbed",
    )

    upside_price = upside_metrics["btc_return_5m"]
    assert upside_module["price_response_state"] == "upside_response"
    assert upside_module["trade_structure_state"] == "bullish_confirmation"
    assert upside_price["price_response_state"] == "upside_response"
    assert upside_price["price_response_source"] == "5m_15m"
    assert upside_price["flow_price_efficiency_state"] == "efficient"
    assert upside_price["metric_score"] == 0.0
    assert no_upside["price_response_state"] == "no_upside_response"
    assert no_upside["trade_structure_state"] == "absorption_or_trapped_long"
    assert rejected["price_response_state"] == "upside_rejected"
    assert rejected["trade_structure_state"] == "buy_pressure_rejected"
    assert sell_absorbed["price_response_state"] == "no_downside_response"
    assert sell_absorbed["trade_structure_state"] == "sell_absorption_or_trapped_short"


def test_trade_structure_price_response_uses_same_weak_confirmation_semantics(
    tmp_path: Path,
) -> None:
    taker = _feature("taker_buy_sell_ratio", 1.1486, 0.40, "bearish", -0.0481)
    taker["change_24h"] = -0.0300624894
    module, metrics = _trade_structure_scored_from_features(
        tmp_path,
        [
            taker,
            _feature("btc_return_5m", 0.0004504249940222582, 0.0, "neutral", 0.0),
            _feature("btc_return_15m", 0.0013581937926387955, 0.0, "neutral", 0.0),
            _feature("btc_close_position_5m", 0.9998382138813338, 0.0, "neutral", 0.0),
            _feature("btc_close_position_15m", 0.8673736199884242, 0.0, "neutral", 0.0),
            _feature("btc_flow_price_efficiency_5m", 0.0016590406616438316, 0.0, "neutral", 0.0),
            _feature("stablecoin_buying_power_proxy", -200_000_000.0, 0.0, "bearish", 0.0),
        ],
        run_id="p3-c39-c40-audit-shape",
    )

    price_metric = metrics["btc_return_5m"]
    taker_metric = metrics["taker_buy_sell_ratio"]
    assert module["aggressive_flow_state"] == "buying_pressure"
    assert module["price_response_state"] == "weak_upside_response"
    assert module["trade_structure_state"] == "buy_pressure_unconfirmed"
    assert module["confirmation_state"] == "unconfirmed"
    assert price_metric["price_response_state"] == module["price_response_state"]
    assert price_metric["price_response_confidence"] == 0.55
    assert taker_metric["semantic_rule_id"] == (
        "semantic.trade_structure.aggressive_flow_context"
    )
    assert taker_metric["aggressive_flow_state"] == "buying_pressure"
    assert taker_metric["direction"] == "neutral"
    assert taker_metric["metric_score"] == 0.0
    assert taker_metric["metric_effective_score"] == 0.0


def test_trade_structure_price_response_falls_back_to_1h(tmp_path: Path) -> None:
    placeholder = _feature("btc_return_5m", 0.0, 0.0, "neutral", 0.0)
    placeholder["current"] = None
    module, metrics = _trade_structure_scored_from_features(
        tmp_path,
        [
            _feature("taker_buy_sell_ratio", 1.34, 0.40, "bullish", 0.08),
            _feature("btc_return_1h", 0.004, 0.0, "neutral", 0.0),
            _feature("btc_close_position_1h", 0.61, 0.0, "neutral", 0.0),
            placeholder,
        ],
        run_id="p3-c38-fallback",
    )

    assert module["price_response_state"] == "upside_response"
    assert metrics["btc_return_5m"]["price_response_source"] == "1h_fallback"


def test_trade_structure_flow_v23_requires_price_acceptance_and_residual(tmp_path: Path) -> None:
    module = _trade_structure_profile_from_features(
        tmp_path,
        [
            _feature("trade_price_acceptance_score_5m", 70.0, 0.05, "bullish", 0.0),
            _feature("trade_price_acceptance_score_15m", 74.0, 0.05, "bullish", 0.0),
            _feature("trade_btc_return_z_5m", 1.1, 0.04, "bullish", 0.0),
            _feature("trade_btc_return_z_15m", 1.2, 0.04, "bullish", 0.0),
            _feature("trade_btc_return_z_1h", 0.8, 0.04, "bullish", 0.0),
            _feature("trade_structure_residual_z", 1.1, 0.05, "bullish", 0.0),
            _feature("trade_spot_led_score", 72.0, 0.04, "bullish", 0.0),
            _feature("trade_volume_quality_score", 65.0, 0.04, "bullish", 0.0),
            _feature("trade_perp_led_score", 20.0, 0.04, "neutral", 0.0),
        ],
        run_id="p3-c53-trade-v23-spot-led",
    )

    assert module["semantic_profile_version"] == "p3.c58.trade_structure_flow.v2.3"
    assert module["trade_structure_state"] == "spot_led_trend_accepted"
    assert module["signal_stage"] == "confirmed_signal"
    assert module["module_direction"] == "bullish"
    assert module["multi_horizon"]["15m"]["direction"] == "bullish"
    assert module["scores"]["price_acceptance_score"] > 0
    assert module["scores"]["residual_confirmation_score"] > 0


def test_trade_structure_flow_v23_blocks_confirmed_without_residual_alignment(tmp_path: Path) -> None:
    module = _trade_structure_profile_from_features(
        tmp_path,
        [
            _feature("trade_price_acceptance_score_5m", 70.0, 0.05, "bullish", 0.0),
            _feature("trade_price_acceptance_score_15m", 74.0, 0.05, "bullish", 0.0),
            _feature("trade_btc_return_z_5m", 1.1, 0.04, "bullish", 0.0),
            _feature("trade_btc_return_z_15m", 1.2, 0.04, "bullish", 0.0),
            _feature("trade_btc_return_z_1h", 0.8, 0.04, "bullish", 0.0),
            _feature("trade_structure_residual_z", -1.1, 0.05, "bearish", 0.0),
            _feature("trade_spot_led_score", 72.0, 0.04, "bullish", 0.0),
            _feature("trade_volume_quality_score", 65.0, 0.04, "bullish", 0.0),
            _feature("trade_perp_led_score", 20.0, 0.04, "neutral", 0.0),
        ],
        run_id="p3-c53-trade-v23-conflict",
    )

    assert module["semantic_profile_version"] == "p3.c58.trade_structure_flow.v2.3"
    assert module["signal_stage"] == "conflict"
    assert module["module_direction"] == "neutral"
    assert "confirmed_signal_blocked_without_price_acceptance_and_residual_alignment" in module["conflict_drivers"]


def test_derivatives_crowding_v25_requires_trend_prior_btc_response_and_residual(
    tmp_path: Path,
) -> None:
    module = _derivatives_profile_from_features(
        tmp_path,
        [
            _feature("btc_funding_rate", 0.00005, 0.0, "neutral", 0.0),
            _feature("btc_open_interest", 100000.0, 0.0, "neutral", 0.0),
            _feature("btc_trend_prior_score", 45.0, 0.03, "bullish", 0.0),
            _feature("btc_trend_strength_z", 1.4, 0.01, "neutral", 0.0),
            _feature("btc_trend_confidence", 78.0, 0.01, "neutral", 0.0),
            _feature("btc_response_z_15m", 0.8, 0.04, "bullish", 0.0),
            _feature("btc_response_z_1h", 0.9, 0.08, "bullish", 0.0),
            _feature("btc_response_z_4h", 0.6, 0.04, "bullish", 0.0),
            _feature("derivatives_acceptance_score", 72.0, 0.11, "bullish", 0.0),
            _feature("derivatives_rejection_score", 5.0, 0.08, "neutral", 0.0),
            _feature("derivatives_residual_z", 1.2, 0.10, "bullish", 0.0),
            _feature("oi_impulse_z_1h", 0.8, 0.04, "neutral", 0.0),
            _feature("oi_price_efficiency", 0.8, 0.05, "bullish", 0.0),
            _feature("oi_participation_type_score", 55.0, 0.06, "bullish", 0.0),
            _feature("funding_rate_8h_equiv_z", 0.4, 0.04, "neutral", 0.0),
            _feature("basis_acceptance_score", 45.0, 0.04, "bullish", 0.0),
        ],
        run_id="p3-c54-derivatives-v25-accepted",
    )

    assert module["semantic_profile_version"] == "p3.c60.derivatives_crowding.v2.5"
    assert module["derivatives_state"] == "derivatives_accepted_uptrend"
    assert module["signal_stage"] == "confirmed_signal"
    assert module["module_direction"] == "bullish"
    assert module["trend_prior"]["btc_trend_state"] == "uptrend"
    assert module["scores"]["trend_acceptance_score"] > 0
    assert "derivatives_crowding_v25" in module


def test_derivatives_crowding_v25_blocks_confirmed_without_residual_alignment(
    tmp_path: Path,
) -> None:
    module = _derivatives_profile_from_features(
        tmp_path,
        [
            _feature("btc_trend_prior_score", 45.0, 0.03, "bullish", 0.0),
            _feature("btc_trend_confidence", 78.0, 0.01, "neutral", 0.0),
            _feature("btc_response_z_15m", 0.8, 0.04, "bullish", 0.0),
            _feature("btc_response_z_1h", 0.9, 0.08, "bullish", 0.0),
            _feature("derivatives_acceptance_score", 72.0, 0.11, "bullish", 0.0),
            _feature("derivatives_rejection_score", 5.0, 0.08, "neutral", 0.0),
            _feature("derivatives_residual_z", -1.2, 0.10, "bearish", 0.0),
            _feature("oi_impulse_z_1h", 0.8, 0.04, "neutral", 0.0),
            _feature("oi_price_efficiency", 0.8, 0.05, "bullish", 0.0),
            _feature("oi_participation_type_score", 55.0, 0.06, "bullish", 0.0),
            _feature("funding_rate_8h_equiv_z", 0.4, 0.04, "neutral", 0.0),
            _feature("basis_acceptance_score", 45.0, 0.04, "bullish", 0.0),
        ],
        run_id="p3-c54-derivatives-v25-conflict",
    )

    assert module["semantic_profile_version"] == "p3.c60.derivatives_crowding.v2.5"
    assert module["signal_stage"] in {"conflict", "fast_signal", "none", "early_warning"}
    assert module["module_direction"] != "bullish" or module["signal_stage"] != "confirmed_signal"
    assert module["derivatives_crowding_v25"]["scores"]["residual_confirmation_score"] < 0


def test_source_conflict_invalidation_distinguishes_true_and_suppressed_conflicts(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_module_outputs(
        db,
        "p3-conflict-test",
        {
            "macro_radar": {
                "conflicting_evidence": {
                    "source_conflicts": [{"metric_id": "dxy_proxy", "type": "true_value_conflict"}]
                },
            },
            "fund_flow": {
                "features": [
                    {
                        "metric_id": "etf_net_flow",
                        "available": True,
                        "conflict": {
                            "suppressed_items": [
                                {"metric_id": "etf_net_flow", "type": "fallback_difference"}
                            ]
                        },
                    }
                ],
            },
        },
    )

    check_module_invalidations(run_id="p3-conflict-test", db=db)

    with db.session() as session:
        macro = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-conflict-test",
                schema.InvalidationEvent.condition_id == "macro_radar_source_conflict_invalidation",
            )
        )
        fund = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-conflict-test",
                schema.InvalidationEvent.condition_id == "fund_flow_source_conflict_invalidation",
            )
        )

    assert macro is not None
    assert macro.status == "triggered"
    assert macro.payload["evidence"]["reason_code"] == "true_source_conflict"
    assert fund is not None
    assert fund.status == "not_triggered"
    assert fund.payload["evidence"]["suppressed_conflicts"][0]["type"] == "fallback_difference"


def test_directional_global_invalidations_do_not_trigger_both_sides(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_module_outputs(
        db,
        "p3-direction-test",
        {
            "macro_radar": {"signal": "bearish", "data_quality": "low"},
            "treasury_credit": {"signal": "bearish", "data_quality": "low"},
        },
    )

    check_module_invalidations(run_id="p3-direction-test", db=db)
    check_global_invalidations(run_id="p3-direction-test", db=db)

    with db.session() as session:
        bullish = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-direction-test",
                schema.InvalidationEvent.condition_id == "bullish_state_invalidation",
            )
        )
        bearish = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-direction-test",
                schema.InvalidationEvent.condition_id == "bearish_state_invalidation",
            )
        )

    assert bullish is not None
    assert bearish is not None
    assert bullish.status == "triggered"
    assert bullish.payload["reason_code"] == "bearish_evidence_against_bullish_state"
    assert bearish.status == "not_triggered"


def test_run_mode_mixed_history_writes_integrity_invalidation(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        _add_series(session, "btc_price", "binance-btcusdt", now, [100.0], run_mode="live")
        _add_series(session, "btc_price", "binance-btcusdt", now, [101.0], run_mode="mock")
    _seed_module_outputs(db, "p3-run-mode-integrity-test")

    check_module_invalidations(run_id="p3-run-mode-integrity-test", db=db)
    check_global_invalidations(
        run_id="p3-run-mode-integrity-test",
        collect_run_id=None,
        db=db,
    )

    with db.session() as session:
        event = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-run-mode-integrity-test",
                schema.InvalidationEvent.condition_id == "run_mode_integrity_invalidation",
            )
        )

    assert event is not None
    assert event.status == "triggered"
    assert event.action == "block_critical_publish"
    assert event.payload["reason_code"] == "run_mode_mixed_history"
    assert event.payload["publish_impact"] == "block_critical_publish"
    assert event.payload["run_mode_risk"]["production_blocker"] is True


def test_run_mode_history_mock_does_not_block_clean_live_current_run(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        _add_series(session, "btc_price", "binance-btcusdt", now, [90.0], run_mode="mock")
        session.add(
            schema.MetricValue(
                metric_id="btc_price",
                source_id="binance-btcusdt",
                run_id="collect-clean-live",
                ts=now,
                value=100.0,
                quality_score=0.9,
                run_mode="live",
            )
        )
    _seed_module_outputs(db, "p3-clean-live-integrity-test")

    check_global_invalidations(
        run_id="p3-clean-live-integrity-test",
        collect_run_id="collect-clean-live",
        db=db,
    )

    with db.session() as session:
        event = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-clean-live-integrity-test",
                schema.InvalidationEvent.condition_id == "run_mode_integrity_invalidation",
            )
        )

    assert event is not None
    assert event.status == "not_triggered"
    risk = event.payload["run_mode_risk"]
    assert risk["production_blocker"] is False
    assert risk["history_contamination_warning"] is True
    assert risk["current_run_counts"] == {"live": 1}
    assert risk["database_history_counts"]["mock"] == 1


def test_run_mode_current_live_mock_mix_blocks_current_run(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        for mode, value in (("live", 100.0), ("mock", 101.0)):
            session.add(
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    run_id="collect-mixed-live",
                    ts=now,
                    value=value,
                    quality_score=0.9,
                    run_mode=mode,
                )
            )
    _seed_module_outputs(db, "p3-mixed-live-integrity-test")

    check_global_invalidations(
        run_id="p3-mixed-live-integrity-test",
        collect_run_id="collect-mixed-live",
        db=db,
    )

    with db.session() as session:
        event = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-mixed-live-integrity-test",
                schema.InvalidationEvent.condition_id == "run_mode_integrity_invalidation",
            )
        )

    assert event is not None
    assert event.status == "triggered"
    assert event.action == "block_critical_publish"
    risk = event.payload["run_mode_risk"]
    assert risk["production_blocker"] is True
    assert risk["current_run_counts"] == {"live": 1, "mock": 1}
    assert risk["current_run_mixed_metric_ids"] == ["btc_price"]


def test_p3_pipeline_carries_collect_run_scope_into_features(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        _add_series(
            session,
            "btc_price",
            "binance-btcusdt",
            now,
            [100.0, 101.0, 102.0, 104.0],
        )
        _add_series(
            session,
            "btc_funding_rate",
            "binance-btcusdt-funding",
            now,
            [0.0001, 0.00011, 0.00012, 0.00013],
        )
        write_data_quality_snapshot(session, run_id="dq-p3-run-scope-test")

    result = run_p3_pipeline(
        run_id="p3-run-scope-test",
        metric_ids=["btc_price", "btc_funding_rate"],
        collect_run_id="collect-btc_price-3",
        historical_fallback=True,
        db=db,
    )

    assert result["collect_run_id"] == "collect-btc_price-3"
    with db.session() as session:
        feature_rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-run-scope-test",
                schema.FeatureValue.module_id == "p3_feature_engine",
            )
        ).all()
        module_invalidation = session.scalar(
            select(schema.InvalidationEvent).where(
                schema.InvalidationEvent.run_id == "p3-run-scope-test",
                schema.InvalidationEvent.condition_id
                == "btc_total_state_data_quality_invalidation",
            )
        )

    metadata_by_metric = {row.metadata_json["metric_id"]: row.metadata_json for row in feature_rows}
    assert metadata_by_metric["btc_price"]["feature_run_scope"] == "current_run"
    assert metadata_by_metric["btc_price"]["collect_run_id"] == "collect-btc_price-3"
    assert metadata_by_metric["btc_funding_rate"]["feature_run_scope"] == ("historical_fallback")
    assert module_invalidation is not None
    assert module_invalidation.payload["reason_code"] in {
        "historical_fallback_dependency",
        "low_same_run_coverage",
    }


def test_event_windows_use_signed_days_summary_and_daily_watch(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        _add_series(session, "cpi_days_until", "official-macro-event-calendar", now, [5.0])
        _add_series(session, "cpi_signed_days", "official-macro-event-calendar", now, [5.0])
        _add_series(session, "macro_surprise_score", "fxstreet-economic-calendar", now, [0.2])
        _add_series(session, "fed_speech_risk", "fed-rss-all-speeches", now, [0.1])
        session.add(
            schema.RawObservation(
                source_id="official-macro-event-calendar",
                run_id="collect-cpi_signed_days-0",
                mode="live",
                observed_at=now,
                payload_hash="hash-1",
                raw_payload={
                    "events": [
                        {
                            "event_type": "cpi",
                            "name": "Consumer Price Index",
                            "datetime": (now + timedelta(days=5)).isoformat(),
                            "source": "fallback_2026_official_calendar",
                        }
                    ],
                    "source_resolution": {
                        "cpi": {
                            "status": "embedded_fallback",
                            "fallback_used": True,
                        }
                    },
                },
            )
        )

    detect_event_windows(run_id="p3-event-1", db=db)

    with db.session() as session:
        rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-event-1",
                schema.FeatureValue.module_id == "p3_event_window_engine",
            )
        ).all()

    cpi = next(row for row in rows if row.metadata_json["event_type"] == "CPI")
    assert cpi.value == 5.0
    assert cpi.metadata_json["window"] == "T-7"
    assert cpi.metadata_json["event_phase"] == "pre_event"
    assert cpi.metadata_json["daily_watch"]["active"] is True
    assert cpi.metadata_json["daily_watch"]["change_summary"] == "no_material_change"
    assert cpi.metadata_json["event_summary"]["data_points"]["macro_surprise_score"]["value"] == 0.2

    later = now + timedelta(hours=1)
    with db.session() as session:
        _add_series(session, "cpi_days_until", "official-macro-event-calendar", later, [4.0])
        _add_series(session, "cpi_signed_days", "official-macro-event-calendar", later, [4.0])
    detect_event_windows(run_id="p3-event-2", db=db)

    with db.session() as session:
        latest = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p3-event-2",
                schema.FeatureValue.feature_id == "cpi_days_until.event_window",
            )
        )

    assert latest is not None
    changed = latest.metadata_json["daily_watch"]["changed_fields"]
    assert any(item["field"] == "signed_days" for item in changed)


def _add_series(
    session,
    metric_id: str,
    source_id: str,
    now: datetime,
    values: list[float],
    run_mode: str = "live",
) -> None:
    for index, value in enumerate(values):
        previous = values[index - 1] if index else None
        session.add(
            schema.MetricValue(
                metric_id=metric_id,
                source_id=source_id,
                run_id=f"collect-{metric_id}-{index}",
                ts=now - timedelta(hours=len(values) - index),
                value=value,
                previous_value=previous,
                change_24h=((value - previous) / abs(previous)) if previous else None,
                quality_score=0.9,
                run_mode=run_mode,
            )
        )


def _feature(
    metric_id: str,
    current: float,
    weight: float,
    direction: str,
    score: float,
) -> dict:
    return {
        "metric_id": metric_id,
        "available": True,
        "current": current,
        "change_24h": 0.0,
        "score": score,
        "direction": direction,
        "weight": weight,
        "role": "primary_signal",
        "affects_signal": True,
        "affects_confidence": True,
        "affects_risk_flags": False,
        "quality_score": 0.9,
        "collection_freshness_status": "fresh",
        "business_recency_status": "current",
        "source_id": f"test-{metric_id}",
        "source_run_id": "collect-semantic-test",
        "feature_run_scope": "current_run",
        "current_run_has_value": True,
        "evidence_tier": "primary",
        "quality_blocking": True,
    }


def _options_profile_from_values(
    tmp_path: Path,
    name: str,
    values: dict[str, float],
) -> dict:
    db = Database(tmp_path / f"options-{name}.sqlite3")
    db.init_schema()
    features = [_feature(metric_id, value, 0.0, "neutral", 0.0) for metric_id, value in values.items()]
    for feature in features:
        feature["role"] = "risk_context"
        feature["affects_signal"] = False
        feature["driver_eligible"] = False
    run_id = f"options-v21-{name}"
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="options_volatility",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "options_volatility",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {
                        "net_score": 0.0,
                        "quality_explanation": {},
                    },
                },
            )
        )
    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "options_volatility.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _event_policy_module_from_values(
    tmp_path: Path,
    name: str,
    values: dict[str, float],
) -> dict:
    db = Database(tmp_path / f"event-policy-{name}.sqlite3")
    db.init_schema()
    features = [_feature(metric_id, value, 0.0, "neutral", 0.0) for metric_id, value in values.items()]
    for feature in features:
        feature["role"] = "macro_data_event"
        feature["affects_signal"] = False
        feature["affects_confidence"] = False
        feature["affects_risk_flags"] = True
        feature["driver_eligible"] = False
    run_id = f"event-policy-{name}"
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="event_policy",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "event_policy",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )
    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "event_policy.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _crypto_breadth_profile_from_values(
    tmp_path: Path,
    name: str,
    values: dict[str, float],
) -> dict:
    db = Database(tmp_path / f"crypto-breadth-{name}.sqlite3")
    db.init_schema()
    features = [_feature(metric_id, value, 0.0, "neutral", 0.0) for metric_id, value in values.items()]
    run_id = f"crypto-breadth-v3-{name}"
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="crypto_breadth",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "crypto_breadth",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )
    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "crypto_breadth.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _macro_radar_profile_from_values(
    tmp_path: Path,
    name: str,
    values: dict[str, float],
) -> dict:
    db = Database(tmp_path / f"macro-radar-{name}.sqlite3")
    db.init_schema()
    features = [_feature(metric_id, value, 0.0, "neutral", 0.0) for metric_id, value in values.items()]
    for feature in features:
        feature["role"] = "btc_relative_confirmation"
        feature["affects_signal"] = False
        feature["driver_eligible"] = False
    run_id = f"macro-radar-v3-{name}"
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="macro_radar",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "macro_radar",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )
    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "macro_radar.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _dollar_liquidity_profile_from_values(
    tmp_path: Path,
    name: str,
    values: dict[str, float],
) -> dict:
    db = Database(tmp_path / f"dollar-liquidity-{name}.sqlite3")
    db.init_schema()
    role_by_metric = {
        "fed_balance_sheet": "liquidity_level",
        "tga": "liquidity_drain_pressure",
        "on_rrp": "liquidity_drain_pressure",
        "bank_reserves": "reserve_buffer",
        "net_liquidity_proxy_bil": "liquidity_level",
        "net_liquidity_change_1w_bil": "liquidity_impulse",
        "net_liquidity_change_4w_bil": "liquidity_impulse",
        "liquidity_impulse_z": "liquidity_impulse",
        "liquidity_acceleration": "liquidity_impulse",
        "reserve_change_1w_bil": "reserve_buffer",
        "tga_change_1w_bil": "liquidity_drain_pressure",
        "rrp_depleted": "liquidity_drain_pressure",
        "sofr": "repo_funding_pressure",
        "iorb": "repo_funding_pressure",
        "sofr_iorb_spread_bps": "repo_funding_pressure",
        "funding_stress_z": "repo_funding_pressure",
        "sofr_jump_1d_bps": "repo_funding_pressure",
        "btc_1d_return": "btc_response_confirmation",
        "btc_5d_return": "btc_response_confirmation",
        "btc_20d_return": "btc_response_confirmation",
        "btc_vs_liquidity_residual": "btc_response_confirmation",
    }
    features = [_feature(metric_id, value, 0.0, "neutral", 0.0) for metric_id, value in values.items()]
    for feature in features:
        feature["role"] = role_by_metric.get(feature["metric_id"], "liquidity_level")
        feature["affects_signal"] = False
        feature["driver_eligible"] = False
        feature["affects_risk_flags"] = feature["role"] == "repo_funding_pressure"
    run_id = f"dollar-liquidity-{name}"
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="dollar_liquidity",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "dollar_liquidity",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )
    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "dollar_liquidity.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _treasury_credit_profile_from_values(
    tmp_path: Path,
    name: str,
    values: dict[str, float],
) -> dict:
    db = Database(tmp_path / f"treasury-credit-{name}.sqlite3")
    db.init_schema()
    role_by_metric = {
        "treasury_2y": "policy_rate_pressure",
        "treasury_2y_change_1d_bps": "policy_rate_pressure",
        "treasury_2y_change_3d_bps": "policy_rate_pressure",
        "treasury_2y_z_60d": "policy_rate_pressure",
        "treasury_10y": "duration_term_pressure",
        "treasury_30y": "duration_term_pressure",
        "treasury_10y_change_1d_bps": "duration_term_pressure",
        "treasury_10y_change_3d_bps": "duration_term_pressure",
        "treasury_30y_change_3d_bps": "duration_term_pressure",
        "real_yield_10y": "real_yield_pressure",
        "real_yield_10y_change_1d_bps": "real_yield_pressure",
        "real_yield_10y_change_3d_bps": "real_yield_pressure",
        "real_yield_10y_z_60d": "real_yield_pressure",
        "breakeven_10y": "inflation_mix",
        "breakeven_10y_change_1d_bps": "inflation_mix",
        "breakeven_10y_change_3d_bps": "inflation_mix",
        "yield_curve_2s10s_bps": "curve_regime",
        "curve_2s10s_change_1d_bps": "curve_regime",
        "curve_2s10s_change_5d_bps": "curve_regime",
        "yield_curve_10s30s_bps": "curve_regime",
        "hy_spread": "credit_stress",
        "ig_oas": "credit_stress",
        "hy_oas_change_1d_bps": "credit_stress",
        "hy_oas_change_5d_bps": "credit_stress",
        "hy_oas_z_60d": "credit_stress",
        "hy_oas_percentile_252d": "credit_stress",
        "btc_return_24h": "btc_response_confirmation",
        "btc_residual_24h": "btc_response_confirmation",
        "btc_vs_rates_residual_24h": "btc_response_confirmation",
        "btc_vs_credit_residual_3d": "btc_response_confirmation",
        "vix_change_1d_pct": "credit_stress",
        "nasdaq_return_24h_pct": "credit_stress",
    }
    features = [_feature(metric_id, value, 0.0, "neutral", 0.0) for metric_id, value in values.items()]
    for feature in features:
        feature["role"] = role_by_metric.get(feature["metric_id"], "policy_rate_pressure")
        feature["affects_signal"] = False
        feature["driver_eligible"] = False
        feature["affects_risk_flags"] = feature["role"] in {"credit_stress", "real_yield_pressure"}
    run_id = f"treasury-credit-{name}"
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="treasury_credit",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "treasury_credit",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )
    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "treasury_credit.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _fund_flow_profile_from_values(
    tmp_path: Path,
    name: str,
    values: dict[str, float],
) -> dict:
    db = Database(tmp_path / f"fund-flow-{name}.sqlite3")
    db.init_schema()
    role_by_metric = {
        "etf_net_flow_usd": "fast_flow_signal",
        "etf_flow_1d_z_60d": "fast_flow_signal",
        "etf_flow_3d_usd": "demand_momentum",
        "etf_flow_7d_usd": "demand_persistence",
        "etf_outflow_streak_days": "pressure_warning",
        "stablecoin_mcap_change_7d": "liquidity_regime",
        "stablecoin_mcap_change_30d": "liquidity_regime",
        "btc_exchange_netflow_z_60d": "supply_pressure_context",
        "btc_return_24h": "btc_response_confirmation",
        "fund_flow_residual_24h": "btc_response_veto",
        "fund_flow_residual_z_60d": "btc_response_veto",
    }
    features = [_feature(metric_id, value, 0.0, "neutral", 0.0) for metric_id, value in values.items()]
    for feature in features:
        feature["role"] = role_by_metric.get(feature["metric_id"], "composite_only")
        feature["affects_signal"] = False
        feature["driver_eligible"] = False
        feature["affects_risk_flags"] = True
    run_id = f"fund-flow-{name}"
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="fund_flow",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "fund_flow",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )
    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "fund_flow.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _btc_total_features(
    *,
    price_change: float,
    oi_change: float,
    funding: float,
) -> list[dict]:
    price = _btc_total_feature("btc_price", 100_000.0)
    price["change_24h"] = price_change
    close = _btc_total_feature("btc_1h_close", 99_500.0)
    close["change_24h"] = price_change
    funding_feature = _btc_total_feature("btc_funding_rate", funding)
    funding_feature["role"] = "perp_state"
    oi = _btc_total_feature("btc_open_interest", 100_000.0)
    oi["role"] = "perp_state"
    oi["change_24h"] = oi_change
    halving_days = _btc_total_feature("btc_halving_estimated_days", 490.0)
    halving_days["role"] = "cycle_context"
    halving_days["affects_confidence"] = False
    halving_blocks = _btc_total_feature("btc_halving_blocks_remaining", 70_000.0)
    halving_blocks["role"] = "cycle_context"
    halving_blocks["affects_confidence"] = False
    block_height = _btc_total_feature("btc_block_height", 890_000.0)
    block_height["role"] = "audit_context"
    block_height["affects_confidence"] = False
    return [price, close, funding_feature, oi, halving_days, halving_blocks, block_height]


def _btc_total_feature(metric_id: str, current: float) -> dict:
    feature = _feature(metric_id, current, 0.0, "neutral", 0.0)
    feature["role"] = "price_state"
    feature["affects_signal"] = False
    feature["driver_eligible"] = False
    feature["horizon_tags"] = ["h24", "d3"]
    return feature


def _btc_total_scored_from_features(
    tmp_path: Path,
    features: list[dict],
    run_id: str,
) -> tuple[dict, dict[str, dict]]:
    db = Database(tmp_path / f"{run_id}.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="btc_total_state",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "btc_total_state",
                    "signal": "neutral",
                    "strength": 0.0,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {"net_score": 0.0, "quality_explanation": {}},
                },
            )
        )

    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "btc_total_state.scored_module",
            )
        )
        metric_rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_METRIC_MODULE_ID,
            )
        ).all()
    assert row is not None
    return row.metadata_json, {
        metric.metadata_json["metric_id"]: metric.metadata_json for metric in metric_rows
    }


def _trade_structure_profile_from_features(
    tmp_path: Path,
    features: list[dict],
    run_id: str = "p3-c37-trade-structure",
) -> dict:
    module, _metrics = _trade_structure_scored_from_features(tmp_path, features, run_id=run_id)
    return module


def _derivatives_profile_from_features(
    tmp_path: Path,
    features: list[dict],
    run_id: str = "p3-c54-derivatives-crowding",
) -> dict:
    db = Database(tmp_path / f"{run_id}.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="derivatives_crowding",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "derivatives_crowding",
                    "signal": "mixed",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {
                        "net_score": sum(float(item["score"]) for item in features),
                        "quality_explanation": {},
                    },
                },
            )
        )

    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "derivatives_crowding.scored_module",
            )
        )
    assert row is not None
    return row.metadata_json


def _trade_structure_scored_from_features(
    tmp_path: Path,
    features: list[dict],
    run_id: str = "p3-c37-trade-structure",
) -> tuple[dict, dict[str, dict]]:
    db = Database(tmp_path / f"{run_id}.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=run_id,
                module_id="trade_structure_flow",
                schema_version="1.0",
                payload={
                    "run_id": run_id,
                    "module_id": "trade_structure_flow",
                    "signal": "mixed",
                    "strength": 0.2,
                    "confidence": 0.9,
                    "features": features,
                    "evidence_summary": {
                        "net_score": sum(float(item["score"]) for item in features),
                        "quality_explanation": {},
                    },
                },
            )
        )

    build_scored_evidence(run_id=run_id, db=db)
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_RADAR_MODULE_ID,
                schema.FeatureValue.feature_id == "trade_structure_flow.scored_module",
            )
        )
        metric_rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == run_id,
                schema.FeatureValue.module_id == SCORED_METRIC_MODULE_ID,
            )
        ).all()
    assert row is not None
    return row.metadata_json, {
        metric.metadata_json["metric_id"]: metric.metadata_json for metric in metric_rows
    }


def _seed_module_outputs(
    db: Database,
    run_id: str,
    overrides: dict[str, dict] | None = None,
) -> None:
    overrides = overrides or {}
    with db.session() as session:
        for module in RADAR_MODULES:
            override = overrides.get(module.module_id, {})
            payload = _module_payload(run_id, module.module_id, override)
            session.add(
                schema.ModuleJsonOutput(
                    run_id=run_id,
                    module_id=module.module_id,
                    schema_version="1.0",
                    payload=payload,
                )
            )


def _module_payload(run_id: str, module_id: str, override: dict) -> dict:
    payload = {
        "run_id": run_id,
        "module_id": module_id,
        "signal": "neutral",
        "strength": 0.2,
        "confidence": 0.9,
        "data_quality": "high",
        "features": [],
        "evidence_summary": {
            "quality_explanation": {
                "coverage_score": 1.0,
                "overall_score": 0.95,
            }
        },
        "conflicting_evidence": {"source_conflicts": []},
        "invalidation_signals": {
            "missing_metrics": [],
            "provider_required_metrics": [],
            "stale_metrics": [],
            "expired_metrics": [],
            "business_lagging_metrics": [],
            "low_coverage": False,
        },
        "run_mode": "live",
        "non_production": False,
    }
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key] = {**payload[key], **value}
        else:
            payload[key] = value
    return payload
