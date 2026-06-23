from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

import onlybtc.api.app as app_module
import onlybtc.p6.dod as dod_module
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p6.article_pipeline import P6_AUTO_ARTICLE_MODULE_ID
from onlybtc.p6.dod import latest_p6_dod_report, run_p6_dod_mock
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID


def test_p6_dod_mock_aggregates_chain_and_writes_scores(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "p6-dod.sqlite3")
    db.init_schema()
    monkeypatch.setattr(dod_module, "paths", SimpleNamespace(project_root=tmp_path))
    anchor_at = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    _seed_p6_dod_fixture(db, anchor_at=anchor_at)

    first = run_p6_dod_mock(
        article_snapshot_id="p6article-final-p6-dod",
        db=db,
    )
    second = run_p6_dod_mock(
        article_snapshot_id="p6article-final-p6-dod",
        db=db,
    )
    latest = latest_p6_dod_report()

    assert first["schema_version"] == "p6.dod_report.v1"
    assert first["status"] in {"passed", "warning"}
    assert first["dod_boundary"]["production_weight_mutation"] is False
    assert first["artifacts"]["article_replay"]["schema_version"] == "p6.article_replay.v1"
    assert first["replay_scores_written"]
    assert first["calibration_notes_written"][0]["production_weight_mutation"] is False
    assert second["replay_scores_written"][0]["action"] == "existing"
    assert latest is not None
    assert latest["schema_version"] == "p6.dod_report.v1"
    assert (tmp_path / "reports" / "p6-dod-report.json").exists()
    assert (tmp_path / "reports" / "p6-dod-report.md").exists()
    with db.session() as session:
        replay_scores = session.query(schema.ReplayScore).filter_by(
            snapshot_id="final-p6-dod"
        ).all()
        notes = session.query(schema.CalibrationNote).filter_by(target="final-p6-dod").all()
    assert len(replay_scores) == 3
    assert len(notes) == 1


def test_p6_dod_api_is_frontend_consumable(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module,
        "run_p6_dod_mock",
        lambda article_snapshot_id=None, run_mode="live", write_scores=True: {
            "schema_version": "p6.dod_report.v1",
            "status": "passed",
            "article_snapshot_id": article_snapshot_id,
            "report_paths": {"json_url": "/reports/p6-dod-report.json"},
        },
    )
    monkeypatch.setattr(
        app_module,
        "latest_p6_dod_report",
        lambda: {
            "schema_version": "p6.dod_report.v1",
            "status": "passed",
        },
    )
    client = TestClient(app_module.app)

    run_response = client.post(
        "/api/p6/dod/mock-run?article_snapshot_id=p6article-final-p6-dod"
    )
    latest_response = client.get("/api/p6/dod/latest")

    assert run_response.status_code == 200
    assert run_response.json()["schema_version"] == "p6.dod_report.v1"
    assert run_response.json()["article_snapshot_id"] == "p6article-final-p6-dod"
    assert latest_response.status_code == 200
    assert latest_response.json()["status"] == "passed"


def _seed_p6_dod_fixture(db: Database, *, anchor_at: datetime) -> None:
    final_payload = {
        "schema_version": "p45.research_report.v2",
        "final_run_id": "final-p6-dod",
        "pack_id": "pack-p6-dod",
        "final_view": "bullish",
        "contract_validation": {"status": "passed"},
        "data_quality": {"data_quality_level": "high"},
        "metric_evidence": [
            {
                "evidence_id": "ev-p6-dod-1",
                "radar_module": "macro_radar",
                "metric_id": "ofr_fsi",
                "source_id": "ofr-source",
                "metric_effective_score": 0.2,
                "direction": "bullish",
            }
        ],
        "radar_module_scores": [
            {
                "radar_module": "macro_radar",
                "module_direction": "bullish",
                "module_score": 0.3,
            }
        ],
    }
    article_payload = {
        "schema_version": "p6.auto_article.v1",
        "article_snapshot_id": "p6article-final-p6-dod",
        "created_at": anchor_at.isoformat(),
        "final_run_id": "final-p6-dod",
        "pack_id": "pack-p6-dod",
        "draft_status": "ready",
        "title": "P6 DoD article",
        "summary": "P6 DoD article summary.",
        "body": "P6 DoD article body with traceable evidence.",
        "evidence_citations": [
            {
                "evidence_id": "ev-p6-dod-1",
                "radar_module": "macro_radar",
                "metric_id": "ofr_fsi",
            }
        ],
        "quality_gate": {
            "status": "passed",
            "checks": {"citations_traceable": True},
        },
        "publish_boundary": {
            "auto_publish_allowed": False,
            "manual_review_required": True,
        },
    }
    pack_payload = {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-p6-dod",
        "analysts": [
            {
                "analyst_id": "macro",
                "modules": [
                    {
                        "radar_module": "macro_radar",
                        "metrics": [
                            {
                                "evidence_id": "ev-p6-dod-1",
                                "radar_module": "macro_radar",
                                "metric_id": "ofr_fsi",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    prices = [
        (anchor_at - timedelta(minutes=5), 100_000.0),
        (anchor_at + timedelta(hours=24), 102_000.0),
        (anchor_at + timedelta(hours=72), 103_000.0),
        (anchor_at + timedelta(days=7), 104_000.0),
    ]
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="final-p6-dod",
                    module_id="p45_final_article",
                    schema_version="p45.research_report.v2",
                    payload=final_payload,
                ),
                schema.ModuleJsonOutput(
                    run_id="p6article-final-p6-dod",
                    module_id=P6_AUTO_ARTICLE_MODULE_ID,
                    schema_version="p6.auto_article.v1",
                    payload=article_payload,
                ),
                schema.ModuleJsonOutput(
                    run_id="pack-p6-dod",
                    module_id=P45_EVIDENCE_PACK_MODULE_ID,
                    schema_version="p45.evidence_pack.v1",
                    payload=pack_payload,
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
