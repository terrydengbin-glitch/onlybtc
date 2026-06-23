from __future__ import annotations

from onlybtc.core.config import Settings
from onlybtc.core.provider_registry import mask_secret, provider_registry_payload


def test_provider_registry_lists_current_and_planned_env_keys() -> None:
    payload = provider_registry_payload(Settings())
    by_id = {item["provider_id"]: item for item in payload["providers"]}

    assert payload["schema_version"] == "p10.c01.provider_registry.v1"
    assert by_id["fred"]["env_key"] == "ONLYBTC_FRED_API_KEY"
    assert by_id["deepseek"]["category"] == "llm"
    assert by_id["glassnode"]["env_key"] == "ONLYBTC_GLASSNODE_API_KEY"
    assert by_id["cryptoquant"]["status"] == "planned_not_integrated"
    assert by_id["coinglass"]["status"] == "planned_not_integrated"
    assert by_id["newsapi"]["status"] == "planned_not_integrated"


def test_provider_registry_masks_configured_values_without_plaintext() -> None:
    settings = Settings(fred_api_key="fred-secret-value", deepseek_api_key="deepseek-secret-value")

    payload = provider_registry_payload(settings)
    by_id = {item["provider_id"]: item for item in payload["providers"]}

    assert by_id["fred"]["configured"] is True
    assert by_id["fred"]["masked_value"] == "fre***lue"
    assert "fred-secret-value" not in str(payload)
    assert by_id["deepseek"]["configured"] is True
    assert "deepseek-secret-value" not in str(payload)


def test_provider_registry_treats_placeholders_as_unconfigured() -> None:
    payload = provider_registry_payload(Settings(fred_api_key="your_fred_api_key_here"))
    fred = next(item for item in payload["providers"] if item["provider_id"] == "fred")

    assert fred["configured"] is False
    assert fred["masked_value"] == ""
    assert fred["status"] == "missing_required"


def test_mask_secret_handles_short_values() -> None:
    assert mask_secret("abcd") == "***"
    assert mask_secret("abcdefghi") == "abc***ghi"
