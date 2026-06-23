from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.schemas import (
    AgentEvidenceItem,
    AnalystHistory,
    AnalystHistoryEntry,
    AnalystInput,
    AnalystOutput,
    CrossExamChallenge,
    FinalControllerJson,
    JudgeSynthesis,
    KeyClaim,
)


def _history() -> AnalystHistory:
    return AnalystHistory(
        history_available=True,
        history=[
            AnalystHistoryEntry(
                debate_id="debate-1",
                run_id="run-prev",
                vote="neutral",
                confidence=0.6,
                evidence_ids=["ev-prev"],
                changed=False,
                created_at=datetime.now(UTC),
            )
        ],
    )


def test_analyst_input_validates_assigned_modules_and_evidence_scope() -> None:
    analyst_id = "macro_event_analyst"
    analyst_input = AnalystInput(
        pack_id="pack-1",
        controller_run_id="p4-run-1",
        p2_radar_run_id="radar-1",
        p3_run_id="p3-1",
        analyst_id=analyst_id,
        assigned_modules=list(ANALYST_MODULES[analyst_id]),
        analyst_history=_history(),
        evidence_items=[
            AgentEvidenceItem(
                evidence_id="ev-1",
                source_layer="p2_radar",
                module_id="macro_radar",
                metric_id="dxy",
                role="primary_signal",
                quality_score=0.9,
                affects_signal=True,
                affects_confidence=True,
                affects_risk_flags=False,
            ),
            AgentEvidenceItem(
                evidence_id="ev-event",
                source_layer="p3_event",
                module_id="p3_event_window_engine",
            ),
        ],
    )

    assert analyst_input.analyst_id == analyst_id
    assert analyst_input.evidence_items[0].evidence_id == "ev-1"


def test_analyst_input_rejects_out_of_scope_radar_evidence() -> None:
    with pytest.raises(ValidationError, match="outside assigned modules"):
        AnalystInput(
            pack_id="pack-1",
            controller_run_id="p4-run-1",
            p2_radar_run_id="radar-1",
            p3_run_id="p3-1",
            analyst_id="macro_event_analyst",
            assigned_modules=list(ANALYST_MODULES["macro_event_analyst"]),
            analyst_history=AnalystHistory(history_available=False, history=[]),
            evidence_items=[
                AgentEvidenceItem(
                    evidence_id="ev-bad",
                    source_layer="p2_radar",
                    module_id="fund_flow",
                )
            ],
        )


def test_agent_outputs_require_evidence_ids_for_claims() -> None:
    claim = KeyClaim(
        claim="Macro event risk is elevated.",
        evidence_ids=["ev-1"],
        direction="risk_off",
        strength=0.7,
    )
    output = AnalystOutput(
        analyst_id="macro_event_analyst",
        vote="risk_off",
        confidence=0.68,
        key_claims=[claim],
    )

    assert output.key_claims[0].evidence_ids == ["ev-1"]
    with pytest.raises(ValidationError):
        KeyClaim(claim="No evidence claim", evidence_ids=[], strength=0.2)


def test_cross_exam_judge_and_final_controller_schema() -> None:
    challenge = CrossExamChallenge(
        challenge_id="ch-1",
        from_agent="cross_examiner_agent",
        to_agent="liquidity_flow_analyst",
        challenge_type="missing_evidence",
        claim_under_review="Liquidity is improving.",
        evidence_ids=["ev-2"],
        severity="medium",
        required_response="Explain whether stale ETF data lowers confidence.",
    )
    claim = KeyClaim(
        claim="Liquidity improvement is not confirmed.",
        evidence_ids=["ev-2"],
        direction="neutral",
        strength=0.5,
    )
    judge = JudgeSynthesis(
        judge_synthesis_id="judge-1",
        debate_id="debate-1",
        pack_id="pack-1",
        controller_run_id="p4-run-1",
        dominant_regime="mixed_liquidity",
        trend_state="neutral",
        risk_state="watch",
        consensus_level="medium",
        disagreement_level="medium",
        accepted_claims=[claim],
        confidence=0.62,
        publish_allowed=True,
        evidence_ids=["ev-2"],
    )
    final_json = FinalControllerJson(
        run_id="p4-run-1",
        evidence_pack_id="pack-1",
        debate_id="debate-1",
        judge_synthesis_id=judge.judge_synthesis_id,
        challenge_ids=[challenge.challenge_id],
        trend_state="neutral",
        risk_state="watch",
        confidence=0.62,
        publish_allowed=True,
        evidence_ids=["ev-2"],
    )

    assert challenge.challenge_type == "missing_evidence"
    assert judge.evidence_ids == ["ev-2"]
    assert final_json.challenge_ids == ["ch-1"]
