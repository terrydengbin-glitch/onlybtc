from __future__ import annotations

from fastapi.testclient import TestClient

import onlybtc.api.app as app_module
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p6.alert_quality import alert_history, alert_quality


def test_p6_alert_history_and_quality_score_observability(tmp_path) -> None:
    db = Database(tmp_path / "p6-alert-quality.sqlite3")
    db.init_schema()
    _seed_alerts(db)

    history = alert_history(db=db)
    quality = alert_quality(db=db)
    filtered = alert_quality(alert_id="alert-p6-good", db=db)

    assert history["schema_version"] == "p6.alert_history.v1"
    assert history["status"] == "ok"
    assert history["history_mode"]["uses_latest_runtime_state"] is False
    assert history["count"] == 2
    assert quality["schema_version"] == "p6.alert_quality.v1"
    assert quality["summary"]["alert_count"] == 2
    assert quality["summary"]["scoring_policy"] == "observability_only_no_alert_mutation"
    assert quality["mutates_alert_state"] is False
    good = next(item for item in quality["items"] if item["alert_id"] == "alert-p6-good")
    weak = next(item for item in quality["items"] if item["alert_id"] == "alert-p6-weak")
    assert good["status"] == "passed"
    assert good["quality_score"] == 1.0
    assert weak["status"] == "warning"
    assert "has_evidence" in weak["issues"]
    assert "has_lifecycle_event" in weak["issues"]
    assert filtered["count"] == 1
    assert filtered["items"][0]["alert_id"] == "alert-p6-good"


def test_p6_alert_quality_empty_state_is_not_error(tmp_path) -> None:
    db = Database(tmp_path / "p6-alert-empty.sqlite3")
    db.init_schema()

    history = alert_history(db=db)
    quality = alert_quality(db=db)

    assert history["status"] == "empty"
    assert history["items"] == []
    assert quality["status"] == "empty"
    assert quality["summary"]["average_quality_score"] == 0.0


def test_p6_alert_history_and_quality_api_are_frontend_consumable(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "p6-alert-api.sqlite3")
    db.init_schema()
    _seed_alerts(db)
    monkeypatch.setattr(
        app_module,
        "p6_alert_history_payload",
        lambda limit=100, alert_id=None: alert_history(limit=limit, alert_id=alert_id, db=db),
    )
    monkeypatch.setattr(
        app_module,
        "p6_alert_quality_payload",
        lambda limit=100, alert_id=None: alert_quality(limit=limit, alert_id=alert_id, db=db),
    )
    client = TestClient(app_module.app)

    history_response = client.get("/api/p6/alerts/history?limit=10")
    quality_response = client.get("/api/p6/alerts/quality?alert_id=alert-p6-good")

    assert history_response.status_code == 200
    assert history_response.json()["schema_version"] == "p6.alert_history.v1"
    assert history_response.json()["items"][0]["quality_url"].startswith(
        "/api/p6/alerts/quality?alert_id="
    )
    assert quality_response.status_code == 200
    assert quality_response.json()["count"] == 1
    assert quality_response.json()["items"][0]["checks"]["has_lifecycle_event"] is True
    with db.session() as session:
        row = session.query(schema.AlgorithmAlert).filter_by(alert_id="alert-p6-good").one()
    assert row.level == "watch"
    assert row.state == "active"


def _seed_alerts(db: Database) -> None:
    with db.session() as session:
        session.add_all(
            [
                schema.AlgorithmAlert(
                    alert_id="alert-p6-good",
                    run_id="p3-p6-good",
                    level="watch",
                    state="active",
                    title="P6 good alert",
                    summary="Alert has evidence and lifecycle event.",
                    evidence_count=2,
                ),
                schema.AlertEvent(
                    alert_id="alert-p6-good",
                    event_type="created",
                    payload={"run_id": "p3-p6-good"},
                ),
                schema.AlgorithmAlert(
                    alert_id="alert-p6-weak",
                    run_id="p3-p6-weak",
                    level="warning",
                    state="active",
                    title="P6 weak alert",
                    summary="Alert lacks evidence and lifecycle event.",
                    evidence_count=0,
                ),
            ]
        )
