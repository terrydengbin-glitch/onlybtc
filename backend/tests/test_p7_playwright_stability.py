from __future__ import annotations

from pathlib import Path

from scripts.generate_p7_c05_playwright_stability_report import generate

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.governance.playwright_stability import (
    build_playwright_stability_report,
    status_contains_sensitive_fields,
)


def test_playwright_stability_confirms_artifacts_are_gitignored(tmp_path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("playwright-artifacts/*\n", encoding="utf-8")
    db = Database(tmp_path / "p7-c05.sqlite3")

    report = build_playwright_stability_report(db=db, gitignore_path=gitignore)

    assert report["artifact_policy"]["playwright_artifacts_ignored"] is True
    assert report["applied_to_production"] is False
    assert report["playwright_sources"]


def test_playwright_stability_detects_sensitive_status_fields() -> None:
    assert status_contains_sensitive_fields({"token": "secret"}) is True
    assert status_contains_sensitive_fields({"nested": [{"authorization": "Bearer x"}]}) is True
    assert status_contains_sensitive_fields({"message": "storage state saved"}) is False


def test_unverified_provider_auth_degrades_to_warning_not_collection_block(tmp_path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("playwright-artifacts/*\n", encoding="utf-8")
    db = Database(tmp_path / "p7-c05-auth.sqlite3")

    report = build_playwright_stability_report(db=db, gitignore_path=gitignore)
    auth_alerts = [alert for alert in report["alerts"] if alert["alert_id"] == "provider_auth_not_verified"]

    assert auth_alerts
    assert auth_alerts[0]["level"] == "warning"
    assert auth_alerts[0]["recommended_action"] == "degrade_provider_to_health_warning_until_verified"


def test_recent_playwright_health_warning_is_reported(tmp_path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("playwright-artifacts/*\n", encoding="utf-8")
    db = Database(tmp_path / "p7-c05-events.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.SourceHealthEvent(
                source_id="playwright-tradingview-dxy",
                status="warning",
                quality_score=0.5,
                latency_ms=1234,
                message="selector changed",
            )
        )

    report = build_playwright_stability_report(db=db, gitignore_path=gitignore)
    alert_ids = {alert["alert_id"] for alert in report["alerts"]}

    assert "playwright_recent_health_warnings" in alert_ids
    assert report["recent_playwright_health_events"][0]["failure_category"] == "selector_or_parse"


def test_playwright_stability_report_generator_writes_json_and_md() -> None:
    report = generate()
    assert report["schema_version"] == "p7.c05.playwright_stability.v1"
    assert report["json_path"].endswith("p7-c05-playwright-stability-report.json")
    assert report["md_path"].endswith("p7-c05-playwright-stability-report.md")
