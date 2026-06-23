from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from onlybtc.core.config import Settings, get_settings
from onlybtc.core.provider_registry import PROVIDER_REGISTRY, ProviderRegistryEntry

PROVIDER_HEALTH_SCHEMA_VERSION = "p10.c04.provider_health.v1"
PROVIDER_TEST_TIMEOUT_SECONDS = 12.0

_HEALTH_CACHE: dict[str, dict[str, Any]] = {}


def provider_health_snapshot(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    items = [_cached_or_default(entry, settings) for entry in PROVIDER_REGISTRY]
    return {
        "schema_version": PROVIDER_HEALTH_SCHEMA_VERSION,
        "status": "ok",
        "provider_count": len(items),
        "tested_count": sum(1 for item in items if item.get("last_tested_at")),
        "healthy_count": sum(1 for item in items if item.get("status") == "healthy"),
        "items": items,
    }


async def test_provider_health(
    provider_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    entry = _entry_by_id(provider_id)
    if entry is None:
        raise ValueError(f"Unknown provider_id: {provider_id}")
    result = await _run_provider_probe(entry, settings)
    _HEALTH_CACHE[entry.provider_id] = result
    return result


async def test_all_provider_health(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    items = [await test_provider_health(entry.provider_id, settings) for entry in PROVIDER_REGISTRY]
    return {
        "schema_version": PROVIDER_HEALTH_SCHEMA_VERSION,
        "status": "ok",
        "provider_count": len(items),
        "tested_count": sum(1 for item in items if item.get("last_tested_at")),
        "healthy_count": sum(1 for item in items if item.get("status") == "healthy"),
        "items": items,
    }


def clear_provider_health_cache() -> None:
    _HEALTH_CACHE.clear()


async def _run_provider_probe(
    entry: ProviderRegistryEntry,
    settings: Settings,
) -> dict[str, Any]:
    started = time.perf_counter()
    tested_at = datetime.now(UTC).isoformat()
    if not entry.supports_test:
        return _result(
            entry,
            status="unsupported",
            configured=_is_configured(entry, settings),
            tested_at=tested_at,
            latency_ms=_elapsed_ms(started),
            error_message="Provider health check is not integrated yet.",
        )
    secret = _setting_value(entry, settings)
    configured = _is_configured_secret(secret)
    if not configured:
        return _result(
            entry,
            status="missing_key" if entry.env_key else "not_configured",
            configured=False,
            tested_at=tested_at,
            latency_ms=_elapsed_ms(started),
            error_message=f"{entry.env_key or entry.provider_id} is not configured.",
        )
    try:
        async with httpx.AsyncClient(timeout=PROVIDER_TEST_TIMEOUT_SECONDS) as client:
            response = await _probe_http(entry, settings, client, str(secret or ""))
        status = "healthy" if 200 <= response.status_code < 300 else "failed"
        error_message = "" if status == "healthy" else f"HTTP {response.status_code}"
        return _result(
            entry,
            status=status,
            configured=True,
            tested_at=tested_at,
            latency_ms=_elapsed_ms(started),
            error_message=error_message,
            http_status=response.status_code,
        )
    except Exception as exc:  # noqa: BLE001 - provider health must not interrupt system.
        return _result(
            entry,
            status="failed",
            configured=True,
            tested_at=tested_at,
            latency_ms=_elapsed_ms(started),
            error_message=_redact_error(str(exc) or exc.__class__.__name__),
        )


async def _probe_http(
    entry: ProviderRegistryEntry,
    settings: Settings,
    client: httpx.AsyncClient,
    secret: str,
) -> httpx.Response:
    provider = entry.provider_id
    if provider == "fred":
        return await client.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": "DGS10",
                "api_key": secret,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 1,
            },
        )
    if provider == "glassnode":
        return await client.get(
            "https://api.glassnode.com/v1/metrics/market/price_usd_close",
            params={"a": "BTC", "i": "24h", "api_key": secret},
        )
    llm_base_url = _llm_base_url(provider, settings)
    if llm_base_url:
        return await client.get(
            f"{llm_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {secret}"},
        )
    raise ValueError(f"No health probe available for provider_id={entry.provider_id}")


def _cached_or_default(entry: ProviderRegistryEntry, settings: Settings) -> dict[str, Any]:
    cached = _HEALTH_CACHE.get(entry.provider_id)
    if cached:
        return dict(cached)
    configured = _is_configured(entry, settings)
    if not entry.supports_test:
        status = "unsupported"
        error_message = "Provider health check is not integrated yet."
    elif configured:
        status = "untested"
        error_message = ""
    else:
        status = "missing_key" if entry.env_key else "not_configured"
        error_message = f"{entry.env_key or entry.provider_id} is not configured."
    return _result(
        entry,
        status=status,
        configured=configured,
        tested_at=None,
        latency_ms=None,
        error_message=error_message,
    )


def _result(
    entry: ProviderRegistryEntry,
    status: str,
    configured: bool,
    tested_at: str | None,
    latency_ms: int | None,
    error_message: str = "",
    http_status: int | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": PROVIDER_HEALTH_SCHEMA_VERSION,
        "provider_id": entry.provider_id,
        "name": entry.name,
        "category": entry.category,
        "env_key": entry.env_key,
        "supports_test": entry.supports_test,
        "configured": configured,
        "status": status,
        "last_tested_at": tested_at,
        "latency_ms": latency_ms,
        "http_status": http_status,
        "error_message": _redact_error(error_message),
    }


def _entry_by_id(provider_id: str) -> ProviderRegistryEntry | None:
    normalized = provider_id.lower().strip()
    for entry in PROVIDER_REGISTRY:
        if entry.provider_id == normalized:
            return entry
    return None


def _is_configured(entry: ProviderRegistryEntry, settings: Settings) -> bool:
    return _is_configured_secret(_setting_value(entry, settings))


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


def _llm_base_url(provider_id: str, settings: Settings) -> str:
    return {
        "openai": settings.openai_base_url,
        "deepseek": settings.deepseek_base_url,
        "qwen": settings.qwen_base_url,
        "volcano": settings.volcano_base_url,
        "kimi": settings.kimi_base_url,
    }.get(provider_id, "")


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _redact_error(message: str) -> str:
    redacted = re.sub(r"(?i)(api_key=)[^&\s]+", r"\1<redacted>", message)
    redacted = re.sub(r"(?i)(authorization:\s*bearer\s+)[^\s,;]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+", r"\1<redacted>", redacted)
    return redacted
