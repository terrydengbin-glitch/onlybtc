from __future__ import annotations

from datetime import UTC, datetime

import pytest

import onlybtc.api.app as app_module
from onlybtc.core.config import Settings
from onlybtc.core.env_writer import write_env_updates


def test_write_env_updates_preserves_unknown_lines_and_backs_up(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# local settings\n"
        "UNKNOWN_FLAG=keep-me\n"
        "ONLYBTC_FRED_API_KEY=old-fred\n",
        encoding="utf-8",
    )

    result = write_env_updates(
        {
            "ONLYBTC_FRED_API_KEY": "new-fred-secret",
            "ONLYBTC_DEEPSEEK_API_KEY": "deepseek secret value",
        },
        project_root=tmp_path,
        now=datetime(2026, 6, 23, 1, 2, 3, tzinfo=UTC),
    )

    written = env_path.read_text(encoding="utf-8")
    backup = tmp_path / "backups" / "env" / ".env.20260623010203.bak"

    assert backup.exists()
    assert "old-fred" in backup.read_text(encoding="utf-8")
    assert "# local settings" in written
    assert "UNKNOWN_FLAG=keep-me" in written
    assert "ONLYBTC_FRED_API_KEY=new-fred-secret" in written
    assert 'ONLYBTC_DEEPSEEK_API_KEY="deepseek secret value"' in written
    assert result["updated_keys"] == ["ONLYBTC_DEEPSEEK_API_KEY", "ONLYBTC_FRED_API_KEY"]
    assert result["appended_keys"] == ["ONLYBTC_DEEPSEEK_API_KEY"]
    assert "new-fred-secret" not in str(result)
    assert "deepseek secret value" not in str(result)


def test_write_env_updates_rejects_unknown_or_multiline_values(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unsupported env key"):
        write_env_updates({"ONLYBTC_NOT_ALLOWED": "secret"}, project_root=tmp_path)

    with pytest.raises(ValueError, match="single-line"):
        write_env_updates({"ONLYBTC_FRED_API_KEY": "line1\nline2"}, project_root=tmp_path)


def test_settings_env_update_endpoint_reloads_and_redacts(monkeypatch) -> None:
    calls: list[object] = []

    def fake_write(updates: dict[str, str]) -> dict[str, object]:
        calls.append(dict(updates))
        return {
            "schema_version": "p10.c03.env_update.v1",
            "status": "ok",
            "updated_keys": sorted(updates),
            "backup_path": "backups/env/.env.test.bak",
            "redacted": True,
        }

    def fake_reload() -> Settings:
        calls.append("reload")
        return Settings()

    def fake_summary() -> dict[str, object]:
        return {
            "status": "ok",
            "providers": {
                "providers": [
                    {
                        "provider_id": "fred",
                        "env_key": "ONLYBTC_FRED_API_KEY",
                        "configured": True,
                        "masked_value": "new***ret",
                    }
                ]
            },
        }

    monkeypatch.setattr(app_module, "write_env_updates", fake_write)
    monkeypatch.setattr(app_module, "reload_settings", fake_reload)
    monkeypatch.setattr(app_module.p45_dashboard, "settings_summary", fake_summary)

    response = app_module.settings_env_update(
        app_module.SettingsEnvUpdateRequest(
            updates={"ONLYBTC_FRED_API_KEY": "new-fred-secret"}
        )
    )

    assert calls == [{"ONLYBTC_FRED_API_KEY": "new-fred-secret"}, "reload"]
    assert response["updated_keys"] == ["ONLYBTC_FRED_API_KEY"]
    assert response["settings"]["providers"]["providers"][0]["masked_value"] == "new***ret"
    assert "new-fred-secret" not in str(response)
