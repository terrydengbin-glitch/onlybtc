from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from io import StringIO
from typing import Any

import httpx

from onlybtc.event_window.connectors.common import FetchResult, stable_hash

HEADERS = {"User-Agent": "onlyBTC EventWatchtower/1.0 (+https://localhost)"}
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

EVENT_SERIES = {
    "CPI": [
        ("cpi_headline", "CUUR0000SA0", "CPIAUCSL"),
        ("core_cpi", "CUUR0000SA0L1E", "CPILFESL"),
    ],
    "NFP": [
        ("nonfarm_payrolls", "CES0000000001", "PAYEMS"),
        ("unemployment_rate", "LNS14000000", "UNRATE"),
        ("average_hourly_earnings", "CES0500000003", "CES0500000003"),
    ],
    "JOLTS": [("jolts_openings", "JTS000000000000000JOL", "JTSJOL")],
    "PPI": [("ppi_final_demand", "WPUFD4", "PPIFIS")],
    "PCE": [
        ("pce_price_index", "", "PCEPI"),
        ("core_pce", "", "PCEPILFE"),
    ],
    "GDP": [("gdp", "", "GDP")],
}


def collect_actual_snapshot(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    event_type = str(event.get("event_type") or "").upper()
    series = EVENT_SERIES.get(event_type, [])
    fetches: list[dict[str, Any]] = []
    observations = []
    expected_observation_month = _expected_observation_month(event_type, event)
    for metric_id, bls_series, fred_series in series:
        observation = None
        if bls_series:
            observation, fetch = _fetch_bls_latest(
                bls_series,
                metric_id,
                expected_observation_month,
            )
            fetches.append(
                _lineage_payload(
                    fetch,
                    provider="bls_api",
                    confidence=0.95,
                    blocked_provider="bls_api" if fetch.status == "failed" else None,
                )
            )
        if observation is None and fred_series:
            observation, fetch = _fetch_fred_latest(
                fred_series,
                metric_id,
                expected_observation_month,
            )
            fetches.append(
                _lineage_payload(
                    fetch,
                    provider="fred_fallback",
                    confidence=0.82,
                )
            )
        if observation:
            observations.append(observation)
    status = "available" if observations else "not_released"
    if fetches and all(item.get("status") == "failed" for item in fetches):
        status = "provider_failed"
    snapshot_id = f"actual-{event.get('event_id', event_type)}-{now.strftime('%Y%m%d%H%M')}"
    primary = observations[0] if observations else {}
    return {
        "actual_snapshot": {
            "snapshot_id": snapshot_id,
            "event_id": event.get("event_id"),
            "event_type": event_type,
            "metric_group": event_type,
            "snapshot_ts": now.isoformat(),
            "release_ts": event.get("release_time_utc") or event.get("release_time") or "",
            "actual_status": status,
            "provider": primary.get("provider"),
            "source_tier": primary.get("source_tier"),
            "latest_observation": primary.get("latest_observation"),
            "previous_observation": primary.get("previous_observation"),
            "observation_date": primary.get("observation_date"),
            "observations": observations,
            "fallback_used": any(item.get("fallback_used") for item in fetches),
            "source_lineage": fetches,
        },
        "source_fetches": fetches,
    }


def _fetch_bls_latest(
    series_id: str,
    metric_id: str,
    expected_observation_month: str | None = None,
) -> tuple[dict[str, Any] | None, FetchResult]:
    url = BLS_API_URL.format(series_id=series_id)
    response, started, finished, error = _get(url)
    if response is None or response.status_code >= 400:
        return None, _failure(
            f"bls-actual-{metric_id}",
            "official",
            url,
            started,
            finished,
            response,
            error,
        )
    observation = _parse_bls_response(response.text, metric_id, series_id)
    stale_reason = _stale_observation_reason(observation, expected_observation_month)
    if stale_reason:
        return None, FetchResult(
            source_id=f"bls-actual-{metric_id}",
            source_tier="official",
            endpoint_url=url,
            started_at=started,
            finished_at=finished,
            status="partial",
            http_status=response.status_code,
            error_code="actual_not_released",
            error_message=stale_reason,
            payload_hash=stable_hash(response.text),
            parsed_item_count=1 if observation else 0,
        )
    return observation, FetchResult(
        source_id=f"bls-actual-{metric_id}",
        source_tier="official",
        endpoint_url=url,
        started_at=started,
        finished_at=finished,
        status="success" if observation else "partial",
        http_status=response.status_code,
        payload_hash=stable_hash(response.text),
        parsed_item_count=1 if observation else 0,
    )


def _fetch_fred_latest(
    series_id: str,
    metric_id: str,
    expected_observation_month: str | None = None,
) -> tuple[dict[str, Any] | None, FetchResult]:
    url = FRED_CSV_URL.format(series_id=series_id)
    response, started, finished, error = _get(url)
    if response is None or response.status_code >= 400:
        return None, _failure(
            f"fred-actual-{metric_id}",
            "official_mirror",
            url,
            started,
            finished,
            response,
            error,
        )
    observation = _parse_fred_csv(response.text, metric_id, series_id)
    stale_reason = _stale_observation_reason(observation, expected_observation_month)
    if stale_reason:
        return None, FetchResult(
            source_id=f"fred-actual-{metric_id}",
            source_tier="official_mirror",
            endpoint_url=url,
            started_at=started,
            finished_at=finished,
            status="partial",
            http_status=response.status_code,
            error_code="actual_not_released",
            error_message=stale_reason,
            payload_hash=stable_hash(response.text),
            parsed_item_count=1 if observation else 0,
            fallback_used=True,
        )
    return observation, FetchResult(
        source_id=f"fred-actual-{metric_id}",
        source_tier="official_mirror",
        endpoint_url=url,
        started_at=started,
        finished_at=finished,
        status="success" if observation else "partial",
        http_status=response.status_code,
        payload_hash=stable_hash(response.text),
        parsed_item_count=1 if observation else 0,
        fallback_used=True,
    )


def _parse_bls_response(text: str, metric_id: str, series_id: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
        data = payload.get("Results", {}).get("series", [{}])[0].get("data") or []
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return None
    if not data:
        return None
    latest = data[0]
    value = _to_float(latest.get("value"))
    if value is None:
        return None
    return {
        "metric_id": metric_id,
        "provider": "bls_api",
        "source_tier": "official",
        "series_id": series_id,
        "latest_observation": value,
        "previous_observation": _to_float(data[1].get("value")) if len(data) > 1 else None,
        "observation_date": f"{latest.get('year')}-{_period_to_month(latest.get('period'))}",
    }


def _parse_fred_csv(text: str, metric_id: str, series_id: str) -> dict[str, Any] | None:
    rows = list(csv.reader(StringIO(text)))
    values = [row for row in rows[1:] if len(row) >= 2 and row[1].strip()]
    if not values:
        return None
    latest = values[-1]
    previous = values[-2] if len(values) > 1 else ["", ""]
    value = _to_float(latest[1])
    if value is None:
        return None
    return {
        "metric_id": metric_id,
        "provider": "fred_fallback",
        "source_tier": "official_mirror",
        "series_id": series_id,
        "latest_observation": value,
        "previous_observation": _to_float(previous[1]),
        "observation_date": latest[0],
    }


def _period_to_month(period: Any) -> str:
    text = str(period or "M01")
    if text.startswith("M"):
        return text[1:].zfill(2)
    return "01"


def _expected_observation_month(event_type: str, event: dict[str, Any]) -> str | None:
    explicit = event.get("expected_observation_month") or event.get("expected_observation_date")
    if explicit:
        parsed = _month_key(str(explicit))
        if parsed:
            return parsed
    lag_months = {"CPI": 1, "NFP": 1, "PPI": 1, "JOLTS": 2}.get(event_type)
    if lag_months is None:
        return None
    release_ts = event.get("release_time_utc") or event.get("release_time")
    if not release_ts:
        return None
    try:
        release_time = datetime.fromisoformat(str(release_ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    year = release_time.year
    month = release_time.month - lag_months
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def _stale_observation_reason(
    observation: dict[str, Any] | None,
    expected_observation_month: str | None,
) -> str | None:
    if not observation or not expected_observation_month:
        return None
    observed = _month_key(str(observation.get("observation_date") or ""))
    if observed and observed < expected_observation_month:
        return (
            "latest observation predates expected release period "
            f"{expected_observation_month}; keep actual_status not_released"
        )
    return None


def _month_key(value: str) -> str | None:
    text = value.strip()
    if len(text) < 7:
        return None
    candidate = text[:7]
    try:
        datetime.fromisoformat(f"{candidate}-01")
    except ValueError:
        return None
    return candidate


def _lineage_payload(
    fetch: FetchResult,
    *,
    provider: str,
    confidence: float,
    blocked_provider: str | None = None,
) -> dict[str, Any]:
    payload = fetch.payload()
    payload["provider"] = provider
    payload["confidence"] = confidence
    if blocked_provider:
        payload["blocked_provider"] = blocked_provider
    return payload


def _get(url: str) -> tuple[httpx.Response | None, datetime, datetime, str | None]:
    started = datetime.now(UTC)
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True, headers=HEADERS) as client:
            response = client.get(url)
        return response, started, datetime.now(UTC), None
    except httpx.HTTPError as exc:
        return None, started, datetime.now(UTC), str(exc)


def _failure(
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
        error_code = "blocked_provider" if response.status_code in {401, 403} else "http_error"
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
    )


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
