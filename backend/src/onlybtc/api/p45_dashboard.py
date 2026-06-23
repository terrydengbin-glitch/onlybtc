from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.api.contracts import missing_response, ok_response
from onlybtc.api.security import api_security_summary
from onlybtc.core.config import get_settings
from onlybtc.core.llm_routing import llm_routing_payload
from onlybtc.core.paths import paths
from onlybtc.core.provider_health import provider_health_snapshot
from onlybtc.core.provider_registry import provider_registry_payload
from onlybtc.core.settings_audit import settings_audit_summary
from onlybtc.core.settings_contract import settings_contract_payload
from onlybtc.db import schema
from onlybtc.db.repositories import RadarRuntimeRepository
from onlybtc.db.session import Database, database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID
from onlybtc.p45.llm_analyst_writer import P45_LLM_ANALYST_ARTICLES_MODULE_ID
from onlybtc.p45.llm_research_writer import P45_LLM_RESEARCH_ARTICLE_MODULE_ID
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID

REPORT_FILES = {
    "p1": "p1-c22-*html",
    "p2": "p2-radar-quality-report.html",
    "p3": "p3-algorithm-audit-report.html",
    "p45": "p45-research-report.html",
    "radar-runtime": "radar-runtime-audit-report.html",
}


def _semantic_profile(module: dict[str, Any]) -> dict[str, Any]:
    profile = module.get("module_semantic_profile")
    return profile if isinstance(profile, dict) else {}


def _project_module(module: dict[str, Any]) -> dict[str, Any]:
    projected = dict(module)
    profile = _semantic_profile(projected)

    for field in ("display_state", "display_summary", "top_kline_reason"):
        if projected.get(field) is None and profile.get(field) is not None:
            projected[field] = profile.get(field)

    if projected.get("display_state") is None:
        projected["display_state"] = projected.get("trend_state")
    if projected.get("display_summary") is None:
        projected["display_summary"] = _display_summary_fallback(projected)
    if projected.get("top_kline_reason") is None:
        projected["top_kline_reason"] = _top_contributor_reason(projected)
    if str(projected.get("radar_module")) == "trade_structure_flow":
        _project_trade_structure_flow_v23(projected, profile)
        projected["trade_structure_summary"] = _trade_structure_summary(projected)
    if str(projected.get("radar_module")) == "derivatives_crowding":
        _project_derivatives_crowding_v25(projected, profile)
    if str(projected.get("radar_module")) == "btc_total_state":
        _project_btc_total_state_v2(projected, profile)
    if str(projected.get("radar_module")) == "options_volatility":
        _project_options_volatility_v21(projected, profile)
    if str(projected.get("radar_module")) == "event_policy":
        _project_event_policy_v21(projected, profile)
    if str(projected.get("radar_module")) == "crypto_breadth":
        _project_crypto_breadth_v3(projected, profile)
    if str(projected.get("radar_module")) == "macro_radar":
        _project_macro_radar_v3(projected, profile)
    if str(projected.get("radar_module")) == "dollar_liquidity":
        _project_dollar_liquidity_v21(projected, profile)
    if str(projected.get("radar_module")) == "treasury_credit":
        _project_treasury_credit_v21(projected, profile)
    if str(projected.get("radar_module")) == "fund_flow":
        _project_fund_flow_v22(projected, profile)
    if str(projected.get("radar_module")) == "onchain_valuation":
        _project_onchain_valuation_v22(projected, profile)
    if str(projected.get("radar_module")) == "btc_adoption":
        _project_btc_adoption_v23(projected, profile)
    if str(projected.get("radar_module")) == "asia_risk":
        _project_asia_risk_v23(projected, profile)
    if str(projected.get("radar_module")) == "kline_orderflow":
        _project_kline_orderflow_v22(projected, profile)
    return projected


def _project_derivatives_crowding_v25(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    version = str(module.get("semantic_profile_version") or profile.get("semantic_profile_version") or "")
    if version != "p3.c60.derivatives_crowding.v2.5" and not module.get("derivatives_crowding_v25"):
        return
    keys = (
        "module_direction",
        "module_score",
        "confidence_score",
        "signal_stage",
        "derivatives_state",
        "btc_implication",
        "trend_prior",
        "scores",
        "states",
        "support_drivers",
        "pressure_drivers",
        "conflict_drivers",
        "early_warning_flags",
        "data_quality_flags",
        "proxy_flags",
        "invalidation_conditions",
        "display_summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    normalized.setdefault("trend_prior", {})
    normalized.setdefault("scores", {})
    normalized.setdefault("states", {})
    normalized.setdefault("support_drivers", [])
    normalized.setdefault("pressure_drivers", [])
    normalized.setdefault("conflict_drivers", [])
    normalized.setdefault("early_warning_flags", [])
    normalized.setdefault("data_quality_flags", [])
    normalized.setdefault("proxy_flags", [])
    normalized.setdefault("invalidation_conditions", [])
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
        module["module_effective_score"] = normalized.get("module_score")
    module["derivatives_crowding_v25"] = normalized
    module["display_state"] = normalized.get("signal_stage") or normalized.get("derivatives_state")
    if normalized.get("display_summary"):
        module["display_summary"] = normalized.get("display_summary")


def _project_trade_structure_flow_v23(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    version = str(module.get("semantic_profile_version") or profile.get("semantic_profile_version") or "")
    if version != "p3.c58.trade_structure_flow.v2.3" and not module.get("trade_structure_flow_v23"):
        return
    keys = (
        "module_direction",
        "module_score",
        "confidence_score",
        "signal_stage",
        "trade_structure_state",
        "btc_implication",
        "scores",
        "multi_horizon",
        "states",
        "support_drivers",
        "pressure_drivers",
        "conflict_drivers",
        "early_warning_flags",
        "data_quality_flags",
        "proxy_flags",
        "invalidation_conditions",
        "display_summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    normalized.setdefault("scores", {})
    normalized.setdefault("multi_horizon", {})
    normalized.setdefault("states", {})
    normalized.setdefault("support_drivers", [])
    normalized.setdefault("pressure_drivers", [])
    normalized.setdefault("conflict_drivers", [])
    normalized.setdefault("early_warning_flags", [])
    normalized.setdefault("data_quality_flags", [])
    normalized.setdefault("proxy_flags", [])
    normalized.setdefault("invalidation_conditions", [])
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
        module["module_effective_score"] = normalized.get("module_score")
    module["trade_structure_flow_v23"] = normalized
    module["display_state"] = normalized.get("signal_stage") or normalized.get("trade_structure_state")
    if normalized.get("display_summary"):
        module["display_summary"] = normalized.get("display_summary")


def _project_kline_orderflow_v22(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    version = str(module.get("semantic_profile_version") or profile.get("semantic_profile_version") or "")
    if version != "p3.c57.kline_orderflow.v2.2" and not module.get("kline_orderflow_v22"):
        return
    keys = (
        "module_direction",
        "module_score",
        "trend_sensitivity_score",
        "trend_reliability_score",
        "confidence_score",
        "signal_stage",
        "volatility_regime",
        "kline_orderflow_state",
        "btc_implication",
        "scores",
        "key_levels",
        "drivers",
        "support_drivers",
        "pressure_drivers",
        "conflict_drivers",
        "early_warning_flags",
        "rejection_flags",
        "data_quality_flags",
        "invalidation_conditions",
        "display_summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    normalized.setdefault("scores", {})
    normalized.setdefault("key_levels", {})
    normalized.setdefault("drivers", {})
    normalized.setdefault("support_drivers", [])
    normalized.setdefault("pressure_drivers", [])
    normalized.setdefault("conflict_drivers", [])
    normalized.setdefault("early_warning_flags", [])
    normalized.setdefault("rejection_flags", [])
    normalized.setdefault("data_quality_flags", [])
    normalized.setdefault("invalidation_conditions", [])
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
        module["module_effective_score"] = normalized.get("module_score")
    module["kline_orderflow_v22"] = normalized
    module["display_state"] = normalized.get("signal_stage") or normalized.get("kline_orderflow_state")
    if normalized.get("display_summary"):
        module["display_summary"] = normalized.get("display_summary")


def _project_asia_risk_v23(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "module_direction",
        "module_score",
        "module_effective_score",
        "module_score_signed",
        "risk_score",
        "confidence_score",
        "signal_stage",
        "asia_risk_state",
        "btc_implication",
        "scores",
        "btc_response",
        "states",
        "support_drivers",
        "pressure_drivers",
        "conflict_drivers",
        "early_warning_flags",
        "data_quality_flags",
        "proxy_flags",
        "invalidation_conditions",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        if key in {"module_direction", "module_score", "module_effective_score"}:
            value = profile.get(key)
            if value is None:
                value = module.get(key)
        else:
            value = module.get(key)
            if value is None:
                value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    normalized.setdefault("scores", {})
    normalized.setdefault("btc_response", {})
    normalized.setdefault("states", {})
    normalized.setdefault("support_drivers", [])
    normalized.setdefault("pressure_drivers", [])
    normalized.setdefault("conflict_drivers", [])
    normalized.setdefault("proxy_flags", [])
    normalized.setdefault("invalidation_conditions", [])
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
    if normalized.get("module_effective_score") is not None:
        module["module_effective_score"] = normalized.get("module_effective_score")
    elif normalized.get("module_score") is not None:
        module["module_effective_score"] = normalized.get("module_score")
    module["asia_risk_v23"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("signal_stage") or normalized.get("asia_risk_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_btc_adoption_v23(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "timeframe",
        "module_direction",
        "module_score",
        "module_effective_score",
        "risk_score",
        "confidence_score",
        "signal_stage",
        "btc_adoption_state",
        "btc_implication",
        "scores",
        "states",
        "support_drivers",
        "pressure_drivers",
        "conflict_drivers",
        "early_warning_flags",
        "data_quality_flags",
        "proxy_flags",
        "invalidation_conditions",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        if key in {"module_direction", "module_score", "module_effective_score"}:
            value = profile.get(key)
            if value is None:
                value = module.get(key)
        else:
            value = module.get(key)
            if value is None:
                value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    normalized.setdefault("timeframe", {})
    normalized.setdefault("scores", {})
    normalized.setdefault("states", {})
    normalized.setdefault("support_drivers", [])
    normalized.setdefault("pressure_drivers", [])
    normalized.setdefault("conflict_drivers", [])
    normalized.setdefault("proxy_flags", [])
    normalized.setdefault("invalidation_conditions", [])
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
    if normalized.get("module_effective_score") is not None:
        module["module_effective_score"] = normalized.get("module_effective_score")
    elif normalized.get("module_score") is not None:
        module["module_effective_score"] = normalized.get("module_score")
    module["btc_adoption_v23"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("signal_stage") or normalized.get("btc_adoption_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_onchain_valuation_v22(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "module_direction",
        "module_bias",
        "module_score",
        "module_effective_score",
        "trend_delta_score",
        "regime_score",
        "risk_score",
        "confidence_score",
        "signal_stage",
        "onchain_valuation_state",
        "btc_implication",
        "scores",
        "states",
        "key_levels",
        "support_drivers",
        "pressure_drivers",
        "early_warning_flags",
        "invalidation_conditions",
        "proxy_flags",
        "data_quality_flags",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        if key in {"module_direction", "module_score", "module_effective_score"}:
            value = profile.get(key)
            if value is None:
                value = module.get(key)
        else:
            value = module.get(key)
            if value is None:
                value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    normalized.setdefault("scores", {})
    normalized.setdefault("states", {})
    normalized.setdefault("key_levels", {})
    normalized.setdefault("proxy_flags", [])
    normalized.setdefault("invalidation_conditions", [])
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
    if normalized.get("module_effective_score") is not None:
        module["module_effective_score"] = normalized.get("module_effective_score")
    elif normalized.get("module_score") is not None:
        module["module_effective_score"] = normalized.get("module_score")
    module["onchain_valuation_v22"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("signal_stage") or normalized.get("onchain_valuation_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_fund_flow_v22(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "timeframe",
        "states",
        "fund_flow_state",
        "module_direction",
        "module_score",
        "module_effective_score",
        "risk_score",
        "confidence_score",
        "btc_implication",
        "scores",
        "support_drivers",
        "pressure_drivers",
        "early_warning_flags",
        "data_quality_flags",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        if key in {"module_direction", "module_score", "module_effective_score"}:
            value = profile.get(key)
            if value is None:
                value = module.get(key)
        else:
            value = module.get(key)
            if value is None:
                value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    normalized.setdefault("states", {})
    normalized.setdefault("scores", {})
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
    if normalized.get("module_effective_score") is not None:
        module["module_effective_score"] = normalized.get("module_effective_score")
    elif normalized.get("module_score") is not None:
        module["module_effective_score"] = normalized.get("module_score")
    module["fund_flow_v22"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("fund_flow_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_treasury_credit_v21(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "timeframe",
        "states",
        "treasury_credit_state",
        "module_direction",
        "module_score",
        "module_effective_score",
        "risk_score",
        "confidence_score",
        "confidence_adjustment",
        "btc_implication",
        "support_drivers",
        "pressure_drivers",
        "risk_drivers",
        "early_warning_flags",
        "data_quality_flags",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        if key in {"module_direction", "module_score", "module_effective_score"}:
            value = profile.get(key)
            if value is None:
                value = module.get(key)
        else:
            value = module.get(key)
            if value is None:
                value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
    if normalized.get("module_effective_score") is not None:
        module["module_effective_score"] = normalized.get("module_effective_score")
    elif normalized.get("module_score") is not None:
        module["module_effective_score"] = normalized.get("module_score")
    module["treasury_credit_v21"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("treasury_credit_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_dollar_liquidity_v21(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "data_freshness",
        "liquidity_level",
        "liquidity_impulse",
        "reserve_buffer",
        "liquidity_drain_pressure",
        "repo_funding_pressure",
        "btc_response_confirmation",
        "dollar_liquidity_state",
        "module_direction",
        "module_score",
        "module_effective_score",
        "risk_score",
        "confidence_score",
        "confidence_adjustment",
        "support_drivers",
        "pressure_drivers",
        "risk_drivers",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        if key in {"module_direction", "module_score", "module_effective_score"}:
            value = profile.get(key)
            if value is None:
                value = module.get(key)
        else:
            value = module.get(key)
            if value is None:
                value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    if normalized.get("module_direction") is not None:
        module["module_direction"] = normalized.get("module_direction")
        module["module_effective_direction"] = normalized.get("module_direction")
    if normalized.get("module_score") is not None:
        module["module_score"] = normalized.get("module_score")
    if normalized.get("module_effective_score") is not None:
        module["module_effective_score"] = normalized.get("module_effective_score")
    elif normalized.get("module_score") is not None:
        module["module_effective_score"] = normalized.get("module_score")
    module["dollar_liquidity_v21"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("dollar_liquidity_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_macro_radar_v3(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "timeframe_focus",
        "macro_trend_state",
        "btc_implication",
        "equity_beta",
        "rates_pressure",
        "dollar_pressure",
        "volatility_stress",
        "financial_stress",
        "commodity_context",
        "macro_impulse",
        "btc_relative_confirmation",
        "event_window",
        "risk_score",
        "confidence_adjustment",
        "support_drivers",
        "pressure_drivers",
        "risk_drivers",
        "invalidation_conditions",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    module["macro_radar_v3"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("macro_trend_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_crypto_breadth_v3(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "primary_question",
        "crypto_breadth_state",
        "btc_implication",
        "btc_trend_anchor",
        "breadth_participation",
        "market_cap_diffusion",
        "btc_vs_alt_leadership",
        "sector_risk_appetite",
        "breadth_quality",
        "support_drivers",
        "pressure_drivers",
        "risk_drivers",
        "context_notes",
        "confidence_adjustment",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    module["crypto_breadth_v3"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("crypto_breadth_state")
    if module.get("display_summary") is None:
        module["display_summary"] = normalized.get("summary")


def _project_event_policy_v21(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "dominant_event_type",
        "nearest_event_type",
        "nearest_event_ts",
        "nearest_event_hours",
        "event_window_phase",
        "event_short_term_state",
        "event_risk_lock_level",
        "penalty_channel",
        "risk_score",
        "confidence_adjustment",
        "trade_gate",
        "risk_drivers",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    if not isinstance(normalized.get("trade_gate"), dict):
        normalized["trade_gate"] = {
            "allow_new_position": True,
            "allow_add_position": True,
            "allow_breakout_entry": True,
            "allow_market_entry": True,
            "position_size_multiplier": 1.0,
            "require_wait_until_ts": None,
            "reason_code": "EVENT_NEUTRAL",
        }
        module["trade_gate"] = normalized["trade_gate"]
    module["module_direction"] = "neutral"
    module["module_score"] = 0.0
    module["module_effective_score"] = 0.0
    module["support_drivers"] = []
    module["pressure_drivers"] = []
    module["event_policy_v21"] = normalized
    module.setdefault("display_state", normalized.get("event_short_term_state"))
    module.setdefault("display_summary", normalized.get("summary"))


def _project_options_volatility_v21(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "module_purpose",
        "options_short_term_state",
        "risk_score",
        "confidence_adjustment",
        "trade_permission_hint",
        "volatility_regime",
        "protection_demand",
        "tail_risk",
        "expiry_pressure",
        "pinning_structure",
        "data_quality",
        "risk_drivers",
        "context_notes",
        "summary",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)
    module["module_direction"] = "neutral"
    module["module_score"] = 0.0
    module["module_effective_score"] = 0.0
    module["support_drivers"] = []
    module["pressure_drivers"] = []
    module["options_volatility_v21"] = normalized
    module.setdefault("display_state", normalized.get("options_short_term_state"))
    module.setdefault("display_summary", normalized.get("summary"))


def _project_btc_total_state_v2(
    module: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    keys = (
        "direction_driver_scope",
        "context_only_scope",
        "price_state",
        "perp_state",
        "cycle_context",
        "audit_context",
        "btc_short_term_state",
        "context_notes",
        "audit_notes",
    )
    normalized: dict[str, Any] = {
        "semantic_profile_version": module.get("semantic_profile_version")
        or profile.get("semantic_profile_version"),
    }
    for key in keys:
        value = module.get(key)
        if value is None:
            value = profile.get(key)
        normalized[key] = value
        module.setdefault(key, value)

    support_drivers = [
        item
        for item in (module.get("support_drivers") or profile.get("support_drivers") or [])
        if _btc_total_driver_allowed(item)
    ]
    pressure_drivers = [
        item
        for item in (module.get("pressure_drivers") or profile.get("pressure_drivers") or [])
        if _btc_total_driver_allowed(item)
    ]
    normalized["support_drivers"] = support_drivers
    normalized["pressure_drivers"] = pressure_drivers
    module["support_drivers"] = support_drivers
    module["pressure_drivers"] = pressure_drivers
    module["btc_total_state_v2"] = normalized
    if module.get("display_state") is None:
        module["display_state"] = normalized.get("btc_short_term_state")
    if module.get("display_summary") is None:
        module["display_summary"] = _btc_total_display_summary(normalized)


def _btc_total_driver_allowed(driver: Any) -> bool:
    if not isinstance(driver, dict):
        return False
    metric_id = str(driver.get("metric_id") or "")
    return metric_id not in {
        "btc_halving_estimated_days",
        "btc_halving_blocks_remaining",
        "btc_block_height",
    }


def _btc_total_display_summary(normalized: dict[str, Any]) -> str | None:
    state = str(normalized.get("btc_short_term_state") or "")
    if not state:
        return None
    return {
        "price_up_confirmed": "BTC short-term price strength is confirmed by perp participation.",
        "short_covering_bounce": "BTC is bouncing while OI falls, so confirmation is weaker.",
        "overheated_upside": "BTC direction is still bullish, but perp crowding risk is elevated.",
        "long_crowding_downside": "BTC downside pressure is reinforced by crowded long positioning.",
        "deleveraging_downside": "BTC is under pressure while leverage is being released.",
        "short_squeeze_potential": "Negative funding creates squeeze potential, not standalone trend confirmation.",
        "neutral_wait_confirm": "BTC short-term state is waiting for price and perp confirmation.",
    }.get(state, state)


def _display_summary_fallback(module: dict[str, Any]) -> str | None:
    if str(module.get("radar_module")) != "kline_orderflow":
        return None
    trend_state = str(module.get("trend_state") or "")
    effective_bias = str(module.get("module_effective_bias") or "")
    if trend_state == "neutral_wait_confirm":
        if effective_bias in {"mild_pressure", "pressure", "strong_pressure"}:
            return "Short-term pressure exists, but kline structure still waits for confirmation."
        if effective_bias in {"mild_support", "support", "strong_support"}:
            return "Short-term support exists, but kline structure still waits for confirmation."
        return "Kline structure is waiting for confirmation."
    if trend_state == "bullish_confirmation":
        return "Kline structure confirms short-term bullish participation."
    if trend_state == "bearish_pressure":
        return "Kline structure confirms short-term downside pressure."
    return None


def _top_contributor_reason(module: dict[str, Any]) -> str | None:
    contributors = module.get("top_contributors")
    if not isinstance(contributors, list):
        return None
    for contributor in contributors:
        if isinstance(contributor, dict):
            reason = contributor.get("reason") or contributor.get("score_reason") or contributor.get("metric_explanation")
            if reason:
                return str(reason)
    return None


def _latest_radar_runtime(db: Database = database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        return RadarRuntimeRepository(session).latest_runtime_snapshot()


def _latest_runtime_modules(db: Database = database) -> list[dict[str, Any]]:
    db.init_schema()
    with db.session() as session:
        return RadarRuntimeRepository(session).latest_module_snapshots()


def _runtime_module_for(module_id: str, db: Database = database) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in _latest_runtime_modules(db)
            if str(item.get("module_name") or item.get("module_id")) == module_id
        ),
        None,
    )


def _p2_radar_output(
    module_id: str,
    *,
    p2_radar_run_id: str,
    db: Database,
) -> dict[str, Any] | None:
    if not p2_radar_run_id:
        return None
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.RadarOutput)
            .where(
                schema.RadarOutput.run_id == p2_radar_run_id,
                schema.RadarOutput.module_id == module_id,
            )
            .order_by(schema.RadarOutput.updated_at.desc(), schema.RadarOutput.id.desc())
            .limit(1)
        )
    if row is None:
        return None
    return {
        "run_id": row.run_id,
        "module_id": row.module_id,
        "signal": row.signal,
        "strength": row.strength,
        "confidence": row.confidence,
        "data_quality": row.data_quality,
        "evidence_summary": row.evidence_summary or {},
        "conflicting_evidence": row.conflicting_evidence or {},
        "risk_flags": row.risk_flags or {},
        "invalidation_signals": row.invalidation_signals or {},
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _radar_detail_summary(module: dict[str, Any], metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "module_id": module.get("module_id") or module.get("radar_module"),
        "score": module.get("module_effective_score") or module.get("module_score"),
        "direction": module.get("module_effective_direction") or module.get("module_direction"),
        "strength": module.get("module_strength") or module.get("strength"),
        "confidence": module.get("confidence_score") or module.get("confidence"),
        "quality": module.get("module_quality_score") or module.get("quality_score"),
        "metric_count": len(metrics),
        "support_count": len(module.get("support_drivers") or []),
        "pressure_count": len(module.get("pressure_drivers") or []),
        "fallback_metric_count": sum(1 for item in metrics if item.get("fallback_used")),
        "stale_metric_count": sum(1 for item in metrics if item.get("is_stale")),
    }


def _radar_source_freshness(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source_ids": sorted(
            {
                str(item.get("source_id"))
                for item in metrics
                if item.get("source_id")
            }
        ),
        "fresh_count": sum(1 for item in metrics if item.get("is_stale") is False),
        "stale_count": sum(1 for item in metrics if item.get("is_stale") is True),
        "missing_source_ts_count": sum(1 for item in metrics if not item.get("source_ts")),
        "max_freshness_minutes": _max_numeric(item.get("freshness_minutes") for item in metrics),
        "fallback_count": sum(1 for item in metrics if item.get("fallback_used")),
        "unavailable_count": sum(1 for item in metrics if item.get("available") is False),
    }


def _radar_metric_weighting(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "freshness_weights": {
            str(item.get("metric_id")): item.get("freshness_weight")
            for item in metrics
            if item.get("metric_id")
        },
        "horizon_weights": {
            str(item.get("metric_id")): item.get("horizon_weight")
            for item in metrics
            if item.get("metric_id")
        },
        "duplicate_adjustments": {
            str(item.get("metric_id")): item.get("duplicate_adjustment")
            for item in metrics
            if item.get("metric_id")
        },
        "horizon_tags": {
            str(item.get("metric_id")): item.get("horizon_tags")
            for item in metrics
            if item.get("metric_id")
        },
    }


def _max_numeric(values: Any) -> float | None:
    nums: list[float] = []
    for value in values:
        try:
            if value is not None:
                nums.append(float(value))
        except (TypeError, ValueError):
            continue
    return max(nums) if nums else None


def _trade_structure_summary(module: dict[str, Any]) -> str:
    state = str(module.get("trade_structure_state") or "mixed_structure")
    price = str(module.get("price_response_state") or "unknown")
    if state == "buy_pressure_unconfirmed":
        return "主动买盘强但价格响应未确认。"
    if state == "absorption_or_trapped_long":
        return "主动买盘强但价格没有跟涨，疑似被吸收或多头被困。"
    if state == "short_squeeze_chase_risk":
        return "短空清算推动价格响应，追涨风险升高。"
    return f"交易结构状态为 {state}，价格响应为 {price}。"


def latest_dashboard(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.")

    evidence = _metric_evidence(final_payload, bundle["pack_payload"])
    modules = [_project_module(item) for item in final_payload.get("radar_module_scores") or []]
    runtime = _latest_radar_runtime(db)
    return ok_response({
        "schema_version": "p45.dashboard.v1",
        "run_lineage": _run_lineage(final_payload, bundle),
        "final_view": final_payload.get("final_view"),
        "final_view_cn": final_payload.get("final_view_cn"),
        "legacy_core_view": final_payload.get("legacy_core_view") or final_payload.get("core_view"),
        "decision_card": final_payload.get("decision_card") or {},
        "btc_trend_cockpit": final_payload.get("btc_trend_cockpit") or {},
        "btc_runtime_cockpit": (runtime or {}).get("btc_runtime_cockpit") or {},
        "radar_runtime": runtime or {},
        "radar_runtime_health": (runtime or {}).get("health") or {},
        "btc_timescale_judge": final_payload.get("btc_timescale_judge") or {},
        "btc_timescale_replay_snapshot": final_payload.get("btc_timescale_replay_snapshot") or {},
        "direct_trend_api": _direct_trend_api_contract(final_payload, runtime),
        "event_window_v3": final_payload.get("event_window_v3") or {},
        "aggregation_audit": final_payload.get("aggregation_audit") or {},
        "horizon_views": final_payload.get("horizon_views") or {},
        "pressure_notes": final_payload.get("pressure_notes") or [],
        "contract_validation": final_payload.get("contract_validation") or {},
        "data_quality": final_payload.get("data_quality") or {},
        "event_policy_explanation": final_payload.get("event_policy_explanation") or {},
        "options_volatility_explanation": final_payload.get("options_volatility_explanation") or {},
        "btc_total_state_explanation": final_payload.get("btc_total_state_explanation") or {},
        "crypto_breadth_explanation": final_payload.get("crypto_breadth_explanation") or {},
        "macro_radar_explanation": final_payload.get("macro_radar_explanation") or {},
        "dollar_liquidity_explanation": final_payload.get("dollar_liquidity_explanation") or {},
        "onchain_valuation_explanation": final_payload.get("onchain_valuation_explanation") or {},
        "btc_adoption_explanation": final_payload.get("btc_adoption_explanation") or {},
        "asia_risk_explanation": final_payload.get("asia_risk_explanation") or {},
        "kline_orderflow_explanation": final_payload.get("kline_orderflow_explanation") or {},
        "trade_structure_flow_explanation": final_payload.get("trade_structure_flow_explanation") or {},
        "derivatives_crowding_explanation": final_payload.get("derivatives_crowding_explanation") or {},
        "radar_module_count": len(modules),
        "metric_evidence_count": len(evidence),
        "radar_modules": modules,
        "llm": _llm_summary(bundle["llm_research_payload"], bundle["llm_analyst_payload"]),
        "audit_reports": audit_reports(),
    }, schema_version="p45.dashboard.v1")


def latest_overview(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.")
    runtime = _latest_radar_runtime(db)
    aggregation_audit = final_payload.get("aggregation_audit") or {}
    return ok_response({
        "run_lineage": _run_lineage(final_payload, bundle),
        "final_view": final_payload.get("final_view"),
        "final_view_cn": final_payload.get("final_view_cn"),
        "decision_card": final_payload.get("decision_card") or {},
        "btc_trend_cockpit": final_payload.get("btc_trend_cockpit") or {},
        "btc_runtime_cockpit": (runtime or {}).get("btc_runtime_cockpit") or {},
        "radar_runtime": runtime or {},
        "btc_timescale_judge": final_payload.get("btc_timescale_judge") or {},
        "btc_timescale_replay_snapshot": final_payload.get("btc_timescale_replay_snapshot") or {},
        "direct_trend_api": _direct_trend_api_contract(final_payload, runtime),
        "event_window_v3": final_payload.get("event_window_v3") or {},
        "aggregation_audit": aggregation_audit,
        "why_not_strong": (
            final_payload.get("why_not_strong")
            or aggregation_audit.get("why_not_strong")
            or []
        ),
        "score_normalization": aggregation_audit.get("score_normalization") or {},
        "support_drivers": aggregation_audit.get("support_drivers") or [],
        "pressure_drivers": aggregation_audit.get("pressure_drivers") or [],
        "dominant_drivers": aggregation_audit.get("dominant_drivers") or [],
        "conflicting_evidence": (
            final_payload.get("conflicting_evidence")
            or aggregation_audit.get("conflicting_evidence")
            or {}
        ),
        "confidence_explanation": (
            final_payload.get("confidence_explanation")
            or aggregation_audit.get("confidence_explanation")
            or {}
        ),
        "watch_rules": (
            final_payload.get("watch_rules")
            or aggregation_audit.get("watch_rules")
            or []
        ),
        "horizon_views": final_payload.get("horizon_views") or {},
        "pressure_notes": final_payload.get("pressure_notes") or [],
        "invalidation_rules": final_payload.get("invalidation_rules") or [],
        "confirmation_rules": final_payload.get("confirmation_rules") or [],
        "research_article": final_payload.get("research_article") or {},
        "publish_article": final_payload.get("publish_article") or {},
    }, schema_version="p45.overview.v1")


def latest_radar_modules(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.") | {"modules": []}
    runtime_modules = _latest_runtime_modules(db)
    modules = [_project_module(item) for item in final_payload.get("radar_module_scores") or []]
    return ok_response({
        "run_lineage": _run_lineage(final_payload, bundle),
        "count": len(modules),
        "modules": modules,
        "radar_modules": modules,
        "runtime_modules": runtime_modules,
        "radar_runtime": _latest_radar_runtime(db) or {},
    }, schema_version="p45.radar_modules.v1")


def radar_module_detail(module_id: str, db: Database = database) -> dict[str, Any] | None:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return None

    modules = [_project_module(item) for item in final_payload.get("radar_module_scores") or []]
    module = next(
        (
            item
            for item in modules
            if str(item.get("radar_module") or item.get("module_id")) == module_id
        ),
        None,
    )
    if module is None:
        return None
    metrics = [
        item
        for item in _metric_evidence(final_payload, bundle["pack_payload"])
        if str(item.get("radar_module") or item.get("module_id")) == module_id
    ]
    lineage = _run_lineage(final_payload, bundle)
    runtime_module = _runtime_module_for(module_id, db=db)
    p2_output = _p2_radar_output(
        module_id,
        p2_radar_run_id=str(lineage.get("p2_radar_run_id") or ""),
        db=db,
    )
    return ok_response({
        "run_lineage": lineage,
        "module_id": module_id,
        "module": module,
        "summary": _radar_detail_summary(module, metrics),
        "support_drivers": module.get("support_drivers") or [],
        "pressure_drivers": module.get("pressure_drivers") or [],
        "conflict_drivers": module.get("conflict_drivers") or [],
        "source_freshness": _radar_source_freshness(metrics),
        "weighting": _radar_metric_weighting(metrics),
        "p2_radar_output": p2_output or {},
        "runtime_module": runtime_module or {},
        "module_json": module,
        "metrics": metrics,
    }, schema_version="p45.radar_module_detail.v1")


def latest_evidence(
    module_id: str | None = None,
    metric_id: str | None = None,
    limit: int = 500,
    db: Database = database,
) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.") | {"items": []}
    items = _metric_evidence(final_payload, bundle["pack_payload"])
    if module_id:
        items = [
            item
            for item in items
            if str(item.get("radar_module") or item.get("module_id")) == module_id
        ]
    if metric_id:
        items = [item for item in items if str(item.get("metric_id")) == metric_id]
    return ok_response({
        "run_lineage": _run_lineage(final_payload, bundle),
        "count": len(items),
        "items": items[: max(1, min(limit, 1000))],
    }, schema_version="p45.evidence.v1")


def evidence_detail(
    evidence_id: str,
    final_run_id: str | None = None,
    pack_id: str | None = None,
    allow_stale_fallback: bool = False,
    db: Database = database,
) -> dict[str, Any] | None:
    bundle = _bundle_for_scope(final_run_id=final_run_id, pack_id=pack_id, db=db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return None
    items = _metric_evidence(final_payload, bundle["pack_payload"])
    for item in items:
        if str(item.get("evidence_id")) == evidence_id:
            return ok_response({
                "run_lineage": _run_lineage(final_payload, bundle),
                "evidence": item,
                "claim": _evidence_claim(item),
                "data": _evidence_data(item),
                "interpretation": _evidence_interpretation(item),
                "resolution": {
                    "status": "historical_exact" if final_run_id or pack_id else "exact",
                    "requested_evidence_id": evidence_id,
                    "resolved_evidence_id": evidence_id,
                    "resolved_by": "scoped_exact" if final_run_id or pack_id else "latest_exact",
                    "stale": False,
                    "warning": None,
                },
            }, schema_version="p45.evidence_detail.v2")
    if allow_stale_fallback:
        scope = _parse_evidence_scope(evidence_id, items)
        if scope:
            latest = latest_bundle(db)
            latest_final = latest["final_payload"]
            if latest_final is not None:
                for item in _metric_evidence(latest_final, latest["pack_payload"]):
                    if (
                        str(item.get("radar_module") or item.get("module_id")) == scope["module_id"]
                        and str(item.get("metric_id")) == scope["metric_id"]
                    ):
                        return ok_response({
                            "run_lineage": _run_lineage(latest_final, latest),
                            "evidence": item,
                            "claim": _evidence_claim(item),
                            "data": _evidence_data(item),
                            "interpretation": _evidence_interpretation(item),
                            "resolution": {
                                "status": "stale_metric_fallback",
                                "requested_evidence_id": evidence_id,
                                "resolved_evidence_id": item.get("evidence_id"),
                                "resolved_by": "latest_module_metric",
                                "stale": True,
                                "warning": "Requested evidence id was not found in scope; resolved by module_id and metric_id in latest completed run.",
                            },
                        }, schema_version="p45.evidence_detail.v2")
    return None


def latest_articles(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.")
    return ok_response({
        "run_lineage": _run_lineage(final_payload, bundle),
        "final_view": final_payload.get("final_view"),
        "decision_card": final_payload.get("decision_card") or {},
        "contract_validation": final_payload.get("contract_validation") or {},
        "data_quality": final_payload.get("data_quality") or {},
        "research_article": final_payload.get("research_article") or {},
        "publish_article": final_payload.get("publish_article") or {},
        "deterministic_article": final_payload.get("article"),
        "llm_research_metadata": _llm_research_metadata(bundle["llm_research_payload"]),
        "deterministic_analyst_metadata": _analyst_metadata(bundle["analyst_payload"]),
        "llm_analyst_metadata": _llm_analyst_metadata(bundle["llm_analyst_payload"]),
        "llm_research": bundle["llm_research_payload"] or {},
        "analyst_articles": (bundle["analyst_payload"] or {}).get("analyst_articles", []),
        "llm_analyst_articles": (bundle["llm_analyst_payload"] or {}).get(
            "analyst_articles", []
        ),
    }, schema_version="p45.articles.v1")


def article_history(limit: int = 20, db: Database = database) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID)
            .order_by(schema.ModuleJsonOutput.created_at.desc())
            .limit(max(1, min(limit, 100)))
        ).all()

    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.payload or {})
        research_article = payload.get("research_article") or {}
        publish_article = payload.get("publish_article") or {}
        contract = payload.get("contract_validation") or {}
        data_quality = payload.get("data_quality") or {}
        items.append(
            {
                "final_run_id": payload.get("final_run_id") or row.run_id,
                "article_run_id": payload.get("article_run_id"),
                "pack_id": payload.get("pack_id"),
                "llm_research_run_id": payload.get("llm_research_run_id"),
                "llm_analyst_run_id": payload.get("llm_analyst_run_id"),
                "collect_run_id": payload.get("collect_run_id"),
                "p2_radar_run_id": payload.get("p2_radar_run_id"),
                "p3_run_id": payload.get("p3_run_id"),
                "created_at": payload.get("created_at") or row.created_at.isoformat(),
                "runtime_mode": payload.get("runtime_mode"),
                "final_view": payload.get("final_view"),
                "final_view_cn": payload.get("final_view_cn"),
                "article_status": "published"
                if publish_article.get("safe_to_publish") is True
                else "draft",
                "contract_status": contract.get("status"),
                "data_quality_level": data_quality.get("data_quality_level")
                or data_quality.get("quality_level"),
                "title": publish_article.get("title")
                or research_article.get("title")
                or "P4.5 research article",
                "summary": research_article.get("executive_summary")
                or payload.get("final_view_cn")
                or payload.get("final_view"),
            }
        )

    return ok_response(
        {
            "items": items,
            "count": len(items),
        },
        schema_version="p45.article_history.v1",
    )


def latest_invalidation(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.") | {
            "invalidation_rules": [],
            "confirmation_rules": [],
        }
    legacy = {
        "invalidation_rules": _project_invalidation_rules(
            final_payload.get("invalidation_rules") or [],
            rule_kind="invalidation",
        ),
        "confirmation_rules": _project_invalidation_rules(
            final_payload.get("confirmation_rules") or [],
            rule_kind="confirmation",
        ),
    }
    workbench = final_payload.get("invalidation_workbench")
    if isinstance(workbench, dict) and workbench.get("schema_version") == "p45.invalidation_workbench.v2":
        return ok_response({
            **workbench,
            "run_lineage": workbench.get("run_lineage") or _run_lineage(final_payload, bundle),
            "final_view": final_payload.get("final_view"),
            "invalidation_rules": legacy["invalidation_rules"],
            "confirmation_rules": legacy["confirmation_rules"],
            "legacy": workbench.get("legacy") or legacy,
        }, schema_version="p45.invalidation_workbench.v2")
    return ok_response({
        "run_lineage": _run_lineage(final_payload, bundle),
        "final_view": final_payload.get("final_view"),
        "validation_state": "watching",
        "validation_reason": "Workbench v2 payload is missing; falling back to legacy P4.5 rules.",
        **legacy,
    }, schema_version="p45.invalidation.v1")


def latest_data_quality(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.")
    lineage = _run_lineage(final_payload, bundle)
    data_quality = final_payload.get("data_quality") or {}
    quality_aux = _quality_aux_snapshot(
        db,
        collect_run_id=str(lineage.get("collect_run_id") or ""),
        llm_summary=_llm_summary(bundle["llm_research_payload"], bundle["llm_analyst_payload"]),
    )
    metric_count_audit = _metric_count_audit(
        db,
        collect_run_id=str(lineage.get("collect_run_id") or ""),
        p3_run_id=str(lineage.get("p3_run_id") or ""),
        data_quality=data_quality,
    )
    return ok_response({
        "run_lineage": lineage,
        "data_quality": {
            **data_quality,
            "metric_count_audit": metric_count_audit,
        },
        "quality_boundary": {
            "p1": quality_aux["p1"],
            "p2": quality_aux["p2"],
            "p3": {
                "run_mode_integrity": "see run_mode_integrity",
                "metric_count_audit": metric_count_audit,
            },
            "p45": {
                "contract_validation": final_payload.get("contract_validation") or {},
                "html_contract": final_payload.get("html_contract") or {},
            },
            "llm": quality_aux["llm"],
        },
        "fallback_events": quality_aux["fallback_events"],
        "rate_limit_events": quality_aux["rate_limit_events"],
        "module_discounts": quality_aux["module_discounts"],
        "data_quality_snapshot": quality_aux["data_quality_snapshot"],
        "metric_count_audit": metric_count_audit,
        "contract_validation": final_payload.get("contract_validation") or {},
        "html_contract": final_payload.get("html_contract") or {},
        "source_health": _source_health_snapshot(
            db,
            collect_run_id=str(lineage.get("collect_run_id") or ""),
        ),
        "run_mode_integrity": _run_mode_integrity_snapshot(
            db,
            collect_run_id=str(lineage.get("collect_run_id") or ""),
        ),
    }, schema_version="p45.data_quality.v1")


def latest_alerts(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"] or {}
    invalidation_rules = _project_invalidation_rules(
        final_payload.get("invalidation_rules") or [],
        rule_kind="invalidation",
    )
    confirmation_rules = _project_invalidation_rules(
        final_payload.get("confirmation_rules") or [],
        rule_kind="confirmation",
    )
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.AlgorithmAlert)
            .order_by(schema.AlgorithmAlert.updated_at.desc())
            .limit(50)
        ).all()
    return ok_response(
        {
            "run_lineage": _run_lineage(final_payload, bundle) if final_payload else {},
            "alerts": [
                {
                    "alert_id": row.alert_id,
                    "run_id": row.run_id,
                    "level": row.level,
                    "state": row.state,
                    "title": row.title,
                    "summary": row.summary,
                    "evidence_count": row.evidence_count,
                    "cooldown_until": row.cooldown_until.isoformat()
                    if row.cooldown_until
                    else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    "supporting_evidence": [],
                    "conflicting_evidence": [],
                    "escalation_conditions": confirmation_rules,
                    "downgrade_conditions": invalidation_rules,
                    "invalidation_context": {
                        "invalidation_rules": invalidation_rules,
                        "confirmation_rules": confirmation_rules,
                    },
                }
                for row in rows
            ],
            "count": len(rows),
            "invalidation_context": {
                "invalidation_rules": invalidation_rules,
                "confirmation_rules": confirmation_rules,
            },
        },
        schema_version="p3.alerts.v1",
    )


def _project_invalidation_rules(
    rules: list[Any],
    *,
    rule_kind: str,
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for raw in rules:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        conditions = item.get("conditions")
        if not isinstance(conditions, list):
            conditions = [conditions] if isinstance(conditions, dict) else []
        item["conditions"] = conditions
        item.setdefault("rule_kind", rule_kind)
        item.setdefault("expression", _rule_expression(item, conditions))
        item.setdefault(
            "action_if_triggered",
            item.get("action")
            or item.get("action_if_true")
            or ("reduce_confidence_or_flip_to_watch" if rule_kind == "invalidation" else "upgrade_confidence"),
        )
        item.setdefault("applies_when", item.get("scope") or item.get("applies_to") or "current_thesis")
        item.setdefault("horizon", item.get("timeframe") or item.get("window") or "multi")
        item.setdefault("module_id", item.get("module") or item.get("radar_module"))
        item.setdefault("metric_ids", _collect_rule_values(item, conditions, ("metric_id", "metric_ids")))
        item.setdefault("evidence_ids", _collect_rule_values(item, conditions, ("evidence_id", "evidence_ids")))
        item.setdefault("distance_to_trigger", item.get("distance") or item.get("trigger_distance"))
        item.setdefault("threshold", item.get("threshold") or _first_condition_value(conditions, "threshold"))
        item.setdefault(
            "current_value",
            item.get("current_value") or _first_condition_value(conditions, "current_value"),
        )
        projected.append(item)
    return projected


def _rule_expression(item: dict[str, Any], conditions: list[dict[str, Any]]) -> str:
    expression = item.get("expression") or item.get("human_expression") or item.get("title")
    if expression:
        return str(expression)
    parts: list[str] = []
    for condition in conditions:
        metric = condition.get("metric_id") or condition.get("field") or condition.get("name")
        operator = condition.get("operator") or condition.get("op") or "meets"
        threshold = condition.get("threshold")
        if metric:
            parts.append(f"{metric} {operator} {threshold}".strip())
    return " AND ".join(parts) if parts else str(item.get("rule_id") or item.get("condition_id") or "rule")


def _collect_rule_values(
    item: dict[str, Any],
    conditions: list[dict[str, Any]],
    keys: tuple[str, str],
) -> list[Any]:
    single_key, list_key = keys
    values: list[Any] = []
    raw_list = item.get(list_key)
    if isinstance(raw_list, list):
        values.extend(raw_list)
    elif raw_list:
        values.append(raw_list)
    if item.get(single_key):
        values.append(item.get(single_key))
    for condition in conditions:
        raw_condition_list = condition.get(list_key)
        if isinstance(raw_condition_list, list):
            values.extend(raw_condition_list)
        elif raw_condition_list:
            values.append(raw_condition_list)
        if condition.get(single_key):
            values.append(condition.get(single_key))
    deduped: list[Any] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _first_condition_value(conditions: list[dict[str, Any]], key: str) -> Any | None:
    for condition in conditions:
        if condition.get(key) is not None:
            return condition.get(key)
    return None


def latest_events(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"] or {}
    p3_run_id = final_payload.get("p3_run_id")
    db.init_schema()
    with db.session() as session:
        query = select(schema.FeatureValue).where(
            schema.FeatureValue.module_id == "p3_event_window_engine"
        )
        if p3_run_id:
            query = query.where(schema.FeatureValue.run_id == p3_run_id)
        rows = session.scalars(query.order_by(schema.FeatureValue.updated_at.desc()).limit(50)).all()
    return ok_response(
        {
            "run_lineage": _run_lineage(final_payload, bundle) if final_payload else {},
            "events": [
                {
                    "run_id": row.run_id,
                    "feature_id": row.feature_id,
                    "value": row.value,
                    "payload": row.metadata_json or {},
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ],
            "count": len(rows),
        },
        schema_version="p3.events.v1",
    )


def _quality_aux_snapshot(
    db: Database,
    *,
    collect_run_id: str,
    llm_summary: dict[str, Any],
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        quality_snapshot = session.scalar(
            select(schema.DataQualitySnapshot)
            .order_by(schema.DataQualitySnapshot.created_at.desc())
            .limit(1)
        )
        fallback_rows = session.scalars(
            select(schema.FallbackEvent)
            .order_by(schema.FallbackEvent.created_at.desc())
            .limit(50)
        ).all()
        rate_limit_rows = session.scalars(
            select(schema.RateLimitEvent)
            .order_by(schema.RateLimitEvent.created_at.desc())
            .limit(50)
        ).all()
        discount_rows = session.scalars(
            select(schema.ModuleDiscount)
            .order_by(schema.ModuleDiscount.created_at.desc())
            .limit(50)
        ).all()
        source_health_rows = session.scalars(
            select(schema.SourceHealthEvent)
            .order_by(schema.SourceHealthEvent.created_at.desc())
            .limit(50)
        ).all()
    fallback_events = [
        {
            "source_id": row.source_id,
            "fallback_source_id": row.fallback_source_id,
            "reason": row.reason,
            "discount": row.discount,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in fallback_rows
    ]
    rate_limit_events = [
        {
            "source_id": row.source_id,
            "current": row.current,
            "limit": row.limit,
            "reset_at": row.reset_at.isoformat() if row.reset_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rate_limit_rows
    ]
    module_discounts = [
        {
            "module_id": row.module_id,
            "reason": row.reason,
            "discount": row.discount,
            "source_id": row.source_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in discount_rows
    ]
    health_events = [
        {
            "source_id": row.source_id,
            "status": row.status,
            "quality_score": row.quality_score,
            "latency_ms": row.latency_ms,
            "message": row.message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in source_health_rows
    ]
    return {
        "data_quality_snapshot": {
            "run_id": quality_snapshot.run_id,
            "score": quality_snapshot.score,
            "status": quality_snapshot.status,
            "payload": quality_snapshot.payload or {},
            "created_at": quality_snapshot.created_at.isoformat()
            if quality_snapshot.created_at
            else None,
        }
        if quality_snapshot
        else None,
        "fallback_events": fallback_events,
        "rate_limit_events": rate_limit_events,
        "module_discounts": module_discounts,
        "p1": {
            "collect_run_id": collect_run_id or None,
            "source_health_events": health_events,
            "fallback_event_count": len(fallback_events),
            "rate_limit_event_count": len(rate_limit_events),
        },
        "p2": {
            "historical_fallback_count": len(fallback_events),
            "source_resolution": "latest_available",
            "conflict_count": 0,
            "module_discount_count": len(module_discounts),
        },
        "llm": llm_summary,
    }


def _redacted_payload_preview(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("key", "token", "secret", "authorization")):
            redacted[key] = "***redacted***"
        elif isinstance(value, dict):
            redacted[key] = _redacted_payload_preview(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redacted_payload_preview(item) if isinstance(item, dict) else item
                for item in value[:5]
            ]
        else:
            redacted[key] = value
    return redacted


def source_detail(source_id: str, db: Database = database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        source = session.scalar(select(schema.Source).where(schema.Source.source_id == source_id))
        if source is None:
            return None
        runs = session.scalars(
            select(schema.SourceRun)
            .where(schema.SourceRun.source_id == source_id)
            .order_by(schema.SourceRun.created_at.desc())
            .limit(20)
        ).all()
        raw = session.scalars(
            select(schema.RawObservation)
            .where(schema.RawObservation.source_id == source_id)
            .order_by(schema.RawObservation.observed_at.desc())
            .limit(5)
        ).all()
        metrics = session.scalars(
            select(schema.MetricValue)
            .where(schema.MetricValue.source_id == source_id)
            .order_by(schema.MetricValue.ts.desc())
            .limit(50)
        ).all()
        fallbacks = session.scalars(
            select(schema.FallbackEvent)
            .where(
                (schema.FallbackEvent.source_id == source_id)
                | (schema.FallbackEvent.fallback_source_id == source_id)
            )
            .order_by(schema.FallbackEvent.created_at.desc())
            .limit(20)
        ).all()
        rate_limits = session.scalars(
            select(schema.RateLimitEvent)
            .where(schema.RateLimitEvent.source_id == source_id)
            .order_by(schema.RateLimitEvent.created_at.desc())
            .limit(20)
        ).all()
        discounts = session.scalars(
            select(schema.ModuleDiscount)
            .where(schema.ModuleDiscount.source_id == source_id)
            .order_by(schema.ModuleDiscount.created_at.desc())
            .limit(20)
        ).all()
    return ok_response(
        {
            "source": {
                "source_id": source.source_id,
                "name": source.name,
                "group_name": source.group_name,
                "method": source.method,
                "priority": source.priority,
                "status": source.status,
                "fallback_source_id": source.fallback_source_id,
                "metadata": source.metadata_json or {},
            },
            "runs": [
                {
                    "run_id": row.run_id,
                    "mode": row.mode,
                    "status": row.status,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                    "latency_ms": row.latency_ms,
                    "error_message": row.error_message,
                }
                for row in runs
            ],
            "raw_observations": [
                {
                    "run_id": row.run_id,
                    "mode": row.mode,
                    "observed_at": row.observed_at.isoformat(),
                    "status": row.raw_payload.get("status"),
                    "error_message": row.raw_payload.get("error_message"),
                    "payload_keys": sorted((row.raw_payload or {}).keys()),
                    "payload_redacted": True,
                    "raw_payload": _redacted_payload_preview(row.raw_payload or {}),
                }
                for row in raw
            ],
            "metrics": [
                {
                    "metric_id": row.metric_id,
                    "run_id": row.run_id,
                    "run_mode": row.run_mode,
                    "ts": row.ts.isoformat(),
                    "value": row.value,
                    "quality_score": row.quality_score,
                    "is_fallback": row.is_fallback,
                }
                for row in metrics
            ],
            "fallback_chain": [
                {
                    "source_id": row.source_id,
                    "fallback_source_id": row.fallback_source_id,
                    "reason": row.reason,
                    "discount": row.discount,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in fallbacks
            ],
            "rate_limit_events": [
                {
                    "source_id": row.source_id,
                    "current": row.current,
                    "limit": row.limit,
                    "reset_at": row.reset_at.isoformat() if row.reset_at else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rate_limits
            ],
            "module_discounts": [
                {
                    "module_id": row.module_id,
                    "reason": row.reason,
                    "discount": row.discount,
                    "source_id": row.source_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in discounts
            ],
        },
        schema_version="p45.source_detail.v1",
    )


def settings_summary() -> dict[str, Any]:
    settings = get_settings()
    settings_contract = settings_contract_payload(settings)
    return ok_response(
        {
            "app": {
                "app_name": settings.app_name,
                "environment": settings.environment,
                "api_host": settings.api_host,
                "api_port": settings.api_port,
                "default_refresh_seconds": settings.default_refresh_seconds,
            },
            "run_defaults": {
                "run_mode": "live",
                "runtime_mode": "deterministic",
                "llm_runtime_mode": "llm",
            },
            "llm": {
                "p45_research_provider": settings.p45_research_provider,
                "deepseek_model": settings.deepseek_model,
                "p45_research_timeout_seconds": settings.p45_research_timeout_seconds,
                "p45_research_max_retries": settings.p45_research_max_retries,
                "has_deepseek_key": bool(settings.deepseek_api_key),
                "has_openai_key": bool(settings.openai_api_key),
                "has_qwen_key": bool(settings.qwen_api_key),
                "has_volcano_key": bool(settings.volcano_api_key),
                "has_kimi_key": bool(settings.kimi_api_key),
            },
            "providers": provider_registry_payload(settings),
            "provider_health": provider_health_snapshot(settings),
            "llm_routing": llm_routing_payload(settings),
            "settings_audit": settings_audit_summary(limit=10),
            "settings_contract": settings_contract,
            "runtime": settings_contract["runtime"],
            "data_sources": settings_contract["data_sources"],
            "paths": settings_contract["paths"],
        },
        schema_version="p45.settings.v1",
    )


def latest_llm(db: Database = database) -> dict[str, Any]:
    payload = _latest_payload(P45_LLM_RESEARCH_ARTICLE_MODULE_ID, db=db)
    if not payload:
        return missing_response("No P4.5 LLM research payload found.") | {"llm_research": {}}
    return ok_response({"llm_research": payload}, schema_version="p45.llm.v1")


def latest_analysts(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    deterministic = bundle["analyst_payload"] or {}
    llm = bundle["llm_analyst_payload"] or {}
    status = "ok" if deterministic or llm else "missing"
    if status == "missing":
        return missing_response("No P4.5 analyst payload found.") | {
            "deterministic": deterministic,
            "llm": llm,
        }
    return ok_response({
        "deterministic": deterministic,
        "llm": llm,
    }, schema_version="p45.analysts.v1")


def latest_runs(db: Database = database) -> dict[str, Any]:
    bundle = latest_bundle(db)
    final_payload = bundle["final_payload"]
    if final_payload is None:
        return missing_response("No P4.5 final report payload found.") | {"items": []}
    lineage = _run_lineage(final_payload, bundle)
    stages = _run_stages(final_payload, bundle)
    return ok_response({
        "latest": lineage,
        "run_lineage": lineage,
        "run_id": lineage.get("final_run_id"),
        "run_status": "completed",
        "progress": {
            "completed_stage_count": sum(1 for stage in stages if stage.get("status") == "completed"),
            "stage_count": len(stages),
            "current_stage": "completed",
        },
        "stages": stages,
        "logs": _run_log_summary(db, lineage),
        "audit_reports": audit_reports(run_id=str(lineage.get("final_run_id") or "")),
        "api_security": api_security_summary(limit=20, db=db),
    }, schema_version="p45.runs.v1")


def _direct_trend_api_contract(
    final_payload: dict[str, Any],
    runtime: dict[str, Any] | None,
) -> dict[str, Any]:
    judge = final_payload.get("btc_timescale_judge") or {}
    horizons = judge.get("horizons") or {}
    h4 = horizons.get("4h") or {}
    h1d = horizons.get("1d") or {}
    runtime_health = (runtime or {}).get("health") or {}
    return {
        "schema_version": judge.get("schema_version"),
        "snapshot_id": judge.get("snapshot_id"),
        "asof_ts": judge.get("asof_ts"),
        "source_layer": judge.get("source_layer"),
        "replay_snapshot": final_payload.get("btc_timescale_replay_snapshot") or {},
        "fallback_used": bool(judge.get("fallback_used")),
        "fallback_reason": judge.get("fallback_reason"),
        "runtime_fresh": runtime_health.get("runtime_fresh", _horizon_bool(h4.get("runtime_fresh"))),
        "source_fresh": judge.get("source_fresh"),
        "freshness_summary": judge.get("freshness_summary") or {},
        "module_level_radar_score": _module_level_radar_score(final_payload),
        "horizons": {
            "4h": _direct_horizon_api(h4),
            "1d": _direct_horizon_api(h1d),
        },
    }


def _direct_horizon_api(horizon: dict[str, Any]) -> dict[str, Any]:
    radar_context = horizon.get("radar_context") or {}
    event_trust = horizon.get("event_trust") or {}
    return {
        "state": horizon.get("state") or horizon.get("timescale_state"),
        "direction": horizon.get("direction"),
        "direct_trend_direction_score": _first_present(
            horizon,
            "direct_trend_direction_score",
            "direction_score",
        ),
        "direct_trend_acceptance_score": _first_present(
            horizon,
            "direct_trend_acceptance_score",
            "acceptance_score",
        ),
        "direct_trend_trust_score": _first_present(
            horizon,
            "direct_trend_trust_score",
            "trust_score",
        ),
        "direct_trend_display_score": horizon.get("display_score"),
        "event_trust_cap": _first_present(horizon, "event_trust_cap", default=event_trust.get("event_trust_cap")),
        "radar_context_bias": _first_present(horizon, "radar_context_bias", default=radar_context.get("bias")),
        "radar_context_status": radar_context.get("status"),
        "runtime_fresh": horizon.get("runtime_fresh"),
        "source_fresh": horizon.get("source_fresh"),
        "source_window": horizon.get("source_window") or {},
        "freshness_summary": horizon.get("freshness_summary") or {},
        "fallback_used": bool(horizon.get("fallback_used")),
        "fallback_reason": horizon.get("fallback_reason"),
    }


def _first_present(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return default


def _module_level_radar_score(final_payload: dict[str, Any]) -> float | None:
    audit = final_payload.get("aggregation_audit") or {}
    score = audit.get("directional_score")
    try:
        return None if score is None else float(score)
    except (TypeError, ValueError):
        return None


def _horizon_bool(value: Any) -> bool | str | None:
    if value in (True, False, "partial"):
        return value
    return None


def history_list(limit: int = 50, db: Database = database) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID)
            .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.payload or {})
        contract = payload.get("contract_validation") or {}
        data_quality = payload.get("data_quality") or {}
        items.append(
            {
                "final_run_id": payload.get("final_run_id") or row.run_id,
                "pack_id": payload.get("pack_id"),
                "article_run_id": payload.get("article_run_id"),
                "collect_run_id": payload.get("collect_run_id"),
                "p2_radar_run_id": payload.get("p2_radar_run_id"),
                "p3_run_id": payload.get("p3_run_id"),
                "created_at": payload.get("created_at") or row.created_at.isoformat(),
                "final_view": payload.get("final_view"),
                "final_view_cn": payload.get("final_view_cn"),
                "contract_status": contract.get("status"),
                "data_quality_level": data_quality.get("data_quality_level")
                or data_quality.get("quality_level"),
                "history_url": f"/api/p45/history/{payload.get('final_run_id') or row.run_id}",
            }
        )
    return ok_response(
        {
            "items": items,
            "count": len(items),
            "history_mode": {
                "anchor": "final_run_id",
                "read_only": True,
                "historical_payload_frozen": True,
            },
        },
        schema_version="p45.history_list.v1",
    )


def history(final_run_id: str, db: Database = database) -> dict[str, Any] | None:
    final_payload = _payload_by_run(P45_FINAL_ARTICLE_MODULE_ID, final_run_id, db=db)
    if final_payload is None:
        return None
    pack_payload = _payload_by_run(
        P45_EVIDENCE_PACK_MODULE_ID,
        str(final_payload.get("pack_id") or ""),
        db=db,
    )
    analyst_payload = _payload_by_run(
        P45_ANALYST_ARTICLES_MODULE_ID,
        str(final_payload.get("article_run_id") or ""),
        db=db,
    )
    llm_research_payload = _llm_research_payload_for_final(final_run_id, db=db)
    llm_analyst_payload = _llm_analyst_payload_for_pack(str(final_payload.get("pack_id") or ""), db=db)
    lineage = _run_lineage(
        final_payload,
        {
            "pack_payload": pack_payload,
            "analyst_payload": analyst_payload,
            "llm_research_payload": llm_research_payload,
            "llm_analyst_payload": llm_analyst_payload,
        },
    )
    modules = [_project_module(item) for item in final_payload.get("radar_module_scores") or []]
    return ok_response({
        "run_lineage": lineage,
        "history_mode": {
            "anchor": "final_run_id",
            "final_run_id": final_run_id,
            "read_only": True,
            "historical_payload_frozen": True,
            "uses_latest_runtime_state": False,
        },
        "created_at": final_payload.get("created_at"),
        "contract_status": (final_payload.get("contract_validation") or {}).get("status"),
        "run_mode_scope": {
            "default_query_scope": "live_only",
            "requested_run_mode": "live",
            "run_mode_all_requires_explicit_selection": True,
            "historical_payload_frozen": True,
        },
        "run_mode_integrity": _run_mode_integrity_snapshot(
            db,
            collect_run_id=str(lineage.get("collect_run_id") or ""),
        ),
        "final": final_payload,
        "btc_trend_cockpit": final_payload.get("btc_trend_cockpit") or {},
        "invalidation_workbench": final_payload.get("invalidation_workbench") or {},
        "btc_timescale_judge": final_payload.get("btc_timescale_judge") or {},
        "btc_timescale_replay_snapshot": final_payload.get("btc_timescale_replay_snapshot") or {},
        "direct_trend_api": _direct_trend_api_contract(final_payload, None),
        "event_window_v3": final_payload.get("event_window_v3") or {},
        "pack": pack_payload or {},
        "analysts": analyst_payload or {},
        "llm_research": llm_research_payload or {},
        "llm_analysts": llm_analyst_payload or {},
        "replay_scores": _replay_scores(final_run_id, db=db),
        "calibration_notes": _calibration_notes(final_run_id, db=db),
        "radar_modules": modules,
        "btc_total_state_explanation": final_payload.get("btc_total_state_explanation") or {},
        "options_volatility_explanation": final_payload.get("options_volatility_explanation") or {},
        "event_policy_explanation": final_payload.get("event_policy_explanation") or {},
        "crypto_breadth_explanation": final_payload.get("crypto_breadth_explanation") or {},
        "macro_radar_explanation": final_payload.get("macro_radar_explanation") or {},
        "dollar_liquidity_explanation": final_payload.get("dollar_liquidity_explanation") or {},
        "onchain_valuation_explanation": final_payload.get("onchain_valuation_explanation") or {},
        "btc_adoption_explanation": final_payload.get("btc_adoption_explanation") or {},
        "asia_risk_explanation": final_payload.get("asia_risk_explanation") or {},
        "kline_orderflow_explanation": final_payload.get("kline_orderflow_explanation") or {},
        "trade_structure_flow_explanation": final_payload.get("trade_structure_flow_explanation") or {},
        "derivatives_crowding_explanation": final_payload.get("derivatives_crowding_explanation") or {},
        "audit_reports": audit_reports(run_id=final_run_id),
    }, schema_version="p45.history.v1")


def _replay_scores(final_run_id: str, db: Database = database) -> list[dict[str, Any]]:
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.ReplayScore)
            .where(schema.ReplayScore.snapshot_id == final_run_id)
            .order_by(schema.ReplayScore.horizon)
        ).all()
    return [
        {
            "snapshot_id": row.snapshot_id,
            "horizon": row.horizon,
            "result_pct": row.result_pct,
            "score": row.score,
            "payload": row.payload or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def _calibration_notes(final_run_id: str, db: Database = database) -> list[dict[str, Any]]:
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.CalibrationNote)
            .where(schema.CalibrationNote.target == final_run_id)
            .order_by(schema.CalibrationNote.created_at.desc(), schema.CalibrationNote.id.desc())
            .limit(50)
        ).all()
    return [
        {
            "target": row.target,
            "note": row.note,
            "payload": row.payload or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "read_only": True,
            "production_weight_mutation": False,
        }
        for row in rows
    ]


def audit_reports(run_id: str | None = None) -> dict[str, Any]:
    reports_dir = paths.project_root / "reports"
    items: list[dict[str, Any]] = []
    for phase, pattern in REPORT_FILES.items():
        path = _find_report_path(reports_dir, pattern)
        if not path.exists():
            continue
        items.append(
            {
                "phase": phase,
                "report_type": "html",
                "title": _report_title(phase),
                "filename": path.name,
                "path": str(path),
                "relative_path": str(Path("reports") / path.name),
                "url": f"/reports/{path.name}",
                "file_url": path.resolve().as_uri(),
                "run_id": run_id,
                "status": "available",
                "size_bytes": path.stat().st_size,
                "updated_at": path.stat().st_mtime,
                "created_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
            }
        )
    return ok_response({
        "run_id": run_id,
        "reports": items,
        "count": len(items),
    }, schema_version="p45.audit_reports.v1")


def latest_bundle(db: Database = database) -> dict[str, Any]:
    final_payload = _latest_payload(P45_FINAL_ARTICLE_MODULE_ID, db=db)
    final_run_id = str((final_payload or {}).get("final_run_id") or "")
    pack_id = str((final_payload or {}).get("pack_id") or "")
    article_run_id = str((final_payload or {}).get("article_run_id") or "")
    return {
        "final_payload": final_payload,
        "pack_payload": _payload_by_run(P45_EVIDENCE_PACK_MODULE_ID, pack_id, db=db)
        if pack_id
        else _latest_payload(P45_EVIDENCE_PACK_MODULE_ID, db=db),
        "analyst_payload": _payload_by_run(
            P45_ANALYST_ARTICLES_MODULE_ID,
            article_run_id,
            db=db,
        )
        if article_run_id
        else _latest_payload(P45_ANALYST_ARTICLES_MODULE_ID, db=db),
        "llm_research_payload": _llm_research_payload_for_final(final_run_id, db=db),
        "llm_analyst_payload": _llm_analyst_payload_for_pack(pack_id, db=db),
    }


def _bundle_for_scope(
    final_run_id: str | None = None,
    pack_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    if not final_run_id and not pack_id:
        return latest_bundle(db)
    final_payload = (
        _payload_by_run(P45_FINAL_ARTICLE_MODULE_ID, final_run_id, db=db)
        if final_run_id
        else _final_payload_by_pack_id(str(pack_id or ""), db=db)
    )
    scoped_pack_id = str(pack_id or (final_payload or {}).get("pack_id") or "")
    scoped_final_run_id = str((final_payload or {}).get("final_run_id") or final_run_id or "")
    article_run_id = str((final_payload or {}).get("article_run_id") or "")
    return {
        "final_payload": final_payload,
        "pack_payload": _payload_by_run(P45_EVIDENCE_PACK_MODULE_ID, scoped_pack_id, db=db)
        if scoped_pack_id
        else None,
        "analyst_payload": _payload_by_run(
            P45_ANALYST_ARTICLES_MODULE_ID,
            article_run_id,
            db=db,
        )
        if article_run_id
        else None,
        "llm_research_payload": _llm_research_payload_for_final(scoped_final_run_id, db=db),
        "llm_analyst_payload": _llm_analyst_payload_for_pack(scoped_pack_id, db=db),
    }


def _final_payload_by_pack_id(pack_id: str, db: Database) -> dict[str, Any] | None:
    if not pack_id:
        return None
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID)
            .order_by(schema.ModuleJsonOutput.created_at.desc())
            .limit(100)
        ).all()
    for row in rows:
        payload = dict(row.payload or {})
        if str(payload.get("pack_id") or "") == pack_id:
            return payload
    return None


def _latest_payload(module_id: str, db: Database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.module_id == module_id)
            .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
            .limit(1)
        )
        return dict(row.payload or {}) if row else None


def _llm_research_payload_for_final(final_run_id: str, db: Database) -> dict[str, Any] | None:
    if not final_run_id:
        return None
    return _payload_by_payload_field(
        P45_LLM_RESEARCH_ARTICLE_MODULE_ID,
        "final_run_id",
        final_run_id,
        db=db,
    )


def _llm_analyst_payload_for_pack(pack_id: str, db: Database) -> dict[str, Any] | None:
    if not pack_id:
        return None
    return _payload_by_payload_field(
        P45_LLM_ANALYST_ARTICLES_MODULE_ID,
        "pack_id",
        pack_id,
        db=db,
    )


def _payload_by_payload_field(
    module_id: str,
    field_name: str,
    field_value: str,
    db: Database,
    limit: int = 100,
) -> dict[str, Any] | None:
    if not field_value:
        return None
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.module_id == module_id)
            .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
            .limit(limit)
        ).all()
    for row in rows:
        payload = dict(row.payload or {})
        if str(payload.get(field_name) or "") == field_value:
            return payload
    return None


def _parse_evidence_scope(
    evidence_id: str,
    items: list[dict[str, Any]],
) -> dict[str, str] | None:
    module_ids = {
        str(item.get("radar_module") or item.get("module_id") or "")
        for item in items
        if item.get("radar_module") or item.get("module_id")
    }
    for module_id in sorted(module_ids, key=len, reverse=True):
        marker = f"-{module_id}-"
        marker_index = evidence_id.find(marker)
        if marker_index >= 0:
            return {
                "module_id": module_id,
                "metric_id": evidence_id[marker_index + len(marker):],
            }
    return None


def _payload_by_run(module_id: str, run_id: str, db: Database) -> dict[str, Any] | None:
    if not run_id:
        return None
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(
                schema.ModuleJsonOutput.module_id == module_id,
                schema.ModuleJsonOutput.run_id == run_id,
            )
            .order_by(schema.ModuleJsonOutput.created_at.desc())
            .limit(1)
        )
        return dict(row.payload or {}) if row else None


def _metric_evidence(
    final_payload: dict[str, Any],
    pack_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    final_metrics = final_payload.get("metric_evidence")
    if isinstance(final_metrics, list):
        return [
            _project_evidence_item(_annotate_legacy_future_source_ts(dict(item)))
            for item in final_metrics
            if isinstance(item, dict)
        ]

    metrics: list[dict[str, Any]] = []
    for analyst in (pack_payload or {}).get("analysts", []):
        for module in analyst.get("modules", []):
            for item in module.get("metrics", []):
                if isinstance(item, dict):
                    metrics.append(
                        _project_evidence_item(_annotate_legacy_future_source_ts(dict(item)))
                    )
    return metrics


def _project_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    projected = dict(item)
    projected.setdefault("module_id", projected.get("radar_module"))
    projected.setdefault("metric_score", projected.get("metric_raw_score"))
    for field in (
        "metric_effective_score",
        "freshness_weight",
        "horizon_weight",
        "duplicate_adjustment",
        "horizon_tags",
        "duplicate_group_id",
        "source_ts",
        "collected_at",
        "freshness_minutes",
        "is_stale",
        "p45_metric_brief",
        "score_reason",
    ):
        projected.setdefault(field, None)
    projected.setdefault("claim", _evidence_claim(projected))
    projected.setdefault("data", _evidence_data(projected))
    projected.setdefault("interpretation", _evidence_interpretation(projected))
    return projected


def _evidence_claim(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "module_id": item.get("module_id") or item.get("radar_module"),
        "metric_id": item.get("metric_id"),
        "direction": item.get("direction"),
        "brief": item.get("p45_metric_brief"),
        "reason": item.get("score_reason") or item.get("reason"),
    }


def _evidence_data(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": item.get("value"),
        "source_id": item.get("source_id"),
        "source_ts": item.get("source_ts"),
        "collected_at": item.get("collected_at"),
        "freshness_minutes": item.get("freshness_minutes"),
        "is_stale": item.get("is_stale"),
        "freshness_status": item.get("freshness_status"),
        "available": item.get("available"),
    }


def _evidence_interpretation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_score": item.get("metric_score"),
        "metric_effective_score": item.get("metric_effective_score"),
        "freshness_weight": item.get("freshness_weight"),
        "horizon_weight": item.get("horizon_weight"),
        "duplicate_adjustment": item.get("duplicate_adjustment"),
        "horizon_tags": item.get("horizon_tags"),
        "duplicate_group_id": item.get("duplicate_group_id"),
        "score_reason": item.get("score_reason") or item.get("reason"),
    }


def _llm_research_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    return {
        "llm_research_run_id": payload.get("llm_research_run_id"),
        "final_run_id": payload.get("final_run_id"),
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "status": payload.get("status"),
    }


def _analyst_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    analyst_articles = payload.get("analyst_articles") or []
    return {
        "article_run_id": payload.get("article_run_id"),
        "pack_id": payload.get("pack_id"),
        "analyst_count": len(analyst_articles) if isinstance(analyst_articles, list) else 0,
        "status": payload.get("status"),
    }


def _llm_analyst_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    summary = payload.get("summary") or {}
    return {
        "llm_analyst_run_id": payload.get("llm_analyst_run_id"),
        "pack_id": payload.get("pack_id"),
        "provider": payload.get("provider"),
        "model": payload.get("model") or _first_analyst_model(payload),
        "status": payload.get("status"),
        "completed_count": summary.get("completed_count"),
        "failed_count": summary.get("failed_count"),
    }


def _parse_api_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _annotate_legacy_future_source_ts(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("metric_id") != "options_rv":
        return item
    source_ts = _parse_api_datetime(item.get("source_ts"))
    collected_at = _parse_api_datetime(item.get("collected_at"))
    if source_ts is None or collected_at is None or source_ts <= collected_at:
        return item
    item["legacy_future_source_ts"] = True
    item["freshness_display_status"] = "legacy_stale_future_source_ts"
    item["freshness_display_note"] = (
        "Legacy options_rv record has source_ts after collected_at; treat as stale "
        "historical display data, not current usable RV."
    )
    item["available"] = False
    item["is_stale"] = True
    item["freshness_status"] = item.get("freshness_status") or "expired"
    return item


def _source_health_snapshot(db: Database, collect_run_id: str = "") -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        sources = session.scalars(select(schema.Source).order_by(schema.Source.source_id)).all()
        recent_runs = session.scalars(
            select(schema.SourceRun).order_by(schema.SourceRun.created_at.desc()).limit(200)
        ).all()
        current_runs = []
        if collect_run_id:
            current_runs = session.scalars(
                select(schema.SourceRun)
                .where(schema.SourceRun.run_id == collect_run_id)
                .order_by(schema.SourceRun.created_at.desc())
            ).all()
    statuses: dict[str, int] = {}
    for source in sources:
        statuses[source.status] = statuses.get(source.status, 0) + 1
    current_failed = [row for row in current_runs if _source_run_failed(row)]
    current_warning = [
        row
        for row in current_runs
        if _source_run_warning(row) and not _source_run_failed(row)
    ]
    history_failed = [
        row
        for row in recent_runs
        if _source_run_failed(row) and (not collect_run_id or row.run_id != collect_run_id)
    ]
    failed_runs = [*current_failed, *history_failed]
    return {
        "source_count": len(sources),
        "status_counts": statuses,
        "recent_run_count": len(recent_runs),
        "current_run_id": collect_run_id or None,
        "current_run_source_count": len(current_runs),
        "current_run_failed_count": len(current_failed),
        "current_run_warning_count": len(current_warning),
        "history_recent_failed_count": len(history_failed),
        "recent_failed_run_count": len(failed_runs),
        "recent_failed_scope": "current_failures_plus_history_window",
        "current_run_failed_sources": [
            _source_run_summary(row, scope="current_run_failure")
            for row in current_failed[:20]
        ],
        "current_run_warning_sources": [
            _source_run_summary(row, scope="current_run_warning")
            for row in current_warning[:20]
        ],
        "history_recent_failed_sources": [
            _source_run_summary(row, scope="history_window_failure")
            for row in history_failed[:20]
        ],
        "recent_failed_sources": [
            _source_run_legacy_summary(row)
            for row in failed_runs[:20]
        ],
    }


def _source_run_legacy_summary(row: schema.SourceRun) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "run_id": row.run_id,
        "mode": row.mode,
        "status": row.status,
        "error_message": row.error_message,
    }


def _source_run_summary(row: schema.SourceRun, scope: str) -> dict[str, Any]:
    return {
        "source_id": row.source_id,
        "run_id": row.run_id,
        "mode": row.mode,
        "status": row.status,
        "error_message": row.error_message,
        "scope": scope,
    }


def _source_run_failed(row: schema.SourceRun) -> bool:
    status = str(row.status or "").lower()
    if _source_run_warning(row):
        return False
    if row.error_message:
        return True
    return status in {"failed", "error", "degraded", "unhealthy"}


def _source_run_warning(row: schema.SourceRun) -> bool:
    status = str(row.status or "").lower()
    return status in {"warning", "warn", "degraded_warning", "partial"}


def _metric_count_audit(
    db: Database,
    collect_run_id: str,
    p3_run_id: str,
    data_quality: dict[str, Any],
) -> dict[str, Any]:
    db.init_schema()
    derived_metrics = [
        "btc_1h_return_pct",
        "btc_4h_return_pct",
        "btc_24h_return_pct",
        "btc_price_vs_1h_close_pct",
        "btc_oi_change_1h_pct",
        "btc_oi_change_4h_pct",
        "btc_oi_change_24h_pct",
        "btc_oi_zscore",
        "btc_funding_band",
    ]
    with db.session() as session:
        collected_metric_count = (
            session.scalar(
                select(func.count(func.distinct(schema.MetricValue.metric_id))).where(
                    schema.MetricValue.run_id == collect_run_id
                )
            )
            if collect_run_id
            else 0
        )
        scored_evidence_count = (
            session.scalar(
                select(func.count()).where(
                    schema.FeatureValue.run_id == p3_run_id,
                    schema.FeatureValue.module_id == "p3_scored_metric_evidence",
                )
            )
            if p3_run_id
            else 0
        )
        derived_metric_count = (
            session.scalar(
                select(func.count(func.distinct(schema.MetricValue.metric_id))).where(
                    schema.MetricValue.run_id == collect_run_id,
                    schema.MetricValue.metric_id.in_(derived_metrics),
                )
            )
            if collect_run_id
            else 0
        )
    return {
        "collected_metric_count": int(collected_metric_count or 0),
        "scored_evidence_count": int(scored_evidence_count or data_quality.get("metric_count") or 0),
        "derived_metric_count": int(derived_metric_count or 0),
        "unavailable_metric_count": int(data_quality.get("unavailable_metric_count") or 0),
        "count_explanation": (
            "P1 collected_metric_count counts metrics written by the collection run, "
            "including derived metrics. P4.5 scored_evidence_count counts scored "
            "evidence records used by the report contract, so it may differ without "
            "indicating data loss."
        ),
    }


def _run_mode_integrity_snapshot(db: Database, collect_run_id: str = "") -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        history_rows = session.execute(
            select(schema.MetricValue.run_mode, func.count()).group_by(schema.MetricValue.run_mode)
        ).all()
        current_rows = []
        if collect_run_id:
            current_rows = session.execute(
                select(schema.MetricValue.run_mode, func.count())
                .where(schema.MetricValue.run_id == collect_run_id)
                .group_by(schema.MetricValue.run_mode)
            ).all()
        mixed_rows = session.execute(
            select(
                schema.MetricValue.metric_id,
                func.count(func.distinct(schema.MetricValue.run_mode)),
            )
            .group_by(schema.MetricValue.metric_id)
            .having(func.count(func.distinct(schema.MetricValue.run_mode)) > 1)
        ).all()
    history_counts = {str(mode or "unknown"): count for mode, count in history_rows}
    current_counts = {str(mode or "unknown"): count for mode, count in current_rows}
    current_non_live_count = (
        current_counts.get("mock", 0)
        + current_counts.get("test", 0)
        + current_counts.get("unknown", 0)
    )
    historical_mixed = bool(
        mixed_rows
        or history_counts.get("mock", 0)
        or history_counts.get("test", 0)
        or history_counts.get("unknown", 0)
    )
    return {
        "current_run": {
            "collect_run_id": collect_run_id,
            "live_count": current_counts.get("live", 0),
            "mock_count": current_counts.get("mock", 0),
            "test_count": current_counts.get("test", 0),
            "unknown_count": current_counts.get("unknown", 0),
            "live_only": bool(collect_run_id) and current_non_live_count == 0,
            "status": "passed" if current_non_live_count == 0 else "failed",
        },
        "history": {
            "live_metric_values": history_counts.get("live", 0),
            "mock_metric_values": history_counts.get("mock", 0),
            "test_metric_values": history_counts.get("test", 0),
            "unknown_metric_values": history_counts.get("unknown", 0),
            "mixed_metric_id_count": len(mixed_rows),
            "mixed_metric_ids": [metric_id for metric_id, _ in mixed_rows[:50]],
            "status": "warning" if historical_mixed else "passed",
        },
        "default_query_scope": "live_only",
        "history_replay_all_requires_explicit_run_mode": True,
        "production_blocker": current_non_live_count > 0,
    }


def _run_lineage(
    final_payload: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    return {
        "collect_run_id": final_payload.get("collect_run_id")
        or (bundle.get("pack_payload") or {}).get("collect_run_id"),
        "p2_radar_run_id": final_payload.get("p2_radar_run_id")
        or (bundle.get("pack_payload") or {}).get("p2_radar_run_id"),
        "p3_run_id": final_payload.get("p3_run_id")
        or (bundle.get("pack_payload") or {}).get("p3_run_id"),
        "pack_id": final_payload.get("pack_id") or (bundle.get("pack_payload") or {}).get("pack_id"),
        "article_run_id": final_payload.get("article_run_id")
        or (bundle.get("analyst_payload") or {}).get("article_run_id"),
        "final_run_id": final_payload.get("final_run_id"),
        "llm_research_run_id": (bundle.get("llm_research_payload") or {}).get(
            "llm_research_run_id"
        ),
        "llm_analyst_run_id": (bundle.get("llm_analyst_payload") or {}).get(
            "llm_analyst_run_id"
        ),
        "created_at": final_payload.get("created_at"),
        "runtime_mode": final_payload.get("runtime_mode"),
    }


def _run_stages(final_payload: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    lineage = _run_lineage(final_payload, bundle)
    reports = audit_reports(run_id=str(lineage.get("final_run_id") or "")).get("reports", [])
    report_by_phase = {item["phase"]: item for item in reports}
    stages = [
        ("p1", "P1 collect", lineage.get("collect_run_id")),
        ("p2", "P2 radar", lineage.get("p2_radar_run_id")),
        ("p3", "P3 scoring", lineage.get("p3_run_id")),
        ("p45", "P4.5 deterministic", lineage.get("final_run_id")),
        ("llm_research", "P4.5 LLM research", lineage.get("llm_research_run_id")),
        ("llm_analysts", "P4.5 analyst LLM", lineage.get("llm_analyst_run_id")),
    ]
    return [
        {
            "stage_id": stage_id,
            "label": label,
            "run_id": run_id,
            "status": "completed" if run_id else "missing",
            "worker_id": None,
            "retry_count": 0,
            "failed_retry_count": 0,
            "audit_report": report_by_phase.get(stage_id if stage_id in report_by_phase else "p45"),
        }
        for stage_id, label, run_id in stages
    ]


def _run_log_summary(db: Database, lineage: dict[str, Any]) -> list[dict[str, Any]]:
    run_ids = [
        str(value)
        for key, value in lineage.items()
        if key.endswith("_run_id") and value
    ]
    if not run_ids:
        return []
    db.init_schema()
    with db.session() as session:
        logs = session.scalars(
            select(schema.RunLog)
            .where(schema.RunLog.run_id.in_(run_ids))
            .order_by(schema.RunLog.created_at.desc(), schema.RunLog.id.desc())
            .limit(50)
        ).all()
    return [
        {
            "run_id": log.run_id,
            "stage_id": log.stage_name,
            "level": log.level,
            "message": log.message,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "metadata": log.metadata_json or {},
        }
        for log in logs
    ]


def _llm_summary(
    research_payload: dict[str, Any] | None,
    analyst_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    analyst_summary = (analyst_payload or {}).get("summary") or {}
    return {
        "research_status": (research_payload or {}).get("status"),
        "research_run_id": (research_payload or {}).get("llm_research_run_id"),
        "analyst_run_id": (analyst_payload or {}).get("llm_analyst_run_id"),
        "provider": (research_payload or {}).get("provider")
        or (analyst_payload or {}).get("provider"),
        "model": (research_payload or {}).get("model") or _first_analyst_model(analyst_payload),
        "analyst_completed_count": analyst_summary.get("completed_count", 0),
        "analyst_failed_count": analyst_summary.get("failed_count", 0),
        "internal_reference": True,
    }


def _first_analyst_model(payload: dict[str, Any] | None) -> str | None:
    for item in (payload or {}).get("analyst_articles", []):
        if item.get("model"):
            return str(item["model"])
    return None


def _report_title(phase: str) -> str:
    return {
        "p1": "P1 数据采集审计",
        "p2": "P2 Radar 质检报告",
        "p3": "P3 算法审计报告",
        "p45": "P4.5 研究报告",
    }.get(phase, phase.upper())


def _find_report_path(reports_dir: Path, pattern: str) -> Path:
    if "*" not in pattern:
        return reports_dir / pattern
    candidates = sorted(
        reports_dir.glob(pattern),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else reports_dir / pattern
