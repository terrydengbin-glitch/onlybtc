from __future__ import annotations

import pytest

import onlybtc.api.app as app_module
from onlybtc.core.settings_audit import (
    record_settings_audit_event,
    settings_audit_log_path,
    settings_audit_summary,
)


def test_settings_audit_event_writes_redacted_jsonl(tmp_path) -> None:
    event = record_settings_audit_event(
        action="env_update",
        env_keys=["ONLYBTC_FRED_API_KEY"],
        backup_path="backups/env/.env.test.bak",
        error_message="Authorization: Bearer raw-token api_key=raw-secret",
        operation_counts={"updated": 1},
        project_root=tmp_path,
    )
    text = settings_audit_log_path(tmp_path).read_text(encoding="utf-8")
    summary = settings_audit_summary(project_root=tmp_path)

    assert event["redacted"] is True
    assert event["provider_ids"] == ["fred"]
    assert "raw-token" not in text
    assert "raw-secret" not in text
    assert "ONLYBTC_FRED_API_KEY" in text
    assert summary["event_count"] == 1
    assert summary["action_counts"]["env_update"] == 1


def test_settings_env_update_endpoint_records_audit_without_plaintext(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_write(updates: dict[str, str]) -> dict[str, object]:
        return {
            "schema_version": "p10.c03.env_update.v1",
            "status": "ok",
            "backup_path": "backups/env/.env.test.bak",
            "updated_keys": sorted(updates),
            "operation_counts": {"updated": len(updates)},
            "redacted": True,
        }

    def fake_audit(**kwargs):
        calls.append(kwargs)
        return {
            "schema_version": "p10.c06.settings_key_audit.v1",
            "action": kwargs["action"],
            "env_keys": kwargs["env_keys"],
            "redacted": True,
        }

    monkeypatch.setattr(app_module, "write_env_updates", fake_write)
    monkeypatch.setattr(app_module, "reload_settings", lambda: None)
    monkeypatch.setattr(app_module.p45_dashboard, "settings_summary", lambda: {"status": "ok"})
    monkeypatch.setattr(app_module, "record_settings_audit_event", fake_audit)

    response = app_module.settings_env_update(
        app_module.SettingsEnvUpdateRequest(
            updates={"ONLYBTC_FRED_API_KEY": "new-fred-secret"}
        )
    )

    assert calls[0]["action"] == "env_update"
    assert calls[0]["operation_counts"] == {"updated": 1}
    assert response["audit_event"]["redacted"] is True
    assert "new-fred-secret" not in str(response)


@pytest.mark.asyncio
async def test_provider_test_endpoint_records_audit(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    async def fake_test(provider_id: str) -> dict[str, object]:
        return {
            "provider_id": provider_id,
            "status": "healthy",
            "error_message": "",
        }

    def fake_audit(**kwargs):
        calls.append(kwargs)
        return {"redacted": True}

    monkeypatch.setattr(app_module, "test_provider_health", fake_test)
    monkeypatch.setattr(app_module, "record_settings_audit_event", fake_audit)

    response = await app_module.settings_provider_health_test("fred")

    assert response["status"] == "healthy"
    assert calls == [
        {
            "action": "tested",
            "env_keys": [],
            "provider_ids": ["fred"],
            "status": "healthy",
            "error_message": "",
        }
    ]
