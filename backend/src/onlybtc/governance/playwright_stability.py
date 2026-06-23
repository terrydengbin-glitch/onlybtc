from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.sources.models import SourceKind
from onlybtc.sources.provider_auth import (
    PROVIDER_AUTH_CONFIGS,
    auth_status,
    provider_auth_paths,
)
from onlybtc.sources.registry import SOURCE_CONFIGS
from onlybtc.sources.service import ensure_source_registry

SCHEMA_VERSION = "p7.c05.playwright_stability.v1"
SENSITIVE_KEYS = (
    "cookie",
    "cookies",
    "token",
    "authorization",
    "auth",
    "localStorage",
    "local_storage",
    "sessionStorage",
    "session_storage",
    "password",
    "secret",
)


def build_playwright_stability_report(
    db: Database = database,
    *,
    now: datetime | None = None,
    gitignore_path: Path | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        health_events = _recent_playwright_health_events(session)
    source_rows = _playwright_sources()
    provider_rows = [_provider_status(provider_id) for provider_id in sorted(PROVIDER_AUTH_CONFIGS)]
    artifact_policy = _artifact_policy(gitignore_path or paths.project_root / ".gitignore")
    alerts = _alerts(source_rows, provider_rows, artifact_policy, health_events)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "applied_to_production": False,
        "overall_status": _overall_status(alerts),
        "alert_count": len(alerts),
        "alerts": alerts,
        "playwright_sources": source_rows,
        "provider_auth": provider_rows,
        "artifact_policy": artifact_policy,
        "recent_playwright_health_events": health_events,
        "stability_contract": {
            "headed_login_bootstrap": "onlybtc provider-login <provider_id>",
            "headless_login_verify": "onlybtc provider-auth-status <provider_id> --verify",
            "auth_storage_dir": "playwright-artifacts/auth/{provider_id}",
            "login_required_degradation": "provider_health_warning_not_global_collection_block",
            "sensitive_fields_forbidden": list(SENSITIVE_KEYS),
        },
        "guardrails": [
            "audit_only",
            "does_not_open_browser",
            "does_not_collect_sources",
            "does_not_store_secrets_in_report",
            "does_not_modify_state_machine",
            "does_not_emit_trading_advice",
            "requires_p7_c08_before_production_apply",
        ],
    }


def status_contains_sensitive_fields(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _looks_sensitive_key(str(key)):
                return True
            if status_contains_sensitive_fields(nested):
                return True
    elif isinstance(value, list):
        return any(status_contains_sensitive_fields(item) for item in value)
    return False


def _playwright_sources() -> list[dict[str, Any]]:
    rows = []
    for source in SOURCE_CONFIGS:
        if source.kind != SourceKind.PLAYWRIGHT:
            continue
        provider_id = source.metadata.get("provider_id") or _infer_provider_id(source.source_id)
        rows.append(
            {
                "source_id": source.source_id,
                "group_name": source.group_name,
                "method": source.method,
                "fallback_source_id": source.fallback_source_id,
                "metrics": list(source.metrics),
                "quality_score": source.metadata.get("quality_score"),
                "requires_human_verified_profile": bool(
                    source.metadata.get("requires_human_verified_profile")
                    or provider_id
                ),
                "linked_provider_id": provider_id,
                "profile_dir": source.metadata.get("profile_dir"),
                "freshness_policy": source.metadata.get("freshness_policy") or {},
            }
        )
    return sorted(rows, key=lambda item: item["source_id"])


def _provider_status(provider_id: str) -> dict[str, Any]:
    auth_paths = provider_auth_paths(provider_id)
    status = auth_status(provider_id)
    sanitized = _sanitize_status(status)
    return {
        "provider_id": provider_id,
        "configured": bool(status.get("configured")),
        "verified": bool(status.get("verified")),
        "message": str(status.get("message") or ""),
        "auth_dir": str(auth_paths.auth_dir),
        "profile_dir": str(auth_paths.profile_dir),
        "storage_state_path": str(auth_paths.storage_state_path),
        "status_path": str(auth_paths.status_path),
        "auth_dir_under_playwright_artifacts": _is_relative_to(
            auth_paths.auth_dir,
            paths.playwright_artifacts_dir,
        ),
        "status_has_sensitive_fields": status_contains_sensitive_fields(status),
        "sanitized_status": sanitized,
    }


def _sanitize_status(status: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in status.items()
        if not _looks_sensitive_key(str(key))
    }


def _artifact_policy(gitignore_path: Path) -> dict[str, Any]:
    text = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    ignored = any(line.strip() == "playwright-artifacts/*" for line in text.splitlines())
    return {
        "gitignore_path": str(gitignore_path),
        "playwright_artifacts_dir": str(paths.playwright_artifacts_dir),
        "auth_dir": str(paths.playwright_artifacts_dir / "auth"),
        "playwright_artifacts_ignored": ignored,
        "status_files_allowed": True,
        "storage_state_reported_as_path_only": True,
    }


def _recent_playwright_health_events(session) -> list[dict[str, Any]]:
    source_ids = [source.source_id for source in SOURCE_CONFIGS if source.kind == SourceKind.PLAYWRIGHT]
    rows = session.scalars(
        select(schema.SourceHealthEvent)
        .where(schema.SourceHealthEvent.source_id.in_(source_ids))
        .order_by(schema.SourceHealthEvent.created_at.desc(), schema.SourceHealthEvent.id.desc())
        .limit(100)
    ).all()
    return [
        {
            "source_id": row.source_id,
            "status": row.status,
            "quality_score": row.quality_score,
            "latency_ms": row.latency_ms,
            "message": row.message,
            "created_at": row.created_at.isoformat(),
            "failure_category": _failure_category(row.message or row.status),
        }
        for row in rows
    ]


def _alerts(
    sources: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    artifact_policy: dict[str, Any],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if not artifact_policy["playwright_artifacts_ignored"]:
        alerts.append(
            {
                "alert_id": "playwright_artifacts_not_gitignored",
                "level": "critical",
                "scope": "artifact_policy",
                "reason": "playwright-artifacts/* missing from .gitignore",
                "recommended_action": "add_playwright_artifacts_to_gitignore_before_login",
            }
        )
    if not sources:
        alerts.append(
            {
                "alert_id": "no_playwright_sources_registered",
                "level": "warning",
                "scope": "source_registry",
                "reason": "no SourceKind.PLAYWRIGHT entries found",
                "recommended_action": "review_source_registry",
            }
        )
    for provider in providers:
        if not provider["auth_dir_under_playwright_artifacts"]:
            alerts.append(
                {
                    "alert_id": "provider_auth_dir_outside_artifacts",
                    "level": "critical",
                    "scope": "provider_auth",
                    "reason": provider["provider_id"],
                    "recommended_action": "move_auth_storage_under_playwright_artifacts",
                }
            )
        if provider["status_has_sensitive_fields"]:
            alerts.append(
                {
                    "alert_id": "provider_auth_status_sensitive_fields",
                    "level": "critical",
                    "scope": "provider_auth",
                    "reason": provider["provider_id"],
                    "recommended_action": "redact_status_file_and_rotate_session",
                }
            )
        if not provider["configured"] or not provider["verified"]:
            alerts.append(
                {
                    "alert_id": "provider_auth_not_verified",
                    "level": "warning",
                    "scope": "provider_auth",
                    "reason": f"{provider['provider_id']}: {provider['message']}",
                    "recommended_action": "degrade_provider_to_health_warning_until_verified",
                }
            )
    warning_events = [event for event in events if event["status"] in {"warning", "error", "stale"}]
    if warning_events:
        alerts.append(
            {
                "alert_id": "playwright_recent_health_warnings",
                "level": "warning",
                "scope": "source_health",
                "reason": ",".join(sorted({event["source_id"] for event in warning_events})[:20]),
                "recommended_action": "inspect_artifacts_selectors_or_provider_auth",
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


def _failure_category(message: str) -> str:
    text = message.lower()
    if "403" in text or "forbidden" in text or "access denied" in text:
        return "access_denied"
    if "timeout" in text:
        return "timeout"
    if "selector" in text or "parse" in text:
        return "selector_or_parse"
    if "login" in text or "auth" in text:
        return "auth"
    if "network" in text or "connect" in text:
        return "network"
    return "unknown"


def _infer_provider_id(source_id: str) -> str | None:
    if "glassnode" in source_id:
        return "glassnode"
    return None


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(item.lower() in lowered for item in SENSITIVE_KEYS)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
