from __future__ import annotations

import logging
import re

from onlybtc.core.paths import paths

SENSITIVE_LOG_PATTERN = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|token|authorization|cookie|password|secret)\s*[:=]\s*([^&\s\"']+)"
)
AUTHORIZATION_BEARER_PATTERN = re.compile(
    r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._\-]+"
)
BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")


class SensitiveValueFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact_sensitive_log_text(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def redact_sensitive_log_text(value: str) -> str:
    redacted = AUTHORIZATION_BEARER_PATTERN.sub("authorization=<redacted>", value)
    redacted = BEARER_PATTERN.sub("bearer <redacted>", redacted)
    return SENSITIVE_LOG_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)


def configure_logging(level: int = logging.INFO) -> None:
    paths.ensure_directories()
    sensitive_filter = SensitiveValueFilter()
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(paths.logs_dir / "onlybtc.log", encoding="utf-8"),
    ]
    for handler in handlers:
        handler.addFilter(sensitive_filter)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
