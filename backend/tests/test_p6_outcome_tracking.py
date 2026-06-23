from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

import onlybtc.api.app as app_module
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p6.article_pipeline import P6_AUTO_ARTICLE_MODULE_ID
from onlybtc.p6.outcome_tracking import outcome_tracking


def test_p6_outcome_tracking_observes_24h_72h_7d_returns(tmp_path) -> None:
    db = Database(tmp_path / "p6-outcomes.sqlite3")
    db.init_schema()
    anchor_at = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    _seed_article(db, anchor_at=anchor_at, final_view="bullish")
    _seed_prices(
        db,
        [
            (anchor_at - timedelta(minutes=5), 100_000.0),
            (anchor_at + timedelta(hours=24), 103_000.0),
            (anchor_at + timedelta(hours=72), 99_000.0),
            (anchor_at + timedelta(days=7), 108_000.0),
        ],
    )

    result = outcome_tracking(article_snapshot_id="p6article-final-p6-outcome", db=db)
    item = result["items"][0]

    assert result["schema_version"] == "p6.outcome_tracking.v1"
    assert result["tracking_policy"]["trading_advice"] is False
    assert item["anchor_price"]["value"] == 100_000.0
    assert item["horizons"]["24h"]["status"] == "observed"
    assert item["horizons"]["24h"]["return_pct"] == 0.03
    assert item["horizons"]["24h"]["directional_alignment"] == "aligned"
    assert item["horizons"]["72h"]["return_pct"] == -0.01
    assert item["horizons"]["72h"]["directional_alignment"] == "not_aligned"
    assert item["horizons"]["7d"]["return_pct"] == 0.08


def test_p6_outcome_tracking_handles_pending_and_empty_states(tmp_path) -> None:
    db = Database(tmp_path / "p6-outcomes-pending.sqlite3")
    db.init_schema()
    anchor_at = datetime.now(UTC) - timedelta(hours=1)
    _seed_article(db, anchor_at=anchor_at, final_view="neutral")
    _seed_prices(db, [(anchor_at - timedelta(minutes=1), 100_000.0)])

    pending = outcome_tracking(article_snapshot_id="p6article-final-p6-outcome", db=db)
    empty = outcome_tracking(article_snapshot_id="missing", db=db)

    assert pending["items"][0]["horizons"]["24h"]["status"] == "pending"
    assert pending["items"][0]["horizons"]["24h"]["directional_alignment"] == "pending"
    assert empty["status"] == "empty"
    assert empty["items"] == []


def test_p6_outcome_tracking_api_is_frontend_consumable(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "p6-outcomes-api.sqlite3")
    db.init_schema()
    anchor_at = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    _seed_article(db, anchor_at=anchor_at, final_view="neutral")
    _seed_prices(
        db,
        [
            (anchor_at - timedelta(minutes=5), 100_000.0),
            (anchor_at + timedelta(hours=24), 101_000.0),
        ],
    )
    monkeypatch.setattr(
        app_module,
        "p6_outcome_tracking_payload",
        lambda article_snapshot_id=None, limit=50, run_mode="live": outcome_tracking(
            article_snapshot_id=article_snapshot_id,
            limit=limit,
            run_mode=run_mode,
            db=db,
        ),
    )
    client = TestClient(app_module.app)

    response = client.get(
        "/api/p6/outcomes/track?article_snapshot_id=p6article-final-p6-outcome"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "p6.outcome_tracking.v1"
    assert payload["items"][0]["horizons"]["24h"]["status"] == "observed"
    assert payload["items"][0]["read_only"] is True
    assert payload["items"][0]["trading_advice"] is False


def _seed_article(db: Database, *, anchor_at: datetime, final_view: str) -> None:
    final_payload = {
        "schema_version": "p45.research_report.v2",
        "final_run_id": "final-p6-outcome",
        "pack_id": "pack-p6-outcome",
        "final_view": final_view,
        "final_view_cn": "观察",
    }
    article_payload = {
        "schema_version": "p6.auto_article.v1",
        "article_snapshot_id": "p6article-final-p6-outcome",
        "created_at": anchor_at.isoformat(),
        "final_run_id": "final-p6-outcome",
        "pack_id": "pack-p6-outcome",
        "draft_status": "ready",
        "title": "P6 outcome article",
    }
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="final-p6-outcome",
                    module_id="p45_final_article",
                    schema_version="p45.research_report.v2",
                    payload=final_payload,
                ),
                schema.ModuleJsonOutput(
                    run_id="p6article-final-p6-outcome",
                    module_id=P6_AUTO_ARTICLE_MODULE_ID,
                    schema_version="p6.auto_article.v1",
                    payload=article_payload,
                ),
            ]
        )


def _seed_prices(db: Database, rows: list[tuple[datetime, float]]) -> None:
    with db.session() as session:
        session.add_all(
            [
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
                for index, (ts, value) in enumerate(rows)
            ]
        )
