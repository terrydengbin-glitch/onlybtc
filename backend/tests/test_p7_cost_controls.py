from __future__ import annotations

from datetime import UTC, datetime, timedelta

from scripts.generate_p7_c06_cost_control_report import generate

from onlybtc.core.config import Settings
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.governance.cost_controls import build_cost_control_report


def test_cost_control_report_exposes_source_and_llm_budgets(tmp_path) -> None:
    db = Database(tmp_path / "p7-c06.sqlite3")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    report = build_cost_control_report(db=db, settings=Settings(), cache_dir=cache_dir, now=_now())

    assert report["applied_to_production"] is False
    assert report["config"]["source_collection"]["source_max_retries"] >= 1
    assert report["config"]["p4_llm_budget"]["has_explicit_call_budget"] is True
    assert report["config"]["p4_llm_budget"]["has_explicit_token_budget"] is True
    assert "p45_research_budget_gap" in {alert["alert_id"] for alert in report["alerts"]}


def test_cost_control_report_detects_rate_limit_saturation(tmp_path) -> None:
    db = Database(tmp_path / "p7-c06-rate.sqlite3")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.RateLimitEvent(
                source_id="fred-test",
                current=100,
                limit=100,
                reset_at=_now() + timedelta(minutes=5),
                created_at=_now(),
            )
        )

    report = build_cost_control_report(db=db, settings=Settings(), cache_dir=cache_dir, now=_now())
    alert_ids = {alert["alert_id"] for alert in report["alerts"]}

    assert "recent_rate_limit_saturation" in alert_ids
    assert report["recent_rate_limit_events"][0]["utilization"] == 1.0


def test_cost_control_report_summarizes_cache_files(tmp_path) -> None:
    db = Database(tmp_path / "p7-c06-cache.sqlite3")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "sample.json").write_text("{}", encoding="utf-8")

    report = build_cost_control_report(db=db, settings=Settings(), cache_dir=cache_dir, now=_now())

    assert report["cache"]["exists"] is True
    assert report["cache"]["file_count"] == 1
    assert report["cache"]["total_bytes"] == 2


def test_cost_control_report_detects_fallback_events(tmp_path) -> None:
    db = Database(tmp_path / "p7-c06-fallback.sqlite3")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.FallbackEvent(
                source_id="primary",
                fallback_source_id="fallback",
                reason="provider_timeout",
                discount=0.2,
                created_at=_now(),
            )
        )

    report = build_cost_control_report(db=db, settings=Settings(), cache_dir=cache_dir, now=_now())

    assert report["fallback_summary"]["fallback_event_count"] == 1
    assert "fallback_events_present" in {alert["alert_id"] for alert in report["alerts"]}


def test_cost_control_report_generator_writes_json_and_md() -> None:
    report = generate()
    assert report["schema_version"] == "p7.c06.cost_control_cache_rate_limit.v1"
    assert report["json_path"].endswith("p7-c06-cost-control-cache-rate-limit-report.json")
    assert report["md_path"].endswith("p7-c06-cost-control-cache-rate-limit-report.md")


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, tzinfo=UTC)
