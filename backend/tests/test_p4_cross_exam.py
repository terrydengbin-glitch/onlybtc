from pathlib import Path

from sqlalchemy import select

from onlybtc.algorithms.p3 import detect_event_windows
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p4.analyst_executor import run_analyst_agents
from onlybtc.p4.cross_exam import run_cross_examination
from onlybtc.p4.cross_exam_revision import run_cross_exam_revisions
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_cross_exam_generates_challenges_and_persists_round(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-cross-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-cross-pack-test",
        db=db,
    )
    analyst_result = run_analyst_agents(
        pack_id=pack["pack_id"],
        debate_id="debate-cross-test",
        runtime_mode="mock",
        db=db,
    )

    result = run_cross_examination(
        debate_id=analyst_result["debate_id"],
        pack_id=pack["pack_id"],
        db=db,
    )

    assert result["status"] == "completed"
    assert result["debate_id"] == "debate-cross-test"
    assert result["pack_id"] == pack["pack_id"]
    assert result["challenge_count"] > 0
    assert result["state_machine"]["critical_publish_allowed"] is False
    assert any(
        challenge["challenge_type"] in {"ignored_invalidation", "missing_evidence", "data_quality"}
        for challenge in result["challenges"]
    )
    assert all(challenge["evidence_ids"] for challenge in result["challenges"])
    with db.session() as session:
        challenges = session.scalars(
            select(schema.LlmChallenge).where(
                schema.LlmChallenge.debate_id == "debate-cross-test"
            )
        ).all()
        round_row = session.scalar(
            select(schema.LlmRound).where(
                schema.LlmRound.debate_id == "debate-cross-test",
                schema.LlmRound.round_type == "cross_examination",
            )
        )

    assert len(challenges) == result["challenge_count"]
    assert round_row is not None
    assert round_row.round_number == 2
    assert any(challenge.severity in {"medium", "high"} for challenge in challenges)

    revision_result = run_cross_exam_revisions(debate_id="debate-cross-test", db=db)
    assert revision_result["status"] == "completed"
    assert revision_result["revision_count"] == result["challenge_count"]
    assert revision_result["revision_integrity"] == "passed"
    with db.session() as session:
        revisions = session.scalars(
            select(schema.LlmRevision).where(
                schema.LlmRevision.debate_id == "debate-cross-test"
            )
        ).all()
        revision_round = session.scalar(
            select(schema.LlmRound).where(
                schema.LlmRound.debate_id == "debate-cross-test",
                schema.LlmRound.round_type == "cross_exam_revision",
            )
        )
    assert len(revisions) == revision_result["revision_count"]
    assert revision_round is not None
