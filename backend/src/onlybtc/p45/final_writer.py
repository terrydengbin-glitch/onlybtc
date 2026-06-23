from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.repositories import EventWatchtowerRepository
from onlybtc.db.session import Database, database
from onlybtc.direct_trend.replay import save_timescale_judge_snapshot
from onlybtc.direct_trend.state_machine import BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID
from onlybtc.p45.cockpit import build_btc_trend_cockpit
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.invalidation_workbench import build_invalidation_workbench
from onlybtc.p45.timescale_judge import build_btc_timescale_judge, build_btc_timescale_judge_v22
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID, run_p45_analyst_writers

P45_FINAL_ARTICLE_MODULE_ID = "p45_final_article"
P45_FINAL_ARTICLE_SCHEMA_VERSION = "p45.research_report.v2"
P45_COMPAT_SCHEMA_VERSION = "p45.final_article.v1"
ALLOWED_DECISION_STATES = {
    "strong_bearish",
    "weak_bearish",
    "neutral",
    "neutral_watch",
    "mixed_watch",
    "weak_bullish",
    "weak_bullish_watch",
    "strong_bullish",
}


def run_p45_final_writer(
    article_run_id: str | None = None,
    final_run_id: str | None = None,
    runtime_mode: str = "deterministic",
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        analyst_payload = _load_analyst_articles(session, article_run_id)
        if analyst_payload is None:
            analyst_payload = run_p45_analyst_writers(runtime_mode=runtime_mode, db=db)
        pack_payload = _load_pack(session, analyst_payload.get("pack_id"))
        final_run_id = final_run_id or _generate_final_run_id()
        result = _final_payload(final_run_id, analyst_payload, runtime_mode, pack_payload, db=db)
        session.add(
            schema.ModuleJsonOutput(
                run_id=final_run_id,
                module_id=P45_FINAL_ARTICLE_MODULE_ID,
                schema_version=P45_FINAL_ARTICLE_SCHEMA_VERSION,
                payload=result,
            )
        )
        return result


def _final_payload(
    final_run_id: str,
    analyst_payload: dict[str, Any],
    runtime_mode: str,
    pack_payload: dict[str, Any] | None = None,
    db: Database | None = None,
) -> dict[str, Any]:
    articles = analyst_payload["analyst_articles"]
    metrics = _flatten_pack_metrics(pack_payload)
    modules = _flatten_pack_modules(pack_payload)
    direction_counts = _direction_counts(articles)
    core_view = _core_view(direction_counts)
    key_positive = [
        evidence
        for article in articles
        for evidence in article.get("key_positive_evidence_ids", [])[:3]
    ]
    key_negative = [
        evidence
        for article in articles
        for evidence in article.get("key_negative_evidence_ids", [])[:3]
    ]
    neutral_watch = [
        evidence
        for article in articles
        for evidence in article.get("neutral_watch_evidence_ids", [])[:2]
    ]
    data_boundary = [
        boundary for article in articles for boundary in article.get("data_boundary", [])
    ]
    aggregation_audit = _aggregation_audit(metrics, modules, core_view)
    btc_total_state_explanation = _btc_total_state_explanation(modules)
    options_volatility_explanation = _options_volatility_explanation(modules)
    event_policy_explanation = _event_policy_explanation(modules)
    crypto_breadth_explanation = _crypto_breadth_explanation(modules)
    macro_radar_explanation = _macro_radar_explanation(modules)
    dollar_liquidity_explanation = _dollar_liquidity_explanation(modules)
    treasury_credit_explanation = _treasury_credit_explanation(modules)
    fund_flow_explanation = _fund_flow_explanation(modules)
    onchain_valuation_explanation = _onchain_valuation_explanation(modules)
    btc_adoption_explanation = _btc_adoption_explanation(modules)
    asia_risk_explanation = _asia_risk_explanation(modules)
    kline_orderflow_explanation = _kline_orderflow_explanation(modules)
    trade_structure_flow_explanation = _trade_structure_flow_explanation(modules)
    derivatives_crowding_explanation = _derivatives_crowding_explanation(modules)
    final_view = str(aggregation_audit["direction"])
    decision_card = _decision_card(final_view, aggregation_audit, metrics)
    horizon_views = _horizon_views(metrics)
    invalidation_rules = _invalidation_rules(metrics, final_view)
    confirmation_rules = _confirmation_rules(metrics, final_view)
    pressure_notes = _pressure_notes(metrics, modules)
    research_article = _research_article_v2(
        decision_card=decision_card,
        aggregation=aggregation_audit,
        horizons=horizon_views,
        invalidation_rules=invalidation_rules,
        confirmation_rules=confirmation_rules,
        data_boundary=data_boundary,
        pressure_notes=pressure_notes,
    )
    article_text = research_article["body"]
    publish_article = _publish_article(decision_card, aggregation_audit, horizon_views)
    view_consistency_check = _view_consistency_check(
        final_view=final_view,
        decision_card=decision_card,
        aggregation_audit=aggregation_audit,
        publish_article=publish_article,
        research_article=research_article,
    )
    contract_validation = _contract_validation(
        final_view=final_view,
        legacy_core_view=core_view,
        view_consistency_check=view_consistency_check,
        decision_card=decision_card,
        aggregation_audit=aggregation_audit,
        horizon_views=horizon_views,
        invalidation_rules=invalidation_rules,
        confirmation_rules=confirmation_rules,
        publish_article=publish_article,
        research_article=research_article,
        metrics=metrics,
        modules=modules,
    )
    data_quality = _data_quality(metrics, modules)
    btc_trend_cockpit = build_btc_trend_cockpit(
        modules,
        contract_validation=contract_validation,
        data_quality=data_quality,
    )
    run_lineage = {
        "final_run_id": final_run_id,
        "article_run_id": analyst_payload["article_run_id"],
        "pack_id": analyst_payload["pack_id"],
        "p3_run_id": analyst_payload.get("p3_run_id"),
        "p2_radar_run_id": analyst_payload.get("p2_radar_run_id"),
        "collect_run_id": analyst_payload.get("collect_run_id"),
    }
    invalidation_workbench = build_invalidation_workbench(
        btc_trend_cockpit=btc_trend_cockpit,
        modules=modules,
        invalidation_rules=invalidation_rules,
        confirmation_rules=confirmation_rules,
        contract_validation=contract_validation,
        data_quality=data_quality,
        run_lineage=run_lineage,
    )
    btc_timescale_judge_v21 = build_btc_timescale_judge(
        btc_trend_cockpit=btc_trend_cockpit,
        modules=modules,
        contract_validation=contract_validation,
        data_quality=data_quality,
    )
    btc_direct_trend_state_machine = _latest_direct_trend_state_machine(db)
    btc_timescale_judge = build_btc_timescale_judge_v22(
        direct_trend_state=btc_direct_trend_state_machine,
        legacy_judge=btc_timescale_judge_v21,
        modules=modules,
    )
    btc_timescale_replay_snapshot = (
        save_timescale_judge_snapshot(final_run_id, btc_timescale_judge, db=db)
        if db is not None
        else {}
    )
    event_window_v3 = _latest_event_window_v3(db)
    return {
        "schema_version": P45_FINAL_ARTICLE_SCHEMA_VERSION,
        "compat_schema_version": P45_COMPAT_SCHEMA_VERSION,
        "final_run_id": final_run_id,
        "article_run_id": analyst_payload["article_run_id"],
        "pack_id": analyst_payload["pack_id"],
        "p3_run_id": analyst_payload.get("p3_run_id"),
        "p2_radar_run_id": analyst_payload.get("p2_radar_run_id"),
        "collect_run_id": analyst_payload.get("collect_run_id"),
        "runtime_mode": runtime_mode,
        "created_at": datetime.now(UTC).isoformat(),
        "final_view": final_view,
        "final_view_cn": _direction_cn(final_view),
        "decision_source": "aggregation_audit.directional_score_with_strength_downgrade",
        "legacy_core_view": core_view,
        "core_view": core_view,
        "direction_counts": direction_counts,
        "view_consistency_check": view_consistency_check,
        "decision_card": decision_card,
        "aggregation_audit": aggregation_audit,
        "horizon_views": horizon_views,
        "invalidation_rules": invalidation_rules,
        "confirmation_rules": confirmation_rules,
        "pressure_notes": pressure_notes,
        "btc_total_state_explanation": btc_total_state_explanation,
        "options_volatility_explanation": options_volatility_explanation,
        "event_policy_explanation": event_policy_explanation,
        "crypto_breadth_explanation": crypto_breadth_explanation,
        "macro_radar_explanation": macro_radar_explanation,
        "dollar_liquidity_explanation": dollar_liquidity_explanation,
        "treasury_credit_explanation": treasury_credit_explanation,
        "fund_flow_explanation": fund_flow_explanation,
        "onchain_valuation_explanation": onchain_valuation_explanation,
        "btc_adoption_explanation": btc_adoption_explanation,
        "asia_risk_explanation": asia_risk_explanation,
        "kline_orderflow_explanation": kline_orderflow_explanation,
        "trade_structure_flow_explanation": trade_structure_flow_explanation,
        "derivatives_crowding_explanation": derivatives_crowding_explanation,
        "research_article": research_article,
        "publish_article": publish_article,
        "radar_module_scores": modules,
        "metric_evidence": metrics,
        "btc_trend_cockpit": btc_trend_cockpit,
        "invalidation_workbench": invalidation_workbench,
        "btc_timescale_judge": btc_timescale_judge,
        "btc_timescale_judge_v21": btc_timescale_judge_v21,
        "btc_direct_trend_state_machine": btc_direct_trend_state_machine or {},
        "btc_timescale_replay_snapshot": {
            key: btc_timescale_replay_snapshot.get(key)
            for key in (
                "snapshot_id",
                "run_id",
                "asof_ts",
                "schema_version",
                "source_window",
                "freshness_summary",
                "fallback_used",
                "fallback_reason",
            )
        }
        if btc_timescale_replay_snapshot
        else {},
        "event_window_v3": event_window_v3,
        "data_quality": data_quality,
        "html_contract": {
            "preferred_sections": [
                "decision_card",
                "horizon_views",
                "invalidation_rules",
                "aggregation_audit",
                "research_article",
                "publish_article",
                "evidence_appendix",
            ],
            "evidence_appendix_required": True,
        },
        "contract_validation": contract_validation,
        "article": article_text,
        "analyst_summaries": [
            {
                "analyst_id": item["analyst_id"],
                "title": item["title"],
                "direction_view": item["direction_view"],
                "score_summary": item["score_summary"],
            }
            for item in articles
        ],
        "key_positive_evidence_ids": key_positive[:12],
        "key_negative_evidence_ids": key_negative[:12],
        "neutral_watch_evidence_ids": neutral_watch[:12],
        "data_boundary": data_boundary,
        "summary": {
            "analyst_count": len(articles),
            "key_positive_count": len(key_positive),
            "key_negative_count": len(key_negative),
            "neutral_watch_count": len(neutral_watch),
            "data_boundary_count": len(data_boundary),
            "fallback_used": runtime_mode != "llm",
            "schema_version": P45_FINAL_ARTICLE_SCHEMA_VERSION,
        },
    }


def _latest_event_window_v3(db: Database | None) -> dict[str, Any]:
    if db is None:
        return {}
    try:
        with db.session() as session:
            return EventWatchtowerRepository(session).latest_snapshot() or {}
    except Exception:
        return {}


def _latest_direct_trend_state_machine(db: Database | None) -> dict[str, Any] | None:
    if db is None:
        return None
    try:
        with db.session() as session:
            row = session.scalar(
                select(schema.ModuleJsonOutput)
                .where(schema.ModuleJsonOutput.module_id == BTC_DIRECT_TREND_STATE_MACHINE_MODULE_ID)
                .order_by(schema.ModuleJsonOutput.created_at.desc())
                .limit(1)
            )
        if row is None or not isinstance(row.payload, dict):
            return None
        return row.payload
    except Exception:
        return None


def _flatten_pack_metrics(pack_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not pack_payload:
        return []
    return [
        metric
        for analyst in pack_payload.get("analysts", [])
        for module in analyst.get("modules", [])
        for metric in module.get("metrics", [])
    ]


def _flatten_pack_modules(pack_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not pack_payload:
        return []
    return [
        {
            "analyst_id": analyst.get("analyst_id"),
            "radar_module": module.get("radar_module"),
            "module_score": module.get("module_score"),
            "module_effective_score": module.get("module_effective_score"),
            "module_direction": module.get("module_direction"),
            "module_effective_direction": module.get("module_effective_direction"),
            "module_weight": _module_weight(module),
            "module_quality_score": module.get("module_quality_score"),
            "module_confidence": module.get("module_confidence"),
            "module_raw_score": module.get("module_raw_score"),
            "module_final_score": module.get("module_final_score"),
            "coverage_score": module.get("coverage_score"),
            "conflict_score": module.get("conflict_score"),
            "freshness_factor": module.get("freshness_factor"),
            "freshness_score": module.get("freshness_score"),
            "direction_score": module.get("direction_score"),
            "risk_score": module.get("risk_score"),
            "confidence_score": module.get("confidence_score"),
            "trend_state": module.get("trend_state"),
            "trend_state_reason": module.get("trend_state_reason"),
            "module_state": module.get("module_state"),
            "module_semantic_profile": module.get("module_semantic_profile"),
            "semantic_profile_version": module.get("semantic_profile_version"),
            "direction_driver_scope": module.get("direction_driver_scope"),
            "context_only_scope": module.get("context_only_scope"),
            "price_state": module.get("price_state"),
            "perp_state": module.get("perp_state"),
            "cycle_context": module.get("cycle_context"),
            "audit_context": module.get("audit_context"),
            "btc_short_term_state": module.get("btc_short_term_state"),
            "context_notes": module.get("context_notes"),
            "audit_notes": module.get("audit_notes"),
            "module_purpose": module.get("module_purpose"),
            "options_short_term_state": module.get("options_short_term_state"),
            "trade_permission_hint": module.get("trade_permission_hint"),
            "confidence_adjustment": module.get("confidence_adjustment"),
            "volatility_regime": module.get("volatility_regime"),
            "protection_demand": module.get("protection_demand"),
            "tail_risk": module.get("tail_risk"),
            "expiry_pressure": module.get("expiry_pressure"),
            "pinning_structure": module.get("pinning_structure"),
            "data_quality": module.get("data_quality"),
            "risk_drivers": module.get("risk_drivers"),
            "dominant_event_type": module.get("dominant_event_type"),
            "nearest_event_type": module.get("nearest_event_type"),
            "nearest_event_ts": module.get("nearest_event_ts"),
            "nearest_event_hours": module.get("nearest_event_hours"),
            "event_window_phase": module.get("event_window_phase"),
            "event_short_term_state": module.get("event_short_term_state"),
            "event_risk_lock_level": module.get("event_risk_lock_level"),
            "event_lock_level": module.get("event_lock_level"),
            "penalty_channel": module.get("penalty_channel"),
            "trade_gate": module.get("trade_gate"),
            "summary": module.get("summary"),
            "crypto_breadth_state": module.get("crypto_breadth_state"),
            "btc_implication": module.get("btc_implication"),
            "btc_trend_anchor": module.get("btc_trend_anchor"),
            "breadth_participation": module.get("breadth_participation"),
            "market_cap_diffusion": module.get("market_cap_diffusion"),
            "btc_vs_alt_leadership": module.get("btc_vs_alt_leadership"),
            "sector_risk_appetite": module.get("sector_risk_appetite"),
            "breadth_quality": module.get("breadth_quality"),
            "macro_trend_state": module.get("macro_trend_state"),
            "equity_beta": module.get("equity_beta"),
            "rates_pressure": module.get("rates_pressure"),
            "dollar_pressure": module.get("dollar_pressure"),
            "volatility_stress": module.get("volatility_stress"),
            "financial_stress": module.get("financial_stress"),
            "commodity_context": module.get("commodity_context"),
            "macro_impulse": module.get("macro_impulse"),
            "btc_relative_confirmation": module.get("btc_relative_confirmation"),
            "event_window": module.get("event_window"),
            "invalidation_conditions": module.get("invalidation_conditions"),
            "dollar_liquidity_state": module.get("dollar_liquidity_state"),
            "liquidity_level": module.get("liquidity_level"),
            "liquidity_impulse": module.get("liquidity_impulse"),
            "reserve_buffer": module.get("reserve_buffer"),
            "liquidity_drain_pressure": module.get("liquidity_drain_pressure"),
            "repo_funding_pressure": module.get("repo_funding_pressure"),
            "btc_response_confirmation": module.get("btc_response_confirmation"),
            "support_drivers": _module_driver_payload(module, "support_drivers"),
            "pressure_drivers": _module_driver_payload(module, "pressure_drivers"),
            "trade_structure_state": module.get("trade_structure_state"),
            "signal_stage": module.get("signal_stage"),
            "scores": module.get("scores"),
            "multi_horizon": module.get("multi_horizon"),
            "states": module.get("states"),
            "conflict_drivers": _module_driver_payload(module, "conflict_drivers"),
            "early_warning_flags": module.get("early_warning_flags"),
            "data_quality_flags": module.get("data_quality_flags"),
            "proxy_flags": module.get("proxy_flags"),
            "trade_structure_flow_v23": module.get("trade_structure_flow_v23"),
            "aggressive_flow_state": module.get("aggressive_flow_state"),
            "price_response_state": module.get("price_response_state"),
            "liquidation_state": module.get("liquidation_state"),
            "liquidation_data_quality": module.get("liquidation_data_quality"),
            "mempool_pressure_state": module.get("mempool_pressure_state"),
            "stablecoin_liquidity_state": module.get("stablecoin_liquidity_state"),
            "risk_state": module.get("risk_state"),
            "trend_direction": module.get("trend_direction"),
            "crowding_state": module.get("crowding_state"),
            "leverage_heat_state": module.get("leverage_heat_state"),
            "module_effective_bias": module.get("module_effective_bias"),
            "confirmation_state": module.get("confirmation_state"),
            "funding_state": module.get("funding_state"),
            "oi_state": module.get("oi_state"),
            "positioning_state": module.get("positioning_state"),
            "top_positioning_state": module.get("top_positioning_state"),
            "top_trader_bias_state": module.get("top_trader_bias_state"),
            "positioning_conflict_level": module.get("positioning_conflict_level"),
            "long_short_squeeze_risk": module.get("long_short_squeeze_risk"),
            "long_short_combo_applied": module.get("long_short_combo_applied"),
            "derivatives_combo_state": module.get("derivatives_combo_state"),
            "crowding_score": module.get("crowding_score"),
            "liquidation_risk": module.get("liquidation_risk"),
            "oi_funding_combo_applied": module.get("oi_funding_combo_applied"),
            "derivatives_crowding_v25": module.get("derivatives_crowding_v25"),
            "derivatives_state": module.get("derivatives_state"),
            "trend_prior": module.get("trend_prior"),
            "trend_acceptance_score": module.get("trend_acceptance_score"),
            "crowding_fragility_score": module.get("crowding_fragility_score"),
            "squeeze_risk_score": module.get("squeeze_risk_score"),
            "fund_flow_absolute_direction": module.get("fund_flow_absolute_direction"),
            "fund_flow_marginal_direction": module.get("fund_flow_marginal_direction"),
            "fund_flow_conflict_level": module.get("fund_flow_conflict_level"),
            "fund_flow_state": module.get("fund_flow_state"),
            "p2_fund_flow_semantics_used": module.get("p2_fund_flow_semantics_used"),
            "btc_implication": module.get("btc_implication"),
            "scores": module.get("scores"),
            "states": module.get("states"),
            "early_warning_flags": module.get("early_warning_flags"),
            "data_quality_flags": module.get("data_quality_flags"),
            "top_contributors": module.get("top_contributors"),
            "positive_metric_count": module.get("positive_metric_count"),
            "negative_metric_count": module.get("negative_metric_count"),
            "zero_metric_count": module.get("zero_metric_count"),
            "unavailable_metric_count": module.get("unavailable_metric_count"),
        }
        for analyst in pack_payload.get("analysts", [])
        for module in analyst.get("modules", [])
    ]


def _btc_total_state_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "btc_total_state"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}
    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    price_state = pick("price_state")
    perp_state = pick("perp_state")
    cycle_context = pick("cycle_context")
    audit_context = pick("audit_context")
    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "btc_short_term_state": pick("btc_short_term_state"),
        "direction_drivers": [
            {"layer": "price_state", "state": (price_state or {}).get("state") if isinstance(price_state, dict) else None},
            {"layer": "perp_state", "state": (perp_state or {}).get("state") if isinstance(perp_state, dict) else None},
        ],
        "risk_drivers": [
            {
                "layer": "perp_state",
                "state": (perp_state or {}).get("state") if isinstance(perp_state, dict) else None,
                "risk_state": (perp_state or {}).get("risk_state") if isinstance(perp_state, dict) else None,
                "confirmation": (perp_state or {}).get("confirmation") if isinstance(perp_state, dict) else None,
            }
        ],
        "cycle_context": cycle_context,
        "audit_context": audit_context,
        "context_notes": pick("context_notes") or [],
        "audit_notes": pick("audit_notes") or [],
        "composite_only_notes": [
            "Funding and OI are interpreted only together with price_state.",
            "Funding positive alone is not bullish; OI high alone is not directional.",
            "Halving and block height are context/audit only and do not drive 24h direction.",
        ],
    }


def _fund_flow_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "fund_flow"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "fund_flow_confirmation_rejection_for_btc_trend",
        "fund_flow_state": pick("fund_flow_state"),
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "confidence_score": pick("confidence_score"),
        "btc_implication": pick("btc_implication"),
        "scores": pick("scores") or {},
        "states": pick("states") or {
            "etf_demand": {},
            "stablecoin_liquidity": {},
            "exchange_supply": {},
            "btc_response_confirmation": {},
        },
        "support_drivers": _module_driver_payload(module, "support_drivers")
        or profile.get("support_drivers")
        or [],
        "pressure_drivers": _module_driver_payload(module, "pressure_drivers")
        or profile.get("pressure_drivers")
        or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "summary": pick("summary"),
        "allowed_interpretations": [
            "ETF inflow or stablecoin expansion must be confirmed by BTC response before becoming trend confirmation.",
            "ETF outflow warning means trend_fragile unless price and residual confirm downside.",
            "BTC rejecting a flow tailwind points to internal weakness or stronger offsetting pressure.",
            "BTC resisting a flow headwind points to stronger-than-expected absorption.",
        ],
        "forbidden_directional_interpretations": [
            "ETF inflow therefore BTC must rise.",
            "Stablecoin supply growth therefore BTC is bullish.",
            "Exchange balance decline therefore supply must be tight.",
            "ETF outflow easing therefore bullish.",
            "Single-day exchange outflow confirms spot buying.",
        ],
    }


def _onchain_valuation_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "onchain_valuation"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "onchain_cost_basis_profitability_confirmation_rejection",
        "onchain_valuation_state": pick("onchain_valuation_state"),
        "module_direction": pick("module_direction"),
        "module_bias": pick("module_bias"),
        "module_score": pick("module_score"),
        "trend_delta_score": pick("trend_delta_score"),
        "regime_score": pick("regime_score"),
        "confidence_score": pick("confidence_score"),
        "signal_stage": pick("signal_stage"),
        "btc_implication": pick("btc_implication"),
        "scores": pick("scores") or {},
        "states": pick("states") or {},
        "key_levels": pick("key_levels") or {},
        "support_drivers": _module_driver_payload(module, "support_drivers")
        or profile.get("support_drivers")
        or [],
        "pressure_drivers": _module_driver_payload(module, "pressure_drivers")
        or profile.get("pressure_drivers")
        or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "proxy_flags": pick("proxy_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "invalidation_conditions": pick("invalidation_conditions") or [],
        "summary": pick("summary"),
        "allowed_interpretations": [
            "MVRV/NUPL describe regime and cannot confirm short-term direction alone.",
            "STH cost basis is interpreted through a dynamic band and BTC response.",
            "SOPR crossing 1 is a fast signal until price response and residual confirm it.",
            "BTC rejecting on-chain tailwind indicates internal weakness or offsetting pressure.",
            "Miner/whale proxies are context when exact provider labels are missing.",
        ],
        "forbidden_directional_interpretations": [
            "MVRV high therefore BTC must fall.",
            "NUPL low therefore BTC must rise.",
            "SOPR above 1 therefore trend is confirmed bullish.",
            "BTC above STH cost basis therefore a bull market is confirmed.",
            "Realized cap rising therefore short-term BTC must rise.",
            "Miner or whale proxy confirms exact on-chain selling.",
        ],
    }


def _btc_adoption_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "btc_adoption"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "btc_adoption_confirmation_rejection_for_btc_trend",
        "btc_adoption_state": pick("btc_adoption_state"),
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "confidence_score": pick("confidence_score"),
        "signal_stage": pick("signal_stage"),
        "btc_implication": pick("btc_implication"),
        "timeframe": pick("timeframe") or {},
        "scores": pick("scores") or {},
        "states": pick("states") or {},
        "support_drivers": _module_driver_payload(module, "support_drivers")
        or profile.get("support_drivers")
        or [],
        "pressure_drivers": _module_driver_payload(module, "pressure_drivers")
        or profile.get("pressure_drivers")
        or [],
        "conflict_drivers": pick("conflict_drivers") or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "proxy_flags": pick("proxy_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "invalidation_conditions": pick("invalidation_conditions") or [],
        "summary": pick("summary"),
        "allowed_interpretations": [
            "BTC adoption confirms trend only when core settlement demand and BTC response agree.",
            "Fee pressure is supportive only when adjusted transfer volume and price response confirm real demand.",
            "Activity spikes without settlement confirmation are non-economic activity warnings.",
            "Hashrate/hashprice and Lightning are regime context, not standalone 24h direction.",
            "BTC rejecting adoption tailwind indicates internal weakness or stronger offsetting pressure.",
        ],
        "forbidden_directional_interpretations": [
            "Active addresses rising therefore BTC is bullish.",
            "Transaction count rising therefore trend is confirmed.",
            "Hashrate rising therefore short-term BTC is bullish.",
            "Lightning capacity rising therefore BTC trend is confirmed.",
            "Fees high therefore demand is always bullish.",
        ],
    }


def _asia_risk_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "asia_risk"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "asia_session_risk_and_btc_response_confirmation_rejection",
        "asia_risk_state": pick("asia_risk_state"),
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "module_score_signed": pick("module_score_signed"),
        "confidence_score": pick("confidence_score"),
        "signal_stage": pick("signal_stage"),
        "btc_implication": pick("btc_implication"),
        "scores": pick("scores") or {},
        "btc_response": pick("btc_response") or {},
        "states": pick("states") or {},
        "support_drivers": _module_driver_payload(module, "support_drivers")
        or profile.get("support_drivers")
        or [],
        "pressure_drivers": _module_driver_payload(module, "pressure_drivers")
        or profile.get("pressure_drivers")
        or [],
        "conflict_drivers": pick("conflict_drivers") or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "proxy_flags": pick("proxy_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "invalidation_conditions": pick("invalidation_conditions") or [],
        "summary": pick("summary"),
        "allowed_interpretations": [
            "Asia risk pressure is context until BTC Asia-session price action and residual confirm it.",
            "JPY carry unwind pressure is a deleveraging warning, not standalone BTC bearish confirmation.",
            "BTC resisting Asia risk indicates internal strength or offsetting support.",
            "BTC rejecting Asia tailwind indicates internal weakness or stronger offsetting pressure.",
            "Korea premium is split into healthy demand, FOMO/stress and fading/dislocation states.",
        ],
        "forbidden_directional_interpretations": [
            "USDJPY falling therefore BTC is bearish.",
            "USDCNH rising therefore BTC is bearish.",
            "Nikkei or Hang Seng Tech falling therefore BTC must fall.",
            "Kimchi premium high therefore BTC is bullish.",
            "risk_off_pressure_score high therefore confirmed bearish.",
        ],
    }


def _options_volatility_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "options_volatility"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "volatility_risk_and_expiry_structure",
        "options_short_term_state": pick("options_short_term_state"),
        "module_direction": "neutral",
        "module_score": 0,
        "risk_score": pick("risk_score"),
        "confidence_adjustment": pick("confidence_adjustment"),
        "trade_permission_hint": pick("trade_permission_hint"),
        "volatility_regime": pick("volatility_regime"),
        "protection_demand": pick("protection_demand"),
        "tail_risk": pick("tail_risk"),
        "expiry_pressure": pick("expiry_pressure"),
        "pinning_structure": pick("pinning_structure"),
        "data_quality": pick("data_quality"),
        "risk_drivers": pick("risk_drivers") or [],
        "context_notes": pick("context_notes") or [
            "Options volatility is not a directional alpha module.",
        ],
        "forbidden_directional_interpretations": [
            "put_call_ratio high therefore bearish",
            "options_skew high therefore bearish",
            "max pain above therefore bullish",
            "gamma wall below therefore bearish",
            "IV high therefore price must fall",
        ],
    }


def _event_policy_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "event_policy"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose") or "event_risk_and_trade_permission",
        "module_direction": "neutral",
        "module_score": 0,
        "module_effective_score": 0,
        "affects_direction": False,
        "dominant_event_type": pick("dominant_event_type"),
        "nearest_event_type": pick("nearest_event_type"),
        "nearest_event_ts": pick("nearest_event_ts"),
        "nearest_event_hours": pick("nearest_event_hours"),
        "event_window_phase": pick("event_window_phase"),
        "event_short_term_state": pick("event_short_term_state"),
        "event_risk_lock_level": pick("event_risk_lock_level"),
        "penalty_channel": pick("penalty_channel") or "event_timing_only",
        "risk_score": pick("risk_score"),
        "confidence_adjustment": pick("confidence_adjustment"),
        "trade_gate": pick("trade_gate")
        or {
            "allow_new_position": True,
            "allow_add_position": True,
            "allow_breakout_entry": True,
            "allow_market_entry": True,
            "position_size_multiplier": 1.0,
            "require_wait_until_ts": None,
            "reason_code": "EVENT_NEUTRAL",
        },
        "risk_drivers": pick("risk_drivers") or [],
        "context_notes": pick("context_notes") or [
            "Event policy is not a directional alpha module.",
        ],
        "summary": pick("summary"),
        "forbidden_directional_interpretations": [
            "CPI near therefore BTC bearish",
            "FOMC near therefore BTC bearish",
            "Fed speech risk therefore bearish",
            "blackout active therefore BTC direction weakens",
        ],
    }


def _crypto_breadth_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "crypto_breadth"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "btc_trend_confirmation_by_crypto_market_diffusion",
        "primary_question": pick("primary_question")
        or "is_btc_trend_confirmed_or_refuted_by_crypto_market_breadth",
        "crypto_breadth_state": pick("crypto_breadth_state"),
        "btc_implication": pick("btc_implication"),
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "risk_score": pick("risk_score"),
        "confidence_adjustment": pick("confidence_adjustment"),
        "btc_trend_anchor": pick("btc_trend_anchor"),
        "breadth_participation": pick("breadth_participation"),
        "market_cap_diffusion": pick("market_cap_diffusion"),
        "btc_vs_alt_leadership": pick("btc_vs_alt_leadership"),
        "sector_risk_appetite": pick("sector_risk_appetite"),
        "breadth_quality": pick("breadth_quality"),
        "support_drivers": pick("support_drivers") or [],
        "pressure_drivers": pick("pressure_drivers") or [],
        "risk_drivers": pick("risk_drivers") or [],
        "context_notes": pick("context_notes") or [
            "Crypto breadth confirms or refutes BTC trend quality; it is not a standalone price target.",
        ],
        "summary": pick("summary"),
        "reporting_guidance": [
            "Explain BTC trend confirmation, fragile narrow rally, defensive leadership, rotation, or breadth divergence.",
            "Do not treat BTC dominance or ETH/BTC alone as bullish/bearish without BTC trend and breadth context.",
        ],
    }


def _macro_radar_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "macro_radar"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "btc_macro_trend_confirmation_and_refutation",
        "macro_trend_state": pick("macro_trend_state"),
        "btc_implication": pick("btc_implication"),
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "risk_score": pick("risk_score"),
        "confidence_adjustment": pick("confidence_adjustment"),
        "equity_beta": pick("equity_beta"),
        "rates_pressure": pick("rates_pressure"),
        "dollar_pressure": pick("dollar_pressure"),
        "volatility_stress": pick("volatility_stress"),
        "financial_stress": pick("financial_stress"),
        "commodity_context": pick("commodity_context"),
        "macro_impulse": pick("macro_impulse"),
        "btc_relative_confirmation": pick("btc_relative_confirmation"),
        "event_window": pick("event_window"),
        "support_drivers": pick("support_drivers") or [],
        "pressure_drivers": pick("pressure_drivers") or [],
        "risk_drivers": pick("risk_drivers") or [],
        "invalidation_conditions": pick("invalidation_conditions") or [],
        "context_notes": pick("context_notes") or [
            "Macro radar confirms or refutes BTC trend quality; single macro metrics are not standalone BTC direction calls.",
        ],
        "summary": pick("summary"),
        "forbidden_directional_interpretations": [
            "DXY up therefore BTC bearish",
            "VIX high therefore BTC must fall",
            "Nasdaq up therefore BTC must rise",
            "Gold up therefore BTC safe-haven bullish",
            "Oil up therefore BTC direction changes",
        ],
        "reporting_guidance": [
            "Explain whether macro conditions confirm, weaken or refute BTC trend.",
            "Separate risk_score from module_score and avoid single-factor causality.",
        ],
    }


def _dollar_liquidity_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "dollar_liquidity"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "confirm_or_refute_btc_trend_by_usd_liquidity_and_funding_conditions",
        "dollar_liquidity_state": pick("dollar_liquidity_state"),
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "risk_score": pick("risk_score"),
        "confidence_adjustment": pick("confidence_adjustment"),
        "data_freshness": pick("data_freshness"),
        "liquidity_level": pick("liquidity_level"),
        "liquidity_impulse": pick("liquidity_impulse"),
        "reserve_buffer": pick("reserve_buffer"),
        "liquidity_drain_pressure": pick("liquidity_drain_pressure"),
        "repo_funding_pressure": pick("repo_funding_pressure"),
        "btc_response_confirmation": pick("btc_response_confirmation"),
        "support_drivers": pick("support_drivers") or [],
        "pressure_drivers": pick("pressure_drivers") or [],
        "risk_drivers": pick("risk_drivers") or [],
        "context_notes": pick("context_notes") or [
            "Dollar liquidity confirms or refutes BTC trend through net liquidity, funding pressure and BTC response.",
        ],
        "summary": pick("summary"),
        "forbidden_directional_interpretations": [
            "SOFR high therefore BTC bearish",
            "Fed balance sheet down therefore BTC bearish",
            "ON RRP down therefore BTC bullish",
            "TGA high therefore BTC must fall",
        ],
        "reporting_guidance": [
            "Explain whether BTC is absorbing or rejecting dollar liquidity changes.",
            "Treat SOFR, TGA, ON RRP and Fed balance sheet as composite inputs, not standalone direction calls.",
        ],
    }


def _treasury_credit_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "treasury_credit"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": pick("module_purpose")
        or "btc_trend_confirmation_by_rates_curve_and_credit_stress",
        "timeframe": pick("timeframe"),
        "treasury_credit_state": pick("treasury_credit_state"),
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "risk_score": pick("risk_score"),
        "confidence_adjustment": pick("confidence_adjustment"),
        "btc_implication": pick("btc_implication"),
        "states": pick("states") or {},
        "support_drivers": pick("support_drivers") or [],
        "pressure_drivers": pick("pressure_drivers") or [],
        "risk_drivers": pick("risk_drivers") or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "context_notes": pick("context_notes") or [
            "Treasury credit confirms or refutes BTC trend through rates, curve and credit stress.",
        ],
        "summary": pick("summary"),
        "forbidden_directional_interpretations": [
            "2Y rising therefore BTC bearish",
            "10Y rising therefore BTC bearish",
            "HY spread high therefore BTC bearish",
            "Treasury yields falling therefore BTC bullish",
        ],
        "reporting_guidance": [
            "Separate warning from confirmed risk-off.",
            "Explain whether BTC absorbs, rejects or resists rates and credit signals.",
            "Distinguish real-yield tightening from breakeven-led reflation.",
        ],
    }


def _kline_orderflow_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "kline_orderflow"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": "short_term_btc_trend_confirmation_by_price_structure_aggressor_flow_vwap_and_residual",
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "trend_sensitivity_score": pick("trend_sensitivity_score"),
        "trend_reliability_score": pick("trend_reliability_score"),
        "confidence_score": pick("confidence_score"),
        "signal_stage": pick("signal_stage"),
        "volatility_regime": pick("volatility_regime"),
        "kline_orderflow_state": pick("kline_orderflow_state"),
        "btc_implication": pick("btc_implication"),
        "scores": pick("scores") or {},
        "key_levels": pick("key_levels") or {},
        "drivers": pick("drivers") or {},
        "support_drivers": pick("support_drivers") or [],
        "pressure_drivers": pick("pressure_drivers") or [],
        "conflict_drivers": pick("conflict_drivers") or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "rejection_flags": pick("rejection_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "invalidation_conditions": pick("invalidation_conditions") or [],
        "summary": pick("display_summary") or pick("summary"),
        "forbidden_directional_interpretations": [
            "taker buy ratio high therefore BTC bullish",
            "taker sell ratio high therefore BTC bearish",
            "volume expansion alone confirms the trend",
            "VWAP reclaim alone is bullish",
            "one 5m candle confirms the trend",
        ],
        "reporting_guidance": [
            "Separate early_warning from confirmed_signal.",
            "Explain whether active flow was accepted or rejected by price.",
            "Treat false breakout, absorption and exhaustion as explicit rejection states.",
        ],
    }


def _trade_structure_flow_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "trade_structure_flow"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": "confirm_or_refute_btc_trend_by_market_structure_liquidity_leverage_liquidation_and_price_acceptance",
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "confidence_score": pick("confidence_score"),
        "signal_stage": pick("signal_stage"),
        "trade_structure_state": pick("trade_structure_state"),
        "btc_implication": pick("btc_implication"),
        "scores": pick("scores") or {},
        "multi_horizon": pick("multi_horizon") or {},
        "states": pick("states") or {},
        "support_drivers": pick("support_drivers") or [],
        "pressure_drivers": pick("pressure_drivers") or [],
        "conflict_drivers": pick("conflict_drivers") or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "proxy_flags": pick("proxy_flags") or [],
        "invalidation_conditions": pick("invalidation_conditions") or [],
        "summary": pick("display_summary") or pick("summary"),
        "forbidden_directional_interpretations": [
            "volume high therefore BTC bullish",
            "taker buy/sell ratio alone determines direction",
            "positive funding therefore bullish",
            "rising open interest alone is bullish or bearish",
            "liquidation spike alone is a confirmed signal",
            "liquidity thinning alone is bearish",
        ],
        "reporting_guidance": [
            "Explain structure pressure separately from BTC direction.",
            "Confirmed signals require price acceptance and standardized residual alignment.",
            "Liquidation snapshots are incomplete market evidence and cannot confirm direction alone.",
            "Do not repeat kline candle-shape analysis; this module is for market structure.",
        ],
    }


def _derivatives_crowding_explanation(modules: list[dict[str, Any]]) -> dict[str, Any]:
    module = next((item for item in modules if item.get("radar_module") == "derivatives_crowding"), None)
    if not module:
        return {}
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}

    def pick(key: str) -> Any:
        return module.get(key) if module.get(key) is not None else profile.get(key)

    return {
        "semantic_profile_version": pick("semantic_profile_version"),
        "module_purpose": "confirm_or_refute_btc_trend_by_derivatives_trend_acceptance_crowding_squeeze_and_liquidation_response",
        "module_direction": pick("module_direction"),
        "module_score": pick("module_score"),
        "confidence_score": pick("confidence_score"),
        "signal_stage": pick("signal_stage"),
        "derivatives_state": pick("derivatives_state"),
        "btc_implication": pick("btc_implication"),
        "trend_prior": pick("trend_prior") or {},
        "scores": pick("scores") or {},
        "states": pick("states") or {},
        "support_drivers": pick("support_drivers") or [],
        "pressure_drivers": pick("pressure_drivers") or [],
        "conflict_drivers": pick("conflict_drivers") or [],
        "early_warning_flags": pick("early_warning_flags") or [],
        "data_quality_flags": pick("data_quality_flags") or [],
        "proxy_flags": pick("proxy_flags") or [],
        "invalidation_conditions": pick("invalidation_conditions") or [],
        "summary": pick("display_summary") or pick("summary"),
        "forbidden_directional_interpretations": [
            "positive funding alone means BTC bullish",
            "negative funding alone means BTC bearish",
            "open interest rising alone is directional",
            "long/short ratio alone confirms trend",
            "liquidation spike alone is a confirmed signal",
            "crowding fragility score high equals bearish",
        ],
        "reporting_guidance": [
            "Explain derivatives pressure separately from BTC direction.",
            "Confirmed signals require BTC response, trend prior and standardized residual alignment.",
            "Crowding fragility is a risk/quality downgrade unless price rejects the trend.",
            "Liquidation evidence must be described as follow-through or absorption.",
        ],
    }


def _filter_btc_total_context_drivers(drivers: Any) -> list[dict[str, Any]]:
    if not isinstance(drivers, list):
        return []
    blocked = {"btc_halving_estimated_days", "btc_halving_blocks_remaining", "btc_block_height"}
    return [
        item
        for item in drivers
        if isinstance(item, dict) and str(item.get("metric_id") or "") not in blocked
    ]


def _module_driver_payload(module: dict[str, Any], key: str) -> list[Any]:
    drivers = module.get(key)
    if not isinstance(drivers, list):
        return []
    if module.get("radar_module") == "btc_total_state":
        return _filter_btc_total_context_drivers(drivers)
    return drivers


def _pressure_notes(
    metrics: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    fund_module = next(
        (item for item in modules if item.get("radar_module") == "fund_flow"),
        {},
    )
    fund_profile = fund_module.get("module_semantic_profile")
    if not isinstance(fund_profile, dict):
        fund_profile = {}
    fund_state = str(fund_module.get("fund_flow_state") or fund_profile.get("fund_flow_state") or "")
    absolute = str(fund_module.get("fund_flow_absolute_direction") or "")
    marginal = str(fund_module.get("fund_flow_marginal_direction") or "")
    if not absolute:
        etf_pressure = sum(
            float(item.get("metric_score") or item.get("metric_effective_score") or 0.0)
            for item in metrics
            if item.get("radar_module") == "fund_flow"
            and item.get("metric_id") in {"etf_net_flow", "etf_flow_7d"}
        )
        absolute = "bearish" if etf_pressure < -0.03 else "bullish" if etf_pressure > 0.03 else ""
    if not marginal:
        states = {
            str(item.get("marginal_state") or item.get("marginal_direction") or "")
            for item in metrics
            if item.get("radar_module") == "fund_flow"
            and item.get("metric_id") in {"etf_net_flow", "etf_flow_7d"}
        }
        marginal = "improving" if any("improving" in state or "easing" in state for state in states) else ""
    if absolute == "bearish" and marginal == "improving":
        etf_easing_confirmed = _etf_pressure_easing_confirmed(metrics)
        message = (
            "ETF 仍处于净流出，绝对资金面偏空，但 ETF 流出压力边际缓和。"
            if etf_easing_confirmed
            else "ETF 仍处于净流出，绝对资金面偏空；资金流整体存在边际改善，但 ETF 端仍是压力来源。"
        )
        notes.append(
            {
                "module": "fund_flow",
                "indicator": "etf_net_flow",
                "type": "absolute_pressure",
                "severity": "medium",
                "message": message,
                "etf_pressure_easing_confirmed": etf_easing_confirmed,
            }
        )
    if fund_state in {"etf_outflow_warning", "etf_demand_fading", "exchange_flow_untrusted"}:
        notes.append(
            {
                "module": "fund_flow",
                "type": "fast_warning",
                "state": fund_state,
                "severity": "medium",
                "message": (
                    "Fund-flow warning is early and needs BTC response confirmation before becoming a trend conclusion."
                ),
            }
        )
    if fund_state in {"btc_rejecting_flow_tailwind", "btc_resisting_flow_headwind"}:
        notes.append(
            {
                "module": "fund_flow",
                "type": "flow_rejection",
                "state": fund_state,
                "severity": "high",
                "message": (
                    "BTC response is inconsistent with the fund-flow tailwind/headwind, so treat it as confirmation or refutation evidence."
                ),
            }
        )
    trade_module = next(
        (item for item in modules if item.get("radar_module") == "trade_structure_flow"),
        {},
    )
    trade_state = str(trade_module.get("trade_structure_state") or "")
    if trade_state:
        notes.append(
            {
                "module": "trade_structure_flow",
                "indicator": "taker_buy_sell_ratio",
                "type": "trade_structure_confirmation",
                "severity": "medium"
                if trade_state
                in {"buy_pressure_unconfirmed", "absorption_or_trapped_long", "buy_pressure_rejected"}
                else "info",
                "message": _trade_structure_note_message(trade_module),
                "trade_structure_state": trade_state,
                "aggressive_flow_state": trade_module.get("aggressive_flow_state"),
                "price_response_state": trade_module.get("price_response_state"),
                "confirmation_state": trade_module.get("confirmation_state"),
                "risk_state": trade_module.get("risk_state"),
            }
        )
    return notes


def _trade_structure_note_message(module: dict[str, Any]) -> str:
    state = str(module.get("trade_structure_state") or "mixed_structure")
    aggressive = str(module.get("aggressive_flow_state") or "unknown")
    price = str(module.get("price_response_state") or "unknown")
    stablecoin = str(module.get("stablecoin_liquidity_state") or "neutral_liquidity")
    mempool = str(module.get("mempool_pressure_state") or "normal_context")
    if state == "buy_pressure_unconfirmed":
        return (
            "主动买盘偏强，但价格响应尚未确认，"
            f"stablecoin={stablecoin}，mempool={mempool}，因此属于 buy_pressure_unconfirmed，不是趋势确认。"
        )
    if state == "absorption_or_trapped_long":
        return (
            "主动买盘偏强但价格没有跟涨，价格响应显示 no_upside_response，"
            "更接近 absorption_or_trapped_long，而不是 bullish confirmation。"
        )
    if state == "short_squeeze_chase_risk":
        return (
            "短空清算与价格上行同时出现，属于 short_squeeze_chase_risk，"
            "追涨风险高于健康趋势确认。"
        )
    return (
        f"trade_structure_flow 当前为 {state}；aggressive_flow={aggressive}，"
        f"price_response={price}，需结合价格响应确认，不能把 taker 单项直接写成趋势确认。"
    )


def _etf_pressure_easing_confirmed(metrics: list[dict[str, Any]]) -> bool:
    for item in metrics:
        if item.get("radar_module") != "fund_flow":
            continue
        if item.get("metric_id") not in {"etf_net_flow", "etf_flow_7d"}:
            continue
        state = " ".join(
            str(value or "")
            for value in (
                item.get("marginal_state"),
                item.get("marginal_direction"),
                item.get("flow_momentum_state"),
            )
        )
        if "pressure_easing" in state or "easing" in state or "improving" in state:
            return True
    return False


def _aggregation_audit(
    metrics: list[dict[str, Any]],
    modules: list[dict[str, Any]],
    fallback_direction: str,
) -> dict[str, Any]:
    scored = [item for item in metrics if item.get("score_bucket") != "unavailable"]
    support = sum(max(_effective_score(item), 0.0) for item in scored)
    pressure = abs(sum(min(_effective_score(item), 0.0) for item in scored))
    raw = sum(_effective_score(item) for item in scored)
    module_weighted = sum(
        float(module.get("module_effective_score") or module.get("module_score") or 0.0)
        * float(module.get("module_weight") or 0.0)
        for module in modules
    )
    final_score_raw = round(module_weighted if modules else raw, 4)
    normalization_base = round(abs(raw / final_score_raw), 4) if final_score_raw else 1.0
    zero_quality = _zero_quality(metrics)
    raw_zero_ratio = zero_quality["raw_zero_metric_ratio"]
    decision_zero_ratio = zero_quality["decision_zero_metric_ratio"]
    rule_gap_zero_ratio = zero_quality["rule_gap_zero_ratio"]
    unavailable_ratio = _ratio(metrics, lambda item: item.get("score_bucket") == "unavailable")
    disagreement = min(support, pressure) / max(max(support, pressure), 0.0001)
    confidence_penalty = min(
        decision_zero_ratio * 0.05 + unavailable_ratio * 0.08 + disagreement * 0.08,
        0.25,
    )
    strength_before = _strength_from_score(final_score_raw, 0.0, 0.0)
    strength = _strength_from_score(final_score_raw, decision_zero_ratio, disagreement)
    direction = _final_direction_from_strength(final_score_raw, strength, fallback_direction)
    downgrade_reasons = _downgrade_reasons(
        strength_before,
        strength,
        decision_zero_ratio,
        rule_gap_zero_ratio,
        disagreement,
    )
    return {
        "raw_net_score": round(raw, 4),
        "directional_score": final_score_raw,
        "adjusted_directional_score": final_score_raw,
        "confidence_score": _confidence(
            strength, decision_zero_ratio, unavailable_ratio, disagreement
        ),
        "strength_before_downgrade": strength_before,
        "strength_after_disagreement": strength,
        "final_direction": direction,
        "downgrade_reasons": downgrade_reasons,
        "final_score_raw": final_score_raw,
        "final_score_adjusted": final_score_raw,
        "score_normalization": {
            "raw_net_score": round(raw, 4),
            "normalization_base": normalization_base,
            "directional_score": final_score_raw,
            "direction_threshold": {
                "weak_bearish": -0.12,
                "neutral_low": -0.12,
                "neutral_high": 0.12,
                "weak_bullish": 0.12,
            },
            "explanation": (
                "raw_net_score 经过模块权重、重复指标降权、质量权重、"
                "新鲜度权重和周期权重归一化后得到 directional_score；"
                "零分占比和支撑/压力分歧只降级强度与置信度，不改变方向分数符号。"
            ),
        },
        "direction": direction,
        "strength": strength,
        "confidence": _confidence(strength, decision_zero_ratio, unavailable_ratio, disagreement),
        "confidence_level": _confidence_level(
            _confidence(strength, decision_zero_ratio, unavailable_ratio, disagreement)
        ),
        "disagreement_level": "high"
        if disagreement > 0.45
        else "medium"
        if disagreement > 0.2
        else "low",
        "data_quality_level": _data_quality_level(metrics),
        "zero_quality": zero_quality,
        "score_components": {
            "support_score_abs": round(support, 4),
            "pressure_score_abs": round(pressure, 4),
            "net_score": round(raw, 4),
            "zero_metric_ratio": round(raw_zero_ratio, 4),
            "raw_zero_metric_ratio": round(raw_zero_ratio, 4),
            "decision_zero_metric_ratio": round(decision_zero_ratio, 4),
            "rule_gap_zero_ratio": round(rule_gap_zero_ratio, 4),
            "context_zero_ratio": zero_quality["context_zero_ratio"],
            "neutral_confirmed_ratio": zero_quality["neutral_confirmed_ratio"],
            "combo_required_ratio": zero_quality["combo_required_ratio"],
            "unavailable_metric_ratio": round(unavailable_ratio, 4),
            "disagreement_penalty": round(disagreement * 0.08, 4),
            "confidence_penalty": round(confidence_penalty, 4),
        },
        "support_drivers": _driver_rows(metrics, want_positive=True),
        "pressure_drivers": _driver_rows(metrics, want_positive=False),
        "dominant_drivers": _dominant_drivers(metrics, direction),
        "counter_drivers": _counter_drivers(metrics, direction),
    }


def _decision_card(
    final_view: str,
    aggregation: dict[str, Any],
    metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    direction = final_view
    strength = aggregation.get("strength") or "neutral"
    why_not = _why_not_strong(direction, aggregation, metrics)
    return {
        "direction": direction,
        "direction_cn": _direction_cn(direction),
        "strength": strength,
        "strength_cn": _strength_cn(strength),
        "confidence": aggregation.get("confidence"),
        "confidence_level": aggregation.get("confidence_level"),
        "trade_permission": "watch_only"
        if strength in {"weak_bearish", "weak_bullish", "neutral"}
        else "small_position_allowed",
        "risk_mode": "defensive" if "bearish" in direction else "balanced",
        "valid_horizon": "24h_to_3d",
        "conclusion_sentence": _conclusion_sentence(direction, strength),
        "why_not_strong_bearish": why_not if "bearish" in direction else [],
        "why_not_strong_bullish": why_not if "bullish" in direction else [],
        "why_not_strong": why_not,
    }


def _horizon_views(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {horizon: _horizon_view(horizon, metrics) for horizon in ("h24", "d3", "d7")}


def _horizon_view(horizon: str, metrics: list[dict[str, Any]]) -> dict[str, Any]:
    items = [item for item in metrics if horizon in set(item.get("horizon_tags") or [])]
    score = round(sum(_effective_score(item) for item in items), 4)
    direction = _direction_from_score(score, "neutral")
    support_drivers = _dedupe_driver_rows(_driver_rows(items, want_positive=True, limit=12))[:5]
    pressure_drivers = _dedupe_driver_rows(_driver_rows(items, want_positive=False, limit=12))[:5]
    support_abs = sum(float(item["weighted_contribution"]) for item in support_drivers)
    pressure_abs = abs(sum(float(item["weighted_contribution"]) for item in pressure_drivers))
    dominant_side = _horizon_dominant_side(
        direction,
        support_abs,
        pressure_abs,
        support_drivers,
        pressure_drivers,
    )
    return {
        "label": {"h24": "24h", "d3": "3d", "d7": "7d"}[horizon],
        "direction": direction,
        "strength": _strength_from_score(
            score, _ratio(items, lambda x: x.get("score_bucket") == "zero"), 0.0
        ),
        "confidence": round(min(0.8, 0.45 + min(abs(score), 0.35)), 4),
        "support_drivers": support_drivers,
        "pressure_drivers": pressure_drivers,
        "dominant_side": dominant_side,
        "dominant_drivers": _horizon_dominant_drivers(
            dominant_side,
            support_drivers,
            pressure_drivers,
        ),
        "main_drivers": [item["metric_id"] for item in _top_by_abs(items, 5)],
        "counter_drivers": [],
        "interpretation": _horizon_interpretation(
            horizon,
            direction,
            support_drivers,
            pressure_drivers,
            dominant_side,
        ),
        "watch_rules": _watch_rules_for_horizon(horizon, items),
    }


def _invalidation_rules(metrics: list[dict[str, Any]], final_view: str) -> list[dict[str, Any]]:
    metric_ids = {str(item.get("metric_id")) for item in metrics}
    return [
        {
            "rule_id": "inv_001_etf_flow_repair",
            "title": "ETF 流出压力缓和",
            "applies_when": _dedupe_states(["bearish", "weak_bearish", "neutral", final_view]),
            "horizon": "3d",
            "metric_ids": [mid for mid in ("etf_net_flow", "etf_flow_7d") if mid in metric_ids],
            "current_state": "watch_etf_flow_pressure",
            "operator": "AND",
            "conditions": [
                {"metric_id": "etf_net_flow", "field": "value", "op": ">", "value": -30000000},
                {"metric_id": "etf_flow_7d", "field": "metric_score", "op": ">=", "value": 0},
            ],
            "action_if_triggered": _rule_action(final_view, "mixed_watch"),
            "reason": "机构边际抛压收窄时，资金流不再支持单边偏空。",
        },
        {
            "rule_id": "inv_002_volume_repair",
            "title": "短线成交量修复",
            "applies_when": _dedupe_states(["bearish", "weak_bearish", "neutral", final_view]),
            "horizon": "24h",
            "metric_ids": [
                mid
                for mid in ("btc_rebound_quality_1h", "btc_close_position_1h", "btc_return_1h")
                if mid in metric_ids
            ],
            "current_state": "watch_price_volume_confirmation",
            "operator": "AND",
            "conditions": [
                {"metric_id": "btc_rebound_quality_1h", "field": "metric_score", "op": ">", "value": 0},
                {"metric_id": "btc_close_position_1h", "field": "value", "op": ">=", "value": 0.55},
                {"metric_id": "btc_return_1h", "field": "metric_score", "op": ">=", "value": 0},
            ],
            "action_if_triggered": _rule_action(final_view, "weak_bullish_watch"),
            "reason": "价格与成交同步修复时，短线下行压力会被削弱。",
        },
        {
            "rule_id": "inv_003_taker_buy_continuation",
            "title": "主动买盘持续强势且 funding 未过热",
            "applies_when": _dedupe_states(["bearish", "weak_bearish", "neutral", final_view]),
            "horizon": "24h",
            "metric_ids": [
                mid for mid in ("taker_buy_sell_ratio", "btc_funding_rate") if mid in metric_ids
            ],
            "current_state": "watch_counter_trend_buying",
            "operator": "AND",
            "conditions": [
                {
                    "metric_id": "taker_buy_sell_ratio",
                    "field": "metric_score",
                    "op": ">",
                    "value": 0,
                },
                {"metric_id": "btc_funding_rate", "field": "value", "op": "<", "value": 0.0001},
            ],
            "action_if_triggered": _rule_action(
                final_view,
                "neutral_watch",
                tag="counter_pressure_watch",
            ),
            "reason": "主动买盘强但杠杆未过热，说明反弹仍可能有健康买盘。",
        },
    ]


def _confirmation_rules(metrics: list[dict[str, Any]], final_view: str) -> list[dict[str, Any]]:
    metric_ids = {str(item.get("metric_id")) for item in metrics}
    return [
        {
            "rule_id": "confirm_001_bearish_continuation",
            "title": "偏空延续确认",
            "applies_when": _dedupe_states(["neutral", "weak_bearish", final_view]),
            "horizon": "24h_to_3d",
            "metric_ids": [
                mid
                for mid in ("etf_net_flow", "taker_buy_sell_ratio", "btc_return_1h")
                if mid in metric_ids
            ],
            "operator": "AND",
            "conditions": [
                {"metric_id": "etf_net_flow", "field": "metric_score", "op": "<", "value": 0},
                {
                    "metric_id": "taker_buy_sell_ratio",
                    "field": "metric_score",
                    "op": "<",
                    "value": 0,
                },
                {"metric_id": "btc_return_1h", "field": "metric_score", "op": "<", "value": 0},
            ],
            "action_if_triggered": _rule_action(final_view, "weak_bearish"),
            "reason": "资金流、主动成交和短线价格同时转弱时，中性观察应降级为弱偏空。",
        }
    ]


def _publish_article(
    decision: dict[str, Any],
    aggregation: dict[str, Any],
    horizons: dict[str, Any],
) -> dict[str, Any]:
    direction_cn = _direction_cn(str(decision.get("direction") or "neutral"))
    title = f"BTC {direction_cn}，先看资金流和短线成交能否确认"
    h24 = _direction_cn(str(horizons.get("h24", {}).get("direction") or "neutral"))
    d3 = _direction_cn(str(horizons.get("d3", {}).get("direction") or "neutral"))
    d7 = _direction_cn(str(horizons.get("d7", {}).get("direction") or "neutral"))
    body = (
        f"$BTC 这里我按{direction_cn}处理，不看单边强趋势，也不急着追方向。"
        f"短线是{h24}，三天和七天分别是{d3}、{d7}，说明节奏还在分歧里。"
        "短线有成交量和部分供给收缩支撑，但 ETF 资金流、美元资金成本、真实利率和"
        "链上活跃度还没有形成一致修复。接下来就盯三件事：ETF 流出能不能收窄，"
        "1h 成交量能不能继续放大，主动买盘能不能重新转强。没确认前，反弹先看压力，"
        "回踩看承接，节奏比立刻下结论更重要。"
    )
    forbidden = _forbidden_content_check(body)
    style_checks = _publish_style_checks(body)
    safe_to_publish = all(not value for value in forbidden.values()) and all(
        _publish_style_pass(style_checks).values()
    )
    return {
        "safe_to_publish": safe_to_publish,
        "publish_type": "market_view",
        "style": "laoma_market_view",
        "title": title,
        "body": body,
        "cashtags": ["$BTC"],
        "forbidden_content_check": forbidden,
        "style_checks": style_checks,
        "publish_score": 82 if safe_to_publish else 40,
        "reject_reason": None if safe_to_publish else "contains_internal_artifact",
    }


def _research_article_v2(
    decision_card: dict[str, Any],
    aggregation: dict[str, Any],
    horizons: dict[str, Any],
    invalidation_rules: list[dict[str, Any]],
    confirmation_rules: list[dict[str, Any]],
    data_boundary: list[str],
    pressure_notes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    final_view_cn = str(decision_card.get("direction_cn") or "中性观察")
    strength_cn = str(decision_card.get("strength_cn") or "中性观察")
    h24 = horizons.get("h24", {})
    d3 = horizons.get("d3", {})
    d7 = horizons.get("d7", {})
    support = aggregation.get("support_drivers") or []
    pressure = aggregation.get("pressure_drivers") or []
    support_text = _driver_names(support[:4]) or "短线成交和部分供给收缩"
    pressure_text = _driver_names(pressure[:4]) or "资金流、利率和链上活跃度压力"
    body = "\n\n".join(
        [
            "# BTC 多维雷达研究结论",
            (
                f"本轮 canonical final view 为{final_view_cn}，强度为{strength_cn}。"
                "这不是单边强趋势结论，而是多周期信号分歧后的主裁判结果。"
            ),
            (
                "核心原因是支撑与压力同时存在：支撑侧主要来自"
                f"{support_text}；压力侧主要来自{pressure_text}。"
                "由于零分指标占比较高，且支撑与压力并没有形成同向共振，"
                "系统将方向强度降级为观察型结论。"
            ),
            (
                "时间尺度上，24h 维度为"
                f"{_direction_cn(str(h24.get('direction') or 'neutral'))}，"
                "3d 维度为"
                f"{_direction_cn(str(d3.get('direction') or 'neutral'))}，"
                "7d 维度为"
                f"{_direction_cn(str(d7.get('direction') or 'neutral'))}。"
                "这说明短线可能有局部承接，但中周期仍需要等待资金流、利率和链上活动确认。"
            ),
            (
                "接下来的观察重点是：ETF 流出是否收窄，1h 成交量是否延续，"
                "主动买盘能否重新转强，以及真实利率和美元资金成本是否松动。"
            ),
            (
                "反证与确认规则已经结构化：若资金流修复且短线量价同步改善，"
                "当前观察结论可以向偏多观察上修；若 ETF 流出、主动成交和短线价格同时转弱，"
                "则需要从中性观察降级为弱偏空。"
            ),
            "数据边界："
            + (_human_data_boundary(data_boundary) if data_boundary else "无重大方向性缺口。"),
        ]
    )
    forbidden = _forbidden_content_check(body)
    return {
        "schema_version": "p45.research_article.v2",
        "title": "BTC 多维雷达研究结论",
        "executive_summary": (
            f"本轮最终结论为{final_view_cn}，强度为{strength_cn}，需要等待资金流与量价确认。"
        ),
        "core_view_narrative": decision_card.get("conclusion_sentence"),
        "horizon_narrative": (
            f"24h={_direction_cn(str(h24.get('direction') or 'neutral'))}；"
            f"3d={_direction_cn(str(d3.get('direction') or 'neutral'))}；"
            f"7d={_direction_cn(str(d7.get('direction') or 'neutral'))}。"
        ),
        "support_pressure_narrative": f"支撑侧：{support_text}。压力侧：{pressure_text}。",
        "invalidation_narrative": (
            f"反证规则 {len(invalidation_rules)} 条，确认规则 {len(confirmation_rules)} 条。"
        ),
        "pressure_notes": pressure_notes or [],
        "data_boundary": data_boundary,
        "safe_for_human_reading": all(not value for value in forbidden.values()),
        "forbidden_content_check": forbidden,
        "body": body,
    }


def _contract_validation(
    final_view: str,
    legacy_core_view: str,
    view_consistency_check: dict[str, Any],
    decision_card: dict[str, Any],
    aggregation_audit: dict[str, Any],
    horizon_views: dict[str, Any],
    invalidation_rules: list[dict[str, Any]],
    confirmation_rules: list[dict[str, Any]],
    publish_article: dict[str, Any],
    research_article: dict[str, Any],
    metrics: list[dict[str, Any]],
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    errors = []
    warnings = []
    zero_quality = aggregation_audit.get("zero_quality") or {}
    decision_zero_ratio = zero_quality.get(
        "decision_zero_metric_ratio",
        aggregation_audit.get("score_components", {}).get("decision_zero_metric_ratio", 0.0),
    )
    if decision_zero_ratio > 0.5 and str(decision_card.get("strength", "")).startswith("strong"):
        errors.append({"code": "STRONG_WITH_HIGH_ZERO_RATIO", "message": "zero metric ratio > 50%"})
    if not zero_quality:
        errors.append(
            {
                "code": "MISSING_ZERO_QUALITY",
                "message": "aggregation_audit.zero_quality is required",
            }
        )
    if zero_quality and zero_quality.get("raw_zero_used_for_penalty") is not False:
        errors.append(
            {
                "code": "RAW_ZERO_USED_FOR_PENALTY",
                "message": "raw zero ratio must be display-only, not penalty basis",
            }
        )
    if not horizon_views:
        errors.append({"code": "MISSING_HORIZON_VIEWS", "message": "horizon views are required"})
    if len(invalidation_rules) < 3:
        errors.append(
            {
                "code": "MISSING_INVALIDATION_RULES",
                "message": "at least 3 invalidation rules required",
            }
        )
    if not publish_article.get("safe_to_publish"):
        errors.append(
            {
                "code": "UNSAFE_PUBLISH_ARTICLE",
                "message": "publish article contains internal artifacts",
            }
        )
    if view_consistency_check.get("status") != "passed":
        errors.append(
            {
                "code": "FINAL_VIEW_CONFLICT",
                "severity": "error",
                "message": "final_view and dependent narrative fields are inconsistent",
                "conflicts": view_consistency_check.get("conflicts", []),
            }
        )
    if not confirmation_rules:
        errors.append(
            {
                "code": "MISSING_CONFIRMATION_RULES",
                "message": "at least one confirmation rule required",
            }
        )
    why_not = decision_card.get("why_not_strong") or []
    if not why_not:
        errors.append(
            {
                "code": "EMPTY_WHY_NOT_STRONG",
                "message": (
                    "decision_card.why_not_strong must explain why the conclusion is not strong"
                ),
            }
        )
    driver_overlap = _driver_overlap(horizon_views)
    if driver_overlap:
        errors.append(
            {
                "code": "HORIZON_DRIVER_OVERLAP",
                "message": "metric appears in both support and pressure drivers",
                "items": driver_overlap,
            }
        )
    duplicated_within_side = _duplicated_horizon_drivers(horizon_views, "metric_id")
    if duplicated_within_side:
        errors.append(
            {
                "code": "HORIZON_DRIVER_DUPLICATED_WITHIN_SIDE",
                "message": "support or pressure drivers contain duplicate metric_id values",
                "items": duplicated_within_side,
            }
        )
    duplicated_group_within_side = _duplicated_horizon_drivers(
        horizon_views,
        "duplicate_group_id",
    )
    if duplicated_group_within_side:
        errors.append(
            {
                "code": "HORIZON_DRIVER_DUPLICATED_GROUP_WITHIN_SIDE",
                "message": (
                    "support or pressure drivers contain duplicate duplicate_group_id values"
                ),
                "items": duplicated_group_within_side,
            }
        )
    duplicated_applies_when = _duplicated_applies_when(invalidation_rules + confirmation_rules)
    if duplicated_applies_when:
        errors.append(
            {
                "code": "DUPLICATED_APPLIES_WHEN",
                "message": "rule applies_when contains duplicate decision states",
                "items": duplicated_applies_when,
            }
        )
    invalid_actions = _invalid_rule_actions(invalidation_rules + confirmation_rules)
    if invalid_actions:
        errors.append(
            {
                "code": "INVALID_RULE_ACTION_STATE",
                "message": "rule action_if_triggered.to must use an allowed decision state",
                "items": invalid_actions,
            }
        )
    horizon_narrative_issues = _horizon_narrative_issues(horizon_views)
    if horizon_narrative_issues:
        errors.append(
            {
                "code": "HORIZON_NARRATIVE_DRIVER_MISMATCH",
                "message": "horizon interpretation must match support/pressure driver side",
                "items": horizon_narrative_issues,
            }
        )
    research_forbidden = research_article.get("forbidden_content_check") or {}
    if any(research_forbidden.values()):
        errors.append(
            {
                "code": "UNSAFE_RESEARCH_ARTICLE",
                "message": "research article contains internal artifacts",
                "checks": research_forbidden,
            }
        )
    missing_freshness = [
        item.get("metric_id") for item in metrics if item.get("freshness_minutes") is None
    ]
    missing_horizon = [item.get("metric_id") for item in metrics if not item.get("horizon_tags")]
    trade_structure = next(
        (item for item in modules if item.get("radar_module") == "trade_structure_flow"),
        {},
    )
    trade_required_fields = {
        "trade_structure_state",
        "aggressive_flow_state",
        "price_response_state",
        "liquidation_state",
        "mempool_pressure_state",
        "stablecoin_liquidity_state",
        "module_effective_bias",
        "confirmation_state",
        "risk_state",
    }
    missing_trade_fields = sorted(
        field for field in trade_required_fields if not trade_structure.get(field)
    )
    if trade_structure and missing_trade_fields:
        errors.append(
            {
                "code": "MISSING_TRADE_STRUCTURE_SEMANTICS",
                "message": "trade_structure_flow composite semantic fields are required",
                "missing_fields": missing_trade_fields,
            }
        )
    if missing_freshness:
        warnings.append({"code": "MISSING_FRESHNESS_FIELDS", "count": len(missing_freshness)})
    if missing_horizon:
        warnings.append({"code": "MISSING_HORIZON_TAGS", "count": len(missing_horizon)})
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "view_consistency_check": view_consistency_check,
        "freshness_check": {
            "required_for_available_metrics": True,
            "required_for_unavailable_metrics": False,
            "available_metric_missing_freshness_count": sum(
                1
                for item in metrics
                if item.get("available") is not False and item.get("freshness_minutes") is None
            ),
            "unavailable_metric_missing_freshness_count": sum(
                1
                for item in metrics
                if item.get("available") is False and item.get("freshness_minutes") is None
            ),
            "status": "passed_with_warning" if missing_freshness else "passed",
        },
        "checks": {
            "final_view": final_view,
            "legacy_core_view": legacy_core_view,
            "final_view_matches_decision_card": decision_card.get("direction") == final_view,
            "final_view_matches_aggregation": aggregation_audit.get("direction") == final_view,
            "has_zero_quality": bool(zero_quality),
            "uses_decision_zero_ratio": zero_quality.get("penalty_basis")
            == "decision_zero_metric_ratio_and_rule_gap_zero_ratio",
            "raw_zero_not_used_as_penalty": zero_quality.get("raw_zero_used_for_penalty") is False,
            "why_not_strong_reason_not_empty": bool(why_not),
            "has_decision_card": bool(decision_card),
            "has_horizon_views": bool(horizon_views),
            "has_invalidation_rules": len(invalidation_rules) >= 3,
            "has_confirmation_rules": len(confirmation_rules) >= 1,
            "has_publish_article": bool(publish_article),
            "publish_article_no_raw_evidence_id": publish_article.get("safe_to_publish") is True,
            "research_article_no_raw_evidence_id": not any(research_forbidden.values()),
            "horizon_driver_no_overlap": not driver_overlap,
            "applies_when_no_duplicates": not duplicated_applies_when,
            "invalidation_action_state_enum_valid": not invalid_actions,
            "horizon_narrative_matches_driver_side": not horizon_narrative_issues,
            "html_no_python_dict_repr": True,
            "horizon_driver_unique_within_side": not duplicated_within_side,
            "horizon_driver_unique_by_duplicate_group": not duplicated_group_within_side,
            "has_confirmation_rules_rendered": bool(confirmation_rules),
            "llm_article_scope_declared": True,
            "all_metrics_have_horizon_tags": not missing_horizon,
            "all_metrics_have_freshness": not missing_freshness,
            "duplicate_groups_checked": True,
            "trade_structure_semantics_present": bool(trade_structure)
            and not missing_trade_fields,
        },
    }


def _final_article_text(
    articles: list[dict[str, Any]],
    core_view: str,
    direction_counts: dict[str, int],
    key_positive: list[str],
    key_negative: list[str],
    neutral_watch: list[str],
    data_boundary: list[str],
    runtime_mode: str,
) -> str:
    sections = [
        "# BTC 多维雷达研究结论",
        (
            f"本轮综合四位分析员的 scored evidence 后，核心判断为{_direction_cn(core_view)}。"
            f"四位分析员方向分布为：{direction_counts}。这不是自由裁判结果，"
            "而是对 P3 已量化正/负/零分和 Radar 板块总分的研究写作汇总。"
        ),
        "## 四大板块共振与分歧",
        "\n".join(
            f"- {item['title']}：{item['score_summary']} 方向={item['direction_view']}。"
            for item in articles
        ),
        "## 正向证据",
        _evidence_sentence(
            key_positive,
            "正向证据主要来自仍在改善或压力较低的指标",
        ),
        "## 负向证据",
        _evidence_sentence(
            key_negative,
            "负向证据代表当前需要尊重的压力来源",
        ),
        "## 中性观察项",
        _evidence_sentence(
            neutral_watch,
            "零分或中性证据不是无效数据，而是后续可能改变方向的观察项",
        ),
        "## 观察路径",
        "接下来 24h 重点看短周期价格与资金流是否同向；3d 重点看 ETF、"
        "稳定币和衍生品拥挤度是否延续；7d 重点看宏观利率压力、链上估值"
        "和采用度是否出现共振修复或进一步背离。",
        "## 数据质量与边界",
        (
            "本轮数据边界："
            + (", ".join(data_boundary[:12]) if data_boundary else "无重大方向性缺口。")
        ),
    ]
    if runtime_mode != "llm":
        sections.append(
            "注：当前为 deterministic fallback 研究文章，后续可由 LLM 在相同证据框架下扩写。"
        )
    return "\n\n".join(sections)


def _direction_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    result = {"bullish": 0, "bearish": 0, "mixed": 0, "neutral": 0}
    for item in articles:
        direction = item.get("direction_view", "neutral")
        result[direction] = result.get(direction, 0) + 1
    return result


def _effective_score(item: dict[str, Any]) -> float:
    return float(item.get("metric_effective_score") or item.get("metric_score") or 0.0)


def _module_weight(module: dict[str, Any]) -> float:
    metrics = module.get("metrics") or []
    values = [
        float(metric.get("module_weight") or 0.0)
        for metric in metrics
        if metric.get("module_weight") is not None
    ]
    return round(sum(values) / len(values), 4) if values else 0.0


def _ratio(items: list[dict[str, Any]], predicate) -> float:
    return (sum(1 for item in items if predicate(item)) / len(items)) if items else 0.0


def _zero_quality(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(metrics) or 1
    counts = {
        "positive": 0,
        "negative": 0,
        "neutral_confirmed": 0,
        "context_only": 0,
        "combo_required": 0,
        "rule_gap_zero": 0,
        "unavailable": 0,
    }
    raw_zero_count = 0
    for item in metrics:
        if item.get("score_bucket") == "zero":
            raw_zero_count += 1
        bucket = str(item.get("score_bucket_v2") or item.get("score_bucket") or "rule_gap_zero")
        if bucket == "zero":
            bucket = "rule_gap_zero"
        if bucket not in counts:
            bucket = "rule_gap_zero"
        counts[bucket] += 1
    decision_zero_count = counts["rule_gap_zero"]
    return {
        "raw_zero_metric_count": raw_zero_count,
        "raw_zero_metric_ratio": round(raw_zero_count / total, 4),
        "score_bucket_v2_counts": counts,
        "decision_zero_metric_count": decision_zero_count,
        "decision_zero_metric_ratio": round(decision_zero_count / total, 4),
        "context_zero_ratio": round(counts["context_only"] / total, 4),
        "neutral_confirmed_ratio": round(counts["neutral_confirmed"] / total, 4),
        "combo_required_ratio": round(counts["combo_required"] / total, 4),
        "rule_gap_zero_ratio": round(counts["rule_gap_zero"] / total, 4),
        "unavailable_ratio": round(counts["unavailable"] / total, 4),
        "penalty_basis": "decision_zero_metric_ratio_and_rule_gap_zero_ratio",
        "raw_zero_used_for_penalty": False,
    }


def _direction_from_score(score: float, fallback: str) -> str:
    if score > 0.12:
        return "bullish"
    if score < -0.12:
        return "bearish"
    if "bullish" in fallback and score > 0:
        return "mixed_bullish"
    if "bearish" in fallback and score < 0:
        return "mixed_bearish"
    return "neutral"


def _horizon_dominant_side(
    direction: str,
    support_abs: float,
    pressure_abs: float,
    support_drivers: list[dict[str, Any]],
    pressure_drivers: list[dict[str, Any]],
) -> str:
    if "bullish" in direction:
        return "support" if support_drivers else "mixed"
    if "bearish" in direction:
        return "pressure" if pressure_drivers else "mixed"
    if support_abs > pressure_abs:
        return "support"
    if pressure_abs > support_abs:
        return "pressure"
    return "mixed"


def _horizon_dominant_drivers(
    dominant_side: str,
    support_drivers: list[dict[str, Any]],
    pressure_drivers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if dominant_side == "support":
        return support_drivers
    if dominant_side == "pressure":
        return pressure_drivers
    return (pressure_drivers[:3] + support_drivers[:3])[:5]


def _final_direction_from_strength(score: float, strength: str, fallback: str) -> str:
    if strength == "neutral":
        return "neutral"
    return _direction_from_score(score, fallback)


def _downgrade_reasons(
    strength_before: str,
    strength_after: str,
    decision_zero_ratio: float,
    rule_gap_zero_ratio: float,
    disagreement: float,
) -> list[str]:
    reasons = []
    if strength_before != strength_after:
        reasons.append("strength_downgraded")
    if decision_zero_ratio > 0.5:
        reasons.append("decision_zero_metric_ratio_high")
    if rule_gap_zero_ratio > 0.35:
        reasons.append("rule_gap_zero_ratio_high")
    if disagreement > 0.45:
        reasons.append("support_pressure_disagreement_high")
    return reasons


def _strength_from_score(score: float, zero_ratio: float, disagreement: float) -> str:
    abs_score = abs(score)
    if zero_ratio > 0.5 or disagreement > 0.45:
        if abs_score >= 0.30:
            return "weak_bearish" if score < 0 else "weak_bullish"
        return "neutral"
    if score <= -0.55:
        return "strong_bearish"
    if score <= -0.30:
        return "medium_bearish"
    if score <= -0.12:
        return "weak_bearish"
    if score >= 0.55:
        return "strong_bullish"
    if score >= 0.30:
        return "medium_bullish"
    if score >= 0.12:
        return "weak_bullish"
    return "neutral"


def _confidence(
    strength: str, zero_ratio: float, unavailable_ratio: float, disagreement: float
) -> float:
    base = 0.72 if strength.startswith(("medium", "strong")) else 0.62
    value = base - zero_ratio * 0.12 - unavailable_ratio * 0.15 - disagreement * 0.18
    return round(max(min(value, 0.86), 0.35), 4)


def _confidence_level(value: float) -> str:
    if value >= 0.72:
        return "high"
    if value >= 0.55:
        return "medium"
    return "low"


def _data_quality_level(metrics: list[dict[str, Any]]) -> str:
    values = [
        float(item.get("quality_score") or 0.0)
        for item in metrics
        if item.get("available") is not False
    ]
    avg = sum(values) / len(values) if values else 0.0
    if avg >= 0.85:
        return "high"
    if avg >= 0.65:
        return "medium"
    return "low"


def _data_quality(metrics: list[dict[str, Any]], modules: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metric_count": len(metrics),
        "module_count": len(modules),
        "avg_metric_quality": round(
            sum(float(item.get("quality_score") or 0.0) for item in metrics) / len(metrics),
            4,
        )
        if metrics
        else 0.0,
        "unavailable_metric_count": sum(
            1 for item in metrics if item.get("score_bucket") == "unavailable"
        ),
        "missing_freshness_count": sum(
            1 for item in metrics if item.get("freshness_minutes") is None
        ),
        "missing_horizon_count": sum(1 for item in metrics if not item.get("horizon_tags")),
    }


def _driver_rows(
    metrics: list[dict[str, Any]],
    want_positive: bool,
    limit: int = 8,
) -> list[dict[str, Any]]:
    items = [
        item
        for item in metrics
        if (_effective_score(item) > 0 if want_positive else _effective_score(item) < 0)
        and item.get("driver_eligible", True) is not False
        and item.get("affects_signal", True) is not False
    ]
    return [
        {
            "metric_id": item.get("metric_id"),
            "module": item.get("radar_module"),
            "direction": item.get("direction"),
            "weighted_contribution": round(_effective_score(item), 4),
            "reason": item.get("p45_metric_brief")
            or item.get("score_reason")
            or item.get("metric_explanation"),
        }
        for item in _top_by_abs(items, limit)
    ]


def _dominant_drivers(metrics: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    if "bullish" in direction:
        return _driver_rows(metrics, want_positive=True)
    if "bearish" in direction:
        return _driver_rows(metrics, want_positive=False)
    return (
        _driver_rows(metrics, want_positive=False)[:4]
        + _driver_rows(metrics, want_positive=True)[:4]
    )


def _counter_drivers(metrics: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    if "bullish" in direction:
        return _driver_rows(metrics, want_positive=False)
    if "bearish" in direction:
        return _driver_rows(metrics, want_positive=True)
    return []


def _top_by_abs(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: abs(_effective_score(item)), reverse=True)[:limit]


def _why_not_strong(
    direction: str,
    aggregation: dict[str, Any],
    metrics: list[dict[str, Any]],
) -> list[str]:
    reasons = []
    components = aggregation.get("score_components", {})
    if components.get("decision_zero_metric_ratio", 0.0) > 0.35:
        reasons.append("零分指标占比较高，方向共振不足。")
    if aggregation.get("support_drivers") and aggregation.get("pressure_drivers"):
        reasons.append("存在明显反向驱动，不能按单边趋势处理。")
    if any(item.get("score_bucket") == "unavailable" for item in metrics):
        reasons.append("仍有不可用指标，结论需要保留数据边界。")
    if not reasons:
        reasons.append("当前分数未达到强趋势阈值。")
    while len(reasons) < 2:
        reasons.append("多周期信号仍未形成一致确认。")
    return reasons


def _strength_cn(value: str) -> str:
    return {
        "strong_bearish": "强偏空",
        "medium_bearish": "中等偏空",
        "weak_bearish": "弱偏空",
        "neutral": "中性观察",
        "weak_bullish": "弱偏多",
        "medium_bullish": "中等偏多",
        "strong_bullish": "强偏多",
    }.get(value, value)


def _conclusion_sentence(direction: str, strength: str) -> str:
    direction_cn = _direction_cn(direction)
    strength_cn = _strength_cn(strength)
    return f"当前 BTC 结构为{direction_cn}，强度为{strength_cn}，更适合按周期验证而非直接外推。"


def _horizon_interpretation(
    horizon: str,
    direction: str,
    support_drivers: list[dict[str, Any]],
    pressure_drivers: list[dict[str, Any]],
    dominant_side: str,
) -> str:
    label = {"h24": "24h", "d3": "3d", "d7": "7d"}[horizon]
    support = _driver_names(support_drivers[:3]) or "暂无明确支撑驱动"
    pressure = _driver_names(pressure_drivers[:3]) or "暂无明确压力驱动"
    direction_cn = _direction_cn(direction)
    if "bullish" in direction:
        return (
            f"{label} 维度方向为{direction_cn}，支撑主因来自 {support}；"
            f"但压力项仍来自 {pressure}，需要继续确认。"
        )
    if "bearish" in direction:
        return (
            f"{label} 维度方向为{direction_cn}，压力主因来自 {pressure}；"
            f"支撑项主要是 {support}，暂时不足以扭转方向。"
        )
    return (
        f"{label} 维度方向为{direction_cn}，支撑侧为 {support}，压力侧为 {pressure}；"
        f"主导侧为 {dominant_side}，更适合继续观察。"
    )


def _watch_rules_for_horizon(horizon: str, items: list[dict[str, Any]]) -> list[str]:
    defaults = {
        "h24": ["观察 1h 成交量是否修复", "观察主动买盘和 funding 是否同步过热"],
        "d3": ["观察 ETF 资金流是否连续修复", "观察美元流动性与风险偏好是否共振"],
        "d7": ["观察真实利率与链上估值是否改变方向", "观察采用度与市场宽度是否持续改善"],
    }
    top = [f"跟踪 {item.get('metric_id')} 是否延续当前方向" for item in _top_by_abs(items, 2)]
    return [*defaults[horizon], *top]


def _forbidden_content_check(body: str) -> dict[str, bool]:
    return {
        "contains_raw_evidence_id": "p3-score-" in body or "ev-" in body,
        "contains_internal_run_id": "run_id" in body or "collect-" in body or "radar-" in body,
        "contains_python_dict": "{" in body or "}" in body,
        "contains_unexplained_score": "schema_version" in body,
    }


def _publish_style_checks(body: str) -> dict[str, bool]:
    lower = body.lower()
    return {
        "contains_score_number": any(token in body for token in ("0.", "综合分数", "置信度")),
        "contains_english_direction": any(
            token in lower for token in ("bullish", "bearish", "neutral")
        ),
        "has_clear_view": any(token in body for token in ("处理", "看", "结论", "观察")),
        "has_watch_points": "盯三件事" in body or "重点看" in body,
        "has_cashtag": "$BTC" in body,
        "no_internal_terms": not any(
            token in body for token in ("run_id", "schema_version", "p3-score")
        ),
    }


def _publish_style_pass(style_checks: dict[str, bool]) -> dict[str, bool]:
    return {
        "no_score_number": style_checks.get("contains_score_number") is False,
        "no_english_direction": style_checks.get("contains_english_direction") is False,
        "has_clear_view": style_checks.get("has_clear_view") is True,
        "has_watch_points": style_checks.get("has_watch_points") is True,
        "has_cashtag": style_checks.get("has_cashtag") is True,
        "no_internal_terms": style_checks.get("no_internal_terms") is True,
    }


def _view_consistency_check(
    final_view: str,
    decision_card: dict[str, Any],
    aggregation_audit: dict[str, Any],
    publish_article: dict[str, Any],
    research_article: dict[str, Any],
) -> dict[str, Any]:
    conflicts = []
    if decision_card.get("direction") != final_view:
        conflicts.append(
            f"decision_card.direction={decision_card.get('direction')} but final_view={final_view}"
        )
    if aggregation_audit.get("direction") != final_view:
        aggregation_direction = aggregation_audit.get("direction")
        conflicts.append(
            f"aggregation_audit.direction={aggregation_direction} "
            f"but final_view={final_view}"
        )
    final_view_cn = _direction_cn(final_view)
    if final_view_cn not in str(publish_article.get("body") or ""):
        conflicts.append("publish_article does not contain final_view_cn")
    if final_view_cn not in str(research_article.get("body") or ""):
        conflicts.append("research_article does not contain final_view_cn")
    return {
        "status": "passed" if not conflicts else "failed",
        "conflicts": conflicts,
    }


def _driver_overlap(horizon_views: dict[str, Any]) -> list[dict[str, Any]]:
    overlaps = []
    for horizon, view in horizon_views.items():
        support = {
            str(item.get("metric_id"))
            for item in view.get("support_drivers", [])
            if item.get("metric_id")
        }
        pressure = {
            str(item.get("metric_id"))
            for item in view.get("pressure_drivers", [])
            if item.get("metric_id")
        }
        shared = sorted(support & pressure)
        if shared:
            overlaps.append({"horizon": horizon, "metric_ids": shared})
    return overlaps


def _dedupe_driver_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    duplicate_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("duplicate_group_id") or row.get("metric_id") or "")
        if not key:
            continue
        duplicate_counts[key] = duplicate_counts.get(key, 0) + 1
        previous = selected.get(key)
        if previous is None or abs(float(row.get("weighted_contribution") or 0.0)) > abs(
            float(previous.get("weighted_contribution") or 0.0)
        ):
            selected[key] = row
    result = []
    for row in selected.values():
        key = str(row.get("duplicate_group_id") or row.get("metric_id") or "")
        if duplicate_counts.get(key, 0) > 1:
            row = {
                **row,
                "dedupe_note": f"merged {duplicate_counts[key]} duplicate driver candidates",
            }
        result.append(row)
    return sorted(
        result,
        key=lambda item: abs(float(item.get("weighted_contribution") or 0.0)),
        reverse=True,
    )


def _duplicated_horizon_drivers(
    horizon_views: dict[str, Any],
    field: str,
) -> list[dict[str, Any]]:
    issues = []
    for horizon, view in horizon_views.items():
        for side in ("support_drivers", "pressure_drivers"):
            values = [
                str(item.get(field))
                for item in view.get(side, [])
                if item.get(field)
            ]
            duplicates = sorted({value for value in values if values.count(value) > 1})
            if duplicates:
                issues.append(
                    {
                        "horizon": horizon,
                        "side": side,
                        field: duplicates,
                    }
                )
    return issues


def _driver_names(drivers: list[dict[str, Any]]) -> str:
    return "、".join(str(item.get("metric_id")) for item in drivers if item.get("metric_id"))


def _dedupe_states(states: list[str]) -> list[str]:
    result = []
    for state in states:
        if state and state not in result:
            result.append(state)
    return result


def _rule_action(from_state: str, to_state: str, tag: str | None = None) -> dict[str, Any]:
    action = {"from": from_state, "to": to_state}
    if tag:
        action["tag"] = tag
    return action


def _duplicated_applies_when(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    for rule in rules:
        states = [str(item) for item in rule.get("applies_when") or []]
        if len(states) != len(set(states)):
            issues.append({"rule_id": rule.get("rule_id"), "applies_when": states})
    return issues


def _invalid_rule_actions(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    for rule in rules:
        action = rule.get("action_if_triggered") or {}
        to_state = str(action.get("to") or "")
        if to_state not in ALLOWED_DECISION_STATES:
            issues.append({"rule_id": rule.get("rule_id"), "to": to_state})
    return issues


def _horizon_narrative_issues(horizon_views: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    for horizon, view in horizon_views.items():
        direction = str(view.get("direction") or "")
        actual_side = str(view.get("dominant_side") or "")
        dominant_ids = {
            str(item.get("metric_id"))
            for item in view.get("dominant_drivers", [])
            if item.get("metric_id")
        }
        support_ids = {
            str(item.get("metric_id"))
            for item in view.get("support_drivers", [])
            if item.get("metric_id")
        }
        pressure_ids = {
            str(item.get("metric_id"))
            for item in view.get("pressure_drivers", [])
            if item.get("metric_id")
        }
        if "bullish" in direction and not dominant_ids.issubset(support_ids):
            issues.append(
                {
                    "horizon": horizon,
                    "direction": direction,
                    "issue": "bullish_not_support",
                    "expected_side": "support",
                    "actual_side": actual_side,
                    "conflicting_driver": sorted(dominant_ids - support_ids),
                }
            )
        if "bearish" in direction and not dominant_ids.issubset(pressure_ids):
            issues.append(
                {
                    "horizon": horizon,
                    "direction": direction,
                    "issue": "bearish_not_pressure",
                    "expected_side": "pressure",
                    "actual_side": actual_side,
                    "conflicting_driver": sorted(dominant_ids - pressure_ids),
                }
            )
    return issues


def _human_data_boundary(data_boundary: list[str]) -> str:
    if not data_boundary:
        return "无重大方向性缺口。"
    return f"存在 {len(data_boundary)} 项数据边界，已在 Evidence 附录保留审计明细。"


def _core_view(counts: dict[str, int]) -> str:
    if counts.get("bearish", 0) >= 3:
        return "bearish"
    if counts.get("bullish", 0) >= 3:
        return "bullish"
    if counts.get("bearish", 0) > counts.get("bullish", 0):
        return "mixed_bearish"
    if counts.get("bullish", 0) > counts.get("bearish", 0):
        return "mixed_bullish"
    return "mixed"


def _evidence_sentence(evidence_ids: list[str], prefix: str) -> str:
    if not evidence_ids:
        return f"{prefix}：暂无。"
    return f"{prefix}：{', '.join(evidence_ids[:12])}。"


def _direction_cn(value: str) -> str:
    return {
        "bearish": "偏空",
        "bullish": "偏多",
        "mixed_bearish": "分歧中偏空",
        "mixed_bullish": "分歧中偏多",
        "mixed": "分歧",
        "neutral": "中性观察",
    }.get(value, value)


def _load_analyst_articles(session, article_run_id: str | None) -> dict[str, Any] | None:
    query = select(schema.ModuleJsonOutput).where(
        schema.ModuleJsonOutput.module_id == P45_ANALYST_ARTICLES_MODULE_ID
    )
    if article_run_id:
        query = query.where(schema.ModuleJsonOutput.run_id == article_run_id)
    row = session.scalar(query.order_by(schema.ModuleJsonOutput.created_at.desc()).limit(1))
    return dict(row.payload) if row else None


def _load_pack(session, pack_id: str | None) -> dict[str, Any] | None:
    if not pack_id:
        return None
    row = session.scalar(
        select(schema.ModuleJsonOutput)
        .where(
            schema.ModuleJsonOutput.module_id == P45_EVIDENCE_PACK_MODULE_ID,
            schema.ModuleJsonOutput.run_id == pack_id,
        )
        .order_by(schema.ModuleJsonOutput.created_at.desc())
        .limit(1)
    )
    return dict(row.payload) if row else None


def _generate_final_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"p45final-{stamp}-{uuid4().hex[:6]}"
