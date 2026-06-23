from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from onlybtc.core.config import Settings, get_settings

REGISTRY_SCHEMA_VERSION = "p10.c01.provider_registry.v1"


@dataclass(frozen=True)
class ProviderRegistryEntry:
    provider_id: str
    name: str
    category: str
    env_key: str | None
    setting_name: str | None
    required: bool
    supports_test: bool
    docs_url: str
    status_policy: str
    notes: str = ""


PROVIDER_REGISTRY: tuple[ProviderRegistryEntry, ...] = (
    ProviderRegistryEntry(
        provider_id="fred",
        name="FRED",
        category="data_source",
        env_key="ONLYBTC_FRED_API_KEY",
        setting_name="fred_api_key",
        required=True,
        supports_test=True,
        docs_url="https://fred.stlouisfed.org/docs/api/api_key.html",
        status_policy="configured_required_for_full_macro_collection",
    ),
    ProviderRegistryEntry(
        provider_id="deepseek",
        name="DeepSeek",
        category="llm",
        env_key="ONLYBTC_DEEPSEEK_API_KEY",
        setting_name="deepseek_api_key",
        required=False,
        supports_test=True,
        docs_url="https://api-docs.deepseek.com/",
        status_policy="disabled_without_api_key",
    ),
    ProviderRegistryEntry(
        provider_id="openai",
        name="OpenAI",
        category="llm",
        env_key="ONLYBTC_OPENAI_API_KEY",
        setting_name="openai_api_key",
        required=False,
        supports_test=True,
        docs_url="https://platform.openai.com/docs",
        status_policy="disabled_without_api_key",
    ),
    ProviderRegistryEntry(
        provider_id="qwen",
        name="Qwen",
        category="llm",
        env_key="ONLYBTC_QWEN_API_KEY",
        setting_name="qwen_api_key",
        required=False,
        supports_test=True,
        docs_url="https://help.aliyun.com/zh/model-studio/",
        status_policy="disabled_without_api_key",
    ),
    ProviderRegistryEntry(
        provider_id="volcano",
        name="Volcano Ark",
        category="llm",
        env_key="ONLYBTC_VOLCANO_API_KEY",
        setting_name="volcano_api_key",
        required=False,
        supports_test=True,
        docs_url="https://www.volcengine.com/docs/82379",
        status_policy="disabled_without_api_key",
    ),
    ProviderRegistryEntry(
        provider_id="kimi",
        name="Kimi",
        category="llm",
        env_key="ONLYBTC_KIMI_API_KEY",
        setting_name="kimi_api_key",
        required=False,
        supports_test=True,
        docs_url="https://platform.moonshot.cn/docs",
        status_policy="disabled_without_api_key",
    ),
    ProviderRegistryEntry(
        provider_id="glassnode",
        name="Glassnode",
        category="manual_login_data_source",
        env_key="ONLYBTC_GLASSNODE_API_KEY",
        setting_name="glassnode_api_key",
        required=False,
        supports_test=True,
        docs_url="https://docs.glassnode.com/",
        status_policy="provider_locked_until_api_key_or_manual_session_verified",
        notes="P1/P7 currently use Playwright session audit; API key support is reserved.",
    ),
    ProviderRegistryEntry(
        provider_id="cryptoquant",
        name="CryptoQuant",
        category="planned_data_source",
        env_key="ONLYBTC_CRYPTOQUANT_API_KEY",
        setting_name="cryptoquant_api_key",
        required=False,
        supports_test=False,
        docs_url="https://cryptoquant.com/",
        status_policy="planned_provider_locked_until_integrated",
    ),
    ProviderRegistryEntry(
        provider_id="coinglass",
        name="Coinglass",
        category="planned_data_source",
        env_key="ONLYBTC_COINGLASS_API_KEY",
        setting_name="coinglass_api_key",
        required=False,
        supports_test=False,
        docs_url="https://www.coinglass.com/",
        status_policy="planned_provider_locked_until_integrated",
    ),
    ProviderRegistryEntry(
        provider_id="newsapi",
        name="News API",
        category="planned_news_source",
        env_key="ONLYBTC_NEWS_API_KEY",
        setting_name="news_api_key",
        required=False,
        supports_test=False,
        docs_url="https://newsapi.org/docs",
        status_policy="planned_provider_locked_until_integrated",
    ),
)


def provider_registry_payload(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    providers = [provider_entry_payload(entry, settings) for entry in PROVIDER_REGISTRY]
    configured_count = sum(1 for item in providers if item["configured"])
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "provider_count": len(providers),
        "configured_count": configured_count,
        "categories": _category_counts(providers),
        "providers": providers,
        "guardrails": [
            "no_plaintext_secret_values",
            "env_keys_are_prefixed_with_ONLYBTC",
            "unconfigured_providers_are_disabled_or_provider_locked",
            "planned_providers_require_integration_before_use",
        ],
    }


def provider_entry_payload(
    entry: ProviderRegistryEntry,
    settings: Settings,
) -> dict[str, Any]:
    value = _setting_value(entry, settings)
    configured = _is_configured_secret(value)
    return {
        "provider_id": entry.provider_id,
        "name": entry.name,
        "category": entry.category,
        "env_key": entry.env_key,
        "required": entry.required,
        "supports_test": entry.supports_test,
        "docs_url": entry.docs_url,
        "configured": configured,
        "masked_value": mask_secret(value) if configured else "",
        "status": "configured" if configured else _unconfigured_status(entry),
        "status_policy": entry.status_policy,
        "notes": entry.notes,
    }


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if len(stripped) <= 8:
        return "***"
    return f"{stripped[:3]}***{stripped[-3:]}"


def _setting_value(entry: ProviderRegistryEntry, settings: Settings) -> str | None:
    if not entry.setting_name:
        return None
    value = getattr(settings, entry.setting_name, None)
    return str(value) if value is not None else None


def _is_configured_secret(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    if not normalized:
        return False
    placeholder_markers = ("your_", "placeholder", "changeme", "todo", "example")
    return not any(marker in normalized for marker in placeholder_markers)


def _unconfigured_status(entry: ProviderRegistryEntry) -> str:
    if entry.category.startswith("planned"):
        return "planned_not_integrated"
    if entry.required:
        return "missing_required"
    if "provider_locked" in entry.status_policy:
        return "provider_locked"
    return "disabled"


def _category_counts(providers: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for provider in providers:
        category = str(provider["category"])
        counts[category] = counts.get(category, 0) + 1
    return counts
