from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID
from onlybtc.p45.html_report import run_p45_html_report
from onlybtc.p45.llm_research_writer import (
    P45_LLM_RESEARCH_ARTICLE_MODULE_ID,
    run_p45_llm_research_writer,
)
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID


def test_p45_llm_research_writer_mock_persists_and_appends_html(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="pack-test",
                    module_id=P45_EVIDENCE_PACK_MODULE_ID,
                    schema_version="p45.evidence_pack.v1",
                    payload=_pack_payload(),
                ),
                schema.ModuleJsonOutput(
                    run_id="articles-test",
                    module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                    schema_version="p45.analyst_articles.v1",
                    payload=_article_payload(),
                ),
                schema.ModuleJsonOutput(
                    run_id="final-test",
                    module_id=P45_FINAL_ARTICLE_MODULE_ID,
                    schema_version="p45.final_article.v1",
                    payload=_final_payload(),
                ),
            ]
        )

    result = run_p45_llm_research_writer(
        final_run_id="final-test",
        research_run_id="research-test",
        runtime_mode="mock",
        db=db,
    )

    assert result["status"] == "completed"
    assert result["llm_research_run_id"] == "research-test"
    assert result["metric_evidence_count_seen"] == 14
    assert set(result["radar_modules_covered"]) == set(_module_ids())
    assert result["evidence_ids_used"]

    output_path = tmp_path / "p45.html"
    run_p45_html_report(final_run_id="final-test", output_path=output_path, db=db)
    html = output_path.read_text(encoding="utf-8")

    assert "最终综合研究文章" in html
    assert "Evidence 附录" in html
    assert "LLM 深度中文研报" in html
    assert "llm_article_scope=internal_reference" in html
    assert "latency_ms" in html
    assert "不参与 final_view" in html
    assert 'href="#ev-macro_radar-1"' in html
    assert 'id="ev-macro_radar-1"' in html

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "research-test",
                schema.ModuleJsonOutput.module_id == P45_LLM_RESEARCH_ARTICLE_MODULE_ID,
            )
        )
    assert row is not None


def test_p45_llm_research_writer_failed_payload_is_explicit(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="pack-test",
                    module_id=P45_EVIDENCE_PACK_MODULE_ID,
                    schema_version="p45.evidence_pack.v1",
                    payload=_pack_payload(),
                ),
                schema.ModuleJsonOutput(
                    run_id="articles-test",
                    module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                    schema_version="p45.analyst_articles.v1",
                    payload=_article_payload(),
                ),
                schema.ModuleJsonOutput(
                    run_id="final-test",
                    module_id=P45_FINAL_ARTICLE_MODULE_ID,
                    schema_version="p45.final_article.v1",
                    payload=_final_payload(),
                ),
            ]
        )

    result = run_p45_llm_research_writer(
        final_run_id="final-test",
        research_run_id="failed-test",
        runtime_mode="bad-mode",
        db=db,
    )

    assert result["status"] == "failed"
    assert result["error"]

    output_path = tmp_path / "p45.html"
    run_p45_html_report(final_run_id="final-test", output_path=output_path, db=db)
    html = output_path.read_text(encoding="utf-8")

    assert "最终综合研究文章" in html
    assert "LLM Research Writer 未完成" in html
    assert "Unsupported runtime_mode" in html


def _final_payload() -> dict:
    return {
        "schema_version": "p45.final_article.v1",
        "final_run_id": "final-test",
        "article_run_id": "articles-test",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "runtime_mode": "deterministic",
        "core_view": "mixed",
        "direction_counts": {"bullish": 1, "bearish": 1, "mixed": 2, "neutral": 0},
        "article": "# 主结论\n引用 ev-macro_radar-1。",
    }


def _article_payload() -> dict:
    return {
        "schema_version": "p45.analyst_articles.v1",
        "article_run_id": "articles-test",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "runtime_mode": "deterministic",
        "analyst_articles": [
            {
                "analyst_id": "macro_event_analyst",
                "title": "宏观与事件分析员",
                "direction_view": "mixed",
                "score_summary": "summary",
                "article": "引用 ev-macro_radar-1。",
            }
        ],
    }


def _pack_payload() -> dict:
    modules = []
    for index, module_id in enumerate(_module_ids(), start=1):
        modules.append(
            {
                "radar_module": module_id,
                "module_score": 0.1 if index % 2 else -0.1,
                "module_direction": "bullish" if index % 2 else "bearish",
                "module_strength": 0.1,
                "module_confidence": 0.9,
                "module_quality_score": 0.95,
                "positive_metric_count": 1 if index % 2 else 0,
                "negative_metric_count": 0 if index % 2 else 1,
                "zero_metric_count": 0,
                "unavailable_metric_count": 0,
                "module_explanation": f"{module_id} explanation",
                "data_boundary": [],
                "metrics": [
                    {
                        "evidence_id": f"ev-{module_id}-1",
                        "metric_id": f"{module_id}_metric",
                        "source_id": "source",
                        "value": index,
                        "metric_score": 0.1 if index % 2 else -0.1,
                        "base_metric_score": 0.1 if index % 2 else -0.1,
                        "score_bucket": "positive" if index % 2 else "negative",
                        "direction": "bullish" if index % 2 else "bearish",
                        "base_direction": "bullish" if index % 2 else "bearish",
                        "quality_score": 0.95,
                        "semantic_rule_id": "semantic.test",
                        "semantic_warning": "",
                        "p45_metric_brief": f"{module_id} metric brief",
                        "score_reason": "score reason",
                    }
                ],
            }
        )
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "analysts": [{"analyst_id": "macro_event_analyst", "modules": modules}],
    }


def _module_ids() -> list[str]:
    return [
        "macro_radar",
        "treasury_credit",
        "asia_risk",
        "event_policy",
        "dollar_liquidity",
        "fund_flow",
        "crypto_breadth",
        "kline_orderflow",
        "derivatives_crowding",
        "trade_structure_flow",
        "options_volatility",
        "btc_total_state",
        "btc_adoption",
        "onchain_valuation",
    ]
