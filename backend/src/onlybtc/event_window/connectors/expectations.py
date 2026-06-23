from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import unescape
from typing import Any

import httpx

from onlybtc.event_window.connectors.atlanta_mpt import collect_atlanta_fed_mpt
from onlybtc.event_window.connectors.common import FetchResult, stable_hash
from onlybtc.event_window.connectors.prediction_markets import collect_prediction_market_odds
from onlybtc.event_window.connectors.secondary_calendar import collect_secondary_calendar_mesh

CLEVELAND_NOWCAST_URL = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
CME_FEDWATCH_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
YAHOO_ZQ_URL = "https://query1.finance.yahoo.com/v8/finance/chart/ZQ%3DF?range=5d&interval=1d"
FRED_EFFR_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=EFFR"
HEADERS = {"User-Agent": "onlyBTC EventWatchtower/1.0 (+https://localhost)"}


def collect_expectation_snapshot(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    event_type = str(event.get("event_type") or "unknown")
    fetches: list[dict[str, Any]] = []
    nowcast = None
    nowcast_payload: dict[str, Any] | None = None
    market_implied = None
    market_payload: dict[str, Any] | None = None
    secondary_result = collect_secondary_calendar_mesh(event, now)
    secondary_snapshot = secondary_result.get("snapshot") or {}
    fetches.extend(secondary_result.get("source_fetches") or [])
    prediction_result = collect_prediction_market_odds(event, now)
    prediction_snapshot = prediction_result.get("snapshot") or {}
    fetches.extend(prediction_result.get("source_fetches") or [])

    if event_type in {"PCE", "CPI"}:
        nowcast_payload, fetch = _fetch_cleveland_nowcast(event_type)
        nowcast = _nowcast_value_for_event(nowcast_payload, event_type)
        fetches.append(fetch.payload())
    if event_type == "FOMC":
        market_payload, market_fetches = _fetch_fedwatch_or_proxy()
        fetches.extend(item.payload() for item in market_fetches)
        atlanta_result = collect_atlanta_fed_mpt(now)
        fetches.extend(atlanta_result.get("source_fetches") or [])
        if isinstance(market_payload, dict):
            market_payload["atlanta_fed_mpt"] = atlanta_result.get("snapshot")
        elif atlanta_result.get("snapshot", {}).get("available"):
            market_payload = {"atlanta_fed_mpt": atlanta_result.get("snapshot")}
        market_implied = market_payload

    consensus = secondary_snapshot.get("consensus")
    previous = None
    gap = None if consensus is None or nowcast is None else round(nowcast - consensus, 4)
    risk_direction = "unknown"
    if gap is not None:
        risk_direction = "hawkish" if gap > 0 else "dovish" if gap < 0 else "neutral"
    source_quality = _source_quality(fetches)
    flags = []
    consensus_status = str(secondary_snapshot.get("consensus_status") or "missing")
    if consensus is None:
        flags.append("consensus_missing")
    if nowcast is None and event_type in {"PCE", "CPI"}:
        flags.append("nowcast_unavailable")
    if consensus is None:
        flags.append("release_surprise_disabled_consensus_missing")
    if market_payload and market_payload.get("fedwatch_proxy_used"):
        flags.append("fedwatch_proxy_used")
    return {
        "snapshot": {
            "snapshot_id": f"exp-{event['event_id']}-{now.strftime('%Y%m%d%H%M')}",
            "event_id": event["event_id"],
            "snapshot_ts": now.isoformat(),
            "consensus": consensus,
            "previous": previous,
            "forecast": None,
            "nowcast": nowcast,
            "nowcast_payload": nowcast_payload,
            "market_implied": market_implied,
            "prediction_market_odds": prediction_snapshot,
            "expectation_gap": gap,
            "expectation_drift_1d": None,
            "expectation_drift_3d": None,
            "rate_cut_prob_drift_1d": None,
            "risk_direction": risk_direction,
            "source_quality": source_quality,
            "consensus_status": consensus_status,
            "consensus_source": None,
            "secondary_calendar_mesh": secondary_snapshot,
            "release_surprise_enabled": False,
            "source_lineage": [
                item for item in fetches if item.get("status") in {"success", "partial"}
            ],
            "data_quality_flags": flags,
        },
        "source_fetches": fetches,
    }


def _fetch_cleveland_nowcast(event_type: str) -> tuple[dict[str, Any] | None, FetchResult]:
    response, started, finished, error = _get(CLEVELAND_NOWCAST_URL)
    if response is None or response.status_code >= 400:
        return None, _failure(
            "cleveland-fed-nowcast",
            "expectation",
            CLEVELAND_NOWCAST_URL,
            started,
            finished,
            response,
            error,
        )
    payload = _parse_cleveland_nowcast(response.text)
    parsed_count = _count_parsed_values(payload)
    status = "success" if parsed_count else "partial"
    return payload, FetchResult(
        source_id="cleveland-fed-nowcast",
        source_tier="official_nowcast",
        endpoint_url=CLEVELAND_NOWCAST_URL,
        started_at=started,
        finished_at=finished,
        status=status,
        http_status=response.status_code,
        payload_hash=stable_hash(response.text),
        parsed_item_count=parsed_count,
    )


def _fetch_fedwatch_or_proxy() -> tuple[dict[str, Any] | None, list[FetchResult]]:
    response, started, finished, error = _get(CME_FEDWATCH_URL)
    fetches: list[FetchResult] = []
    if response is None or response.status_code >= 400:
        fetches.append(
            _failure(
                "cme-fedwatch",
                "official_market_implied",
                CME_FEDWATCH_URL,
                started,
                finished,
                response,
                error,
            )
        )
        proxy, proxy_fetches = _fetch_fed_funds_futures_proxy()
        fetches.extend(proxy_fetches)
        return proxy, fetches
    fetches.append(FetchResult(
        source_id="cme-fedwatch",
        source_tier="official_market_implied",
        endpoint_url=CME_FEDWATCH_URL,
        started_at=started,
        finished_at=finished,
        status="partial",
        http_status=response.status_code,
        payload_hash=stable_hash(response.text),
        parsed_item_count=0,
    ))
    proxy, proxy_fetches = _fetch_fed_funds_futures_proxy()
    fetches.extend(proxy_fetches)
    return proxy, fetches


def _fetch_fed_funds_futures_proxy() -> tuple[dict[str, Any] | None, list[FetchResult]]:
    fetches: list[FetchResult] = []
    zq_response, zq_started, zq_finished, zq_error = _get(YAHOO_ZQ_URL)
    effr_response, effr_started, effr_finished, effr_error = _get(FRED_EFFR_URL)
    zq_price = (
        _parse_yahoo_close(zq_response.text)
        if zq_response is not None and zq_response.status_code < 400
        else None
    )
    effr = (
        _parse_last_csv_value(effr_response.text)
        if effr_response is not None and effr_response.status_code < 400
        else None
    )
    fetches.append(
        _fetch_for_value(
            "zq-futures-yahoo-proxy",
            "market_implied_proxy",
            YAHOO_ZQ_URL,
            zq_started,
            zq_finished,
            zq_response,
            zq_error,
            zq_price,
        )
    )
    fetches.append(
        _fetch_for_value(
            "effr-fred-proxy",
            "official_mirror",
            FRED_EFFR_URL,
            effr_started,
            effr_finished,
            effr_response,
            effr_error,
            effr,
        )
    )
    if zq_price is None or effr is None:
        return None, fetches
    implied_avg_rate = 100.0 - zq_price
    expected_change_bps = (implied_avg_rate - effr) * 100.0
    probability = max(0.0, min(abs(expected_change_bps) / 25.0, 1.0))
    return {
        "provider": "zq_futures_proxy",
        "source_tier": "market_implied_proxy",
        "fedwatch_proxy_used": True,
        "implied_avg_rate": round(implied_avg_rate, 4),
        "current_effr": round(effr, 4),
        "expected_change_bps": round(expected_change_bps, 2),
        "cut_25bp_probability_proxy": round(probability, 4),
        "warning": "not_cme_fedwatch_probability",
    }, fetches


def _get(url: str) -> tuple[httpx.Response | None, datetime, datetime, str | None]:
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=HEADERS) as client:
            response = client.get(url)
        return response, started, datetime.now(UTC), None
    except httpx.HTTPError as exc:
        return None, started, datetime.now(UTC), str(exc)


def _parse_cleveland_nowcast(text: str) -> dict[str, Any] | None:
    tables = re.findall(r"<table[^>]*>.*?</table>", text, flags=re.IGNORECASE | re.DOTALL)
    parsed_tables: list[dict[str, Any]] = []
    for table in tables:
        headers = _extract_cells(table, "th")
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.IGNORECASE | re.DOTALL)
        body_rows = []
        for row in rows:
            cells = _extract_cells(row, "td")
            if len(cells) >= 5 and re.search(r"\d{4}|Q\d", cells[0]):
                body_rows.append(cells)
        if not headers or not body_rows:
            continue
        label = _table_label(headers, body_rows)
        if not label:
            continue
        parsed_tables.append(_table_payload(label, headers, body_rows[0]))
    if not parsed_tables:
        return None
    by_label = {item["label"]: item for item in parsed_tables}
    monthly_mom = by_label.get("monthly_mom") or parsed_tables[0]
    return {
        "provider": "cleveland_fed_inflation_nowcasting",
        "source_tier": "official_nowcast",
        "updated_date": monthly_mom.get("updated_date"),
        "period": monthly_mom.get("period"),
        "monthly_mom": (by_label.get("monthly_mom") or {}).get("values", {}),
        "monthly_yoy": (by_label.get("monthly_yoy") or {}).get("values", {}),
        "quarterly_annualized": (by_label.get("quarterly_annualized") or {}).get("values", {}),
        "parsed_tables": parsed_tables,
        "data_quality": "ok",
    }


def _extract_cells(html: str, tag: str) -> list[str]:
    cells = re.findall(
        rf"<{tag}[^>]*>(.*?)</{tag}>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(cell))).strip() for cell in cells]


def _table_label(headers: list[str], rows: list[list[str]]) -> str:
    first_period = rows[0][0].lower()
    if "q" in first_period:
        return "quarterly_annualized"
    values = [_to_float(cell) for cell in rows[0][1:5]]
    if any(value is not None and abs(value) > 2.0 for value in values):
        return "monthly_yoy"
    return "monthly_mom"


def _table_payload(label: str, headers: list[str], row: list[str]) -> dict[str, Any]:
    mapping = {
        "CPI": "cpi",
        "Core CPI": "core_cpi",
        "PCE": "pce",
        "Core PCE": "core_pce",
    }
    values: dict[str, float | None] = {}
    for index, header in enumerate(headers[1:5], start=1):
        key = mapping.get(header)
        if key:
            values[key] = _to_float(row[index]) if index < len(row) else None
    return {
        "label": label,
        "period": row[0],
        "values": values,
        "updated_date": row[5] if len(row) > 5 else "",
    }


def _count_parsed_values(payload: dict[str, Any] | None) -> int:
    if not payload:
        return 0
    total = 0
    for key in ("monthly_mom", "monthly_yoy", "quarterly_annualized"):
        values = payload.get(key) or {}
        total += sum(1 for value in values.values() if value is not None)
    return total


def _nowcast_value_for_event(payload: dict[str, Any] | None, event_type: str) -> float | None:
    if not payload:
        return None
    values = payload.get("monthly_mom") or {}
    key = "pce" if event_type == "PCE" else "cpi"
    return _to_float(values.get(key))


def _parse_yahoo_close(text: str) -> float | None:
    try:
        payload = json.loads(text)
        result = (payload.get("chart", {}).get("result") or [])[0]
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close") or []
        closes = [float(item) for item in closes if item is not None]
        return closes[-1] if closes else None
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _parse_last_csv_value(text: str) -> float | None:
    for line in reversed(text.splitlines()):
        parts = line.split(",")
        if len(parts) < 2 or not parts[1].strip():
            continue
        return _to_float(parts[1])
    return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fetch_for_value(
    source_id: str,
    source_tier: str,
    url: str,
    started: datetime,
    finished: datetime,
    response: httpx.Response | None,
    error: str | None,
    value: float | None,
) -> FetchResult:
    if response is None or response.status_code >= 400:
        return _failure(source_id, source_tier, url, started, finished, response, error)
    return FetchResult(
        source_id=source_id,
        source_tier=source_tier,
        endpoint_url=url,
        started_at=started,
        finished_at=finished,
        status="success" if value is not None else "partial",
        http_status=response.status_code,
        payload_hash=stable_hash(response.text),
        parsed_item_count=1 if value is not None else 0,
    )


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
        error_message=error or (response.text[:300] if response is not None else "request failed"),
    )


def _source_quality(fetches: list[dict[str, Any]]) -> str:
    if any(item.get("status") == "success" for item in fetches):
        return "live"
    if any(item.get("status") == "partial" for item in fetches):
        return "partial"
    if fetches:
        return "failed"
    return "missing"
