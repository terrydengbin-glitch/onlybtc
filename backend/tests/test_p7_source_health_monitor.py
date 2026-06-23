from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.generate_p7_c04_source_health_monitor_report import generate

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.governance.source_health import build_source_health_monitor_report


def test_source_health_monitor_reports_healthy_snapshot(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-healthy.sqlite3")
    _seed_snapshot(db, status="healthy", score=0.91)

    report = build_source_health_monitor_report(db=db, now=_now())

    assert report["overall_status"] == "healthy"
    assert report["applied_to_production"] is False
    assert report["alert_count"] == 0
    assert report["downstream_policy"]["participation_policy"] == "full"


def test_source_health_monitor_preserves_source_detail_lists(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-source-details.sqlite3")
    _seed_snapshot(
        db,
        status="healthy",
        score=0.91,
        stale_sources=[{"source_id": "stale-source"}],
        business_lagging_sources=[{"source_id": "lagging-source"}],
        missing_sources=[{"source_id": "missing-source"}],
    )

    report = build_source_health_monitor_report(db=db, now=_now())
    quality = report["latest_data_quality"]

    assert quality["stale_sources"][0]["source_id"] == "stale-source"
    assert quality["business_lagging_sources"][0]["source_id"] == "lagging-source"
    assert quality["missing_sources"][0]["source_id"] == "missing-source"


def test_source_health_monitor_raises_recent_error_and_missing_alerts(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-warning.sqlite3")
    _seed_snapshot(
        db,
        status="warning",
        score=0.62,
        freshness_counts={"fresh": 10, "stale": 2, "expired": 1, "missing": 1},
    )
    with db.session() as session:
        session.add(
            schema.SourceHealthEvent(
                source_id="binance-btcusdt",
                status="error",
                quality_score=0.2,
                latency_ms=9000,
                message="provider timeout",
                created_at=_now(),
            )
        )

    report = build_source_health_monitor_report(db=db, now=_now())
    alert_ids = {alert["alert_id"] for alert in report["alerts"]}

    assert report["overall_status"] == "critical"
    assert "source_freshness_gap" in alert_ids
    assert "recent_source_health_events" in alert_ids
    assert report["downstream_policy"]["publish_gate_recommendation"] == "block_production_publish"


def test_source_health_monitor_treats_fresh_current_quality_warning_as_watch(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-fresh-warning.sqlite3")
    _seed_snapshot(db, status="healthy", score=0.91)
    with db.session() as session:
        session.add(
            schema.SourceHealthEvent(
                source_id="binance-btcusdt-open-interest",
                status="warning",
                quality_score=0.6,
                latency_ms=None,
                message=(
                    "collection_freshness=fresh collection_age_seconds=0.0 "
                    "expected_seconds=600.0 business_recency=current business_age_seconds=42.0"
                ),
                created_at=_now(),
            )
        )

    report = build_source_health_monitor_report(db=db, now=_now())
    recent = next(alert for alert in report["alerts"] if alert["alert_id"] == "recent_source_health_events")

    assert recent["level"] == "watch"
    assert report["overall_status"] == "watch"


def test_source_health_monitor_keeps_stale_warning_as_warning(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-stale-warning.sqlite3")
    _seed_snapshot(db, status="healthy", score=0.91)
    with db.session() as session:
        session.add(
            schema.SourceHealthEvent(
                source_id="alternative-fear-greed",
                status="warning",
                quality_score=0.6,
                latency_ms=None,
                message=(
                    "collection_freshness=stale collection_age_seconds=9000.0 "
                    "expected_seconds=86400.0 business_recency=current"
                ),
                created_at=_now(),
            )
        )

    report = build_source_health_monitor_report(db=db, now=_now())
    recent = next(alert for alert in report["alerts"] if alert["alert_id"] == "recent_source_health_events")

    assert recent["level"] == "warning"
    assert report["overall_status"] == "warning"


def test_source_health_monitor_handles_missing_snapshot(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-missing.sqlite3")
    report = build_source_health_monitor_report(db=db, now=_now())

    assert report["overall_status"] == "warning"
    assert report["alerts"][0]["alert_id"] == "data_quality_snapshot_missing"
    assert report["latest_data_quality"]["status"] == "missing"


def test_source_health_monitor_detects_run_mode_and_403(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-403.sqlite3")
    _seed_snapshot(
        db,
        status="healthy",
        score=0.82,
        fallback_summary={
            "fallback_event_count": 1,
            "warning_source_count": 1,
            "http_403_sources": ["playwright-glassnode-sopr"],
            "warning_sources": ["playwright-glassnode-sopr"],
        },
        run_mode_summary={"production_blocker": True, "mock_metric_values": 3},
    )

    report = build_source_health_monitor_report(db=db, now=_now())
    alert_ids = {alert["alert_id"] for alert in report["alerts"]}

    assert report["overall_status"] == "critical"
    assert "source_auth_or_permission_403" in alert_ids
    assert "run_mode_mixing_production_blocker" in alert_ids


def test_source_health_monitor_prefers_scoped_run_mode_snapshot_over_newer_legacy_snapshot(tmp_path) -> None:
    db = Database(tmp_path / "p7-c04-scoped-run-mode.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.DataQualitySnapshot(
                run_id="scoped-clean-live",
                score=0.9,
                status="healthy",
                payload={
                    "source_count": 12,
                    "freshness_counts": {"fresh": 12, "stale": 0, "expired": 0, "missing": 0},
                    "business_recency_counts": {"current": 12},
                    "business_lagging_sources": [],
                    "fallback_summary": {"fallback_event_count": 0, "warning_source_count": 0},
                    "run_mode_summary": {
                        "current_run_id": "collect-current",
                        "current_run": {
                            "live_metric_values": 10,
                            "mock_metric_values": 0,
                            "test_metric_values": 0,
                            "unknown_metric_values": 0,
                            "mixed_metric_ids": [],
                            "production_blocker": False,
                        },
                        "history": {
                            "mock_metric_values": 3,
                            "history_contamination_warning": True,
                        },
                        "production_blocker": False,
                    },
                    "registry_drift_count": 0,
                },
                created_at=_now(),
            )
        )
        session.add(
            schema.DataQualitySnapshot(
                run_id="newer-legacy-history-mixed",
                score=0.9,
                status="healthy",
                payload={
                    "source_count": 12,
                    "freshness_counts": {"fresh": 12, "stale": 0, "expired": 0, "missing": 0},
                    "business_recency_counts": {"current": 12},
                    "business_lagging_sources": [],
                    "fallback_summary": {"fallback_event_count": 0, "warning_source_count": 0},
                    "run_mode_summary": {"production_blocker": True, "mock_metric_values": 3},
                    "registry_drift_count": 0,
                },
                created_at=_now() + timedelta(minutes=1),
            )
        )

    report = build_source_health_monitor_report(db=db, now=_now() + timedelta(minutes=2))
    alert_ids = {alert["alert_id"] for alert in report["alerts"]}

    assert report["latest_data_quality"]["run_id"] == "scoped-clean-live"
    assert "run_mode_mixing_production_blocker" not in alert_ids
    assert report["overall_status"] == "healthy"


def test_source_health_report_generator_writes_json_and_md() -> None:
    report = generate()
    assert report["schema_version"] == "p7.c04.source_health_monitor.v1"
    assert report["json_path"].endswith("p7-c04-source-health-monitor-report.json")
    assert report["md_path"].endswith("p7-c04-source-health-monitor-report.md")


def _seed_snapshot(
    db: Database,
    *,
    status: str,
    score: float,
    freshness_counts: dict | None = None,
    fallback_summary: dict | None = None,
    run_mode_summary: dict | None = None,
    stale_sources: list[dict] | None = None,
    business_lagging_sources: list[dict] | None = None,
    missing_sources: list[dict] | None = None,
) -> None:
    db.init_schema()
    payload = {
        "source_count": 12,
        "freshness_counts": freshness_counts or {"fresh": 12, "stale": 0, "expired": 0, "missing": 0},
        "business_recency_counts": {"current": 12},
        "stale_sources": stale_sources or [],
        "business_lagging_sources": business_lagging_sources or [],
        "missing_sources": missing_sources or [],
        "fallback_summary": fallback_summary
        or {"fallback_event_count": 0, "warning_source_count": 0, "http_403_sources": []},
        "run_mode_summary": run_mode_summary or {"production_blocker": False},
        "registry_drift_count": 0,
    }
    with db.session() as session:
        session.add(
            schema.DataQualitySnapshot(
                run_id="p7-c04-test-snapshot",
                score=score,
                status=status,
                payload=payload,
                created_at=_now(),
            )
        )


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, tzinfo=UTC)
