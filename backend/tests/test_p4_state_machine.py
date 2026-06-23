from pathlib import Path

from onlybtc.algorithms.p3 import detect_event_windows
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.p4.rule_baseline import build_rule_baseline
from onlybtc.p4.state_machine import run_state_machine
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_state_machine_does_not_hard_block_provider_required_or_monitor(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-state-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-state-pack-test",
        db=db,
    )
    baseline = build_rule_baseline(pack_id=pack["pack_id"], db=db)

    state = run_state_machine(pack_id=pack["pack_id"], baseline=baseline, db=db)

    assert state["status"] == "completed"
    assert state["schema_version"] == "p4.state_machine.v1"
    assert state["pack_id"] == pack["pack_id"]
    assert state["controller_run_id"] == p3_events["run_id"]
    assert state["trend_state"] in {
        "insufficient_confidence",
        "bullish_candidate",
        "bearish_candidate",
        "mixed_watch",
        "neutral_watch",
    }
    assert state["risk_state"] in {"normal", "watch", "event_watch", "warning"}
    assert state["analysis_output_allowed"] is True
    assert state["publish_allowed"] == state["critical_publish_allowed"]
    assert "event_window_publish_constraint" not in state["blocked_by"]
    assert "missing_primary_signal_evidence" not in state["blocked_by"]
    assert state["state_machine_constraints_applied"]
    assert state["evidence_ids"]
    assert "provider_required" not in ", ".join(state["blocked_by"])


async def test_state_machine_blocks_critical_on_run_mode_integrity_invalidation(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-state-block-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-state-block-pack-test",
        db=db,
    )
    with db.session() as session:
        session.add(
            schema.InvalidationEvent(
                condition_id="run_mode_integrity_invalidation",
                run_id=p3_events["run_id"],
                status="triggered",
                action="block_critical_publish",
                payload={"publish_impact": "block_critical_publish"},
            )
        )

    state = run_state_machine(pack_id=pack["pack_id"], db=db)

    assert state["critical_publish_allowed"] is False
    assert "run_mode_integrity_invalidation" in state["blocked_by"]
    assert any(
        constraint["constraint"] == "run_mode_or_p3_block_critical"
        for constraint in state["state_machine_constraints_applied"]
    )
