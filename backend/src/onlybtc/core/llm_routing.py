from __future__ import annotations

from typing import Any

from onlybtc.core.config import Settings, get_settings
from onlybtc.core.provider_registry import PROVIDER_REGISTRY
from onlybtc.p4.agent_runtime import ProviderConfig, provider_config

LLM_ROUTING_SCHEMA_VERSION = "p10.c05.llm_routing.v1"

P4_AGENT_ROUTES: tuple[tuple[str, str, str], ...] = (
    ("macro_event_analyst", "Macro Event Analyst", "p4_macro_event_provider"),
    ("liquidity_flow_analyst", "Liquidity Flow Analyst", "p4_liquidity_flow_provider"),
    (
        "leverage_microstructure_analyst",
        "Leverage Microstructure Analyst",
        "p4_leverage_microstructure_provider",
    ),
    (
        "onchain_market_structure_analyst",
        "On-chain Market Structure Analyst",
        "p4_onchain_market_structure_provider",
    ),
    ("cross_examiner_agent", "Cross-examiner Agent", "p4_cross_exam_provider"),
    ("judge_agent", "Judge Agent", "p4_judge_provider"),
    ("adversarial_reviewer_agent", "Adversarial Reviewer Agent", "p4_adversarial_provider"),
    ("article_writer_agent", "Article Writer Agent", "p4_article_provider"),
)


def llm_routing_payload(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    providers = [
        _provider_payload(provider_config(entry.provider_id, settings))
        for entry in _llm_entries()
    ]
    route_rows = [
        _route_payload(agent_id, label, field_name, settings)
        for agent_id, label, field_name in P4_AGENT_ROUTES
    ]
    p45_provider = provider_config(settings.p45_research_provider, settings)
    return {
        "schema_version": LLM_ROUTING_SCHEMA_VERSION,
        "status": "ok",
        "mock_mode_enabled": settings.p4_use_mock_llm,
        "fallback_policy": settings.p4_llm_fallback_policy,
        "runtime_defaults": {
            "timeout_seconds": settings.p4_llm_timeout_seconds,
            "max_retries": settings.p4_llm_max_retries,
            "max_calls_per_run": settings.p4_llm_max_calls_per_run,
            "max_tokens_per_call": settings.p4_llm_max_tokens_per_call,
            "temperature": settings.p4_llm_temperature,
            "max_estimated_tokens_per_run": settings.p4_llm_max_estimated_tokens_per_run,
        },
        "providers": providers,
        "available_providers": [
            item["provider"]
            for item in providers
            if item["enabled"]
        ],
        "p4_agent_routes": route_rows,
        "p45_routes": [
            {
                "route_id": "p45_research_provider",
                "consumer": "P4.5 Research Writer",
                "provider": p45_provider.provider,
                "model": p45_provider.model_name,
                "enabled_for_llm": p45_provider.enabled,
                "disabled_reason": p45_provider.disabled_reason,
            },
            {
                "route_id": "p45_analyst_provider",
                "consumer": "P4.5 Analyst Writers",
                "provider": p45_provider.provider,
                "model": p45_provider.model_name,
                "enabled_for_llm": p45_provider.enabled,
                "disabled_reason": p45_provider.disabled_reason,
            },
        ],
        "guardrails": [
            "mock_mode_never_calls_real_provider",
            "missing_api_key_disables_real_llm_call",
            "provider_name_is_runtime_route_not_business_role",
            "no_plaintext_secret_values",
        ],
    }


def _llm_entries():
    return [entry for entry in PROVIDER_REGISTRY if entry.category == "llm"]


def _route_payload(
    agent_id: str,
    label: str,
    field_name: str,
    settings: Settings,
) -> dict[str, Any]:
    provider_name = str(getattr(settings, field_name))
    config = provider_config(provider_name, settings)
    return {
        "agent_id": agent_id,
        "agent_label": label,
        "settings_field": field_name,
        "provider": config.provider,
        "model": config.model_name,
        "enabled_for_llm": config.enabled,
        "mock_mode_bypasses_provider": settings.p4_use_mock_llm,
        "disabled_reason": config.disabled_reason,
    }


def _provider_payload(config: ProviderConfig) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "model": config.model_name,
        "base_url": config.base_url,
        "api_key_configured": config.api_key_configured,
        "enabled": config.enabled,
        "disabled_reason": config.disabled_reason,
        "enable_thinking": config.enable_thinking,
        "timeout_seconds": config.timeout_seconds,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
