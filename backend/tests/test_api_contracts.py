from __future__ import annotations

from fastapi.testclient import TestClient

from onlybtc.api.app import app
from onlybtc.api.contracts import ApiErrorResponse


def test_http_exception_uses_p9_error_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/p45/evidence/not-a-real-evidence-id")

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["schema_version"] == "onlybtc.api.v1"
    assert payload["api_schema_version"] == "onlybtc.api.v1"
    assert payload["http_status"] == 404
    assert payload["error"] == payload["errors"][0]
    assert payload["error"]["code"] == "http_404"
    assert payload["error"]["message"] == "Evidence not found"
    assert payload["error"]["stage"] == "/api/p45/evidence/not-a-real-evidence-id"
    assert payload["error"]["recoverable"] is True
    assert payload["error"]["run_id"] is None
    ApiErrorResponse.model_validate(payload)


def test_validation_error_uses_p9_error_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/p45/evidence?limit=not-an-int")

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["http_status"] == 422
    assert payload["error"]["code"] == "validation_error"
    assert payload["error"]["message"] == "Request validation failed"
    assert payload["error"]["stage"] == "/api/p45/evidence"
    assert payload["error"]["recoverable"] is True
    assert payload["error"]["details"]
    ApiErrorResponse.model_validate(payload)
