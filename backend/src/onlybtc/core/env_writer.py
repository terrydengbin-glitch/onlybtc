from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from onlybtc.core.paths import paths
from onlybtc.core.provider_registry import PROVIDER_REGISTRY

ENV_UPDATE_SCHEMA_VERSION = "p10.c03.env_update.v1"
ENV_LINE_RE = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?)(?P<key>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P<sep>\s*=\s*)(?P<value>.*)$"
)
ALLOWED_ENV_KEYS = frozenset(
    entry.env_key for entry in PROVIDER_REGISTRY if entry.env_key
)


def write_env_updates(
    updates: dict[str, str],
    project_root: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    clean_updates = _validate_updates(updates)
    root = (project_root or paths.project_root).resolve()
    env_path = (root / ".env").resolve()
    if env_path.parent != root:
        raise ValueError(".env path must stay inside project root")

    backup_path = _backup_env_file(env_path, root, now=now)
    original_lines = _read_env_lines(env_path)
    updated_lines, changed_keys, appended_keys, operation_by_key = _merge_env_lines(
        original_lines,
        clean_updates,
    )
    _write_env_lines(env_path, updated_lines)
    created_keys = sorted(
        key for key, operation in operation_by_key.items() if operation == "created"
    )
    replaced_keys = sorted(
        key for key, operation in operation_by_key.items() if operation == "updated"
    )
    deleted_keys = sorted(
        key for key, operation in operation_by_key.items() if operation == "deleted"
    )
    return {
        "schema_version": ENV_UPDATE_SCHEMA_VERSION,
        "status": "ok",
        "env_path": str(env_path),
        "backup_path": str(backup_path),
        "updated_keys": sorted(changed_keys),
        "appended_keys": sorted(appended_keys),
        "created_keys": created_keys,
        "replaced_keys": replaced_keys,
        "deleted_keys": deleted_keys,
        "operation_counts": {
            "created": len(created_keys),
            "updated": len(replaced_keys),
            "deleted": len(deleted_keys),
        },
        "redacted": True,
    }


def _validate_updates(updates: dict[str, str]) -> dict[str, str]:
    if not updates:
        raise ValueError("No env updates provided")
    clean: dict[str, str] = {}
    for key, value in updates.items():
        normalized_key = str(key).strip()
        if normalized_key not in ALLOWED_ENV_KEYS:
            raise ValueError(f"Unsupported env key: {normalized_key}")
        text_value = "" if value is None else str(value).strip()
        if "\n" in text_value or "\r" in text_value:
            raise ValueError(f"Env value for {normalized_key} must be single-line")
        clean[normalized_key] = text_value
    return clean


def _backup_env_file(env_path: Path, root: Path, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d%H%M%S")
    backup_dir = root / "backups" / "env"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f".env.{stamp}.bak"
    suffix = 1
    while backup_path.exists():
        backup_path = backup_dir / f".env.{stamp}.{suffix}.bak"
        suffix += 1
    content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    backup_path.write_text(content, encoding="utf-8")
    return backup_path


def _read_env_lines(env_path: Path) -> list[str]:
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8").splitlines()


def _merge_env_lines(
    lines: list[str],
    updates: dict[str, str],
) -> tuple[list[str], set[str], set[str], dict[str, str]]:
    changed_keys: set[str] = set()
    appended_keys: set[str] = set()
    seen_keys: set[str] = set()
    operation_by_key: dict[str, str] = {}
    merged: list[str] = []
    for line in lines:
        match = ENV_LINE_RE.match(line)
        if not match:
            merged.append(line)
            continue
        key = match.group("key")
        if key not in updates:
            merged.append(line)
            continue
        seen_keys.add(key)
        changed_keys.add(key)
        operation_by_key[key] = "deleted" if updates[key] == "" else "updated"
        merged.append(f"{match.group('prefix')}{key}{match.group('sep')}{_format_env_value(updates[key])}")
    for key, value in updates.items():
        if key in seen_keys:
            continue
        appended_keys.add(key)
        changed_keys.add(key)
        operation_by_key[key] = "deleted" if value == "" else "created"
        merged.append(f"{key}={_format_env_value(value)}")
    return merged, changed_keys, appended_keys, operation_by_key


def _write_env_lines(env_path: Path, lines: list[str]) -> None:
    env_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines)
    if text:
        text += "\n"
    tmp_path = env_path.with_name(".env.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(env_path)


def _format_env_value(value: str) -> str:
    if value == "":
        return ""
    if re.search(r"\s|#|=|['\"]", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
