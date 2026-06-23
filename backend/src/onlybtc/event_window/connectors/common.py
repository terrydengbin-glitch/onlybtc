from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _safe_zoneinfo(name: str, fallback_offset_hours: int) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=fallback_offset_hours), name)


ET = _safe_zoneinfo("America/New_York", -4)
LOCAL_TZ = _safe_zoneinfo("Asia/Shanghai", 8)


@dataclass(frozen=True)
class FetchResult:
    source_id: str
    source_tier: str
    endpoint_url: str
    started_at: datetime
    finished_at: datetime
    status: str
    http_status: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    payload_hash: str | None = None
    parsed_item_count: int = 0
    fallback_used: bool = False

    def payload(self) -> dict[str, Any]:
        fetch_id_seed = (
            f"{self.source_id}|{self.endpoint_url}|{self.started_at.isoformat()}|"
            f"{self.status}|{self.payload_hash or ''}"
        )
        return {
            "fetch_id": f"fetch-{self.source_id}-{stable_hash(fetch_id_seed)[:12]}",
            "source_id": self.source_id,
            "source_tier": self.source_tier,
            "endpoint_url": self.endpoint_url,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "status": self.status,
            "http_status": self.http_status,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "payload_hash": self.payload_hash,
            "parsed_item_count": self.parsed_item_count,
            "fallback_used": self.fallback_used,
        }


def stable_hash(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "event"


def event_id(event_type: str, title: str, release_time: datetime) -> str:
    return f"{event_type.lower()}-{release_time.strftime('%Y%m%d%H%M')}-{slug(title)[:32]}"


def format_event_time(release_time_utc: datetime) -> dict[str, str]:
    utc_time = release_time_utc.astimezone(UTC)
    et_time = utc_time.astimezone(ET)
    local_time = utc_time.astimezone(LOCAL_TZ)
    return {
        "release_time": utc_time.isoformat(),
        "release_time_utc": utc_time.isoformat(),
        "release_time_et": et_time.strftime("%Y-%m-%d %H:%M %Z"),
        "release_time_local": local_time.strftime("%Y-%m-%d %H:%M %Z"),
    }


def parse_ics_datetime(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        if "T" in raw:
            return datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=ET).astimezone(UTC)
        return datetime.strptime(raw, "%Y%m%d").replace(tzinfo=ET).astimezone(UTC)
    except ValueError:
        return None
