from __future__ import annotations

from datetime import UTC, datetime

from onlybtc.api.event_window import _normalize_shock_fast_lane
from onlybtc.db.repositories import EventWatchtowerRepository
from onlybtc.db.session import Database
from onlybtc.event_window.connectors.shock_lane import collect_market_shocks
from onlybtc.event_window.speech_analyzer import analyze_fed_texts, boundary_audit
from onlybtc.event_window.watchtower import _overlay_from_state, _state_from_inputs


def _minimal_payload(snapshot_id: str = "evt-offline-001") -> dict:
    return {
        "schema_version": "p45.event_window.v3",
        "snapshot_id": snapshot_id,
        "asof_ts": "2026-05-28T08:00:00+00:00",
        "module_name": "event_window_policy_shock_watchtower",
        "direct_score_impact": False,
        "daemon": {"status": "running"},
        "state": {
            "event_window_state": "pre_event_high_alert",
            "state_priority": 70,
            "emergency_level": "high",
            "reason_codes": ["offline_test"],
        },
        "overlay": {
            "trade_permission_modifier": "watch_only",
            "confidence_cap": 55,
            "volatility_warning": True,
            "ordinary_radar_trust": "low",
        },
        "active_event": {
            "event_id": "evt-pce-offline",
            "event_type": "PCE",
            "title": "Personal Income and Outlays",
        },
        "calendar_items": [],
        "expectation_snapshots": [],
        "official_text_items": [],
        "llm_analyses": [],
        "market_probes": [],
        "shock_lane_items": [],
        "post_event_reactions": [],
        "alerts": [],
        "source_fetches": [],
    }


def test_snapshot_by_id_roundtrip_is_not_latest_dependent(tmp_path) -> None:
    db = Database(tmp_path / "event-watchtower-offline.sqlite3")
    db.init_schema()
    first = _minimal_payload("evt-offline-first")
    second = _minimal_payload("evt-offline-second")
    second["state"]["event_window_state"] = "event_neutral"

    with db.session() as session:
        repo = EventWatchtowerRepository(session)
        repo.save_snapshot(first)
        repo.save_snapshot(second)

    with db.session() as session:
        repo = EventWatchtowerRepository(session)
        exact = repo.snapshot_by_id("evt-offline-first")
        latest = repo.latest_snapshot()

    assert exact is not None
    assert exact["snapshot_id"] == "evt-offline-first"
    assert (exact["state"] or {})["event_window_state"] == "pre_event_high_alert"
    assert latest is not None
    assert latest["snapshot_id"] == "evt-offline-second"


def test_shock_lane_latest_normalizer_returns_stable_aggregate_contract() -> None:
    raw = {
        "shock_id": "shock-btc-4h-202605280800",
        "detected_at": "2026-05-28T08:00:00+00:00",
        "shock_type": "crypto_native",
        "emergency_level": "high",
        "confirmation_level": "market_dislocation",
        "source_count": 1,
        "market_dislocation": True,
        "btc_microstructure_confirmation": True,
        "rumor_risk": False,
        "raw_title": "BTC 4h market dislocation",
        "reason_codes": ["btc_4h_market_dislocation"],
        "evidence": {"primary_window": "4h", "primary_return": -0.05},
    }
    normalized = _normalize_shock_fast_lane(raw, latest_item_from_sqlite=True)

    assert normalized["shock_detected"] is True
    assert normalized["shock_type"] == "crypto_native"
    assert normalized["summary"] == "BTC 4h market dislocation"
    assert normalized["latest_item_from_sqlite"] is True
    assert normalized["latest_item"]["shock_id"] == raw["shock_id"]
    assert normalized["evidence"]["primary_window"] == "4h"


def test_state_machine_overlay_and_llm_boundary_are_offline_deterministic() -> None:
    now = datetime(2026, 5, 28, 8, 0, tzinfo=UTC)
    active = {
        "event_id": "pce-case",
        "event_type": "PCE",
        "title": "Personal Income and Outlays",
        "release_time": "2026-05-28T18:00:00+00:00",
        "phase": "high_alert",
    }
    state = _state_from_inputs(
        now,
        active,
        [{"emergency_level": "critical", "shock_type": "official_policy_shock"}],
        True,
        "running",
        {"overall_source_mode": "live", "data_quality_flags": []},
    )
    overlay = _overlay_from_state(state)
    analyses = analyze_fed_texts(
        [
            {
                "text_id": "fed-offline-1",
                "text_hash": "fed-offline-1",
                "source_name": "Federal Reserve RSS",
                "source_tier": "official",
                "published_at": now.isoformat(),
                "speaker": "Chair Powell",
                "title": "Policy remarks",
                "url": "https://www.federalreserve.gov/",
                "raw_text": "Inflation remains elevated; policy remains data dependent.",
            }
        ],
        now=now,
        use_deepseek=False,
    )

    assert state["event_window_state"] == "unscheduled_shock_confirmed"
    assert overlay["trade_permission_modifier"] == "event_lock"
    assert "btc_score" not in overlay
    assert all(item["direct_btc_score_impact"] is False for item in analyses)
    assert boundary_audit(analyses)["boundary_passed"] is True


def test_market_shock_detection_uses_fake_probe_without_network() -> None:
    now = datetime(2026, 5, 28, 8, 0, tzinfo=UTC)
    shocks = collect_market_shocks(
        now,
        market_probe={
            "market_probe_id": "probe-offline-001",
            "source": "offline_fixture",
            "returns": {"5m": -0.012, "15m": -0.021, "1h": -0.035, "4h": -0.052, "24h": -0.04},
            "return_zscores": {"5m": 1.2, "15m": 2.1, "1h": 2.4, "4h": 3.1, "24h": 1.5},
            "data_quality_flags": [],
        },
    )

    assert shocks
    shock = shocks[0]
    assert shock["market_dislocation"] is True
    assert shock["emergency_level"] in {"high", "critical"}
    assert shock["direct_score_impact"] is False
    assert shock["evidence"]["primary_window"] in {"15m", "1h", "4h"}
