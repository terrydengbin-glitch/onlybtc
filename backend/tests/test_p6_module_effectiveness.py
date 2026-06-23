from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

import onlybtc.api.app as app_module
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p6.article_pipeline import P6_AUTO_ARTICLE_MODULE_ID
from onlybtc.p6.module_effectiveness import module_effectiveness


def test_p6_module_effectiveness_scores_aligned_and_noisy_modules(tmp_path) -> None:
    db = Database(tmp_path / "p6-module-effectiveness.sqlite3")
    db.init_schema()
    anchor_at = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    _seed_article_final_and_prices(db, anchor_at=anchor_at)

    result = module_effectiveness(
        article_snapshot_id="p6article-final-p6-module",
        db=db,
    )
    bullish = _module(result, "macro_radar")
    bearish = _module(result, "derivatives_crowding")

    assert result["schema_version"] == "p6.module_effectiveness.v1"
    assert result["read_only"] is True
    assert result["mutates_module_weights"] is False
    assert bullish["observed_count"] == 3
    assert bullish["aligned_count"] == 2
    assert bullish["miss_count"] == 1
    assert bullish["effectiveness_score"] == 0.6667
    assert bullish["status"] == "effective"
    assert bearish["aligned_count"] == 1
    assert bearish["miss_count"] == 2
    assert bearish["status"] == "noisy"
    assert result["status"] == "warning"


def test_p6_module_effectiveness_pending_outcomes_are_insufficient(tmp_path) -> None:
    db = Database(tmp_path / "p6-module-pending.sqlite3")
    db.init_schema()
    anchor_at = datetime.now(UTC) - timedelta(hours=1)
    _seed_article_final_and_prices(db, anchor_at=anchor_at, include_future_prices=False)

    result = module_effectiveness(
        article_snapshot_id="p6article-final-p6-module",
        db=db,
    )
    macro = _module(result, "macro_radar")

    assert result["status"] == "insufficient"
    assert result["summary"]["gap_count"] == 1
    assert macro["observed_count"] == 0
    assert macro["status"] == "insufficient"
    assert macro["effectiveness_score"] is None


def test_p6_module_effectiveness_api_is_frontend_consumable(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "p6-module-api.sqlite3")
    db.init_schema()
    anchor_at = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    _seed_article_final_and_prices(db, anchor_at=anchor_at)
    monkeypatch.setattr(
        app_module,
        "p6_module_effectiveness_payload",
        lambda article_snapshot_id=None, limit=50, run_mode="live": module_effectiveness(
            article_snapshot_id=article_snapshot_id,
            limit=limit,
            run_mode=run_mode,
            db=db,
        ),
    )
    client = TestClient(app_module.app)

    response = client.get(
        "/api/p6/modules/effectiveness?article_snapshot_id=p6article-final-p6-module"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "p6.module_effectiveness.v1"
    assert payload["summary"]["module_count"] == 2
    assert payload["mutates_module_weights"] is False
    assert payload["trading_advice"] is False


def _module(result: dict, module_id: str) -> dict:
    return next(item for item in result["modules"] if item["module_id"] == module_id)


def _seed_article_final_and_prices(
    db: Database,
    *,
    anchor_at: datetime,
    include_future_prices: bool = True,
) -> None:
    final_payload = {
        "schema_version": "p45.research_report.v2",
        "final_run_id": "final-p6-module",
        "final_view": "neutral",
        "radar_module_scores": [
            {
                "radar_module": "macro_radar",
                "module_direction": "bullish",
                "module_score": 0.3,
            },
            {
                "radar_module": "derivatives_crowding",
                "module_direction": "bearish",
                "module_score": -0.4,
            },
        ],
    }
    article_payload = {
        "schema_version": "p6.auto_article.v1",
        "article_snapshot_id": "p6article-final-p6-module",
        "created_at": anchor_at.isoformat(),
        "final_run_id": "final-p6-module",
        "draft_status": "ready",
    }
    prices = [(anchor_at - timedelta(minutes=5), 100_000.0)]
    if include_future_prices:
        prices.extend(
            [
                (anchor_at + timedelta(hours=24), 104_000.0),
                (anchor_at + timedelta(hours=72), 95_000.0),
                (anchor_at + timedelta(days=7), 110_000.0),
            ]
        )
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="final-p6-module",
                    module_id="p45_final_article",
                    schema_version="p45.research_report.v2",
                    payload=final_payload,
                ),
                schema.ModuleJsonOutput(
                    run_id="p6article-final-p6-module",
                    module_id=P6_AUTO_ARTICLE_MODULE_ID,
                    schema_version="p6.auto_article.v1",
                    payload=article_payload,
                ),
                *[
                    schema.MetricValue(
                        metric_id="btc_price",
                        source_id="binance-btcusdt",
                        run_id=f"price-{index}",
                        run_mode="live",
                        ts=ts,
                        timeframe="spot",
                        value=value,
                        quality_score=1.0,
                    )
                    for index, (ts, value) in enumerate(prices)
                ],
            ]
        )
