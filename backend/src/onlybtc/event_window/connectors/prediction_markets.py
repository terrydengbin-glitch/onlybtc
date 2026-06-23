from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from onlybtc.event_window.connectors.common import FetchResult, stable_hash

KALSHI_MARKETS_URL = "https://external-api.kalshi.com/trade-api/v2/markets"
POLYMARKET_EVENTS_URL = "https://gamma-api.polymarket.com/events"

HEADERS = {
    "User-Agent": "onlyBTC EventWatchtower/1.0 (+https://localhost)",
    "Accept": "application/json,text/plain,*/*",
}

KALSHI_SERIES_BY_EVENT = {
    "FOMC": ["KXFEDDECISION", "KXFED"],
    "CPI": ["KXCPI"],
    "PCE": ["KXPCECORE", "PCECORE"],
}

POLYMARKET_KEYWORDS_BY_EVENT = {
    "FOMC": ["fed", "fomc", "interest rate", "rate cut", "rate hike"],
    "CPI": ["cpi", "inflation"],
    "PCE": ["pce", "inflation"],
}


def collect_prediction_market_odds(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    asof = now if now.tzinfo else now.replace(tzinfo=UTC)
    event_type = str(event.get("event_type") or "").upper()
    fetches: list[dict[str, Any]] = []
    markets: list[dict[str, Any]] = []

    kalshi_markets, kalshi_fetches = _fetch_kalshi(event_type)
    markets.extend(kalshi_markets)
    fetches.extend(fetch.payload() for fetch in kalshi_fetches)

    polymarket_markets, polymarket_fetch = _fetch_polymarket(event_type)
    markets.extend(polymarket_markets)
    fetches.append(polymarket_fetch.payload())

    liquid = [market for market in markets if _liquidity_status(market) == "pass"]
    status = "available" if markets else "missing"
    if markets and not liquid:
        status = "available_low_liquidity"
    return {
        "snapshot": {
            "asof_ts": asof.isoformat(),
            "event_id": event.get("event_id"),
            "event_type": event_type,
            "status": status,
            "source_tier": "prediction_market",
            "markets": markets[:12],
            "market_count": len(markets),
            "liquid_market_count": len(liquid),
            "source_count": len({market["provider"] for market in markets}),
            "warning": "prediction_market_not_official",
        },
        "source_fetches": fetches,
    }


def _fetch_kalshi(event_type: str) -> tuple[list[dict[str, Any]], list[FetchResult]]:
    markets: list[dict[str, Any]] = []
    fetches: list[FetchResult] = []
    series = KALSHI_SERIES_BY_EVENT.get(event_type, [])
    for ticker in series:
        url = f"{KALSHI_MARKETS_URL}?limit=80&series_ticker={ticker}"
        response, started, finished, error = _get(url)
        if response is None or response.status_code >= 400:
            fetches.append(
                _failure(
                    "kalshi-public-markets",
                    "prediction_market",
                    url,
                    started,
                    finished,
                    response,
                    error,
                )
            )
            continue
        parsed = _parse_kalshi_markets(response.text)
        markets.extend(parsed)
        fetches.append(
            FetchResult(
                source_id="kalshi-public-markets",
                source_tier="prediction_market",
                endpoint_url=url,
                started_at=started,
                finished_at=finished,
                status="success" if parsed else "partial",
                http_status=response.status_code,
                payload_hash=stable_hash(response.text),
                parsed_item_count=len(parsed),
            )
        )
    return markets, fetches


def _fetch_polymarket(event_type: str) -> tuple[list[dict[str, Any]], FetchResult]:
    url = f"{POLYMARKET_EVENTS_URL}?limit=100&active=true&closed=false"
    response, started, finished, error = _get(url)
    if response is None or response.status_code >= 400:
        return [], _failure(
            "polymarket-public-events",
            "prediction_market",
            url,
            started,
            finished,
            response,
            error,
        )
    markets = _parse_polymarket_events(response.text, event_type)
    return markets, FetchResult(
        source_id="polymarket-public-events",
        source_tier="prediction_market",
        endpoint_url=url,
        started_at=started,
        finished_at=finished,
        status="success" if markets else "partial",
        http_status=response.status_code,
        payload_hash=stable_hash(response.text),
        parsed_item_count=len(markets),
    )


def _get(url: str) -> tuple[httpx.Response | None, datetime, datetime, str | None]:
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers=HEADERS) as client:
            response = client.get(url)
        return response, started, datetime.now(UTC), None
    except httpx.HTTPError as exc:
        return None, started, datetime.now(UTC), str(exc)


def _parse_kalshi_markets(text: str) -> list[dict[str, Any]]:
    try:
        rows = json.loads(text).get("markets") or []
    except (json.JSONDecodeError, TypeError):
        return []
    parsed: list[dict[str, Any]] = []
    for row in rows:
        price = _number(row.get("last_price"))
        yes_bid = _number(row.get("yes_bid"))
        yes_ask = _number(row.get("yes_ask"))
        if price is None and yes_bid is not None and yes_ask is not None:
            price = (yes_bid + yes_ask) / 2.0
        probability = None if price is None else round(price / 100.0, 4)
        parsed.append(
            {
                "provider": "kalshi",
                "source_tier": "prediction_market",
                "market_id": row.get("ticker"),
                "event_ticker": row.get("event_ticker"),
                "title": row.get("title"),
                "status": row.get("status"),
                "close_time": row.get("close_time"),
                "implied_probability": probability,
                "yes_bid": row.get("yes_bid"),
                "yes_ask": row.get("yes_ask"),
                "last_price": row.get("last_price"),
                "volume": _number(row.get("volume")),
                "liquidity": _number(row.get("liquidity")),
                "open_interest": _number(row.get("open_interest")),
                "liquidity_status": _liquidity_status(row),
                "warning": "prediction_market_not_official",
            }
        )
    return parsed


def _parse_polymarket_events(text: str, event_type: str) -> list[dict[str, Any]]:
    try:
        rows = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    keywords = POLYMARKET_KEYWORDS_BY_EVENT.get(event_type, [event_type.lower()])
    parsed: list[dict[str, Any]] = []
    for row in rows:
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("title", "slug", "description")
        ).lower()
        if not any(keyword in haystack for keyword in keywords):
            continue
        parsed.append(
            {
                "provider": "polymarket",
                "source_tier": "prediction_market",
                "market_id": row.get("id"),
                "title": row.get("title"),
                "status": "active",
                "implied_probability": None,
                "volume": _number(row.get("volume")),
                "liquidity": _number(row.get("liquidity")),
                "liquidity_status": _liquidity_status(row),
                "warning": "prediction_market_not_official",
            }
        )
    return parsed[:8]


def _liquidity_status(row: dict[str, Any]) -> str:
    liquidity = _number(row.get("liquidity"))
    volume = _number(row.get("volume"))
    open_interest = _number(row.get("open_interest"))
    if any(value is not None and value >= 10_000 for value in (liquidity, volume, open_interest)):
        return "pass"
    if any(value is not None and value > 0 for value in (liquidity, volume, open_interest)):
        return "weak"
    return "unknown"


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _failure(
    source_id: str,
    source_tier: str,
    url: str,
    started: datetime,
    finished: datetime,
    response: httpx.Response | None,
    error: str | None,
) -> FetchResult:
    return FetchResult(
        source_id=source_id,
        source_tier=source_tier,
        endpoint_url=url,
        started_at=started,
        finished_at=finished,
        status="failed",
        http_status=response.status_code if response is not None else None,
        error_code="http_error" if response is not None else "network_error",
        error_message=error or (response.text[:240] if response is not None else "request failed"),
    )
