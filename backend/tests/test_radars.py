from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.radars.registry import RADAR_MODULES, get_radar
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.registry import METRIC_DEFINITIONS
from onlybtc.sources.service import collect_sources


async def test_analyze_all_radars_persists_outputs(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    result = analyze_radars(run_mode="mock", db=db)

    assert result["analyzed"] == len(RADAR_MODULES)
    with db.session() as session:
        radar_count = session.scalar(select(func.count()).select_from(schema.RadarOutput))
        feature_count = session.scalar(select(func.count()).select_from(schema.FeatureValue))
        module_count = session.scalar(select(func.count()).select_from(schema.ModuleJsonOutput))
        incomplete_quality_count = session.scalar(
            select(func.count())
            .select_from(schema.RadarOutput)
            .where(schema.RadarOutput.data_quality.in_(["low", "medium"]))
        )

    assert radar_count == len(RADAR_MODULES)
    assert feature_count >= 40
    assert module_count == len(RADAR_MODULES)
    assert incomplete_quality_count == 0


async def test_macro_radar_consumes_p1_c29_realtime_market_metrics(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    result = analyze_radars(module_ids=["macro_radar"], run_mode="mock", db=db)

    assert result["analyzed"] == 1
    macro = get_radar("macro_radar")
    metric_ids = {rule.metric_id for rule in macro.metrics}
    assert {
        "sp500",
        "dow_jones",
        "russell_2000",
        "gold",
        "wti_oil",
        "brent_oil",
    }.issubset(metric_ids)

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "macro_radar"
            )
        )

    assert output is not None
    features = output.payload["features"]
    feature_by_metric = {item["metric_id"]: item for item in features}
    assert feature_by_metric["sp500"]["source_id"] == "playwright-tradingview-sp500"
    assert feature_by_metric["sp500"]["freshness_policy"]["cadence"] == "intraday"
    assert feature_by_metric["wti_oil"]["source_id"] == "playwright-tradingview-wti-oil"
    assert feature_by_metric["brent_oil"]["available"] is True


async def test_onchain_provider_required_gaps_do_not_force_medium_quality(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    result = analyze_radars(module_ids=["onchain_valuation"], run_mode="mock", db=db)

    assert result["modules"][0]["data_quality"] == "high"
    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "onchain_valuation"
            )
        )

    assert output is not None
    quality = output.payload["evidence_summary"]["quality_explanation"]
    invalidation = output.payload["invalidation_signals"]
    feature_by_metric = {item["metric_id"]: item for item in output.payload["features"]}
    assert quality["coverage_score"] == 1.0
    assert quality["raw_coverage_score"] >= 0.8
    assert set(invalidation["provider_required_metrics"]) == {"whale_flow", "miner_flow"}
    assert invalidation["missing_metrics"] == []
    assert feature_by_metric["whale_flow"]["evidence_tier"] == "provider_required"
    assert feature_by_metric["whale_flow"]["quality_blocking"] is False


def test_all_metric_definitions_are_assigned_to_a_radar_module() -> None:
    metric_definitions = {metric.metric_id for metric in METRIC_DEFINITIONS}
    radar_metrics = {
        rule.metric_id
        for module in RADAR_MODULES
        for rule in module.metrics
    }

    assert sorted(metric_definitions - radar_metrics) == []


async def test_context_metrics_do_not_distort_radar_signal(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    analyze_radars(module_ids=["event_policy"], run_mode="mock", db=db)

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "event_policy"
            )
        )

    assert output is not None
    feature_by_metric = {item["metric_id"]: item for item in output.payload["features"]}
    assert feature_by_metric["fomc_blackout_active"]["role"] == "blackout_context"
    assert feature_by_metric["fomc_blackout_active"]["affects_signal"] is False
    assert feature_by_metric["fomc_blackout_active"]["score"] == 0.0
    assert feature_by_metric["fed_speech_scheduled_risk"]["role"] == "fed_speech_event"
    assert feature_by_metric["fed_speech_scheduled_risk"]["driver_eligible"] is False
    assert feature_by_metric["cpi_hours_until"]["role"] == "macro_data_event"


async def test_trade_structure_flow_roles_prevent_context_metrics_from_directional_signal(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    analyze_radars(module_ids=["trade_structure_flow"], run_mode="mock", db=db)

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "trade_structure_flow"
            )
        )

    assert output is not None
    feature_by_metric = {item["metric_id"]: item for item in output.payload["features"]}
    assert feature_by_metric["taker_buy_sell_ratio"]["role"] == "aggressive_flow"
    assert feature_by_metric["taker_buy_sell_ratio"]["affects_signal"] is False
    assert feature_by_metric["btc_return_5m"]["role"] == "price_response"
    assert feature_by_metric["btc_return_15m"]["role"] == "price_response"
    assert feature_by_metric["btc_return_5m"]["score"] == 0.0
    assert feature_by_metric["stablecoin_buying_power_proxy"]["role"] == "liquidity_context"
    assert feature_by_metric["stablecoin_buying_power_proxy"]["affects_signal"] is False
    assert feature_by_metric["mempool_blocks_to_clear"]["role"] == "execution_friction"
    assert feature_by_metric["mempool_blocks_to_clear"]["affects_signal"] is False
    assert feature_by_metric["liquidation_long_usd"]["role"] == "liquidation_event"
    assert feature_by_metric["liquidation_long_usd"]["affects_signal"] is False
    assert feature_by_metric["futures_basis"]["role"] == "derivatives_pricing_context"
    assert feature_by_metric["futures_basis"]["affects_signal"] is False


async def test_btc_total_state_uses_composite_only_roles_for_v2_contract(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    analyze_radars(module_ids=["btc_total_state"], run_mode="mock", db=db)

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "btc_total_state"
            )
        )

    assert output is not None
    feature_by_metric = {item["metric_id"]: item for item in output.payload["features"]}
    for metric_id in (
        "btc_price",
        "btc_1h_close",
        "btc_1h_return_pct",
        "btc_4h_return_pct",
        "btc_24h_return_pct",
        "btc_price_vs_1h_close_pct",
    ):
        assert feature_by_metric[metric_id]["role"] == "price_state"
        assert feature_by_metric[metric_id]["affects_signal"] is False
        assert feature_by_metric[metric_id]["driver_eligible"] is False
        assert feature_by_metric[metric_id]["score"] == 0.0
    for metric_id in (
        "btc_funding_rate",
        "btc_funding_band",
        "btc_open_interest",
        "btc_oi_change_1h_pct",
        "btc_oi_change_4h_pct",
        "btc_oi_change_24h_pct",
        "btc_oi_zscore",
    ):
        assert feature_by_metric[metric_id]["role"] == "perp_state"
        assert feature_by_metric[metric_id]["affects_signal"] is False
        assert feature_by_metric[metric_id]["driver_eligible"] is False
        assert feature_by_metric[metric_id]["score"] == 0.0
    assert feature_by_metric["btc_funding_band"]["duplicate_group_id"] == "derivatives_funding_btc"
    assert feature_by_metric["btc_oi_change_1h_pct"]["duplicate_group_id"] == "derivatives_open_interest_btc"
    for metric_id in ("btc_halving_estimated_days", "btc_halving_blocks_remaining"):
        assert feature_by_metric[metric_id]["role"] == "cycle_context"
        assert feature_by_metric[metric_id]["affects_signal"] is False
        assert feature_by_metric[metric_id]["affects_confidence"] is False
        assert feature_by_metric[metric_id]["driver_eligible"] is False
        assert feature_by_metric[metric_id]["score"] == 0.0
    assert feature_by_metric["btc_block_height"]["role"] == "audit_context"
    assert feature_by_metric["btc_block_height"]["affects_signal"] is False
    assert feature_by_metric["btc_block_height"]["affects_confidence"] is False
    assert feature_by_metric["btc_block_height"]["driver_eligible"] is False
    assert feature_by_metric["btc_block_height"]["score"] == 0.0


async def test_dollar_liquidity_v21_metrics_are_composite_or_risk_context(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    analyze_radars(module_ids=["dollar_liquidity"], run_mode="mock", db=db)

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "dollar_liquidity"
            )
        )

    assert output is not None
    feature_by_metric = {item["metric_id"]: item for item in output.payload["features"]}
    expected_roles = {
        "fed_balance_sheet": "liquidity_level",
        "bank_reserves": "reserve_buffer",
        "on_rrp": "liquidity_drain_pressure",
        "tga": "liquidity_drain_pressure",
        "sofr": "repo_funding_pressure",
        "iorb": "repo_funding_pressure",
        "net_liquidity_proxy_bil": "liquidity_level",
        "liquidity_impulse_z": "liquidity_impulse",
        "sofr_iorb_spread_bps": "repo_funding_pressure",
        "btc_vs_liquidity_residual": "btc_response_confirmation",
    }
    for metric_id, role in expected_roles.items():
        assert feature_by_metric[metric_id]["role"] == role
        assert feature_by_metric[metric_id]["affects_signal"] is False
        assert feature_by_metric[metric_id]["driver_eligible"] is False
        assert feature_by_metric[metric_id]["score"] == 0.0
    assert feature_by_metric["sofr_iorb_spread_bps"]["affects_risk_flags"] is True


async def test_options_volatility_uses_risk_roles_without_directional_signal(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)

    analyze_radars(module_ids=["options_volatility"], run_mode="mock", db=db)

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "options_volatility"
            )
        )

    assert output is not None
    feature_by_metric = {item["metric_id"]: item for item in output.payload["features"]}
    expected_roles = {
        "options_iv": "volatility_regime",
        "options_rv": "volatility_regime",
        "put_call_ratio": "protection_demand",
        "options_skew": "tail_risk",
        "options_expiry_notional": "expiry_pressure",
        "max_pain_distance": "pinning_structure",
        "gamma_wall_proxy_distance": "pinning_structure",
    }
    for metric_id, role in expected_roles.items():
        assert feature_by_metric[metric_id]["role"] == role
        assert feature_by_metric[metric_id]["affects_signal"] is False
        assert feature_by_metric[metric_id]["driver_eligible"] is False
        assert feature_by_metric[metric_id]["score"] == 0.0


async def test_radar_marks_current_run_and_historical_fallback_features(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, run_id="history-run", db=db)
    await collect_sources(
        mode=SourceMode.MOCK,
        source_ids=["binance-btcusdt"],
        run_id="current-run",
        db=db,
    )

    analyze_radars(
        module_ids=["btc_total_state"],
        run_mode="mock",
        collect_run_id="current-run",
        historical_fallback=True,
        db=db,
    )

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "btc_total_state"
            )
        )

    assert output is not None
    feature_by_metric = {item["metric_id"]: item for item in output.payload["features"]}
    assert feature_by_metric["btc_price"]["feature_run_scope"] == "current_run"
    assert feature_by_metric["btc_price"]["source_run_id"] == "current-run"
    assert feature_by_metric["btc_1h_close"]["feature_run_scope"] == "historical_fallback"
    assert feature_by_metric["btc_1h_close"]["fallback_reason"] == (
        "missing_current_collect_run_metric"
    )
    quality = output.payload["evidence_summary"]["quality_explanation"]
    assert quality["same_run_coverage_score"] < 1.0
    assert "historical_fallback_dependency" in quality["main_discount_reasons"]


def test_fund_flow_etf_outflow_is_not_marked_bullish(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime.now(UTC)
    with db.session() as session:
        _add_metric_series(
            session,
            "etf_net_flow",
            "playwright-glassnode-asset-overview",
            now,
            [-200_000_000.0, -100_000_000.0],
        )
        _add_metric_series(
            session,
            "etf_flow_7d",
            "playwright-glassnode-asset-overview",
            now,
            [-2_000_000_000.0, -1_400_000_000.0],
        )
        _add_metric_series(
            session,
            "exchange_balance_delta_1d_proxy",
            "playwright-glassnode-asset-overview",
            now,
            [0.0, -2_000.0],
        )
        _add_metric_series(
            session,
            "stablecoin_supply",
            "coingecko-global",
            now,
            [100.0, 99.0],
        )

    analyze_radars(module_ids=["fund_flow"], run_mode="live", db=db)

    with db.session() as session:
        output = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.module_id == "fund_flow"
            )
        )

    assert output is not None
    payload = output.payload
    by_metric = {item["metric_id"]: item for item in payload["features"]}
    assert by_metric["etf_net_flow"]["direction"] == "bearish"
    assert by_metric["etf_flow_7d"]["direction"] == "bearish"
    assert by_metric["etf_net_flow"]["flow_state"] == "bearish_outflow"
    assert by_metric["etf_net_flow"]["marginal_state"] == "pressure_easing"
    assert payload["fund_flow_absolute_direction"] == "bearish"
    assert payload["fund_flow_marginal_direction"] == "improving"
    assert payload["fund_flow_conflict_level"] == "high"
    assert payload["fund_flow_state"] == "bearish_but_improving"


def test_fund_flow_v22_registry_roles_are_context_or_state_machine_inputs() -> None:
    fund_flow = get_radar("fund_flow")
    by_metric = {rule.metric_id: rule for rule in fund_flow.metrics}

    expected_roles = {
        "etf_net_flow": "fast_flow_signal",
        "etf_net_flow_usd": "fast_flow_signal",
        "etf_flow_3d_z_60d": "demand_momentum",
        "etf_flow_7d_z_60d": "demand_persistence",
        "etf_outflow_streak_days": "pressure_warning",
        "stablecoin_supply": "composite_only",
        "stablecoin_mcap_change_7d": "liquidity_regime",
        "ssr_z_180d": "liquidity_buying_power",
        "exchange_balance_delta_1d_proxy": "context_only",
        "btc_exchange_netflow_z_60d": "supply_pressure_context",
        "exchange_flow_confirmed": "confirmed_supply_signal",
        "fund_flow_residual_z_60d": "btc_response_veto",
    }
    for metric_id, role in expected_roles.items():
        assert by_metric[metric_id].role == role
        assert by_metric[metric_id].affects_signal is False
        assert by_metric[metric_id].driver_eligible is False
        assert by_metric[metric_id].weight == 0.0


def _add_metric_series(
    session,
    metric_id: str,
    source_id: str,
    now: datetime,
    values: list[float],
) -> None:
    for index, value in enumerate(values):
        previous = values[index - 1] if index else None
        session.add(
            schema.MetricValue(
                metric_id=metric_id,
                source_id=source_id,
                run_id=f"collect-{metric_id}-{index}",
                run_mode="live",
                ts=now - timedelta(hours=len(values) - index),
                value=value,
                previous_value=previous,
                change_24h=((value - previous) / abs(previous)) if previous else None,
                quality_score=0.9,
            )
        )
