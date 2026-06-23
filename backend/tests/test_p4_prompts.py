from datetime import UTC, datetime

from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.prompts import (
    PROHIBITED_TRADING_TERMS,
    build_adversarial_reviewer_system_prompt,
    build_analyst_prompt,
    build_cross_examiner_system_prompt,
    build_judge_system_prompt,
)
from onlybtc.p4.schemas import (
    AgentEvidenceItem,
    AnalystHistory,
    AnalystHistoryEntry,
    AnalystInput,
)


def _analyst_input() -> AnalystInput:
    return AnalystInput(
        pack_id="pack-1",
        controller_run_id="p4-run-1",
        p2_radar_run_id="radar-1",
        p3_run_id="p3-1",
        analyst_id="macro_event_analyst",
        assigned_modules=list(ANALYST_MODULES["macro_event_analyst"]),
        analyst_history=AnalystHistory(
            history_available=True,
            history=[
                AnalystHistoryEntry(
                    debate_id="debate-prev",
                    run_id="p4-prev",
                    vote="risk_off",
                    confidence=0.7,
                    evidence_ids=["old-ev"],
                    changed=True,
                    created_at=datetime.now(UTC),
                )
            ],
        ),
        evidence_items=[
            AgentEvidenceItem(
                evidence_id="ev-macro-1",
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
                evidence_id="ev-event-1",
                source_layer="p3_event",
                module_id="p3_event_window_engine",
                metric_id="cpi_signed_days",
                quality_score=0.82,
                affects_signal=False,
                affects_confidence=True,
                affects_risk_flags=True,
            ),
        ],
    )


def test_build_analyst_prompt_binds_evidence_pack_and_schema() -> None:
    prompt = build_analyst_prompt(_analyst_input())

    assert prompt.prompt_version == "p4.agent_prompt.v1"
    assert prompt.agent_id == "macro_event_analyst"
    assert prompt.agent_role == "analyst"
    assert prompt.evidence_ids == ["ev-macro-1", "ev-event-1"]
    assert "pack-1" in prompt.user_prompt
    assert "radar-1" in prompt.user_prompt
    assert "macro_radar" in prompt.system_prompt
    assert "event_policy" in prompt.system_prompt
    assert "ev-macro-1" in prompt.user_prompt
    assert "ev-event-1" in prompt.user_prompt
    assert "AnalystOutput" in prompt.user_prompt
    assert "key_claims" in prompt.user_prompt
    assert prompt.output_schema["title"] == "AnalystOutput"


def test_analyst_prompt_contains_guardrails_and_history_boundary() -> None:
    prompt = build_analyst_prompt(_analyst_input())
    combined = prompt.system_prompt + "\n" + prompt.user_prompt

    assert "analyst_history is continuity context only" in combined
    assert "cannot override current P2/P3 evidence" in combined
    assert "Do not invent external facts" in combined
    assert "final BTC controller decision" in combined
    assert "run_mode integrity" in combined
    assert "source conflicts" in combined
    for term in PROHIBITED_TRADING_TERMS:
        assert term in combined


def test_supporting_agent_prompt_bundles_expose_expected_schemas() -> None:
    cross_exam = build_cross_examiner_system_prompt()
    judge = build_judge_system_prompt()
    adversarial = build_adversarial_reviewer_system_prompt()

    assert cross_exam.agent_role == "cross_examiner"
    assert cross_exam.output_schema["title"] == "CrossExamChallenge"
    assert "evidence_ids" in cross_exam.user_prompt
    assert judge.agent_role == "judge"
    assert judge.output_schema["title"] == "JudgeSynthesis"
    assert "Hard constraints override" in judge.system_prompt
    assert adversarial.agent_role == "adversarial_reviewer"
    assert adversarial.output_schema["title"] == "AdversarialReview"
