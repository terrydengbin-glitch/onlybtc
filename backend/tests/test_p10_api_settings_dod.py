from __future__ import annotations

import httpx
import pytest

import onlybtc.core.provider_health as provider_health
from onlybtc.core.config import Settings
from onlybtc.core.env_writer import write_env_updates
from onlybtc.core.llm_routing import llm_routing_payload
from onlybtc.core.provider_registry import provider_registry_payload
from onlybtc.core.settings_audit import (
    record_settings_audit_event,
    settings_audit_summary,
)


def test_p10_mock_env_settings_chain_reads_masked_provider_status(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("# mock settings\nONLYBTC_UNKNOWN_FLAG=keep\n", encoding="utf-8")

    write_result = write_env_updates(
        {
            "ONLYBTC_FRED_API_KEY": "mock-fred-secret",
            "ONLYBTC_DEEPSEEK_API_KEY": "mock-deepseek-secret",
        },
        project_root=tmp_path,
    )
    settings = Settings(_env_file=env_path)
    provider_payload = provider_registry_payload(settings)
    routing_payload = llm_routing_payload(settings)
    audit_event = record_settings_audit_event(
        action="env_update",
        env_keys=write_result["updated_keys"],
        backup_path=str(write_result["backup_path"]),
        operation_counts=write_result["operation_counts"],
        project_root=tmp_path,
    )
    audit_payload = settings_audit_summary(project_root=tmp_path)

    providers = {item["provider_id"]: item for item in provider_payload["providers"]}

    assert providers["fred"]["configured"] is True
    assert providers["fred"]["masked_value"] == "moc***ret"
    assert providers["deepseek"]["configured"] is True
    assert "deepseek" in routing_payload["available_providers"]
    assert audit_event["redacted"] is True
    assert audit_payload["event_count"] == 1
    assert "ONLYBTC_UNKNOWN_FLAG=keep" in env_path.read_text(encoding="utf-8")
    combined = f"{write_result}{provider_payload}{routing_payload}{audit_payload}"
    assert "mock-fred-secret" not in combined
    assert "mock-deepseek-secret" not in combined


@pytest.mark.asyncio
async def test_p10_provider_health_success_and_failure_paths_are_redacted(monkeypatch) -> None:
    class SuccessClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(provider_health.httpx, "AsyncClient", SuccessClient)
    success = await provider_health.test_provider_health(
        "deepseek",
        Settings(_env_file=None, deepseek_api_key="mock-deepseek-secret"),
    )

    class FailureClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def get(self, url: str, **kwargs):
            raise httpx.HTTPError("Authorization: Bearer mock-deepseek-secret")

    monkeypatch.setattr(provider_health.httpx, "AsyncClient", FailureClient)
    failure = await provider_health.test_provider_health(
        "deepseek",
        Settings(_env_file=None, deepseek_api_key="mock-deepseek-secret"),
    )

    assert success["status"] == "healthy"
    assert failure["status"] == "failed"
    assert "mock-deepseek-secret" not in str(success)
    assert "mock-deepseek-secret" not in str(failure)


def test_p10_frontend_settings_mock_wiring_is_present() -> None:
    app_vue = open("frontend/src/App.vue", encoding="utf-8").read()
    api_ts = open("frontend/src/api.ts", encoding="utf-8").read()

    assert "updateSettingsEnv" in api_ts
    assert "getSettingsAudit" in api_ts
    assert "testProviderHealth" in api_ts
    assert "settingsKeyInputs" in app_vue
    assert "Recent Key Audit" in app_vue
    assert "Provider Readiness" in app_vue
