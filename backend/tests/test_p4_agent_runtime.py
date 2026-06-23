from datetime import UTC, datetime

from onlybtc.p4.agent_runtime import AgentRuntimeAdapter, provider_config, provider_for_agent
from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.prompts import build_analyst_article_prompt, build_analyst_prompt
from onlybtc.p4.schemas import (
    AgentEvidenceItem,
    AnalystHistory,
    AnalystHistoryEntry,
    AnalystInput,
    AnalystOutput,
    AnalystReadableArticle,
    CrossExamChallenge,
    CrossExamRevision,
    JudgeSynthesis,
)


def _prompt():
    analyst_input = AnalystInput(
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
                    vote="neutral",
                    confidence=0.6,
                    evidence_ids=["ev-old"],
                    changed=False,
                    created_at=datetime.now(UTC),
                )
            ],
        ),
        evidence_items=[
            AgentEvidenceItem(
                evidence_id="ev-1",
                source_layer="p2_radar",
                module_id="macro_radar",
                metric_id="dxy",
            )
        ],
    )
    return build_analyst_prompt(analyst_input)


def test_provider_routing_reads_p4_agent_settings() -> None:
    deepseek = provider_for_agent("macro_event_analyst")
    judge = provider_for_agent("judge_agent")
    adversarial = provider_for_agent("adversarial_reviewer_agent")
    direct = provider_config("kimi")

    assert deepseek.provider == "deepseek"
    assert deepseek.model_name == "deepseek-reasoner"
    assert judge.provider == "deepseek"
    assert adversarial.provider == "deepseek"
    assert direct.provider == "kimi"
    assert direct.model_name == "kimi-k2.6"


def test_mock_runtime_validates_schema_and_guardrails() -> None:
    runtime = AgentRuntimeAdapter()
    result = runtime.run_mock(_prompt(), AnalystOutput)

    assert result.succeeded
    assert result.agent_role == "analyst"
    assert result.agent_name == "macro_event_analyst"
    assert result.model_provider == "deepseek"
    assert result.prompt_version == "p4.agent_prompt.v1"
    assert result.schema_version == "p4.analyst_output.v1"
    assert result.structured_output is not None
    assert result.structured_output["key_claims"][0]["evidence_ids"] == ["ev-1"]
    assert result.trace_id.startswith("trace-")
    assert result.agent_run_id.startswith("agent-run-")


def test_runtime_blocks_unknown_evidence_ids() -> None:
    runtime = AgentRuntimeAdapter()
    result = runtime.run_mock(
        _prompt(),
        AnalystOutput,
        structured_output={
            "analyst_id": "macro_event_analyst",
            "vote": "neutral",
            "confidence": 0.5,
            "key_claims": [
                {
                    "claim": "Uses evidence outside the pack.",
                    "evidence_ids": ["ev-not-in-pack"],
                    "direction": "neutral",
                    "strength": 0.2,
                }
            ],
            "history_delta": {"changed": False},
        },
    )

    assert not result.succeeded
    assert result.error is not None
    assert "Unknown evidence ids" in result.error


def test_runtime_blocks_trading_advice_terms() -> None:
    runtime = AgentRuntimeAdapter()
    result = runtime.run_mock(
        _prompt(),
        AnalystOutput,
        structured_output={
            "analyst_id": "macro_event_analyst",
            "vote": "neutral",
            "confidence": 0.5,
            "key_claims": [
                {
                    "claim": "Do not 建议开仓 based on this mock.",
                    "evidence_ids": ["ev-1"],
                    "direction": "neutral",
                    "strength": 0.2,
                }
            ],
            "history_delta": {"changed": False},
        },
    )

    assert not result.succeeded
    assert result.error is not None
    assert "Prohibited trading terms" in result.error


def test_llm_runtime_budget_error_can_fallback_to_mock() -> None:
    runtime = AgentRuntimeAdapter()
    runtime.settings.p4_llm_max_calls_per_run = 0
    prompt = _prompt()
    fallback = runtime.run_mock(prompt, AnalystOutput).structured_output
    assert fallback is not None

    result = runtime.run_llm_or_mock(prompt, AnalystOutput, fallback_output=fallback)

    assert result.succeeded
    assert result.fallback_used
    assert result.fallback_reason is not None
    assert "llm_budget_exceeded" in result.fallback_reason


def test_runtime_unwraps_common_llm_schema_wrappers() -> None:
    runtime = AgentRuntimeAdapter()
    prompt = _prompt().model_copy(
        update={
            "agent_id": "macro_event_analyst",
            "agent_role": "cross_exam_revision",
            "evidence_ids": ["ev-1"],
        }
    )
    result = runtime.run_mock(
        prompt,
        CrossExamRevision,
        structured_output={
            "cross_exam_revision": {
                "challenge_id": "ch-1",
                "responding_agent": "macro_event_analyst",
                "changed": False,
                "previous_vote": "neutral",
                "revised_vote": "neutral",
                "previous_confidence": 0.5,
                "revised_confidence": 0.5,
                "accepted_points": [],
                "rejected_points": ["Evidence ev-1 still supports the scoped conclusion."],
                "reason": "No change because the cited evidence remains sufficient.",
                "evidence_ids": ["ev-1"],
            }
        },
    )

    assert result.succeeded
    assert result.structured_output is not None
    assert result.structured_output["challenge_id"] == "ch-1"


def test_runtime_repairs_cross_exam_revision_from_prompt_context() -> None:
    runtime = AgentRuntimeAdapter()
    prompt = _prompt().model_copy(
        update={
            "agent_id": "macro_event_analyst",
            "agent_role": "cross_exam_revision",
            "evidence_ids": ["ev-1"],
            "user_prompt": (
                "Produce one CrossExamRevision JSON object.\n\n"
                '{"challenge":{"challenge_id":"ch-1","to_agent":"macro_event_analyst",'
                '"evidence_ids":["ev-1"]},"vote":{"model_name":"macro_event_analyst",'
                '"vote":"neutral","confidence":0.55,"evidence_ids":["ev-1"]}}'
            ),
        }
    )
    result = runtime.run_mock(
        prompt,
        CrossExamRevision,
        structured_output={
            "challenge_id": "ch-1",
            "changed": True,
            "revised_confidence": 0.5,
            "reason": "Challenge lowers confidence but not vote.",
            "evidence_ids": ["ev-1"],
        },
    )

    assert result.succeeded
    assert result.structured_output is not None
    assert result.structured_output["responding_agent"] == "macro_event_analyst"
    assert result.structured_output["previous_vote"] == "neutral"
    assert result.structured_output["revised_vote"] == "neutral"
    assert result.structured_output["previous_confidence"] == 0.55
    assert result.structured_output["revised_confidence"] == 0.5


def test_runtime_repairs_cross_exam_revision_vote_dict_leak() -> None:
    runtime = AgentRuntimeAdapter()
    prompt = _prompt().model_copy(
        update={
            "agent_id": "macro_event_analyst",
            "agent_role": "cross_exam_revision",
            "evidence_ids": ["ev-1"],
            "user_prompt": (
                "Produce one CrossExamRevision JSON object.\n\n"
                '{"challenge":{"challenge_id":"ch-1","to_agent":"macro_event_analyst",'
                '"evidence_ids":["ev-1"]},"vote":{"model_name":"macro_event_analyst",'
                '"vote":"neutral","confidence":0.55,"evidence_ids":["ev-1"]}}'
            ),
        }
    )
    result = runtime.run_mock(
        prompt,
        CrossExamRevision,
        structured_output={
            "challenge_id": "ch-1",
            "changed": False,
            "revised_vote": {"model_name": "macro_event_analyst", "vote": "neutral"},
            "reason": "No change.",
            "evidence_ids": ["ev-1"],
        },
    )

    assert result.succeeded
    assert result.structured_output is not None
    assert result.structured_output["revised_vote"] == "neutral"


def test_runtime_repairs_cross_exam_challenge_type_and_evidence_ids() -> None:
    runtime = AgentRuntimeAdapter()
    prompt = _prompt().model_copy(
        update={
            "agent_id": "cross_examiner_agent",
            "agent_role": "cross_examiner",
            "evidence_ids": ["ev-1"],
            "user_prompt": (
                "Return one CrossExamChallenge JSON object.\n\n"
                '{"candidate_challenge":{"challenge_id":"ch-1",'
                '"from_agent":"cross_examiner_agent","to_agent":"macro_event_analyst",'
                '"challenge_type":"missing_evidence","claim_under_review":"low confidence",'
                '"evidence_ids":["ev-1"],"severity":"medium",'
                '"required_response":"Explain confidence."}}'
            ),
        }
    )
    result = runtime.run_mock(
        prompt,
        CrossExamChallenge,
        structured_output={
            "challenge_id": "ch-1",
            "from_agent": "cross_examiner_agent",
            "to_agent": "macro_event_analyst",
            "challenge_type": "low_confidence",
            "claim_under_review": "low confidence",
            "evidence_ids": ["ev-1", "ev-unknown"],
            "severity": "medium",
            "required_response": "Explain confidence.",
        },
    )

    assert result.succeeded
    assert result.structured_output is not None
    assert result.structured_output["challenge_type"] == "missing_evidence"
    assert result.structured_output["evidence_ids"] == ["ev-1"]


def test_runtime_wraps_partial_analyst_article_section() -> None:
    runtime = AgentRuntimeAdapter()
    prompt = build_analyst_article_prompt(
        analyst_id="macro_event_analyst",
        article_context={"example": True},
        evidence_ids=["ev-1"],
    )
    result = runtime.run_mock(
        prompt,
        AnalystReadableArticle,
        structured_output={
            "heading": "宏观事件要点",
            "body": "事件窗口约束仍然压制发布范围。",
            "evidence_ids": ["ev-1"],
        },
    )

    assert result.succeeded
    assert result.structured_output is not None
    assert result.structured_output["analyst_id"] == "macro_event_analyst"
    assert result.structured_output["sections"][0]["heading"] == "宏观事件要点"
    assert result.structured_output["data_source_appendix"][0]["evidence_id"] == "ev-1"


def test_runtime_filters_judge_extra_context_fields() -> None:
    runtime = AgentRuntimeAdapter()
    prompt = _prompt().model_copy(
        update={
            "agent_id": "judge_agent",
            "agent_role": "judge",
            "evidence_ids": ["ev-1"],
        }
    )
    result = runtime.run_mock(
        prompt,
        JudgeSynthesis,
        structured_output={
            "judge_synthesis_id": "judge-1",
            "debate_id": "debate-1",
            "pack_id": "pack-1",
            "controller_run_id": "run-1",
            "dominant_regime": "neutral",
            "trend_state": "neutral",
            "risk_state": "watch",
            "consensus_level": "low",
            "disagreement_level": "medium",
            "confidence": 0.5,
            "confidence_discount": 0.1,
            "publish_allowed": False,
            "evidence_ids": ["ev-1"],
            "votes": [{"extra": True}],
            "baseline": {"extra": True},
        },
    )

    assert result.succeeded
    assert result.structured_output is not None
    assert "votes" not in result.structured_output


def test_runtime_sanitizes_article_trading_terms_before_guardrail() -> None:
    runtime = AgentRuntimeAdapter()
    prompt = build_analyst_article_prompt(
        analyst_id="macro_event_analyst",
        article_context={"example": True},
        evidence_ids=["ev-1"],
    )
    result = runtime.run_mock(
        prompt,
        AnalystReadableArticle,
        structured_output={
            "title": "宏观事件",
            "summary": "讨论仓位拥挤度，但不提供直接交易指令。",
            "sections": [
                {
                    "heading": "观察",
                    "body": "这里只讨论仓位风险暴露和拥挤度，不提供直接交易指令。",
                    "evidence_ids": ["ev-1"],
                }
            ],
            "evidence_citations": [{"evidence_id": "ev-1", "note": "测试证据"}],
        },
    )

    assert result.succeeded
    assert result.structured_output is not None
    assert "仓位" in str(result.structured_output)
