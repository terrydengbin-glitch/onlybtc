from __future__ import annotations

import onlybtc.api.app as app_module
from onlybtc.core.config import Settings, get_settings, reload_settings
from onlybtc.core.provider_registry import provider_registry_payload


def test_settings_reads_planned_provider_keys_and_registry_masks_them() -> None:
    settings = Settings(
        glassnode_api_key="glassnode-secret-value",
        cryptoquant_api_key="cryptoquant-secret-value",
        coinglass_api_key="coinglass-secret-value",
        news_api_key="news-secret-value",
    )

    payload = provider_registry_payload(settings)
    by_id = {item["provider_id"]: item for item in payload["providers"]}

    assert by_id["glassnode"]["configured"] is True
    assert by_id["cryptoquant"]["configured"] is True
    assert by_id["coinglass"]["configured"] is True
    assert by_id["newsapi"]["configured"] is True
    assert "glassnode-secret-value" not in str(payload)
    assert "cryptoquant-secret-value" not in str(payload)
    assert "coinglass-secret-value" not in str(payload)
    assert "news-secret-value" not in str(payload)


def test_reload_settings_clears_cached_settings(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ONLYBTC_APP_NAME", "first-app")
    assert get_settings().app_name == "first-app"

    monkeypatch.setenv("ONLYBTC_APP_NAME", "second-app")
    assert get_settings().app_name == "first-app"
    assert reload_settings().app_name == "second-app"

    get_settings.cache_clear()


def test_settings_reload_endpoint_uses_reload_helper(monkeypatch) -> None:
    calls: list[str] = []

    def fake_reload() -> Settings:
        calls.append("reload")
        return Settings()

    def fake_summary() -> dict[str, object]:
        return {"status": "ok", "providers": {"schema_version": "p10.c01.provider_registry.v1"}}

    monkeypatch.setattr(app_module, "reload_settings", fake_reload)
    monkeypatch.setattr(app_module.p45_dashboard, "settings_summary", fake_summary)

    response = app_module.settings_reload()

    assert calls == ["reload"]
    assert response["status"] == "ok"
