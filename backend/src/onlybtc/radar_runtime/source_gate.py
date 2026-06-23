from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from typing import Any
from uuid import uuid4

from onlybtc.db.session import Database, database
from onlybtc.radar_runtime.profile import FAST_MODULES, CONFIRMATION_MODULES, REGIME_MODULES
from onlybtc.sources.models import SourceMode
from onlybtc.sources.registry import SOURCE_CONFIGS
from onlybtc.sources.service import collect_sources

FAST_BTC_MARKET_SOURCE_IDS = [
    "binance-btcusdt",
    "binance-btcusdt-kline-5m",
    "binance-btcusdt-kline-15m",
    "binance-btcusdt-kline-1h",
    "binance-btcusdt-open-interest",
    "binance-btcusdt-funding",
    "binance-btcusdt-global-long-short-account-ratio",
    "binance-btcusdt-top-long-short-account-ratio",
    "binance-btcusdt-top-long-short-position-ratio",
    "binance-btcusdt-taker-buy-sell-ratio",
    "binance-usdm-force-order-btcusdt",
    "bybit-v5-all-liquidation-btcusdt",
    "playwright-tradingview-usdjpy",
    "playwright-tradingview-usdcnh",
    "playwright-tradingview-jgb-10y",
    "playwright-tradingview-topix",
    "playwright-tradingview-hang-seng-tech",
    "fred-usdjpy",
    "fred-usdcnh-proxy",
    "fred-nikkei",
    "fred-jgb-10y",
]

CONFIRMATION_MACRO_FLOW_SOURCE_IDS = [
    "playwright-tradingview-dxy",
    "playwright-tradingview-sp500",
    "playwright-tradingview-dow-jones",
    "playwright-tradingview-russell-2000",
    "playwright-tradingview-gold",
    "playwright-tradingview-wti-oil",
    "playwright-tradingview-brent-oil",
    "fred-real-yield",
    "fred-treasury-2y",
    "fred-treasury-10y",
    "fred-treasury-30y",
    "fred-vix",
    "fred-sp500",
    "fred-wti-oil",
    "fred-brent-oil",
    "fred-fed-balance-sheet",
    "fred-bank-reserves",
    "fred-on-rrp",
    "fred-sofr",
    "fred-iorb",
    "fred-tga",
    "fred-breakeven-10y",
    "fred-ig-oas",
    "fred-hy-spread",
    "ofr-fsi",
    "defillama-stablecoins",
]

REGIME_SLOW_SOURCE_IDS = [
    "bitcoin-blockstream",
    "blockchain-active-addresses",
    "blockchain-transaction-count",
    "blockchain-hashrate",
    "mempool-lightning-network-stats",
    "clarkmoody-dashboard",
    "coinmetrics-community-btc-csv",
    "bitbo-sth-lth-realized-price",
    "playwright-glassnode-asset-overview",
    "playwright-glassnode-sopr",
    "coingecko-global",
    "coingecko-eth-btc",
    "coingecko-top50-markets",
    "binance-btcusdt-kline-1d-rv",
    "deribit-btc-options",
    "official-macro-event-calendar",
    "fxstreet-economic-calendar",
    "fed-calendar",
    "fed-rss-all-speeches",
    "fed-fomc-blackout-calendar",
    "alternative-fear-greed",
]

MODULE_SOURCE_GROUPS: dict[str, str] = {
    **{module_id: "fast_btc_market" for module_id in FAST_MODULES},
    **{module_id: "confirmation_macro_flow" for module_id in CONFIRMATION_MODULES},
    **{module_id: "regime_slow" for module_id in REGIME_MODULES},
}

SOURCE_GROUP_IDS: dict[str, list[str]] = {
    "fast_btc_market": FAST_BTC_MARKET_SOURCE_IDS,
    "confirmation_macro_flow": CONFIRMATION_MACRO_FLOW_SOURCE_IDS,
    "regime_slow": REGIME_SLOW_SOURCE_IDS,
}


def source_group_for_module(module_id: str) -> str:
    return MODULE_SOURCE_GROUPS.get(module_id, "confirmation_macro_flow")


def source_ids_for_modules(module_ids: list[str]) -> dict[str, Any]:
    configured = {source.source_id for source in SOURCE_CONFIGS}
    source_group_ids = sorted({source_group_for_module(module_id) for module_id in module_ids})
    source_ids: list[str] = []
    missing: list[str] = []
    for group_id in source_group_ids:
        for source_id in SOURCE_GROUP_IDS.get(group_id, []):
            if source_id in configured:
                source_ids.append(source_id)
            else:
                missing.append(source_id)
    deduped = list(dict.fromkeys(source_ids))
    return {
        "source_group_ids": source_group_ids,
        "source_ids": deduped,
        "missing_configured_source_ids": sorted(set(missing)),
    }


def run_source_refresh_gate(
    module_ids: list[str],
    *,
    db: Database = database,
    mode: SourceMode | None = None,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    run_id = f"radar-runtime-source-{started.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    mapping = source_ids_for_modules(module_ids)
    source_ids = list(mapping["source_ids"])
    if not source_ids:
        return {
            "schema_version": "p9.c54.source_refresh_gate.v1",
            "run_id": run_id,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "mode": "targeted",
            "module_ids": module_ids,
            **mapping,
            "status": "skipped",
            "refreshed_source_count": 0,
            "failed_source_count": 0,
            "errors": [],
            "reason": "no_configured_sources",
        }

    collect_mode = mode or _default_collect_mode(db)
    try:
        result = _run_collect_sources_sync(
            mode=collect_mode,
            source_ids=source_ids,
            run_id=run_id,
            db=db,
        )
    except Exception as exc:
        return {
            "schema_version": "p9.c54.source_refresh_gate.v1",
            "run_id": run_id,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "mode": "targeted",
            "collect_mode": collect_mode.value,
            "module_ids": module_ids,
            **mapping,
            "status": "failed",
            "refreshed_source_count": 0,
            "failed_source_count": len(source_ids),
            "errors": [{"error": str(exc), "error_type": exc.__class__.__name__}],
        }

    errors = result.get("errors") if isinstance(result, dict) else []
    failed_source_ids = {
        str(item.get("source_id"))
        for item in errors or []
        if isinstance(item, dict) and item.get("source_id")
    }
    refreshed = max(int(result.get("collected") or 0) - len(failed_source_ids), 0)
    status = "success"
    if failed_source_ids:
        status = "partial" if refreshed else "failed"
    return {
        "schema_version": "p9.c54.source_refresh_gate.v1",
        "run_id": run_id,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "mode": "targeted",
        "collect_mode": collect_mode.value,
        "module_ids": module_ids,
        **mapping,
        "status": status,
        "refreshed_source_count": refreshed,
        "failed_source_count": len(failed_source_ids),
        "failed_source_ids": sorted(failed_source_ids),
        "errors": errors or [],
        "warnings": result.get("warnings") if isinstance(result, dict) else [],
    }


def _default_collect_mode(db: Database) -> SourceMode:
    try:
        if Path(db.db_path).resolve() == Path(database.db_path).resolve():
            return SourceMode.LIVE
    except OSError:
        pass
    return SourceMode.MOCK


def _run_collect_sources_sync(
    *,
    mode: SourceMode,
    source_ids: list[str],
    run_id: str,
    db: Database,
) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            collect_sources(
                mode=mode,
                source_ids=source_ids,
                run_id=run_id,
                db=db,
            )
        )

    result_box: dict[str, Any] = {}
    error_box: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result_box["result"] = asyncio.run(
                collect_sources(
                    mode=mode,
                    source_ids=source_ids,
                    run_id=run_id,
                    db=db,
                )
            )
        except BaseException as exc:  # pragma: no cover - surfaced to caller below.
            error_box["error"] = exc

    thread = Thread(target=runner, name="radar-runtime-source-gate-collect", daemon=True)
    thread.start()
    thread.join()
    if error_box:
        raise error_box["error"]
    result = result_box.get("result")
    return result if isinstance(result, dict) else {}
