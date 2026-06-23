from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from onlybtc.core.logging import redact_sensitive_log_text
from onlybtc.core.paths import paths
from onlybtc.core.provider_registry import PROVIDER_REGISTRY

SETTINGS_AUDIT_SCHEMA_VERSION = "p10.c06.settings_key_audit.v1"
AUDIT_LOG_NAME = "settings-key-audit.jsonl"

PROVIDER_BY_ENV_KEY = {
    entry.env_key: entry.provider_id
    for entry in PROVIDER_REGISTRY
    if entry.env_key
}


def settings_audit_log_path(project_root: Path | None = None) -> Path:
    root = (project_root or paths.project_root).resolve()
    return root / "logs" / AUDIT_LOG_NAME


def record_settings_audit_event(
    *,
    action: str,
    env_keys: list[str] | tuple[str, ...],
    status: str = "success",
    actor: str = "local_api",
    provider_ids: list[str] | tuple[str, ...] | None = None,
    backup_path: str | None = None,
    error_message: str = "",
    operation_counts: dict[str, int] | None = None,
    project_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_keys = sorted({str(key) for key in env_keys if key})
    normalized_providers = sorted(
        {
            str(provider_id)
            for provider_id in (
                provider_ids
                if provider_ids is not None
                else [PROVIDER_BY_ENV_KEY.get(key, "") for key in normalized_keys]
            )
            if provider_id
        }
    )
    event = {
        "schema_version": SETTINGS_AUDIT_SCHEMA_VERSION,
        "event_id": f"settings-audit-{uuid4().hex[:12]}",
        "created_at": (now or datetime.now(UTC)).isoformat(),
        "actor": actor,
        "action": action,
        "status": status,
        "env_keys": normalized_keys,
        "provider_ids": normalized_providers,
        "backup_path": backup_path or "",
        "operation_counts": operation_counts or {},
        "error_message": redact_sensitive_log_text(error_message) if error_message else "",
        "redacted": True,
    }
    path = settings_audit_log_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def settings_audit_summary(
    *,
    project_root: Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    events = read_settings_audit_events(project_root=project_root, limit=limit)
    action_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for event in events:
        action = str(event.get("action") or "unknown")
        status = str(event.get("status") or "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema_version": SETTINGS_AUDIT_SCHEMA_VERSION,
        "status": "ok",
        "log_path": str(settings_audit_log_path(project_root)),
        "event_count": len(events),
        "action_counts": action_counts,
        "status_counts": status_counts,
        "events": events,
        "guardrails": [
            "no_plaintext_secret_values",
            "logs_store_env_key_names_only",
            "error_messages_are_redacted",
            "permission_gate_reserved_for_operator_auth",
        ],
    }


def read_settings_audit_events(
    *,
    project_root: Path | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    path = settings_audit_log_path(project_root)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(_sanitize_event(event))
        if len(events) >= limit:
            break
    return events


def _sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(event)
    if "error_message" in sanitized:
        sanitized["error_message"] = redact_sensitive_log_text(str(sanitized["error_message"]))
    for forbidden in ("value", "secret", "api_key", "token", "authorization"):
        sanitized.pop(forbidden, None)
    sanitized["redacted"] = True
    return sanitized
