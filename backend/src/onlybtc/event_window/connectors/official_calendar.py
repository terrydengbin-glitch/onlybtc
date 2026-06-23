from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ETXML
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any

import httpx

from onlybtc.core.config import get_settings
from onlybtc.core.paths import paths
from onlybtc.event_window.connectors.common import (
    ET,
    FetchResult,
    clean_text,
    event_id,
    format_event_time,
    parse_ics_datetime,
    stable_hash,
)

CLIENT_HEADERS = {
    "User-Agent": "onlyBTC EventWatchtower/1.0 (+https://localhost)",
    "Accept": "text/html,application/xml,text/xml,application/rss+xml,*/*",
}

BLS_ICS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BEA_SCHEDULE_URL = "https://www.bea.gov/news/schedule/"
FED_RSS_URL = "https://www.federalreserve.gov/feeds/press_all.xml"
FED_FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"
FRED_BLS_SOURCE_RELEASES_URL = "https://api.stlouisfed.org/fred/source/releases"
NYFED_ECON_CALENDAR_URL = "https://www.newyorkfed.org/research/calendars/nationalecon_cal"
DOL_BLS_ECONOMIC_DATA_URL = "https://www.dol.gov/newsroom/economicdata"
FRED_RELEASE_IDS = {
    "CPI": 10,
    "NFP": 50,
    "PPI": 46,
    "JOLTS": 192,
    "ECI": 11,
    "PRODUCTIVITY": 47,
    "IMPORT_EXPORT": 188,
}
BLS_CALENDAR_DISABLED_REASON = "bls.gov access denied in current runtime; FRED official_mirror is primary."
BLS_MANUAL_OVERRIDE_VERSION = "bls-calendar-v1"
BLS_MANUAL_OVERRIDE_UPDATED_AT = "2026-06-23T00:00:00+00:00"
BLS_MANUAL_OVERRIDE_SOURCE_NOTE = (
    "Deterministic BLS major-release fallback used only when official and mirror "
    "calendar providers are unavailable."
)


def collect_official_calendar(now: datetime) -> dict[str, Any]:
    asof = now if now.tzinfo else now.replace(tzinfo=UTC)
    items: list[dict[str, Any]] = []
    official_texts: list[dict[str, Any]] = []
    fetches: list[dict[str, Any]] = []

    bls_fetch = _disabled_bls_calendar_fetch(asof)
    bls_items, bls_fallback_fetch = _collect_bls_calendar_fallback(asof, bls_fetch)
    nyfed_crosscheck, nyfed_fetch = _collect_nyfed_time_crosscheck(asof)
    dol_docs, dol_fetch = _collect_dol_post_release_docs(asof)
    items.extend(_apply_bls_replacement_metadata(bls_items, nyfed_crosscheck, dol_docs))
    fetches.append(_calendar_fetch_payload(bls_fallback_fetch))
    fetches.append(_calendar_fetch_payload(bls_fetch, blocked_provider="bls-release-calendar"))
    fetches.append(_calendar_fetch_payload(nyfed_fetch))
    fetches.append(_calendar_fetch_payload(dol_fetch))

    bea_items, bea_fetch = _collect_bea_schedule(asof)
    items.extend(bea_items)
    fetches.append(_calendar_fetch_payload(bea_fetch))

    fomc_items, fomc_fetch = _collect_fomc_calendar(asof)
    items.extend(fomc_items)
    fetches.append(_calendar_fetch_payload(fomc_fetch))

    fed_texts, fed_fetch = _collect_fed_rss(asof)
    official_texts.extend(fed_texts)
    fetches.append(_calendar_fetch_payload(fed_fetch))

    deduped = _dedupe_future_events(items, asof)
    return {
        "calendar_items": deduped,
        "official_text_items": official_texts,
        "source_fetches": fetches,
    }


def _disabled_bls_calendar_fetch(now: datetime) -> FetchResult:
    return FetchResult(
        source_id="bls-release-calendar",
        source_tier="official",
        endpoint_url=BLS_ICS_URL,
        started_at=now,
        finished_at=now,
        status="failed",
        error_code="provider_failed_access_blocked",
        error_message=BLS_CALENDAR_DISABLED_REASON,
        parsed_item_count=0,
        fallback_used=False,
    )


def _http_get(url: str) -> tuple[httpx.Response | None, datetime, datetime, str | None]:
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=CLIENT_HEADERS) as client:
            response = client.get(url)
        finished = datetime.now(UTC)
        return response, started, finished, None
    except httpx.HTTPError as exc:
        finished = datetime.now(UTC)
        return None, started, finished, str(exc)


def _collect_bls_calendar(now: datetime) -> tuple[list[dict[str, Any]], FetchResult]:
    response, started, finished, error = _http_get(BLS_ICS_URL)
    if response is None or response.status_code >= 400:
        return [], _fetch_failure(
            "bls-release-calendar",
            "official",
            BLS_ICS_URL,
            started,
            finished,
            response,
            error,
        )
    events = _parse_bls_ics(response.text, now)
    return events, _fetch_success(
        "bls-release-calendar",
        "official",
        BLS_ICS_URL,
        started,
        finished,
        response,
        len(events),
    )


def _collect_bls_calendar_fallback(
    now: datetime,
    blocked_fetch: FetchResult,
) -> tuple[list[dict[str, Any]], FetchResult]:
    blocked_reason = str(blocked_fetch.http_status or blocked_fetch.error_code or "")
    events, fred_fetch = _collect_fred_bls_release_dates(now, blocked_reason)
    if events:
        return events, fred_fetch
    events = _manual_bls_calendar(now, blocked_reason)
    fetch = FetchResult(
        source_id="bls-calendar-manual-override",
        source_tier="manual_override",
        endpoint_url="manual://event-window/bls-calendar-v1",
        started_at=now,
        finished_at=now,
        status="fallback_used",
        error_code="blocked_provider",
        error_message=(
            "BLS official calendar was unavailable; "
            "using explicit manual override fallback."
        ),
        parsed_item_count=len(events),
        fallback_used=True,
    )
    return events, fetch


def _collect_fred_bls_release_dates(
    now: datetime,
    blocked_reason: str,
) -> tuple[list[dict[str, Any]], FetchResult]:
    api_key = _fred_api_key()
    started = datetime.now(UTC)
    if not api_key:
        finished = datetime.now(UTC)
        return [], FetchResult(
            source_id="fred-bls-release-calendar",
            source_tier="official_mirror",
            endpoint_url=FRED_RELEASE_DATES_URL,
            started_at=started,
            finished_at=finished,
            status="failed",
            error_code="api_key_missing",
            error_message="FRED release dates API requires ONLYBTC_FRED_API_KEY.",
            parsed_item_count=0,
            fallback_used=True,
        )
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    payload_hash_seed: list[str] = []
    with httpx.Client(timeout=12.0, follow_redirects=True, headers=CLIENT_HEADERS) as client:
        for event_type, release_id in FRED_RELEASE_IDS.items():
            url = (
                f"{FRED_RELEASE_DATES_URL}?release_id={release_id}"
                f"&file_type=json&api_key={api_key}"
                "&sort_order=desc&limit=24&include_release_dates_with_no_data=true"
            )
            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                errors.append(f"{event_type}:{exc}")
                continue
            payload_hash_seed.append(response.text)
            if response.status_code >= 400:
                errors.append(f"{event_type}:http_{response.status_code}")
                continue
            events.extend(_parse_fred_release_dates(response.text, now, event_type, blocked_reason))
    finished = datetime.now(UTC)
    status = "fallback_used" if events else "failed"
    return events, FetchResult(
        source_id="fred-bls-release-calendar",
        source_tier="official_mirror",
        endpoint_url=FRED_RELEASE_DATES_URL,
        started_at=started,
        finished_at=finished,
        status=status,
        error_code="blocked_provider" if events else "provider_failed",
        error_message=(
            "BLS calendar disabled/access denied; using FRED BLS release calendar official_mirror as primary replacement."
            if events
            else "; ".join(errors[:5]) or "FRED release dates returned no events."
        ),
        payload_hash=stable_hash("|".join(payload_hash_seed)) if payload_hash_seed else None,
        parsed_item_count=len(events),
        fallback_used=True,
    )


def _fred_api_key() -> str:
    value = os.getenv("ONLYBTC_FRED_API_KEY", "").strip()
    if value:
        return value
    settings_value = (get_settings().fred_api_key or "").strip()
    if settings_value:
        return settings_value
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        str(paths.project_root / ".env"),
        str(paths.backend_root / ".env"),
    ]
    for env_path in env_paths:
        try:
            with open(env_path, encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("ONLYBTC_FRED_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            continue
    return ""


def _parse_fred_release_dates(
    text: str,
    now: datetime,
    event_type: str,
    blocked_reason: str,
) -> list[dict[str, Any]]:
    try:
        import json

        rows = json.loads(text).get("release_dates") or []
    except (ValueError, TypeError):
        return []
    events: list[dict[str, Any]] = []
    for row in rows:
        release_date = str(row.get("date") or row.get("release_date") or "")
        try:
            release_day = date.fromisoformat(release_date)
        except ValueError:
            continue
        release_local = datetime.combine(
            release_day,
            _default_bls_release_time(event_type),
            tzinfo=ET,
        )
        release_utc = release_local.astimezone(UTC)
        if release_utc < now - _hours(24):
            continue
        title = _title_for_bls(event_type, event_type)
        payload = _event_payload(
            event_type,
            title,
            "critical",
            release_utc,
            FRED_RELEASE_DATES_URL,
            "FRED release dates mirror",
        )
        payload.update(
            {
                "source_tier": "official_mirror",
                "provider": "fred_bls_release_calendar",
                "original_authority": "BLS",
                "mirror_provider": "FRED",
                "release_id": FRED_RELEASE_IDS.get(event_type),
                "release_name": title,
                "calendar_confidence": 0.86,
                "blocked_provider": "bls-release-calendar",
                "blocked_reason": blocked_reason or "provider_failed_access_blocked",
                "fallback_used": True,
                "time_inferred": True,
                "release_date": release_date,
                "data_quality_flags": ["fred_release_dates_time_inferred"],
                "replacement_reason": "bls_calendar_disabled_access_denied",
                "source_lineage": _bls_replacement_lineage(
                    "fred_bls_release_calendar",
                    "official_mirror",
                    0.86,
                    blocked_reason,
                ),
            }
        )
        events.append(payload)
    return sorted(events, key=lambda event: str(event.get("release_time") or ""))[:6]


def _collect_nyfed_time_crosscheck(now: datetime) -> tuple[dict[str, dict[str, Any]], FetchResult]:
    response, started, finished, error = _http_get(NYFED_ECON_CALENDAR_URL)
    if response is None or response.status_code >= 400:
        return {}, _fetch_failure(
            "nyfed-economic-indicators-calendar",
            "official_fed_crosscheck",
            NYFED_ECON_CALENDAR_URL,
            started,
            finished,
            response,
            error,
        )
    text = clean_text(response.text)
    mapping: dict[str, dict[str, Any]] = {}
    aliases = {
        "CPI": ["Consumer Price Index", "CPI"],
        "NFP": ["Employment Situation", "Nonfarm"],
        "PPI": ["Producer Price Index", "PPI"],
        "JOLTS": ["Job Openings", "JOLTS"],
        "ECI": ["Employment Cost Index"],
    }
    for event_type, names in aliases.items():
        if any(name.lower() in text.lower() for name in names):
            mapping[event_type] = {
                "source_id": "nyfed-economic-indicators-calendar",
                "source_tier": "official_fed_crosscheck",
                "source_url": NYFED_ECON_CALENDAR_URL,
                "status": "present_on_calendar",
            }
    return mapping, _fetch_success(
        "nyfed-economic-indicators-calendar",
        "official_fed_crosscheck",
        NYFED_ECON_CALENDAR_URL,
        started,
        finished,
        response,
        len(mapping),
    )


def _collect_dol_post_release_docs(now: datetime) -> tuple[dict[str, dict[str, Any]], FetchResult]:
    response, started, finished, error = _http_get(DOL_BLS_ECONOMIC_DATA_URL)
    if response is None or response.status_code >= 400:
        return {}, _fetch_failure(
            "dol-bls-economicdata",
            "official_parent_mirror",
            DOL_BLS_ECONOMIC_DATA_URL,
            started,
            finished,
            response,
            error,
        )
    text = clean_text(response.text)
    mapping: dict[str, dict[str, Any]] = {}
    aliases = {
        "CPI": ["Consumer Price Index", "CPI"],
        "NFP": ["Employment Situation"],
        "PPI": ["Producer Price Index", "PPI"],
        "ECI": ["Employment Cost Index"],
        "PRODUCTIVITY": ["Productivity and Costs"],
        "IMPORT_EXPORT": ["Import and Export Price"],
    }
    for event_type, names in aliases.items():
        if any(name.lower() in text.lower() for name in names):
            mapping[event_type] = {
                "source_id": "dol-bls-economicdata",
                "source_tier": "official_parent_mirror",
                "source_url": DOL_BLS_ECONOMIC_DATA_URL,
                "use_for": ["post_release_pdf", "release_document_link", "arrival_confirmation"],
                "not_use_for": ["full_future_schedule"],
            }
    return mapping, _fetch_success(
        "dol-bls-economicdata",
        "official_parent_mirror",
        DOL_BLS_ECONOMIC_DATA_URL,
        started,
        finished,
        response,
        len(mapping),
    )


def _apply_bls_replacement_metadata(
    events: list[dict[str, Any]],
    nyfed_crosscheck: dict[str, dict[str, Any]],
    dol_docs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for raw in events:
        item = dict(raw)
        event_type = str(item.get("event_type") or "")
        nyfed = nyfed_crosscheck.get(event_type)
        if nyfed:
            item["time_crosscheck_status"] = "present_on_nyfed_calendar"
            item["time_crosscheck_source"] = nyfed
        else:
            item["time_crosscheck_status"] = "missing"
        dol = dol_docs.get(event_type)
        if dol:
            item["post_release_document_mirror"] = dol
        item["calendar_replacement_stack"] = {
            "primary": "fred-bls-release-calendar",
            "time_crosscheck": "nyfed-economic-indicators-calendar",
            "post_release_document_mirror": "dol-bls-economicdata",
            "disabled": ["bls-release-calendar"],
        }
        enriched.append(item)
    return enriched


def _default_bls_release_time(event_type: str):
    from datetime import time

    if event_type == "JOLTS":
        return time(10, 0)
    return time(8, 30)


def _parse_bls_ics(text: str, now: datetime) -> list[dict[str, Any]]:
    wanted = {
        "Consumer Price Index": "CPI",
        "Producer Price Index": "PPI",
        "Employment Situation": "NFP",
        "Job Openings and Labor Turnover": "JOLTS",
        "Employment Cost Index": "ECI",
    }
    events: list[dict[str, Any]] = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.split(";", 1)[0]] = value
        summary = clean_text(unescape(fields.get("SUMMARY", "")))
        event_type = next(
            (kind for name, kind in wanted.items() if name.lower() in summary.lower()),
            "",
        )
        if not event_type:
            continue
        release_time = parse_ics_datetime(fields.get("DTSTART", ""))
        if release_time is None or release_time < now.replace(tzinfo=UTC) - _hours(2):
            continue
        title = _title_for_bls(event_type, summary)
        payload = _event_payload(
            event_type,
            title,
            "critical",
            release_time,
            BLS_ICS_URL,
            "BLS release calendar",
        )
        payload.update(
            {
                "provider": "bls_release_calendar",
                "original_authority": "BLS",
                "calendar_confidence": 0.95,
                "fallback_used": False,
                "source_lineage": [
                    {
                        "provider": "bls_release_calendar",
                        "source_tier": "official",
                        "status": "success",
                        "fallback_used": False,
                        "confidence": 0.95,
                    }
                ],
            }
        )
        events.append(payload)
    return events


def _title_for_bls(event_type: str, summary: str) -> str:
    return {
        "CPI": "Consumer Price Index",
        "PPI": "Producer Price Index",
        "NFP": "Employment Situation",
        "JOLTS": "Job Openings and Labor Turnover Survey",
        "ECI": "Employment Cost Index",
    }.get(event_type, summary)


def _manual_bls_calendar(now: datetime, blocked_reason: str) -> list[dict[str, Any]]:
    templates = [
        ("NFP", "Employment Situation", "first_friday", 8, 30),
        ("CPI", "Consumer Price Index", 12, 8, 30),
        ("PPI", "Producer Price Index", 13, 8, 30),
        ("JOLTS", "Job Openings and Labor Turnover Survey", 5, 10, 0),
    ]
    events: list[dict[str, Any]] = []
    cursor = now.astimezone(ET).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for month_offset in range(0, 4):
        month_start = _add_months(cursor, month_offset)
        for event_type, title, rule, hour, minute in templates:
            release_local = _rule_date(month_start, rule).replace(hour=hour, minute=minute)
            release_utc = release_local.astimezone(UTC)
            if release_utc < now - _hours(2):
                continue
            payload = _event_payload(
                event_type,
                title,
                "critical",
                release_utc,
                "manual://event-window/bls-calendar-v1",
                "BLS calendar manual override",
            )
            payload.update(
                {
                    "source_tier": "manual_override",
                    "provider": "manual_override_yaml",
                    "original_authority": "BLS",
                    "calendar_confidence": 0.45,
                    "blocked_provider": "bls-release-calendar",
                    "blocked_reason": blocked_reason or "provider_failed_access_blocked",
                    "fallback_used": True,
                    "override_version": BLS_MANUAL_OVERRIDE_VERSION,
                    "updated_at": BLS_MANUAL_OVERRIDE_UPDATED_AT,
                    "source_note": BLS_MANUAL_OVERRIDE_SOURCE_NOTE,
                    "data_quality_flags": ["bls_calendar_manual_override"],
                    "source_lineage": _bls_replacement_lineage(
                        "manual_override_yaml",
                        "manual_override",
                        0.45,
                        blocked_reason,
                    ),
                }
            )
            events.append(payload)
    return sorted(events, key=lambda item: str(item.get("release_time_utc") or ""))[:20]


def _add_months(value: datetime, months: int) -> datetime:
    month = value.month + months
    year = value.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return value.replace(year=year, month=month, day=1)


def _rule_date(month_start: datetime, rule: str | int) -> datetime:
    if rule == "first_friday":
        day = month_start
        while day.weekday() != 4:
            day += timedelta(days=1)
        return day
    day_num = min(int(rule), 28)
    return month_start.replace(day=day_num)


def _collect_bea_schedule(now: datetime) -> tuple[list[dict[str, Any]], FetchResult]:
    response, started, finished, error = _http_get(BEA_SCHEDULE_URL)
    if response is None or response.status_code >= 400:
        return [], _fetch_failure(
            "bea-release-schedule",
            "official",
            BEA_SCHEDULE_URL,
            started,
            finished,
            response,
            error,
        )
    events = _parse_bea_schedule(response.text, now)
    return events, _fetch_success(
        "bea-release-schedule",
        "official",
        BEA_SCHEDULE_URL,
        started,
        finished,
        response,
        len(events),
    )


def _parse_bea_schedule(text: str, now: datetime) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    row_pattern = re.compile(
        r"<tr[^>]*>.*?<div class=\"release-date\">(?P<date>[^<]+)</div>\s*"
        r"<small[^>]*>(?P<time>[^<]+)</small>.*?"
        r"<td class=\"release-title[^>]*>(?P<title>.*?)</td>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in row_pattern.finditer(text):
        title_raw = clean_text(re.sub(r"<[^>]+>", " ", unescape(match.group("title"))))
        if "Personal Income and Outlays" in title_raw:
            event_type = "PCE"
            title = "Personal Income and Outlays"
        elif "Gross Domestic Product" in title_raw or title_raw.startswith("GDP"):
            event_type = "GDP"
            title = "Gross Domestic Product"
        else:
            continue
        release_time = _parse_month_day_time(
            clean_text(match.group("date")),
            clean_text(match.group("time")),
            now,
        )
        if release_time is None or release_time < now - _hours(2):
            continue
        events.append(
            _event_payload(
                event_type,
                title,
                "critical",
                release_time,
                BEA_SCHEDULE_URL,
                "BEA release schedule",
            )
        )
    return events


def _collect_fomc_calendar(now: datetime) -> tuple[list[dict[str, Any]], FetchResult]:
    response, started, finished, error = _http_get(FED_FOMC_URL)
    if response is None or response.status_code >= 400:
        return [], _fetch_failure(
            "fed-fomc-calendar",
            "official",
            FED_FOMC_URL,
            started,
            finished,
            response,
            error,
        )
    events = _parse_fomc_page(response.text, now)
    return events, _fetch_success(
        "fed-fomc-calendar",
        "official",
        FED_FOMC_URL,
        started,
        finished,
        response,
        len(events),
    )


def _parse_fomc_page(text: str, now: datetime) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    year_pattern = (
        r"<a[^>]*>(20\d{2}) FOMC Meetings</a>.*?"
        r"(?=<a[^>]*>20\d{2} FOMC Meetings</a>|$)"
    )
    for year_match in re.finditer(year_pattern, text, flags=re.IGNORECASE | re.DOTALL):
        year = year_match.group(1)
        block = year_match.group(0)
        for meeting in re.finditer(
            r"fomc-meeting__month[^>]*><strong>(?P<month>[A-Z][a-z]+)</strong>.*?"
            r"fomc-meeting__date[^>]*>(?P<date>\d{1,2}(?:-\d{1,2})?\*?)</div>",
            block,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            month = meeting.group("month")
            date_text = meeting.group("date").replace("*", "")
            day = date_text.split("-")[-1]
            release_time = _parse_month_day_year(f"{month} {day}, {year}", hour=14, minute=0)
            if release_time is None or release_time < now - _hours(24):
                continue
            events.append(
                _event_payload(
                    "FOMC",
                    "FOMC meeting",
                    "critical",
                    release_time,
                    FED_FOMC_URL,
                    "Federal Reserve FOMC calendar",
                )
            )
    if events:
        return sorted(events, key=lambda item: str(item.get("release_time_utc") or ""))[:8]
    plain = clean_text(re.sub(r"<[^>]+>", " ", unescape(text)))
    for match in re.finditer(r"([A-Z][a-z]+ \d{1,2}(?:-\d{1,2})?, 20\d{2})", plain):
        value = match.group(1)
        month_year = re.match(r"([A-Z][a-z]+) (\d{1,2})(?:-(\d{1,2}))?, (20\d{2})", value)
        if not month_year:
            continue
        month, first_day, second_day, year = month_year.groups()
        day = second_day or first_day
        release_time = _parse_month_day_year(f"{month} {day}, {year}", hour=14, minute=0)
        if release_time is None or release_time < now - _hours(24):
            continue
        events.append(
            _event_payload(
                "FOMC",
                "FOMC meeting",
                "critical",
                release_time,
                FED_FOMC_URL,
                "Federal Reserve FOMC calendar",
            )
        )
    return sorted(events, key=lambda item: str(item.get("release_time_utc") or ""))[:8]


def _collect_fed_rss(now: datetime) -> tuple[list[dict[str, Any]], FetchResult]:
    response, started, finished, error = _http_get(FED_RSS_URL)
    if response is None or response.status_code >= 400:
        return [], _fetch_failure(
            "fed-rss",
            "official",
            FED_RSS_URL,
            started,
            finished,
            response,
            error,
        )
    items = _parse_fed_rss(response.text, now)
    return items, _fetch_success(
        "fed-rss",
        "official",
        FED_RSS_URL,
        started,
        finished,
        response,
        len(items),
    )


def _parse_fed_rss(text: str, now: datetime) -> list[dict[str, Any]]:
    try:
        root = ETXML.fromstring(text)
    except ETXML.ParseError:
        return []
    items = []
    for item in root.findall(".//item")[:12]:
        title = clean_text(item.findtext("title") or "")
        link = clean_text(item.findtext("link") or "")
        published_raw = clean_text(item.findtext("pubDate") or "")
        published_at = _parse_rss_date(published_raw) or now
        if published_at < now - _hours(24 * 30):
            continue
        source_hash = stable_hash(f"{title}|{link}|{published_at.isoformat()}")
        text_id = f"fed-rss-{source_hash[:16]}"
        items.append(
            {
                "text_id": text_id,
                "text_hash": source_hash,
                "source_name": "Federal Reserve RSS",
                "source_tier": "official",
                "published_at": published_at.isoformat(),
                "speaker": "",
                "title": title or "Federal Reserve RSS item",
                "url": link or FED_RSS_URL,
                "raw_text": title,
            }
        )
    return items


def _event_payload(
    event_type: str,
    title: str,
    importance: str,
    release_time: datetime,
    source_url: str,
    source_name: str,
) -> dict[str, Any]:
    release_time = release_time.astimezone(UTC)
    payload = {
        "event_id": event_id(event_type, title, release_time),
        "event_type": event_type,
        "title": title,
        "importance": importance,
        **format_event_time(release_time),
        "source_url": source_url,
        "source_name": source_name,
        "source_tier": "official",
        "status": "scheduled",
        "actual_available": False,
        "official_text_available": False,
        "data_quality_flags": [],
    }
    return payload


def _dedupe_future_events(items: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        release_text = str(item.get("release_time_utc") or item.get("release_time") or "")
        key = (str(item.get("event_type") or ""), release_text[:10])
        if not key[0] or not key[1]:
            continue
        release_time = datetime.fromisoformat(release_text)
        if release_time < now - _hours(24):
            continue
        current = by_key.get(key)
        if current is None or str(item.get("source_tier")) == "official":
            by_key[key] = item
    return sorted(by_key.values(), key=lambda item: str(item.get("release_time_utc") or ""))[:40]


def _fetch_success(
    source_id: str,
    source_tier: str,
    url: str,
    started: datetime,
    finished: datetime,
    response: httpx.Response,
    parsed_item_count: int,
) -> FetchResult:
    status = "success" if parsed_item_count > 0 else "partial"
    return FetchResult(
        source_id=source_id,
        source_tier=source_tier,
        endpoint_url=url,
        started_at=started,
        finished_at=finished,
        status=status,
        http_status=response.status_code,
        payload_hash=stable_hash(response.text),
        parsed_item_count=parsed_item_count,
    )


def _fetch_failure(
    source_id: str,
    source_tier: str,
    url: str,
    started: datetime,
    finished: datetime,
    response: httpx.Response | None,
    error: str | None,
) -> FetchResult:
    error_code = "network_error"
    if response is not None:
        error_code = (
            "provider_failed_access_blocked"
            if response.status_code in {401, 403}
            else "http_error"
        )
    return FetchResult(
        source_id=source_id,
        source_tier=source_tier,
        endpoint_url=url,
        started_at=started,
        finished_at=finished,
        status="failed",
        http_status=response.status_code if response is not None else None,
        error_code=error_code,
        error_message=error or (response.text[:300] if response is not None else "request failed"),
        parsed_item_count=0,
    )


def _calendar_fetch_payload(
    fetch: FetchResult,
    *,
    blocked_provider: str | None = None,
) -> dict[str, Any]:
    payload = fetch.payload()
    payload["provider"] = _provider_for_fetch(fetch)
    payload["confidence"] = 0.0 if fetch.status == "failed" else _confidence_for_tier(fetch.source_tier)
    if blocked_provider:
        payload["blocked_provider"] = blocked_provider
    if fetch.source_id == "bls-calendar-manual-override":
        payload["override_version"] = BLS_MANUAL_OVERRIDE_VERSION
        payload["updated_at"] = BLS_MANUAL_OVERRIDE_UPDATED_AT
        payload["source_note"] = BLS_MANUAL_OVERRIDE_SOURCE_NOTE
    return payload


def _provider_for_fetch(fetch: FetchResult) -> str:
    return {
        "bls-release-calendar": "bls_release_calendar",
        "fred-bls-release-calendar": "fred_bls_release_calendar",
        "bls-calendar-manual-override": "manual_override_yaml",
        "nyfed-economic-indicators-calendar": "nyfed_economic_indicators_calendar",
        "dol-bls-economicdata": "dol_bls_economicdata",
        "bea-release-schedule": "bea_release_schedule",
        "fed-fomc-calendar": "fed_fomc_calendar",
        "fed-rss": "fed_rss",
    }.get(fetch.source_id, fetch.source_id.replace("-", "_"))


def _confidence_for_tier(source_tier: str) -> float:
    return {
        "official": 0.95,
        "official_mirror": 0.86,
        "official_fed_crosscheck": 0.80,
        "official_parent_mirror": 0.78,
        "manual_override": 0.45,
    }.get(source_tier, 0.0)


def _bls_replacement_lineage(
    provider: str,
    source_tier: str,
    confidence: float,
    blocked_reason: str,
) -> list[dict[str, Any]]:
    return [
        {
            "provider": "bls_release_calendar",
            "source_tier": "official",
            "status": "failed",
            "error_code": "provider_failed_access_blocked",
            "blocked_provider": "bls-release-calendar",
            "blocked_reason": blocked_reason or "provider_failed_access_blocked",
            "fallback_used": False,
            "confidence": 0.0,
        },
        {
            "provider": provider,
            "source_tier": source_tier,
            "status": "fallback_used",
            "fallback_used": True,
            "confidence": confidence,
        },
    ]


def _parse_month_day_year(value: str, *, hour: int, minute: int) -> datetime | None:
    try:
        date = datetime.strptime(value, "%B %d, %Y")
    except ValueError:
        return None
    return date.replace(hour=hour, minute=minute, tzinfo=ET).astimezone(UTC)


def _parse_month_day_time(date_value: str, time_value: str, now: datetime) -> datetime | None:
    candidate = f"{date_value}, {now.year}"
    parsed = _parse_month_day_year(candidate, hour=8, minute=30)
    if parsed is None:
        return None
    time_match = re.match(r"(\d{1,2}):(\d{2})\s*([AP]M)", time_value, flags=re.IGNORECASE)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        if time_match.group(3).upper() == "PM" and hour != 12:
            hour += 12
        if time_match.group(3).upper() == "AM" and hour == 12:
            hour = 0
        parsed = parsed.astimezone(ET).replace(hour=hour, minute=minute).astimezone(UTC)
    if parsed < now - _hours(24 * 180):
        next_year = _parse_month_day_year(f"{date_value}, {now.year + 1}", hour=8, minute=30)
        return next_year
    return parsed


def _parse_rss_date(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value).astimezone(UTC)
    except (TypeError, ValueError):
        return None


def _hours(value: int | float):
    from datetime import timedelta

    return timedelta(hours=value)
