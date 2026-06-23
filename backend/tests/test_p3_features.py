from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from onlybtc.algorithms.features import MODULE_ID, calculate_p3_features
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.sources.service import ensure_source_registry


def test_p3_features_calculate_and_persist_traceable_rows(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    run_id="collect-feature-test-1",
                    ts=now - timedelta(hours=2),
                    value=100.0,
                    quality_score=0.95,
                ),
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    run_id="collect-feature-test-2",
                    ts=now - timedelta(hours=1),
                    value=110.0,
                    previous_value=100.0,
                    quality_score=0.95,
                ),
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="binance-btcusdt",
                    run_id="collect-feature-test-3",
                    ts=now,
                    value=121.0,
                    previous_value=110.0,
                    quality_score=0.95,
                ),
            ]
        )

    result = calculate_p3_features(
        metric_ids=["btc_price"],
        run_id="feature-test",
        db=db,
    )

    assert result["状态"] == "完成"
    assert result["已计算指标"] == 1
    assert result["写入特征数"] >= 8
    with db.session() as session:
        rows = session.scalars(
            select(schema.FeatureValue)
            .where(schema.FeatureValue.run_id == "feature-test")
            .order_by(schema.FeatureValue.feature_id)
        ).all()

    feature_ids = {row.feature_id for row in rows}
    assert "btc_price.change_window" in feature_ids
    assert "btc_price.ma_7" in feature_ids
    assert "btc_price.volatility" in feature_ids
    assert all(row.module_id == MODULE_ID for row in rows)

    change_window = next(row for row in rows if row.feature_id == "btc_price.change_window")
    assert change_window.value == 0.21
    assert change_window.metadata_json["metric_id"] == "btc_price"
    assert change_window.metadata_json["source_id"] == "binance-btcusdt"
    assert change_window.metadata_json["source_run_id"] == "collect-feature-test-3"
    assert change_window.metadata_json["latest_ts"] is not None
    assert change_window.metadata_json["effective_quality_score"] is not None
    assert change_window.metadata_json["source_freshness"] in {"fresh", "stale", "expired"}
    assert change_window.metadata_json["p3_quality_rule"] in {
        "normal",
        "watch_or_info_only",
        "evidence_only_no_sensitive_trigger",
        "reduced_short_term_sensitivity",
    }
    assert change_window.metadata_json["conflict"]["detected"] is False


def test_p3_features_skip_missing_metric(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    result = calculate_p3_features(
        metric_ids=["not_exist_metric"],
        run_id="feature-missing-test",
        db=db,
    )

    assert result["已计算指标"] == 0
    assert result["写入特征数"] == 0
    assert result["跳过"][0]["reason"] == "no_historical_window"

