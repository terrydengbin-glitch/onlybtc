from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from onlybtc.api import p45_dashboard, p45_jobs
from onlybtc.api.radar_runtime import cockpit_latest
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.direct_trend.replay import save_timescale_judge_snapshot


def test_p45_dashboard_bundle_exposes_final_view_and_lineage(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    result = p45_dashboard.latest_dashboard(db=db)

    assert result["status"] == "ok"
    assert result["api_schema_version"] == "onlybtc.api.v1"
    assert result["schema_version"] == "p45.dashboard.v1"
    assert result["final_view"] == "neutral"
    assert result["run_lineage"]["final_run_id"] == "final-test"
    assert result["run_lineage"]["pack_id"] == "pack-test"
    assert result["radar_module_count"] == 3
    assert result["metric_evidence_count"] == 6
    assert result["contract_validation"]["status"] == "passed"
    assert result["pressure_notes"] == [
        {
            "module": "fund_flow",
            "indicator": "etf_net_flow",
            "type": "absolute_pressure",
            "severity": "medium",
            "message": "ETF still has absolute outflow pressure.",
            "etf_pressure_easing_confirmed": False,
        }
    ]
    assert result["llm"]["provider"] == "deepseek"
    assert result["llm"]["analyst_completed_count"] == 4

    overview = p45_dashboard.latest_overview(db=db)
    assert overview["status"] == "ok"
    assert overview["pressure_notes"] == result["pressure_notes"]
    assert overview["why_not_strong"] == ["zero score metrics remain high"]
    assert overview["score_normalization"]["normalization_base"] == "abs_support_pressure"
    assert overview["support_drivers"][0]["module"] == "macro_radar"
    assert overview["pressure_drivers"][0]["module"] == "fund_flow"
    assert overview["dominant_drivers"][0]["module"] == "macro_radar"
    assert overview["watch_rules"][0]["rule_id"] == "watch-fund-flow"
    assert overview["conflicting_evidence"]["state"] == "mixed"
    assert overview["confidence_explanation"]["level"] == "medium"


def test_p45_dashboard_does_not_leak_stale_llm_lineage(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    _seed_newer_p45_payload(db)

    result = p45_dashboard.latest_dashboard(db=db)

    assert result["status"] == "ok"
    assert result["run_lineage"]["final_run_id"] == "final-new"
    assert result["run_lineage"]["pack_id"] == "pack-new"
    assert result["run_lineage"]["llm_research_run_id"] is None
    assert result["run_lineage"]["llm_analyst_run_id"] is None
    assert result["llm"]["research_run_id"] is None
    assert result["llm"]["analyst_run_id"] is None
    assert result["pressure_notes"] == []


def test_p45_evidence_and_module_filters_use_scored_payload(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    evidence = p45_dashboard.latest_evidence(module_id="macro_radar", db=db)
    detail = p45_dashboard.evidence_detail("p3-score-p3-old-macro_radar-ofr_fsi", db=db)
    module = p45_dashboard.radar_module_detail("macro_radar", db=db)

    assert evidence["count"] == 2
    item = evidence["items"][0]
    assert item["metric_score"] == 0.1
    assert item["metric_effective_score"] == 0.08
    assert item["freshness_weight"] == 0.9
    assert item["horizon_weight"] == 1.0
    assert item["duplicate_adjustment"] == 0.0
    assert item["horizon_tags"] == ["24h", "3d"]
    assert item["duplicate_group_id"] == "macro-risk"
    assert item["source_ts"] == "2026-05-22T00:00:00+00:00"
    assert item["collected_at"] == "2026-05-22T00:02:00+00:00"
    assert item["freshness_minutes"] == 2
    assert item["is_stale"] is False
    assert item["p45_metric_brief"] == "OFR stress is contained."
    assert item["score_reason"] == "OFR stress supports risk appetite."
    assert detail is not None
    assert detail["evidence"]["metric_id"] == "ofr_fsi"
    assert detail["claim"]["brief"] == "OFR stress is contained."
    assert detail["data"]["source_ts"] == "2026-05-22T00:00:00+00:00"
    assert detail["interpretation"]["metric_effective_score"] == 0.08
    assert module is not None
    assert module["module"]["module_effective_direction"] == "bullish"
    assert module["summary"]["module_id"] == "macro_radar"
    assert module["summary"]["score"] == 0.12
    assert module["summary"]["confidence"] == 0.7
    assert module["support_drivers"][0]["metric_id"] == "ofr_fsi"
    assert module["pressure_drivers"][0]["metric_id"] == "vix"
    assert module["source_freshness"]["source_ids"] == ["ofr-source"]
    assert module["source_freshness"]["fresh_count"] == 1
    assert module["weighting"]["freshness_weights"]["ofr_fsi"] == 0.9
    assert module["weighting"]["horizon_tags"]["ofr_fsi"] == ["24h", "3d"]
    assert module["p2_radar_output"]["run_id"] == "radar-test"
    assert module["p2_radar_output"]["module_id"] == "macro_radar"
    assert module["module_json"]["radar_module"] == "macro_radar"
    assert [item["metric_id"] for item in module["metrics"]] == ["ofr_fsi", "vix"]


def test_p45_articles_latest_exposes_article_and_appendix_metadata(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    result = p45_dashboard.latest_articles(db=db)

    assert result["status"] == "ok"
    assert result["schema_version"] == "p45.articles.v1"
    assert result["run_lineage"]["final_run_id"] == "final-test"
    assert result["decision_card"]["direction"] == "neutral"
    assert result["contract_validation"]["status"] == "passed"
    assert result["data_quality"]["metric_count"] == 2
    assert result["research_article"]["title"] == "研究正文"
    assert result["publish_article"]["body"] == "$BTC 中性观察"
    assert result["llm_research_metadata"]["llm_research_run_id"] == "research-test"
    assert result["llm_research_metadata"]["provider"] == "deepseek"
    assert result["deterministic_analyst_metadata"]["article_run_id"] == "articles-test"
    assert result["deterministic_analyst_metadata"]["analyst_count"] == 1
    assert result["llm_analyst_metadata"]["llm_analyst_run_id"] == "llm-analysts-test"
    assert result["llm_analyst_metadata"]["completed_count"] == 4


def test_p45_alerts_and_invalidation_project_p9_c05_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    alerts = p45_dashboard.latest_alerts(db=db)
    invalidation = p45_dashboard.latest_invalidation(db=db)

    assert alerts["status"] == "ok"
    assert alerts["schema_version"] == "p3.alerts.v1"
    assert alerts["count"] == 1
    alert = alerts["alerts"][0]
    assert alert["alert_id"] == "alert-p9-c05"
    assert alert["supporting_evidence"] == []
    assert alert["conflicting_evidence"] == []
    assert alert["escalation_conditions"][0]["rule_id"] == "confirm-1"
    assert alert["downgrade_conditions"][0]["rule_id"] == "inv-1"
    assert alert["invalidation_context"]["invalidation_rules"][0]["expression"] == (
        "btc_price < 65000"
    )

    assert invalidation["schema_version"] == "p45.invalidation.v1"
    rule = invalidation["invalidation_rules"][0]
    assert rule["rule_kind"] == "invalidation"
    assert rule["expression"] == "btc_price < 65000"
    assert rule["action_if_triggered"] == "reduce_confidence_or_flip_to_watch"
    assert rule["applies_when"] == "neutral_watch"
    assert rule["horizon"] == "24h"
    assert rule["module_id"] == "kline_orderflow"
    assert rule["metric_ids"] == ["btc_price"]
    assert rule["evidence_ids"] == ["ev-kline-close-position"]
    assert rule["threshold"] == 65000
    assert rule["current_value"] == 66000
    assert rule["distance_to_trigger"] == 1000
    confirmation = invalidation["confirmation_rules"][0]
    assert confirmation["rule_kind"] == "confirmation"
    assert confirmation["action_if_triggered"] == "upgrade_confidence"


def test_options_rv_legacy_future_source_ts_is_display_marked() -> None:
    item = p45_dashboard._annotate_legacy_future_source_ts(
        {
            "metric_id": "options_rv",
            "source_ts": "2026-05-25T23:59:59.999000+00:00",
            "collected_at": "2026-05-25T11:04:13.983099+00:00",
            "available": True,
            "is_stale": False,
        }
    )

    assert item["legacy_future_source_ts"] is True
    assert item["freshness_display_status"] == "legacy_stale_future_source_ts"
    assert item["available"] is False
    assert item["is_stale"] is True


def test_p45_radar_module_detail_exposes_composite_semantics(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    dashboard = p45_dashboard.latest_dashboard(db=db)
    module = p45_dashboard.radar_module_detail("derivatives_crowding", db=db)

    assert dashboard["status"] == "ok"
    assert module is not None
    derivatives_summary = next(
        item
        for item in dashboard["radar_modules"]
        if item["radar_module"] == "derivatives_crowding"
    )
    funding = next(item for item in module["metrics"] if item["metric_id"] == "btc_funding_rate")
    oi = next(item for item in module["metrics"] if item["metric_id"] == "btc_open_interest")
    contributor = module["module"]["top_contributors"][0]

    assert derivatives_summary["module_effective_bias"] == "mild_support"
    assert derivatives_summary["crowding_state"] == "not_crowded"
    assert derivatives_summary["leverage_heat_state"] == "low_to_normal"
    assert derivatives_summary["positioning_state"] == "balanced"
    assert derivatives_summary["top_positioning_state"] == "top_balanced"
    assert derivatives_summary["long_short_squeeze_risk"] == "none"
    assert module["module"]["confirmation_state"] == "unconfirmed"
    assert module["module"]["semantic_profile_version"] == "p3.c32.derivatives_crowding.v2"
    assert funding["direction"] == "neutral"
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
        for item in module["metrics"]
        if item["metric_id"] == "btc_top_long_short_position_ratio"
    )
    assert ratio["positioning_signal"] == "balanced"
    assert ratio["crowding_contribution"] == "neutral"
    assert ratio["positioning_scope"] == "top_position"


def test_p45_radar_module_detail_projects_btc_total_state_v2_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "btc_total_state",
                "module_direction": "bullish",
                "module_score": 0.35,
                "module_semantic_profile": {
                    "semantic_profile_version": "p3.c41.btc_total_state.v2",
                    "direction_driver_scope": ["price_state", "perp_state"],
                    "context_only_scope": ["cycle_context", "audit_context"],
                    "price_state": {"state": "price_up", "affects_direction": True},
                    "perp_state": {
                        "state": "healthy_participation",
                        "confirmation": "confirming",
                        "risk_state": "normal",
                        "affects_direction": True,
                    },
                    "cycle_context": {"state": "halving_context_only", "affects_direction": False},
                    "audit_context": {"state": "block_height_synced", "affects_direction": False},
                    "btc_short_term_state": "price_up_confirmed",
                    "context_notes": ["halving_context_only"],
                    "audit_notes": ["block_height_synced"],
                    "support_drivers": [{"driver_type": "composite", "state": "price_up_confirmed"}],
                    "pressure_drivers": [{"metric_id": "btc_block_height", "state": "wrong"}],
                },
            }
        ]
        payload["metric_evidence"] = list(payload["metric_evidence"]) + [
            {
                "evidence_id": "ev-btc-halving",
                "radar_module": "btc_total_state",
                "metric_id": "btc_halving_estimated_days",
                "metric_effective_score": 0.0,
                "driver_eligible": False,
            },
            {
                "evidence_id": "ev-btc-block",
                "radar_module": "btc_total_state",
                "metric_id": "btc_block_height",
                "metric_effective_score": 0.0,
                "driver_eligible": False,
            },
        ]
        row.payload = payload

    dashboard = p45_dashboard.latest_dashboard(db=db)
    detail = p45_dashboard.radar_module_detail("btc_total_state", db=db)

    assert detail is not None
    summary = next(
        item for item in dashboard["radar_modules"] if item["radar_module"] == "btc_total_state"
    )
    contract = detail["module"]["btc_total_state_v2"]
    assert summary["btc_short_term_state"] == "price_up_confirmed"
    assert detail["module"]["display_state"] == "price_up_confirmed"
    assert "perp participation" in detail["module"]["display_summary"]
    assert contract["price_state"]["state"] == "price_up"
    assert contract["perp_state"]["state"] == "healthy_participation"
    assert contract["cycle_context"]["affects_direction"] is False
    assert contract["audit_context"]["affects_direction"] is False
    assert contract["pressure_drivers"] == []
    assert [item["metric_id"] for item in detail["metrics"]] == [
        "btc_halving_estimated_days",
        "btc_block_height",
    ]


def test_p45_radar_module_detail_keeps_btc_total_v1_compatible(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "btc_total_state",
                "module_direction": "neutral",
                "semantic_profile_version": "p3.c27.btc_total_state.v1",
            }
        ]
        row.payload = payload

    detail = p45_dashboard.radar_module_detail("btc_total_state", db=db)

    assert detail is not None
    contract = detail["module"]["btc_total_state_v2"]
    assert contract["semantic_profile_version"] == "p3.c27.btc_total_state.v1"
    assert contract["price_state"] is None
    assert contract["perp_state"] is None
    assert contract["btc_short_term_state"] is None


def test_p45_radar_module_detail_projects_options_volatility_v21_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    profile = {
        "semantic_profile_version": "p3.c42.options_volatility.v2.1",
        "module_purpose": "volatility_risk_and_expiry_structure",
        "options_short_term_state": "downside_protection_bid",
        "module_direction": "neutral",
        "module_score": 0,
        "module_effective_score": 0,
        "risk_score": 72.0,
        "confidence_adjustment": -0.1,
        "trade_permission_hint": "avoid_chasing",
        "volatility_regime": {"state": "iv_over_rv"},
        "protection_demand": {"state": "downside_protection_bid"},
        "tail_risk": {"state": "downside_tail_risk"},
        "expiry_pressure": {"state": "expiry_normal"},
        "pinning_structure": {"state": "structure_neutral"},
        "data_quality": {"state": "usable"},
        "risk_drivers": [{"driver_type": "protection_demand", "state": "downside_protection_bid"}],
        "context_notes": ["not directional alpha"],
    }
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "options_volatility",
                "module_direction": "bearish",
                "module_score": -0.3,
                "module_semantic_profile": profile,
                "support_drivers": [{"metric_id": "put_call_ratio", "state": "wrong"}],
                "pressure_drivers": [{"metric_id": "options_skew", "state": "wrong"}],
            }
        ]
        payload["metric_evidence"] = list(payload["metric_evidence"]) + [
            {
                "evidence_id": "ev-options-pcr",
                "radar_module": "options_volatility",
                "metric_id": "put_call_ratio",
                "metric_effective_score": 0.0,
                "driver_eligible": False,
            }
        ]
        row.payload = payload

    detail = p45_dashboard.radar_module_detail("options_volatility", db=db)

    assert detail is not None
    module = detail["module"]
    contract = module["options_volatility_v21"]
    assert module["module_direction"] == "neutral"
    assert module["module_score"] == 0
    assert module["module_effective_score"] == 0
    assert module["support_drivers"] == []
    assert module["pressure_drivers"] == []
    assert contract["options_short_term_state"] == "downside_protection_bid"
    assert contract["trade_permission_hint"] == "avoid_chasing"
    assert contract["protection_demand"]["state"] == "downside_protection_bid"


def test_p45_radar_module_detail_projects_event_policy_v21_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    profile = {
        "semantic_profile_version": "p3.c43.event_policy.v2.1",
        "module_purpose": "event_risk_and_trade_permission",
        "module_direction": "neutral",
        "module_score": 0,
        "module_effective_score": 0,
        "dominant_event_type": "cpi",
        "nearest_event_type": "fed_speech",
        "nearest_event_hours": 2.5,
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
        "context_notes": ["not directional alpha"],
    }
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "event_policy",
                "module_direction": "bearish",
                "module_score": -0.4,
                "module_semantic_profile": profile,
                "support_drivers": [{"metric_id": "cpi_days_until"}],
                "pressure_drivers": [{"metric_id": "fomc_days_until"}],
            }
        ]
        row.payload = payload

    detail = p45_dashboard.radar_module_detail("event_policy", db=db)

    assert detail is not None
    module = detail["module"]
    contract = module["event_policy_v21"]
    assert module["module_direction"] == "neutral"
    assert module["module_score"] == 0
    assert module["module_effective_score"] == 0
    assert module["support_drivers"] == []
    assert module["pressure_drivers"] == []
    assert contract["event_window_phase"] == "caution"
    assert contract["trade_gate"]["allow_breakout_entry"] is False
    assert contract["trade_gate"]["reason_code"] == "PRE_CPI_24H_CAUTION"


def test_p45_radar_module_detail_projects_dollar_liquidity_v21_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    profile = {
        "semantic_profile_version": "p3.c46.dollar_liquidity.v2.1",
        "module_purpose": "confirm_or_refute_btc_trend_by_usd_liquidity_and_funding_conditions",
        "module_direction": "bullish",
        "module_score": 0.23,
        "module_effective_score": 0.23,
        "risk_score": 20.0,
        "confidence_score": 0.05,
        "dollar_liquidity_state": "liquidity_tailwind_confirmed",
        "data_freshness": {"weekly_macro_asof": "2026-05-20", "is_stale": False},
        "liquidity_level": {"net_liquidity_proxy_bil": 5931.0, "rrp_depleted": True},
        "liquidity_impulse": {"state": "expansion_impulse", "net_liquidity_change_1w_bil": 75.0},
        "reserve_buffer": {"state": "reserves_improving", "reserve_change_1w_bil": 55.0},
        "liquidity_drain_pressure": {"state": "tga_drain_support", "tga_change_1w_bil": -60.0},
        "repo_funding_pressure": {"state": "easing", "sofr_iorb_spread_bps": -14.0},
        "btc_response_confirmation": {"state": "absorbing_tailwind", "btc_5d_return": 0.04},
        "support_drivers": [{"layer": "liquidity_impulse", "state": "expansion_impulse"}],
        "pressure_drivers": [],
        "risk_drivers": [],
        "context_notes": ["RRP depleted limits future release buffer."],
    }
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "dollar_liquidity",
                "module_direction": "bearish",
                "module_score": -0.4,
                "module_semantic_profile": profile,
                "support_drivers": [{"metric_id": "fed_balance_sheet"}],
                "pressure_drivers": [{"metric_id": "sofr"}],
            }
        ]
        row.payload = payload

    dashboard = p45_dashboard.latest_dashboard(db=db)
    detail = p45_dashboard.radar_module_detail("dollar_liquidity", db=db)

    assert detail is not None
    module = detail["module"]
    contract = module["dollar_liquidity_v21"]
    summary = next(item for item in dashboard["radar_modules"] if item["radar_module"] == "dollar_liquidity")
    assert module["module_direction"] == "bullish"
    assert module["module_score"] == 0.23
    assert module["module_effective_score"] == 0.23
    assert module["dollar_liquidity_state"] == "liquidity_tailwind_confirmed"
    assert summary["dollar_liquidity_state"] == "liquidity_tailwind_confirmed"
    assert contract["repo_funding_pressure"]["state"] == "easing"
    assert contract["btc_response_confirmation"]["state"] == "absorbing_tailwind"


def test_p45_radar_module_detail_projects_treasury_credit_v21_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    profile = {
        "semantic_profile_version": "p3.c47.treasury_credit.v2.1",
        "module_purpose": "btc_trend_confirmation_by_rates_curve_and_credit_stress",
        "treasury_credit_state": "credit_widening_warning",
        "module_direction": "neutral",
        "module_score": -0.12,
        "module_effective_score": -0.12,
        "risk_score": 72.0,
        "btc_implication": "trend_fragile",
        "states": {
            "policy_rate_pressure": {"state": "policy_neutral", "basis": {}},
            "real_yield_pressure": {"state": "real_yield_neutral", "basis": {}},
            "duration_term_pressure": {"state": "duration_neutral", "basis": {}},
            "curve_regime": {"state": "curve_neutral", "basis": {}},
            "inflation_mix": {"state": "inflation_neutral", "basis": {}},
            "credit_stress": {"state": "credit_widening_warning", "basis": {"hy_oas_change_5d_bps": 18.0}},
            "btc_response_confirmation": {"state": "btc_credit_neutral", "basis": {}},
        },
        "early_warning_flags": ["credit_widening_warning"],
        "data_quality_flags": [],
    }
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "treasury_credit",
                "module_direction": "bearish",
                "module_score": -0.4,
                "module_semantic_profile": profile,
            }
        ]
        row.payload = payload

    dashboard = p45_dashboard.latest_dashboard(db=db)
    detail = p45_dashboard.radar_module_detail("treasury_credit", db=db)

    assert detail is not None
    module = detail["module"]
    contract = module["treasury_credit_v21"]
    summary = next(item for item in dashboard["radar_modules"] if item["radar_module"] == "treasury_credit")
    assert module["module_direction"] == "neutral"
    assert module["module_score"] == -0.12
    assert module["treasury_credit_state"] == "credit_widening_warning"
    assert summary["treasury_credit_state"] == "credit_widening_warning"
    assert contract["states"]["credit_stress"]["state"] == "credit_widening_warning"


def test_p45_radar_module_detail_projects_fund_flow_v22_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    profile = {
        "semantic_profile_version": "p3.c50.fund_flow.v2.2",
        "module_purpose": "fund_flow_confirmation_rejection_for_btc_trend",
        "fund_flow_state": "btc_rejecting_flow_tailwind",
        "module_direction": "bearish",
        "module_score": -0.42,
        "module_effective_score": -0.42,
        "risk_score": 72.0,
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
        "early_warning_flags": ["etf_demand_fading"],
        "data_quality_flags": [],
    }
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = [
            (
                {
                    "radar_module": "fund_flow",
                    "module_direction": "neutral",
                    "module_score": 0.0,
                    "module_semantic_profile": profile,
                }
                if item.get("radar_module") == "fund_flow"
                else item
            )
            for item in payload["radar_module_scores"]
        ]
        if not any(item.get("radar_module") == "fund_flow" for item in payload["radar_module_scores"]):
            payload["radar_module_scores"].append(
                {
                "radar_module": "fund_flow",
                "module_direction": "neutral",
                "module_score": 0.0,
                "module_semantic_profile": profile,
                }
            )
        row.payload = payload

    dashboard = p45_dashboard.latest_dashboard(db=db)
    detail = p45_dashboard.radar_module_detail("fund_flow", db=db)

    assert detail is not None
    module = detail["module"]
    contract = module["fund_flow_v22"]
    summary = next(item for item in dashboard["radar_modules"] if item["radar_module"] == "fund_flow")
    assert module["module_direction"] == "bearish"
    assert module["module_score"] == -0.42
    assert module["fund_flow_state"] == "btc_rejecting_flow_tailwind"
    assert summary["fund_flow_state"] == "btc_rejecting_flow_tailwind"
    assert contract["states"]["btc_response_confirmation"]["state"] == "btc_rejecting_flow_tailwind"
    assert contract["scores"]["btc_response_score"] == -78.0


def test_p45_radar_module_detail_projects_macro_relative_confirmation_reason(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    profile = {
        "semantic_profile_version": "p3.c45.macro_radar.v3",
        "module_purpose": "btc_macro_trend_confirmation_and_refutation",
        "macro_trend_state": "macro_mixed",
        "module_direction": "neutral",
        "module_score": 0.0,
        "module_effective_score": 0.0,
        "btc_implication": "wait_for_confirmation",
        "summary": "macro_radar.v3 state=macro_mixed; environment=0.000, impulse=no_impulse, BTC relative=missing.",
        "btc_relative_confirmation": {
            "state": "missing",
            "score": 0.0,
            "missing_reason": "btc_relative_basis_missing;btc_return_missing;equity_return_missing",
            "btc_beta_residual": None,
            "basis": {
                "btc_return_24h_pct": 0.0,
                "btc_vs_ndx_relative_return": None,
                "btc_vs_spx_relative_return": None,
            },
        },
    }
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = [
            (
                {
                    "radar_module": "macro_radar",
                    "module_direction": "bullish",
                    "module_score": 0.4,
                    "module_semantic_profile": profile,
                }
                if item.get("radar_module") == "macro_radar"
                else item
            )
            for item in payload["radar_module_scores"]
        ]
        row.payload = payload

    dashboard = p45_dashboard.latest_dashboard(db=db)
    detail = p45_dashboard.radar_module_detail("macro_radar", db=db)

    assert detail is not None
    summary = next(item for item in dashboard["radar_modules"] if item["radar_module"] == "macro_radar")
    confirmation = detail["module"]["macro_radar_v3"]["btc_relative_confirmation"]
    assert detail["module"]["macro_trend_state"] == "macro_mixed"
    assert summary["macro_trend_state"] == "macro_mixed"
    assert confirmation["state"] == "missing"
    assert "btc_relative_basis_missing" in confirmation["missing_reason"]


def test_p45_radar_module_detail_projects_kline_display_fields(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    dashboard = p45_dashboard.latest_dashboard(db=db)
    detail = p45_dashboard.radar_module_detail("kline_orderflow", db=db)

    assert detail is not None
    summary = next(
        item
        for item in dashboard["radar_modules"]
        if item["radar_module"] == "kline_orderflow"
    )
    assert detail["module"]["module_effective_bias"] == "mild_pressure"
    assert detail["module"]["display_state"] == "neutral_wait_confirm"
    assert "pressure exists" in detail["module"]["display_summary"]
    assert detail["module"]["top_kline_reason"] == "close position sits near the low"
    assert summary["display_state"] == detail["module"]["display_state"]
    assert summary["display_summary"] == detail["module"]["display_summary"]


def test_p45_dashboard_api_projects_trade_structure_semantics(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "trade_structure_flow",
                "module_direction": "bullish",
                "module_effective_direction": "bullish",
                "trade_structure_state": "buy_pressure_unconfirmed",
                "aggressive_flow_state": "strong_buying_pressure",
                "price_response_state": "need_kline_confirmation",
                "liquidation_state": "quiet",
                "mempool_pressure_state": "execution_friction",
                "stablecoin_liquidity_state": "liquidity_pressure",
                "module_effective_bias": "mild_support",
                "confirmation_state": "unconfirmed",
                "risk_state": "execution_friction",
            }
        ]
        payload["metric_evidence"] = list(payload["metric_evidence"]) + [
            {
                "evidence_id": "ev-trade-price-response",
                "radar_module": "trade_structure_flow",
                "metric_id": "btc_return_5m",
                "metric_effective_score": 0.0,
                "direction": "neutral",
                "price_response_state": "unknown",
                "price_response_confidence": 0.0,
                "flow_price_efficiency_state": "unknown",
                "price_response_source": "5m_15m",
            }
        ]
        row.payload = payload

    dashboard = p45_dashboard.latest_dashboard(db=db)
    detail = p45_dashboard.radar_module_detail("trade_structure_flow", db=db)
    evidence = p45_dashboard.evidence_detail("ev-trade-price-response", db=db)

    trade_summary = next(
        item for item in dashboard["radar_modules"] if item["radar_module"] == "trade_structure_flow"
    )
    assert detail is not None
    assert evidence is not None
    assert trade_summary["trade_structure_state"] == "buy_pressure_unconfirmed"
    assert trade_summary["trade_structure_summary"] == "主动买盘强但价格响应未确认。"
    assert detail["module"]["price_response_state"] == "need_kline_confirmation"
    assert detail["module"]["module_direction"] == "bullish"
    assert detail["metrics"][0]["price_response_state"] == "unknown"
    assert evidence["evidence"]["price_response_source"] == "5m_15m"


def test_data_quality_source_health_failed_count_filters_healthy_runs(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        session.add_all(
            [
                schema.Source(
                    source_id="healthy-source",
                    name="Healthy Source",
                    group_name="test",
                    method="api",
                    status="healthy",
                ),
                schema.Source(
                    source_id="failed-source",
                    name="Failed Source",
                    group_name="test",
                    method="api",
                    status="healthy",
                ),
                schema.SourceRun(
                    run_id="collect-test",
                    source_id="healthy-source",
                    mode="live",
                    status="healthy",
                    error_message=None,
                ),
                schema.SourceRun(
                    run_id="collect-test",
                    source_id="failed-source",
                    mode="live",
                    status="failed",
                    error_message="timeout",
                ),
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="healthy-source",
                    run_id="collect-test",
                    run_mode="live",
                    ts=datetime(2026, 5, 22, tzinfo=UTC),
                    timeframe="latest",
                    is_fallback=False,
                    value=100.0,
                    quality_score=1.0,
                ),
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="failed-source",
                    run_id="collect-old",
                    run_mode="mock",
                    ts=datetime(2026, 5, 21, tzinfo=UTC),
                    timeframe="latest",
                    is_fallback=False,
                    value=99.0,
                    quality_score=1.0,
                ),
            ]
        )

    result = p45_dashboard.latest_data_quality(db=db)
    source_health = result["source_health"]

    assert source_health["recent_run_count"] == 2
    assert source_health["recent_failed_run_count"] == 1
    assert source_health["recent_failed_sources"] == [
        {
            "source_id": "failed-source",
            "run_id": "collect-test",
            "mode": "live",
            "status": "failed",
            "error_message": "timeout",
        }
    ]
    run_mode_integrity = result["run_mode_integrity"]
    assert run_mode_integrity["current_run"]["live_only"] is True
    assert run_mode_integrity["production_blocker"] is False
    assert run_mode_integrity["history"]["status"] == "warning"
    assert run_mode_integrity["default_query_scope"] == "live_only"


def test_data_quality_and_source_detail_project_p9_c06_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        session.add(
            schema.Source(
                source_id="p9-c06-source",
                name="P9 C06 Source",
                group_name="test",
                method="api",
                status="healthy",
                fallback_source_id="p9-c06-fallback",
                metadata_json={"cadence": "5m"},
            )
        )
        session.flush()
        session.add_all(
            [
                schema.SourceRun(
                    run_id="collect-test",
                    source_id="p9-c06-source",
                    mode="live",
                    status="healthy",
                    latency_ms=123,
                ),
                schema.RawObservation(
                    source_id="p9-c06-source",
                    run_id="collect-test",
                    mode="live",
                    observed_at=datetime(2026, 5, 22, tzinfo=UTC),
                    raw_payload={
                        "status": "ok",
                        "api_key": "secret-key",
                        "nested": {"authorization": "Bearer secret"},
                    },
                    payload_hash="hash-p9-c06",
                ),
                schema.MetricValue(
                    metric_id="btc_price",
                    source_id="p9-c06-source",
                    run_id="collect-test",
                    run_mode="live",
                    ts=datetime(2026, 5, 22, tzinfo=UTC),
                    timeframe="latest",
                    is_fallback=False,
                    value=100.0,
                    quality_score=0.98,
                ),
                schema.DataQualitySnapshot(
                    run_id="collect-test",
                    score=0.91,
                    status="warning",
                    payload={"confidence_cap": 0.8},
                ),
                schema.SourceHealthEvent(
                    source_id="p9-c06-source",
                    status="healthy",
                    quality_score=0.98,
                    latency_ms=123,
                    message="ok",
                ),
                schema.FallbackEvent(
                    source_id="p9-c06-source",
                    fallback_source_id="p9-c06-fallback",
                    reason="primary_timeout",
                    discount=0.2,
                ),
                schema.RateLimitEvent(
                    source_id="p9-c06-source",
                    current=9,
                    limit=10,
                ),
                schema.ModuleDiscount(
                    module_id="macro_radar",
                    reason="fallback_used",
                    discount=0.1,
                    source_id="p9-c06-source",
                ),
            ]
        )

    quality = p45_dashboard.latest_data_quality(db=db)
    detail = p45_dashboard.source_detail("p9-c06-source", db=db)

    assert quality["schema_version"] == "p45.data_quality.v1"
    assert quality["data_quality_snapshot"]["score"] == 0.91
    assert quality["quality_boundary"]["p1"]["fallback_event_count"] == 1
    assert quality["quality_boundary"]["p1"]["rate_limit_event_count"] == 1
    assert quality["quality_boundary"]["p2"]["module_discount_count"] == 1
    assert quality["fallback_events"][0]["reason"] == "primary_timeout"
    assert quality["rate_limit_events"][0]["current"] == 9
    assert quality["module_discounts"][0]["module_id"] == "macro_radar"

    assert detail is not None
    assert detail["schema_version"] == "p45.source_detail.v1"
    assert detail["source"]["source_id"] == "p9-c06-source"
    assert detail["fallback_chain"][0]["fallback_source_id"] == "p9-c06-fallback"
    assert detail["rate_limit_events"][0]["limit"] == 10
    assert detail["module_discounts"][0]["discount"] == 0.1
    raw = detail["raw_observations"][0]
    assert raw["payload_redacted"] is True
    assert raw["raw_payload"]["api_key"] == "***redacted***"
    assert raw["raw_payload"]["nested"]["authorization"] == "***redacted***"


def test_p45_evidence_detail_supports_scoped_and_stale_resolution(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    _seed_newer_p45_payload(db)

    old_evidence_id = "p3-score-p3-old-macro_radar-ofr_fsi"
    historical = p45_dashboard.evidence_detail(old_evidence_id, final_run_id="final-test", db=db)
    stale = p45_dashboard.evidence_detail(old_evidence_id, allow_stale_fallback=True, db=db)

    assert historical is not None
    assert historical["resolution"]["status"] == "historical_exact"
    assert historical["evidence"]["metric_id"] == "ofr_fsi"
    assert stale is not None
    assert stale["resolution"]["status"] == "stale_metric_fallback"
    assert stale["resolution"]["requested_evidence_id"] == old_evidence_id
    assert stale["resolution"]["resolved_evidence_id"] == "ev-new"


def test_p45_job_status_uses_runtime_tables(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    p45_jobs._init_job("p45job-test", {"run_mode": "live"}, db=db)
    p45_jobs._set_stage("p45job-test", "p1_collect", "running", "collecting", db=db)
    running = p45_jobs.job_status("p45job-test", db=db)
    p45_jobs._complete_job(
        "p45job-test",
        "completed",
        {"final_run_id": "final-test", "collect_run_id": "collect-test"},
        db=db,
    )
    completed = p45_jobs.job_status("p45job-test", db=db)

    assert running is not None
    assert running["status"] == "running"
    assert running["current_stage"] == "p1_collect"
    assert completed is not None
    assert completed["status"] == "completed"
    assert completed["run_lineage"]["final_run_id"] == "final-test"
    assert "audit_reports" in completed
    assert completed["logs"][0]["metadata"]


def test_p45_job_status_exposes_execution_profile_and_decision_ready(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    p45_jobs._init_job(
        "p45job-profile",
        {
            "run_mode": "live",
            "execution_profile": "fast_deterministic",
            "skip_llm": True,
            "skip_research_llm": True,
            "skip_analyst_llm": True,
        },
        db=db,
    )
    p45_jobs._set_stage("p45job-profile", "p45_final", "completed", "final-test", db=db)
    p45_jobs._checkpoint_job(
        "p45job-profile",
        {
            "execution_profile": "fast_deterministic",
            "skip_llm": True,
            "decision_ready": True,
            "final_run_id": "final-test",
            "pack_id": "pack-test",
        },
        stage_name="p45_final",
        db=db,
    )
    p45_jobs._set_stage(
        "p45job-profile",
        "p45_llm_research",
        "skipped",
        "skipped_by_execution_profile",
        db=db,
    )
    p45_jobs._set_stage(
        "p45job-profile",
        "p45_llm_analysts",
        "skipped",
        "skipped_by_execution_profile",
        db=db,
    )

    result = p45_jobs.job_status("p45job-profile", db=db)

    assert result is not None
    assert result["execution_profile"] == "fast_deterministic"
    assert result["decision_ready"] is True
    assert result["llm_enabled"] is False
    assert result["llm_status"] == "skipped"
    assert result["run_lineage"]["final_run_id"] == "final-test"
    assert {stage["status"] for stage in result["stages"] if stage["stage_id"].startswith("p45_llm")} == {
        "skipped"
    }


def test_p45_job_status_derives_fast_profile_from_legacy_skip_llm(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    p45_jobs._init_job(
        "p45job-legacy-skip",
        {
            "run_mode": "live",
            "skip_llm": True,
        },
        db=db,
    )
    p45_jobs._set_stage("p45job-legacy-skip", "p45_final", "completed", "final-test", db=db)
    p45_jobs._set_stage("p45job-legacy-skip", "p45_llm_research", "completed", "skipped", db=db)
    p45_jobs._set_stage("p45job-legacy-skip", "p45_llm_analysts", "completed", "skipped", db=db)
    p45_jobs._complete_job(
        "p45job-legacy-skip",
        "completed",
        {"final_run_id": "final-test"},
        db=db,
    )

    result = p45_jobs.job_status("p45job-legacy-skip", db=db)

    assert result is not None
    assert result["execution_profile"] == "fast_deterministic"
    assert result["llm_enabled"] is False
    assert result["llm_status"] == "skipped"


def test_p45_history_returns_frozen_final_payload(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        session.add_all(
            [
                schema.ReplayScore(
                    snapshot_id="final-test",
                    horizon="24h",
                    result_pct=1.2,
                    score=0.8,
                    payload={"direction_hit": True},
                ),
                schema.CalibrationNote(
                    target="final-test",
                    note="Keep neutral threshold unchanged.",
                    payload={"author": "test"},
                ),
            ]
        )

    result = p45_dashboard.history("final-test", db=db)

    assert result is not None
    assert result["status"] == "ok"
    assert result["history_mode"]["anchor"] == "final_run_id"
    assert result["history_mode"]["read_only"] is True
    assert result["history_mode"]["uses_latest_runtime_state"] is False
    assert result["created_at"] == "2026-05-22T00:00:00+00:00"
    assert result["contract_status"] == "passed"
    assert result["final"]["final_view"] == "neutral"
    assert result["pack"]["pack_id"] == "pack-test"
    assert result["analysts"]["article_run_id"] == "articles-test"
    assert result["llm_research"]["llm_research_run_id"] == "research-test"
    assert result["llm_analysts"]["llm_analyst_run_id"] == "llm-analysts-test"
    assert result["replay_scores"][0]["horizon"] == "24h"
    assert result["replay_scores"][0]["payload"]["direction_hit"] is True
    assert result["calibration_notes"][0]["note"] == "Keep neutral threshold unchanged."
    assert result["calibration_notes"][0]["production_weight_mutation"] is False


def test_p45_history_list_uses_final_run_id_anchor(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    result = p45_dashboard.history_list(db=db)

    assert result["status"] == "ok"
    assert result["schema_version"] == "p45.history_list.v1"
    assert result["history_mode"]["anchor"] == "final_run_id"
    assert result["history_mode"]["historical_payload_frozen"] is True
    assert result["count"] == 1
    assert result["items"][0]["final_run_id"] == "final-test"
    assert result["items"][0]["history_url"] == "/api/p45/history/final-test"


def test_p45_history_replay_projects_btc_total_state_v2_from_sqlite(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["btc_total_state_explanation"] = {
            "btc_short_term_state": "price_up_confirmed",
            "direction_drivers": [{"layer": "price_state", "state": "price_up"}],
        }
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "btc_total_state",
                "module_direction": "bullish",
                "semantic_profile_version": "p3.c41.btc_total_state.v2",
                "price_state": {"state": "price_up", "affects_direction": True},
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
            }
        ]
        row.payload = payload

    result = p45_dashboard.history("final-test", db=db)

    assert result is not None
    assert result["final"]["btc_total_state_explanation"]["btc_short_term_state"] == "price_up_confirmed"
    assert result["btc_total_state_explanation"]["btc_short_term_state"] == "price_up_confirmed"
    btc_module = next(
        item for item in result["radar_modules"] if item["radar_module"] == "btc_total_state"
    )
    assert btc_module["btc_total_state_v2"]["price_state"]["state"] == "price_up"
    assert btc_module["btc_total_state_v2"]["audit_context"]["affects_direction"] is False


def test_p45_history_replay_keeps_btc_total_v1_fallback(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "final-test",
                schema.ModuleJsonOutput.module_id == "p45_final_article",
            )
        )
        assert row is not None
        payload = dict(row.payload)
        payload["radar_module_scores"] = list(payload["radar_module_scores"]) + [
            {
                "radar_module": "btc_total_state",
                "module_direction": "neutral",
                "semantic_profile_version": "p3.c27.btc_total_state.v1",
            }
        ]
        row.payload = payload

    result = p45_dashboard.history("final-test", db=db)

    assert result is not None
    btc_module = next(
        item for item in result["radar_modules"] if item["radar_module"] == "btc_total_state"
    )
    assert btc_module["btc_total_state_v2"]["semantic_profile_version"] == "p3.c27.btc_total_state.v1"
    assert btc_module["btc_total_state_v2"]["price_state"] is None
    assert btc_module["btc_total_state_v2"]["btc_short_term_state"] is None


def test_p45_latest_runs_exposes_stage_lineage(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    _seed_p45_payloads(db)

    result = p45_dashboard.latest_runs(db=db)

    assert result["status"] == "ok"
    assert result["schema_version"] == "p45.runs.v1"
    assert result["run_id"] == "final-test"
    assert result["progress"]["current_stage"] == "completed"
    stage_ids = {item["stage_id"] for item in result["stages"]}
    assert {"p1", "p2", "p3", "p45", "llm_research", "llm_analysts"} <= stage_ids
    assert all("worker_id" in item for item in result["stages"])
    assert all("retry_count" in item for item in result["stages"])
    assert result["latest"]["final_run_id"] == "final-test"
    assert result["audit_reports"]["schema_version"] == "p45.audit_reports.v1"
    for report in result["audit_reports"]["reports"]:
        assert {"phase", "report_type", "path", "url", "run_id", "created_at", "status"} <= set(report)


def test_p45_settings_masks_api_keys() -> None:
    result = p45_dashboard.settings_summary()

    assert result["status"] == "ok"
    assert "deepseek_api_key" not in result["llm"]
    assert "has_deepseek_key" in result["llm"]


def test_p45_api_exposes_direct_trend_v22_contract(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-direct-api.sqlite3")
    db.init_schema()
    _seed_p45_v22_payload(db)

    dashboard = p45_dashboard.latest_dashboard(db=db)
    overview = p45_dashboard.latest_overview(db=db)
    history = p45_dashboard.history("final-v22-test", db=db)

    for result in (dashboard, overview, history):
        assert result["btc_timescale_judge"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
        assert result["direct_trend_api"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
        assert result["direct_trend_api"]["snapshot_id"] == "state-v22-test"
        assert result["direct_trend_api"]["horizons"]["4h"]["direct_trend_direction_score"] == 42.0
        assert result["direct_trend_api"]["horizons"]["4h"]["event_trust_cap"] == 88.0
        assert result["direct_trend_api"]["horizons"]["4h"]["radar_context_bias"] == 8.0
        assert result["direct_trend_api"]["source_fresh"] is True
        assert result["btc_timescale_replay_snapshot"]["snapshot_id"] == "state-v22-test"


def test_radar_runtime_cockpit_exposes_latest_direct_trend_replay(tmp_path, monkeypatch) -> None:
    db = Database(tmp_path / "onlybtc-runtime-direct-api.sqlite3")
    db.init_schema()
    payload = _v22_judge_payload()
    save_timescale_judge_snapshot("final-v22-test", payload, db=db)

    import onlybtc.api.radar_runtime as radar_runtime_api
    import onlybtc.direct_trend.replay as replay_module

    monkeypatch.setattr(radar_runtime_api, "latest_runtime_payload", lambda: {"health": {"runtime_fresh": True}})
    monkeypatch.setattr(replay_module, "database", db, raising=False)
    monkeypatch.setattr(radar_runtime_api, "replay_timescale_judge", lambda latest=True: replay_module.replay_timescale_judge(latest=latest, db=db))

    result = cockpit_latest()

    assert result["btc_timescale_judge"]["schema_version"] == "p45.btc_timescale_judge.v2.2"
    assert result["btc_timescale_replay_snapshot"]["snapshot_id"] == "state-v22-test"
    assert result["direct_trend_api"]["runtime_fresh"] is True
    assert result["direct_trend_api"]["source_fresh"] is True
    assert result["direct_trend_api"]["horizons"]["1d"]["direct_trend_trust_score"] == 77.0


def _seed_p45_payloads(db: Database) -> None:
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="pack-test",
                    module_id="p45_analyst_evidence_pack",
                    schema_version="p45.evidence_pack.v1",
                    payload={
                        "pack_id": "pack-test",
                        "p3_run_id": "p3-test",
                        "p2_radar_run_id": "radar-test",
                        "collect_run_id": "collect-test",
                        "analysts": [],
                    },
                ),
                schema.ModuleJsonOutput(
                    run_id="articles-test",
                    module_id="p45_analyst_articles",
                    schema_version="p45.analyst_articles.v1",
                    payload={
                        "article_run_id": "articles-test",
                        "pack_id": "pack-test",
                        "analyst_articles": [
                            {"analyst_id": "macro_event_analyst", "direction": "neutral"}
                        ],
                    },
                ),
                schema.ModuleJsonOutput(
                    run_id="final-test",
                    module_id="p45_final_article",
                    schema_version="p45.research_report.v2",
                    payload={
                        "schema_version": "p45.research_report.v2",
                        "final_run_id": "final-test",
                        "article_run_id": "articles-test",
                        "pack_id": "pack-test",
                        "p3_run_id": "p3-test",
                        "p2_radar_run_id": "radar-test",
                        "collect_run_id": "collect-test",
                        "created_at": "2026-05-22T00:00:00+00:00",
                        "runtime_mode": "deterministic",
                        "final_view": "neutral",
                        "final_view_cn": "中性观察",
                        "decision_card": {"direction": "neutral"},
                        "aggregation_audit": {
                            "direction": "neutral",
                            "why_not_strong": ["zero score metrics remain high"],
                            "score_normalization": {
                                "normalization_base": "abs_support_pressure",
                                "direction_threshold": {
                                    "neutral_low": -0.15,
                                    "neutral_high": 0.15,
                                },
                            },
                            "support_drivers": [
                                {"module": "macro_radar", "score": 0.08},
                            ],
                            "pressure_drivers": [
                                {"module": "fund_flow", "score": -0.06},
                            ],
                            "dominant_drivers": [
                                {"module": "macro_radar", "side": "support"},
                            ],
                            "watch_rules": [
                                {"rule_id": "watch-fund-flow", "state": "armed"},
                            ],
                            "conflicting_evidence": {"state": "mixed"},
                            "confidence_explanation": {"level": "medium"},
                        },
                        "horizon_views": {"h24": {"direction": "mixed"}},
                        "pressure_notes": [
                            {
                                "module": "fund_flow",
                                "indicator": "etf_net_flow",
                                "type": "absolute_pressure",
                                "severity": "medium",
                                "message": "ETF still has absolute outflow pressure.",
                                "etf_pressure_easing_confirmed": False,
                            }
                        ],
                        "invalidation_rules": [
                            {
                                "rule_id": "inv-1",
                                "scope": "neutral_watch",
                                "horizon": "24h",
                                "module_id": "kline_orderflow",
                                "conditions": [
                                    {
                                        "metric_id": "btc_price",
                                        "operator": "<",
                                        "threshold": 65000,
                                        "current_value": 66000,
                                        "evidence_id": "ev-kline-close-position",
                                    }
                                ],
                                "distance_to_trigger": 1000,
                            }
                        ],
                        "confirmation_rules": [
                            {
                                "rule_id": "confirm-1",
                                "scope": "neutral_watch",
                                "horizon": "24h",
                                "conditions": [
                                    {
                                        "metric_id": "btc_price",
                                        "operator": ">",
                                        "threshold": 69000,
                                        "current_value": 66000,
                                    }
                                ],
                            }
                        ],
                        "research_article": {"title": "研究正文"},
                        "publish_article": {"body": "$BTC 中性观察"},
                        "radar_module_scores": [
                            {
                                "radar_module": "macro_radar",
                                "module_effective_direction": "bullish",
                                "module_effective_score": 0.12,
                                "module_strength": "medium",
                                "confidence_score": 0.7,
                                "module_quality_score": 0.93,
                                "support_drivers": [
                                    {"metric_id": "ofr_fsi", "score": 0.08},
                                ],
                                "pressure_drivers": [
                                    {"metric_id": "vix", "score": -0.01},
                                ],
                            },
                            {
                                "radar_module": "derivatives_crowding",
                                "module_effective_direction": "neutral",
                                "module_effective_bias": "mild_support",
                                "trend_direction": "neutral",
                                "trend_state": "neutral_wait_confirm",
                                "module_state": "balanced",
                                "crowding_state": "not_crowded",
                                "leverage_heat_state": "low_to_normal",
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
                            }
                            ,
                            {
                                "radar_module": "kline_orderflow",
                                "module_score": -0.1139,
                                "module_effective_score": -0.1095,
                                "module_direction": "bearish",
                                "module_effective_direction": "neutral",
                                "module_effective_bias": "mild_pressure",
                                "trend_state": "neutral_wait_confirm",
                                "module_state": "pressure_dominant",
                                "module_semantic_profile": {
                                    "module_effective_bias": "mild_pressure",
                                    "display_state": "neutral_wait_confirm",
                                    "display_summary": "Short-term pressure exists, but kline structure still waits for confirmation.",
                                    "top_kline_reason": "close position sits near the low",
                                },
                                "top_contributors": [
                                    {
                                        "metric_id": "btc_close_position_1h",
                                        "direction": "bearish",
                                        "reason": "close position sits near the low",
                                    }
                                ],
                            }
                        ],
                        "metric_evidence": [
                            {
                                "evidence_id": "p3-score-p3-old-macro_radar-ofr_fsi",
                                "radar_module": "macro_radar",
                                "metric_id": "ofr_fsi",
                                "source_id": "ofr-source",
                                "metric_score": 0.1,
                                "metric_effective_score": 0.08,
                                "freshness_weight": 0.9,
                                "horizon_weight": 1.0,
                                "duplicate_adjustment": 0.0,
                                "horizon_tags": ["24h", "3d"],
                                "duplicate_group_id": "macro-risk",
                                "source_ts": "2026-05-22T00:00:00+00:00",
                                "collected_at": "2026-05-22T00:02:00+00:00",
                                "freshness_minutes": 2,
                                "is_stale": False,
                                "fallback_used": False,
                                "available": True,
                                "p45_metric_brief": "OFR stress is contained.",
                                "score_reason": "OFR stress supports risk appetite.",
                            },
                            {
                                "evidence_id": "ev-2",
                                "radar_module": "macro_radar",
                                "metric_id": "vix",
                                "metric_effective_score": 0.0,
                            },
                            {
                                "evidence_id": "ev-funding",
                                "radar_module": "derivatives_crowding",
                                "metric_id": "btc_funding_rate",
                                "metric_effective_score": 0.054,
                                "direction": "neutral",
                                "funding_state": "funding_mild",
                                "crowding_signal": "not_hot",
                                "direction_contribution": "mild_support",
                                "trend_confirmation": "unconfirmed",
                            },
                            {
                                "evidence_id": "ev-oi",
                                "radar_module": "derivatives_crowding",
                                "metric_id": "btc_open_interest",
                                "metric_effective_score": 0.0,
                                "direction": "neutral",
                                "oi_state": "oi_flat",
                                "oi_confirmation": "none",
                                "oi_trend_signal": "unconfirmed",
                            },
                            {
                                "evidence_id": "ev-top-ls-position",
                                "radar_module": "derivatives_crowding",
                                "metric_id": "btc_top_long_short_position_ratio",
                                "metric_effective_score": 0.0,
                                "direction": "neutral",
                                "positioning_signal": "balanced",
                                "crowding_contribution": "neutral",
                                "positioning_scope": "top_position",
                            },
                            {
                                "evidence_id": "ev-kline-close-position",
                                "radar_module": "kline_orderflow",
                                "metric_id": "btc_close_position_1h",
                                "metric_effective_score": -0.0538,
                                "direction": "bearish",
                                "score_bucket_v2": "negative",
                                "module_composite_state": "neutral_wait_confirm",
                            },
                        ],
                        "data_quality": {"metric_count": 2},
                        "contract_validation": {"status": "passed"},
                    },
                ),
                schema.ModuleJsonOutput(
                    run_id="research-test",
                    module_id="p45_llm_research_article",
                    schema_version="p45.llm_research_article.v1",
                    payload={
                        "llm_research_run_id": "research-test",
                        "final_run_id": "final-test",
                        "provider": "deepseek",
                        "model": "deepseek-reasoner",
                        "status": "completed",
                    },
                ),
                schema.ModuleJsonOutput(
                    run_id="llm-analysts-test",
                    module_id="p45_llm_analyst_articles",
                    schema_version="p45.llm_analyst_articles.v1",
                    payload={
                        "llm_analyst_run_id": "llm-analysts-test",
                        "pack_id": "pack-test",
                        "provider": "deepseek",
                        "analyst_articles": [],
                        "summary": {"completed_count": 4, "failed_count": 0},
                    },
                ),
                schema.AlgorithmAlert(
                    alert_id="alert-p9-c05",
                    run_id="p3-test",
                    level="watch",
                    state="active",
                    title="P9-C05 alert",
                    summary="Alert context contract fixture.",
                    evidence_count=1,
                ),
                schema.RadarOutput(
                    run_id="radar-test",
                    module_id="macro_radar",
                    signal="support",
                    strength=0.12,
                    confidence=0.7,
                    data_quality="high",
                    evidence_summary={"support": ["ofr_fsi"]},
                    conflicting_evidence={"pressure": ["vix"]},
                    risk_flags={},
                    invalidation_signals={},
                ),
            ]
        )


def _seed_p45_v22_payload(db: Database) -> None:
    payload = _v22_judge_payload()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="final-v22-test",
                module_id="p45_final_article",
                schema_version="p45.research_report.v2",
                payload={
                    "schema_version": "p45.research_report.v2",
                    "final_run_id": "final-v22-test",
                    "pack_id": "pack-v22-test",
                    "created_at": "2026-06-22T08:00:00+00:00",
                    "runtime_mode": "deterministic",
                    "final_view": "neutral",
                    "btc_timescale_judge": payload,
                    "btc_timescale_replay_snapshot": {
                        "snapshot_id": "state-v22-test",
                        "run_id": "final-v22-test",
                        "schema_version": "p45.btc_timescale_judge.v2.2",
                    },
                    "radar_module_scores": [],
                    "metric_evidence": [],
                    "contract_validation": {"status": "passed"},
                },
            )
        )


def _v22_judge_payload() -> dict:
    return {
        "schema_version": "p45.btc_timescale_judge.v2.2",
        "snapshot_id": "state-v22-test",
        "asof_ts": "2026-06-22T08:00:00+00:00",
        "source_fresh": True,
        "fallback_used": False,
        "fallback_reason": None,
        "source_window": {
            "schema_version": "p1.c75.source_window.v1",
            "source_fresh": True,
            "max_source_lag_minutes": 12.0,
            "max_source_lag_source_id": "btc_ohlcv_4h",
            "coverage": {"fresh_count": 4, "stale_count": 0, "missing_count": 0, "total_count": 4},
        },
        "freshness_summary": {
            "schema_version": "p2.c43.freshness_summary.v1",
            "source_fresh": True,
            "accepted_count": 4,
            "total_count": 4,
        },
        "horizons": {
            "4h": {
                "horizon": "4h",
                "timescale_state": "direct_up_confirming",
                "direct_trend_direction_score": 42.0,
                "direct_trend_acceptance_score": 65.0,
                "direct_trend_trust_score": 79.0,
                "display_score": 33.18,
                "event_trust_cap": 88.0,
                "radar_context_bias": 8.0,
                "runtime_fresh": True,
                "source_fresh": True,
                "fallback_used": False,
                "fallback_reason": None,
                "module_level_radar_score": 0.42,
            },
            "1d": {
                "horizon": "1d",
                "timescale_state": "direct_up_watch",
                "direct_trend_direction_score": 21.0,
                "direct_trend_acceptance_score": 54.0,
                "direct_trend_trust_score": 77.0,
                "display_score": 16.17,
                "event_trust_cap": 92.0,
                "radar_context_bias": 4.0,
                "runtime_fresh": True,
                "source_fresh": True,
                "fallback_used": False,
                "fallback_reason": None,
                "module_level_radar_score": 0.21,
            },
        },
        "aggregation_audit": {
            "direct_trend_direction_score": 42.0,
            "directional_score": 0.42,
            "module_level_radar_score": 0.42,
        },
    }


def _seed_newer_p45_payload(db: Database) -> None:
    with db.session() as session:
        session.add_all(
            [
                schema.ModuleJsonOutput(
                    run_id="pack-new",
                    module_id="p45_analyst_evidence_pack",
                    schema_version="p45.evidence_pack.v1",
                    payload={"pack_id": "pack-new", "analysts": []},
                ),
                schema.ModuleJsonOutput(
                    run_id="final-new",
                    module_id="p45_final_article",
                    schema_version="p45.research_report.v2",
                    payload={
                        "schema_version": "p45.research_report.v2",
                        "final_run_id": "final-new",
                        "pack_id": "pack-new",
                        "created_at": "2026-05-22T01:00:00+00:00",
                        "runtime_mode": "deterministic",
                        "final_view": "neutral",
                        "metric_evidence": [
                            {
                                "evidence_id": "ev-new",
                                "radar_module": "macro_radar",
                                "metric_id": "ofr_fsi",
                                "metric_effective_score": 0.09,
                            }
                        ],
                        "radar_module_scores": [],
                        "contract_validation": {"status": "passed"},
                    },
                ),
            ]
        )
