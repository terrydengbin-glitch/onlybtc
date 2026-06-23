from __future__ import annotations

import re
from datetime import UTC, datetime
from html import unescape
from typing import Any

import httpx

from onlybtc.event_window.connectors.common import FetchResult, clean_text, stable_hash

ATLANTA_MPT_URLS = [
    "https://www.atlantafed.org/cenfis/market-probability-tracker",
    "https://www.atlantafed.org/cenfis/market-probability-tracker.aspx",
    "https://www.atlantafed.org/cenfis/market-probability-tracker.aspx?panel=1",
]

HEADERS = {
    "User-Agent": "onlyBTC EventWatchtower/1.0 (+https://localhost)",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def collect_atlanta_fed_mpt(now: datetime) -> dict[str, Any]:
    asof = now if now.tzinfo else now.replace(tzinfo=UTC)
    fetches: list[dict[str, Any]] = []
    payload: dict[str, Any] | None = None
    for url in ATLANTA_MPT_URLS:
        response, started, finished, error = _get(url)
        if response is None or response.status_code >= 400:
            fetch = FetchResult(
                source_id="atlanta-fed-mpt",
                source_tier="fed_research_tool",
                endpoint_url=url,
                started_at=started,
                finished_at=finished,
                status="failed",
                http_status=response.status_code if response is not None else None,
                error_code="http_error" if response is not None else "network_error",
                error_message=error
                or (response.text[:240] if response is not None else "request failed"),
            )
            fetches.append(fetch.payload())
            continue
        parsed = _parse_mpt_page(response.text)
        payload = {
            "provider": "atlanta_fed_market_probability_tracker",
            "source_tier": "fed_research_tool",
            "asof_ts": asof.isoformat(),
            "available": parsed["available"],
            "summary": parsed["summary"],
            "rate_range_probabilities": parsed["rate_range_probabilities"],
            "note": "not_same_as_cme_fomc_meeting_probability",
        }
        fetch = FetchResult(
            source_id="atlanta-fed-mpt",
            source_tier="fed_research_tool",
            endpoint_url=url,
            started_at=started,
            finished_at=finished,
            status="success" if parsed["available"] else "partial",
            http_status=response.status_code,
            payload_hash=stable_hash(response.text),
            parsed_item_count=len(parsed["rate_range_probabilities"]),
        )
        fetches.append(fetch.payload())
        break
    if payload is None:
        payload = {
            "provider": "atlanta_fed_market_probability_tracker",
            "source_tier": "fed_research_tool",
            "asof_ts": asof.isoformat(),
            "available": False,
            "summary": "",
            "rate_range_probabilities": [],
            "note": "not_same_as_cme_fomc_meeting_probability",
            "warning": "atlanta_fed_mpt_unavailable",
        }
    return {
        "snapshot": payload,
        "source_fetches": fetches,
    }


def _get(url: str) -> tuple[httpx.Response | None, datetime, datetime, str | None]:
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=HEADERS) as client:
            response = client.get(url)
        return response, started, datetime.now(UTC), None
    except httpx.HTTPError as exc:
        return None, started, datetime.now(UTC), str(exc)


def _parse_mpt_page(html: str) -> dict[str, Any]:
    text = clean_text(unescape(re.sub(r"<[^>]+>", " ", html)))
    has_tracker = (
        "Market Probability Tracker" in text
        or "market probability tracker" in text.lower()
    )
    rows: list[dict[str, Any]] = []
    for label, value in re.findall(
        r"(\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*%)\s+(\d+(?:\.\d+)?)\s*%",
        text,
        flags=re.IGNORECASE,
    ):
        try:
            rows.append({"range": label, "probability": float(value) / 100.0})
        except ValueError:
            continue
    return {
        "available": bool(has_tracker),
        "summary": text[:320] if has_tracker else "",
        "rate_range_probabilities": rows[:12],
    }
