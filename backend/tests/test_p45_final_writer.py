from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID, run_p45_final_writer
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID


def test_p45_final_writer_builds_research_article(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    assert result["final_run_id"] == "final-test"
    assert result["core_view"] == "bearish"
    assert result["legacy_core_view"] == "bearish"
    assert result["final_view"] == result["decision_card"]["direction"]
    assert result["final_view"] == result["aggregation_audit"]["direction"]
    assert result["view_consistency_check"]["status"] == "passed"
    assert "BTC 多维雷达研究结论" in result["article"]
    assert "p3-score" not in result["article"]
    assert "{'bullish'" not in result["article"]
    assert result["summary"]["analyst_count"] == 4
    assert result["key_negative_evidence_ids"]
    assert result["schema_version"] == "p45.research_report.v2"
    assert result["compat_schema_version"] == "p45.final_article.v1"
    assert result["decision_card"]["direction"]
    assert result["aggregation_audit"]["score_components"]["pressure_score_abs"] > 0
    assert (
        result["aggregation_audit"]["directional_score"]
        == result["aggregation_audit"]["final_score_adjusted"]
    )
    assert set(result["horizon_views"]) == {"h24", "d3", "d7"}
    for view in result["horizon_views"].values():
        support = {item["metric_id"] for item in view["support_drivers"]}
        pressure = {item["metric_id"] for item in view["pressure_drivers"]}
        assert not support & pressure
        for side in ("support_drivers", "pressure_drivers"):
            metric_ids = [item["metric_id"] for item in view[side]]
            duplicate_groups = [
                item["duplicate_group_id"]
                for item in view[side]
                if item.get("duplicate_group_id")
            ]
            assert len(metric_ids) == len(set(metric_ids))
            assert len(duplicate_groups) == len(set(duplicate_groups))
    assert len(result["invalidation_rules"]) >= 3
    assert result["invalidation_rules"][0]["conditions"]
    assert result["confirmation_rules"]
    assert result["publish_article"]["safe_to_publish"] is True
    assert result["publish_article"]["style"] == "laoma_market_view"
    assert result["publish_article"]["style_checks"]["contains_score_number"] is False
    assert result["publish_article"]["style_checks"]["contains_english_direction"] is False
    assert "$BTC" in result["publish_article"]["body"]
    assert result["contract_validation"]["status"] == "passed"
    checks = result["contract_validation"]["checks"]
    assert checks["horizon_driver_unique_within_side"] is True
    assert checks["horizon_driver_unique_by_duplicate_group"] is True
    assert checks["has_confirmation_rules_rendered"] is True
    assert checks["llm_article_scope_declared"] is True

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID,
            )
        )

    assert row is not None


def test_horizon_bearish_direction_uses_pressure_drivers_as_dominant(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_bearish_horizon_and_large_support_driver(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    d3 = result["horizon_views"]["d3"]
    assert d3["direction"] == "bearish"
    assert d3["dominant_side"] == "pressure"
    pressure_ids = {item["metric_id"] for item in d3["pressure_drivers"]}
    dominant_ids = {item["metric_id"] for item in d3["dominant_drivers"]}
    assert dominant_ids
    assert dominant_ids.issubset(pressure_ids)
    assert result["contract_validation"]["checks"]["horizon_narrative_matches_driver_side"] is True
    assert result["contract_validation"]["status"] == "passed"


def test_p45_final_writer_preserves_fund_flow_etf_pressure_note(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_fund_flow_pressure_note(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    notes = result["pressure_notes"]
    assert notes
    assert notes[0]["module"] == "fund_flow"
    assert notes[0]["indicator"] == "etf_net_flow"
    assert notes[0]["type"] == "absolute_pressure"
    assert notes[0]["etf_pressure_easing_confirmed"] is False
    assert "资金流整体存在边际改善" in notes[0]["message"]
    assert "ETF 流出压力边际缓和" not in notes[0]["message"]
    assert result["research_article"]["pressure_notes"] == notes


def test_p45_final_writer_uses_etf_easing_phrase_only_when_metric_confirms(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_confirmed_etf_pressure_easing(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    notes = result["pressure_notes"]
    assert notes
    assert notes[0]["etf_pressure_easing_confirmed"] is True
    assert "ETF 流出压力边际缓和" in notes[0]["message"]


def test_p45_final_writer_preserves_derivatives_composite_semantics(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_derivatives_semantics(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    module = next(
        item
        for item in result["radar_module_scores"]
        if item["radar_module"] == "derivatives_crowding"
    )
    funding = next(
        item for item in result["metric_evidence"] if item["metric_id"] == "btc_funding_rate"
    )
    oi = next(
        item for item in result["metric_evidence"] if item["metric_id"] == "btc_open_interest"
    )
    contributor = module["top_contributors"][0]

    assert module["module_effective_direction"] == "neutral"
    assert module["module_effective_bias"] == "mild_support"
    assert module["crowding_state"] == "not_crowded"
    assert module["leverage_heat_state"] == "low_to_normal"
    assert module["confirmation_state"] == "unconfirmed"
    assert module["positioning_state"] == "balanced"
    assert module["top_positioning_state"] == "top_balanced"
    assert module["long_short_squeeze_risk"] == "none"
    assert module["semantic_profile_version"] == "p3.c32.derivatives_crowding.v2"
    assert funding["funding_state"] == "funding_mild"
    assert funding["crowding_signal"] == "not_hot"
    assert funding["direction_contribution"] == "mild_support"
    assert funding["trend_confirmation"] == "unconfirmed"
    assert oi["oi_state"] == "oi_flat"
    assert oi["oi_confirmation"] == "none"
    assert oi["oi_trend_signal"] == "unconfirmed"
    assert contributor["direction"] == "neutral"
    assert contributor["contribution_side"] == "positive"
    assert contributor["direction_contribution"] == "mild_support"
    ratio = next(
        item
        for item in result["metric_evidence"]
        if item["metric_id"] == "btc_top_long_short_position_ratio"
    )
    assert ratio["positioning_signal"] == "balanced"
    assert ratio["crowding_contribution"] == "neutral"
    assert ratio["positioning_scope"] == "top_position"


def test_p45_final_writer_preserves_btc_total_state_v2_layers(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_btc_total_state_v2(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    module = next(
        item for item in result["radar_module_scores"] if item["radar_module"] == "btc_total_state"
    )
    explanation = result["btc_total_state_explanation"]

    assert module["semantic_profile_version"] == "p3.c41.btc_total_state.v2"
    assert module["price_state"]["state"] == "price_up"
    assert module["perp_state"]["state"] == "healthy_participation"
    assert module["cycle_context"]["affects_direction"] is False
    assert module["audit_context"]["affects_direction"] is False
    assert explanation["btc_short_term_state"] == "price_up_confirmed"
    assert explanation["direction_drivers"] == [
        {"layer": "price_state", "state": "price_up"},
        {"layer": "perp_state", "state": "healthy_participation"},
    ]
    assert "Funding positive alone is not bullish; OI high alone is not directional." in explanation[
        "composite_only_notes"
    ]
    for view in result["horizon_views"].values():
        support = {item["metric_id"] for item in view["support_drivers"]}
        pressure = {item["metric_id"] for item in view["pressure_drivers"]}
        assert "btc_halving_estimated_days" not in support | pressure
        assert "btc_block_height" not in support | pressure


def test_p45_final_writer_preserves_event_policy_trade_gate(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_event_policy_v21(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    module = next(
        item for item in result["radar_module_scores"] if item["radar_module"] == "event_policy"
    )
    explanation = result["event_policy_explanation"]

    assert module["semantic_profile_version"] == "p3.c43.event_policy.v2.1"
    assert module["module_direction"] == "neutral"
    assert module["module_score"] == 0
    assert explanation["dominant_event_type"] == "cpi"
    assert explanation["event_window_phase"] == "caution"
    assert explanation["trade_gate"]["allow_breakout_entry"] is False
    assert explanation["trade_gate"]["position_size_multiplier"] == 0.7
    assert "CPI near therefore BTC bearish" in explanation[
        "forbidden_directional_interpretations"
    ]


def test_p45_final_writer_preserves_dollar_liquidity_v21_layers(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_dollar_liquidity_v21(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    module = next(
        item for item in result["radar_module_scores"] if item["radar_module"] == "dollar_liquidity"
    )
    explanation = result["dollar_liquidity_explanation"]

    assert module["semantic_profile_version"] == "p3.c46.dollar_liquidity.v2.1"
    assert module["dollar_liquidity_state"] == "liquidity_tailwind_confirmed"
    assert module["liquidity_impulse"]["state"] == "expansion_impulse"
    assert module["repo_funding_pressure"]["state"] == "easing"
    assert module["btc_response_confirmation"]["state"] == "absorbing_tailwind"
    assert explanation["dollar_liquidity_state"] == "liquidity_tailwind_confirmed"
    assert explanation["liquidity_level"]["rrp_depleted"] is True
    assert "SOFR high therefore BTC bearish" in explanation[
        "forbidden_directional_interpretations"
    ]


def test_p45_final_writer_preserves_fund_flow_v22_explanation_and_notes(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_fund_flow_v22(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    module = next(item for item in result["radar_module_scores"] if item["radar_module"] == "fund_flow")
    explanation = result["fund_flow_explanation"]
    rejection_note = next(item for item in result["pressure_notes"] if item.get("type") == "flow_rejection")

    assert module["semantic_profile_version"] == "p3.c50.fund_flow.v2.2"
    assert module["fund_flow_state"] == "btc_rejecting_flow_tailwind"
    assert explanation["fund_flow_state"] == "btc_rejecting_flow_tailwind"
    assert explanation["states"]["btc_response_confirmation"]["state"] == "btc_rejecting_flow_tailwind"
    assert explanation["scores"]["btc_response_score"] == -78.0
    assert "ETF inflow therefore BTC must rise." in explanation[
        "forbidden_directional_interpretations"
    ]
    assert rejection_note["state"] == "btc_rejecting_flow_tailwind"
    assert result["research_article"]["pressure_notes"] == result["pressure_notes"]


def test_p45_final_writer_preserves_trade_structure_composite_semantics(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="articles-test",
                module_id=P45_ANALYST_ARTICLES_MODULE_ID,
                schema_version="p45.analyst_articles.v1",
                payload=_analyst_payload(),
            )
        )
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack_payload_with_trade_structure_semantics(),
            )
        )

    result = run_p45_final_writer(
        article_run_id="articles-test",
        final_run_id="final-test",
        db=db,
    )

    module = next(
        item for item in result["radar_module_scores"] if item["radar_module"] == "trade_structure_flow"
    )
    price_metric = next(
        item for item in result["metric_evidence"] if item["metric_id"] == "btc_return_5m"
    )
    trade_note = next(
        item for item in result["pressure_notes"] if item["module"] == "trade_structure_flow"
    )

    assert module["trade_structure_state"] == "buy_pressure_unconfirmed"
    assert module["aggressive_flow_state"] == "strong_buying_pressure"
    assert module["price_response_state"] == "need_kline_confirmation"
    assert module["module_effective_bias"] == "mild_support"
    assert module["confirmation_state"] == "unconfirmed"
    assert price_metric["price_response_state"] == "unknown"
    assert price_metric["price_response_source"] == "5m_15m"
    assert trade_note["trade_structure_state"] == "buy_pressure_unconfirmed"
    assert "不是趋势确认" in trade_note["message"]
    assert result["contract_validation"]["checks"]["trade_structure_semantics_present"] is True


def _analyst_payload() -> dict:
    articles = [
        _article("macro_event_analyst", "bearish"),
        _article("liquidity_flow_analyst", "bearish"),
        _article("microstructure_analyst", "bullish"),
        _article("onchain_structure_analyst", "bearish"),
    ]
    return {
        "schema_version": "p45.analyst_articles.v1",
        "article_run_id": "articles-test",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "analyst_articles": articles,
    }


def _article(analyst_id: str, direction: str) -> dict:
    return {
        "analyst_id": analyst_id,
        "title": f"{analyst_id} title",
        "direction_view": direction,
        "score_summary": "summary",
        "article": "body",
        "key_positive_evidence_ids": [f"ev-{analyst_id}-pos"],
        "key_negative_evidence_ids": [f"ev-{analyst_id}-neg"],
        "neutral_watch_evidence_ids": [f"ev-{analyst_id}-zero"],
        "data_boundary": [],
    }


def _pack_payload() -> dict:
    metrics = [
        _metric("macro_radar", "dxy_proxy", -0.12, ["h24", "d3"]),
        _metric("fund_flow", "etf_flow_7d", -0.18, ["d3", "d7"]),
        _metric("kline_orderflow", "btc_1h_volume", 0.08, ["h24"]),
        _metric("onchain_valuation", "mvrv_zscore", 0.0, ["d7", "structural"]),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "macro_radar",
                        "module_score": -0.12,
                        "module_effective_score": -0.10,
                        "module_direction": "bearish",
                        "module_effective_direction": "bearish",
                        "module_quality_score": 0.9,
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_bearish_horizon_and_large_support_driver() -> dict:
    metrics = [
        _metric("fund_flow", "large_support_driver", 0.25, ["d3"]),
        *[
            _metric("treasury_credit", f"small_pressure_driver_{index}", -0.03, ["d3"])
            for index in range(20)
        ],
        _metric("kline_orderflow", "h24_context", 0.02, ["h24"]),
        _metric("onchain_valuation", "d7_context", 0.02, ["d7"]),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "treasury_credit",
                        "module_score": -0.12,
                        "module_effective_score": -0.10,
                        "module_direction": "bearish",
                        "module_effective_direction": "bearish",
                        "module_quality_score": 0.9,
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_fund_flow_pressure_note() -> dict:
    metrics = [
        _metric("fund_flow", "etf_net_flow", -0.12, ["d3"]),
        _metric("fund_flow", "etf_flow_7d", -0.18, ["d3", "d7"]),
        _metric("fund_flow", "exchange_balance_delta_1d_proxy", 0.20, ["h24", "d3"]),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "fund_flow",
                        "module_score": -0.10,
                        "module_effective_score": 0.04,
                        "module_direction": "bearish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.9,
                        "fund_flow_absolute_direction": "bearish",
                        "fund_flow_marginal_direction": "improving",
                        "fund_flow_conflict_level": "high",
                        "fund_flow_state": "bearish_but_improving",
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_confirmed_etf_pressure_easing() -> dict:
    metrics = [
        _metric(
            "fund_flow",
            "etf_net_flow",
            -0.12,
            ["d3"],
            marginal_state="pressure_easing",
            marginal_direction="improving",
        ),
        _metric("fund_flow", "etf_flow_7d", -0.18, ["d3", "d7"]),
        _metric("fund_flow", "exchange_balance_delta_1d_proxy", 0.20, ["h24", "d3"]),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "fund_flow",
                        "module_score": -0.10,
                        "module_effective_score": 0.04,
                        "module_direction": "bearish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.9,
                        "fund_flow_absolute_direction": "bearish",
                        "fund_flow_marginal_direction": "improving",
                        "fund_flow_conflict_level": "high",
                        "fund_flow_state": "bearish_but_improving",
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_fund_flow_v22() -> dict:
    profile = {
        "semantic_profile_version": "p3.c50.fund_flow.v2.2",
        "module_purpose": "fund_flow_confirmation_rejection_for_btc_trend",
        "fund_flow_state": "btc_rejecting_flow_tailwind",
        "module_direction": "bearish",
        "module_score": -0.42,
        "confidence_score": 82.0,
        "btc_implication": "internal_weakness",
        "scores": {
            "etf_demand_score": 35.0,
            "stablecoin_liquidity_score": 12.0,
            "exchange_supply_score": 0.0,
            "btc_response_score": -78.0,
            "data_quality_penalty": 0.0,
        },
        "states": {
            "etf_demand": {"state": "etf_neutral", "flow_3d_usd": 300_000_000.0},
            "stablecoin_liquidity": {"state": "stablecoin_liquidity_tailwind"},
            "exchange_supply": {"state": "exchange_supply_neutral"},
            "btc_response_confirmation": {"state": "btc_rejecting_flow_tailwind"},
        },
        "support_drivers": ["etf_demand"],
        "pressure_drivers": ["btc_rejecting_flow"],
        "early_warning_flags": ["etf_demand_fading"],
        "data_quality_flags": [],
        "summary": "fund_flow.v2.2 state=btc_rejecting_flow_tailwind.",
    }
    metrics = [
        _metric("fund_flow", "etf_flow_3d_usd", 0.0, ["d3"]),
        _metric("fund_flow", "fund_flow_residual_z_60d", 0.0, ["d7"]),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "fund_flow",
                        "module_score": -0.42,
                        "module_effective_score": -0.42,
                        "module_direction": "bearish",
                        "module_effective_direction": "bearish",
                        "module_quality_score": 0.9,
                        "module_semantic_profile": profile,
                        **profile,
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_dollar_liquidity_v21() -> dict:
    metrics = [
        _metric("dollar_liquidity", "net_liquidity_change_1w_bil", 0.0, ["d3"]),
        _metric("dollar_liquidity", "sofr_iorb_spread_bps", 0.0, ["d3"]),
        _metric("dollar_liquidity", "btc_5d_return", 0.0, ["d3"]),
    ]
    profile = {
        "semantic_profile_version": "p3.c46.dollar_liquidity.v2.1",
        "module_purpose": "confirm_or_refute_btc_trend_by_usd_liquidity_and_funding_conditions",
        "dollar_liquidity_state": "liquidity_tailwind_confirmed",
        "module_direction": "bullish",
        "module_score": 0.23,
        "risk_score": 20.0,
        "confidence_adjustment": 0.05,
        "data_freshness": {"weekly_macro_asof": "2026-05-20", "is_stale": False},
        "liquidity_level": {
            "fed_assets_bil": 6713.0,
            "tga_bil": 781.0,
            "on_rrp_bil": 0.965,
            "bank_reserves_bil": 3130.0,
            "net_liquidity_proxy_bil": 5931.0,
            "rrp_depleted": True,
        },
        "liquidity_impulse": {
            "state": "expansion_impulse",
            "net_liquidity_change_1w_bil": 75.0,
            "liquidity_impulse_z": 1.2,
        },
        "reserve_buffer": {"state": "reserves_improving", "reserve_change_1w_bil": 55.0},
        "liquidity_drain_pressure": {
            "state": "tga_drain_support",
            "tga_change_1w_bil": -60.0,
        },
        "repo_funding_pressure": {
            "state": "easing",
            "sofr_iorb_spread_bps": -14.0,
        },
        "btc_response_confirmation": {
            "state": "absorbing_tailwind",
            "btc_5d_return": 0.04,
        },
        "support_drivers": [{"layer": "liquidity_impulse", "state": "expansion_impulse"}],
        "pressure_drivers": [],
        "risk_drivers": [],
        "context_notes": ["RRP depleted limits future release buffer."],
    }
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "dollar_liquidity",
                        "module_score": 0.23,
                        "module_effective_score": 0.23,
                        "module_direction": "bullish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.9,
                        "module_semantic_profile": profile,
                        **profile,
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_derivatives_semantics() -> dict:
    metrics = [
        _metric(
            "derivatives_crowding",
            "btc_funding_rate",
            0.06,
            ["h24"],
            direction="neutral",
            score_bucket_v2="neutral_confirmed",
            funding_state="funding_mild",
            crowding_signal="not_hot",
            direction_contribution="mild_support",
            trend_confirmation="unconfirmed",
        ),
        _metric(
            "derivatives_crowding",
            "btc_open_interest",
            0.0,
            ["h24"],
            direction="neutral",
            score_bucket_v2="combo_required",
            oi_state="oi_flat",
            oi_confirmation="none",
            oi_trend_signal="unconfirmed",
        ),
        _metric(
            "derivatives_crowding",
            "btc_top_long_short_position_ratio",
            0.0,
            ["h24"],
            direction="neutral",
            score_bucket_v2="neutral_confirmed",
            positioning_signal="balanced",
            crowding_contribution="neutral",
            positioning_scope="top_position",
        ),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "derivatives_crowding",
                        "module_score": 0.06,
                        "module_effective_score": 0.054,
                        "module_direction": "neutral",
                        "module_effective_direction": "neutral",
                        "module_quality_score": 0.98,
                        "trend_direction": "neutral",
                        "trend_state": "neutral_wait_confirm",
                        "module_state": "balanced",
                        "crowding_state": "not_crowded",
                        "leverage_heat_state": "low_to_normal",
                        "module_effective_bias": "mild_support",
                        "confirmation_state": "unconfirmed",
                        "funding_state": "funding_mild",
                        "oi_state": "oi_flat",
                        "positioning_state": "balanced",
                        "top_positioning_state": "top_balanced",
                        "positioning_conflict_level": "none",
                        "long_short_squeeze_risk": "none",
                        "long_short_combo_applied": True,
                        "semantic_profile_version": "p3.c32.derivatives_crowding.v2",
                        "top_contributors": [
                            {
                                "metric_id": "btc_funding_rate",
                                "direction": "neutral",
                                "contribution_side": "positive",
                                "direction_contribution": "mild_support",
                            }
                        ],
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_trade_structure_semantics() -> dict:
    metrics = [
        _metric(
            "trade_structure_flow",
            "taker_buy_sell_ratio",
            0.08,
            ["h24"],
            direction="bullish",
        ),
        _metric(
            "trade_structure_flow",
            "btc_return_5m",
            0.0,
            ["h24"],
            price_response_state="unknown",
            price_response_confidence=0.0,
            flow_price_efficiency_state="unknown",
            price_response_source="5m_15m",
        ),
    ]
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "trade_structure_flow",
                        "module_score": 0.08,
                        "module_effective_score": 0.04,
                        "module_direction": "bullish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.96,
                        "trend_state": "neutral_wait_confirm",
                        "module_state": "balanced",
                        "trade_structure_state": "buy_pressure_unconfirmed",
                        "aggressive_flow_state": "strong_buying_pressure",
                        "price_response_state": "need_kline_confirmation",
                        "liquidation_state": "quiet",
                        "liquidation_data_quality": "snapshot_not_full_market_volume",
                        "mempool_pressure_state": "execution_friction",
                        "stablecoin_liquidity_state": "liquidity_pressure",
                        "module_effective_bias": "mild_support",
                        "confirmation_state": "unconfirmed",
                        "risk_state": "execution_friction",
                        "semantic_profile_version": "p3.c37.trade_structure_flow.v1",
                        "top_contributors": [
                            {
                                "metric_id": "taker_buy_sell_ratio",
                                "direction": "bullish",
                                "contribution_side": "positive",
                            }
                        ],
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_btc_total_state_v2() -> dict:
    metrics = [
        _metric("btc_total_state", "btc_price", 0.0, ["h24"], affects_signal=False, driver_eligible=False),
        _metric("btc_total_state", "btc_funding_rate", 0.0, ["h24"], affects_signal=False, driver_eligible=False),
        _metric("btc_total_state", "btc_open_interest", 0.0, ["h24"], affects_signal=False, driver_eligible=False),
        _metric(
            "btc_total_state",
            "btc_halving_estimated_days",
            0.2,
            ["h24", "d7"],
            affects_signal=False,
            driver_eligible=False,
        ),
        _metric(
            "btc_total_state",
            "btc_block_height",
            -0.2,
            ["h24", "d7"],
            affects_signal=False,
            driver_eligible=False,
        ),
    ]
    profile = {
        "semantic_profile_version": "p3.c41.btc_total_state.v2",
        "direction_driver_scope": ["price_state", "perp_state"],
        "context_only_scope": ["cycle_context", "audit_context"],
        "price_state": {"state": "price_up", "strength": "normal", "affects_direction": True},
        "perp_state": {
            "state": "healthy_participation",
            "confirmation": "confirming",
            "risk_state": "normal",
            "affects_direction": True,
        },
        "cycle_context": {"state": "halving_context_only", "affects_direction": False},
        "audit_context": {"state": "block_height_synced", "affects_direction": False},
        "btc_short_term_state": "price_up_confirmed",
        "context_notes": ["halving context only"],
        "audit_notes": ["block height audit only"],
        "support_drivers": [{"driver_type": "composite", "state": "price_up_confirmed"}],
        "pressure_drivers": [{"metric_id": "btc_block_height", "state": "wrong"}],
    }
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "test_analyst",
                "modules": [
                    {
                        "radar_module": "btc_total_state",
                        "module_score": 0.35,
                        "module_effective_score": 0.35,
                        "module_direction": "bullish",
                        "module_effective_direction": "bullish",
                        "module_quality_score": 0.96,
                        "semantic_profile_version": "p3.c41.btc_total_state.v2",
                        **profile,
                        "module_semantic_profile": profile,
                        "metrics": metrics,
                    }
                ],
            }
        ],
    }


def _pack_payload_with_event_policy_v21() -> dict:
    profile = {
        "semantic_profile_version": "p3.c43.event_policy.v2.1",
        "module_purpose": "event_risk_and_trade_permission",
        "module_direction": "neutral",
        "module_score": 0,
        "module_effective_score": 0,
        "dominant_event_type": "cpi",
        "nearest_event_type": "cpi",
        "nearest_event_hours": 18.0,
        "event_window_phase": "caution",
        "event_short_term_state": "cpi_caution",
        "event_risk_lock_level": "soft",
        "penalty_channel": "event_timing_only",
        "risk_score": 65.0,
        "confidence_adjustment": -0.06,
        "trade_gate": {
            "allow_new_position": True,
            "allow_add_position": False,
            "allow_breakout_entry": False,
            "allow_market_entry": True,
            "position_size_multiplier": 0.7,
            "require_wait_until_ts": None,
            "reason_code": "PRE_CPI_24H_CAUTION",
        },
        "risk_drivers": [{"event_type": "cpi", "phase": "caution"}],
        "context_notes": ["Event policy is not directional alpha."],
        "summary": "CPI caution window reduces breakout permission.",
    }
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "analysts": [
            {
                "analyst_id": "macro_event_analyst",
                "modules": [
                    {
                        "radar_module": "event_policy",
                        "module_score": 0,
                        "module_effective_score": 0,
                        "module_direction": "neutral",
                        "module_effective_direction": "neutral",
                        "module_quality_score": 0.96,
                        "semantic_profile_version": "p3.c43.event_policy.v2.1",
                        **profile,
                        "module_semantic_profile": profile,
                        "metrics": [
                            _metric(
                                "event_policy",
                                "cpi_hours_until",
                                0.0,
                                ["h24"],
                                affects_signal=False,
                                driver_eligible=False,
                            )
                        ],
                    }
                ],
            }
        ],
    }


def _metric(
    module_id: str,
    metric_id: str,
    score: float,
    horizons: list[str],
    **extra: object,
) -> dict:
    payload = {
        "evidence_id": f"ev-{metric_id}",
        "radar_module": module_id,
        "metric_id": metric_id,
        "metric_score": score,
        "metric_effective_score": score * 0.9,
        "score_bucket": "negative" if score < 0 else "positive" if score > 0 else "zero",
        "direction": "bearish" if score < 0 else "bullish" if score > 0 else "neutral",
        "quality_score": 0.9,
        "horizon_tags": horizons,
        "module_weight": 0.1,
        "freshness_minutes": 12,
        "p45_metric_brief": f"{metric_id} brief",
        "available": True,
    }
    payload.update(extra)
    return payload
