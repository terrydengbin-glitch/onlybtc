from __future__ import annotations

import hashlib
import json
import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from onlybtc.core.config import get_settings
from onlybtc.db import schema
from onlybtc.db.session import database

BINANCE_SPOT = "https://api.binance.com"
BINANCE_FAPI = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"


def collect_market_probe(now: datetime | None = None) -> dict[str, Any]:
    asof = _ensure_utc(now or datetime.now(UTC))
    started = datetime.now(UTC)
    source_lineage: list[dict[str, Any]] = []
    flags: list[str] = []
    ticker: dict[str, Any] = {}
    klines: dict[str, list[list[Any]]] = {}
    futures: dict[str, Any] = {}

    with httpx.Client(
        timeout=get_settings().source_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": "onlyBTC-event-watchtower/1.0"},
    ) as client:
        ticker, item = _get_json(
            client,
            f"{BINANCE_SPOT}/api/v3/ticker/24hr?symbol={SYMBOL}",
            "binance_spot_ticker_24hr",
        )
        source_lineage.append(item)
        for interval, limit in (("5m", 26), ("15m", 26), ("1h", 30)):
            data, item = _get_json(
                client,
                f"{BINANCE_SPOT}/api/v3/klines?symbol={SYMBOL}&interval={interval}&limit={limit}",
                f"binance_spot_kline_{interval}",
            )
            source_lineage.append(item)
            if isinstance(data, list):
                klines[interval] = data
        premium, item = _get_json(
            client,
            f"{BINANCE_FAPI}/fapi/v1/premiumIndex?symbol={SYMBOL}",
            "binance_futures_premium_index",
        )
        source_lineage.append(item)
        oi, item = _get_json(
            client,
            f"{BINANCE_FAPI}/fapi/v1/openInterest?symbol={SYMBOL}",
            "binance_futures_open_interest",
        )
        source_lineage.append(item)
        futures = {
            "funding_rate": _to_float((premium or {}).get("lastFundingRate")) if isinstance(premium, dict) else None,
            "mark_price": _to_float((premium or {}).get("markPrice")) if isinstance(premium, dict) else None,
            "open_interest": _to_float((oi or {}).get("openInterest")) if isinstance(oi, dict) else None,
        }

    price = _to_float((ticker or {}).get("lastPrice")) if isinstance(ticker, dict) else None
    returns = _returns_from_klines(klines)
    if price is None:
        price = _latest_metric("btc_price")
        flags.append("binance_ticker_failed_metric_fallback")
    metric_fallbacks = _metric_return_fallbacks()
    for key, value in metric_fallbacks.items():
        if returns.get(key) is None:
            returns[key] = value
            if value is not None:
                flags.append(f"{key}_main_pipeline_metric_fallback")

    realized_vol = _realized_vol_from_klines(klines)
    return_z = _return_zscores(returns, realized_vol)
    finished = datetime.now(UTC)
    ok_sources = [item for item in source_lineage if item.get("status") == "success"]
    if not ok_sources:
        flags.append("market_probe_all_sources_failed")

    payload = {
        "market_probe_id": f"mprobe-{asof.strftime('%Y%m%d%H%M%S')}-{_hash([price, returns])[:8]}",
        "schema_version": "p1.event_window.market_probe.v1",
        "collected_at": asof.isoformat(),
        "source": "binance",
        "symbol": SYMBOL,
        "price": price,
        "returns": returns,
        "return_zscores": return_z,
        "realized_vol": realized_vol,
        "open_interest": futures.get("open_interest"),
        "funding_rate": futures.get("funding_rate"),
        "mark_price": futures.get("mark_price"),
        "source_lineage": source_lineage,
        "data_quality_flags": sorted(set(flags)),
        "freshness_sec": 0,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "payload_hash": "",
    }
    payload["payload_hash"] = _hash(payload)
    return payload


def latest_market_probe_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    probe = payload.get("market_probe")
    return probe if isinstance(probe, dict) else {}


def _get_json(client: httpx.Client, url: str, source_id: str) -> tuple[Any, dict[str, Any]]:
    started = datetime.now(UTC)
    try:
        response = client.get(url)
        finished = datetime.now(UTC)
        response.raise_for_status()
        parsed = response.json()
        return parsed, {
            "source_id": source_id,
            "source_tier": "market_live",
            "endpoint_url": url,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "status": "success",
            "http_status": response.status_code,
            "error_code": None,
            "error_message": None,
            "parsed_item_count": len(parsed) if isinstance(parsed, list) else 1,
            "fallback_used": False,
        }
    except Exception as exc:
        finished = datetime.now(UTC)
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return None, {
            "source_id": source_id,
            "source_tier": "market_live",
            "endpoint_url": url,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "status": "failed",
            "http_status": status,
            "error_code": exc.__class__.__name__,
            "error_message": str(exc)[:300],
            "parsed_item_count": 0,
            "fallback_used": False,
        }


def _returns_from_klines(klines: dict[str, list[list[Any]]]) -> dict[str, float | None]:
    returns: dict[str, float | None] = {
        "5m": _kline_return(klines.get("5m"), bars=1),
        "15m": _kline_return(klines.get("15m"), bars=1),
        "1h": _kline_return(klines.get("1h"), bars=1),
        "4h": _kline_return(klines.get("1h"), bars=4),
        "24h": _kline_return(klines.get("1h"), bars=24),
    }
    return returns


def _kline_return(rows: list[list[Any]] | None, *, bars: int) -> float | None:
    if not rows or len(rows) <= bars:
        return None
    try:
        start = float(rows[-bars - 1][4])
        end = float(rows[-1][4])
    except (TypeError, ValueError, IndexError):
        return None
    if not start:
        return None
    return end / start - 1.0


def _realized_vol_from_klines(klines: dict[str, list[list[Any]]]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key, rows in klines.items():
        closes: list[float] = []
        for row in rows or []:
            value = _to_float(row[4] if len(row) > 4 else None)
            if value:
                closes.append(value)
        rs = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes)) if closes[i - 1]]
        result[key] = statistics.pstdev(rs) if len(rs) >= 3 else None
    return result


def _return_zscores(
    returns: dict[str, float | None],
    realized_vol: dict[str, float | None],
) -> dict[str, float | None]:
    scale = {
        "5m": realized_vol.get("5m") or 0.0015,
        "15m": realized_vol.get("15m") or 0.003,
        "1h": realized_vol.get("1h") or 0.006,
        "4h": (realized_vol.get("1h") or 0.006) * 2.0,
        "24h": (realized_vol.get("1h") or 0.006) * 4.9,
    }
    return {
        key: (abs(value) / scale[key] if value is not None and scale.get(key) else None)
        for key, value in returns.items()
    }


def _metric_return_fallbacks() -> dict[str, float | None]:
    mapping = {
        "5m": "btc_return_5m",
        "15m": "btc_return_15m",
        "1h": "btc_return_1h",
        "4h": "btc_return_4h",
        "24h": "btc_return_24h",
    }
    return {key: _latest_metric(metric_id) for key, metric_id in mapping.items()}


def _latest_metric(metric_id: str) -> float | None:
    try:
        with database.session() as session:
            row = (
                session.query(schema.MetricValue)
                .filter(schema.MetricValue.metric_id == metric_id)
                .order_by(schema.MetricValue.ts.desc())
                .limit(1)
                .one_or_none()
            )
    except Exception:
        return None
    return _to_float(row.value) if row else None


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

