from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

from onlybtc.api.security import (
    api_security_summary,
    check_api_rate_limit,
    record_api_audit_event,
    record_rate_limit_event,
    redact_api_payload,
    reset_rate_limit_state,
)
from onlybtc.db.session import Database


def test_api_payload_redaction_masks_sensitive_keys_and_strings() -> None:
    payload = {
        "provider": "fred",
        "api_key": "plain-secret",
        "nested": {
            "Authorization": "Bearer raw-token",
            "url": "https://example.test/data?api_key=raw-secret&safe=value",
        },
        "items": [{"cookie": "session-id", "safe": "value"}],
    }

    redacted = redact_api_payload(payload)
    text = str(redacted)

    assert redacted["api_key"] == "***redacted***"
    assert redacted["nested"]["Authorization"] == "***redacted***"
    assert redacted["items"][0]["cookie"] == "***redacted***"
    assert "plain-secret" not in text
    assert "raw-token" not in text
    assert "raw-secret" not in text
    assert "safe=value" in text


def test_api_audit_log_writes_redacted_sqlite_event(tmp_path: Path) -> None:
    db = Database(tmp_path / "api-audit.sqlite3")

    event = record_api_audit_event(
        action="post.api.p45.run_full_with_llm.jobs",
        path="/api/p45/run-full-with-llm/jobs",
        method="POST",
        status_code=200,
        request_id="req-1",
        metadata={
            "query": {"run_mode": "live"},
            "headers": {"Authorization": "Bearer raw-token"},
            "api_key": "plain-secret",
        },
        db=db,
    )
    summary = api_security_summary(db=db)

    assert event["status"] == "success"
    assert summary["audit_logs"][0]["path"] == "/api/p45/run-full-with-llm/jobs"
    assert summary["audit_logs"][0]["metadata"]["api_key"] == "***redacted***"
    assert "raw-token" not in str(summary)
    assert "plain-secret" not in str(summary)


def test_api_rate_limit_event_is_traceable_in_summary(tmp_path: Path) -> None:
    db = Database(tmp_path / "api-rate-limit.sqlite3")
    reset_rate_limit_state()
    request = _request("/api/p45/dashboard/latest")

    assert check_api_rate_limit(request, now=1.0, limit=1, window_seconds=60) is None
    limited = check_api_rate_limit(request, now=2.0, limit=1, window_seconds=60)
    assert limited is not None

    record_rate_limit_event(limited, db=db)
    summary = api_security_summary(db=db)

    assert summary["rate_limit_events"][0]["source_id"] == "api:/api/p45/dashboard/latest"
    assert summary["rate_limit_events"][0]["current"] == 2
    assert summary["rate_limit_events"][0]["limit"] == 1


def _request(path: str, method: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "client": ("testclient", 123),
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )
