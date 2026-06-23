import json
from pathlib import Path

from sqlalchemy import select

from onlybtc.algorithms.p3 import detect_event_windows
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p4.adversarial_review import run_adversarial_review
from onlybtc.p4.analyst_executor import run_analyst_agents
from onlybtc.p4.cross_exam import run_cross_examination
from onlybtc.p4.cross_exam_revision import run_cross_exam_revisions
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.p4.final_controller import build_final_controller_json
from onlybtc.p4.judge import run_judge_synthesis
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_final_controller_writes_dashboard_snapshot_and_payload(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-final-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-final-pack-test",
        db=db,
    )
    analyst = run_analyst_agents(
        pack_id=pack["pack_id"],
        debate_id="debate-final-test",
        runtime_mode="mock",
        db=db,
    )
    run_cross_examination(
        debate_id=analyst["debate_id"],
        pack_id=pack["pack_id"],
        db=db,
    )
    run_cross_exam_revisions(debate_id=analyst["debate_id"], db=db)
    judge = run_judge_synthesis(
        debate_id=analyst["debate_id"],
        pack_id=pack["pack_id"],
        db=db,
    )
    review = run_adversarial_review(debate_id=analyst["debate_id"], db=db)

    result = build_final_controller_json(debate_id=analyst["debate_id"], db=db)
    final_json = result["final_controller_json"]

    assert result["status"] == "completed"
    assert result["snapshot_id"].startswith("snapshot-")
    assert result["snapshot_module_count"] == radar["analyzed"]
    assert final_json["schema_version"] == "p4.final_controller.v1"
    assert final_json["evidence_pack_id"] == pack["pack_id"]
    assert final_json["debate_id"] == analyst["debate_id"]
    assert final_json["judge_synthesis_id"] == judge["judge_synthesis"]["judge_synthesis_id"]
    assert (
        final_json["adversarial_review_id"]
        == review["adversarial_review"]["review_id"]
    )
    assert final_json["analyst_vote_ids"]
    assert final_json["challenge_ids"]
    assert final_json["revision_ids"]
    assert final_json["revision_integrity"] in {"passed", "partial", "failed"}
    assert final_json["publish_scope"] in {
        "publish_candidate",
        "watch_only",
        "dashboard_only",
        "blocked",
    }
    assert final_json["dominant_drivers"]
    assert final_json["observation_points"]
    assert final_json["blocked_by"] == judge["judge_synthesis"]["blocked_by"]
    if final_json["blocked_by"]:
        assert final_json["publish_allowed"] is False
        assert final_json["publish_scope"] in {"watch_only", "dashboard_only", "blocked"}
        assert final_json["watch_only"] is True
    else:
        assert "missing_primary_signal_evidence" not in final_json["publish_constraints"]
        assert "event_window_publish_constraint" not in final_json["publish_constraints"]
        assert final_json["publish_scope"] in {"publish_candidate", "watch_only", "blocked"}
    assert "leverage" not in json.dumps(final_json).lower()
    with db.session() as session:
        snapshot = session.scalar(
            select(schema.DashboardSnapshot).where(
                schema.DashboardSnapshot.snapshot_id == result["snapshot_id"]
            )
        )
        modules = session.scalars(
            select(schema.SnapshotModule).where(
                schema.SnapshotModule.snapshot_id == result["snapshot_id"]
            )
        ).all()
        judge_row = session.scalar(
            select(schema.JudgeSynthesis).where(
                schema.JudgeSynthesis.debate_id == analyst["debate_id"]
            )
        )

    assert snapshot is not None
    assert snapshot.payload["schema_version"] == "p4.final_controller.v1"
    assert snapshot.payload["publish_constraints"] == final_json["publish_constraints"]
    assert len(modules) == radar["analyzed"]
    assert judge_row is not None
    assert judge_row.payload["dashboard_snapshot_id"] == result["snapshot_id"]
    assert (
        judge_row.payload["final_controller_json"]["schema_version"]
        == "p4.final_controller.v1"
    )
