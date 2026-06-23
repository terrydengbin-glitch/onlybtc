from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID
from onlybtc.p45.html_report import run_p45_html_report
from onlybtc.p45.llm_analyst_writer import (
    P45_LLM_ANALYST_ARTICLES_MODULE_ID,
    run_p45_llm_analyst_writers,
)
from onlybtc.p45.llm_research_writer import P45_LLM_RESEARCH_ARTICLE_MODULE_ID
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID


def test_p45_llm_analyst_writers_mock_append_after_research(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_payloads(db)

    result = run_p45_llm_analyst_writers(
        pack_id="pack-test",
        analyst_run_id="analysts-test",
        runtime_mode="mock",
        db=db,
    )

    assert result["summary"]["analyst_count"] == 4
    assert result["summary"]["completed_count"] == 4
    assert result["summary"]["failed_count"] == 0
    assert len(result["summary"]["radar_modules_covered"]) == 14
    for item in result["analyst_articles"]:
        expected = set(_modules_by_analyst()[item["analyst_id"]])
        assert set(item["radar_modules_covered"]) == expected
        assert item["evidence_ids_used"]

    output_path = tmp_path / "p45.html"
    run_p45_html_report(final_run_id="final-test", output_path=output_path, db=db)
    html = output_path.read_text(encoding="utf-8")

    assert "LLM 深度中文研报" in html
    assert "llm_article_scope=internal_reference" in html
    assert "四分析师 LLM 板块深度分析" in html
    assert "latency_ms" in html
    assert "error" in html
    assert html.index("四分析师 LLM 板块深度分析") > html.index("LLM 深度中文研报")
    assert 'href="#ev-macro_radar-1"' in html
    assert 'id="ev-macro_radar-1"' in html

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "analysts-test",
                schema.ModuleJsonOutput.module_id == P45_LLM_ANALYST_ARTICLES_MODULE_ID,
            )
        )
    assert row is not None


def test_p45_llm_analyst_writers_failed_cards_are_explicit(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_payloads(db)

    result = run_p45_llm_analyst_writers(
        pack_id="pack-test",
        analyst_run_id="analysts-failed",
        runtime_mode="bad-mode",
        db=db,
    )

    assert result["summary"]["failed_count"] == 4
    assert all(item["error"] for item in result["analyst_articles"])

    output_path = tmp_path / "p45.html"
    run_p45_html_report(final_run_id="final-test", output_path=output_path, db=db)
    html = output_path.read_text(encoding="utf-8")

    assert "最终综合研究文章" in html
    assert "四分析师 LLM 板块深度分析" in html
    assert "分析师 LLM 未完成" in html
    assert "Unsupported runtime_mode" in html


def _seed_payloads(db: Database) -> None:
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
                schema.ModuleJsonOutput(
                    run_id="research-test",
                    module_id=P45_LLM_RESEARCH_ARTICLE_MODULE_ID,
                    schema_version="p45.llm_research_article.v1",
                    payload=_research_payload(),
                ),
            ]
        )


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
        "analyst_articles": [],
    }


def _research_payload() -> dict:
    return {
        "schema_version": "p45.llm_research_article.v1",
        "llm_research_run_id": "research-test",
        "final_run_id": "final-test",
        "article_run_id": "articles-test",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "provider": "mock",
        "model": "mock",
        "runtime_mode": "mock",
        "status": "completed",
        "article": "# LLM 主研报\n引用 ev-macro_radar-1。",
        "title": "LLM 主研报",
        "core_view": "mixed",
        "evidence_ids_used": ["ev-macro_radar-1"],
        "radar_modules_covered": _all_modules(),
        "metric_evidence_count_seen": 14,
        "created_at": "2026-05-22T00:00:00+00:00",
        "latency_ms": 1,
        "error": None,
        "prompt_context_summary": {},
    }


def _pack_payload() -> dict:
    analysts = []
    for analyst_id, modules in _modules_by_analyst().items():
        analysts.append(
            {
                "analyst_id": analyst_id,
                "modules": [_module_payload(module_id) for module_id in modules],
            }
        )
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "analysts": analysts,
    }


def _module_payload(module_id: str) -> dict:
    return {
        "radar_module": module_id,
        "module_score": 0.1,
        "module_direction": "bullish",
        "module_strength": 0.1,
        "module_confidence": 0.9,
        "module_quality_score": 0.95,
        "positive_metric_count": 1,
        "negative_metric_count": 0,
        "zero_metric_count": 0,
        "unavailable_metric_count": 0,
        "module_explanation": f"{module_id} explanation",
        "data_boundary": [],
        "metrics": [
            {
                "evidence_id": f"ev-{module_id}-1",
                "metric_id": f"{module_id}_metric",
                "source_id": "source",
                "value": 1.0,
                "metric_score": 0.1,
                "base_metric_score": 0.1,
                "score_bucket": "positive",
                "direction": "bullish",
                "base_direction": "bullish",
                "quality_score": 0.95,
                "semantic_rule_id": "semantic.test",
                "semantic_warning": "",
                "p45_metric_brief": f"{module_id} metric brief",
                "score_reason": "score reason",
            }
        ],
    }


def _modules_by_analyst() -> dict[str, list[str]]:
    return {
        "macro_event_analyst": [
            "macro_radar",
            "treasury_credit",
            "asia_risk",
            "event_policy",
        ],
        "liquidity_flow_analyst": [
            "dollar_liquidity",
            "fund_flow",
            "crypto_breadth",
        ],
        "microstructure_analyst": [
            "kline_orderflow",
            "derivatives_crowding",
            "trade_structure_flow",
            "options_volatility",
        ],
        "onchain_structure_analyst": [
            "btc_total_state",
            "btc_adoption",
            "onchain_valuation",
        ],
    }


def _all_modules() -> list[str]:
    return [
        module for modules in _modules_by_analyst().values() for module in modules
    ]
