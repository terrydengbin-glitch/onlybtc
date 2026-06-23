from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.direct_trend.evidence import (
    BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
    build_btc_direct_trend_evidence,
)


def test_btc_direct_trend_evidence_writes_five_categories_with_lineage(tmp_path) -> None:
    db = Database(tmp_path / "btc-direct-trend-evidence.sqlite3")
    db.init_schema()
    now = datetime.now(UTC)
    with db.session() as session:
        _seed_metric_history(
            session,
            "taker_buy_sell_ratio",
            "binance-btcusdt-taker-buy-sell-ratio",
            [0.94, 1.02, 1.04, 0.99, 1.08, 1.12],
            now,
        )
        _seed_metric_history(
            session,
            "exchange_spot_volume",
            "binance-btcusdt",
            [1_000_000_000, 1_100_000_000, 1_200_000_000, 1_250_000_000, 1_300_000_000],
            now,
        )
        for metric_id, source_id, values in (
            ("btc_return_1h", "binance-btcusdt-kline-1h", [0.001, 0.002, 0.003]),
            ("btc_return_4h", "binance-btcusdt-kline-1h", [0.005, 0.006, 0.008]),
            ("btc_return_24h", "binance-btcusdt-kline-1h", [0.02, 0.025, 0.03]),
            ("oi_impulse_z_15m", "binance-btcusdt-open-interest", [0.1, 0.2, 0.3]),
            ("oi_impulse_z_1h", "binance-btcusdt-open-interest", [0.2, 0.3, 0.4]),
            ("oi_impulse_z_4h", "binance-btcusdt-open-interest", [0.3, 0.4, 0.5]),
            ("funding_rate_8h_equiv_z", "binance-btcusdt-funding", [0.1, 0.2, 0.3]),
            ("funding_acceleration_z_24h", "binance-btcusdt-funding", [0.0, 0.1, 0.2]),
            ("liquidation_followthrough_score", "binance-usdm-force-order-btcusdt", [0.1, 0.2, 0.3]),
            ("liquidation_absorption_score", "binance-usdm-force-order-btcusdt", [0.2, 0.3, 0.4]),
            ("btc_expected_return_24h", "treasury-credit-derived", [-0.01, -0.02, -0.03]),
            ("btc_residual_24h", "treasury-credit-derived", [0.01, 0.015, 0.02]),
            ("btc_residual_z_60d", "treasury-credit-derived", [0.5, 0.6, 0.7]),
            ("cpi_hours_until", "official-macro-event-calendar", [36.0, 24.0, 12.0]),
            ("fomc_hours_until", "official-macro-event-calendar", [72.0, 48.0, 30.0]),
            ("pce_hours_until", "official-macro-event-calendar", [96.0, 72.0, 60.0]),
            ("nfp_hours_until", "official-macro-event-calendar", [120.0, 96.0, 84.0]),
            ("fomc_event_risk", "fed-fomc-blackout-calendar", [0.1, 0.2, 0.3]),
            ("macro_surprise_score", "fxstreet-economic-calendar", [0.0, 0.2, 0.4]),
        ):
            _seed_metric_history(session, metric_id, source_id, values, now)

    result = build_btc_direct_trend_evidence(run_id="p1c75-test", db=db)

    assert result["status"] == "completed"
    assert result["written"] >= 20
    assert set(result["category_counts"]) == {
        "price_structure",
        "orderflow_acceptance",
        "derivatives_positioning",
        "btc_residual_cross_asset",
        "event_overlay_context",
    }
    with db.session() as session:
        rows = session.scalars(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p1c75-test",
                schema.FeatureValue.module_id == BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
            )
        ).all()

    assert len(rows) == result["written"]
    for row in rows:
        metadata = row.metadata_json
        assert metadata["snapshot_id"]
        assert metadata["derived_at"]
        assert metadata["valid_until"]
        assert metadata["freshness_state"] in {"fresh", "partial", "stale", "missing"}
        assert "source_health" in metadata
        assert metadata["upstream_metric_ids"]
        assert metadata["source_tier"] in {"fast_direct", "slow_context", "event_context"}

    by_feature = {row.feature_id: row for row in rows}
    taker_delta = by_feature[
        "btc_direct_trend.orderflow_acceptance.taker_delta_quote"
    ]
    assert taker_delta.value is not None
    assert "not full OFI/MLOFI" in " ".join(taker_delta.metadata_json["limitations"])
    cvd = by_feature["btc_direct_trend.orderflow_acceptance.cvd_slope_z"]
    assert cvd.metadata_json["upstream_metric_ids"] == [
        "taker_buy_sell_ratio",
        "exchange_spot_volume",
    ]
    semantic = by_feature["btc_direct_trend.btc_residual_cross_asset.residual_semantic"]
    assert semantic.metadata_json["semantic_state"] == "external_pressure_down_but_btc_resilient"
    interaction = by_feature[
        "btc_direct_trend.derivatives_positioning.price_oi_interaction_state"
    ]
    assert interaction.metadata_json["semantic_state"] == "aggressive_long_building"


def test_btc_direct_trend_evidence_marks_missing_windows(tmp_path) -> None:
    db = Database(tmp_path / "btc-direct-trend-missing.sqlite3")
    db.init_schema()

    result = build_btc_direct_trend_evidence(run_id="p1c75-missing-test", db=db)

    assert result["written"] > 0
    assert result["freshness_counts"]["missing"] >= 1
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue).where(
                schema.FeatureValue.run_id == "p1c75-missing-test",
                schema.FeatureValue.feature_id == "btc_direct_trend.price_structure.btc_return_4h",
            )
        )
    assert row is not None
    assert row.value is None
    assert row.metadata_json["freshness_state"] == "missing"
    assert row.metadata_json["missing_reason"] == "no_historical_window"


def _seed_metric_history(
    session,
    metric_id: str,
    source_id: str,
    values: list[float],
    now: datetime,
) -> None:
    for index, value in enumerate(values):
        ts = now - timedelta(minutes=5 * (len(values) - index - 1))
        session.add(
            schema.MetricValue(
                run_id="collect-test",
                run_mode="live",
                metric_id=metric_id,
                source_id=source_id,
                ts=ts,
                timeframe="spot",
                value=value,
                previous_value=values[index - 1] if index else None,
                quality_score=0.95,
            )
        )
