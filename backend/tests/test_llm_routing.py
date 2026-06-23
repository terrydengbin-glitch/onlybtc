from __future__ import annotations

from onlybtc.core.config import Settings
from onlybtc.core.llm_routing import llm_routing_payload
from onlybtc.p4.agent_runtime import provider_config, provider_for_agent


def test_llm_routing_discovers_enabled_providers_without_plaintext() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="deepseek-secret-value",
        qwen_api_key="your_qwen_key_here",
        p4_macro_event_provider="deepseek",
        p4_liquidity_flow_provider="qwen",
        p4_use_mock_llm=False,
    )

    payload = llm_routing_payload(settings)
    by_provider = {item["provider"]: item for item in payload["providers"]}
    by_agent = {item["agent_id"]: item for item in payload["p4_agent_routes"]}

    assert payload["schema_version"] == "p10.c05.llm_routing.v1"
    assert payload["mock_mode_enabled"] is False
    assert "deepseek" in payload["available_providers"]
    assert "qwen" not in payload["available_providers"]
    assert by_provider["deepseek"]["enabled"] is True
    assert by_provider["deepseek"]["max_tokens"] == settings.p4_llm_max_tokens_per_call
    assert by_provider["deepseek"]["temperature"] == settings.p4_llm_temperature
    assert by_provider["qwen"]["enabled"] is False
    assert by_provider["qwen"]["disabled_reason"] == "api_key_missing"
    assert by_agent["macro_event_analyst"]["provider"] == "deepseek"
    assert by_agent["macro_event_analyst"]["enabled_for_llm"] is True
    assert by_agent["liquidity_flow_analyst"]["provider"] == "qwen"
    assert by_agent["liquidity_flow_analyst"]["enabled_for_llm"] is False
    assert "deepseek-secret-value" not in str(payload)


def test_provider_config_exposes_runtime_parameters_and_disabled_reason() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="deepseek-secret-value",
        p4_llm_max_tokens_per_call=2048,
        p4_llm_temperature=0.35,
        p4_llm_timeout_seconds=45,
    )

    deepseek = provider_config("deepseek", settings)
    openai = provider_config("openai", settings)

    assert deepseek.enabled is True
    assert deepseek.max_tokens == 2048
    assert deepseek.temperature == 0.35
    assert deepseek.timeout_seconds == 45
    assert openai.enabled is False
    assert openai.disabled_reason == "api_key_missing"


def test_mock_mode_keeps_routes_usable_without_api_keys() -> None:
    settings = Settings(
        _env_file=None,
        p4_use_mock_llm=True,
        p4_macro_event_provider="deepseek",
    )

    route = provider_for_agent("macro_event_analyst", settings)
    payload = llm_routing_payload(settings)
    macro_route = next(item for item in payload["p4_agent_routes"] if item["agent_id"] == "macro_event_analyst")

    assert route.provider == "deepseek"
    assert route.enabled is False
    assert macro_route["mock_mode_bypasses_provider"] is True
    assert macro_route["enabled_for_llm"] is False
    assert "mock_mode_never_calls_real_provider" in payload["guardrails"]
