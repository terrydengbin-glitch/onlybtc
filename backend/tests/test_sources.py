from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

import onlybtc.sources.clients as clients_module
import onlybtc.sources.service as source_service
from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.sources.clients import (
    NEXT_HALVING_BLOCK,
    BitcoinClient,
    PlaywrightClient,
    _extract_tradingview_number,
    _fallback_macro_calendar_metadata,
    _fomc_blackout_state,
    _binance_realized_volatility_result,
    _glassnode_capture_payload,
    _kline_derived_values,
    _parse_clarkmoody_dashboard,
    _parse_fed_rss,
    _parse_fxstreet_calendar_text,
    _score_fed_speech_event,
    _score_macro_event,
)
from onlybtc.sources.models import (
    CollectionResult,
    MetricSample,
    RawObservationData,
    SourceMode,
    SourceStatus,
)
from onlybtc.sources.registry import SOURCE_CONFIGS, get_source
from onlybtc.sources.service import (
    collect_sources,
    compute_business_recency,
    compute_freshness,
    ensure_source_registry,
    historical_window,
    persist_collection_result,
    reconcile_source_registry,
    source_health_summary,
    write_data_quality_snapshot,
)


async def test_collect_sources_mock_writes_standard_tables(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    result = await collect_sources(mode=SourceMode.MOCK, db=db)

    assert result["collected"] >= 5
    assert result["counts"]["sources"] >= 5
    assert result["counts"]["metric_values"] >= 5
    assert result["counts"]["source_health_events"] >= 5


async def test_collect_sources_run_id_links_standard_tables(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    result = await collect_sources(mode=SourceMode.MOCK, source_ids=["binance-btcusdt"], db=db)
    run_id = result["run_id"]

    assert run_id.startswith("collect-")
    assert result["data_quality"]["run_id"] == run_id
    with db.session() as session:
        assert session.scalar(
            select(schema.SourceRun).where(schema.SourceRun.run_id == run_id)
        )
        assert session.scalar(
            select(schema.RawObservation).where(schema.RawObservation.run_id == run_id)
        )
        assert session.scalar(
            select(schema.MetricValue).where(schema.MetricValue.run_id == run_id)
        )
        assert session.scalar(
            select(schema.DataQualitySnapshot).where(
                schema.DataQualitySnapshot.run_id == run_id
            )
        )
        source_run = session.scalar(
            select(schema.SourceRun).where(schema.SourceRun.run_id == run_id)
        )
        raw_observation = session.scalar(
            select(schema.RawObservation).where(schema.RawObservation.run_id == run_id)
        )
        metric_value = session.scalar(
            select(schema.MetricValue).where(schema.MetricValue.run_id == run_id)
        )

    assert source_run is not None
    assert source_run.mode == "mock"
    assert raw_observation is not None
    assert raw_observation.mode == "mock"
    assert metric_value is not None
    assert metric_value.run_mode == "mock"


async def test_collect_sources_writes_iorb_for_dollar_liquidity_v21(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    await collect_sources(mode=SourceMode.MOCK, source_ids=["fred-iorb"], db=db)

    with db.session() as session:
        iorb = session.scalar(
            select(schema.MetricValue).where(schema.MetricValue.metric_id == "iorb")
        )

    assert iorb is not None
    assert iorb.source_id == "fred-iorb"
    assert iorb.value == 3.65


async def test_dollar_liquidity_derived_source_is_not_collected_directly(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    result = await collect_sources(mode=SourceMode.MOCK, db=db)

    with db.session() as session:
        direct_rows = session.scalars(
            select(schema.MetricValue).where(
                schema.MetricValue.source_id == "dollar-liquidity-derived",
                schema.MetricValue.metric_id == "net_liquidity_proxy_bil",
                schema.MetricValue.value == 1.0,
            )
        ).all()
        source = session.scalar(
            select(schema.Source).where(schema.Source.source_id == "dollar-liquidity-derived")
        )

    assert source is not None
    assert source.metadata_json["collectable"] is False
    assert result["collect_gate"]["source_attempted_count"] < result["counts"]["sources"]
    assert direct_rows == []


async def test_collect_sources_retries_critical_source_and_records_attempts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    source = get_source("binance-btcusdt")
    attempts = {"count": 0}

    class FlakyClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def collect(self) -> CollectionResult:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise TimeoutError()
            return CollectionResult(
                source=source,
                raw=RawObservationData(
                    source_id=source.source_id,
                    payload={"ok": True},
                    status=SourceStatus.HEALTHY,
                    latency_ms=1,
                ),
                metrics=[
                    MetricSample(
                        metric_id="btc_price",
                        source_id=source.source_id,
                        value=100.0,
                    )
                ],
            )

    monkeypatch.setattr(source_service, "make_client", lambda *_args, **_kwargs: FlakyClient())

    result = await collect_sources(
        mode=SourceMode.LIVE,
        source_ids=["binance-btcusdt"],
        db=db,
    )

    assert attempts["count"] == 2
    assert result["errors"] == []
    assert result["collect_gate"]["collect_gate_status"] == "passed"
    with db.session() as session:
        raw = session.scalar(
            select(schema.RawObservation).where(
                schema.RawObservation.run_id == result["run_id"],
                schema.RawObservation.source_id == "binance-btcusdt",
            )
        )
    assert raw is not None
    assert raw.raw_payload["attempt_count"] == 2
    assert raw.raw_payload["collect_attempts"][0]["error_type"] == "TimeoutError"
    assert "empty exception message" in raw.raw_payload["collect_attempts"][0]["error_message"]


async def test_collect_sources_gate_fails_on_critical_source_error(tmp_path: Path, monkeypatch) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    source = get_source("binance-btcusdt")

    class BrokenClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def collect(self) -> CollectionResult:
            raise TimeoutError()

    monkeypatch.setattr(source_service, "make_client", lambda *_args, **_kwargs: BrokenClient())

    result = await collect_sources(
        mode=SourceMode.LIVE,
        source_ids=["binance-btcusdt"],
        db=db,
    )

    assert result["collect_gate"]["collect_gate_status"] == "failed"
    assert result["collect_gate"]["critical_source_failure_count"] == 1
    assert result["errors"][0]["error_type"] == "TimeoutError"
    assert "empty exception message" in result["errors"][0]["error"]
    with db.session() as session:
        snapshot = session.scalar(
            select(schema.DataQualitySnapshot).where(
                schema.DataQualitySnapshot.run_id == result["run_id"]
            )
        )
    assert snapshot is not None
    assert snapshot.payload["collect_gate"]["collect_gate_status"] == "failed"


async def test_fred_client_retries_api_504_then_succeeds(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, params=None):
            calls["count"] += 1
            request = clients_module.httpx.Request("GET", url)
            if calls["count"] == 1:
                return clients_module.httpx.Response(504, request=request, text="Gateway Time-out")
            return clients_module.httpx.Response(
                200,
                request=request,
                json={"observations": [{"date": "2026-05-28", "value": "4.52"}]},
            )

    monkeypatch.setattr(clients_module.httpx, "AsyncClient", FakeAsyncClient)
    client = clients_module.FredClient(get_source("fred-treasury-10y"), SourceMode.LIVE)
    client.settings.fred_api_key = "test-key"
    client.settings.source_fred_api_max_attempts = 3
    client.settings.source_fred_api_backoff_seconds = 0

    result = await client.collect()

    assert calls["count"] == 2
    assert result.raw.status == SourceStatus.HEALTHY
    assert result.raw.payload["retry_count"] == 1
    assert result.raw.payload["fallback_used"] is False
    assert result.raw.payload["api_attempts"][0]["http_status"] == 504
    assert result.metrics[0].value == pytest.approx(4.52)


async def test_fred_client_falls_back_to_fredgraph_csv(monkeypatch) -> None:
    calls: list[str] = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, params=None):
            calls.append(url)
            request = clients_module.httpx.Request("GET", url)
            if "series/observations" in url:
                return clients_module.httpx.Response(504, request=request, text="Gateway Time-out")
            return clients_module.httpx.Response(
                200,
                request=request,
                text="observation_date,DGS10\n2026-05-27,.\n2026-05-28,4.61\n",
            )

    monkeypatch.setattr(clients_module.httpx, "AsyncClient", FakeAsyncClient)
    client = clients_module.FredClient(get_source("fred-treasury-10y"), SourceMode.LIVE)
    client.settings.fred_api_key = "test-key"
    client.settings.source_fred_api_max_attempts = 1

    result = await client.collect()

    assert len(calls) == 2
    assert result.raw.status == SourceStatus.WARNING
    assert result.raw.payload["fallback_used"] is True
    assert result.raw.payload["fallback_provider"] == "fredgraph_csv"
    assert result.raw.payload["primary_error"].startswith("HTTPStatusError")
    assert result.metrics[0].is_fallback is True
    assert result.metrics[0].quality_score == pytest.approx(0.90)
    assert result.metrics[0].value == pytest.approx(4.61)


async def test_bitcoin_mock_halving_countdown() -> None:
    source = get_source("bitcoin-blockstream")

    result = await BitcoinClient(source, SourceMode.MOCK).collect()

    metrics = {item.metric_id: item.value for item in result.metrics}
    assert metrics["btc_block_height"] > 0
    assert (
        metrics["btc_halving_blocks_remaining"]
        == NEXT_HALVING_BLOCK - metrics["btc_block_height"]
    )
    assert metrics["btc_halving_estimated_days"] > 0


async def test_playwright_mock_writes_artifact() -> None:
    source = get_source("playwright-tradingview-dxy")

    result = await PlaywrightClient(source, SourceMode.MOCK).collect()

    assert result.raw.payload["artifact_path"].endswith(".html")


def test_tradingview_parser_uses_jsonld_price_fallback() -> None:
    html = """
    <script type="application/ld+json">{
      "@type": "FinancialProduct",
      "name": "S&P 500",
      "tickerSymbol": "SPX",
      "offers": {"@type": "Offer", "price": "7432.96", "priceCurrency": "USD"}
    }</script>
    """

    value = _extract_tradingview_number(
        "S&P 500 overview without a visible quote",
        {"symbol_label": "SPX", "value_min": 1000, "value_max": 10000},
        html=html,
    )

    assert value == 7432.96


def test_fallback_event_and_source_health(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    source = get_source("playwright-tradingview-dxy")
    result = CollectionResult(
        source=source,
        raw=RawObservationData(
            source_id=source.source_id,
            payload={"mock": True, "failure": "selector changed"},
            status=SourceStatus.WARNING,
            error_message="selector changed",
        ),
        metrics=[],
    )

    with db.session() as session:
        ensure_source_registry(session)
        persist_collection_result(session, result)

    with db.session() as session:
        fallback = session.scalar(select(schema.FallbackEvent))
        health = session.scalar(select(schema.SourceHealthEvent))

    assert fallback is not None
    assert fallback.fallback_source_id == "fred-dxy"
    assert health is not None
    assert health.status == "error"


async def test_historical_window_uses_metric_values(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, source_ids=["binance-btcusdt"], db=db)
    await collect_sources(mode=SourceMode.MOCK, source_ids=["binance-btcusdt"], db=db)

    window = historical_window("btc_price", run_mode="mock", db=db)

    assert window is not None
    assert window["metric_id"] == "btc_price"
    assert window["sample_count"] == 2
    assert window["previous"] is not None


async def test_historical_window_defaults_to_live_and_excludes_mock(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, source_ids=["binance-btcusdt"], db=db)

    live_window = historical_window("btc_price", db=db)
    all_window = historical_window("btc_price", run_mode="all", db=db)

    assert live_window is None
    assert all_window is not None
    assert all_window["run_mode"] == "mock"


async def test_p2_first_batch_mock_sources_write_metrics(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    await collect_sources(
        mode=SourceMode.MOCK,
        source_ids=[
            "fred-treasury-2y",
            "fred-vix",
            "fred-fed-balance-sheet",
            "binance-btcusdt-kline-1h",
            "binance-btcusdt-funding",
            "binance-btcusdt-open-interest",
            "bitcoin-blockstream",
        ],
        db=db,
    )

    metric_ids = {
        "treasury_2y",
        "vix",
        "fed_balance_sheet",
        "btc_1h_close",
        "btc_return_1h",
        "btc_1h_return_pct",
        "btc_4h_return_pct",
        "btc_24h_return_pct",
        "btc_price_vs_1h_close_pct",
        "btc_volume_zscore_1h",
        "btc_down_volume_pressure",
        "btc_funding_rate",
        "btc_funding_band",
        "btc_open_interest",
        "btc_oi_change_1h_pct",
        "btc_oi_change_4h_pct",
        "btc_oi_change_24h_pct",
        "btc_oi_zscore",
        "btc_halving_estimated_days",
    }
    with db.session() as session:
        rows = session.scalars(
            select(schema.MetricValue.metric_id).where(schema.MetricValue.metric_id.in_(metric_ids))
        ).all()

    assert metric_ids.issubset(set(rows))


def _kline_row(
    index: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    taker_buy_base_volume: float | None = None,
) -> list[object]:
    taker_buy = volume / 2 if taker_buy_base_volume is None else taker_buy_base_volume
    return [
        index,
        str(open_),
        str(high),
        str(low),
        str(close),
        str(volume),
        index * 60_000,
        str(volume * close),
        100,
        str(taker_buy),
        str(taker_buy * close),
        "0",
    ]


def test_short_kline_price_response_derived_values_normal_case() -> None:
    klines = [
        _kline_row(
            i,
            100 + i,
            102 + i + (i % 3) * 0.2,
            99 + i - (i % 2) * 0.1,
            101 + i,
            10 + i,
            5 + i * 0.2,
        )
        for i in range(1, 25)
    ]
    klines.append(_kline_row(25, 125, 132, 124, 131, 45, 31.5))

    values = _kline_derived_values(klines, suffix="5m")

    assert values["btc_return_5m"] > 0
    assert values["btc_close_position_5m"] == (131 - 124) / (132 - 124)
    assert values["btc_range_expansion_z_5m"] > 0
    assert values["btc_volume_zscore_5m"] > 0
    assert values["btc_flow_price_efficiency_5m"] > 0


def test_hourly_kline_derives_btc_total_state_price_aliases() -> None:
    klines = [
        _kline_row(i, 100 + i, 102 + i, 99 + i, 101 + i, 10 + i)
        for i in range(1, 25)
    ]
    klines.append(_kline_row(25, 125, 132, 124, 131, 45))

    values = _kline_derived_values(klines, suffix="1h")

    assert values["btc_1h_return_pct"] == values["btc_return_1h"]
    assert values["btc_4h_return_pct"] == values["btc_return_4h"]
    assert values["btc_24h_return_pct"] == values["btc_return_24h"]
    assert values["btc_price_vs_1h_close_pct"] == 0.0


def test_options_rv_uses_closed_daily_kline_timestamp() -> None:
    source = get_source("binance-btcusdt-kline-1d-rv")
    now = datetime.now(UTC)
    day_ms = 86_400_000
    today_open = datetime(now.year, now.month, now.day, tzinfo=UTC)
    start_ms = int((today_open - timedelta(days=31)).timestamp() * 1000)
    klines = []
    for index in range(31):
        open_ms = start_ms + index * day_ms
        close_ms = open_ms + day_ms - 1
        close = 100 + index
        klines.append([
            open_ms,
            str(close - 1),
            str(close + 1),
            str(close - 2),
            str(close),
            "10",
            close_ms,
            "1000",
            100,
            "5",
            "500",
            "0",
        ])
    current_open_ms = int(today_open.timestamp() * 1000)
    future_close_ms = current_open_ms + day_ms - 1
    klines.append([
        current_open_ms,
        "130",
        "140",
        "120",
        "135",
        "10",
        future_close_ms,
        "1000",
        100,
        "5",
        "500",
        "0",
    ])

    result = _binance_realized_volatility_result(source, klines)
    sample = result.metrics[0]

    assert sample.metric_id == "options_rv"
    assert sample.ts is not None
    assert sample.ts <= now
    assert sample.ts == datetime.fromtimestamp(float(klines[-2][6]) / 1000, tz=UTC)


def test_options_rv_uses_daily_closed_candle_freshness_policy() -> None:
    source = get_source("binance-btcusdt-kline-1d-rv")
    now = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)

    collection = compute_freshness(source, now - timedelta(hours=10), now)
    business = compute_business_recency(source, now - timedelta(hours=12), now)

    assert source.metadata["freshness_policy"]["cadence"] == "daily_closed_candle"
    assert collection["freshness_status"] == "fresh"
    assert collection["stale_after_minutes"] == 720.0
    assert business["business_recency_status"] == "current"


def test_short_kline_price_response_handles_flat_candle() -> None:
    klines = [_kline_row(i, 100, 100, 100, 100, 10) for i in range(1, 4)]

    values = _kline_derived_values(klines, suffix="15m")

    assert values["btc_return_15m"] == 0.0
    assert values["btc_close_position_15m"] == 0.5
    assert values["btc_range_expansion_z_15m"] == 0.0
    assert values["btc_volume_zscore_15m"] == 0.0


def test_short_kline_price_response_handles_missing_history_window() -> None:
    klines = [
        _kline_row(1, 100, 101, 99, 100, 10),
        _kline_row(2, 100, 103, 99, 102, 12, 8),
    ]

    values = _kline_derived_values(klines, suffix="5m")

    assert round(values["btc_return_5m"], 6) == 0.02
    assert values["btc_close_position_5m"] == 0.75
    assert values["btc_range_expansion_z_5m"] == 0.0
    assert values["btc_volume_zscore_5m"] == 0.0
    assert values["btc_flow_price_efficiency_5m"] > 0


async def test_p1_c42_short_kline_mock_sources_write_price_response_metrics(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    await collect_sources(
        mode=SourceMode.MOCK,
        source_ids=[
            "binance-btcusdt-kline-5m",
            "binance-btcusdt-kline-15m",
        ],
        db=db,
    )

    metric_ids = {
        "btc_return_5m",
        "btc_return_15m",
        "btc_close_position_5m",
        "btc_close_position_15m",
        "btc_range_expansion_z_5m",
        "btc_range_expansion_z_15m",
        "btc_volume_zscore_5m",
        "btc_volume_zscore_15m",
        "btc_flow_price_efficiency_5m",
        "btc_flow_price_efficiency_15m",
    }
    with db.session() as session:
        rows = session.scalars(
            select(schema.MetricValue.metric_id).where(schema.MetricValue.metric_id.in_(metric_ids))
        ).all()

    assert metric_ids.issubset(set(rows))
    windows = [
        historical_window(metric_id, run_mode="mock", historical_fallback=True, db=db)
        for metric_id in metric_ids
    ]
    assert all(window is not None for window in windows)
    assert all(window["source_ts"] for window in windows if window is not None)
    assert all(
        window["freshness_status"] in {"fresh", "stale", "expired"}
        for window in windows
        if window is not None
    )


def test_kline_partial_metric_chain_is_warned_at_persist(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.commit()
    source = get_source("binance-btcusdt-kline-1h")
    assert source is not None
    ts = datetime(2026, 5, 23, 8, tzinfo=UTC)
    result = CollectionResult(
        source=source,
        raw=RawObservationData(
            source_id=source.source_id,
            payload={
                "klines": [
                    [1, "100", "101", "99", "100", "10", 1],
                    [2, "100", "101", "99", "100", "10", 2],
                ]
            },
            status=SourceStatus.HEALTHY,
        ),
        metrics=[
            MetricSample(metric_id=metric_id, source_id=source.source_id, ts=ts, value=1.0)
            for metric_id in {
                "btc_1h_open",
                "btc_1h_high",
                "btc_1h_low",
                "btc_1h_close",
                "btc_1h_volume",
            }
        ],
    )

    with db.session() as session:
        persist_collection_result(session, result, run_id="collect-kline-partial", mode="live")
        session.commit()

    with db.session() as session:
        source_run = session.scalar(
            select(schema.SourceRun).where(
                schema.SourceRun.run_id == "collect-kline-partial",
                schema.SourceRun.source_id == source.source_id,
            )
        )
        metric_count = session.scalar(
            select(func.count(schema.MetricValue.id)).where(
                schema.MetricValue.run_id == "collect-kline-partial",
                schema.MetricValue.source_id == source.source_id,
            )
        )

    assert source_run is not None
    assert source_run.status == "warning"
    assert "insufficient_kline_metric_chain" in str(source_run.error_message)
    assert "btc_return_1h" in str(source_run.error_message)
    assert metric_count == 5


async def test_tradingview_macro_market_sources_write_mock_metrics(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    source_ids = [
        "playwright-tradingview-sp500",
        "playwright-tradingview-dow-jones",
        "playwright-tradingview-russell-2000",
        "playwright-tradingview-gold",
        "playwright-tradingview-wti-oil",
        "playwright-tradingview-brent-oil",
    ]

    await collect_sources(mode=SourceMode.MOCK, source_ids=source_ids, db=db)

    expected_metrics = {
        "sp500",
        "dow_jones",
        "russell_2000",
        "gold",
        "wti_oil",
        "brent_oil",
    }
    with db.session() as session:
        rows = session.scalars(
            select(schema.MetricValue.metric_id).where(
                schema.MetricValue.metric_id.in_(expected_metrics)
            )
        ).all()

    assert expected_metrics.issubset(set(rows))


def test_tradingview_macro_sources_have_realtime_policy_and_fallbacks() -> None:
    source_ids = {
        "playwright-tradingview-sp500": "fred-sp500",
        "playwright-tradingview-dow-jones": "fred-dow-jones",
        "playwright-tradingview-wti-oil": "fred-wti-oil",
        "playwright-tradingview-brent-oil": "fred-brent-oil",
    }

    for source_id, fallback_source_id in source_ids.items():
        source = get_source(source_id)

        assert source.fallback_source_id == fallback_source_id
        assert source.metadata["freshness_policy"]["cadence"] == "intraday"
        assert source.metadata["freshness_policy"]["expected_update_seconds"] == 600

    for source_id in [
        "fred-sp500",
        "fred-dow-jones",
        "fred-wti-oil",
        "fred-brent-oil",
    ]:
        assert get_source(source_id).method == "fred_api"


def test_binance_long_short_ratio_sources_are_registered() -> None:
    expected = {
        "binance-btcusdt-global-long-short-account-ratio": {
            "btc_global_long_account_ratio",
            "btc_global_short_account_ratio",
            "btc_global_long_short_account_ratio",
        },
        "binance-btcusdt-top-long-short-account-ratio": {
            "btc_top_long_account_ratio",
            "btc_top_short_account_ratio",
            "btc_top_long_short_account_ratio",
        },
        "binance-btcusdt-top-long-short-position-ratio": {
            "btc_top_long_position_ratio",
            "btc_top_short_position_ratio",
            "btc_top_long_short_position_ratio",
        },
    }

    for source_id, metric_ids in expected.items():
        source = get_source(source_id)
        assert source.group_name == "derivatives"
        assert set(source.metrics) == metric_ids
        assert source.metadata["freshness_policy"]["cadence"] == "intraday"



def test_source_health_summary(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    db.init_schema()
    with db.session() as session:
        session.add(
            schema.SourceHealthEvent(
                source_id="test-source",
                status="healthy",
                quality_score=0.9,
                latency_ms=100,
            )
        )

    summary = source_health_summary(db)

    assert summary["events"][0]["source_id"] == "test-source"


def test_compute_freshness_uses_source_refresh_policy() -> None:
    source = get_source("clarkmoody-dashboard")
    now = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)

    fresh = compute_freshness(source, datetime(2026, 5, 20, 11, 52, tzinfo=UTC), now)
    stale = compute_freshness(source, datetime(2026, 5, 20, 11, 40, tzinfo=UTC), now)
    expired = compute_freshness(source, datetime(2026, 5, 20, 10, 30, tzinfo=UTC), now)

    assert fresh["freshness_status"] == "fresh"
    assert stale["freshness_status"] == "stale"
    assert expired["freshness_status"] == "expired"


def test_ofr_and_glassnode_use_daily_business_recency_policy() -> None:
    ofr = get_source("ofr-fsi")
    glassnode = get_source("playwright-glassnode-sopr")
    now = datetime(2026, 5, 21, 12, 0, tzinfo=UTC)

    ofr_collection = compute_freshness(ofr, datetime(2026, 5, 20, 12, 0, tzinfo=UTC), now)
    ofr_business = compute_business_recency(
        ofr,
        datetime(2026, 5, 18, 0, 0, tzinfo=UTC),
        now,
    )
    glassnode_business = compute_business_recency(
        glassnode,
        datetime(2026, 5, 20, 0, 0, tzinfo=UTC),
        now,
    )

    assert ofr.metadata["freshness_policy"]["cadence"] == "official_daily"
    assert ofr_collection["freshness_status"] == "fresh"
    assert ofr_business["business_recency_status"] == "expected_lag"
    assert glassnode.metadata["freshness_policy"]["cadence"] == "page_snapshot_daily"
    assert glassnode_business["business_recency_status"] == "expected_lag"


def test_fx_proxy_business_recency_marks_provider_stale_suspect() -> None:
    usdjpy = get_source("fred-usdjpy")
    now = datetime(2026, 5, 25, 0, 0, tzinfo=UTC)

    result = compute_business_recency(
        usdjpy,
        datetime(2026, 5, 15, 0, 0, tzinfo=UTC),
        now,
    )

    assert result["business_recency_status"] == "provider_stale_suspect"


def test_macro_radar_yield_curve_change_uses_historical_2s10s_curve(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime(2026, 5, 26, 0, 0, tzinfo=UTC)
    previous = now - timedelta(days=1)
    current_10y = MetricSample(
        metric_id="treasury_10y",
        source_id="fred-treasury-10y",
        ts=now,
        value=4.60,
        quality_score=0.95,
    )
    with db.session() as session:
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="treasury_10y",
                    source_id="fred-treasury-10y",
                    run_id="collect-prev",
                    run_mode="test",
                    ts=previous,
                    value=4.50,
                ),
                schema.MetricValue(
                    metric_id="treasury_2y",
                    source_id="fred-treasury-2y",
                    run_id="collect-prev",
                    run_mode="test",
                    ts=previous,
                    value=4.05,
                ),
                schema.MetricValue(
                    metric_id="treasury_2y",
                    source_id="fred-treasury-2y",
                    run_id="collect-now",
                    run_mode="test",
                    ts=now,
                    value=4.10,
                ),
            ]
        )
        session.flush()

        derived = source_service._macro_radar_derived_samples(
            session,
            current_10y,
            SourceMode.TEST,
        )

    by_metric = {sample.metric_id: sample.value for sample in derived}
    assert by_metric["yield_curve_2s10s_change_bps"] == pytest.approx(5.0)


def test_macro_radar_yield_curve_change_skips_missing_previous_leg(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime(2026, 5, 26, 0, 0, tzinfo=UTC)
    current_10y = MetricSample(
        metric_id="treasury_10y",
        source_id="fred-treasury-10y",
        ts=now,
        value=4.60,
        quality_score=0.95,
    )
    with db.session() as session:
        session.add(
            schema.MetricValue(
                metric_id="treasury_2y",
                source_id="fred-treasury-2y",
                run_id="collect-now",
                run_mode="test",
                ts=now,
                value=4.10,
            )
        )
        session.flush()

        derived = source_service._macro_radar_derived_samples(
            session,
            current_10y,
            SourceMode.TEST,
        )

    assert "yield_curve_2s10s_change_bps" not in {
        sample.metric_id for sample in derived
    }


def test_treasury_credit_derived_metrics_include_curve_credit_and_btc_residual(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime(2026, 5, 26, 0, 0, tzinfo=UTC)
    previous = now - timedelta(days=1)
    with db.session() as session:
        session.add_all(
            [
                schema.MetricValue(metric_id="treasury_2y", source_id="fred-treasury-2y", run_id="prev", run_mode="test", ts=previous, value=4.00),
                schema.MetricValue(metric_id="treasury_10y", source_id="fred-treasury-10y", run_id="prev", run_mode="test", ts=previous, value=4.40),
                schema.MetricValue(metric_id="treasury_2y", source_id="fred-treasury-2y", run_id="now", run_mode="test", ts=now, value=4.08),
                schema.MetricValue(metric_id="treasury_10y", source_id="fred-treasury-10y", run_id="now", run_mode="test", ts=now, value=4.50),
                schema.MetricValue(metric_id="treasury_30y", source_id="fred-treasury-30y", run_id="now", run_mode="test", ts=now, value=4.80),
                schema.MetricValue(metric_id="real_yield_10y_change_1d_bps", source_id="treasury-credit-derived", run_id="now", run_mode="test", ts=now, value=5.0),
                schema.MetricValue(metric_id="nasdaq_return_24h_pct", source_id="macro-radar-derived", run_id="now", run_mode="test", ts=now, value=0.01),
                schema.MetricValue(metric_id="sp500_return_24h_pct", source_id="macro-radar-derived", run_id="now", run_mode="test", ts=now, value=0.004),
                schema.MetricValue(metric_id="dxy_change_24h_pct", source_id="macro-radar-derived", run_id="now", run_mode="test", ts=now, value=0.002),
                schema.MetricValue(metric_id="hy_oas_change_5d_bps", source_id="treasury-credit-derived", run_id="now", run_mode="test", ts=now, value=10.0),
                schema.MetricValue(metric_id="btc_return_24h", source_id="binance-btcusdt-kline-1h", run_id="now", run_mode="test", ts=now, value=0.012),
            ]
        )
        session.flush()

        treasury_samples = source_service._treasury_credit_derived_samples(
            session,
            MetricSample(
                metric_id="treasury_10y",
                source_id="fred-treasury-10y",
                ts=now,
                value=4.50,
                quality_score=0.95,
            ),
            SourceMode.TEST,
        )
        btc_samples = source_service._treasury_credit_derived_samples(
            session,
            MetricSample(
                metric_id="btc_return_24h",
                source_id="binance-btcusdt-kline-1h",
                ts=now,
                value=0.012,
                quality_score=0.95,
            ),
            SourceMode.TEST,
        )

    by_metric = {sample.metric_id: sample.value for sample in [*treasury_samples, *btc_samples]}
    assert by_metric["treasury_10y_change_1d_bps"] == pytest.approx(10.0)
    assert by_metric["yield_curve_2s10s_bps"] == pytest.approx(42.0)
    assert by_metric["curve_2s10s_change_1d_bps"] == pytest.approx(2.0)
    assert "btc_residual_24h" in by_metric
    assert "btc_vs_credit_residual_3d" in by_metric


def test_fund_flow_derived_metrics_include_flow_supply_and_btc_residual(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime(2026, 5, 26, 0, 0, tzinfo=UTC)
    with db.session() as session:
        rows: list[schema.MetricValue] = []
        etf_values = [120_000_000.0, 90_000_000.0, -40_000_000.0, 150_000_000.0]
        for days_ago, value in enumerate(reversed(etf_values)):
            rows.append(
                schema.MetricValue(
                    metric_id="etf_net_flow",
                    source_id="coinglass-etf-flow",
                    run_id=f"etf-{days_ago}",
                    run_mode="test",
                    ts=now - timedelta(days=days_ago),
                    value=value,
                )
            )
        rows.append(
            schema.MetricValue(
                metric_id="etf_net_flow",
                source_id="farside-etf-flow",
                run_id="etf-cross",
                run_mode="test",
                ts=now,
                value=135_000_000.0,
            )
        )
        rows.extend(
            [
                schema.MetricValue(metric_id="stablecoin_supply", source_id="defillama-stablecoins", run_id="stable-30d", run_mode="test", ts=now - timedelta(days=30), value=180_000_000_000.0),
                schema.MetricValue(metric_id="stablecoin_supply", source_id="defillama-stablecoins", run_id="stable-prev", run_mode="test", ts=now - timedelta(days=7), value=190_000_000_000.0),
                schema.MetricValue(metric_id="stablecoin_supply", source_id="defillama-stablecoins", run_id="stable-now", run_mode="test", ts=now, value=200_000_000_000.0),
                schema.MetricValue(metric_id="btc_price", source_id="binance-btcusdt", run_id="btc", run_mode="test", ts=now, value=100_000.0),
                schema.MetricValue(metric_id="supply_current", source_id="blockchaincom-supply", run_id="supply", run_mode="test", ts=now, value=19_800_000.0),
                schema.MetricValue(metric_id="exchange_balance_delta_1d_proxy", source_id="glassnode-exchange-balance", run_id="ex-prev", run_mode="test", ts=now - timedelta(days=1), value=400.0),
                schema.MetricValue(metric_id="exchange_balance_delta_1d_proxy", source_id="glassnode-exchange-balance", run_id="ex-now", run_mode="test", ts=now, value=1_000.0),
                schema.MetricValue(metric_id="btc_return_4h", source_id="binance-btcusdt-kline-1h", run_id="ret4h", run_mode="test", ts=now, value=0.01),
                schema.MetricValue(metric_id="btc_return_24h", source_id="binance-btcusdt-kline-1h", run_id="ret24h", run_mode="test", ts=now, value=0.025),
                schema.MetricValue(metric_id="exchange_spot_volume", source_id="binance-btcusdt", run_id="vol", run_mode="test", ts=now, value=5_000_000_000.0),
            ]
        )
        session.add_all(rows)
        session.flush()

        etf_samples = source_service._fund_flow_derived_samples(
            session,
            MetricSample(
                metric_id="etf_net_flow",
                source_id="coinglass-etf-flow",
                ts=now,
                value=150_000_000.0,
                quality_score=0.95,
            ),
            SourceMode.TEST,
        )
        session.add_all(
            [
                schema.MetricValue(
                    metric_id=sample.metric_id,
                    source_id=sample.source_id,
                    run_id="derived-etf",
                    run_mode="test",
                    ts=sample.ts,
                    value=sample.value,
                )
                for sample in etf_samples
            ]
        )
        stable_samples = source_service._fund_flow_derived_samples(
            session,
            MetricSample(
                metric_id="stablecoin_supply",
                source_id="defillama-stablecoins",
                ts=now,
                value=200_000_000_000.0,
                quality_score=0.95,
            ),
            SourceMode.TEST,
        )
        exchange_samples = source_service._fund_flow_derived_samples(
            session,
            MetricSample(
                metric_id="exchange_balance_delta_1d_proxy",
                source_id="glassnode-exchange-balance",
                ts=now,
                value=1_000.0,
                quality_score=0.90,
            ),
            SourceMode.TEST,
        )
        session.add_all(
            [
                schema.MetricValue(
                    metric_id=sample.metric_id,
                    source_id=sample.source_id,
                    run_id="derived-context",
                    run_mode="test",
                    ts=sample.ts,
                    value=sample.value,
                )
                for sample in [*stable_samples, *exchange_samples]
            ]
        )
        session.flush()
        btc_samples = source_service._fund_flow_derived_samples(
            session,
            MetricSample(
                metric_id="btc_return_24h",
                source_id="binance-btcusdt-kline-1h",
                ts=now,
                value=0.025,
                quality_score=0.95,
            ),
            SourceMode.TEST,
        )

    by_metric = {
        sample.metric_id: sample.value
        for sample in [*etf_samples, *stable_samples, *exchange_samples, *btc_samples]
    }
    assert by_metric["etf_flow_3d_usd"] == pytest.approx(200_000_000.0)
    assert by_metric["etf_inflow_streak_days"] == pytest.approx(1.0)
    assert by_metric["etf_flow_data_source_count"] == pytest.approx(2.0)
    assert by_metric["stablecoin_liquidity_regime"] == pytest.approx(1.0)
    assert by_metric["ssr"] == pytest.approx(9.9)
    assert abs(by_metric["stablecoin_mcap_change_7d_z_120d"]) < 10.0
    assert by_metric["btc_exchange_netflow_7d"] == pytest.approx(1_400.0)
    assert "fund_flow_expected_return_24h" in by_metric
    assert "fund_flow_residual_24h" in by_metric
    assert abs(by_metric["fund_flow_expected_return_24h"]) <= 0.08


def test_glassnode_capture_payload_includes_capture_diagnostics() -> None:
    payload = _glassnode_capture_payload(
        {
            "sopr": {
                "url": "https://studio.glassnode.com/v1/metrics/indicators/sopr",
                "status": 200,
                "artifact_path": "glassnode.html",
                "used_proxy_token": True,
                "series": [{"t": 1, "v": 0.99}, {"t": 2, "v": 1.01}],
            }
        }
    )

    assert payload["sopr"]["sample_count"] == 2
    assert payload["capture_diagnostics"]["proxy_token_obtained"] is True
    assert payload["capture_diagnostics"]["endpoint_status_by_metric"]["sopr"] == 200
    assert payload["capture_diagnostics"]["latest_point_by_metric"]["sopr"]["v"] == 1.01


async def test_collect_sources_writes_data_quality_snapshot(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    result = await collect_sources(mode=SourceMode.MOCK, source_ids=["binance-btcusdt"], db=db)

    assert result["data_quality"]["status"] in {"healthy", "warning", "critical"}
    with db.session() as session:
        snapshot = session.scalar(select(schema.DataQualitySnapshot))

    assert snapshot is not None
    assert "freshness_counts" in snapshot.payload


def test_data_quality_run_mode_summary_does_not_block_clean_current_run_with_mixed_history(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime(2026, 6, 23, 12, 0, tzinfo=UTC)

    with db.session() as session:
        session.add_all(
            [
                _metric_value("btc_price", "collect-current", "live", now, 100.0),
                _metric_value("btc_price", "collect-history", "mock", now, 99.0),
            ]
        )
        session.flush()
        result = write_data_quality_snapshot(session, run_id="collect-current")

    summary = result["payload"]["run_mode_summary"]

    assert summary["production_blocker"] is False
    assert summary["current_run"]["production_blocker"] is False
    assert summary["current_run"]["mock_metric_values"] == 0
    assert summary["history"]["mock_metric_values"] == 1
    assert summary["history_contamination_warning"] is True
    assert "btc_price" in summary["history"]["mixed_metric_ids"]


def test_data_quality_run_mode_summary_blocks_current_run_mixing(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    now = datetime(2026, 6, 23, 12, 0, tzinfo=UTC)

    with db.session() as session:
        session.add_all(
            [
                _metric_value("btc_price", "collect-current", "live", now, 100.0),
                _metric_value("btc_price", "collect-current", "mock", now, 99.0),
            ]
        )
        session.flush()
        result = write_data_quality_snapshot(session, run_id="collect-current")

    summary = result["payload"]["run_mode_summary"]

    assert summary["production_blocker"] is True
    assert summary["current_run"]["production_blocker"] is True
    assert summary["current_run"]["mock_metric_values"] == 1
    assert summary["current_run_mixed_metric_ids"] == ["btc_price"]


def test_reconcile_source_registry_archives_removed_sources(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    with db.session() as session:
        ensure_source_registry(session)
        session.add(
            schema.Source(
                source_id="old-source",
                name="Old source",
                group_name="legacy",
                method="legacy",
                status="healthy",
                metadata_json={},
            )
        )
        session.flush()
        archived = reconcile_source_registry(session)

    assert "old-source" in archived
    with db.session() as session:
        source = session.scalar(
            select(schema.Source).where(schema.Source.source_id == "old-source")
        )
        health = session.scalar(
            select(schema.SourceHealthEvent).where(
                schema.SourceHealthEvent.source_id == "old-source"
            )
        )

    assert source is not None
    assert source.status == "archived"
    assert source.metadata_json["archived"] is True
    assert health is not None
    assert health.status == "archived"


def _metric_value(
    metric_id: str,
    run_id: str,
    run_mode: str,
    ts: datetime,
    value: float,
) -> schema.MetricValue:
    return schema.MetricValue(
        metric_id=metric_id,
        source_id="binance-btcusdt",
        run_id=run_id,
        run_mode=run_mode,
        ts=ts,
        timeframe="spot",
        value=value,
        quality_score=1.0,
    )


def test_data_quality_snapshot_excludes_archived_sources(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()

    with db.session() as session:
        ensure_source_registry(session)
        session.add(
            schema.Source(
                source_id="old-source",
                name="Old source",
                group_name="legacy",
                method="legacy",
                status="archived",
                metadata_json={"archived": True},
            )
        )
        session.flush()
        snapshot = write_data_quality_snapshot(session, run_id="dq-test")

    assert snapshot["payload"]["registry_drift_count"] == 1
    assert "old-source" in snapshot["payload"]["archived_sources"]
    collectable_source_count = sum(
        1 for source in SOURCE_CONFIGS if source.metadata.get("collectable", True)
    )
    assert snapshot["payload"]["source_count"] == collectable_source_count


async def test_historical_window_returns_freshness_fields(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    await collect_sources(mode=SourceMode.MOCK, source_ids=["binance-btcusdt"], db=db)
    window = historical_window("btc_price", run_mode="mock", db=db)

    assert window is not None
    assert window["freshness_status"] in {"fresh", "stale", "expired"}
    assert window["collection_freshness_status"] in {"fresh", "stale", "expired"}
    assert window["business_recency_status"] in {
        "current",
        "expected_lag",
        "lagging",
        "outdated",
        "unknown",
    }
    assert window["observed_at"] is not None
    assert window["collected_at"] is not None
    assert window["effective_quality_score"] is not None


def test_historical_window_arbitrates_sources_without_mixing(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="mempool-lightning-network-stats",
                    run_id="collect-test-mempool",
                    ts=now - timedelta(minutes=2),
                    value=4920.0,
                    quality_score=0.55,
                ),
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="mempool-lightning-network-stats",
                    run_id="collect-test-mempool",
                    ts=now - timedelta(minutes=1),
                    value=4925.0,
                    previous_value=4920.0,
                    change_24h=0.001,
                    quality_score=0.55,
                ),
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="clarkmoody-dashboard",
                    run_id="collect-test-clark",
                    ts=now - timedelta(minutes=2),
                    value=4770.0,
                    quality_score=0.84,
                ),
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="clarkmoody-dashboard",
                    run_id="collect-test-clark",
                    ts=now - timedelta(minutes=1),
                    value=4775.0,
                    previous_value=4770.0,
                    change_24h=0.001,
                    quality_score=0.84,
                ),
            ]
        )

    window = historical_window("lightning_capacity_btc", db=db)

    assert window is not None
    assert window["source_id"] == "mempool-lightning-network-stats"
    assert window["sample_count"] == 2
    candidates = {item["source_id"]: item for item in window["candidates"]}
    assert set(candidates) == {
        "clarkmoody-dashboard",
        "mempool-lightning-network-stats",
    }
    assert candidates["mempool-lightning-network-stats"]["role"] == "selected"
    assert candidates["clarkmoody-dashboard"]["role"] == "fallback"
    assert window["conflict"]["detected"] is False
    assert window["conflict"]["suppressed_items"][0]["severity"] == "low"
    assert window["conflict"]["suppressed_items"][0]["type"] == "definition_conflict"
    assert (
        window["conflict"]["suppressed_items"][0]["suppressed_reason"]
        == "definition_variant_cross_check"
    )


def test_historical_window_prefers_tradingview_realtime_over_fred_daily(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="sp500",
                    source_id="playwright-tradingview-sp500",
                    run_id="collect-test-tv",
                    ts=now - timedelta(minutes=1),
                    value=6800.0,
                    quality_score=0.78,
                ),
                schema.MetricValue(
                    metric_id="sp500",
                    source_id="fred-sp500",
                    run_id="collect-test-fred",
                    ts=now.replace(hour=0, minute=0, second=0, microsecond=0),
                    value=6720.0,
                    quality_score=0.95,
                ),
            ]
        )

    window = historical_window("sp500", db=db)

    assert window is not None
    assert window["source_id"] == "playwright-tradingview-sp500"
    assert window["freshness_policy"]["cadence"] == "intraday"
    candidates = {item["source_id"]: item for item in window["candidates"]}
    assert candidates["playwright-tradingview-sp500"]["role"] == "selected"
    assert candidates["fred-sp500"]["role"] in {"fallback", "cross_check"}


def test_historical_window_uses_priority_when_quality_ties(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="mempool-lightning-network-stats",
                    ts=now - timedelta(minutes=1),
                    value=4925.0,
                    quality_score=0.84,
                ),
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="clarkmoody-dashboard",
                    ts=now - timedelta(minutes=1),
                    value=4775.0,
                    quality_score=0.84,
                ),
            ]
        )

    window = historical_window("lightning_capacity_btc", db=db)

    assert window is not None
    assert window["source_id"] == "mempool-lightning-network-stats"


def test_historical_window_falls_back_when_primary_is_stale(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="mempool-lightning-network-stats",
                    ts=now - timedelta(minutes=20),
                    created_at=now - timedelta(hours=2),
                    updated_at=now - timedelta(hours=2),
                    value=4925.0,
                    quality_score=0.95,
                ),
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="clarkmoody-dashboard",
                    ts=now - timedelta(minutes=1),
                    value=4775.0,
                    quality_score=0.84,
                ),
            ]
        )

    window = historical_window("lightning_capacity_btc", db=db)

    assert window is not None
    assert window["source_id"] == "clarkmoody-dashboard"
    assert window["freshness_status"] == "fresh"


def test_historical_window_source_id_returns_specific_source(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="mempool-lightning-network-stats",
                    ts=now - timedelta(minutes=1),
                    value=4925.0,
                    quality_score=0.55,
                ),
                schema.MetricValue(
                    metric_id="lightning_capacity_btc",
                    source_id="clarkmoody-dashboard",
                    ts=now - timedelta(minutes=1),
                    value=4775.0,
                    quality_score=0.84,
                ),
            ]
        )

    window = historical_window(
        "lightning_capacity_btc",
        source_id="mempool-lightning-network-stats",
        db=db,
    )

    assert window is not None
    assert window["source_id"] == "mempool-lightning-network-stats"
    assert window["current"] == 4925.0
    assert window["candidates"] == []


def test_historical_window_collect_run_value_wins_over_newer_old_row(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        ensure_source_registry(session)
        session.add_all(
            [
                schema.MetricValue(
                    metric_id="net_liquidity_proxy_bil",
                    source_id="dollar-liquidity-derived",
                    run_id="collect-current",
                    run_mode="live",
                    ts=now - timedelta(days=6),
                    value=5930.699,
                    quality_score=0.9,
                ),
                schema.MetricValue(
                    metric_id="net_liquidity_proxy_bil",
                    source_id="dollar-liquidity-derived",
                    run_id="collect-polluted-old",
                    run_mode="live",
                    ts=now - timedelta(minutes=5),
                    value=1.0,
                    quality_score=0.9,
                ),
                schema.MetricValue(
                    metric_id="net_liquidity_proxy_bil",
                    source_id="dollar-liquidity-derived",
                    run_id="collect-history",
                    run_mode="live",
                    ts=now - timedelta(days=13),
                    value=5900.0,
                    quality_score=0.9,
                ),
            ]
        )

    window = historical_window(
        "net_liquidity_proxy_bil",
        run_mode="live",
        collect_run_id="collect-current",
        db=db,
    )

    assert window is not None
    assert window["source_id"] == "dollar-liquidity-derived"
    assert window["current"] == 5930.699
    assert window["source_run_id"] == "collect-current"
    assert window["feature_run_scope"] == "current_run"
    assert window["current_run_has_value"] is True


def test_fxstreet_calendar_parser_scores_hawkish_cpi() -> None:
    text = """
Time\tEvent\tImpact\tActual\tDev\tConsensus\tPrevious
WEDNESDAY, MAY 20
8:30 AM
USD\tConsumer Price Index (MoM) (Apr)
0.4%\t1.25\t0.3%\t0.2%
8:30 AM
USD\tUnemployment Rate (Apr)
4.3%\t1.00\t4.0%\t4.1%
"""
    rows = _parse_fxstreet_calendar_text(
        text,
        {
            "country_codes": ["USD"],
            "event_keywords": ["consumer price index", "unemployment rate"],
        },
    )
    scored = [_score_macro_event(row) for row in rows]

    assert scored[0]["usable"] is True
    assert scored[0]["weighted_surprise"] > 0
    assert scored[0]["btc_impact_bias"] == "bearish"
    assert scored[1]["usable"] is True
    assert scored[1]["weighted_surprise"] < 0
    assert scored[1]["btc_impact_bias"] == "bullish"


def test_macro_calendar_fallback_metadata_is_versioned() -> None:
    bls_urls = get_source("official-macro-event-calendar").metadata["urls"]["bls"]
    metadata = _fallback_macro_calendar_metadata(date(2026, 5, 21))

    assert isinstance(bls_urls, list)
    assert any("{year}" in url for url in bls_urls)
    assert metadata["year"] == 2026
    assert metadata["expires_at"] == "2026-12-31"
    assert metadata["expired"] is False


async def test_bls_403_is_optional_when_embedded_fallback_covers_events(monkeypatch) -> None:
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str):
            request = clients_module.httpx.Request("GET", url)
            if "bls.gov" in url:
                return clients_module.httpx.Response(403, request=request, text="Forbidden")
            if "federalreserve.gov" in url:
                return clients_module.httpx.Response(
                    200,
                    request=request,
                    text="June 16-17, 2026",
                )
            if "bea.gov" in url:
                return clients_module.httpx.Response(
                    200,
                    request=request,
                    text="Personal Income and Outlays June 26, 2026",
                )
            return clients_module.httpx.Response(404, request=request)

    monkeypatch.setattr(clients_module.httpx, "AsyncClient", FakeAsyncClient)

    client = clients_module.OfficialClient(
        get_source("official-macro-event-calendar"),
        SourceMode.LIVE,
    )
    result = await client._collect_macro_event_calendar()

    metric_ids = {metric.metric_id for metric in result.metrics}
    bls_resolution = result.raw.payload["source_resolution"]["bls"]

    assert result.raw.status == SourceStatus.HEALTHY
    assert result.raw.payload["errors"] == []
    assert "cpi_days_until" in metric_ids
    assert "nfp_days_until" in metric_ids
    assert bls_resolution["status"] == "official_blocked_embedded_fallback"
    assert bls_resolution["official_blocked"] is True
    assert bls_resolution["blocking_error"] is False
    assert bls_resolution["fallback_provider"] == "embedded_official_calendar_table"


async def test_fxstreet_rendered_without_actual_is_no_released_event(monkeypatch) -> None:
    text = """
Time\tEvent\tImpact\tActual\tDev\tConsensus\tPrevious
WEDNESDAY, MAY 20
8:30 AM
USD\tConsumer Price Index (MoM) (Apr)
-\t-\t0.3%\t0.2%
9:00 AM
USD\tFed Chair Powell Speech
LOCKED\t-\t-\t-
"""
    client = PlaywrightClient(get_source("fxstreet-economic-calendar"), SourceMode.LIVE)

    async def fake_render_page_text(wait_ms: int = 10_000) -> tuple[str, str]:
        return text, "fxstreet.html"

    monkeypatch.setattr(client, "_render_page_text", fake_render_page_text)

    result = await client._collect_fxstreet_economic_calendar()

    assert result.raw.status == SourceStatus.HEALTHY
    assert result.raw.payload["fxstreet_status"] == "no_released_event"
    assert result.raw.payload["macro_surprise"]["meaning"] == "no_new_surprise"
    assert result.raw.payload["macro_surprise"]["should_not_trigger_alert"] is True
    assert result.metrics[0].metric_id == "macro_surprise_score"
    assert result.metrics[0].value == 0
    assert result.metrics[0].quality_score == 0.70
    assert result.raw.payload["diagnostics"]["usable_event_count"] == 0
    assert result.raw.payload["diagnostics"]["unreleased_event_count"] == 1
    assert result.raw.payload["diagnostics"]["locked_event_count"] == 1


async def test_fxstreet_macro_surprise_mock_writes_metrics(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    await collect_sources(
        mode=SourceMode.MOCK,
        source_ids=["fxstreet-economic-calendar", "bitbo-sth-lth-realized-price"],
        db=db,
    )

    with db.session() as session:
        rows = session.scalars(
            select(schema.MetricValue.metric_id).where(
                schema.MetricValue.metric_id.in_(
                    {
                        "macro_surprise_score",
                        "aggregate_macro_surprise",
                        "macro_surprise_event_count",
                        "sth_cost_basis",
                        "lth_cost_basis",
                    }
                )
            )
        ).all()

    assert {
        "macro_surprise_score",
        "aggregate_macro_surprise",
        "macro_surprise_event_count",
        "sth_cost_basis",
        "lth_cost_basis",
    }.issubset(set(rows))


def test_fed_rss_parser_and_speech_score() -> None:
    xml = """<?xml version="1.0"?>
<rss><channel><item>
<title>Waller, Economic Outlook and Monetary Policy</title>
<link>https://www.federalreserve.gov/newsevents/speech/waller-test.htm</link>
<pubDate>Tue, 19 May 2026 15:00:00 GMT</pubDate>
<description>Speech At a policy forum</description>
</item></channel></rss>"""
    events = _parse_fed_rss(xml)
    score = _score_fed_speech_event(
        events[0],
        "Inflation remains elevated and price stability requires a restrictive policy rate. "
        "The labor market is tight and upside risks to inflation remain.",
    )

    assert events[0]["speaker"] == "Waller"
    assert events[0]["speaker_weight"] == 3
    assert score["hawkish_score"] > score["dovish_score"]
    assert score["fed_speech_risk"] > 0


def test_fomc_blackout_state_detects_active_window() -> None:
    state = _fomc_blackout_state(datetime(2026, 6, 10, tzinfo=UTC))

    assert state["active"] is True
    assert state["fomc_event_risk"] >= 0.8


async def test_fed_speech_risk_mock_writes_metrics(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    await collect_sources(
        mode=SourceMode.MOCK,
        source_ids=[
            "fed-rss-all-speeches",
            "fed-calendar",
            "fed-fomc-blackout-calendar",
        ],
        db=db,
    )

    wanted = {
        "fed_speaker_weight",
        "fed_speech_hawkish_score",
        "fed_speech_dovish_score",
        "fed_speech_content_risk",
        "fed_speech_risk",
        "next_fed_speech_hours_until",
        "fed_speech_scheduled_risk",
        "fomc_blackout_active",
        "fomc_event_risk",
    }
    with db.session() as session:
        rows = session.scalars(
            select(schema.MetricValue.metric_id).where(schema.MetricValue.metric_id.in_(wanted))
        ).all()

    assert wanted.issubset(set(rows))


def test_clarkmoody_dashboard_parser_extracts_lightning_and_mempool() -> None:
    html = """
    <html><body>
    Bitcoin Network Reachable Bitcoin Nodes 23,866 Bitcoin Tor Nodes 15,382
    Percentage Tor Nodes 64.5%
    Lightning Network (Public) Total Capacity 4,776.04 BTC Capacity Value $369.7M
    Total Nodes 10,020 Total Channels 39,444 Tor Capacity 3,716.14 BTC
    Percentage Tor Capacity 77.8% Tor Nodes 5,412
    Transactions Total All Time 1,360,845,535 Rate, 30 days 6.9 tx/s
    Chain Security Hash Rate, 90 Days 979.7 EH/s Chain Work 96.20 bits
    Mining Economics Block Subsidy 3.125 BTC Hash Price (PHash/s) $35.53
    Avg. Fees per Block 0.02 BTC Avg. Fees vs. Reward 0.51%
    Mempool Transactions 3,464 Percentage RBF 76.2% vSize 1.18 MB
    Blocks to Clear 2 Pending Fees 0.02 BTC Minimum Fee Rate 1 sat/vB
    Predicted Next Block Transactions 2,710
    </body></html>
    """

    parsed = _parse_clarkmoody_dashboard(html)

    assert parsed["lightning_capacity_btc"]["value"] == 4776.04
    assert parsed["lightning_capacity_usd"]["value"] == 369_700_000
    assert parsed["lightning_node_count"]["value"] == 10020
    assert parsed["lightning_channel_count"]["value"] == 39444
    assert parsed["lightning_tor_capacity_pct"]["value"] == 77.8
    assert parsed["bitcoin_reachable_nodes"]["value"] == 23866
    assert parsed["bitcoin_tor_nodes_pct"]["value"] == 64.5
    assert parsed["mempool_blocks_to_clear"]["value"] == 2
    assert parsed["mempool_min_fee_rate_sat_vb"]["value"] == 1
    assert parsed["hashrate_90d_ehs"]["value"] == 979.7
    assert parsed["fees_vs_reward_pct"]["value"] == 0.51


def test_clarkmoody_dashboard_parser_extracts_compact_percentage_rows() -> None:
    html = """
    Bitcoin Network Reachable Bitcoin Nodes 23,866 Bitcoin Tor Nodes 15,382 64.5%
    Lightning Network (Public) Total Capacity 4,776.04 BTC Capacity Value $369.7M
    Tor Capacity 3,716.14 BTC 77.8% Tor Nodes 5,412
    Transactions Total All Time 1,360,845,535
    Chain Security Hash Rate, 90 Days 979.7 EH/s
    Mining Economics Avg. Fees per Block 0.02 BTC 0.51%
    Mempool Transactions 3,464 Predicted Next Block
    """

    parsed = _parse_clarkmoody_dashboard(html)

    assert parsed["lightning_tor_capacity_pct"]["value"] == 77.8
    assert parsed["bitcoin_tor_nodes_pct"]["value"] == 64.5
    assert parsed["fees_vs_reward_pct"]["value"] == 0.51


async def test_clarkmoody_dashboard_mock_writes_metrics(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")

    await collect_sources(mode=SourceMode.MOCK, source_ids=["clarkmoody-dashboard"], db=db)

    wanted = {
        "lightning_capacity_btc",
        "lightning_capacity_usd",
        "lightning_node_count",
        "lightning_channel_count",
        "lightning_tor_capacity_pct",
        "bitcoin_tor_nodes_pct",
        "bitcoin_reachable_nodes",
        "mempool_blocks_to_clear",
        "hashrate_90d_ehs",
        "fees_vs_reward_pct",
    }
    with db.session() as session:
        rows = session.scalars(
            select(schema.MetricValue.metric_id).where(schema.MetricValue.metric_id.in_(wanted))
        ).all()

    assert wanted.issubset(set(rows))
