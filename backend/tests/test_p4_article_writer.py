from onlybtc.p4.agent_runtime import AgentRuntimeAdapter
from onlybtc.p4.article_writer import generate_readable_articles
from onlybtc.p4.prompts import build_analyst_article_prompt, build_final_article_prompt
from onlybtc.p4.schemas import AnalystReadableArticle, FinalObservationArticle


def test_article_writer_mock_generates_schema_valid_articles() -> None:
    result = generate_readable_articles(
        analyst_narratives=[
            {
                "analyst_id": "Macro Analyst",
                "raw_analyst_id": "macro_event_analyst",
                "modules": "macro_surprise, event_risk",
                "vote": "neutral",
                "confidence": 0.62,
                "evidence_count": 1,
                "history_summary": "previous vote=neutral",
                "conclusion": "Evidence ev-1 constrains the macro conclusion.",
                "top_evidence": [
                    {
                        "evidence_id": "ev-1",
                        "metric_id": "cpi_days_until",
                        "source_id": "official-macro-event-calendar",
                        "value": 3,
                        "quality_score": 0.9,
                        "claim": "CPI event is inside watch window.",
                    }
                ],
                "all_evidence": [
                    {
                        "evidence_id": "ev-1",
                        "metric_id": "cpi_days_until",
                        "source_id": "official-macro-event-calendar",
                        "value": 3,
                        "quality_score": 0.9,
                        "claim": "CPI event is inside watch window.",
                    },
                    {
                        "evidence_id": "ev-2",
                        "metric_id": "fomc_days_until",
                        "source_id": "official-macro-event-calendar",
                        "value": 12,
                        "quality_score": 0.88,
                        "claim": "FOMC event remains in the daily watch horizon.",
                    },
                ],
                "coverage_target_evidence_ids": ["ev-1", "ev-2"],
            }
        ],
        final_json={
            "trend_state": "neutral",
            "risk_state": "watch",
            "publish_allowed": True,
            "blocked_by": [],
            "confidence": 0.6,
            "confidence_discount": 0.1,
            "evidence_ids": ["ev-1", "ev-2"],
            "data_quality_notes": [],
            "publish_constraints": [],
        },
        judge={"consensus_level": "medium"},
        review={"passed": True},
        state={"critical_publish_allowed": True, "state_transition_allowed": True},
        article_runtime_mode="mock",
    )

    assert result["status"] == "completed"
    assert result["article_runtime_mode"] == "mock"
    assert result["analyst_articles"][0]["schema_version"] == "p4.analyst_readable_article.v1"
    assert result["final_article"]["schema_version"] == "p4.final_observation_article.v1"
    assert result["analyst_articles"][0]["evidence_citations"][0]["evidence_id"] == "ev-1"
    assert result["analyst_articles"][0]["data_source_appendix"][0]["evidence_id"] == "ev-1"
    analyst_ids = {
        item["evidence_id"] for item in result["analyst_articles"][0]["evidence_citations"]
    }
    final_ids = {item["evidence_id"] for item in result["final_article"]["evidence_citations"]}
    final_appendix_ids = {
        item["evidence_id"] for item in result["final_article"]["data_source_appendix"]
    }
    assert {"ev-1", "ev-2"}.issubset(analyst_ids)
    assert {"ev-1", "ev-2"}.issubset(final_ids)
    assert {"ev-1", "ev-2"}.issubset(final_appendix_ids)


def test_agent_runtime_mock_supports_article_schemas() -> None:
    runtime = AgentRuntimeAdapter()
    analyst_prompt = build_analyst_article_prompt(
        analyst_id="macro_event_analyst",
        article_context={"example": True},
        evidence_ids=["ev-1"],
    )
    analyst_result = runtime.run_mock(analyst_prompt, AnalystReadableArticle)
    assert analyst_result.succeeded
    assert analyst_result.schema_version == "p4.analyst_readable_article.v1"

    final_prompt = build_final_article_prompt(
        article_context={"example": True},
        evidence_ids=["ev-1"],
    )
    final_result = runtime.run_mock(final_prompt, FinalObservationArticle)
    assert final_result.succeeded
    assert final_result.schema_version == "p4.final_observation_article.v1"
