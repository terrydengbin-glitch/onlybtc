from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.direct_trend.replay import (
    list_timescale_judge_replays,
    replay_timescale_judge,
    save_timescale_judge_snapshot,
)


def test_timescale_replay_persists_v22_snapshot_and_replays_by_keys(tmp_path) -> None:
    db = Database(tmp_path / "timescale-replay.sqlite3")
    db.init_schema()
    first = _payload("snap-first", "2026-06-22T10:00:00+00:00", h4_score=25.0)
    second = _payload("snap-second", "2026-06-22T11:00:00+00:00", h4_score=-40.0)

    saved_first = save_timescale_judge_snapshot("final-first", first, db=db)
    saved_second = save_timescale_judge_snapshot("final-second", second, db=db)

    assert saved_first["snapshot_id"] == "snap-first"
    assert saved_first["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert saved_first["source_window"]["max_source_lag_sec"] == 300.0
    with db.session() as session:
        rows = session.scalars(select(schema.TimescaleJudgeSnapshot)).all()
    assert len(rows) == 2

    by_snapshot = replay_timescale_judge(snapshot_id="snap-first", db=db)
    by_run = replay_timescale_judge(run_id="final-second", db=db)
    by_asof = replay_timescale_judge(asof_ts="2026-06-22T10:30:00+00:00", db=db)
    latest = replay_timescale_judge(latest=True, db=db)

    assert by_snapshot["payload"]["horizons"]["4h"]["direction_score"] == 25.0
    assert by_run["payload"]["horizons"]["4h"]["direction_score"] == -40.0
    assert by_asof["snapshot_id"] == "snap-first"
    assert latest["snapshot_id"] == saved_second["snapshot_id"]


def test_timescale_replay_preserves_stale_and_fallback_flags(tmp_path) -> None:
    db = Database(tmp_path / "timescale-replay-stale.sqlite3")
    db.init_schema()
    payload = _payload(
        "snap-stale",
        "2026-06-22T12:00:00+00:00",
        h4_score=12.0,
        source_fresh=False,
        fallback_used=True,
        fallback_reason="stale_acceptance_gate",
    )

    saved = save_timescale_judge_snapshot("final-stale", payload, db=db)

    assert saved["fallback_used"] is True
    assert saved["fallback_reason"] == "stale_acceptance_gate"
    assert saved["payload"]["source_fresh"] is False
    replay = replay_timescale_judge(run_id="final-stale", db=db)
    assert replay["payload"]["horizons"]["4h"]["source_fresh"] is False
    assert replay["freshness_summary"]["stale_evidence"] == ["cvd_slope_z"]


def test_timescale_replay_lists_recent_in_asof_order(tmp_path) -> None:
    db = Database(tmp_path / "timescale-replay-list.sqlite3")
    db.init_schema()
    base = datetime(2026, 6, 22, 10, tzinfo=UTC)
    for index in range(3):
        save_timescale_judge_snapshot(
            f"final-{index}",
            _payload(
                f"snap-{index}",
                (base + timedelta(hours=index)).isoformat(),
                h4_score=float(index),
            ),
            db=db,
        )

    rows = list_timescale_judge_replays(limit=2, db=db)

    assert [row["snapshot_id"] for row in rows] == ["snap-2", "snap-1"]


def test_timescale_replay_keeps_multiple_runs_for_same_snapshot_id(tmp_path) -> None:
    db = Database(tmp_path / "timescale-replay-duplicate-snapshot.sqlite3")
    db.init_schema()
    payload_a = _payload("shared-state-snapshot", "2026-06-22T10:00:00+00:00", h4_score=10.0)
    payload_b = _payload("shared-state-snapshot", "2026-06-22T10:05:00+00:00", h4_score=20.0)

    save_timescale_judge_snapshot("final-a", payload_a, db=db)
    save_timescale_judge_snapshot("final-b", payload_b, db=db)

    replay_a = replay_timescale_judge(run_id="final-a", db=db)
    replay_b = replay_timescale_judge(run_id="final-b", db=db)
    replay_latest_snapshot = replay_timescale_judge(snapshot_id="shared-state-snapshot", db=db)

    assert replay_a["payload"]["horizons"]["4h"]["direction_score"] == 10.0
    assert replay_b["payload"]["horizons"]["4h"]["direction_score"] == 20.0
    assert replay_latest_snapshot["run_id"] == "final-b"


def _payload(
    snapshot_id: str,
    asof_ts: str,
    h4_score: float,
    source_fresh: bool = True,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
) -> dict:
    return {
        "schema_version": "p45.btc_timescale_judge.v2.2",
        "snapshot_id": snapshot_id,
        "asof_ts": asof_ts,
        "source_fresh": source_fresh,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "freshness_summary": {
            "missing_evidence": [],
            "stale_evidence": ["cvd_slope_z"] if not source_fresh else [],
            "blocked_evidence": [],
        },
        "horizons": {
            "4h": {
                "state": "range_chop",
                "direction_score": h4_score,
                "acceptance_score": 20.0,
                "trust_score": 80.0,
                "display_score": h4_score * 0.8,
                "runtime_fresh": True,
                "source_fresh": source_fresh,
                "freshness_summary": {
                    "missing_evidence": [],
                    "stale_evidence": ["cvd_slope_z"] if not source_fresh else [],
                    "blocked_evidence": [],
                },
                "source_window": {
                    "min_source_asof_ts": "2026-06-22T09:55:00+00:00",
                    "max_source_asof_ts": "2026-06-22T10:00:00+00:00",
                    "max_source_lag_sec": 300.0,
                },
                "direct_evidence": {
                    "orderflow_acceptance": {
                        "cvd_slope_z": {
                            "source_asof_ts": "2026-06-22T10:00:00+00:00",
                            "freshness_state": "stale" if not source_fresh else "fresh",
                            "normalizer_version": "robust_z_tanh",
                        }
                    }
                },
            },
            "1d": {
                "state": "trend_building",
                "direction_score": h4_score / 2,
                "acceptance_score": 10.0,
                "trust_score": 75.0,
                "display_score": h4_score * 0.375,
                "runtime_fresh": True,
                "source_fresh": source_fresh,
                "freshness_summary": {},
                "source_window": {
                    "min_source_asof_ts": "2026-06-22T09:55:00+00:00",
                    "max_source_asof_ts": "2026-06-22T10:00:00+00:00",
                    "max_source_lag_sec": 300.0,
                },
            },
        },
    }
