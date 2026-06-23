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
from onlybtc.p4.judge import run_judge_synthesis
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_adversarial_review_passes_full_mock_chain(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-review-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-review-pack-test",
        db=db,
    )
    analyst = run_analyst_agents(
        pack_id=pack["pack_id"],
        debate_id="debate-review-test",
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

    result = run_adversarial_review(debate_id=analyst["debate_id"], db=db)
    review = result["adversarial_review"]

    assert result["status"] == "completed"
    assert review["schema_version"] == "p4.adversarial_review.v1"
    assert review["judge_synthesis_id"] == judge["judge_synthesis"]["judge_synthesis_id"]
    assert review["passed"] is True
    assert review["publish_allowed"] == judge["judge_synthesis"]["publish_allowed"]
    assert review["evidence_ids"]
    assert not review["required_fixes"]
    with db.session() as session:
        row = session.scalar(
            select(schema.AdversarialReview).where(
                schema.AdversarialReview.debate_id == "debate-review-test"
            )
        )
        debate = session.scalar(
            select(schema.LlmDebate).where(schema.LlmDebate.debate_id == "debate-review-test")
        )

    assert row is not None
    assert row.review_passed is True
    assert row.issues["review_id"] == review["review_id"]
    assert debate is not None
    assert debate.publish_allowed == review["publish_allowed"]


def test_adversarial_review_blocks_bad_judge_payload(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.LlmDebate(
                debate_id="debate-review-bad",
                run_id="p4-bad-run",
                consensus_score=0.8,
                disagreement_level="low",
                final_state="risk_on",
                publish_allowed=True,
            )
        )
        session.add(
            schema.LlmModelVote(
                debate_id="debate-review-bad",
                model_name="macro_event_analyst",
                vote="bullish",
                confidence=0.8,
                evidence_ids=[],
                changed=False,
            )
        )
        session.add(
            schema.JudgeSynthesis(
                run_id="p4-bad-run",
                debate_id="debate-review-bad",
                final_state="risk_on",
                confidence=0.8,
                confidence_discount=0.0,
                summary="bad judge",
                payload={
                    "schema_version": "p4.judge_synthesis.v1",
                    "judge_synthesis_id": "judge-bad",
                    "debate_id": "debate-review-bad",
                    "pack_id": "p4-bad-pack",
                    "controller_run_id": "p4-bad-run",
                    "dominant_regime": "risk_on",
                    "trend_state": "risk_on",
                    "risk_state": "event_watch",
                    "consensus_level": "high",
                    "disagreement_level": "low",
                    "accepted_claims": [
                        {
                            "claim": "Aggressive conclusion without concrete evidence.",
                            "evidence_ids": ["no-evidence-id-available"],
                            "direction": "bullish",
                            "strength": 0.9,
                            "uncertainty": "missing evidence",
                        }
                    ],
                    "rejected_claims": [],
                    "minority_objections": [],
                    "confidence": 0.8,
                    "confidence_discount": 0.0,
                    "blocked_by": ["run_mode_integrity_invalidation"],
                    "publish_allowed": True,
                    "evidence_ids": ["no-evidence-id-available"],
                    "state_machine_constraints_applied": [],
                },
            )
        )

    result = run_adversarial_review(debate_id="debate-review-bad", db=db)
    review = result["adversarial_review"]

    assert review["passed"] is False
    assert review["publish_allowed"] is False
    assert review["required_fixes"]
    with db.session() as session:
        debate = session.scalar(
            select(schema.LlmDebate).where(schema.LlmDebate.debate_id == "debate-review-bad")
        )
        row = session.scalar(
            select(schema.AdversarialReview).where(
                schema.AdversarialReview.debate_id == "debate-review-bad"
            )
        )

    assert debate is not None
    assert debate.publish_allowed is False
    assert row is not None
    assert row.review_passed is False
