from __future__ import annotations

import onlybtc.api.app as app_module
from onlybtc.api import p45_dashboard
from onlybtc.core.config import Settings
from onlybtc.core.settings_contract import (
    settings_contract_payload,
    settings_data_sources_payload,
    settings_paths_payload,
    settings_runtime_payload,
)


def test_settings_contract_includes_runtime_sources_paths_without_secrets() -> None:
    payload = settings_contract_payload(
        Settings(deepseek_api_key="deepseek-secret", _env_file=None)
    )

    assert payload["schema_version"] == "p9.c59.settings_contract.v1"
    assert payload["read_only"] is True
    assert payload["runtime"]["scheduler"]["default_refresh_seconds"] == 600
    assert payload["data_sources"]["source_count"] > 0
    assert payload["paths"]["path_count"] > 0
    text = str(payload).lower()
    assert "deepseek-secret" not in text
    assert "authorization" not in text


def test_settings_data_sources_exposes_fallback_and_freshness_policy() -> None:
    payload = settings_data_sources_payload(Settings(_env_file=None))

    assert payload["schema_version"] == "p9.c59.settings_contract.v1"
    assert payload["read_only"] is True
    assert payload["fallback_configured_count"] > 0
    assert payload["freshness_policy_count"] > 0
    assert payload["source_groups"]
    by_id = {item["source_id"]: item for item in payload["items"]}
    assert by_id["clarkmoody-dashboard"]["fallback_source_id"] == (
        "mempool-lightning-network-stats"
    )
    assert by_id["fred-bank-reserves"]["freshness_policy"]


def test_settings_runtime_and_paths_are_read_only_contracts() -> None:
    runtime = settings_runtime_payload(Settings(_env_file=None))
    path_payload = settings_paths_payload()

    assert runtime["mutation_policy"]["write_endpoints_enabled"] is False
    assert path_payload["mutation_policy"]["mode"] == "read_only"
    assert path_payload["storage"]["sqlite_db_path"]
    assert path_payload["maintenance"]["database_backup_endpoint"] == "/api/db/backup"


def test_settings_summary_and_api_helpers_include_p9_c59_contract() -> None:
    summary = p45_dashboard.settings_summary()
    runtime = app_module.settings_runtime()
    data_sources = app_module.settings_data_sources()
    path_payload = app_module.settings_paths()

    assert summary["status"] == "ok"
    assert summary["settings_contract"]["schema_version"] == "p9.c59.settings_contract.v1"
    assert summary["runtime"]["read_only"] is True
    assert summary["data_sources"]["source_count"] == data_sources["source_count"]
    assert runtime["schema_version"] == "p9.c59.settings_contract.v1"
    assert path_payload["path_count"] > 0
