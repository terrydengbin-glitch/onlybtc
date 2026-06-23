from pathlib import Path

from sqlalchemy import select

from onlybtc.algorithms.p3 import detect_event_windows
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p4.analyst_executor import run_analyst_agents
from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_run_analyst_agents_writes_debate_votes_and_round(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-agent-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-agent-pack-test",
        db=db,
    )

    result = run_analyst_agents(
        pack_id=pack["pack_id"],
        debate_id="debate-agent-test",
        runtime_mode="mock",
        db=db,
    )

    assert result["status"] == "completed"
    assert result["analyst_count"] == len(ANALYST_MODULES)
    assert result["succeeded_count"] == len(ANALYST_MODULES)
    assert result["votes_written_count"] == len(ANALYST_MODULES)
    assert {item["analyst_id"] for item in result["analyst_inputs"]} == set(ANALYST_MODULES)
    assert all(item["evidence_count"] > 0 for item in result["analyst_inputs"])
    with db.session() as session:
        debate = session.scalar(
            select(schema.LlmDebate).where(schema.LlmDebate.debate_id == "debate-agent-test")
        )
        round_row = session.scalar(
            select(schema.LlmRound).where(schema.LlmRound.debate_id == "debate-agent-test")
        )
        votes = session.scalars(
            select(schema.LlmModelVote).where(
                schema.LlmModelVote.debate_id == "debate-agent-test"
            )
        ).all()

    assert debate is not None
    assert debate.run_id == p3_events["run_id"]
    assert debate.final_state == "analyst_independent_review"
    assert round_row is not None
    assert round_row.round_type == "analyst_independent_review"
    assert len(votes) == len(ANALYST_MODULES)
    assert {vote.model_name for vote in votes} == set(ANALYST_MODULES)
    assert all(vote.evidence_ids for vote in votes)
