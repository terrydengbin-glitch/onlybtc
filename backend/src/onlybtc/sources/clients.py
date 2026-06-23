from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import math
import re
import statistics
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from io import StringIO
from pathlib import Path
from typing import Any

import httpx

from onlybtc.core.config import get_settings
from onlybtc.core.paths import paths
from onlybtc.sources.models import (
    CollectionResult,
    MetricSample,
    RawObservationData,
    SourceConfig,
    SourceKind,
    SourceMode,
    SourceStatus,
)

NEXT_HALVING_BLOCK = 1_050_000


class SourceClient:
    def __init__(self, source: SourceConfig, mode: SourceMode = SourceMode.MOCK) -> None:
        self.source = source
        self.mode = mode
        self.settings = get_settings()

    async def collect(self) -> CollectionResult:
        if self.mode == SourceMode.MOCK:
            return self._mock_result()
        return await self._live_result()

    async def _live_result(self) -> CollectionResult:
        return self._mock_result(status=SourceStatus.WARNING, quality=0.65)

    def _mock_result(
        self,
        status: SourceStatus = SourceStatus.HEALTHY,
        quality: float = 0.95,
    ) -> CollectionResult:
        now = datetime.now(UTC)
        payload = {"source_id": self.source.source_id, "mock": True, "observed_at": now.isoformat()}
        metrics = [
            MetricSample(
                metric_id=metric_id,
                source_id=self.source.source_id,
                ts=now,
                value=_mock_value(metric_id),
                quality_score=quality,
            )
            for metric_id in self.source.metrics
        ]
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload, status=status),
            metrics=metrics,
        )


class FredClient(SourceClient):
    async def _live_result(self) -> CollectionResult:
        api_key = self.settings.fred_api_key
        if not api_key:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        series_id = self.source.metadata["fred_series_id"]
        metric_id = self.source.metrics[0]
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        }
        started = datetime.now(UTC)
        attempts: list[dict[str, Any]] = []
        primary_error: str | None = None
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            for attempt in range(1, self.settings.source_fred_api_max_attempts + 1):
                attempt_started = datetime.now(UTC)
                try:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    observation = _latest_fred_observation(payload.get("observations") or [])
                    value = float(observation["value"])
                    ts = datetime.fromisoformat(observation["date"]).replace(tzinfo=UTC)
                    api_payload = {
                        **payload,
                        "provider": "fred_api",
                        "fred_series_id": series_id,
                        "fallback_used": False,
                        "retry_count": attempt - 1,
                        "api_attempts": [
                            *attempts,
                            {
                                "provider": "fred_api",
                                "attempt": attempt,
                                "status": "success",
                                "http_status": response.status_code,
                                "elapsed_ms": _elapsed_ms(attempt_started),
                            },
                        ],
                    }
                    return CollectionResult(
                        source=self.source,
                        raw=RawObservationData(
                            source_id=self.source.source_id,
                            payload=api_payload,
                            latency_ms=_elapsed_ms(started),
                        ),
                        metrics=[
                            MetricSample(
                                metric_id=metric_id,
                                source_id=self.source.source_id,
                                ts=ts,
                                value=value,
                                quality_score=0.95,
                            )
                        ],
                    )
                except Exception as exc:  # noqa: BLE001 - provider lineage keeps raw type.
                    primary_error = _format_provider_error(exc)
                    status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                    attempts.append(
                        {
                            "provider": "fred_api",
                            "attempt": attempt,
                            "status": "failed",
                            "http_status": status_code,
                            "error_type": exc.__class__.__name__,
                            "error_message": primary_error,
                            "elapsed_ms": _elapsed_ms(attempt_started),
                        }
                    )
                    if attempt >= self.settings.source_fred_api_max_attempts or not _fred_should_retry(exc):
                        break
                    await asyncio.sleep(self.settings.source_fred_api_backoff_seconds * attempt)

            csv_started = datetime.now(UTC)
            csv_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            try:
                csv_response = await client.get(csv_url)
                csv_response.raise_for_status()
                csv_observation = _latest_fred_csv_observation(csv_response.text)
                value = float(csv_observation["value"])
                ts = datetime.fromisoformat(csv_observation["date"]).replace(tzinfo=UTC)
                payload = {
                    "provider": "fredgraph_csv",
                    "source_tier": "official_public_fallback",
                    "fred_series_id": series_id,
                    "fallback_used": True,
                    "fallback_provider": "fredgraph_csv",
                    "fallback_for": "fred_api",
                    "primary_error": primary_error,
                    "retry_count": len(attempts),
                    "api_attempts": attempts,
                    "csv_attempt": {
                        "provider": "fredgraph_csv",
                        "status": "success",
                        "http_status": csv_response.status_code,
                        "elapsed_ms": _elapsed_ms(csv_started),
                    },
                    "observations": [csv_observation],
                }
                return CollectionResult(
                    source=self.source,
                    raw=RawObservationData(
                        source_id=self.source.source_id,
                        payload=payload,
                        status=SourceStatus.WARNING,
                        latency_ms=_elapsed_ms(started),
                        error_message=f"FRED API failed; using fredgraph.csv fallback. primary_error={primary_error}",
                    ),
                    metrics=[
                        MetricSample(
                            metric_id=metric_id,
                            source_id=self.source.source_id,
                            ts=ts,
                            value=value,
                            is_fallback=True,
                            quality_score=0.90,
                        )
                    ],
                )
            except Exception as exc:  # noqa: BLE001 - surfaced by source service.
                csv_error = _format_provider_error(exc)
                request = httpx.Request("GET", csv_url)
                response = httpx.Response(
                    502,
                    request=request,
                    text=f"fred_api_error={primary_error}; fredgraph_csv_error={csv_error}",
                )
                raise httpx.HTTPStatusError(
                    "FRED API and fredgraph.csv fallback failed",
                    request=request,
                    response=response,
                ) from exc


def _latest_fred_observation(observations: list[dict[str, Any]]) -> dict[str, Any]:
    for observation in observations:
        value = str(observation.get("value", "")).strip()
        if value and value != ".":
            return observation
    raise ValueError("FRED response contains no usable observation")


def _latest_fred_csv_observation(text: str) -> dict[str, Any]:
    rows = list(csv.DictReader(StringIO(text)))
    if not rows:
        raise ValueError("fredgraph.csv returned no rows")
    for row in reversed(rows):
        date_value = (row.get("observation_date") or row.get("DATE") or row.get("date") or "").strip()
        value = ""
        for key, item in row.items():
            if key and key.lower() not in {"observation_date", "date"}:
                value = str(item or "").strip()
                break
        if date_value and value and value != ".":
            return {"date": date_value, "value": value}
    raise ValueError("fredgraph.csv contains no usable observation")


def _fred_should_retry(error: Exception) -> bool:
    if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {429, 500, 502, 503, 504}
    return False


def _format_provider_error(error: Exception) -> str:
    message = str(error).strip()
    return f"{error.__class__.__name__}: {message or 'empty exception message'}"


def _elapsed_ms(started: datetime) -> int:
    return int((datetime.now(UTC) - started).total_seconds() * 1000)


class ExchangeClient(SourceClient):
    async def _live_result(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        if self.source.source_id.startswith("binance-btcusdt-kline-") and self.source.source_id != "binance-btcusdt-kline-1d-rv":
            return _binance_kline_result(self.source, payload)
        if self.source.source_id == "binance-btcusdt-kline-1d-rv":
            return _binance_realized_volatility_result(self.source, payload)
        if self.source.source_id == "binance-btcusdt-funding":
            mark_price = float(payload["markPrice"])
            index_price = float(payload["indexPrice"])
            funding_rate = float(payload["lastFundingRate"])
            basis = (mark_price - index_price) / index_price
            funding_z = _clamp(funding_rate / 0.0001, -3.0, 3.0)
            basis_z = _clamp(basis / 0.001, -3.0, 3.0)
            next_funding_ms = payload.get("nextFundingTime")
            now_ms = datetime.now(UTC).timestamp() * 1000
            time_to_settlement_min = (
                max(0.0, (float(next_funding_ms) - now_ms) / 60_000.0)
                if next_funding_ms is not None
                else 480.0
            )
            return CollectionResult(
                source=self.source,
                raw=RawObservationData(source_id=self.source.source_id, payload=payload),
                metrics=[
                    MetricSample(
                        metric_id="btc_funding_rate",
                        source_id=self.source.source_id,
                        value=funding_rate,
                        quality_score=0.96,
                    ),
                    MetricSample(
                        metric_id="btc_funding_band",
                        source_id=self.source.source_id,
                        value=_funding_band_value(funding_rate),
                        quality_score=0.96,
                    ),
                    MetricSample(
                        metric_id="futures_basis",
                        source_id=self.source.source_id,
                        value=basis,
                        quality_score=0.96,
                    ),
                    MetricSample(
                        metric_id="funding_rate_8h_equiv",
                        source_id=self.source.source_id,
                        value=funding_rate,
                        quality_score=0.94,
                    ),
                    MetricSample(
                        metric_id="funding_rate_8h_equiv_z",
                        source_id=self.source.source_id,
                        value=funding_z,
                        quality_score=0.90,
                    ),
                    MetricSample(
                        metric_id="funding_shock_z_8h",
                        source_id=self.source.source_id,
                        value=funding_z,
                        quality_score=0.90,
                    ),
                    MetricSample(
                        metric_id="funding_acceleration_z_24h",
                        source_id=self.source.source_id,
                        value=0.0,
                        quality_score=0.70,
                    ),
                    MetricSample(
                        metric_id="predicted_funding_z",
                        source_id=self.source.source_id,
                        value=funding_z,
                        quality_score=0.84,
                    ),
                    MetricSample(
                        metric_id="funding_time_to_settlement_min",
                        source_id=self.source.source_id,
                        value=time_to_settlement_min,
                        quality_score=0.88,
                    ),
                    MetricSample(
                        metric_id="funding_persistence_score",
                        source_id=self.source.source_id,
                        value=_clamp(abs(funding_z) * 33.0, 0.0, 100.0),
                        quality_score=0.76,
                    ),
                    MetricSample(
                        metric_id="funding_basis_gap_z",
                        source_id=self.source.source_id,
                        value=_clamp(funding_z - basis_z, -3.0, 3.0),
                        quality_score=0.82,
                    ),
                ],
            )
        if self.source.source_id == "binance-btcusdt-open-interest":
            ts = datetime.fromtimestamp(payload["time"] / 1000, tz=UTC)
            open_interest = float(payload["openInterest"])
            return CollectionResult(
                source=self.source,
                raw=RawObservationData(source_id=self.source.source_id, payload=payload),
                metrics=[
                    MetricSample(
                        metric_id="btc_open_interest",
                        source_id=self.source.source_id,
                        ts=ts,
                        value=open_interest,
                        quality_score=0.95,
                    ),
                    MetricSample(
                        metric_id="oi_impulse_z_15m",
                        source_id=self.source.source_id,
                        ts=ts,
                        value=0.0,
                        quality_score=0.62,
                    ),
                    MetricSample(
                        metric_id="oi_impulse_z_1h",
                        source_id=self.source.source_id,
                        ts=ts,
                        value=0.0,
                        quality_score=0.62,
                    ),
                    MetricSample(
                        metric_id="oi_impulse_z_4h",
                        source_id=self.source.source_id,
                        ts=ts,
                        value=0.0,
                        quality_score=0.62,
                    ),
                    MetricSample(
                        metric_id="oi_price_efficiency",
                        source_id=self.source.source_id,
                        ts=ts,
                        value=0.0,
                        quality_score=0.60,
                    ),
                    MetricSample(
                        metric_id="oi_participation_type_score",
                        source_id=self.source.source_id,
                        ts=ts,
                        value=0.0,
                        quality_score=0.60,
                    ),
                    MetricSample(
                        metric_id="oi_source_coverage_score",
                        source_id=self.source.source_id,
                        ts=ts,
                        value=70.0,
                        quality_score=0.86,
                    ),
                ],
            )
        long_short_metric_map = {
            "binance-btcusdt-global-long-short-account-ratio": (
                "btc_global_long_account_ratio",
                "btc_global_short_account_ratio",
                "btc_global_long_short_account_ratio",
            ),
            "binance-btcusdt-top-long-short-account-ratio": (
                "btc_top_long_account_ratio",
                "btc_top_short_account_ratio",
                "btc_top_long_short_account_ratio",
            ),
            "binance-btcusdt-top-long-short-position-ratio": (
                "btc_top_long_position_ratio",
                "btc_top_short_position_ratio",
                "btc_top_long_short_position_ratio",
            ),
        }
        if self.source.source_id in long_short_metric_map:
            latest = payload[-1]
            ts = datetime.fromtimestamp(latest["timestamp"] / 1000, tz=UTC)
            long_metric, short_metric, ratio_metric = long_short_metric_map[self.source.source_id]
            ratio = float(latest["longShortRatio"])
            ratio_z = _clamp((ratio - 1.0) / 0.10, -3.0, 3.0)
            derived_metrics: list[MetricSample] = []
            if self.source.source_id == "binance-btcusdt-global-long-short-account-ratio":
                derived_metrics.extend(
                    [
                        MetricSample(
                            metric_id="global_account_ratio_z",
                            source_id=self.source.source_id,
                            value=ratio_z,
                            ts=ts,
                            quality_score=0.88,
                        ),
                        MetricSample(
                            metric_id="retail_crowding_score",
                            source_id=self.source.source_id,
                            value=_clamp(max(ratio_z, 0.0) * 33.0, 0.0, 100.0),
                            ts=ts,
                            quality_score=0.82,
                        ),
                    ]
                )
            elif self.source.source_id == "binance-btcusdt-top-long-short-account-ratio":
                derived_metrics.append(
                    MetricSample(
                        metric_id="top_account_ratio_z",
                        source_id=self.source.source_id,
                        value=ratio_z,
                        ts=ts,
                        quality_score=0.88,
                    )
                )
            elif self.source.source_id == "binance-btcusdt-top-long-short-position-ratio":
                derived_metrics.extend(
                    [
                        MetricSample(
                            metric_id="top_position_ratio_z",
                            source_id=self.source.source_id,
                            value=ratio_z,
                            ts=ts,
                            quality_score=0.88,
                        ),
                        MetricSample(
                            metric_id="top_vs_global_positioning_gap_z",
                            source_id=self.source.source_id,
                            value=ratio_z,
                            ts=ts,
                            quality_score=0.72,
                        ),
                        MetricSample(
                            metric_id="smart_money_divergence_score",
                            source_id=self.source.source_id,
                            value=_clamp(-ratio_z * 25.0, -100.0, 100.0),
                            ts=ts,
                            quality_score=0.72,
                        ),
                    ]
                )
            return CollectionResult(
                source=self.source,
                raw=RawObservationData(source_id=self.source.source_id, payload={"rows": payload}),
                metrics=[
                    MetricSample(
                        metric_id=long_metric,
                        source_id=self.source.source_id,
                        value=float(latest["longAccount"]),
                        ts=ts,
                        quality_score=0.96,
                    ),
                    MetricSample(
                        metric_id=short_metric,
                        source_id=self.source.source_id,
                        value=float(latest["shortAccount"]),
                        ts=ts,
                        quality_score=0.96,
                    ),
                    MetricSample(
                        metric_id=ratio_metric,
                        source_id=self.source.source_id,
                        value=ratio,
                        ts=ts,
                        quality_score=0.96,
                    ),
                    *derived_metrics,
                ],
            )
        if self.source.source_id == "binance-btcusdt-taker-buy-sell-ratio":
            latest = payload[-1]
            ts = datetime.fromtimestamp(latest["timestamp"] / 1000, tz=UTC)
            return _single_exchange_metric_result(
                self.source,
                {"rows": payload},
                "taker_buy_sell_ratio",
                float(latest["buySellRatio"]),
                ts=ts,
            )
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="btc_price",
                    source_id=self.source.source_id,
                    value=float(payload["lastPrice"]),
                    quality_score=0.96,
                ),
                MetricSample(
                    metric_id="exchange_spot_volume",
                    source_id=self.source.source_id,
                    value=float(payload["quoteVolume"]),
                    quality_score=0.96,
                )
            ],
        )


class BitcoinClient(SourceClient):
    async def _live_result(self) -> CollectionResult:
        urls = [self.source.url, *self.source.metadata.get("fallback_urls", [])]
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            for url in urls:
                if not url:
                    continue
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    height = _parse_bitcoin_height(response)
                    return _bitcoin_result(
                        self.source,
                        height,
                        raw_payload={"height": height, "live": True, "url": url},
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{url}: {exc}")
        raise RuntimeError("; ".join(errors))

    def _mock_result(
        self,
        status: SourceStatus = SourceStatus.HEALTHY,
        quality: float = 0.95,
    ) -> CollectionResult:
        height = 897_300
        result = _bitcoin_result(self.source, height, raw_payload={"height": height, "mock": True})
        result.raw.status = status
        for metric in result.metrics:
            metric.quality_score = quality
        return result


class OfficialClient(SourceClient):
    async def _live_result(self) -> CollectionResult:
        if self.source.source_id == "ofr-fsi":
            return await self._collect_ofr_fsi()
        if self.source.source_id == "mempool-lightning-network-stats":
            return await self._collect_mempool_lightning()
        if self.source.source_id == "clarkmoody-dashboard":
            return await self._collect_clarkmoody_dashboard()
        if self.source.source_id == "coinmetrics-community-btc-csv":
            return await self._collect_coinmetrics_btc_csv()
        if self.source.source_id == "official-macro-event-calendar":
            return await self._collect_macro_event_calendar()
        if self.source.source_id in {"fed-rss-all-speeches", "fed-rss-all-testimony"}:
            return await self._collect_fed_rss()
        if self.source.source_id == "fed-calendar":
            return await self._collect_fed_calendar()
        if self.source.source_id == "fed-fomc-blackout-calendar":
            return await self._collect_fomc_blackout()
        if self.source.source_id in {
            "binance-usdm-force-order-btcusdt",
            "bybit-v5-all-liquidation-btcusdt",
        }:
            return await self._collect_liquidation_snapshot()
        if self.source.source_id.startswith("blockchain-"):
            return await self._collect_blockchain_chart()
        if self.source.source_id == "defillama-stablecoins":
            return await self._collect_defillama_stablecoins()
        if self.source.source_id == "coingecko-global":
            return await self._collect_coingecko_global()
        if self.source.source_id == "coingecko-eth-btc":
            return await self._collect_coingecko_eth_btc()
        if self.source.source_id == "coingecko-top50-markets":
            return await self._collect_coingecko_top50_markets()
        if self.source.source_id == "deribit-btc-options":
            return await self._collect_deribit_options()
        if self.source.source_id == "alternative-fear-greed":
            return await self._collect_fear_greed()
        return await super()._live_result()

    async def _collect_ofr_fsi(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        latest = payload["OFRFSI"]["data"][-1]
        ts = datetime.fromtimestamp(latest[0] / 1000, tz=UTC)
        value = float(latest[1])
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="ofr_fsi",
                    source_id=self.source.source_id,
                    ts=ts,
                    value=value,
                    quality_score=0.96,
                )
            ],
        )

    async def _collect_fear_greed(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        latest = payload["data"][0]
        ts = datetime.fromtimestamp(int(latest["timestamp"]), tz=UTC)
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="sector_heat",
                    source_id=self.source.source_id,
                    ts=ts,
                    value=float(latest["value"]),
                    quality_score=0.86,
                )
            ],
        )

    async def _collect_blockchain_chart(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        latest = payload["values"][-1]
        ts = datetime.fromtimestamp(latest["x"], tz=UTC)
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id=self.source.metrics[0],
                    source_id=self.source.source_id,
                    ts=ts,
                    value=float(latest["y"]),
                    quality_score=0.92,
                )
            ],
        )

    async def _collect_mempool_lightning(self) -> CollectionResult:
        urls = [
            self.source.url,
            *self.source.metadata.get("fallback_urls", []),
        ]
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            for url in urls:
                if not url:
                    continue
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    payload = response.json()
                    return _mempool_lightning_result(self.source, payload, url)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{url}: {exc}")
        result = self._mock_result(status=SourceStatus.WARNING, quality=0.55)
        result.raw.error_message = "; ".join(errors)
        return result

    async def _collect_clarkmoody_dashboard(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(
            timeout=self.settings.source_timeout_seconds,
            follow_redirects=True,
            headers={"user-agent": "onlyBTC research bot contact: local"},
        ) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        parsed = _parse_clarkmoody_dashboard(response.text)
        required = {"lightning_capacity_btc", "lightning_channel_count", "lightning_node_count"}
        missing = sorted(required - parsed.keys())
        if missing:
            raise RuntimeError(f"Clark Moody missing required fields: {', '.join(missing)}")
        ts = datetime.now(UTC)
        quality = float(self.source.metadata.get("quality_score", 0.84))
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload={
                    "url": self.source.url,
                    "fields": parsed,
                    "note": "Clark Moody public dashboard text parse",
                },
            ),
            metrics=[
                MetricSample(
                    metric_id=metric_id,
                    source_id=self.source.source_id,
                    ts=ts,
                    value=float(item["value"]),
                    timeframe="spot",
                    quality_score=quality,
                )
                for metric_id, item in parsed.items()
                if metric_id in self.source.metrics
            ],
        )

    async def _collect_coinmetrics_btc_csv(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        csv_text = response.text
        rows = csv.DictReader(csv_text.splitlines())
        latest: dict[str, str] | None = None
        for row in rows:
            if _has_float(row, "SplyCur") and (
                _has_float(row, "CapRealUSD")
                or (_has_float(row, "CapMrktCurUSD") and _has_float(row, "CapMVRVCur"))
            ):
                latest = row
        if latest is None:
            raise RuntimeError("Coin Metrics CSV did not include realized cap inputs")
        supply = float(latest["SplyCur"])
        if _has_float(latest, "CapRealUSD"):
            realized_cap = float(latest["CapRealUSD"])
            formula = "CapRealUSD / SplyCur"
        else:
            market_cap = float(latest["CapMrktCurUSD"])
            mvrv = float(latest["CapMVRVCur"])
            realized_cap = market_cap / mvrv
            formula = "(CapMrktCurUSD / CapMVRVCur) / SplyCur"
        realized_price = realized_cap / supply
        ts = datetime.fromisoformat(latest["time"]).replace(tzinfo=UTC)
        payload = {
            "latest": latest,
            "formula": formula,
            "realized_cap_usd": realized_cap,
            "supply_current": supply,
        }
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="realized_price",
                    source_id=self.source.source_id,
                    ts=ts,
                    value=realized_price,
                    quality_score=0.86,
                ),
                MetricSample(
                    metric_id="cap_real_usd",
                    source_id=self.source.source_id,
                    ts=ts,
                    value=realized_cap,
                    quality_score=0.86,
                ),
                MetricSample(
                    metric_id="supply_current",
                    source_id=self.source.source_id,
                    ts=ts,
                    value=supply,
                    quality_score=0.86,
                ),
            ],
        )

    async def _collect_macro_event_calendar(self) -> CollectionResult:
        now = datetime.now(UTC)
        events: list[dict[str, Any]] = []
        errors: list[str] = []
        diagnostics: list[str] = []
        source_resolution: dict[str, dict[str, Any]] = {}
        optional_sources = set(self.source.metadata.get("optional_official_sources", []))
        fallback_policy = dict(self.source.metadata.get("fallback_policy", {}))
        async with httpx.AsyncClient(
            timeout=self.settings.source_timeout_seconds,
            follow_redirects=True,
            headers={
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0 Safari/537.36 onlyBTC"
                ),
                "accept-language": "en-US,en;q=0.9",
            },
        ) as client:
            for event_type, configured_urls in self.source.metadata["urls"].items():
                urls = configured_urls if isinstance(configured_urls, list) else [configured_urls]
                attempted: list[str] = []
                parsed_events: list[dict[str, Any]] = []
                url_errors: list[str] = []
                last_error: str | None = None
                for configured_url in urls:
                    url = str(configured_url).format(year=now.year)
                    attempted.append(url)
                    try:
                        response = await client.get(url)
                        response.raise_for_status()
                        parsed_events = _parse_macro_events(event_type, response.text, now.date())
                        if parsed_events:
                            break
                    except Exception as exc:  # noqa: BLE001
                        url_errors.append(f"{url}: {exc}")
                if not parsed_events and url_errors:
                    last_error = " | ".join(url_errors)
                    if event_type in optional_sources and _resolution_error_status(last_error) == "http_403":
                        diagnostics.append(f"{event_type}: {last_error}")
                    else:
                        errors.append(f"{event_type}: {last_error}")
                events.extend(parsed_events)
                source_resolution[event_type] = {
                    "status": "parsed" if parsed_events else _resolution_error_status(last_error),
                    "url_attempted": attempted,
                    "fallback_used": False,
                    "event_count": len(parsed_events),
                    "error": last_error,
                    "optional_official": event_type in optional_sources,
                    "fallback_stack": fallback_policy.get(event_type, []),
                }
        fallback_events = _fallback_macro_events(now.date())
        events.extend(fallback_events)
        _apply_macro_fallback_resolution(source_resolution, events, fallback_events)
        _mark_optional_official_calendar_resolution(source_resolution)
        next_by_type = _next_event_by_type(events, now)
        nearest_by_type = _nearest_event_by_type(events, now)
        required = ["cpi", "nfp", "fomc", "pce"]
        missing = [event_type for event_type in required if event_type not in next_by_type]
        if missing:
            raise RuntimeError(f"Macro event calendar missing: {', '.join(missing)}")
        metrics: list[MetricSample] = []
        calendar_quality = 0.82 if errors or diagnostics else 0.9
        for event_type, event in next_by_type.items():
            seconds_until = max((event["datetime"] - now).total_seconds(), 0)
            metrics.append(
                MetricSample(
                    metric_id=f"{event_type}_days_until",
                    source_id=self.source.source_id,
                    ts=now,
                    value=seconds_until / 86_400,
                    timeframe="event",
                    quality_score=calendar_quality,
                )
            )
            metrics.append(
                MetricSample(
                    metric_id=f"{event_type}_hours_until",
                    source_id=self.source.source_id,
                    ts=now,
                    value=seconds_until / 3_600,
                    timeframe="event",
                    quality_score=calendar_quality,
                )
            )
        for event_type, event in nearest_by_type.items():
            metrics.append(
                MetricSample(
                    metric_id=f"{event_type}_signed_days",
                    source_id=self.source.source_id,
                    ts=now,
                    value=(event["datetime"] - now).total_seconds() / 86_400,
                    timeframe="event",
                    quality_score=calendar_quality,
                )
            )
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload={
                    "events": [
                        {**event, "datetime": event["datetime"].isoformat()} for event in events
                    ],
                    "errors": errors,
                    "diagnostics": diagnostics,
                    "source_resolution": source_resolution,
                    "macro_calendar_fallbacks": _fallback_macro_calendar_metadata(now.date()),
                },
                status=SourceStatus.WARNING if errors else SourceStatus.HEALTHY,
                error_message="; ".join(errors) if errors else None,
            ),
            metrics=metrics,
        )

    async def _collect_liquidation_snapshot(self) -> CollectionResult:
        if self.source.source_id == "binance-usdm-force-order-btcusdt":
            return await _collect_binance_force_order(self.source)
        if self.source.source_id == "bybit-v5-all-liquidation-btcusdt":
            return await _collect_bybit_liquidation(self.source)
        return await super()._live_result()

    async def _collect_fed_rss(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.6)
        now = datetime.now(UTC)
        errors: list[str] = []
        async with httpx.AsyncClient(
            timeout=self.settings.source_timeout_seconds,
            follow_redirects=True,
            headers={"user-agent": "onlyBTC research bot contact: local"},
        ) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
            events = _parse_fed_rss(response.text)
            if not events:
                raise RuntimeError("Fed RSS returned no parsable items")
            latest = events[0]
            text = f"{latest['title']} {latest.get('description', '')}"
            if self.source.metadata.get("fetch_official_text") and latest.get("url"):
                try:
                    page = await client.get(str(latest["url"]))
                    page.raise_for_status()
                    text = _html_to_text(page.text)
                    latest["text_excerpt"] = text[:1_200]
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"official text fallback: {exc}")
                    latest["text_excerpt"] = text[:1_200]
        score = _score_fed_speech_event(latest, text)
        ts = latest.get("published_at")
        if not isinstance(ts, datetime):
            ts = now
        quality = float(self.source.metadata.get("quality_score", 0.82))
        if errors:
            quality = min(quality, 0.72)
        metrics = [
            MetricSample(
                metric_id="fed_speaker_weight",
                source_id=self.source.source_id,
                ts=ts,
                value=score["speaker_weight"],
                timeframe="event",
                quality_score=quality,
            ),
            MetricSample(
                metric_id="fed_speech_hawkish_score",
                source_id=self.source.source_id,
                ts=ts,
                value=score["hawkish_score"],
                timeframe="event",
                quality_score=quality,
            ),
            MetricSample(
                metric_id="fed_speech_dovish_score",
                source_id=self.source.source_id,
                ts=ts,
                value=score["dovish_score"],
                timeframe="event",
                quality_score=quality,
            ),
            MetricSample(
                metric_id="fed_speech_content_risk",
                source_id=self.source.source_id,
                ts=ts,
                value=score["content_risk"],
                timeframe="event",
                quality_score=quality,
            ),
            MetricSample(
                metric_id="fed_speech_risk",
                source_id=self.source.source_id,
                ts=ts,
                value=score["fed_speech_risk"],
                timeframe="event",
                quality_score=quality,
            ),
        ]
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload={
                    "latest_event": {
                        **latest,
                        "published_at": ts.isoformat(),
                    },
                    "score": score,
                    "errors": errors,
                },
                status=SourceStatus.WARNING if errors else SourceStatus.HEALTHY,
                error_message="; ".join(errors) if errors else None,
            ),
            metrics=metrics,
        )

    async def _collect_fed_calendar(self) -> CollectionResult:
        now = datetime.now(UTC)
        events: list[dict[str, Any]] = []
        errors: list[str] = []
        if self.source.url:
            async with httpx.AsyncClient(
                timeout=self.settings.source_timeout_seconds,
                follow_redirects=True,
                headers={"user-agent": "onlyBTC research bot contact: local"},
            ) as client:
                try:
                    response = await client.get(self.source.url)
                    response.raise_for_status()
                    events = _parse_fed_calendar_events(response.text, now.date())
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"calendar: {exc}")
        events.extend(_fallback_fed_speech_events(now.date()))
        upcoming = [event for event in events if event["datetime"] >= now]
        next_event = min(upcoming, key=lambda item: item["datetime"], default=None)
        hours_until = (
            max((next_event["datetime"] - now).total_seconds() / 3_600, 0)
            if next_event
            else 168.0
        )
        scheduled_risk = _fed_scheduled_risk(next_event, hours_until) if next_event else 0.0
        quality = float(self.source.metadata.get("quality_score", 0.72))
        status = SourceStatus.WARNING if errors else SourceStatus.HEALTHY
        if not events:
            status = SourceStatus.WARNING
            errors.append("no Fed calendar events parsed")
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload={
                    "events": [
                        {**event, "datetime": event["datetime"].isoformat()} for event in events
                    ],
                    "next_event": (
                        {**next_event, "datetime": next_event["datetime"].isoformat()}
                        if next_event
                        else None
                    ),
                    "errors": errors,
                },
                status=status,
                error_message="; ".join(errors) if errors else None,
            ),
            metrics=[
                MetricSample(
                    metric_id="next_fed_speech_hours_until",
                    source_id=self.source.source_id,
                    ts=now,
                    value=hours_until,
                    timeframe="event",
                    quality_score=quality,
                ),
                MetricSample(
                    metric_id="fed_speech_scheduled_risk",
                    source_id=self.source.source_id,
                    ts=now,
                    value=scheduled_risk,
                    timeframe="event",
                    quality_score=quality,
                ),
            ],
        )

    async def _collect_fomc_blackout(self) -> CollectionResult:
        now = datetime.now(UTC)
        blackout = _fomc_blackout_state(now)
        quality = float(self.source.metadata.get("quality_score", 0.86))
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=blackout),
            metrics=[
                MetricSample(
                    metric_id="fomc_blackout_active",
                    source_id=self.source.source_id,
                    ts=now,
                    value=1.0 if blackout["active"] else 0.0,
                    timeframe="event",
                    quality_score=quality,
                ),
                MetricSample(
                    metric_id="fomc_event_risk",
                    source_id=self.source.source_id,
                    ts=now,
                    value=blackout["fomc_event_risk"],
                    timeframe="event",
                    quality_score=quality,
                ),
            ],
        )

    async def _collect_defillama_stablecoins(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        supply = sum(
            float(asset.get("circulating", {}).get("peggedUSD") or 0)
            for asset in payload["peggedAssets"]
        )
        previous_week_supply = _defillama_previous_week_supply(payload)
        supply_7d_change = supply - previous_week_supply if previous_week_supply else 0.0
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="stablecoin_supply",
                    source_id=self.source.source_id,
                    value=supply,
                    quality_score=0.9,
                ),
                MetricSample(
                    metric_id="stablecoin_buying_power_proxy",
                    source_id=self.source.source_id,
                    value=supply_7d_change,
                    quality_score=0.72,
                    timeframe="7d",
                ),
            ],
        )

    async def _collect_coingecko_global(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        data = payload["data"]
        btc_dominance = float(data["market_cap_percentage"]["btc"])
        total_market_cap_usd = float(data["total_market_cap"]["usd"])
        total2_market_cap = total_market_cap_usd * (1 - btc_dominance / 100)
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="btc_dominance",
                    source_id=self.source.source_id,
                    value=btc_dominance,
                    quality_score=0.9,
                ),
                MetricSample(
                    metric_id="total_market_cap",
                    source_id=self.source.source_id,
                    value=total_market_cap_usd,
                    quality_score=0.9,
                ),
                MetricSample(
                    metric_id="total2_market_cap",
                    source_id=self.source.source_id,
                    value=total2_market_cap,
                    quality_score=0.9,
                ),
            ],
        )

    async def _collect_coingecko_eth_btc(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="eth_btc",
                    source_id=self.source.source_id,
                    value=float(payload["ethereum"]["btc"]),
                    quality_score=0.9,
                )
            ],
        )

    async def _collect_coingecko_top50_markets(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        changes = [
            float(item["price_change_percentage_24h"])
            for item in payload
            if item.get("price_change_percentage_24h") is not None
        ]
        market_rows = [
            (
                float(item["price_change_percentage_24h"]),
                float(item.get("market_cap") or 0.0),
            )
            for item in payload
            if item.get("price_change_percentage_24h") is not None
        ]
        positive_ratio = sum(1 for value in changes if value > 0) / len(changes) if changes else 0.0
        equal_weight_return = (sum(changes) / len(changes) / 100.0) if changes else 0.0
        market_cap_sum = sum(max(cap, 0.0) for _, cap in market_rows)
        cap_weight_return = (
            sum(change * max(cap, 0.0) for change, cap in market_rows) / market_cap_sum / 100.0
            if market_cap_sum > 0
            else 0.0
        )
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload={"markets": payload}),
            metrics=[
                MetricSample(
                    metric_id="top50_strength",
                    source_id=self.source.source_id,
                    value=positive_ratio,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="top50_advance_pct_24h",
                    source_id=self.source.source_id,
                    value=positive_ratio,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="top50_equal_weight_return_24h_pct",
                    source_id=self.source.source_id,
                    value=equal_weight_return,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="top50_cap_weight_return_24h_pct",
                    source_id=self.source.source_id,
                    value=cap_weight_return,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="top50_equal_minus_cap_weight_return_24h_pct",
                    source_id=self.source.source_id,
                    value=equal_weight_return - cap_weight_return,
                    quality_score=0.88,
                ),
            ],
        )

    async def _collect_deribit_options(self) -> CollectionResult:
        if not self.source.url:
            return self._mock_result(status=SourceStatus.WARNING, quality=0.7)
        async with httpx.AsyncClient(timeout=self.settings.source_timeout_seconds) as client:
            response = await client.get(self.source.url)
            response.raise_for_status()
        payload = response.json()
        rows = payload["result"]
        calls = [item for item in rows if item["instrument_name"].endswith("-C")]
        puts = [item for item in rows if item["instrument_name"].endswith("-P")]
        call_volume = sum(float(item.get("volume") or 0) for item in calls)
        put_volume = sum(float(item.get("volume") or 0) for item in puts)
        call_iv = _weighted_average(calls, "mark_iv", "open_interest")
        put_iv = _weighted_average(puts, "mark_iv", "open_interest")
        all_iv = _weighted_average(rows, "mark_iv", "open_interest")
        spot = _first_positive(rows, "underlying_price")
        max_pain_distance, gamma_wall_distance = _derive_options_positioning(rows, spot)
        notional = sum(
            float(item.get("open_interest") or 0) * float(item.get("underlying_price") or 0)
            for item in rows
        )
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(source_id=self.source.source_id, payload=payload),
            metrics=[
                MetricSample(
                    metric_id="options_iv",
                    source_id=self.source.source_id,
                    value=all_iv,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="put_call_ratio",
                    source_id=self.source.source_id,
                    value=put_volume / call_volume if call_volume else 0,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="options_skew",
                    source_id=self.source.source_id,
                    value=put_iv - call_iv,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="options_expiry_notional",
                    source_id=self.source.source_id,
                    value=notional,
                    quality_score=0.88,
                ),
                MetricSample(
                    metric_id="max_pain_distance",
                    source_id=self.source.source_id,
                    value=max_pain_distance,
                    quality_score=0.72,
                ),
                MetricSample(
                    metric_id="gamma_wall_proxy_distance",
                    source_id=self.source.source_id,
                    value=gamma_wall_distance,
                    quality_score=0.65,
                ),
            ],
        )


class PlaywrightClient(SourceClient):
    async def _live_result(self) -> CollectionResult:
        if self.source.source_id == "playwright-glassnode-asset-overview":
            return await self._collect_glassnode_asset_overview()
        if self.source.source_id == "playwright-glassnode-sopr":
            return await self._collect_glassnode_sopr()
        if self.source.source_id == "fxstreet-economic-calendar":
            return await self._collect_fxstreet_economic_calendar()
        if self.source.source_id == "bitbo-sth-lth-realized-price":
            return await self._collect_bitbo_sth_lth_realized_price()

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is not installed; run `python -m playwright install chromium`"
            ) from exc

        artifact = paths.playwright_artifacts_dir / f"{self.source.source_id}-live.html"
        paths.ensure_directories()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.source.url or "", wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3_000)
            html = await page.content()
            text = await page.locator("body").inner_text(timeout=10_000)
            await browser.close()
        artifact.write_text(html, encoding="utf-8")
        metric_id = self.source.metrics[0]
        value = _extract_tradingview_number(text, self.source.metadata, html=html)
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload={
                    "url": self.source.url,
                    "artifact_path": str(artifact),
                    "text_sample": text[:1000],
                },
            ),
            metrics=[
                MetricSample(
                    metric_id=metric_id,
                    source_id=self.source.source_id,
                    value=value,
                    quality_score=float(self.source.metadata.get("quality_score", 0.7)),
                )
            ],
        )

    async def _render_page_text(self, wait_ms: int = 3_000) -> tuple[str, str]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is not installed; run `python -m playwright install chromium`"
            ) from exc

        artifact = paths.playwright_artifacts_dir / f"{self.source.source_id}-live.html"
        paths.ensure_directories()
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.source.url or "", wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(wait_ms)
            html = await page.content()
            text = await page.locator("body").inner_text(timeout=10_000)
            await browser.close()
        artifact.write_text(html, encoding="utf-8")
        return text, str(artifact)

    async def _collect_fxstreet_economic_calendar(self) -> CollectionResult:
        text, artifact_path = await self._render_page_text(wait_ms=10_000)
        rows = _parse_fxstreet_calendar_text(text, self.source.metadata)
        scored = [_score_macro_event(row) for row in rows]
        usable = [row for row in scored if row.get("usable")]
        if usable:
            weighted_sum = sum(float(row["weighted_surprise"]) for row in usable)
            weight_total = sum(float(row["importance_weight"]) for row in usable) or 1.0
            aggregate = weighted_sum / weight_total
            latest = usable[-1]
            score = float(latest["weighted_surprise"])
            quality = float(self.source.metadata.get("quality_score", 0.74))
            status = SourceStatus.HEALTHY
            error_message = None
            fxstreet_status = "healthy"
            surprise_meaning = "released_surprise"
            should_trigger_alert = True
        else:
            aggregate = 0.0
            score = 0.0
            quality = 0.70 if rows else 0.45
            status = SourceStatus.HEALTHY if rows else SourceStatus.WARNING
            error_message = None if rows else "FXStreet rendered but no USD event rows were found"
            fxstreet_status = "no_released_event" if rows else "parser_or_page_failure"
            surprise_meaning = "no_new_surprise" if rows else "parser_or_page_failure"
            should_trigger_alert = False
        now = datetime.now(UTC)
        payload = {
            "url": self.source.url,
            "artifact_path": artifact_path,
            "fxstreet_status": fxstreet_status,
            "rows": rows,
            "scored_events": scored,
            "usable_event_count": len(usable),
            "diagnostics": _fxstreet_diagnostics(rows, scored, usable),
            "macro_surprise": {
                "value": score,
                "meaning": surprise_meaning,
                "should_trigger_alert": should_trigger_alert,
                "should_not_trigger_alert": not should_trigger_alert,
            },
            "fallback_candidates": [
                "investing_calendar_playwright",
                "forexfactory_calendar_playwright",
                "finnhub_economic_calendar_api_optional",
            ],
            "formula": "raw_surprise = actual - consensus; weighted = normalized * importance",
            "note": "Positive score means hawkish/rate-pressure surprise; negative means dovish.",
        }
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload=payload,
                status=status,
                error_message=error_message,
            ),
            metrics=[
                MetricSample(
                    metric_id="macro_surprise_score",
                    source_id=self.source.source_id,
                    ts=now,
                    value=score,
                    timeframe="event",
                    quality_score=quality,
                ),
                MetricSample(
                    metric_id="aggregate_macro_surprise",
                    source_id=self.source.source_id,
                    ts=now,
                    value=aggregate,
                    timeframe="event",
                    quality_score=max(quality - 0.03, 0.0),
                ),
                MetricSample(
                    metric_id="macro_surprise_event_count",
                    source_id=self.source.source_id,
                    ts=now,
                    value=float(len(usable)),
                    timeframe="event",
                    quality_score=quality,
                ),
            ],
        )

    async def _collect_bitbo_sth_lth_realized_price(self) -> CollectionResult:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is not installed; run `python -m playwright install chromium`"
            ) from exc

        profile_dir = paths.cache_dir / str(
            self.source.metadata.get("profile_dir", "playwright-bitbo-profile")
        )
        pages = dict(self.source.metadata["pages"])
        value_columns = dict(self.source.metadata["value_columns"])
        quality = float(self.source.metadata.get("quality_score", 0.72))
        captures: dict[str, dict[str, Any]] = {}
        metrics: list[MetricSample] = []
        status = SourceStatus.HEALTHY
        error_message: str | None = None

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=True,
                viewport={"width": 1600, "height": 950},
            )
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                for metric_id, url in pages.items():
                    await page.goto(url, wait_until="networkidle", timeout=60_000)
                    title = await page.title()
                    if "Human Challenge" in title:
                        raise RuntimeError(
                            "Bitbo human verification is required; run "
                            "`python scripts/bitbo_capture_visible.py` first"
                        )
                    export_data = await page.evaluate("window.chartExportData")
                    sample = _bitbo_metric_sample(
                        self.source,
                        metric_id,
                        export_data,
                        value_columns[metric_id],
                        quality,
                    )
                    metrics.append(sample)
                    captures[metric_id] = {
                        "url": url,
                        "title": title,
                        "columns": export_data.get("columns"),
                        "latest_row": (export_data.get("data") or [])[-1],
                        "row_count": len(export_data.get("data") or []),
                    }
            except Exception as exc:  # noqa: BLE001
                status = SourceStatus.WARNING
                error_message = str(exc)
            finally:
                await context.close()

        if not metrics:
            result = self._mock_result(status=SourceStatus.WARNING, quality=0.45)
            result.raw.error_message = error_message or "Bitbo chart export data unavailable"
            result.raw.payload["requires_human_verified_profile"] = True
            return result

        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload={
                    "captures": captures,
                    "profile_dir": str(profile_dir),
                    "requires_human_verified_profile": True,
                },
                status=status,
                error_message=error_message,
            ),
            metrics=metrics,
        )

    def _mock_result(
        self,
        status: SourceStatus = SourceStatus.HEALTHY,
        quality: float = 0.95,
    ) -> CollectionResult:
        artifact = _write_playwright_artifact(self.source.source_id)
        result = super()._mock_result(status=status, quality=quality)
        result.raw.payload["artifact_path"] = str(artifact)
        return result

    async def _collect_glassnode_asset_overview(self) -> CollectionResult:
        captures = await _capture_glassnode_series(
            self.source,
            {
                "etf_net_flow": (
                    "/api/metrics-proxy/institutions/us_spot_etf_flows_net"
                    "?a=BTC&c=usd&i=24h&referrer=dashboards"
                ),
                "exchange_balance": (
                    "/api/metrics-proxy/distribution/balance_exchanges"
                    "?a=BTC&e=aggregated&referrer=dashboards"
                ),
                "active_addresses": (
                    "/api/metrics-proxy/addresses/active_count?a=BTC&i=24h&referrer=dashboards"
                ),
                "transfer_volume_adjusted_usd": (
                    "/api/metrics-proxy/transactions/transfers_volume_adjusted_sum"
                    "?a=BTC&c=usd&i=24h&referrer=dashboards"
                ),
                "nupl": (
                    "/api/metrics-proxy/indicators/net_unrealized_profit_loss"
                    "?a=BTC&c=native&i=24h&referrer=dashboards"
                ),
                "mvrv_zscore": (
                    "/api/metrics-proxy/market/mvrv_z_score"
                    "?a=BTC&c=native&i=24h&referrer=dashboards"
                ),
            },
        )
        etf_series = captures["etf_net_flow"]["series"]
        balance_series = captures["exchange_balance"]["series"]
        latest_etf = _latest_non_null_point(etf_series)
        latest_balance = _latest_non_null_point(balance_series)
        previous_balance = _previous_non_null_point(balance_series)
        latest_active_addresses = _latest_non_null_point(captures["active_addresses"]["series"])
        latest_transfer_volume = _latest_non_null_point(
            captures["transfer_volume_adjusted_usd"]["series"]
        )
        latest_nupl = _latest_non_null_point(captures["nupl"]["series"])
        latest_mvrv = _latest_non_null_point(captures["mvrv_zscore"]["series"])
        if latest_etf is None or latest_balance is None or previous_balance is None:
            raise RuntimeError("Glassnode public overview did not return enough data")
        etf_7d = sum(point["v"] for point in _latest_non_null_points(etf_series, 7))
        exchange_netflow = latest_balance["v"] - previous_balance["v"]
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload=_glassnode_capture_payload(captures),
            ),
            metrics=[
                MetricSample(
                    metric_id="etf_net_flow",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest_etf["t"], tz=UTC),
                    value=float(latest_etf["v"]),
                    quality_score=0.78,
                ),
                MetricSample(
                    metric_id="etf_flow_7d",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest_etf["t"], tz=UTC),
                    value=float(etf_7d),
                    quality_score=0.78,
                ),
                MetricSample(
                    metric_id="exchange_balance_delta_1d_proxy",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest_balance["t"], tz=UTC),
                    value=float(exchange_netflow),
                    quality_score=0.7,
                ),
                MetricSample(
                    metric_id="active_addresses",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest_active_addresses["t"], tz=UTC),
                    value=float(latest_active_addresses["v"]),
                    quality_score=0.82,
                ),
                MetricSample(
                    metric_id="transfer_volume_adjusted_usd",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest_transfer_volume["t"], tz=UTC),
                    value=float(latest_transfer_volume["v"]),
                    quality_score=0.78,
                ),
                MetricSample(
                    metric_id="nupl",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest_nupl["t"], tz=UTC),
                    value=float(latest_nupl["v"]),
                    quality_score=0.78,
                ),
                MetricSample(
                    metric_id="mvrv_zscore",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest_mvrv["t"], tz=UTC),
                    value=float(latest_mvrv["v"]),
                    quality_score=0.78,
                ),
            ],
        )

    async def _collect_glassnode_sopr(self) -> CollectionResult:
        captures = await _capture_glassnode_series(
            self.source,
            {"sopr": "/v1/metrics/indicators/sopr"},
        )
        latest = _latest_non_null_point(captures["sopr"]["series"])
        if latest is None:
            raise RuntimeError("Glassnode public SOPR chart did not return data")
        return CollectionResult(
            source=self.source,
            raw=RawObservationData(
                source_id=self.source.source_id,
                payload=_glassnode_capture_payload(captures),
            ),
            metrics=[
                MetricSample(
                    metric_id="sopr",
                    source_id=self.source.source_id,
                    ts=datetime.fromtimestamp(latest["t"], tz=UTC),
                    value=float(latest["v"]),
                    quality_score=0.76,
                )
            ],
        )


def make_client(source: SourceConfig, mode: SourceMode = SourceMode.MOCK) -> SourceClient:
    match source.kind:
        case SourceKind.FRED:
            return FredClient(source, mode)
        case SourceKind.EXCHANGE:
            return ExchangeClient(source, mode)
        case SourceKind.BITCOIN:
            return BitcoinClient(source, mode)
        case SourceKind.OFFICIAL:
            return OfficialClient(source, mode)
        case SourceKind.PLAYWRIGHT:
            return PlaywrightClient(source, mode)


def _has_float(row: dict[str, Any], key: str) -> bool:
    try:
        value = row.get(key)
        return value not in {None, ""} and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _mempool_lightning_result(
    source: SourceConfig,
    payload: Any,
    url: str,
) -> CollectionResult:
    rows = payload if isinstance(payload, list) else [payload]
    latest = rows[-1] if rows else {}
    if not isinstance(latest, dict):
        raise RuntimeError("mempool lightning response is not an object")
    capacity = _first_available_float(
        latest,
        "total_capacity",
        "totalCapacity",
        "network_capacity",
        "networkCapacity",
        "capacity",
        "total_capacity_sat",
        "totalCapacitySat",
    )
    if capacity is None:
        raise RuntimeError("mempool lightning response missing capacity")
    if capacity > 21_000_000:
        capacity = capacity / 100_000_000
    channels = _first_available_float(
        latest,
        "channel_count",
        "channels",
        "channels_count",
        "channelCount",
    )
    nodes = _first_available_float(latest, "node_count", "nodes", "nodes_count", "nodeCount")
    ts = _timestamp_from_payload(latest)
    return CollectionResult(
        source=source,
        raw=RawObservationData(source_id=source.source_id, payload={"url": url, "latest": latest}),
        metrics=[
            MetricSample(
                metric_id="lightning_capacity_btc",
                source_id=source.source_id,
                ts=ts,
                value=capacity,
                quality_score=0.82,
            ),
            MetricSample(
                metric_id="lightning_channel_count",
                source_id=source.source_id,
                ts=ts,
                value=channels or 0.0,
                quality_score=0.78 if channels else 0.55,
            ),
            MetricSample(
                metric_id="lightning_node_count",
                source_id=source.source_id,
                ts=ts,
                value=nodes or 0.0,
                quality_score=0.78 if nodes else 0.55,
            ),
        ],
    )


def _first_available_float(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value in {None, ""}:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _timestamp_from_payload(payload: dict[str, Any]) -> datetime:
    value = payload.get("time") or payload.get("timestamp") or payload.get("created_at")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return datetime.now(UTC)
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=UTC)
    return datetime.now(UTC)


def _parse_clarkmoody_dashboard(html: str) -> dict[str, dict[str, Any]]:
    text = _html_to_text(html).replace("×", "x")
    sections = {
        "bitcoin_network": _text_between(text, "Bitcoin Network", "Lightning Network (Public)"),
        "lightning": _text_between(text, "Lightning Network (Public)", "Transactions"),
        "transactions": _text_between(text, "Transactions", "Chain Security"),
        "chain_security": _text_between(text, "Chain Security", "Mining"),
        "mining": _text_between(text, "Mining Economics", "Mempool"),
        "mempool": _text_between(text, "Mempool", "Predicted Next Block"),
    }
    specs: dict[str, tuple[str, tuple[str, ...], str]] = {
        "lightning_capacity_btc": ("lightning", ("Total Capacity",), "btc"),
        "lightning_capacity_usd": ("lightning", ("Capacity Value",), "usd"),
        "lightning_node_count": ("lightning", ("Total Nodes",), "count"),
        "lightning_channel_count": ("lightning", ("Total Channels",), "count"),
        "lightning_tor_capacity_btc": ("lightning", ("Tor Capacity",), "btc"),
        "lightning_tor_capacity_pct": (
            "lightning",
            ("Percentage Tor Capacity", "Tor Capacity Percentage", "% Tor Capacity"),
            "percent",
        ),
        "lightning_tor_node_count": ("lightning", ("Tor Nodes",), "count"),
        "bitcoin_reachable_nodes": ("bitcoin_network", ("Reachable Bitcoin Nodes",), "count"),
        "bitcoin_tor_nodes": ("bitcoin_network", ("Bitcoin Tor Nodes",), "count"),
        "bitcoin_tor_nodes_pct": (
            "bitcoin_network",
            ("Percentage Tor Nodes", "Tor Nodes Percentage", "% Tor Nodes"),
            "percent",
        ),
        "mempool_tx_count": ("mempool", ("Transactions",), "count"),
        "mempool_vsize_mb": ("mempool", ("vSize",), "mb"),
        "mempool_blocks_to_clear": ("mempool", ("Blocks to Clear",), "blocks"),
        "mempool_pending_fees_btc": ("mempool", ("Pending Fees",), "btc"),
        "mempool_min_fee_rate_sat_vb": ("mempool", ("Minimum Fee Rate",), "sat_vb"),
        "hashrate_90d_ehs": ("chain_security", ("Hash Rate, 90 Days",), "eh_s"),
        "hash_price_usd": ("mining", ("Hash Price (PHash/s)",), "usd"),
        "avg_fees_per_block_btc": ("mining", ("Avg. Fees per Block",), "btc"),
        "fees_vs_reward_pct": (
            "mining",
            ("Avg. Fees vs. Reward", "Average Fees vs. Reward", "Fees vs. Reward"),
            "percent",
        ),
    }
    parsed: dict[str, dict[str, Any]] = {}
    for metric_id, (section_id, labels, unit) in specs.items():
        raw_value = _first_label_value(sections.get(section_id, ""), labels)
        if raw_value is None:
            raw_value = _clarkmoody_fallback_value(metric_id, sections.get(section_id, ""))
        if raw_value is None:
            continue
        value = _parse_clarkmoody_value(raw_value)
        if value is None:
            continue
        parsed[metric_id] = {
            "section": section_id,
            "label": labels[0],
            "raw_value": raw_value,
            "value": value,
            "unit": unit,
        }
    return parsed


def _text_between(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    if start_index == -1:
        return ""
    end_index = text.find(end, start_index + len(start))
    if end_index == -1:
        return text[start_index:]
    return text[start_index:end_index]


def _label_value(text: str, label: str) -> str | None:
    pattern = re.compile(
        rf"{re.escape(label)}\s+"
        r"(\$?[0-9][0-9,]*(?:\.\d+)?(?:[KMBT])?(?:\s*(?:BTC|%|MB|EH/s|sat/vB|sats))?)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def _first_label_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        value = _label_value(text, label)
        if value is not None:
            return value
    return None


def _clarkmoody_fallback_value(metric_id: str, text: str) -> str | None:
    patterns = {
        "lightning_tor_capacity_pct": (
            r"Tor Capacity\s+\$?[0-9][0-9,]*(?:\.\d+)?(?:[KMBT])?\s*BTC\s+"
            r"([0-9]+(?:\.\d+)?)\s*%",
            r"Tor Capacity[^\n%]{0,120}?([0-9]+(?:\.\d+)?)\s*%",
        ),
        "bitcoin_tor_nodes_pct": (
            r"Bitcoin Tor Nodes\s+[0-9][0-9,]*\s+([0-9]+(?:\.\d+)?)\s*%",
            r"Tor Nodes[^\n%]{0,120}?([0-9]+(?:\.\d+)?)\s*%",
        ),
        "fees_vs_reward_pct": (
            r"Avg\.\s*Fees per Block\s+[0-9]+(?:\.\d+)?\s*BTC\s+"
            r"([0-9]+(?:\.\d+)?)\s*%",
            r"Fees vs\.?\s*Reward[^\n%]{0,80}?([0-9]+(?:\.\d+)?)\s*%",
        ),
    }
    for pattern in patterns.get(metric_id, ()):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return f"{match.group(1)}%"
    return None


def _parse_clarkmoody_value(raw_value: str) -> float | None:
    value = raw_value.replace(",", "").replace("$", "").strip()
    value = re.sub(r"\s*(BTC|MB|EH/s|sat/vB|sats)\b", "", value, flags=re.IGNORECASE)
    value = value.replace("%", "")
    multiplier = 1.0
    suffix = value[-1:].upper()
    if suffix in {"K", "M", "B", "T"}:
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}[
            suffix
        ]
        value = value[:-1]
    try:
        return float(value) * multiplier
    except ValueError:
        return None


async def _collect_binance_force_order(source: SourceConfig) -> CollectionResult:
    message = await _websocket_first_message(
        "wss://fstream.binance.com/ws/btcusdt@forceOrder",
        timeout_seconds=float(source.metadata.get("sample_seconds", 5)),
    )
    if message is None:
        return _liquidation_result(source, {"events": [], "window_ms": 1000}, 0.0, 0.0, 0.74)
    payload = json.loads(message)
    order = payload.get("o", payload)
    notional = float(order.get("q", 0) or 0) * float(order.get("ap") or order.get("p") or 0)
    side = str(order.get("S", "")).upper()
    long_usd = notional if side == "SELL" else 0.0
    short_usd = notional if side == "BUY" else 0.0
    ts = datetime.fromtimestamp(float(payload.get("E") or order.get("T") or 0) / 1000, tz=UTC)
    return _liquidation_result(
        source,
        {"event": payload, "window_ms": 1000, "note": "Binance forceOrder snapshot"},
        long_usd,
        short_usd,
        0.76,
        ts=ts,
    )


async def _collect_bybit_liquidation(source: SourceConfig) -> CollectionResult:
    subscribe = {"op": "subscribe", "args": ["allLiquidation.BTCUSDT"]}
    message = await _websocket_first_message(
        "wss://stream.bybit.com/v5/public/linear",
        subscribe=subscribe,
        timeout_seconds=float(source.metadata.get("sample_seconds", 5)),
    )
    if message is None:
        return _liquidation_result(source, {"events": [], "window_ms": 500}, 0.0, 0.0, 0.74)
    payload = json.loads(message)
    rows = payload.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    long_usd = 0.0
    short_usd = 0.0
    for row in rows:
        size = float(row.get("v") or row.get("size") or 0)
        price = float(row.get("p") or row.get("price") or 0)
        notional = size * price
        side = str(row.get("S") or row.get("side") or "").lower()
        if side == "sell":
            long_usd += notional
        elif side == "buy":
            short_usd += notional
    ts_value = payload.get("ts") or payload.get("creationTime") or 0
    ts = datetime.fromtimestamp(float(ts_value) / 1000, tz=UTC) if ts_value else datetime.now(UTC)
    return _liquidation_result(
        source,
        {"event": payload, "window_ms": 500, "note": "Bybit allLiquidation snapshot"},
        long_usd,
        short_usd,
        0.76,
        ts=ts,
    )


async def _websocket_first_message(
    url: str,
    subscribe: dict[str, Any] | None = None,
    timeout_seconds: float = 5,
) -> str | None:
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("websockets is not installed") from exc
    try:
        async with websockets.connect(url, open_timeout=timeout_seconds) as websocket:
            if subscribe is not None:
                await websocket.send(json.dumps(subscribe))
            deadline = datetime.now(UTC) + timedelta(seconds=timeout_seconds)
            while datetime.now(UTC) < deadline:
                remaining = max((deadline - datetime.now(UTC)).total_seconds(), 0.1)
                raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                if _is_data_websocket_message(text):
                    return text
    except TimeoutError:
        return None
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"websocket collection failed: {exc}") from exc
    return None


def _is_data_websocket_message(message: str) -> bool:
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return False
    if payload.get("success") is True or payload.get("op") in {"subscribe", "pong"}:
        return False
    return bool(payload.get("o") or payload.get("data"))


def _liquidation_result(
    source: SourceConfig,
    payload: dict[str, Any],
    long_usd: float,
    short_usd: float,
    quality: float,
    ts: datetime | None = None,
) -> CollectionResult:
    ts = ts or datetime.now(UTC)
    total_usd = long_usd + short_usd
    impulse_z = _clamp(total_usd / 1_000_000.0, 0.0, 3.0)
    imbalance = (short_usd - long_usd) / total_usd if total_usd > 0 else 0.0
    return CollectionResult(
        source=source,
        raw=RawObservationData(source_id=source.source_id, payload=payload),
        metrics=[
            MetricSample(
                metric_id="liquidation_long_usd",
                source_id=source.source_id,
                ts=ts,
                value=long_usd,
                timeframe="snapshot",
                quality_score=quality,
            ),
            MetricSample(
                metric_id="liquidation_short_usd",
                source_id=source.source_id,
                ts=ts,
                value=short_usd,
                timeframe="snapshot",
                quality_score=quality,
            ),
            MetricSample(
                metric_id="liquidation_impulse_z_15m",
                source_id=source.source_id,
                ts=ts,
                value=impulse_z,
                timeframe="snapshot",
                quality_score=max(quality - 0.05, 0.0),
            ),
            MetricSample(
                metric_id="liquidation_impulse_z_1h",
                source_id=source.source_id,
                ts=ts,
                value=impulse_z,
                timeframe="snapshot",
                quality_score=max(quality - 0.05, 0.0),
            ),
            MetricSample(
                metric_id="liquidation_followthrough_score",
                source_id=source.source_id,
                ts=ts,
                value=_clamp(imbalance * 35.0, -100.0, 100.0),
                timeframe="snapshot",
                quality_score=max(quality - 0.12, 0.0),
            ),
            MetricSample(
                metric_id="liquidation_absorption_score",
                source_id=source.source_id,
                ts=ts,
                value=0.0,
                timeframe="snapshot",
                quality_score=max(quality - 0.18, 0.0),
            ),
        ],
    )


def _defillama_previous_week_supply(payload: dict[str, Any]) -> float | None:
    total = 0.0
    found = False
    for asset in payload.get("peggedAssets", []):
        candidates = [
            asset.get("circulatingPrevWeek", {}).get("peggedUSD"),
            asset.get("circulatingPrev7d", {}).get("peggedUSD"),
            asset.get("circulating7dAgo", {}).get("peggedUSD"),
        ]
        for value in candidates:
            if value is not None:
                total += float(value)
                found = True
                break
    return total if found else None


def _parse_fed_rss(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    events: list[dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        title = _xml_text(item, "title")
        link = _xml_text(item, "link")
        published = _parse_rss_datetime(_xml_text(item, "pubDate"))
        description = _html_to_text(_xml_text(item, "description"))
        if not title:
            continue
        speaker = _fed_speaker_from_title(title)
        events.append(
            {
                "event_id": _stable_event_id("fed", title, published, link),
                "source": "federalreserve_rss",
                "speaker": speaker["name"],
                "role": speaker["role"],
                "speaker_weight": speaker["weight"],
                "title": title,
                "url": link,
                "published_at": published,
                "description": description,
            }
        )
    return sorted(events, key=lambda item: item["published_at"], reverse=True)


def _xml_text(item: ET.Element, tag: str) -> str:
    child = item.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_rss_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fed_speaker_from_title(title: str) -> dict[str, Any]:
    raw = title.split(",", 1)[0].strip()
    name = raw or "Unknown"
    lowered = name.lower()
    role = "fed_official"
    weight = 2
    if "powell" in lowered or "chair" in lowered:
        role = "chair"
        weight = 5
    elif lowered in {"jefferson", "barr"} or "vice chair" in lowered:
        role = "vice_chair"
        weight = 4
    elif lowered in {"bowman", "waller", "cook", "kugler"}:
        role = "board_governor"
        weight = 3
    elif "williams" in lowered or "new york" in lowered:
        role = "ny_fed_president"
        weight = 4
    elif name == "Unknown":
        role = "unknown"
        weight = 1
    return {"name": name, "role": role, "weight": weight}


def _score_fed_speech_event(event: dict[str, Any], text: str) -> dict[str, Any]:
    normalized = text.lower()
    topic_hits = _fed_topic_hits(normalized)
    hawkish_hits = _keyword_hits(
        normalized,
        [
            "inflation remains elevated",
            "inflation is still too high",
            "price stability",
            "restrictive",
            "higher for longer",
            "further tightening",
            "tight labor market",
            "upside risks to inflation",
            "balance sheet runoff",
            "quantitative tightening",
            "not yet sufficiently restrictive",
        ],
    )
    dovish_hits = _keyword_hits(
        normalized,
        [
            "rate cuts",
            "cut rates",
            "easing",
            "disinflation",
            "softening labor market",
            "downside risks",
            "slowdown",
            "unemployment has risen",
            "inflation has moved down",
            "less restrictive",
        ],
    )
    uncertainty_hits = _keyword_hits(
        normalized,
        ["data dependent", "uncertainty", "uncertain", "risks on both sides", "wait and see"],
    )
    topic_weight = max(topic_hits.values(), default=1)
    speaker_weight = float(event.get("speaker_weight") or 1)
    hawkish_score = _clamp(
        (hawkish_hits * 0.18 + topic_weight * 0.06) * speaker_weight / 5,
        0,
        1,
    )
    dovish_score = _clamp((dovish_hits * 0.18) * speaker_weight / 5, 0, 1)
    uncertainty_score = _clamp(uncertainty_hits * 0.12, 0, 1)
    content_risk = _clamp(hawkish_score - dovish_score + uncertainty_score * 0.25, -1, 1)
    fed_speech_risk = _clamp(max(content_risk, 0) * 0.82 + speaker_weight / 5 * 0.08, 0, 1)
    return {
        "speaker": event.get("speaker"),
        "speaker_weight": speaker_weight,
        "topic_hits": topic_hits,
        "hawkish_score": hawkish_score,
        "dovish_score": dovish_score,
        "uncertainty_score": uncertainty_score,
        "content_risk": content_risk,
        "fed_speech_risk": fed_speech_risk,
        "btc_macro_bias": "bearish"
        if content_risk > 0.12
        else "bullish"
        if content_risk < -0.12
        else "mixed",
    }


def _fed_topic_hits(text: str) -> dict[str, int]:
    topics = {
        "rate_path": ["policy rate", "federal funds rate", "rate path", "rate cuts", "hikes"],
        "inflation": ["inflation", "price stability", "pce", "cpi"],
        "labor_market": ["employment", "unemployment", "payrolls", "labor market", "wage"],
        "balance_sheet_qt_qe": ["balance sheet", "qt", "reserves", "asset purchases"],
        "financial_stability": ["financial stability", "banking stress", "liquidity"],
    }
    return {topic: _keyword_hits(text, words) for topic, words in topics.items()}


def _keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(text.count(keyword.lower()) for keyword in keywords)


def _stable_event_id(prefix: str, title: str, published_at: datetime, url: str) -> str:
    digest = hashlib.sha1(f"{title}|{published_at.isoformat()}|{url}".encode()).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _parse_fed_calendar_events(html: str, today: date) -> list[dict[str, Any]]:
    text = _html_to_text(html)
    events: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(Speech|Testimony|FOMC|Beige Book).*?"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),\s+(20\d{2})",
        text,
        flags=re.IGNORECASE,
    ):
        event_date = _date_from_month_name(match.group(2), int(match.group(3)), int(match.group(4)))
        if event_date >= today:
            events.append(
                _fed_calendar_event(
                    match.group(1).title(),
                    event_date,
                    time(12, 0),
                    "official_calendar",
                )
            )
    return events


def _fallback_fed_speech_events(today: date) -> list[dict[str, Any]]:
    rows = [
        ("Fed public communication window", date(2026, 6, 12), 2),
        ("FOMC statement and Powell press conference", date(2026, 6, 17), 5),
        ("Fed public communication window", date(2026, 7, 24), 2),
        ("FOMC statement and Powell press conference", date(2026, 7, 29), 5),
        ("FOMC statement and Powell press conference", date(2026, 9, 16), 5),
        ("FOMC statement and Powell press conference", date(2026, 10, 28), 5),
        ("FOMC statement and Powell press conference", date(2026, 12, 9), 5),
    ]
    return [
        _fed_calendar_event(name, event_date, time(14, 0), "fallback_fomc_calendar", weight)
        for name, event_date, weight in rows
        if event_date >= today
    ]


def _fed_calendar_event(
    name: str,
    event_date: date,
    event_time: time,
    source: str,
    speaker_weight: int = 2,
) -> dict[str, Any]:
    event = _macro_event("fed_speech", name, event_date, event_time, "US/Eastern", source=source)
    event["speaker_weight"] = speaker_weight
    return event


def _fed_scheduled_risk(event: dict[str, Any] | None, hours_until: float) -> float:
    if event is None:
        return 0.0
    speaker_weight = float(event.get("speaker_weight") or 2)
    if hours_until <= 6:
        time_weight = 5
    elif hours_until <= 24:
        time_weight = 4
    elif hours_until <= 72:
        time_weight = 3
    elif hours_until <= 168:
        time_weight = 1
    else:
        time_weight = 0.25
    return _clamp((speaker_weight * time_weight) / 25, 0, 1)


def _fomc_blackout_state(now: datetime) -> dict[str, Any]:
    fomc_events = [
        event for event in _fallback_macro_events(now.date()) if event["event_type"] == "fomc"
    ]
    active_period: dict[str, Any] | None = None
    for event in fomc_events:
        meeting_dt = event["datetime"]
        start_date = _second_saturday_before(meeting_dt.date())
        start_dt = _macro_event(
            "blackout",
            "FOMC blackout begins",
            start_date,
            time(0, 0),
            "US/Eastern",
        )["datetime"]
        end_dt = meeting_dt + timedelta(days=1, hours=9, minutes=59)
        period = {"meeting_date": event["date"], "start": start_dt, "end": end_dt}
        if start_dt <= now <= end_dt:
            active_period = period
    next_meeting = min(
        (event for event in fomc_events if event["datetime"] >= now),
        key=lambda item: item["datetime"],
        default=None,
    )
    days_until = (
        max((next_meeting["datetime"] - now).total_seconds() / 86_400, 0)
        if next_meeting
        else None
    )
    active = active_period is not None
    if active:
        event_risk = 0.85
    elif days_until is not None and days_until <= 7:
        event_risk = 0.62
    elif days_until is not None and days_until <= 14:
        event_risk = 0.38
    else:
        event_risk = 0.14
    return {
        "active": active,
        "active_period": (
            {
                "meeting_date": active_period["meeting_date"],
                "start": active_period["start"].isoformat(),
                "end": active_period["end"].isoformat(),
            }
            if active_period
            else None
        ),
        "next_fomc": (
            {**next_meeting, "datetime": next_meeting["datetime"].isoformat()}
            if next_meeting
            else None
        ),
        "days_until_next_fomc": days_until,
        "fomc_event_risk": event_risk,
        "rule": "second Saturday before FOMC through day after meeting, approximated in UTC",
    }


def _second_saturday_before(event_date: date) -> date:
    current = event_date
    saturdays = 0
    while saturdays < 2:
        current -= timedelta(days=1)
        if current.weekday() == 5:
            saturdays += 1
    return current


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _parse_macro_events(event_type: str, html: str, today: date) -> list[dict[str, Any]]:
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    text = re.sub(r"\s+", " ", text)
    parsers = {
        "fomc": _parse_fomc_events,
        "pce": _parse_bea_pce_events,
        "bls": _parse_bls_events,
    }
    parser = parsers.get(event_type)
    return parser(text, today) if parser else []


def _parse_fomc_events(text: str, today: date) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})(?:-\d{1,2})?,\s+(20\d{2})",
        text,
    ):
        event_date = _date_from_month_name(match.group(1), int(match.group(2)), int(match.group(3)))
        if event_date >= today:
            events.append(
                _macro_event("fomc", "FOMC meeting", event_date, time(14, 0), "US/Eastern")
            )
    return events


def _parse_bea_pce_events(text: str, today: date) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for match in re.finditer(
        r"(Personal Income and Outlays).*?"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),\s+(20\d{2})",
        text,
    ):
        event_date = _date_from_month_name(match.group(2), int(match.group(3)), int(match.group(4)))
        if event_date >= today:
            events.append(
                _macro_event("pce", match.group(1), event_date, time(8, 30), "US/Eastern")
            )
    return events


def _parse_bls_events(text: str, today: date) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    patterns = [
        ("cpi", "Consumer Price Index"),
        ("nfp", "Employment Situation"),
    ]
    for event_type, label in patterns:
        for match in re.finditer(
            rf"{label}.*?"
            r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+(\d{1,2}),\s+(20\d{2})",
            text,
        ):
            event_date = _date_from_month_name(
                match.group(1),
                int(match.group(2)),
                int(match.group(3)),
            )
            if event_date >= today:
                events.append(
                    _macro_event(event_type, label, event_date, time(8, 30), "US/Eastern")
                )
    return events


def _resolution_error_status(error: str | None) -> str:
    if error and "403" in error:
        return "http_403"
    return "error" if error else "empty"


def _apply_macro_fallback_resolution(
    source_resolution: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    fallback_events: list[dict[str, Any]],
) -> None:
    fallback_counts: dict[str, int] = {}
    for event in fallback_events:
        fallback_counts[event["event_type"]] = fallback_counts.get(event["event_type"], 0) + 1
    for event_type, count in fallback_counts.items():
        if event_type in {"cpi", "nfp"}:
            resolution_key = "bls"
        else:
            resolution_key = event_type
        resolution = source_resolution.setdefault(
            resolution_key,
            {
                "status": "embedded_fallback",
                "url_attempted": [],
                "fallback_used": True,
                "event_count": 0,
                "error": None,
            },
        )
        official_events = [
            event
            for event in events
            if event["event_type"] == event_type
            and event.get("source") != "fallback_2026_official_calendar"
        ]
        if not official_events:
            resolution["status"] = "embedded_fallback"
            resolution["fallback_used"] = True
            resolution["fallback_event_count"] = count


def _mark_optional_official_calendar_resolution(
    source_resolution: dict[str, dict[str, Any]],
) -> None:
    for resolution in source_resolution.values():
        if not resolution.get("optional_official"):
            continue
        original_status = str(resolution.get("status", ""))
        if original_status != "embedded_fallback":
            continue
        error = str(resolution.get("error") or "")
        if "403" not in error:
            continue
        fallback_stack = list(resolution.get("fallback_stack") or [])
        fallback_provider = (
            "embedded_official_calendar_table"
            if "embedded_official_calendar_table" in fallback_stack
            else "embedded_fallback"
        )
        resolution["status"] = "official_blocked_embedded_fallback"
        resolution["official_status"] = "http_403"
        resolution["official_blocked"] = True
        resolution["fallback_provider"] = fallback_provider
        resolution["blocking_error"] = False


def _fallback_macro_calendar_metadata(today: date) -> dict[str, Any]:
    return {
        "year": 2026,
        "source_note": "official release schedule manually pinned",
        "updated_at": "2026-05-20",
        "expires_at": "2026-12-31",
        "expired": today > date(2026, 12, 31),
    }


def _fallback_macro_events(today: date) -> list[dict[str, Any]]:
    dates = {
        "nfp": [
            (2026, 6, 5),
            (2026, 7, 2),
            (2026, 8, 7),
            (2026, 9, 4),
            (2026, 10, 2),
            (2026, 11, 6),
            (2026, 12, 4),
        ],
        "cpi": [
            (2026, 6, 10),
            (2026, 7, 15),
            (2026, 8, 12),
            (2026, 9, 11),
            (2026, 10, 15),
            (2026, 11, 12),
            (2026, 12, 10),
        ],
        "fomc": [
            (2026, 6, 17),
            (2026, 7, 29),
            (2026, 9, 16),
            (2026, 10, 28),
            (2026, 12, 9),
        ],
        "pce": [
            (2026, 5, 29),
            (2026, 6, 26),
            (2026, 7, 30),
            (2026, 8, 26),
            (2026, 9, 30),
            (2026, 10, 30),
            (2026, 11, 25),
            (2026, 12, 23),
        ],
    }
    labels = {
        "nfp": "Employment Situation",
        "cpi": "Consumer Price Index",
        "fomc": "FOMC meeting",
        "pce": "Personal Income and Outlays",
    }
    times = {"fomc": time(14, 0)}
    events: list[dict[str, Any]] = []
    for event_type, rows in dates.items():
        for year, month, day in rows:
            event_date = date(year, month, day)
            if event_date >= today - timedelta(days=7):
                events.append(
                    _macro_event(
                        event_type,
                        labels[event_type],
                        event_date,
                        times.get(event_type, time(8, 30)),
                        "US/Eastern",
                        source="fallback_2026_official_calendar",
                    )
                )
    return events


def _next_event_by_type(events: list[dict[str, Any]], now: datetime) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event in sorted(events, key=lambda item: item["datetime"]):
        if event["datetime"] < now:
            continue
        result.setdefault(event["event_type"], event)
    return result


def _nearest_event_by_type(
    events: list[dict[str, Any]],
    now: datetime,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event in sorted(
        events,
        key=lambda item: abs((item["datetime"] - now).total_seconds()),
    ):
        result.setdefault(event["event_type"], event)
    return result


def _macro_event(
    event_type: str,
    name: str,
    event_date: date,
    event_time: time,
    timezone: str,
    source: str = "official_page",
) -> dict[str, Any]:
    # Store the event in UTC using a fixed Eastern offset approximation.
    # Day-level precision is enough for P3 windows; exact DST handling can be refined later.
    eastern_offset_hours = 4 if event_date.month in range(3, 11) else 5
    local_dt = datetime.combine(event_date, event_time)
    utc_dt = local_dt + timedelta(hours=eastern_offset_hours)
    return {
        "event_type": event_type,
        "name": name,
        "date": event_date.isoformat(),
        "time": event_time.isoformat(),
        "timezone": timezone,
        "datetime": utc_dt.replace(tzinfo=UTC),
        "source": source,
    }


def _date_from_month_name(month_name: str, day: int, year: int) -> date:
    month = datetime.strptime(month_name, "%B").month
    return date(year, month, day)


def _parse_fxstreet_calendar_text(
    text: str,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    country_codes = {str(item).upper() for item in metadata.get("country_codes", ["USD"])}
    keywords = [str(item).lower() for item in metadata.get("event_keywords", [])]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rows: list[dict[str, Any]] = []
    current_day: str | None = None
    current_time: str | None = None
    for index, line in enumerate(lines):
        if re.match(r"^[A-Z]+,\s+[A-Z][A-Za-z]+\s+\d{1,2}$", line):
            current_day = line
            continue
        if _looks_like_calendar_time(line):
            current_time = line
            continue
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) < 2:
            continue
        country = parts[0].upper()
        if country not in country_codes:
            continue
        event_name = " ".join(parts[1:]).strip()
        if not event_name:
            continue
        values = (
            [part.strip() for part in lines[index + 1].split("\t")]
            if index + 1 < len(lines)
            else []
        )
        actual_text = values[0] if len(values) > 0 else None
        deviation_text = values[1] if len(values) > 1 else None
        consensus_text = values[2] if len(values) > 2 else None
        previous_text = values[3] if len(values) > 3 else None
        lower_name = event_name.lower()
        rows.append(
            {
                "day": current_day,
                "time": current_time,
                "country": country,
                "event_name": event_name,
                "actual_text": actual_text,
                "deviation_text": deviation_text,
                "consensus_text": consensus_text,
                "previous_text": previous_text,
                "actual": _parse_macro_numeric(actual_text),
                "deviation": _parse_macro_numeric(deviation_text),
                "consensus": _parse_macro_numeric(consensus_text),
                "previous": _parse_macro_numeric(previous_text),
                "relevant": not keywords or any(keyword in lower_name for keyword in keywords),
            }
        )
    return rows


def _looks_like_calendar_time(value: str) -> bool:
    return bool(
        re.match(r"^\d{1,2}:\d{2}\s*(?:AM|PM)$", value, re.IGNORECASE)
        or re.match(r"^\d+'\s*$", value)
    )


def _parse_macro_numeric(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned in {"", "-", "LOCKED", "REPORT"}:
        return None
    cleaned = cleaned.replace(",", "").replace("$", "")
    multiplier = 1.0
    suffix_match = re.search(r"([KMB])$", cleaned, re.IGNORECASE)
    if suffix_match:
        suffix = suffix_match.group(1).upper()
        multiplier = {"K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0}[suffix]
        cleaned = cleaned[:-1]
    cleaned = cleaned.replace("%", "")
    try:
        return float(cleaned) * multiplier
    except ValueError:
        return None


def _fxstreet_diagnostics(
    rows: list[dict[str, Any]],
    scored: list[dict[str, Any]],
    usable: list[dict[str, Any]],
) -> dict[str, Any]:
    relevant = [row for row in scored if row.get("relevant")]
    unreleased = [
        row
        for row in relevant
        if row.get("actual") is None
        and (row.get("consensus") is not None or row.get("previous") is not None)
    ]
    locked = [
        row
        for row in rows
        if str(row.get("actual_text") or "").strip().upper() == "LOCKED"
        or str(row.get("previous_text") or "").strip().upper() == "LOCKED"
        or str(row.get("consensus_text") or "").strip().upper() == "LOCKED"
    ]
    return {
        "total_usd_events": len(rows),
        "relevant_event_count": len(relevant),
        "usable_event_count": len(usable),
        "unreleased_event_count": len(unreleased),
        "locked_event_count": len(locked),
        "next_relevant_events": [
            {
                "event_name": row.get("event_name"),
                "local_time": " ".join(
                    str(part)
                    for part in (row.get("day"), row.get("time"))
                    if part
                ),
                "consensus": row.get("consensus_text"),
                "previous": row.get("previous_text"),
            }
            for row in relevant[:5]
        ],
    }


def _score_macro_event(row: dict[str, Any]) -> dict[str, Any]:
    actual = row.get("actual")
    consensus = row.get("consensus")
    event_name = str(row.get("event_name", ""))
    if actual is None or consensus is None or not row.get("relevant"):
        return {**row, "usable": False}
    raw_surprise = float(actual) - float(consensus)
    deviation = row.get("deviation")
    if deviation is None:
        denominator = max(abs(float(consensus)) * 0.25, 0.1)
        normalized = max(min(raw_surprise / denominator, 7.0), -7.0)
    else:
        normalized = max(min(float(deviation), 7.0), -7.0)
    direction_multiplier = _macro_event_direction_multiplier(event_name)
    importance_weight = _macro_event_importance_weight(event_name)
    hawkish_surprise = normalized * direction_multiplier
    weighted = hawkish_surprise * importance_weight
    return {
        **row,
        "usable": True,
        "raw_surprise": raw_surprise,
        "normalized_surprise": normalized,
        "direction_multiplier": direction_multiplier,
        "importance_weight": importance_weight,
        "weighted_surprise": weighted,
        "hawkish_dovish": "hawkish" if weighted > 0 else "dovish" if weighted < 0 else "neutral",
        "btc_impact_bias": "bearish" if weighted > 0 else "bullish" if weighted < 0 else "neutral",
    }


def _macro_event_direction_multiplier(event_name: str) -> float:
    name = event_name.lower()
    dovish_when_higher = [
        "unemployment rate",
        "jobless claims",
        "continuing claims",
        "layoffs",
    ]
    if any(keyword in name for keyword in dovish_when_higher):
        return -1.0
    return 1.0


def _macro_event_importance_weight(event_name: str) -> float:
    name = event_name.lower()
    high = [
        "consumer price index",
        "core consumer price index",
        "personal consumption expenditures",
        "nonfarm payrolls",
        "fed interest rate decision",
        "fomc",
        "retail sales",
        "ism",
    ]
    medium = [
        "pmi",
        "unemployment rate",
        "average hourly earnings",
        "jobless claims",
        "durable goods",
    ]
    if any(keyword in name for keyword in high):
        return 1.0
    if any(keyword in name for keyword in medium):
        return 0.65
    return 0.35


def _bitbo_metric_sample(
    source: SourceConfig,
    metric_id: str,
    export_data: dict[str, Any],
    value_column: str,
    quality: float,
) -> MetricSample:
    columns = export_data.get("columns") or []
    rows = export_data.get("data") or []
    if not columns or not rows:
        raise RuntimeError(f"Bitbo export data missing rows for {metric_id}")
    try:
        date_index = columns.index("Date")
        value_index = columns.index(value_column)
    except ValueError as exc:
        raise RuntimeError(f"Bitbo export data missing column {value_column}") from exc
    latest = rows[-1]
    ts = datetime.fromisoformat(str(latest[date_index])).replace(tzinfo=UTC)
    value = float(latest[value_index])
    return MetricSample(
        metric_id=metric_id,
        source_id=source.source_id,
        ts=ts,
        value=value,
        timeframe="1d",
        quality_score=quality,
    )


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(repr(sorted(payload.items())).encode("utf-8")).hexdigest()


def _parse_bitcoin_height(response: httpx.Response) -> int:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return int(response.json()["height"])
    return int(response.text.strip())


def _extract_tradingview_number(
    text: str,
    metadata: dict[str, Any],
    html: str | None = None,
) -> float:
    min_value = float(metadata.get("value_min", "-inf"))
    max_value = float(metadata.get("value_max", "inf"))
    symbol_label = str(metadata.get("symbol_label", "")).strip()
    search_text = text
    if symbol_label:
        index = text.upper().find(symbol_label.upper())
        if index >= 0:
            search_text = text[index : index + 600]
    number_pattern = (
        r"(?<![A-Za-z])[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?"
        r"|(?<![A-Za-z])[-+]?\d+\.\d+"
    )
    matches = re.findall(number_pattern, search_text)
    for match in matches:
        value = float(match.replace(",", ""))
        if min_value <= value <= max_value:
            return value
    if html:
        structured_value = _extract_tradingview_structured_price(
            html,
            min_value=min_value,
            max_value=max_value,
            symbol_label=symbol_label,
        )
        if structured_value is not None:
            return structured_value
    raise RuntimeError("Could not extract TradingView numeric quote from page text")


def _extract_tradingview_structured_price(
    html: str,
    *,
    min_value: float,
    max_value: float,
    symbol_label: str,
) -> float | None:
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for script in scripts:
        try:
            payload = json.loads(unescape(script).strip())
        except json.JSONDecodeError:
            continue
        for item in _iter_jsonld_items(payload):
            if not isinstance(item, dict):
                continue
            offers = item.get("offers")
            price = offers.get("price") if isinstance(offers, dict) else None
            if price is None:
                continue
            ticker = str(item.get("tickerSymbol") or item.get("name") or "")
            if symbol_label and ticker and symbol_label.upper() not in ticker.upper():
                identifiers = item.get("identifier") or []
                identifier_values = [
                    str(identifier.get("value", ""))
                    for identifier in identifiers
                    if isinstance(identifier, dict)
                ]
                if not any(symbol_label.upper() in value.upper() for value in identifier_values):
                    continue
            value = float(str(price).replace(",", ""))
            if min_value <= value <= max_value:
                return value
    return None


def _iter_jsonld_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
        return payload["@graph"]
    return [payload]


def _bitcoin_result(
    source: SourceConfig,
    height: int,
    raw_payload: dict[str, Any],
) -> CollectionResult:
    remaining = max(NEXT_HALVING_BLOCK - height, 0)
    return CollectionResult(
        source=source,
        raw=RawObservationData(source_id=source.source_id, payload=raw_payload),
        metrics=[
            MetricSample(metric_id="btc_block_height", source_id=source.source_id, value=height),
            MetricSample(
                metric_id="btc_halving_blocks_remaining",
                source_id=source.source_id,
                value=remaining,
            ),
            MetricSample(
                metric_id="btc_halving_estimated_days",
                source_id=source.source_id,
                value=remaining * 10 / 1440,
            ),
        ],
    )


def _mock_value(metric_id: str) -> float:
    values = {
        "dxy_proxy": 104.12,
        "real_yield_10y": 1.62,
        "btc_price": 108420.5,
        "exchange_spot_volume": 2_800_000_000.0,
        "ofr_fsi": -0.42,
        "treasury_2y": 4.09,
        "treasury_10y": 4.59,
        "treasury_30y": 5.12,
        "vix": 17.82,
        "fed_balance_sheet": 6_728_502,
        "bank_reserves": 3_102_810,
        "on_rrp": 7.193,
        "sofr": 3.53,
        "iorb": 3.65,
        "tga": 777_000.0,
        "breakeven_10y": 2.48,
        "nasdaq": 26_090.73,
        "sp500": 6800.12,
        "dow_jones": 46_200.5,
        "russell_2000": 2480.4,
        "gold": 3300.2,
        "wti_oil": 62.4,
        "brent_oil": 66.8,
        "btc_1h_open": 108_120.0,
        "btc_1h_high": 108_760.0,
        "btc_1h_low": 107_880.0,
        "btc_1h_close": 108_420.5,
        "btc_1h_volume": 1260.5,
        "btc_return_1h": 0.0028,
        "btc_return_4h": 0.0065,
        "btc_return_24h": 0.018,
        "btc_1h_return_pct": 0.0028,
        "btc_4h_return_pct": 0.0065,
        "btc_24h_return_pct": 0.018,
        "btc_price_vs_1h_close_pct": 0.0,
        "btc_drawdown_24h": -0.012,
        "btc_close_position_1h": 0.61,
        "btc_candle_body_pct_1h": 0.34,
        "btc_upper_wick_ratio_1h": 0.39,
        "btc_lower_wick_ratio_1h": 0.27,
        "btc_volume_zscore_1h": 0.7,
        "btc_breakdown_24h_low": 0.0,
        "btc_breakout_24h_high": 0.0,
        "btc_rebound_quality_1h": 0.18,
        "btc_down_volume_pressure": 0.0,
        "btc_return_5m": 0.0012,
        "btc_return_15m": 0.0021,
        "btc_close_position_5m": 0.58,
        "btc_close_position_15m": 0.62,
        "btc_range_expansion_z_5m": 0.35,
        "btc_range_expansion_z_15m": 0.42,
        "btc_volume_zscore_5m": 0.55,
        "btc_volume_zscore_15m": 0.68,
        "btc_flow_price_efficiency_5m": 0.0012,
        "btc_flow_price_efficiency_15m": 0.0021,
        "btc_funding_rate": 0.0001,
        "btc_funding_band": 0.0,
        "btc_open_interest": 88_000.0,
        "btc_oi_change_1h_pct": 0.0,
        "btc_oi_change_4h_pct": 0.0,
        "btc_oi_change_24h_pct": 0.0,
        "btc_oi_zscore": 0.0,
        "btc_global_long_account_ratio": 0.53,
        "btc_global_short_account_ratio": 0.47,
        "btc_global_long_short_account_ratio": 1.13,
        "btc_top_long_account_ratio": 0.54,
        "btc_top_short_account_ratio": 0.46,
        "btc_top_long_short_account_ratio": 1.17,
        "btc_top_long_position_ratio": 0.55,
        "btc_top_short_position_ratio": 0.45,
        "btc_top_long_short_position_ratio": 1.22,
        "taker_buy_sell_ratio": 1.08,
        "btc_halving_estimated_days": 1060.0,
        "futures_basis": 0.0002,
        "usdjpy": 158.69,
        "jgb_10y": 1.76,
        "usdcnh": 6.8092,
        "nikkei": 60_550.59,
        "topix": 3300.0,
        "hang_seng_tech": 4857.0,
        "hy_spread": 2.83,
        "ig_oas": 0.75,
        "active_addresses": 396_443.0,
        "transfer_volume_adjusted_usd": 14_000_000_000.0,
        "transaction_count": 605_313.0,
        "btc_hashrate": 750_000_000.0,
        "lightning_capacity_btc": 4_900.0,
        "lightning_channel_count": 72_000.0,
        "lightning_node_count": 15_000.0,
        "lightning_capacity_usd": 370_000_000.0,
        "lightning_tor_capacity_btc": 3_700.0,
        "lightning_tor_capacity_pct": 77.8,
        "lightning_tor_node_count": 5_400.0,
        "bitcoin_reachable_nodes": 23_800.0,
        "bitcoin_tor_nodes": 15_300.0,
        "bitcoin_tor_nodes_pct": 64.5,
        "mempool_tx_count": 3_400.0,
        "mempool_vsize_mb": 1.2,
        "mempool_blocks_to_clear": 2.0,
        "mempool_pending_fees_btc": 0.02,
        "mempool_min_fee_rate_sat_vb": 1.0,
        "hashrate_90d_ehs": 980.0,
        "hash_price_usd": 35.5,
        "avg_fees_per_block_btc": 0.02,
        "fees_vs_reward_pct": 0.51,
        "realized_price": 52_000.0,
        "cap_real_usd": 1_030_000_000_000.0,
        "supply_current": 19_800_000.0,
        "sth_cost_basis": 78_344.23,
        "lth_cost_basis": 48_646.66,
        "stablecoin_supply": 280_000_000_000.0,
        "stablecoin_buying_power_proxy": 1_200_000_000.0,
        "etf_net_flow": 120_000_000.0,
        "etf_flow_7d": 620_000_000.0,
        "exchange_netflow": -12_000.0,
        "exchange_balance_delta_1d_proxy": -12_000.0,
        "btc_dominance": 58.0,
        "btc_dominance_change_24h_pp": 0.15,
        "btc_dominance_change_3d_pp": 0.22,
        "total_market_cap": 3_800_000_000_000.0,
        "total2_market_cap": 1_600_000_000_000.0,
        "total_return_24h_pct": 0.012,
        "total2_return_24h_pct": 0.009,
        "total2_return_3d_pct": 0.026,
        "total2_vs_btc_return_24h_pct": -0.009,
        "eth_btc": 0.0275,
        "eth_btc_return_24h_pct": -0.002,
        "eth_btc_return_3d_pct": 0.006,
        "options_iv": 52.0,
        "options_rv": 44.0,
        "put_call_ratio": 0.82,
        "options_skew": 3.5,
        "gamma_wall_distance": 0.03,
        "gamma_wall_proxy_distance": 0.03,
        "max_pain_distance": -0.04,
        "options_expiry_notional": 12_000_000_000.0,
        "liquidation_long_usd": 2_000_000.0,
        "liquidation_short_usd": 1_600_000.0,
        "cpi_days_until": 21.0,
        "cpi_hours_until": 504.0,
        "fomc_days_until": 28.0,
        "fomc_hours_until": 672.0,
        "pce_days_until": 9.0,
        "pce_hours_until": 216.0,
        "nfp_days_until": 16.0,
        "nfp_hours_until": 384.0,
        "cpi_signed_days": 21.0,
        "fomc_signed_days": 28.0,
        "pce_signed_days": 9.0,
        "nfp_signed_days": 16.0,
        "macro_surprise_score": 0.35,
        "aggregate_macro_surprise": 0.18,
        "macro_surprise_event_count": 2.0,
        "next_fed_speech_hours_until": 36.0,
        "fed_speaker_weight": 3.0,
        "fed_speech_scheduled_risk": 0.32,
        "fed_speech_hawkish_score": 0.42,
        "fed_speech_dovish_score": 0.12,
        "fed_speech_content_risk": 0.33,
        "fed_speech_risk": 0.34,
        "fomc_blackout_active": 0.0,
        "fomc_event_risk": 0.14,
        "top50_strength": 0.58,
        "top50_advance_pct_24h": 0.58,
        "top50_advance_pct_3d": 0.04,
        "top50_ad_line_7d_slope": 0.08,
        "top50_equal_weight_return_24h_pct": 0.011,
        "top50_cap_weight_return_24h_pct": 0.014,
        "top50_equal_minus_cap_weight_return_24h_pct": -0.003,
        "sector_heat": 48.0,
        "sector_heat_change_24h": 3.0,
        "overheat_penalty": 0.0,
        "sopr": 1.01,
        "nupl": 0.32,
        "mvrv_zscore": 0.8,
    }
    return values.get(metric_id, 1.0)


def _binance_kline_result(source: SourceConfig, payload: list[list[Any]]) -> CollectionResult:
    closed_klines = payload[:-1] if len(payload) > 1 else payload
    kline = closed_klines[-1]
    ts = datetime.fromtimestamp(kline[6] / 1000, tz=UTC)
    suffix = str(source.metadata.get("kline_suffix") or "1h")
    timeframe = str(source.metadata.get("kline_interval") or suffix)
    values = _kline_derived_values(closed_klines, suffix=suffix)
    return CollectionResult(
        source=source,
        raw=RawObservationData(source_id=source.source_id, payload={"klines": payload}),
        metrics=[
            MetricSample(
                metric_id=metric_id,
                source_id=source.source_id,
                ts=ts,
                value=value,
                timeframe=timeframe,
                quality_score=0.96,
            )
            for metric_id, value in values.items()
        ],
    )


def _kline_derived_values(klines: list[list[Any]], suffix: str = "1h") -> dict[str, float]:
    latest = klines[-1]
    open_ = float(latest[1])
    high = float(latest[2])
    low = float(latest[3])
    close = float(latest[4])
    volume = float(latest[5])
    taker_buy_base_volume = float(latest[9]) if len(latest) > 9 else None
    closes = [float(kline[4]) for kline in klines]
    highs = [float(kline[2]) for kline in klines]
    lows = [float(kline[3]) for kline in klines]
    volumes = [float(kline[5]) for kline in klines]

    range_ = max(high - low, 0.0)
    close_position = (close - low) / range_ if range_ > 0 else 0.5
    body_pct = abs(close - open_) / range_ if range_ > 0 else 0.0
    upper_wick = (high - max(open_, close)) / range_ if range_ > 0 else 0.0
    lower_wick = (min(open_, close) - low) / range_ if range_ > 0 else 0.0

    prior_24h = klines[-25:-1] if len(klines) >= 25 else klines[:-1]
    prior_24h_high = max((float(kline[2]) for kline in prior_24h), default=high)
    prior_24h_low = min((float(kline[3]) for kline in prior_24h), default=low)
    volume_window = volumes[-21:-1] if len(volumes) >= 21 else volumes[:-1]
    volume_mean = statistics.mean(volume_window) if volume_window else volume
    volume_std = statistics.pstdev(volume_window) if len(volume_window) > 1 else 0.0
    volume_zscore = (volume - volume_mean) / volume_std if volume_std > 0 else 0.0
    ranges = [max(float(kline[2]) - float(kline[3]), 0.0) for kline in klines]
    range_window = ranges[-21:-1] if len(ranges) >= 21 else ranges[:-1]
    range_mean = statistics.mean(range_window) if range_window else range_
    range_std = statistics.pstdev(range_window) if len(range_window) > 1 else 0.0
    range_expansion_z = (range_ - range_mean) / range_std if range_std > 0 else 0.0

    return_1h = _safe_return(close, closes[-2] if len(closes) >= 2 else None)
    return_3 = _safe_return(close, closes[-4] if len(closes) >= 4 else None)
    return_5 = _safe_return(close, closes[-6] if len(closes) >= 6 else None)
    slope, slope_tstat = _linear_slope_tstat(closes[-12:])
    slope_acceleration = _safe_return(close, closes[-2] if len(closes) >= 2 else None) - _safe_return(
        closes[-2], closes[-3] if len(closes) >= 3 else None
    )
    net_taker_pressure = (
        (2.0 * taker_buy_base_volume / volume) - 1.0
        if taker_buy_base_volume is not None and volume > 0
        else None
    )
    taker_sell_volume = max(volume - (taker_buy_base_volume or 0.0), 0.0)
    taker_delta = (taker_buy_base_volume or 0.0) - taker_sell_volume
    taker_deltas = []
    taker_imbalances = []
    for row in klines:
        row_volume = float(row[5])
        row_taker_buy = float(row[9]) if len(row) > 9 else row_volume / 2.0
        row_delta = row_taker_buy - max(row_volume - row_taker_buy, 0.0)
        taker_deltas.append(row_delta)
        taker_imbalances.append(row_delta / row_volume if row_volume > 0 else 0.0)
    taker_imbalance = taker_delta / volume if volume > 0 else 0.0
    taker_imbalance_z_20 = _zscore_latest(taker_imbalances[-20:])
    taker_imbalance_z_60 = _zscore_latest(taker_imbalances[-60:])
    taker_imbalance_accel_3 = taker_imbalance - (
        statistics.mean(taker_imbalances[-4:-1]) if len(taker_imbalances) >= 4 else 0.0
    )
    taker_imbalance_persistence_5 = (
        sum(1 for value in taker_imbalances[-5:] if value > 0) / min(len(taker_imbalances), 5)
        if taker_imbalances
        else 0.0
    )
    flow_price_efficiency = (
        abs(return_1h) / abs(net_taker_pressure)
        if net_taker_pressure is not None and abs(net_taker_pressure) > 0
        else abs(return_1h)
    )
    return_4h = _safe_return(close, closes[-5] if len(closes) >= 5 else None)
    return_24h = _safe_return(close, closes[-25] if len(closes) >= 25 else None)
    high_24h = max(highs[-24:]) if highs else high
    drawdown_24h = (close / high_24h - 1.0) if high_24h > 0 else 0.0
    breakdown_24h_low = 1.0 if prior_24h and close < prior_24h_low else 0.0
    breakout_24h_high = 1.0 if prior_24h and close > prior_24h_high else 0.0
    rebound_quality = max(return_1h, 0.0) * max(close_position - 0.5, 0.0) * max(volume_zscore, 0.0)
    down_volume_pressure = max(-return_1h, 0.0) * max(volume_zscore, 0.0) * max(0.5 - close_position, 0.0)
    vwap = _window_vwap(klines)
    vwap_distance = (close / vwap - 1.0) if vwap > 0 else 0.0
    vwap_distance_history = []
    for idx in range(1, len(klines) + 1):
        window = klines[max(0, idx - min(len(klines), 12)) : idx]
        window_vwap = _window_vwap(window)
        window_close = float(klines[idx - 1][4])
        vwap_distance_history.append((window_close / window_vwap - 1.0) if window_vwap > 0 else 0.0)
    price_vs_vwap_z = _zscore_latest(vwap_distance_history)
    vwap_acceptance_duration = _vwap_acceptance_duration(closes, vwap_distance_history)
    flow_acceptance = _flow_price_acceptance(return_1h, taker_imbalance_z_60)
    local_high = max(highs[-12:]) if highs else high
    local_low = min(lows[-12:]) if lows else low
    prior_local = klines[-13:-1] if len(klines) >= 13 else klines[:-1]
    prior_local_high = max((float(row[2]) for row in prior_local), default=high)
    prior_local_low = min((float(row[3]) for row in prior_local), default=low)
    local_breakout = 1.0 if prior_local and high > prior_local_high else 0.0
    local_breakdown = 1.0 if prior_local and low < prior_local_low else 0.0
    false_breakout_score = 1.0 if local_breakout and close < prior_local_high and upper_wick >= 0.45 else 0.0
    false_breakdown_score = 1.0 if local_breakdown and close > prior_local_low and lower_wick >= 0.45 else 0.0
    returns = [
        _safe_return(current, previous)
        for previous, current in zip(closes, closes[1:], strict=False)
        if previous > 0
    ]
    rv = statistics.pstdev(returns[-12:]) if len(returns) >= 2 else 0.0
    rv_history = [
        statistics.pstdev(returns[max(0, idx - 12) : idx])
        for idx in range(2, len(returns) + 1)
        if len(returns[max(0, idx - 12) : idx]) >= 2
    ]
    rv_z = _zscore_for_value(rv_history, rv)
    atr = (statistics.mean(ranges[-14:]) / close) if len(ranges) >= 1 and close > 0 else 0.0
    volatility_regime_code = _volatility_regime_code(rv_z)
    expected_return = (
        0.0035 * taker_imbalance_z_60
        + 0.0020 * volume_zscore
        + 0.0025 * price_vs_vwap_z
        + 0.0020 * ((close_position - 0.5) * 2.0)
    )
    orderflow_residual = return_1h - expected_return
    residual_history = []
    for idx in range(2, len(closes)):
        row_return = _safe_return(closes[idx], closes[idx - 1])
        row_imbalance = taker_imbalances[idx] if idx < len(taker_imbalances) else 0.0
        row_expected = 0.0035 * row_imbalance
        residual_history.append(row_return - row_expected)
    orderflow_residual_z = _zscore_for_value(residual_history, orderflow_residual)
    return_z = return_1h / max(rv, 0.0001)
    agg_buy_volume = taker_buy_base_volume or volume / 2.0
    agg_sell_volume = max(volume - agg_buy_volume, 0.0)
    agg_flow_delta = agg_buy_volume - agg_sell_volume
    agg_flow_delta_z = _zscore_for_value(taker_deltas[:-1], agg_flow_delta)
    taker_buy_sell_ratio = agg_buy_volume / agg_sell_volume if agg_sell_volume > 0 else 2.0
    taker_flow_persistence = taker_imbalance_persistence_5 * 2.0 - 1.0
    price_impact_per_1m_buy = return_1h / max(agg_buy_volume / 1_000_000, 1.0) if agg_buy_volume > agg_sell_volume else 0.0
    price_impact_per_1m_sell = -return_1h / max(agg_sell_volume / 1_000_000, 1.0) if agg_sell_volume > agg_buy_volume else 0.0
    flow_absorption_score = 0.0
    flow_exhaustion_score = 0.0
    if taker_imbalance_z_60 >= 1.0 and return_1h <= 0:
        flow_absorption_score = min(100.0, taker_imbalance_z_60 * 35.0 + abs(return_z) * 15.0)
    if taker_imbalance_z_60 <= -1.0 and return_1h >= 0:
        flow_exhaustion_score = min(100.0, abs(taker_imbalance_z_60) * 35.0 + abs(return_z) * 15.0)
    spread_z = range_expansion_z
    depth_thinning_z = max(0.0, range_expansion_z) if volume_zscore <= 0 else max(0.0, range_expansion_z - volume_zscore * 0.35)
    liquidity_directional_score = max(-100.0, min(100.0, -35.0 * depth_thinning_z + 20.0 * (close_position - 0.5) * 2.0))
    price_acceptance_score = flow_acceptance * min(100.0, 35.0 + abs(taker_imbalance_z_60) * 25.0 + abs(return_z) * 15.0)
    structure_pressure_z = max(-2.5, min(2.5, 0.35 * taker_imbalance_z_60 + 0.25 * price_vs_vwap_z - 0.25 * depth_thinning_z + 0.15 * volume_zscore))
    expected_return_z = max(-2.5, min(2.5, 0.65 * structure_pressure_z))
    trade_structure_residual_z = return_z - expected_return_z
    spot_led_score = max(-100.0, min(100.0, 45.0 * volume_zscore + 35.0 * flow_acceptance + 20.0 * max(price_vs_vwap_z, -1.0)))
    perp_led_score = max(0.0, min(100.0, max(agg_flow_delta_z, 0.0) * 25.0 + max(volume_zscore, 0.0) * 20.0))
    volume_quality_score = max(-100.0, min(100.0, 45.0 * flow_acceptance + 25.0 * volume_zscore + 30.0 * (close_position - 0.5) * 2.0))
    leverage_participation_score = max(-100.0, min(100.0, 0.35 * spot_led_score + 0.25 * price_acceptance_score))
    leverage_crowding_risk_score = max(0.0, min(100.0, max(perp_led_score - max(spot_led_score, 0.0) * 0.35, 0.0)))
    liquidation_followthrough_score = max(-100.0, min(100.0, 70.0 * (1 if return_1h > 0 else -1 if return_1h < 0 else 0) * min(abs(return_z), 1.5) / 1.5))
    liquidation_absorption_score = max(flow_exhaustion_score, flow_absorption_score if return_1h >= 0 else 0.0)
    liquidation_cascade_score = max(0.0, min(100.0, -return_z * 35.0 + depth_thinning_z * 20.0)) if return_1h < 0 else 0.0
    squeeze_failure_score = max(0.0, min(100.0, flow_absorption_score + max(-trade_structure_residual_z, 0.0) * 20.0))
    trend_prior_score = _clamp((slope_tstat * 18.0) + (return_z * 20.0), -100.0, 100.0)
    trend_strength_z = _clamp(abs(slope_tstat) / 2.0 + abs(return_z) / 2.0, 0.0, 3.0)
    trend_confidence = _clamp(45.0 + trend_strength_z * 18.0 + abs(price_acceptance_score) * 0.15, 0.0, 100.0)
    trend_age_bars = min(
        float(
            sum(
                1
                for item in reversed(returns[-12:])
                if (item >= 0 and return_1h >= 0) or (item <= 0 and return_1h < 0)
            )
        ),
        12.0,
    )
    btc_response_z_15m = _clamp(return_5 / max(rv, 0.0001), -3.0, 3.0)
    btc_response_z_1h = _clamp(return_z, -3.0, 3.0)
    btc_response_z_4h = _clamp(return_4h / max(rv * 2.0, 0.0001), -3.0, 3.0)
    derivatives_pressure_z = _clamp(
        0.35 * structure_pressure_z
        + 0.25 * max(perp_led_score, 0.0) / 100.0
        + 0.20 * leverage_crowding_risk_score / 100.0
        + 0.20 * max(abs(agg_flow_delta_z), 0.0) / 2.5,
        -2.5,
        2.5,
    )
    derivatives_expected_return_z = _clamp(0.65 * derivatives_pressure_z, -2.5, 2.5)
    derivatives_residual_z = _clamp(return_z - derivatives_expected_return_z, -4.0, 4.0)
    derivatives_acceptance_score = _clamp(
        0.55 * price_acceptance_score + 0.30 * max(derivatives_residual_z, 0.0) * 35.0 + 0.15 * max(trend_prior_score, 0.0),
        -100.0,
        100.0,
    )
    derivatives_rejection_score = _clamp(
        0.45 * max(-price_acceptance_score, 0.0)
        + 0.35 * max(-derivatives_residual_z, 0.0) * 35.0
        + 0.20 * max(-trend_prior_score, 0.0),
        0.0,
        100.0,
    )
    basis_impulse_z_1h = _clamp(price_vs_vwap_z, -3.0, 3.0)
    perp_spot_premium_z = _clamp(max(perp_led_score - spot_led_score, -100.0) / 40.0, -3.0, 3.0)
    basis_acceptance_score = _clamp(price_acceptance_score - max(perp_spot_premium_z, 0.0) * 10.0, -100.0, 100.0)
    trade_v23_common = {
        f"trade_agg_buy_volume_{suffix}": agg_buy_volume,
        f"trade_agg_sell_volume_{suffix}": agg_sell_volume,
        f"trade_agg_flow_delta_{suffix}": agg_flow_delta,
        f"trade_agg_flow_delta_z_{suffix}": agg_flow_delta_z,
        f"trade_taker_buy_sell_ratio_{suffix}": taker_buy_sell_ratio,
        f"trade_taker_flow_persistence_{suffix}": taker_flow_persistence,
        f"trade_price_impact_per_1m_buy_{suffix}": price_impact_per_1m_buy,
        f"trade_price_impact_per_1m_sell_{suffix}": price_impact_per_1m_sell,
        f"trade_flow_absorption_score_{suffix}": flow_absorption_score,
        f"trade_flow_exhaustion_score_{suffix}": flow_exhaustion_score,
        f"trade_btc_return_z_{suffix}": return_z,
        f"trade_price_acceptance_score_{suffix}": price_acceptance_score,
        f"trade_spread_z_{suffix}": spread_z,
        f"trade_depth_thinning_z_{suffix}": depth_thinning_z,
        f"trade_liquidity_directional_score_{suffix}": liquidity_directional_score,
    }
    v22_common = {
        f"btc_return_3_{suffix}": return_3,
        f"btc_return_5_{suffix}": return_5,
        f"btc_slope_{suffix}": slope,
        f"btc_slope_tstat_{suffix}": slope_tstat,
        f"btc_slope_acceleration_{suffix}": slope_acceleration,
        f"btc_realized_vol_{suffix}": rv,
        f"btc_atr_14_{suffix}": atr,
        f"btc_volatility_regime_code_{suffix}": volatility_regime_code,
        f"btc_taker_delta_{suffix}": taker_delta,
        f"btc_taker_imbalance_{suffix}": taker_imbalance,
        f"btc_taker_imbalance_z_20_{suffix}": taker_imbalance_z_20,
        f"btc_taker_imbalance_z_60_{suffix}": taker_imbalance_z_60,
        f"btc_taker_imbalance_accel_3_{suffix}": taker_imbalance_accel_3,
        f"btc_taker_imbalance_persistence_5_{suffix}": taker_imbalance_persistence_5,
        f"btc_flow_price_acceptance_{suffix}": flow_acceptance,
        f"btc_vwap_{suffix}": vwap,
        f"btc_price_vs_vwap_z_{suffix}": price_vs_vwap_z,
        f"btc_vwap_acceptance_duration_{suffix}": vwap_acceptance_duration,
        f"btc_local_range_high_{suffix}": local_high,
        f"btc_local_range_low_{suffix}": local_low,
        f"btc_local_range_breakout_{suffix}": local_breakout,
        f"btc_local_range_breakdown_{suffix}": local_breakdown,
        f"btc_false_breakout_score_{suffix}": false_breakout_score,
        f"btc_false_breakdown_score_{suffix}": false_breakdown_score,
        f"btc_orderflow_expected_return_{suffix}": expected_return,
        f"btc_orderflow_residual_{suffix}": orderflow_residual,
        f"btc_orderflow_residual_z_60_{suffix}": orderflow_residual_z,
        f"btc_orderflow_residual_z_180_{suffix}": orderflow_residual_z,
    }

    if suffix != "1h":
        return {
            f"btc_return_{suffix}": return_1h,
            f"btc_close_position_{suffix}": close_position,
            f"btc_range_expansion_z_{suffix}": range_expansion_z,
            f"btc_volume_zscore_{suffix}": volume_zscore,
            f"btc_flow_price_efficiency_{suffix}": flow_price_efficiency,
            **v22_common,
            **trade_v23_common,
        }

    return {
        "btc_1h_open": open_,
        "btc_1h_high": high,
        "btc_1h_low": low,
        "btc_1h_close": close,
        "btc_1h_volume": volume,
        "btc_return_1h": return_1h,
        "btc_return_4h": return_4h,
        "btc_return_24h": return_24h,
        "btc_1h_return_pct": return_1h,
        "btc_4h_return_pct": return_4h,
        "btc_24h_return_pct": return_24h,
        "btc_price_vs_1h_close_pct": 0.0,
        "btc_drawdown_24h": drawdown_24h,
        "btc_close_position_1h": close_position,
        "btc_candle_body_pct_1h": body_pct,
        "btc_upper_wick_ratio_1h": upper_wick,
        "btc_lower_wick_ratio_1h": lower_wick,
        "btc_volume_zscore_1h": volume_zscore,
        "btc_breakdown_24h_low": breakdown_24h_low,
        "btc_breakout_24h_high": breakout_24h_high,
        "btc_rebound_quality_1h": rebound_quality,
        "btc_down_volume_pressure": down_volume_pressure,
        "btc_return_3m_proxy": return_3,
        "btc_return_5m_proxy": return_5,
        "btc_slope_tstat_1h": slope_tstat,
        "btc_slope_acceleration_15m_proxy": slope_acceleration,
        "btc_realized_vol_1h": rv,
        "btc_atr_14_15m_proxy": atr,
        "btc_volatility_regime_code": volatility_regime_code,
        "btc_taker_delta_1h": taker_delta,
        "btc_taker_imbalance_1h": taker_imbalance,
        "btc_taker_imbalance_z_20": taker_imbalance_z_20,
        "btc_taker_imbalance_z_60": taker_imbalance_z_60,
        "btc_taker_imbalance_accel_3": taker_imbalance_accel_3,
        "btc_taker_imbalance_persistence_5": taker_imbalance_persistence_5,
        "btc_flow_price_acceptance_1h": flow_acceptance,
        "btc_vwap_1h": vwap,
        "btc_price_vs_vwap_1h_z": price_vs_vwap_z,
        "btc_vwap_acceptance_duration_1m_proxy": vwap_acceptance_duration,
        "btc_micro_range_high_15m_proxy": max(highs[-4:]) if highs else high,
        "btc_micro_range_low_15m_proxy": min(lows[-4:]) if lows else low,
        "btc_local_range_high_1h": local_high,
        "btc_local_range_low_1h": local_low,
        "btc_major_range_high_4h": max(highs[-4:]) if highs else high,
        "btc_major_range_low_4h": min(lows[-4:]) if lows else low,
        "btc_micro_range_breakout_15m_proxy": 1.0 if high >= max(highs[-4:]) else 0.0,
        "btc_local_range_breakout_1h": local_breakout,
        "btc_major_range_breakout_4h": breakout_24h_high,
        "btc_local_range_breakdown_1h": local_breakdown,
        "btc_false_breakout_score": false_breakout_score,
        "btc_false_breakdown_score": false_breakdown_score,
        "btc_orderflow_expected_return_1h": expected_return,
        "btc_orderflow_residual_1h": orderflow_residual,
        "btc_orderflow_residual_z_60": orderflow_residual_z,
        "btc_orderflow_residual_z_180": orderflow_residual_z,
        "trade_btc_return_z_1h": return_z,
        "trade_structure_pressure_z": structure_pressure_z,
        "trade_expected_return_z": expected_return_z,
        "trade_structure_residual_z": trade_structure_residual_z,
        "trade_spot_led_score": spot_led_score,
        "trade_perp_led_score": perp_led_score,
        "trade_volume_quality_score": volume_quality_score,
        "trade_spot_perp_volume_ratio_z_60d": volume_zscore - max(agg_flow_delta_z, 0.0) * 0.25,
        "trade_leverage_participation_score": leverage_participation_score,
        "trade_leverage_crowding_risk_score": leverage_crowding_risk_score,
        "trade_liquidation_followthrough_score": liquidation_followthrough_score,
        "trade_liquidation_absorption_score": liquidation_absorption_score,
        "trade_liquidation_cascade_score": liquidation_cascade_score,
        "trade_squeeze_failure_score": squeeze_failure_score,
        "btc_trend_prior_score": trend_prior_score,
        "btc_trend_strength_z": trend_strength_z,
        "btc_trend_confidence": trend_confidence,
        "btc_trend_age_bars": trend_age_bars,
        "btc_response_z_15m": btc_response_z_15m,
        "btc_response_z_1h": btc_response_z_1h,
        "btc_response_z_4h": btc_response_z_4h,
        "derivatives_pressure_z": derivatives_pressure_z,
        "derivatives_expected_return_z": derivatives_expected_return_z,
        "derivatives_residual_z": derivatives_residual_z,
        "derivatives_acceptance_score": derivatives_acceptance_score,
        "derivatives_rejection_score": derivatives_rejection_score,
        "basis_impulse_z_1h": basis_impulse_z_1h,
        "perp_spot_premium_z": perp_spot_premium_z,
        "basis_acceptance_score": basis_acceptance_score,
    }


def _safe_return(current: float, previous: float | None) -> float:
    if previous is None or previous <= 0:
        return 0.0
    return current / previous - 1.0


def _zscore_latest(values: list[float]) -> float:
    if not values:
        return 0.0
    return _zscore_for_value(values[:-1], values[-1])


def _zscore_for_value(history: list[float], value: float) -> float:
    clean = [float(item) for item in history if math.isfinite(float(item))]
    if len(clean) < 2:
        return 0.0
    mean = statistics.mean(clean)
    std = statistics.pstdev(clean)
    return (float(value) - mean) / std if std > 0 else 0.0


def _linear_slope_tstat(values: list[float]) -> tuple[float, float]:
    if len(values) < 3:
        return 0.0, 0.0
    xs = list(range(len(values)))
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(values)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom <= 0:
        return 0.0, 0.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values, strict=False)) / denom
    residuals = [y - (y_mean + slope * (x - x_mean)) for x, y in zip(xs, values, strict=False)]
    if len(values) <= 2:
        return slope, 0.0
    residual_var = sum(item * item for item in residuals) / (len(values) - 2)
    slope_se = math.sqrt(residual_var / denom) if denom > 0 else 0.0
    tstat = slope / slope_se if slope_se > 0 else 0.0
    return slope / values[-1] if values[-1] else 0.0, tstat


def _window_vwap(klines: list[list[Any]]) -> float:
    numerator = 0.0
    denominator = 0.0
    for row in klines:
        high = float(row[2])
        low = float(row[3])
        close = float(row[4])
        volume = float(row[5])
        numerator += ((high + low + close) / 3.0) * volume
        denominator += volume
    return numerator / denominator if denominator > 0 else 0.0


def _vwap_acceptance_duration(closes: list[float], distances: list[float]) -> float:
    if not distances:
        return 0.0
    latest_sign = 1 if distances[-1] > 0 else -1 if distances[-1] < 0 else 0
    if latest_sign == 0:
        return 0.0
    count = 0
    for distance in reversed(distances):
        sign = 1 if distance > 0 else -1 if distance < 0 else 0
        if sign != latest_sign:
            break
        count += 1
    return float(count * latest_sign)


def _flow_price_acceptance(return_value: float, taker_imbalance_z: float) -> float:
    if abs(taker_imbalance_z) < 0.25 or abs(return_value) < 0.0001:
        return 0.0
    if return_value * taker_imbalance_z > 0:
        return 1.0 if return_value > 0 else -1.0
    return -1.0 if taker_imbalance_z > 0 else 1.0


def _volatility_regime_code(rv_z: float) -> float:
    if rv_z <= -0.8:
        return -1.0
    if rv_z >= 2.0:
        return 2.0
    if rv_z >= 1.0:
        return 1.0
    return 0.0


def _funding_band_value(value: float) -> float:
    if value >= 0.001:
        return 2.0
    if value >= 0.0003:
        return 1.0
    if value <= -0.0001:
        return -1.0
    return 0.0


def _binance_realized_volatility_result(
    source: SourceConfig,
    payload: list[list[Any]],
) -> CollectionResult:
    now = datetime.now(UTC)
    closed_payload = [
        kline
        for kline in payload
        if datetime.fromtimestamp(float(kline[6]) / 1000, tz=UTC) <= now
    ]
    usable_payload = closed_payload if len(closed_payload) >= 2 else payload
    closes = [float(kline[4]) for kline in usable_payload]
    returns = [
        math.log(current / previous)
        for previous, current in zip(closes, closes[1:], strict=False)
        if previous > 0 and current > 0
    ]
    realized_volatility = (
        statistics.stdev(returns) * math.sqrt(365) * 100 if len(returns) > 1 else 0.0
    )
    latest = usable_payload[-1]
    close_ts = datetime.fromtimestamp(float(latest[6]) / 1000, tz=UTC)
    open_ts = datetime.fromtimestamp(float(latest[0]) / 1000, tz=UTC)
    ts = close_ts if close_ts <= now else min(open_ts, now)
    return CollectionResult(
        source=source,
        raw=RawObservationData(source_id=source.source_id, payload={"klines": payload}),
        metrics=[
            MetricSample(
                metric_id="options_rv",
                source_id=source.source_id,
                ts=ts,
                value=realized_volatility,
                timeframe="30d",
                quality_score=0.92,
            )
        ],
    )


def _single_exchange_metric_result(
    source: SourceConfig,
    payload: dict[str, Any],
    metric_id: str,
    value: float,
    ts: datetime | None = None,
) -> CollectionResult:
    metric_kwargs: dict[str, Any] = {
        "metric_id": metric_id,
        "source_id": source.source_id,
        "value": value,
        "quality_score": 0.96,
    }
    if ts is not None:
        metric_kwargs["ts"] = ts
    return CollectionResult(
        source=source,
        raw=RawObservationData(source_id=source.source_id, payload=payload),
        metrics=[MetricSample(**metric_kwargs)],
    )


def _weighted_average(rows: list[dict[str, Any]], value_key: str, weight_key: str) -> float:
    weighted_sum = 0.0
    weight_sum = 0.0
    for item in rows:
        value = item.get(value_key)
        weight = float(item.get(weight_key) or 0)
        if value is None or weight <= 0:
            continue
        weighted_sum += float(value) * weight
        weight_sum += weight
    return weighted_sum / weight_sum if weight_sum else 0.0


def _first_positive(rows: list[dict[str, Any]], key: str) -> float:
    for item in rows:
        value = float(item.get(key) or 0)
        if value > 0:
            return value
    return 0.0


def _derive_options_positioning(rows: list[dict[str, Any]], spot: float) -> tuple[float, float]:
    if spot <= 0:
        return 0.0, 0.0
    strike_open_interest: dict[float, dict[str, float]] = {}
    for item in rows:
        strike = _option_strike(item.get("instrument_name", ""))
        if strike <= 0:
            continue
        side = "call" if str(item.get("instrument_name", "")).endswith("-C") else "put"
        open_interest = float(item.get("open_interest") or 0)
        bucket = strike_open_interest.setdefault(strike, {"call": 0.0, "put": 0.0})
        bucket[side] += open_interest
    if not strike_open_interest:
        return 0.0, 0.0
    max_pain_strike = min(
        strike_open_interest,
        key=lambda candidate: sum(
            exposure["call"] * max(0.0, candidate - strike)
            + exposure["put"] * max(0.0, strike - candidate)
            for strike, exposure in strike_open_interest.items()
        ),
    )
    gamma_wall_strike = max(
        strike_open_interest,
        key=lambda strike: (
            strike_open_interest[strike]["call"] + strike_open_interest[strike]["put"]
        ),
    )
    return (max_pain_strike - spot) / spot, (gamma_wall_strike - spot) / spot


def _option_strike(instrument_name: str) -> float:
    parts = instrument_name.split("-")
    if len(parts) < 4:
        return 0.0
    try:
        return float(parts[2])
    except ValueError:
        return 0.0


async def _capture_glassnode_series(
    source: SourceConfig,
    markers: dict[str, str],
) -> dict[str, dict[str, Any]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed; run `python -m playwright install chromium`"
        ) from exc

    captures: dict[str, dict[str, Any]] = {}
    artifact = paths.playwright_artifacts_dir / f"{source.source_id}-live.html"
    paths.ensure_directories()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        done = asyncio.Event()
        proxy_token: str | None = None

        async def handle_response(response: Any) -> None:
            nonlocal proxy_token
            for key, marker in markers.items():
                marker_path = marker.split("?", 1)[0]
                if key in captures or marker_path not in response.url:
                    continue
                request_headers = await response.request.all_headers()
                proxy_token = proxy_token or request_headers.get("x-proxy-token")
                try:
                    data = await response.json()
                except Exception as exc:  # noqa: BLE001
                    captures[key] = {
                        "url": response.url,
                        "status": response.status,
                        "error": repr(exc),
                        "series": [],
                    }
                    continue
                if isinstance(data, list):
                    captures[key] = {
                        "url": response.url,
                        "status": response.status,
                        "series": data,
                    }
                    if set(markers).issubset(captures):
                        done.set()

        page.on("response", lambda response: asyncio.create_task(handle_response(response)))
        await page.goto(source.url or "", wait_until="domcontentloaded", timeout=60_000)
        try:
            await asyncio.wait_for(done.wait(), timeout=10)
        except TimeoutError:
            for scroll_y in source.metadata.get(
                "scroll_points",
                [700, 1400, 2100, 2800, 3500, 4200, 5000],
            ):
                await page.evaluate("(y) => window.scrollTo(0, y)", scroll_y)
                try:
                    await asyncio.wait_for(done.wait(), timeout=2)
                    break
                except TimeoutError:
                    continue
        if proxy_token:
            await _fetch_missing_glassnode_series(page, markers, captures, proxy_token)
        html = await page.content()
        await browser.close()
    artifact.write_text(html, encoding="utf-8")
    missing = sorted(set(markers) - set(captures))
    if missing:
        raise RuntimeError(f"Glassnode public capture missing series: {', '.join(missing)}")
    for key, capture in captures.items():
        if not capture.get("series"):
            raise RuntimeError(f"Glassnode public capture returned no data for {key}")
        capture["artifact_path"] = str(artifact)
    return captures


async def _fetch_missing_glassnode_series(
    page: Any,
    markers: dict[str, str],
    captures: dict[str, dict[str, Any]],
    proxy_token: str,
) -> None:
    headers = {
        "x-proxy-token": proxy_token,
        "referer": page.url,
        "accept": "*/*",
    }
    for key, endpoint in markers.items():
        if key in captures:
            continue
        url = f"https://studio.glassnode.com{endpoint}"
        response = await page.context.request.get(url, headers=headers)
        try:
            data = await response.json()
        except Exception as exc:  # noqa: BLE001
            captures[key] = {
                "url": url,
                "status": response.status,
                "error": repr(exc),
                "series": [],
            }
            continue
        if isinstance(data, list):
            captures[key] = {
                "url": url,
                "status": response.status,
                "series": data,
                "used_proxy_token": True,
            }


def _latest_non_null_point(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    for point in reversed(series):
        if point.get("v") is not None:
            return point
    return None


def _previous_non_null_point(series: list[dict[str, Any]]) -> dict[str, Any] | None:
    found_latest = False
    for point in reversed(series):
        if point.get("v") is None:
            continue
        if found_latest:
            return point
        found_latest = True
    return None


def _latest_non_null_points(series: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    points = [point for point in reversed(series) if point.get("v") is not None]
    return list(reversed(points[:count]))


def _glassnode_capture_payload(captures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = {
        key: {
            "url": capture["url"],
            "status": capture["status"],
            "artifact_path": capture.get("artifact_path"),
            "sample_count": len(capture.get("series", [])),
            "latest": _latest_non_null_point(capture.get("series", [])),
        }
        for key, capture in captures.items()
    }
    payload["capture_diagnostics"] = {
        "browser_refreshed_at": datetime.now(UTC).isoformat(),
        "proxy_token_obtained": any(
            capture.get("used_proxy_token") for capture in captures.values()
        ),
        "endpoint_status_by_metric": {
            key: capture.get("status") for key, capture in captures.items()
        },
        "latest_point_by_metric": {
            key: _latest_non_null_point(capture.get("series", []))
            for key, capture in captures.items()
        },
    }
    return payload


def _write_playwright_artifact(source_id: str) -> Path:
    paths.ensure_directories()
    artifact = paths.playwright_artifacts_dir / f"{source_id}-mock.html"
    artifact.write_text("<html><body>mock playwright capture</body></html>", encoding="utf-8")
    return artifact
