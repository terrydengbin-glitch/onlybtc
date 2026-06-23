from pathlib import Path

from sqlalchemy import select

from onlybtc.algorithms.p3 import detect_event_windows
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p4.analyst_executor import run_analyst_agents
from onlybtc.p4.cross_exam import run_cross_examination
from onlybtc.p4.cross_exam_revision import run_cross_exam_revisions
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.p4.judge import run_judge_synthesis
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_judge_synthesis_persists_and_preserves_state_constraints(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-judge-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-judge-pack-test",
        db=db,
    )
    analyst_result = run_analyst_agents(
        pack_id=pack["pack_id"],
        debate_id="debate-judge-test",
        runtime_mode="mock",
        db=db,
    )
    cross_result = run_cross_examination(
        debate_id=analyst_result["debate_id"],
        pack_id=pack["pack_id"],
        db=db,
    )
    revision_result = run_cross_exam_revisions(debate_id=analyst_result["debate_id"], db=db)

    result = run_judge_synthesis(
        debate_id=analyst_result["debate_id"],
        pack_id=pack["pack_id"],
        db=db,
    )
    synthesis = result["judge_synthesis"]

    assert result["status"] == "completed"
    assert synthesis["schema_version"] == "p4.judge_synthesis.v1"
    assert synthesis["debate_id"] == "debate-judge-test"
    assert synthesis["pack_id"] == pack["pack_id"]
    assert synthesis["controller_run_id"] == p3_events["run_id"]
    assert synthesis["trend_state"] == cross_result["state_machine"]["trend_state"]
    assert synthesis["risk_state"] == cross_result["state_machine"]["risk_state"]
    assert synthesis["blocked_by"] == cross_result["state_machine"]["blocked_by"]
    assert synthesis["confidence_discount"] > 0
    assert 0 <= synthesis["confidence"] <= 1
    assert synthesis["accepted_claims"]
    assert synthesis["minority_objections"]
    assert revision_result["revision_count"] > 0
    assert synthesis["evidence_ids"]
    assert "event_window_publish_constraint" not in synthesis["blocked_by"]
    assert "missing_primary_signal_evidence" not in synthesis["blocked_by"]
    with db.session() as session:
        row = session.scalar(
            select(schema.JudgeSynthesis).where(
                schema.JudgeSynthesis.debate_id == "debate-judge-test"
            )
        )
        debate = session.scalar(
            select(schema.LlmDebate).where(schema.LlmDebate.debate_id == "debate-judge-test")
        )

    assert row is not None
    assert row.final_state == synthesis["trend_state"]
    assert row.payload["judge_synthesis_id"] == synthesis["judge_synthesis_id"]
    assert row.payload["revision_summary"]["revision_count"] == revision_result["revision_count"]
    assert debate is not None
    assert debate.final_state == synthesis["trend_state"]
    assert debate.consensus_score == synthesis["confidence"]
