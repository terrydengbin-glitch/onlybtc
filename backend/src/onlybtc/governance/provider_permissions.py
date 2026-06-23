from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from onlybtc.core.config import Settings, get_settings
from onlybtc.core.paths import paths
from onlybtc.governance.playwright_stability import SENSITIVE_KEYS, status_contains_sensitive_fields
from onlybtc.sources.models import SourceKind
from onlybtc.sources.provider_auth import PROVIDER_AUTH_CONFIGS, auth_status, provider_auth_paths
from onlybtc.sources.registry import SOURCE_CONFIGS

SCHEMA_VERSION = "p7.c07.provider_permission_source_onboarding.v1"
PROVIDER_PERMISSION_SENSITIVE_KEYS = (
    *SENSITIVE_KEYS,
    "api_key",
    "apikey",
    "access_key",
    "private_key",
)

API_KEY_PROVIDERS = {
    "fred": {
        "setting": "fred_api_key",
        "permission_level": "public_data_api",
        "allowed_metrics": "fred_source_metrics",
    },
    "openai": {
        "setting": "openai_api_key",
        "permission_level": "llm_runtime",
        "allowed_metrics": "p4_agent_runtime",
    },
    "deepseek": {
        "setting": "deepseek_api_key",
        "permission_level": "llm_runtime",
        "allowed_metrics": "p4_p45_llm_runtime",
    },
    "qwen": {
        "setting": "qwen_api_key",
        "permission_level": "llm_runtime",
        "allowed_metrics": "p4_agent_runtime",
    },
    "volcano": {
        "setting": "volcano_api_key",
        "permission_level": "llm_runtime",
        "allowed_metrics": "p4_agent_runtime",
    },
    "kimi": {
        "setting": "kimi_api_key",
        "permission_level": "llm_runtime",
        "allowed_metrics": "p4_agent_runtime",
    },
}


def build_provider_permission_report(
    *,
    settings: Settings | None = None,
    gitignore_path: Path | None = None,
    env_example_path: Path | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    provider_matrix = _provider_matrix(settings)
    source_onboarding = _source_onboarding_matrix()
    sensitive_scan = _source_sensitive_scan()
    safety = _filesystem_safety(
        gitignore_path or paths.project_root / ".gitignore",
        env_example_path or paths.project_root / ".env.example",
    )
    alerts = _alerts(provider_matrix, source_onboarding, sensitive_scan, safety)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "applied_to_production": False,
        "overall_status": _overall_status(alerts),
        "alert_count": len(alerts),
        "alerts": alerts,
        "provider_matrix": provider_matrix,
        "source_onboarding": source_onboarding,
        "sensitive_scan": sensitive_scan,
        "filesystem_safety": safety,
        "provider_locked_policy": {
            "metric_status": "missing",
            "missing_reason": "provider_locked",
            "forbidden_behavior": "do_not_fabricate_default_metric_values",
            "dashboard_visibility": "show_sanitized_provider_permission_status",
        },
        "guardrails": [
            "audit_only",
            "does_not_read_secret_values",
            "does_not_write_provider_tokens",
            "does_not_modify_source_registry",
            "does_not_modify_state_machine",
            "does_not_emit_trading_advice",
            "requires_p7_c08_before_production_apply",
        ],
    }


def _provider_matrix(settings: Settings) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider_id, meta in sorted(API_KEY_PROVIDERS.items()):
        configured = bool(getattr(settings, meta["setting"]))
        rows.append(
            {
                "provider_id": provider_id,
                "auth_method": "api_key",
                "configured": configured,
                "verified": configured,
                "last_verified_at": None,
                "permission_level": meta["permission_level"],
                "allowed_metrics": meta["allowed_metrics"],
                "secret_value_exposed": False,
                "status_message": "configured" if configured else "missing_api_key",
            }
        )
    for provider_id in sorted(PROVIDER_AUTH_CONFIGS):
        status = auth_status(provider_id)
        paths_row = provider_auth_paths(provider_id)
        rows.append(
            {
                "provider_id": provider_id,
                "auth_method": "manual_login_playwright",
                "configured": bool(status.get("configured")),
                "verified": bool(status.get("verified")),
                "last_verified_at": status.get("last_checked_at"),
                "permission_level": "session_cookie_page_access",
                "allowed_metrics": _provider_allowed_metrics(provider_id),
                "secret_value_exposed": status_contains_sensitive_fields(status),
                "status_message": status.get("message") or "status_unknown",
                "auth_dir": str(paths_row.auth_dir),
                "storage_state_path": str(paths_row.storage_state_path),
            }
        )
    rows.append(
        {
            "provider_id": "oauth_session_placeholder",
            "auth_method": "oauth/session",
            "configured": False,
            "verified": False,
            "last_verified_at": None,
            "permission_level": "not_configured",
            "allowed_metrics": [],
            "secret_value_exposed": False,
            "status_message": "no_oauth_provider_registered_yet",
        }
    )
    return rows


def _provider_allowed_metrics(provider_id: str) -> list[str]:
    metrics: list[str] = []
    for source in SOURCE_CONFIGS:
        if provider_id in source.source_id or source.metadata.get("provider_id") == provider_id:
            metrics.extend(source.metrics)
    return sorted(set(metrics))


def _source_onboarding_matrix() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in SOURCE_CONFIGS:
        needs_login = bool(
            source.metadata.get("requires_human_verified_profile")
            or source.metadata.get("requires_login")
            or source.metadata.get("provider_id")
            or "glassnode" in source.source_id
        )
        requires_paid = bool(
            source.metadata.get("requires_paid_plan")
            or source.metadata.get("paid_plan_required")
        )
        rows.append(
            {
                "source_id": source.source_id,
                "kind": str(source.kind),
                "method": source.method,
                "group_name": source.group_name,
                "metric_count": len(source.metrics),
                "needs_login": needs_login,
                "requires_paid_plan": requires_paid,
                "playwright_fallback_allowed": bool(
                    source.kind == SourceKind.PLAYWRIGHT or source.fallback_source_id
                ),
                "p5_settings_visible": True,
                "source_health_required": True,
                "schema_declared": bool(source.metrics and source.group_name and source.method),
                "provider_id": source.metadata.get("provider_id")
                or ("glassnode" if "glassnode" in source.source_id else None),
            }
        )
    return {
        "source_count": len(rows),
        "login_required_count": sum(1 for item in rows if item["needs_login"]),
        "paid_plan_required_count": sum(1 for item in rows if item["requires_paid_plan"]),
        "playwright_fallback_allowed_count": sum(
            1 for item in rows if item["playwright_fallback_allowed"]
        ),
        "rows": rows,
        "new_source_checklist": [
            "declare_source_id_name_kind_group_method_metrics",
            "declare_auth_method_and_provider_id_if_needed",
            "declare_requires_login",
            "declare_requires_paid_plan",
            "declare_playwright_fallback_allowed",
            "declare_freshness_policy",
            "declare_quality_score_or_quality_policy",
            "register_source_health_visibility",
            "register_p5_settings_visibility",
            "ensure_provider_locked_maps_to_missing_not_default_value",
        ],
    }


def _source_sensitive_scan() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for source in SOURCE_CONFIGS:
        paths_found = _sensitive_paths(source.metadata)
        if paths_found:
            findings.append(
                {
                    "source_id": source.source_id,
                    "metadata_paths": paths_found,
                }
            )
    return {
        "passed": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "sensitive_key_hints": list(SENSITIVE_KEYS),
    }


def _sensitive_paths(value: Any, prefix: str = "metadata") -> list[str]:
    paths_found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            current = f"{prefix}.{key}"
            if _looks_sensitive_key(str(key)):
                paths_found.append(current)
            paths_found.extend(_sensitive_paths(nested, current))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths_found.extend(_sensitive_paths(nested, f"{prefix}[{index}]"))
    return paths_found


def _filesystem_safety(gitignore_path: Path, env_example_path: Path) -> dict[str, Any]:
    gitignore_text = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    env_example_text = env_example_path.read_text(encoding="utf-8") if env_example_path.exists() else ""
    return {
        "gitignore_path": str(gitignore_path),
        "env_example_path": str(env_example_path),
        "env_file_ignored": any(line.strip() == ".env" for line in gitignore_text.splitlines()),
        "env_wildcard_ignored": any(line.strip() == ".env.*" for line in gitignore_text.splitlines()),
        "playwright_artifacts_ignored": any(
            line.strip() == "playwright-artifacts/*" for line in gitignore_text.splitlines()
        ),
        "env_example_has_placeholder_values": "your_fred_api_key_here" in env_example_text,
    }


def _alerts(
    provider_matrix: list[dict[str, Any]],
    source_onboarding: dict[str, Any],
    sensitive_scan: dict[str, Any],
    safety: dict[str, Any],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    exposed = [row for row in provider_matrix if row.get("secret_value_exposed")]
    if exposed:
        alerts.append(
            {
                "alert_id": "provider_secret_exposed",
                "level": "critical",
                "scope": "provider_permissions",
                "reason": ",".join(row["provider_id"] for row in exposed),
                "recommended_action": "redact_status_and_rotate_credentials",
            }
        )
    if not sensitive_scan["passed"]:
        alerts.append(
            {
                "alert_id": "source_registry_sensitive_metadata",
                "level": "critical",
                "scope": "source_registry",
                "reason": f"finding_count={sensitive_scan['finding_count']}",
                "recommended_action": "remove_secret_fields_from_source_metadata",
            }
        )
    missing_auth = [
        row
        for row in provider_matrix
        if row["auth_method"] in {"api_key", "manual_login_playwright"} and not row["configured"]
    ]
    if missing_auth:
        alerts.append(
            {
                "alert_id": "provider_permission_missing",
                "level": "warning",
                "scope": "provider_permissions",
                "reason": ",".join(row["provider_id"] for row in missing_auth[:20]),
                "recommended_action": "mark_affected_metrics_missing_provider_locked",
            }
        )
    unverified_sessions = [
        row
        for row in provider_matrix
        if row["auth_method"] == "manual_login_playwright" and not row["verified"]
    ]
    if unverified_sessions:
        alerts.append(
            {
                "alert_id": "manual_login_session_unverified",
                "level": "warning",
                "scope": "provider_permissions",
                "reason": ",".join(row["provider_id"] for row in unverified_sessions),
                "recommended_action": "verify_session_before_using_login_required_sources",
            }
        )
    if not (
        safety["env_file_ignored"]
        and safety["env_wildcard_ignored"]
        and safety["playwright_artifacts_ignored"]
    ):
        alerts.append(
            {
                "alert_id": "secret_files_not_fully_ignored",
                "level": "critical",
                "scope": "filesystem_safety",
                "reason": json.dumps(safety, ensure_ascii=False),
                "recommended_action": "update_gitignore_before_new_provider_onboarding",
            }
        )
    if source_onboarding["login_required_count"] and not any(
        row["auth_method"] == "manual_login_playwright" for row in provider_matrix
    ):
        alerts.append(
            {
                "alert_id": "login_required_sources_without_provider",
                "level": "warning",
                "scope": "source_onboarding",
                "reason": f"login_required_count={source_onboarding['login_required_count']}",
                "recommended_action": "register_manual_login_provider_before_enabling_source",
            }
        )
    return alerts


def _overall_status(alerts: list[dict[str, Any]]) -> str:
    levels = {alert["level"] for alert in alerts}
    if "critical" in levels:
        return "critical"
    if "warning" in levels:
        return "warning"
    if "watch" in levels:
        return "watch"
    return "healthy"


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    normalized = "".join(char for char in lowered if char.isalnum())
    return any(
        item.lower() in lowered
        or "".join(char for char in item.lower() if char.isalnum()) in normalized
        for item in PROVIDER_PERMISSION_SENSITIVE_KEYS
    )
