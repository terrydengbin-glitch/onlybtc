from __future__ import annotations

import logging

from onlybtc.core.logging import SensitiveValueFilter, redact_sensitive_log_text


def test_redact_sensitive_log_text_masks_query_values() -> None:
    text = (
        "GET https://example.test/path?series_id=BTC"
        "&api_key=secret-key&access_token=token-value&authorization=Bearer abc"
        "&cookie=session-id&safe=value"
    )

    redacted = redact_sensitive_log_text(text)

    assert "secret-key" not in redacted
    assert "token-value" not in redacted
    assert "Bearer" not in redacted
    assert "session-id" not in redacted
    assert "api_key=<redacted>" in redacted
    assert "access_token=<redacted>" in redacted
    assert "authorization=<redacted>" in redacted
    assert "cookie=<redacted>" in redacted
    assert "safe=value" in redacted


def test_sensitive_value_filter_redacts_record_message() -> None:
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="url api_key=%s",
        args=("plain-secret",),
        exc_info=None,
    )

    assert SensitiveValueFilter().filter(record) is True
    assert record.getMessage() == "url api_key=<redacted>"
