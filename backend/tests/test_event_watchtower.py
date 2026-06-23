from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient

from onlybtc.api.app import app
from onlybtc.db import schema
from onlybtc.db.repositories import EventWatchtowerRepository
from onlybtc.db.session import Database
from onlybtc.event_window.connectors import actuals
from onlybtc.event_window.connectors.actuals import collect_actual_snapshot
from onlybtc.event_window.connectors import official_calendar
from onlybtc.event_window.connectors import reactions
from onlybtc.event_window.connectors.reactions import build_post_event_reaction
from onlybtc.event_window.connectors.shock_lane import collect_official_shocks
from onlybtc.event_window.daemon import EventWatchtowerDaemon
from onlybtc.event_window.speech_analyzer import analyze_fed_texts, boundary_audit
from onlybtc.event_window.watchtower import (
    EVENT_WINDOW_SCHEMA_VERSION,
    _overlay_from_state,
    _source_quality_breakdown,
    _state_from_inputs,
    build_event_window_payload,
)


def _released_event(release: datetime) -> dict:
    return {
        "event_id": "cpi-202606101230",
        "event_type": "CPI",
        "release_time": release.isoformat(),
        "release_time_utc": release.isoformat(),
        "expectation": {"consensus": 316.5},
        "actual_snapshot": {
            "actual_status": "available",
            "observations": [{"latest_observation": 317.2}],
        },
    }


def _insert_reaction_metric_rows(
    db: Database,
    release: datetime,
    *,
    prices: list[float],
    oi: list[float],
    funding: float,
    basis: float,
    cvd: list[float],
    ofi: list[float],
) -> None:
    offsets = [0, 5, 30, 120]
    rows = [
        schema.MetricValue(
            metric_id="btc_price",
            source_id="test-price",
            run_id=f"price-{index}",
            run_mode="test",
            ts=release + timedelta(minutes=offsets[index]),
            value=value,
        )
        for index, value in enumerate(prices)
    ]
    rows.extend(
        [
            schema.MetricValue(
                metric_id="btc_open_interest",
                source_id="test-oi",
                run_id="oi-start",
                run_mode="test",
                ts=release,
                value=oi[0],
            ),
            schema.MetricValue(
                metric_id="btc_open_interest",
                source_id="test-oi",
                run_id="oi-end",
                run_mode="test",
                ts=release + timedelta(minutes=30),
                value=oi[1],
            ),
            schema.MetricValue(
                metric_id="btc_funding_rate",
                source_id="test-funding",
                run_id="funding",
                run_mode="test",
                ts=release + timedelta(minutes=30),
                value=funding,
            ),
            schema.MetricValue(
                metric_id="btc_basis",
                source_id="test-basis",
                run_id="basis",
                run_mode="test",
                ts=release + timedelta(minutes=30),
                value=basis,
            ),
            schema.MetricValue(
                metric_id="cvd_slope_z",
                source_id="test-cvd",
                run_id="cvd-start",
                run_mode="test",
                ts=release,
                value=cvd[0],
            ),
            schema.MetricValue(
                metric_id="cvd_slope_z",
                source_id="test-cvd",
                run_id="cvd-end",
                run_mode="test",
                ts=release + timedelta(minutes=30),
                value=cvd[1],
            ),
            schema.MetricValue(
                metric_id="taker_delta_quote",
                source_id="test-ofi",
                run_id="ofi-start",
                run_mode="test",
                ts=release,
                value=ofi[0],
            ),
            schema.MetricValue(
                metric_id="taker_delta_quote",
                source_id="test-ofi",
                run_id="ofi-end",
                run_mode="test",
                ts=release + timedelta(minutes=30),
                value=ofi[1],
            ),
        ]
    )
    with db.session() as session:
        session.add_all(rows)


def test_event_watchtower_schema_and_repository_roundtrip(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-event-test.sqlite3")
    db.init_schema()
    payload = build_event_window_payload(now=datetime(2026, 5, 28, 8, 0, tzinfo=UTC))

    with db.session() as session:
        saved = EventWatchtowerRepository(session).save_snapshot(payload)

    with db.session() as session:
        repo = EventWatchtowerRepository(session)
        latest = repo.latest_snapshot()
        calendar = repo.list_calendar()
        alerts = repo.list_alerts()
        tables = {
            "snapshots": session.query(schema.EventWatchtowerSnapshot).count(),
            "calendar": session.query(schema.EventCalendarItem).count(),
        }

    assert saved["schema_version"] == EVENT_WINDOW_SCHEMA_VERSION
    assert latest is not None
    assert latest["schema_version"] == EVENT_WINDOW_SCHEMA_VERSION
    assert calendar
    assert alerts
    assert tables["snapshots"] == 1
    assert tables["calendar"] >= 4


def test_event_watchtower_daemon_pause_resume_collects_snapshot(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-event-daemon.sqlite3")
    daemon = EventWatchtowerDaemon()

    start_status = daemon.start(db=db)
    paused = daemon.pause()
    resumed = daemon.resume(db=db)

    assert start_status["status"] == "running"
    assert paused["status"] == "paused_by_user"
    assert resumed["status"] == "running"
    assert resumed["scheduler_enabled"] is True
    assert resumed["source_cadence"]
    assert resumed["health_state"] in {"healthy", "degraded"}
    assert resumed["watchdog"]["enabled"] is True

    with db.session() as session:
        assert EventWatchtowerRepository(session).latest_snapshot() is not None
        assert EventWatchtowerRepository(session).scheduler_state()


def test_event_watchtower_scheduler_tick_respects_due_gate(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-event-due-gate.sqlite3")
    daemon = EventWatchtowerDaemon()
    daemon.start(db=db)

    with daemon._lock:  # noqa: SLF001 - due gate regression requires controlled schedule.
        for source_group, item in daemon._schedule.items():  # noqa: SLF001
            item["next_due_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        daemon._schedule["btc_reaction"]["next_due_at"] = (  # noqa: SLF001
            datetime.now(UTC) - timedelta(seconds=1)
        ).isoformat()

    tick = daemon.scheduler_tick(db=db)
    health = daemon.health(attempt_recovery=False)

    assert tick["ran"] is True
    assert tick["due_source_groups"] == ["btc_reaction"]
    assert health["last_tick_mode"] == "scheduled_due_tick"
    assert health["last_due_sources"] == ["btc_reaction"]
    assert "official_calendar" in health["last_skipped_sources"]
    assert "fed_rss_official_text" in health["last_skipped_sources"]

    with db.session() as session:
        latest = EventWatchtowerRepository(session).latest_snapshot()
        assert latest is not None
        fetches = latest["source_fetches"]
        skipped = [item for item in fetches if item.get("status") == "skipped_not_due"]
        assert any(item.get("source_group") == "official_calendar" for item in skipped)
        assert any(item.get("source_group") == "fed_rss_official_text" for item in skipped)
        assert not any(
            item.get("source_id") in {"fed-fomc-calendar", "fed-rss", "bea-release-schedule"}
            for item in fetches
        )


def test_event_watchtower_daemon_watchdog_health_states(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-event-health.sqlite3")
    daemon = EventWatchtowerDaemon()
    healthy = daemon.start(db=db)

    assert healthy["watchdog"]["thresholds"]["last_tick_max_age_sec"] > 0
    assert healthy["health_state"] in {"healthy", "degraded"}

    with daemon._lock:  # noqa: SLF001 - watchdog regression needs controlled stale state.
        daemon._last_tick_at = datetime.now(UTC) - timedelta(minutes=10)  # noqa: SLF001
    stale = daemon.health(attempt_recovery=False)
    assert stale["health_state"] == "stale"
    assert "scheduler_tick_stale" in stale["stale_reasons"]

    paused = daemon.pause()
    assert paused["health_state"] == "paused_by_user"


def test_event_window_api_latest_and_daemon_controls() -> None:
    client = TestClient(app)

    latest = client.get("/api/event-window/latest")
    status = client.get("/api/event-window/daemon/status")
    health = client.get("/api/event-window/daemon/health")
    pause = client.post("/api/event-window/daemon/pause")
    resume = client.post("/api/event-window/daemon/resume")
    timeline = client.get("/api/event-window/timeline")
    run_once = client.post("/api/event-window/run-once")

    assert latest.status_code == 200
    assert latest.json()["schema_version"] == EVENT_WINDOW_SCHEMA_VERSION
    assert latest.json()["event_window"]["direct_score_impact"] is False
    assert status.status_code == 200
    assert health.status_code == 200
    assert health.json()["daemon"]["watchdog"]["enabled"] is True
    assert pause.json()["daemon"]["status"] == "paused_by_user"
    assert resume.json()["daemon"]["status"] == "running"
    assert timeline.status_code == 200
    assert run_once.status_code == 200
    assert run_once.json()["manual_full_sweep"] is True
    assert run_once.json()["daemon"]["source_cadence"]


def test_fed_speech_analyzer_never_outputs_btc_direction() -> None:
    analyses = analyze_fed_texts(
        [
            {
                "text_id": "fed-text-1",
                "text_hash": "fed-text-1",
                "source_name": "Federal Reserve RSS",
                "source_tier": "official",
                "published_at": "2026-05-28T08:00:00+00:00",
                "speaker": "Chair Powell",
                "title": "Policy remarks",
                "url": "https://www.federalreserve.gov/",
                "raw_text": (
                    "Inflation remains elevated and policy may need to stay "
                    "restrictive. Incoming data will be assessed carefully."
                ),
            }
        ],
        now=datetime(2026, 5, 28, 8, 0, tzinfo=UTC),
        use_deepseek=False,
    )
    analysis = analyses[0]
    audit = boundary_audit(analyses)

    assert analysis["tone"] == "hawkish"
    assert analysis["policy_relevance"] == "high"
    assert analysis["direct_btc_score_impact"] is False
    assert audit["boundary_passed"] is True


def test_event_window_state_priority_and_overlay_score_isolation() -> None:
    now = datetime(2026, 5, 28, 8, 0, tzinfo=UTC)
    active = {
        "event_id": "pce-case",
        "event_type": "PCE",
        "title": "Personal Income and Outlays",
        "release_time": "2026-05-28T18:00:00+00:00",
        "phase": "high_alert",
    }
    live_quality = {"overall_source_mode": "live", "data_quality_flags": []}
    shock_state = _state_from_inputs(
        now,
        active,
        [{"emergency_level": "critical", "shock_type": "official_policy_shock"}],
        True,
        "running",
        live_quality,
    )
    fallback_state = _state_from_inputs(
        now,
        active,
        [],
        True,
        "running",
        {"overall_source_mode": "fallback", "data_quality_flags": []},
    )
    overlay = _overlay_from_state(shock_state)

    assert shock_state["event_window_state"] == "unscheduled_shock_confirmed"
    assert shock_state["state_priority"] == 95
    assert fallback_state["event_window_state"] == "pre_event_high_alert"
    assert fallback_state["emergency_level"] == "watch"
    assert set(overlay) == {
        "trade_permission_modifier",
        "confidence_cap",
        "volatility_warning",
        "ordinary_radar_trust",
    }
    assert "module_score" not in overlay
    assert "btc_score" not in overlay


def test_event_window_partial_live_is_functional_and_not_blocking() -> None:
    active = {
        "event_id": "pce-case",
        "event_type": "PCE",
        "title": "Personal Income and Outlays",
        "expectation": {
            "consensus_status": "secondary_unconfirmed",
            "nowcast_payload": {"mom": {"pce": 0.4}},
        },
        "actual_snapshot": {"actual_status": "not_released"},
    }
    flags: list[str] = []
    source_quality = _source_quality_breakdown(
        active,
        [
            {
                "source_id": "fred-bls-release-calendar",
                "source_tier": "official_mirror",
                "status": "success",
            },
            {
                "source_id": "cleveland-fed-nowcast",
                "source_tier": "official_nowcast",
                "status": "success",
            },
            {
                "source_id": "fxstreet-calendar",
                "source_tier": "secondary_consensus",
                "status": "partial",
            },
        ],
        "partial",
        flags,
    )

    assert source_quality["overall_source_mode"] == "partial_live"
    assert source_quality["functional_live"] is True
    assert source_quality["blocked"] is False
    assert source_quality["blocked_reason"] is None
    assert "release_surprise_disabled" in source_quality["disabled_capabilities"]
    assert "actual_pending" in source_quality["disabled_capabilities"]
    assert "system-blocking" in source_quality["confidence_note"]


def test_event_window_actual_provider_uses_bls_official_success(monkeypatch) -> None:
    now = datetime(2026, 6, 10, 13, 0, tzinfo=UTC)
    event = {
        "event_id": "cpi-202606101230",
        "event_type": "CPI",
        "release_time": "2026-06-10T12:30:00+00:00",
        "release_time_utc": "2026-06-10T12:30:00+00:00",
    }

    def fake_get(url: str):
        payload = {
            "Results": {
                "series": [
                    {
                        "data": [
                            {"year": "2026", "period": "M05", "value": "317.2"},
                            {"year": "2026", "period": "M04", "value": "316.8"},
                        ]
                    }
                ]
            }
        }
        started = finished = now
        return httpx.Response(200, json=payload), started, finished, None

    monkeypatch.setattr(actuals, "_get", fake_get)

    snapshot = collect_actual_snapshot(event, now)["actual_snapshot"]

    assert snapshot["actual_status"] == "available"
    assert snapshot["metric_group"] == "CPI"
    assert snapshot["provider"] == "bls_api"
    assert snapshot["source_tier"] == "official"
    assert snapshot["latest_observation"] == 317.2
    assert snapshot["previous_observation"] == 316.8
    assert snapshot["observation_date"] == "2026-05"
    assert snapshot["release_ts"] == "2026-06-10T12:30:00+00:00"
    assert snapshot["fallback_used"] is False
    assert snapshot["source_lineage"][0]["provider"] == "bls_api"
    assert snapshot["source_lineage"][0]["confidence"] == 0.95


def test_event_window_actual_provider_records_bls_blocked_and_fred_fallback(monkeypatch) -> None:
    now = datetime(2026, 6, 5, 13, 0, tzinfo=UTC)
    event = {
        "event_id": "nfp-202606051230",
        "event_type": "NFP",
        "release_time": "2026-06-05T12:30:00+00:00",
        "release_time_utc": "2026-06-05T12:30:00+00:00",
    }

    def fake_get(url: str):
        started = finished = now
        if "api.bls.gov" in url:
            return httpx.Response(403, text="blocked"), started, finished, None
        return (
            httpx.Response(200, text="DATE,VALUE\n2026-04-01,160000\n2026-05-01,160250\n"),
            started,
            finished,
            None,
        )

    monkeypatch.setattr(actuals, "_get", fake_get)

    snapshot = collect_actual_snapshot(event, now)["actual_snapshot"]

    assert snapshot["actual_status"] == "available"
    assert snapshot["provider"] == "fred_fallback"
    assert snapshot["source_tier"] == "official_mirror"
    assert snapshot["latest_observation"] == 160250.0
    assert snapshot["fallback_used"] is True
    assert any(
        item["provider"] == "bls_api"
        and item["status"] == "failed"
        and item["error_code"] == "blocked_provider"
        and item["blocked_provider"] == "bls_api"
        for item in snapshot["source_lineage"]
    )
    assert any(
        item["provider"] == "fred_fallback"
        and item["source_tier"] == "official_mirror"
        and item["fallback_used"] is True
        for item in snapshot["source_lineage"]
    )


def test_event_window_actual_provider_keeps_stale_observation_not_released(monkeypatch) -> None:
    now = datetime(2026, 6, 10, 13, 0, tzinfo=UTC)
    event = {
        "event_id": "cpi-202606101230",
        "event_type": "CPI",
        "release_time": "2026-06-10T12:30:00+00:00",
        "release_time_utc": "2026-06-10T12:30:00+00:00",
    }

    def fake_get(url: str):
        started = finished = now
        if "api.bls.gov" in url:
            payload = {
                "Results": {
                    "series": [
                        {
                            "data": [
                                {"year": "2026", "period": "M04", "value": "316.8"},
                                {"year": "2026", "period": "M03", "value": "316.1"},
                            ]
                        }
                    ]
                }
            }
            return httpx.Response(200, json=payload), started, finished, None
        return (
            httpx.Response(200, text="DATE,VALUE\n2026-03-01,316.1\n2026-04-01,316.8\n"),
            started,
            finished,
            None,
        )

    monkeypatch.setattr(actuals, "_get", fake_get)

    snapshot = collect_actual_snapshot(event, now)["actual_snapshot"]

    assert snapshot["actual_status"] == "not_released"
    assert snapshot["latest_observation"] is None
    assert snapshot["observations"] == []
    assert {item["error_code"] for item in snapshot["source_lineage"]} == {"actual_not_released"}


def test_event_window_reaction_requires_available_actual_status_for_surprise() -> None:
    now = datetime(2026, 6, 10, 13, 0, tzinfo=UTC)
    reaction = build_post_event_reaction(
        {
            "event_id": "cpi-202606101230",
            "event_type": "CPI",
            "release_time": "2026-06-10T12:30:00+00:00",
            "release_time_utc": "2026-06-10T12:30:00+00:00",
            "expectation": {"consensus": 316.5},
            "actual_snapshot": {
                "actual_status": "not_released",
                "observations": [{"latest_observation": 317.2}],
            },
        },
        now,
    )

    assert reaction["actual_status"] == "not_released"
    assert reaction["actual"] is None
    assert reaction["surprise_raw"] is None
    assert "official_actual_pending" in reaction["data_quality_flags"]


def test_event_window_post_event_reaction_pending_before_release() -> None:
    now = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    reaction = build_post_event_reaction(
        {
            "event_id": "cpi-202606101230",
            "event_type": "CPI",
            "release_time": "2026-06-10T12:30:00+00:00",
            "release_time_utc": "2026-06-10T12:30:00+00:00",
        },
        now,
    )

    assert reaction["reaction_state"] == "pending"
    assert reaction["followthrough"] == "pending"
    assert reaction["event_lock_release_allowed"] is False
    assert reaction["realized_volatility"] is None
    assert reaction["event_lock_release_reason"] == "pre_release_reaction_pending"


def test_event_window_post_event_reaction_absorbed_with_context_metrics(tmp_path, monkeypatch) -> None:
    db = Database(tmp_path / "event-reaction-absorbed.sqlite3")
    db.init_schema()
    release = datetime(2026, 6, 10, 12, 30, tzinfo=UTC)
    _insert_reaction_metric_rows(
        db,
        release,
        prices=[100.0, 95.0, 99.0, 98.0],
        oi=[1000.0, 1100.0],
        funding=0.0002,
        basis=0.015,
        cvd=[1.0, 3.0],
        ofi=[10.0, 25.0],
    )
    monkeypatch.setattr(reactions, "database", db)

    reaction = build_post_event_reaction(
        _released_event(release),
        release + timedelta(hours=2, minutes=5),
    )

    assert reaction["actual"] == 317.2
    assert reaction["consensus"] == 316.5
    assert round(reaction["surprise_raw"], 4) == 0.7
    assert round(reaction["btc_return_5m"], 4) == -0.05
    assert round(reaction["btc_return_30m"], 4) == -0.01
    assert reaction["reaction_state"] == "absorbed"
    assert reaction["followthrough"] == "absorbed"
    assert reaction["btc_absorbed_shock"] is True
    assert reaction["event_lock_release_allowed"] is True
    assert reaction["realized_volatility"] is not None
    assert reaction["oi_change"] == 0.1
    assert reaction["funding_rate"] == 0.0002
    assert reaction["basis"] == 0.015
    assert reaction["cvd_proxy"] == 2.0
    assert reaction["ofi_proxy"] == 1.5


def test_event_window_post_event_reaction_followthrough_keeps_event_lock(tmp_path, monkeypatch) -> None:
    db = Database(tmp_path / "event-reaction-followthrough.sqlite3")
    db.init_schema()
    release = datetime(2026, 6, 10, 12, 30, tzinfo=UTC)
    _insert_reaction_metric_rows(
        db,
        release,
        prices=[100.0, 95.0, 90.0, 88.0],
        oi=[1000.0, 1300.0],
        funding=0.0005,
        basis=0.02,
        cvd=[2.0, -3.0],
        ofi=[20.0, -30.0],
    )
    monkeypatch.setattr(reactions, "database", db)

    reaction = build_post_event_reaction(
        _released_event(release),
        release + timedelta(hours=2, minutes=5),
    )

    assert round(reaction["btc_return_5m"], 4) == -0.05
    assert round(reaction["btc_return_30m"], 4) == -0.1
    assert reaction["reaction_state"] == "followthrough"
    assert reaction["followthrough"] == "followthrough"
    assert reaction["btc_absorbed_shock"] is False
    assert reaction["event_lock_release_allowed"] is False
    assert reaction["event_lock_release_reason"] == "policy_or_macro_shock_followthrough_keep_event_lock"


def test_event_window_bls_calendar_official_success_contract() -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    events = official_calendar._parse_bls_ics(  # noqa: SLF001
        "\n".join(
            [
                "BEGIN:VCALENDAR",
                "BEGIN:VEVENT",
                "SUMMARY:Consumer Price Index",
                "DTSTART:20260710T083000",
                "END:VEVENT",
                "END:VCALENDAR",
            ]
        ),
        now,
    )

    assert events
    event = events[0]
    assert event["event_type"] == "CPI"
    assert event["source_tier"] == "official"
    assert event["provider"] == "bls_release_calendar"
    assert event["original_authority"] == "BLS"
    assert event["calendar_confidence"] == 0.95
    assert event["fallback_used"] is False
    assert event["source_lineage"][0]["provider"] == "bls_release_calendar"


def test_event_window_bls_calendar_fred_mirror_fallback_contract() -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    payload = json.dumps({"release_dates": [{"date": "2026-07-10"}]})
    events = official_calendar._parse_fred_release_dates(  # noqa: SLF001
        payload,
        now,
        "CPI",
        "provider_failed_access_blocked",
    )

    assert events
    event = events[0]
    assert event["source_tier"] == "official_mirror"
    assert event["provider"] == "fred_bls_release_calendar"
    assert event["original_authority"] == "BLS"
    assert event["blocked_provider"] == "bls-release-calendar"
    assert event["blocked_reason"] == "provider_failed_access_blocked"
    assert event["fallback_used"] is True
    assert event["source_lineage"][0]["error_code"] == "provider_failed_access_blocked"
    assert event["source_lineage"][1]["provider"] == "fred_bls_release_calendar"


def test_event_window_bls_calendar_manual_override_has_versioned_source_note(monkeypatch) -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    def no_fred_events(now_arg, blocked_reason):
        return [], official_calendar.FetchResult(  # noqa: SLF001
            source_id="fred-bls-release-calendar",
            source_tier="official_mirror",
            endpoint_url=official_calendar.FRED_RELEASE_DATES_URL,
            started_at=now_arg,
            finished_at=now_arg,
            status="failed",
            error_code="provider_failed",
            error_message=blocked_reason,
            parsed_item_count=0,
            fallback_used=True,
        )

    monkeypatch.setattr(official_calendar, "_collect_fred_bls_release_dates", no_fred_events)

    events, fetch = official_calendar._collect_bls_calendar_fallback(  # noqa: SLF001
        now,
        official_calendar._disabled_bls_calendar_fetch(now),  # noqa: SLF001
    )

    assert fetch.source_id == "bls-calendar-manual-override"
    assert fetch.source_tier == "manual_override"
    assert fetch.status == "fallback_used"
    assert events
    event = events[0]
    assert event["source_tier"] == "manual_override"
    assert event["provider"] == "manual_override_yaml"
    assert event["override_version"] == official_calendar.BLS_MANUAL_OVERRIDE_VERSION
    assert event["updated_at"] == official_calendar.BLS_MANUAL_OVERRIDE_UPDATED_AT
    assert event["source_note"] == official_calendar.BLS_MANUAL_OVERRIDE_SOURCE_NOTE
    assert event["source_lineage"][1]["source_tier"] == "manual_override"


def test_event_window_bls_calendar_blocked_fetch_diagnostics() -> None:
    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    fetch = official_calendar._disabled_bls_calendar_fetch(now)  # noqa: SLF001
    payload = official_calendar._calendar_fetch_payload(  # noqa: SLF001
        fetch,
        blocked_provider="bls-release-calendar",
    )

    assert payload["status"] == "failed"
    assert payload["error_code"] == "provider_failed_access_blocked"
    assert payload["provider"] == "bls_release_calendar"
    assert payload["blocked_provider"] == "bls-release-calendar"
    assert payload["confidence"] == 0.0


def test_event_window_blocked_source_quality_is_not_functional_live() -> None:
    flags: list[str] = []
    source_quality = _source_quality_breakdown(None, [], "failed", flags)

    assert source_quality["overall_source_mode"] == "blocked"
    assert source_quality["functional_live"] is False
    assert source_quality["blocked"] is True
    assert source_quality["blocked_reason"] == "critical_event_time_unavailable"


def test_event_window_shock_fast_lane_levels_and_boundaries() -> None:
    now = datetime(2026, 5, 28, 8, 0, tzinfo=UTC)
    active = {
        "event_id": "pce-case",
        "event_type": "PCE",
        "title": "Personal Income and Outlays",
        "release_time": "2026-05-28T18:00:00+00:00",
        "phase": "event_lock",
    }
    quality = {"overall_source_mode": "live", "data_quality_flags": []}
    high_state = _state_from_inputs(
        now,
        active,
        [{"emergency_level": "high", "shock_type": "crypto_native"}],
        True,
        "running",
        quality,
    )
    high_overlay = _overlay_from_state(high_state)
    watch_state = _state_from_inputs(
        now,
        active,
        [{"emergency_level": "watch", "shock_type": "rumor"}],
        True,
        "running",
        quality,
    )
    watch_overlay = _overlay_from_state(watch_state)

    assert high_state["event_window_state"] == "unscheduled_shock_watch"
    assert high_overlay["trade_permission_modifier"] == "watch_only"
    assert high_overlay["ordinary_radar_trust"] == "low"
    assert watch_state["event_window_state"] == "unscheduled_shock_watch"
    assert watch_overlay["trade_permission_modifier"] == "reduce_size"
    assert watch_overlay["ordinary_radar_trust"] == "reduced"
    assert "btc_score" not in high_overlay


def test_official_shock_collector_requires_lineage_and_never_scores_btc() -> None:
    now = datetime(2026, 5, 28, 8, 0, tzinfo=UTC)
    shocks = collect_official_shocks(
        now,
        [
            {
                "text_id": "fed-emergency",
                "text_hash": "fed-emergency-hash",
                "source_name": "Federal Reserve RSS",
                "source_tier": "official",
                "published_at": now.isoformat(),
                "title": "Federal Reserve issues emergency policy statement",
                "url": "https://www.federalreserve.gov/newsevents/pressreleases/test.htm",
                "raw_text": "Emergency policy statement on market disruption.",
            }
        ],
    )
    shock = shocks[0]

    assert shock["emergency_level"] == "critical"
    assert shock["confirmation_level"] == "official"
    assert shock["raw_url"]
    assert shock["source_hash"] == "fed-emergency-hash"
    assert shock["source_lineage"][0]["source_tier"] == "official"
    assert shock["direct_score_impact"] is False
