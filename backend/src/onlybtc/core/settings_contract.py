from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from onlybtc.core.config import Settings, get_settings
from onlybtc.core.paths import PathResolver, paths
from onlybtc.radar_runtime.profile import cadence_profile
from onlybtc.radar_runtime.source_gate import SOURCE_GROUP_IDS
from onlybtc.sources.registry import SOURCE_CONFIGS

SETTINGS_CONTRACT_SCHEMA_VERSION = "p9.c59.settings_contract.v1"


def settings_contract_payload(
    settings: Settings | None = None,
    *,
    path_resolver: PathResolver = paths,
) -> dict[str, Any]:
    settings = settings or get_settings()
    return {
        "schema_version": SETTINGS_CONTRACT_SCHEMA_VERSION,
        "read_only": True,
        "mutation_policy": _mutation_policy(),
        "runtime": settings_runtime_payload(settings),
        "data_sources": settings_data_sources_payload(settings),
        "paths": settings_paths_payload(path_resolver),
    }


def settings_runtime_payload(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    profile = cadence_profile()
    group_counts = Counter(str(item["cadence_group"]) for item in profile)
    return {
        "schema_version": SETTINGS_CONTRACT_SCHEMA_VERSION,
        "read_only": True,
        "scheduler": {
            "default_refresh_seconds": settings.default_refresh_seconds,
            "event_window_scheduler_enabled": settings.event_window_scheduler_enabled,
            "event_window_scheduler_tick_seconds": settings.event_window_scheduler_tick_seconds,
            "event_window_cadence_profile": settings.event_window_cadence_profile,
            "event_window_manual_full_sweep_ignores_cadence": (
                settings.event_window_manual_full_sweep_ignores_cadence
            ),
            "radar_cadence_profile_schema": profile[0]["schema_version"] if profile else "",
            "radar_module_count": len(profile),
            "radar_cadence_group_counts": dict(sorted(group_counts.items())),
        },
        "source_collection": {
            "source_timeout_seconds": settings.source_timeout_seconds,
            "source_http_concurrency": settings.source_http_concurrency,
            "source_playwright_concurrency": settings.source_playwright_concurrency,
            "source_official_concurrency": settings.source_official_concurrency,
            "source_fred_concurrency": settings.source_fred_concurrency,
            "source_fred_batch_size": settings.source_fred_batch_size,
            "source_fred_inter_batch_delay_ms": settings.source_fred_inter_batch_delay_ms,
            "source_fred_per_request_jitter_ms": settings.source_fred_per_request_jitter_ms,
            "source_fred_api_max_attempts": settings.source_fred_api_max_attempts,
            "source_fred_api_backoff_seconds": settings.source_fred_api_backoff_seconds,
            "source_max_retries": settings.source_max_retries,
            "source_retry_backoff_seconds": settings.source_retry_backoff_seconds,
            "source_failure_gate_threshold": settings.source_failure_gate_threshold,
            "source_min_current_metrics": settings.source_min_current_metrics,
        },
        "run_defaults": {
            "run_mode": "live",
            "runtime_mode": "deterministic",
            "llm_runtime_mode": "llm",
            "execution_profile": "standard",
        },
        "llm_runtime": {
            "p4_use_mock_llm": settings.p4_use_mock_llm,
            "p4_llm_timeout_seconds": settings.p4_llm_timeout_seconds,
            "p4_llm_max_retries": settings.p4_llm_max_retries,
            "p4_llm_max_calls_per_run": settings.p4_llm_max_calls_per_run,
            "p4_llm_max_tokens_per_call": settings.p4_llm_max_tokens_per_call,
            "p4_llm_temperature": settings.p4_llm_temperature,
            "p4_llm_max_estimated_tokens_per_run": (
                settings.p4_llm_max_estimated_tokens_per_run
            ),
            "p4_llm_fallback_policy": settings.p4_llm_fallback_policy,
            "p45_research_timeout_seconds": settings.p45_research_timeout_seconds,
            "p45_research_max_retries": settings.p45_research_max_retries,
        },
        "mutation_policy": _mutation_policy(),
    }


def settings_data_sources_payload(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    items = [_source_item(source) for source in SOURCE_CONFIGS]
    kind_counts = Counter(str(item["kind"]) for item in items)
    group_counts = Counter(str(item["group_name"]) for item in items)
    return {
        "schema_version": SETTINGS_CONTRACT_SCHEMA_VERSION,
        "read_only": True,
        "source_count": len(items),
        "enabled_count": sum(1 for item in items if item["enabled"]),
        "derived_only_count": sum(1 for item in items if item["derived_only"]),
        "fallback_configured_count": sum(1 for item in items if item["fallback_source_id"]),
        "freshness_policy_count": sum(1 for item in items if item["freshness_policy"]),
        "kind_counts": dict(sorted(kind_counts.items())),
        "group_counts": dict(sorted(group_counts.items())),
        "source_groups": _source_groups_payload(),
        "global_collection_policy": {
            "source_timeout_seconds": settings.source_timeout_seconds,
            "source_max_retries": settings.source_max_retries,
            "source_retry_backoff_seconds": settings.source_retry_backoff_seconds,
            "source_failure_gate_threshold": settings.source_failure_gate_threshold,
            "source_min_current_metrics": settings.source_min_current_metrics,
        },
        "items": items,
        "mutation_policy": _mutation_policy(),
    }


def settings_paths_payload(path_resolver: PathResolver = paths) -> dict[str, Any]:
    raw = path_resolver.as_dict()
    items = [
        {
            "path_id": key,
            "path": value,
            "exists": Path(value).exists(),
            "is_dir": Path(value).is_dir(),
            "is_file": Path(value).is_file(),
        }
        for key, value in raw.items()
    ]
    return {
        "schema_version": SETTINGS_CONTRACT_SCHEMA_VERSION,
        "read_only": True,
        "path_count": len(items),
        "items": items,
        "storage": {
            "data_dir": raw.get("data_dir", ""),
            "sqlite_db_path": raw.get("sqlite_db_path", ""),
            "logs_dir": raw.get("logs_dir", ""),
            "backup_dir": raw.get("backup_dir", ""),
            "reports_dir": str(path_resolver.project_root / "reports"),
        },
        "maintenance": {
            "database_backup_endpoint": "/api/db/backup",
            "database_export_schema_endpoint": "/api/db/export-schema",
            "reports_mount": "/reports",
        },
        "mutation_policy": _mutation_policy(),
    }


def _source_item(source: Any) -> dict[str, Any]:
    metadata = dict(source.metadata or {})
    freshness_policy = metadata.get("freshness_policy") or {}
    return {
        "source_id": source.source_id,
        "name": source.name,
        "kind": str(source.kind),
        "group_name": source.group_name,
        "method": source.method,
        "priority": source.priority,
        "enabled": metadata.get("collectable") is not False,
        "derived_only": bool(metadata.get("derived_only")),
        "fallback_source_id": source.fallback_source_id,
        "metric_count": len(source.metrics),
        "metrics": list(source.metrics),
        "freshness_policy": freshness_policy,
        "expected_refresh_seconds": freshness_policy.get("expected_update_seconds"),
        "collection_stale_after_seconds": freshness_policy.get(
            "collection_stale_after_seconds"
        ),
        "business_outdated_after_seconds": freshness_policy.get(
            "business_outdated_after_seconds"
        ),
        "guardrails": _source_guardrails(source, metadata),
    }


def _source_groups_payload() -> list[dict[str, Any]]:
    configured = {source.source_id for source in SOURCE_CONFIGS}
    groups = []
    for group_id, source_ids in sorted(SOURCE_GROUP_IDS.items()):
        groups.append(
            {
                "source_group_id": group_id,
                "source_count": len(source_ids),
                "configured_source_count": sum(
                    1 for source_id in source_ids if source_id in configured
                ),
                "missing_configured_source_ids": sorted(
                    source_id for source_id in source_ids if source_id not in configured
                ),
                "source_ids": list(source_ids),
            }
        )
    return groups


def _source_guardrails(source: Any, metadata: dict[str, Any]) -> list[str]:
    guardrails: list[str] = []
    if source.fallback_source_id:
        guardrails.append("fallback_source_must_be_labeled")
    if metadata.get("derived_only"):
        guardrails.append("derived_only_not_direct_collection")
    if metadata.get("collectable") is False:
        guardrails.append("disabled_for_direct_collection")
    if source.kind.value == "playwright":
        guardrails.append("browser_collection_must_not_block_global_pipeline")
    return guardrails


def _mutation_policy() -> dict[str, Any]:
    return {
        "mode": "read_only",
        "write_endpoints_enabled": False,
        "reason": "P9-C59 exposes current non-secret Settings state only.",
        "future_write_contract_required": [
            "persistent_config_store",
            "operator_auth",
            "settings_audit_event",
            "runtime_reload_or_restart_policy",
        ],
    }
