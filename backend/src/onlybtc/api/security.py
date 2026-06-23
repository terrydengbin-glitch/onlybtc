from __future__ import annotations

import json
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select

from onlybtc.api.contracts import error_payload
from onlybtc.core.logging import redact_sensitive_log_text
from onlybtc.db import schema
from onlybtc.db.session import Database, database

API_SECURITY_SCHEMA_VERSION = "p9.c11.api_security.v1"
API_RATE_LIMIT_WINDOW_SECONDS = 60
API_RATE_LIMIT_MAX_REQUESTS = 240
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "session",
    "token",
)
_RATE_LIMIT_EXEMPT_PATHS = ("/api/health", "/api/events", "/reports/")
_REQUEST_BUCKETS: dict[str, deque[float]] = {}
_BUCKET_LOCK = threading.Lock()


async def api_security_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    rate_event = check_api_rate_limit(request)
    if rate_event is not None:
        record_rate_limit_event(rate_event)
        return JSONResponse(
            status_code=429,
            content=error_payload(
                code="api_rate_limited",
                message="API rate limit exceeded",
                status_code=429,
                stage=str(request.url.path),
                recoverable=True,
                details={
                    "limit": rate_event["limit"],
                    "current": rate_event["current"],
                    "reset_at": rate_event["reset_at"],
                },
            ),
        )

    response = await call_next(request)
    if _is_write_request(request):
        record_api_audit_event(
            action=_action_name(request),
            path=str(request.url.path),
            method=request.method,
            status_code=response.status_code,
            client_host=request.client.host if request.client else None,
            request_id=request.headers.get("x-request-id"),
            metadata={
                "query": dict(request.query_params),
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
    return await redact_json_response(response)


def redact_api_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                redacted[key_text] = "***redacted***"
            else:
                redacted[key_text] = redact_api_payload(item)
        return redacted
    if isinstance(value, list):
        return [redact_api_payload(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_log_text(value)
    return value


async def redact_json_response(response: Response) -> Response:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    headers = dict(response.headers)
    headers.pop("content-length", None)
    redacted = redact_api_payload(payload)
    return JSONResponse(
        content=redacted,
        status_code=response.status_code,
        headers=headers,
    )


def check_api_rate_limit(
    request: Request,
    *,
    now: float | None = None,
    limit: int = API_RATE_LIMIT_MAX_REQUESTS,
    window_seconds: int = API_RATE_LIMIT_WINDOW_SECONDS,
) -> dict[str, Any] | None:
    path = str(request.url.path)
    if not path.startswith("/api/") or path.startswith(_RATE_LIMIT_EXEMPT_PATHS):
        return None
    current_time = now if now is not None else time.monotonic()
    client_host = request.client.host if request.client else "unknown"
    key = f"{client_host}:{request.method}:{path}"
    with _BUCKET_LOCK:
        bucket = _REQUEST_BUCKETS.setdefault(key, deque())
        while bucket and current_time - bucket[0] >= window_seconds:
            bucket.popleft()
        bucket.append(current_time)
        current = len(bucket)
        reset_in = max(window_seconds - (current_time - bucket[0]), 0.0) if bucket else 0.0
    if current <= limit:
        return None
    return {
        "source_id": f"api:{path}",
        "current": current,
        "limit": limit,
        "reset_at": (datetime.now(UTC) + timedelta(seconds=reset_in)).isoformat(),
        "path": path,
        "method": request.method,
        "client_host": client_host,
    }


def reset_rate_limit_state() -> None:
    with _BUCKET_LOCK:
        _REQUEST_BUCKETS.clear()


def record_rate_limit_event(
    event: dict[str, Any],
    *,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    reset_at = event.get("reset_at")
    with db.session() as session:
        row = schema.RateLimitEvent(
            source_id=str(event.get("source_id") or "api:unknown"),
            current=int(event.get("current") or 0),
            limit=int(event.get("limit") or 0),
            reset_at=datetime.fromisoformat(str(reset_at)) if reset_at else None,
        )
        session.add(row)
        session.flush()
        return {
            "source_id": row.source_id,
            "current": row.current,
            "limit": row.limit,
            "reset_at": row.reset_at.isoformat() if row.reset_at else None,
        }


def record_api_audit_event(
    *,
    action: str,
    path: str,
    method: str,
    status_code: int,
    actor: str = "local_api",
    client_host: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    status = "success" if status_code < 400 else "failed"
    safe_metadata = redact_api_payload(metadata or {})
    with db.session() as session:
        row = schema.AuditLog(
            event_id=f"api-audit-{uuid4().hex[:12]}",
            action=action,
            path=path,
            method=method.upper(),
            status=status,
            status_code=status_code,
            actor=actor,
            client_host=client_host,
            request_id=request_id,
            metadata_json=safe_metadata,
        )
        session.add(row)
        session.flush()
        return _audit_row_payload(row)


def api_security_summary(
    *,
    limit: int = 20,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        audit_rows = session.scalars(
            select(schema.AuditLog).order_by(schema.AuditLog.created_at.desc()).limit(limit)
        ).all()
        rate_rows = session.scalars(
            select(schema.RateLimitEvent)
            .where(schema.RateLimitEvent.source_id.like("api:%"))
            .order_by(schema.RateLimitEvent.created_at.desc())
            .limit(limit)
        ).all()
    return {
        "schema_version": API_SECURITY_SCHEMA_VERSION,
        "status": "ok",
        "audit_logs": [_audit_row_payload(row) for row in audit_rows],
        "rate_limit_events": [
            {
                "source_id": row.source_id,
                "current": row.current,
                "limit": row.limit,
                "reset_at": row.reset_at.isoformat() if row.reset_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rate_rows
        ],
        "redaction": {
            "enabled": True,
            "sensitive_keys": list(_SENSITIVE_KEY_PARTS),
        },
    }


def _audit_row_payload(row: schema.AuditLog) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "action": row.action,
        "path": row.path,
        "method": row.method,
        "status": row.status,
        "status_code": row.status_code,
        "actor": row.actor,
        "client_host": row.client_host,
        "request_id": row.request_id,
        "metadata": redact_api_payload(row.metadata_json or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _is_write_request(request: Request) -> bool:
    return request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"} and str(
        request.url.path
    ).startswith("/api/")


def _action_name(request: Request) -> str:
    path = str(request.url.path).strip("/").replace("/", ".").replace("-", "_")
    return f"{request.method.lower()}.{path or 'root'}"
