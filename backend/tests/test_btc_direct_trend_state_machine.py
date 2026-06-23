from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.direct_trend.evidence import BTC_DIRECT_TREND_EVIDENCE_MODULE_ID
from onlybtc.direct_trend.state_machine import (
    BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID,
    build_direct_trend_state_machine,
)


def test_state_machine_keeps_strong_4h_with_weak_acceptance_as_watch(tmp_path) -> None:
    db = Database(tmp_path / "direct-trend-state-watch.sqlite3")
    db.init_schema()
    with db.session() as session:
        _add_evidence(session, "p1-state-watch", "btc_direct_trend.price_structure.btc_return_4h", 0.9, "price_structure")
        _add_evidence(
            session,
            "p1-state-watch",
            "btc_direct_trend.derivatives_positioning.price_oi_interaction_state",
            0.8,
            "derivatives_positioning",
            semantic_state="aggressive_long_building",
        )
        _add_evidence(
            session,
            "p1-state-watch",
            "btc_direct_trend.orderflow_acceptance.cvd_slope_z",
            0.0,
            "orderflow_acceptance",
        )
        _add_evidence(
            session,
            "p1-state-watch",
            "btc_direct_trend.event_overlay_context.event_trust_cap",
            1.0,
            "event_overlay_context",
        )

    payload = build_direct_trend_state_machine(evidence_run_id="p1-state-watch", db=db)

    h4 = payload["horizons"]["4h"]
    assert h4["direction_score"] >= 60
    assert h4["acceptance_score"] < 45
    assert h4["state"] == "impulse_watch"


def test_state_machine_event_cap_preserves_direction_but_caps_trust(tmp_path) -> None:
    db = Database(tmp_path / "direct-trend-state-event.sqlite3")
    db.init_schema()
    with db.session() as session:
        for feature_id, score, category in (
            ("btc_direct_trend.price_structure.btc_return_4h", 0.9, "price_structure"),
            (
                "btc_direct_trend.derivatives_positioning.price_oi_interaction_state",
                0.8,
                "derivatives_positioning",
            ),
            ("btc_direct_trend.orderflow_acceptance.cvd_slope_z", 0.8, "orderflow_acceptance"),
            ("btc_direct_trend.orderflow_acceptance.taker_delta_quote", 0.7, "orderflow_acceptance"),
        ):
            _add_evidence(session, "p1-state-event", feature_id, score, category)
        _add_evidence(
            session,
            "p1-state-event",
            "btc_direct_trend.event_overlay_context.event_trust_cap",
            0.45,
            "event_overlay_context",
        )
        _add_evidence(
            session,
            "p1-state-event",
            "btc_direct_trend.event_overlay_context.post_event_reaction_state",
            0.0,
            "event_overlay_context",
            semantic_state="neutral_reaction",
        )

    payload = build_direct_trend_state_machine(evidence_run_id="p1-state-event", db=db)

    h4 = payload["horizons"]["4h"]
    assert h4["direction_score"] >= 60
    assert h4["trust_score"] < 65
    assert h4["state"] == "event_distorted"


def test_state_machine_stale_trigger_blocks_confirmed_acceptance(tmp_path) -> None:
    db = Database(tmp_path / "direct-trend-state-stale.sqlite3")
    db.init_schema()
    with db.session() as session:
        _add_evidence(
            session,
            "p1-state-stale",
            "btc_direct_trend.price_structure.btc_return_4h",
            0.9,
            "price_structure",
            freshness_state="stale",
        )
        _add_evidence(
            session,
            "p1-state-stale",
            "btc_direct_trend.derivatives_positioning.price_oi_interaction_state",
            0.8,
            "derivatives_positioning",
        )
        _add_evidence(
            session,
            "p1-state-stale",
            "btc_direct_trend.orderflow_acceptance.cvd_slope_z",
            0.8,
            "orderflow_acceptance",
        )

    payload = build_direct_trend_state_machine(evidence_run_id="p1-state-stale", db=db)

    h4 = payload["horizons"]["4h"]
    assert h4["state"] != "fast_trend_acceptance"
    assert payload["source_fresh"] is False
    assert "btc_direct_trend.price_structure.btc_return_4h" in payload["blocked_evidence"]


def test_state_machine_outputs_btc_resilient_semantic_for_1d(tmp_path) -> None:
    db = Database(tmp_path / "direct-trend-state-resilient.sqlite3")
    db.init_schema()
    with db.session() as session:
        _add_evidence(session, "p1-state-resilient", "btc_direct_trend.price_structure.btc_return_24h", 0.6, "price_structure")
        _add_evidence(
            session,
            "p1-state-resilient",
            "btc_direct_trend.btc_residual_cross_asset.residual_semantic",
            0.8,
            "btc_residual_cross_asset",
            semantic_state="external_pressure_down_but_btc_resilient",
        )

    payload = build_direct_trend_state_machine(evidence_run_id="p1-state-resilient", db=db)

    h1d = payload["horizons"]["1d"]
    assert "btc_resilient" in h1d["semantic_flags"]
    assert h1d["state"] == "pullback_in_uptrend"


def test_state_machine_persists_module_json_output(tmp_path) -> None:
    db = Database(tmp_path / "direct-trend-state-persist.sqlite3")
    db.init_schema()
    with db.session() as session:
        _add_evidence(session, "p1-state-persist", "btc_direct_trend.price_structure.btc_return_4h", 0.2, "price_structure")

    payload = build_direct_trend_state_machine(
        evidence_run_id="p1-state-persist",
        state_run_id="p3-state-test",
        db=db,
    )

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "p3-state-test",
                schema.ModuleJsonOutput.module_id == BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID,
            )
        )
    assert row is not None
    assert row.payload["schema_version"] == payload["schema_version"]


def _add_evidence(
    session,
    run_id: str,
    feature_id: str,
    score: float,
    category: str,
    freshness_state: str = "fresh",
    semantic_state: str | None = None,
) -> None:
    now = datetime.now(UTC)
    session.add(
        schema.FeatureValue(
            run_id=run_id,
            module_id=BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
            feature_id=feature_id,
            value=score,
            metadata_json={
                "feature_score": score,
                "category": category,
                "freshness_state": freshness_state,
                "source_asof_ts": now.isoformat(),
                "valid_until": (now + timedelta(minutes=30)).isoformat(),
                "semantic_state": semantic_state,
            },
        )
    )
