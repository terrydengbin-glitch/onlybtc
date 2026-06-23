from onlybtc.p45.explanations import build_metric_brief, catalog_coverage


def test_p45_metric_explanation_catalog_covers_radar_metrics() -> None:
    coverage = catalog_coverage()

    assert coverage["radar_metric_count"] > 100
    assert coverage["missing_metric_ids"] == []


def test_p45_metric_brief_includes_dynamic_context() -> None:
    brief = build_metric_brief(
        {
            "metric_id": "etf_net_flow",
            "value": -100_000_000,
            "direction": "bearish",
            "metric_score": -0.1,
            "score_bucket": "negative",
            "quality_score": 0.9,
            "semantic_rule_id": "semantic.etf_flow.absolute_negative",
            "semantic_warning": "pressure is easing but still negative",
        }
    )

    assert "美国现货 BTC ETF 单日净流" in brief
    assert "方向=bearish" in brief
    assert "semantic.etf_flow.absolute_negative" in brief
    assert "pressure is easing" in brief
