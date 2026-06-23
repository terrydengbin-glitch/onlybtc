from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

API_SCHEMA_VERSION = "onlybtc.api.v1"


class ApiErrorItem(BaseModel):
    code: str
    message: str
    run_id: str | None = None
    stage: str | None = None
    recoverable: bool = False
    details: Any | None = None


class ApiErrorResponse(BaseModel):
    status: str = "error"
    schema_version: str = API_SCHEMA_VERSION
    api_schema_version: str = API_SCHEMA_VERSION
    created_at: str
    error: ApiErrorItem
    errors: list[ApiErrorItem] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    http_status: int


class ApiOkEnvelope(BaseModel):
    status: str = "ok"
    schema_version: str = API_SCHEMA_VERSION
    api_schema_version: str = API_SCHEMA_VERSION
    created_at: str
    run_lineage: dict[str, Any] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[ApiErrorItem] = Field(default_factory=list)


def ok_response(
    data: dict[str, Any] | None = None,
    *,
    schema_version: str = API_SCHEMA_VERSION,
    run_lineage: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = dict(data or {})
    payload.setdefault("status", "ok")
    payload.setdefault("schema_version", schema_version)
    payload.setdefault("api_schema_version", API_SCHEMA_VERSION)
    payload.setdefault("created_at", datetime.now(UTC).isoformat())
    payload.setdefault("run_lineage", run_lineage or payload.get("run_lineage") or {})
    payload.setdefault("warnings", warnings or payload.get("warnings") or [])
    payload.setdefault("errors", [])
    return payload


def missing_response(
    message: str,
    *,
    code: str = "missing_payload",
    schema_version: str = API_SCHEMA_VERSION,
    run_lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "missing",
        "schema_version": schema_version,
        "api_schema_version": API_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "run_lineage": run_lineage or {},
        "message": message,
        "errors": [
            {
                "code": code,
                "message": message,
                "recoverable": True,
            }
        ],
        "warnings": [],
    }


def error_payload(
    *,
    code: str,
    message: str,
    status_code: int = 500,
    run_id: str | None = None,
    stage: str | None = None,
    recoverable: bool = False,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "schema_version": API_SCHEMA_VERSION,
        "api_schema_version": API_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "error": {
            "code": code,
            "message": message,
            "run_id": run_id,
            "stage": stage,
            "recoverable": recoverable,
            "details": details,
        },
        "errors": [
            {
                "code": code,
                "message": message,
                "run_id": run_id,
                "stage": stage,
                "recoverable": recoverable,
                "details": details,
            }
        ],
        "warnings": [],
        "http_status": status_code,
    }


def _error_from_http_exception(request: Request, exc: StarletteHTTPException) -> dict[str, Any]:
    detail = exc.detail
    code = f"http_{exc.status_code}"
    message = str(detail)
    run_id = None
    stage = str(request.url.path)
    recoverable = 400 <= exc.status_code < 500
    details: Any | None = None
    if isinstance(detail, dict):
        code = str(detail.get("code") or detail.get("error_code") or code)
        message = str(detail.get("message") or detail.get("detail") or code)
        run_id = detail.get("run_id")
        stage = str(detail.get("stage") or stage)
        recoverable = bool(detail.get("recoverable", recoverable))
        details = detail.get("details")
    return error_payload(
        code=code,
        message=message,
        status_code=exc.status_code,
        run_id=run_id,
        stage=stage,
        recoverable=recoverable,
        details=details,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    payload = _error_from_http_exception(request, exc)
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    payload = error_payload(
        code="validation_error",
        message="Request validation failed",
        status_code=422,
        stage=str(request.url.path),
        recoverable=True,
        details=exc.errors(),
    )
    return JSONResponse(status_code=422, content=payload)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    payload = error_payload(
        code="internal_error",
        message=f"{type(exc).__name__}: {exc}",
        status_code=500,
        stage=str(request.url.path),
        recoverable=False,
    )
    return JSONResponse(status_code=500, content=payload)
