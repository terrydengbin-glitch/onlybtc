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


def test_source_action_endpoints_expose_safe_capability_contract() -> None:
    client = TestClient(app)
    client.post("/api/sources/collect?mode=mock")
    source_id = "coingecko-global"

    auth = client.get(f"/api/sources/{source_id}/auth-state")
    capture = client.get(f"/api/sources/{source_id}/last-capture")
    verify = client.post(f"/api/sources/{source_id}/open-verify-window")
    retry = client.post(f"/api/sources/{source_id}/retry-collect")

    for response in [auth, capture, verify, retry]:
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] in {"ok", "healthy", "disabled", "dry_run"}
        assert payload["schema_version"] == "p12.source_action.v1"
        assert payload["api_schema_version"] == "onlybtc.api.v1"
        assert payload["source_id"] == source_id
        assert "capability" in payload
        assert payload["capability"]["source_id"] == source_id
        assert payload["capability"]["external_side_effect"] is False

    assert auth.json()["auth_state"] in {"not_required", "unknown", "valid", "required"}
    assert capture.json()["last_capture"]["payload_redacted"] is True
    assert verify.json()["action"] == "open_verify_window"
    assert verify.json()["status"] in {"disabled", "dry_run"}
    assert retry.json()["action"] == "retry_collect"
    assert retry.json()["status"] == "dry_run"
    assert "secret" not in str(auth.json()).lower()


def test_source_action_missing_source_uses_error_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/sources/not-a-real-source/auth-state")

    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["schema_version"] == "onlybtc.api.v1"
    assert payload["error"]["message"] == "Source not found"
