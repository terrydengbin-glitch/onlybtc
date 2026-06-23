from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from onlybtc.algorithms.p3 import detect_event_windows
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p4.evidence_pack import ANALYST_MODULES, build_p4_evidence_pack
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_p4_evidence_pack_freezes_radar_events_and_analyst_history(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-pack-test", run_mode="mock", db=db)
    now = datetime.now(UTC)
    with db.session() as session:
        session.add(
            schema.LlmDebate(
                debate_id="debate-history",
                run_id="previous-p4-run",
                consensus_score=0.62,
                disagreement_level="medium",
                final_state="event_compression",
                publish_allowed=False,
            )
        )
        session.add(
            schema.LlmModelVote(
                debate_id="debate-history",
                model_name="macro_event_analyst",
                vote="event_compression",
                confidence=0.66,
                evidence_ids=["old-ev-1"],
                changed=True,
                created_at=now,
                updated_at=now,
            )
        )

    result = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-pack-test",
        db=db,
    )

    assert result["status"] == "completed"
    assert result["radar_modules_consumed_count"] == len(RADAR_MODULES)
    assert result["signed_event_metrics_consumed_count"] == 4
    assert result["analyst_history_evidence_count"] == len(ANALYST_MODULES)
    with db.session() as session:
        pack = session.scalar(
            select(schema.EvidencePack).where(schema.EvidencePack.pack_id == "p4-pack-test")
        )
        items = session.scalars(
            select(schema.EvidenceItem).where(schema.EvidenceItem.pack_id == "p4-pack-test")
        ).all()
        links = session.scalars(select(schema.EvidenceMetricLink)).all()

    assert pack is not None
    assert len(items) == result["evidence_item_count"]
    assert links
    source_layers = {item.data["source_layer"] for item in items}
    assert {"p2_radar", "p3_event", "analyst_history"}.issubset(source_layers)
    macro_history = next(
        item
        for item in items
        if item.data["source_layer"] == "analyst_history"
        and item.data["assigned_analyst"] == "macro_event_analyst"
    )
    assert macro_history.data["history_available"] is True
    assert macro_history.data["history"][0]["vote"] == "event_compression"
