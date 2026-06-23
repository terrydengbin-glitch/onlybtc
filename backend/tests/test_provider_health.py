from __future__ import annotations

import httpx
import pytest

import onlybtc.api.app as app_module
import onlybtc.core.provider_health as provider_health
from onlybtc.core.config import Settings


@pytest.fixture(autouse=True)
def clear_health_cache() -> None:
    provider_health.clear_provider_health_cache()


def test_provider_health_snapshot_defaults_without_secrets() -> None:
    snapshot = provider_health.provider_health_snapshot(Settings(_env_file=None))
    by_id = {item["provider_id"]: item for item in snapshot["items"]}

    assert snapshot["schema_version"] == "p10.c04.provider_health.v1"
    assert by_id["fred"]["status"] == "missing_key"
    assert by_id["cryptoquant"]["status"] == "unsupported"
    assert "secret" not in str(snapshot).lower()


@pytest.mark.asyncio
async def test_provider_health_fred_success_redacts_key(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            seen["url"] = url
            seen["params"] = kwargs.get("params")
            return httpx.Response(200, json={"observations": [{"date": "2026-01-01"}]})

    monkeypatch.setattr(provider_health.httpx, "AsyncClient", FakeClient)

    result = await provider_health.test_provider_health(
        "fred",
        Settings(fred_api_key="fred-secret-value"),
    )

    assert result["status"] == "healthy"
    assert result["http_status"] == 200
    assert result["last_tested_at"]
    assert result["latency_ms"] >= 0
    assert seen["params"]["api_key"] == "fred-secret-value"
    assert "fred-secret-value" not in str(result)


@pytest.mark.asyncio
async def test_provider_health_failure_redacts_provider_error(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            raise httpx.HTTPError("bad request api_key=fred-secret-value")

    monkeypatch.setattr(provider_health.httpx, "AsyncClient", FakeClient)

    result = await provider_health.test_provider_health(
        "fred",
        Settings(fred_api_key="fred-secret-value"),
    )

    assert result["status"] == "failed"
    assert "fred-secret-value" not in result["error_message"]
    assert "api_key=<redacted>" in result["error_message"]


@pytest.mark.asyncio
async def test_provider_health_llm_uses_models_endpoint(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            seen["url"] = url
            seen["headers"] = kwargs.get("headers")
            return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(provider_health.httpx, "AsyncClient", FakeClient)

    result = await provider_health.test_provider_health(
        "deepseek",
        Settings(deepseek_api_key="deepseek-secret-value"),
    )

    assert result["status"] == "healthy"
    assert seen["url"] == "https://api.deepseek.com/models"
    assert seen["headers"]["Authorization"] == "Bearer deepseek-secret-value"
    assert "deepseek-secret-value" not in str(result)


def test_settings_summary_includes_provider_health() -> None:
    response = app_module.settings_provider_health()

    assert response["schema_version"] == "p10.c04.provider_health.v1"
    assert response["provider_count"] >= 10


@pytest.mark.asyncio
async def test_provider_health_endpoint_unknown_provider_404() -> None:
    with pytest.raises(app_module.HTTPException) as exc:
        await app_module.settings_provider_health_test("missing-provider")

    assert exc.value.status_code == 404
