from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID
from onlybtc.p45.html_report import run_p45_html_report
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID


def test_p45_html_report_links_article_to_evidence_appendix(tmp_path) -> None:
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

    output_path = tmp_path / "p45.html"
    result = run_p45_html_report(
        final_run_id="final-test",
        output_path=output_path,
        db=db,
    )

    html = output_path.read_text(encoding="utf-8")
    assert result["html_path"] == str(output_path)
    assert "P4.5 BTC 研究报告" in html
    assert 'href="#ev-test-1"' in html
    assert 'id="ev-test-1"' in html
    assert "metric brief" in html
    assert "final_view" in html
    assert "legacy_core_view" in html
    assert "决策卡" in html
    assert "时间尺度拆分" in html
    assert "反证条件" in html
    assert "Confirmation Rules" in html
    assert "聚合逻辑审计" in html
    assert "发文版本" in html
    assert "四位分析员审计附录" in html
    assert "deterministic_analyst_audit_appendix" in html
    assert "BTC Total State v2 分层解释" in html
    assert "price_up_confirmed" in html
    assert "Event Policy v2.1" in html
    assert "PRE_CPI_24H_CAUTION" in html
    assert "size_multiplier=0.7" in html
    assert "Funding positive alone is not bullish" in html
    assert "<details>" in html
    assert "BTC 测试发文" in html
    assert "{'metric_id'" not in html

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID,
            )
        )
    assert row is not None


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
        "core_view": "bullish",
        "legacy_core_view": "bearish",
        "final_view": "bullish",
        "final_view_cn": "偏多",
        "view_consistency_check": {"status": "passed", "conflicts": []},
        "decision_card": {
            "direction": "bullish",
            "direction_cn": "偏多",
            "strength": "weak_bullish",
            "strength_cn": "弱偏多",
            "confidence": 0.62,
            "confidence_level": "medium",
            "trade_permission": "watch_only",
            "valid_horizon": "24h_to_3d",
            "conclusion_sentence": "测试决策卡。",
            "why_not_strong_bullish": ["仍有反向驱动。"],
        },
        "horizon_views": {
            "h24": {
                "label": "24h",
                "direction": "bullish",
                "strength": "weak_bullish",
                "confidence": 0.62,
                "support_drivers": [
                    {
                        "metric_id": "btc_price",
                        "weighted_contribution": 0.18,
                        "direction": "bullish",
                    }
                ],
                "pressure_drivers": [],
                "dominant_side": "support",
                "dominant_drivers": [
                    {
                        "metric_id": "btc_price",
                        "weighted_contribution": 0.18,
                        "direction": "bullish",
                    }
                ],
                "interpretation": "24h 测试。",
                "watch_rules": ["观察成交量"],
            },
            "d3": {
                "label": "3d",
                "direction": "neutral",
                "strength": "neutral",
                "confidence": 0.55,
                "support_drivers": [],
                "pressure_drivers": [],
                "dominant_side": "mixed",
                "dominant_drivers": [],
                "interpretation": "3d 测试。",
                "watch_rules": ["观察 ETF"],
            },
            "d7": {
                "label": "7d",
                "direction": "neutral",
                "strength": "neutral",
                "confidence": 0.55,
                "support_drivers": [],
                "pressure_drivers": [],
                "dominant_side": "mixed",
                "dominant_drivers": [],
                "interpretation": "7d 测试。",
                "watch_rules": ["观察链上"],
            },
        },
        "invalidation_rules": [
            {
                "rule_id": "inv_test",
                "horizon": "24h",
                "title": "测试反证",
                "metric_ids": ["btc_price"],
                "applies_when": ["bullish"],
                "operator": "AND",
                "conditions": [
                    {"metric_id": "btc_price", "field": "metric_score", "op": "<", "value": 0}
                ],
                "action_if_triggered": {"from": "bullish", "to": "neutral"},
                "reason": "测试",
            }
        ],
        "confirmation_rules": [
            {
                "rule_id": "confirm_test",
                "horizon": "24h_to_3d",
                "title": "测试确认",
                "metric_ids": ["btc_price"],
                "applies_when": ["neutral", "weak_bearish"],
                "operator": "AND",
                "conditions": [
                    {"metric_id": "btc_price", "field": "metric_score", "op": "<", "value": 0}
                ],
                "action_if_triggered": {"from": "neutral", "to": "weak_bearish"},
                "reason": "测试",
            }
        ],
        "aggregation_audit": {
            "final_score_raw": 0.2,
            "final_score_adjusted": 0.18,
            "direction": "bullish",
            "strength": "weak_bullish",
            "confidence": 0.62,
            "disagreement_level": "low",
            "data_quality_level": "high",
            "score_components": {"support_score_abs": 0.2},
            "dominant_drivers": [
                {
                    "metric_id": "btc_price",
                    "module": "btc_total_state",
                    "direction": "bullish",
                    "weighted_contribution": 0.18,
                    "reason": "测试",
                }
            ],
            "support_drivers": [
                {
                    "metric_id": "btc_price",
                    "module": "btc_total_state",
                    "direction": "bullish",
                    "weighted_contribution": 0.18,
                    "reason": "测试",
                }
            ],
            "pressure_drivers": [],
            "counter_drivers": [],
        },
        "btc_total_state_explanation": {
            "btc_short_term_state": "price_up_confirmed",
            "direction_drivers": [
                {"layer": "price_state", "state": "price_up"},
                {"layer": "perp_state", "state": "healthy_participation"},
            ],
            "risk_drivers": [
                {
                    "layer": "perp_state",
                    "state": "healthy_participation",
                    "risk_state": "normal",
                    "confirmation": "confirming",
                }
            ],
            "cycle_context": {"state": "halving_context_only"},
            "audit_context": {"state": "block_height_synced"},
            "context_notes": ["halving context only"],
            "audit_notes": ["block height audit only"],
            "composite_only_notes": [
                "Funding positive alone is not bullish; OI high alone is not directional."
            ],
        },
        "event_policy_explanation": {
            "event_short_term_state": "cpi_caution",
            "dominant_event_type": "cpi",
            "nearest_event_type": "cpi",
            "nearest_event_hours": 18.0,
            "event_window_phase": "caution",
            "trade_gate": {
                "allow_new_position": True,
                "allow_add_position": False,
                "allow_breakout_entry": False,
                "allow_market_entry": True,
                "position_size_multiplier": 0.7,
                "require_wait_until_ts": None,
                "reason_code": "PRE_CPI_24H_CAUTION",
            },
            "context_notes": ["Event policy is not directional alpha."],
            "summary": "CPI caution window reduces breakout permission.",
        },
        "research_article": {
            "body": "# 主结论\n测试决策卡。没有内部证据编号。",
            "forbidden_content_check": {},
        },
        "publish_article": {
            "safe_to_publish": True,
            "title": "BTC 测试发文",
            "body": "BTC 测试正文。$BTC",
            "cashtags": ["$BTC"],
            "forbidden_content_check": {},
        },
        "contract_validation": {"status": "passed"},
        "article": "# 主结论\n引用 ev-test-1 判断偏多。",
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
                "analyst_id": "microstructure_analyst",
                "title": "微观结构分析员：偏多",
                "direction_view": "bullish",
                "score_summary": "summary",
                "article": "短线动能引用 ev-test-1。",
                "key_positive_evidence_ids": ["ev-test-1"],
                "key_negative_evidence_ids": [],
                "neutral_watch_evidence_ids": [],
            }
        ],
    }


def _pack_payload() -> dict:
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "analysts": [
            {
                "analyst_id": "microstructure_analyst",
                "modules": [
                    {
                        "radar_module": "btc_total_state",
                        "module_score": 0.35,
                        "module_direction": "bullish",
                        "semantic_profile_version": "p3.c41.btc_total_state.v2",
                        "price_state": {"state": "price_up", "affects_direction": True},
                        "perp_state": {
                            "state": "healthy_participation",
                            "confirmation": "confirming",
                            "risk_state": "normal",
                            "affects_direction": True,
                        },
                        "cycle_context": {
                            "state": "halving_context_only",
                            "affects_direction": False,
                        },
                        "audit_context": {
                            "state": "block_height_synced",
                            "affects_direction": False,
                        },
                        "btc_short_term_state": "price_up_confirmed",
                        "context_notes": ["halving context only"],
                        "audit_notes": ["block height audit only"],
                        "metrics": [],
                    },
                    {
                        "radar_module": "kline_orderflow",
                        "module_score": 0.2,
                        "module_direction": "bullish",
                        "module_strength": 0.2,
                        "module_confidence": 0.9,
                        "module_quality_score": 0.95,
                        "positive_metric_count": 1,
                        "negative_metric_count": 0,
                        "zero_metric_count": 0,
                        "unavailable_metric_count": 0,
                        "module_explanation": "module explanation",
                        "data_boundary": [],
                        "metrics": [
                            {
                                "evidence_id": "ev-test-1",
                                "metric_id": "btc_price",
                                "source_id": "binance",
                                "value": 100.0,
                                "metric_score": 0.2,
                                "base_metric_score": 0.2,
                                "score_bucket": "positive",
                                "direction": "bullish",
                                "base_direction": "bullish",
                                "quality_score": 0.95,
                                "semantic_rule_id": "rule",
                                "semantic_warning": "",
                                "p45_metric_brief": "metric brief",
                                "score_reason": "score reason",
                            }
                        ],
                    },
                    {
                        "radar_module": "event_policy",
                        "module_score": 0,
                        "module_direction": "neutral",
                        "semantic_profile_version": "p3.c43.event_policy.v2.1",
                        "event_short_term_state": "cpi_caution",
                        "dominant_event_type": "cpi",
                        "nearest_event_type": "cpi",
                        "nearest_event_hours": 18.0,
                        "event_window_phase": "caution",
                        "trade_gate": {
                            "allow_new_position": True,
                            "allow_add_position": False,
                            "allow_breakout_entry": False,
                            "allow_market_entry": True,
                            "position_size_multiplier": 0.7,
                            "require_wait_until_ts": None,
                            "reason_code": "PRE_CPI_24H_CAUTION",
                        },
                        "context_notes": ["Event policy is not directional alpha."],
                        "summary": "CPI caution window reduces breakout permission.",
                        "metrics": [],
                    },
                ],
            }
        ],
    }
