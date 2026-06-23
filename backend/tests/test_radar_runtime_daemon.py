from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from onlybtc.db import schema
from onlybtc.db.repositories import RadarRuntimeRepository
from onlybtc.db.session import Database
from onlybtc.radar_runtime.daemon import RadarRuntimeDaemon
from onlybtc.radar_runtime.service import _source_freshness_from_payload
from onlybtc.radar_runtime.source_gate import run_source_refresh_gate, source_ids_for_modules
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID


def _latest_runtime_id(db: Database) -> str:
    db.init_schema()
    with db.session() as session:
        latest = RadarRuntimeRepository(session).latest_runtime_snapshot() or {}
    return str(latest.get("runtime_snapshot_id") or "")


def test_radar_runtime_audit_html_refreshes_after_manual_and_scheduled_ticks(tmp_path) -> None:
    db = Database(tmp_path / "radar-runtime-audit-refresh.sqlite3")
    calls: list[dict[str, Any]] = []

    def fake_generator(*, db: Database, refresh_mode: str) -> dict[str, Any]:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "runtime_snapshot_id": _latest_runtime_id(db),
            "html_refresh_mode": refresh_mode,
        }
        calls.append(payload)
        return payload

    daemon = RadarRuntimeDaemon(audit_generator=fake_generator, audit_refresh_seconds=300)

    daemon.run_once(db=db, trigger_type="manual_full_sweep")
    assert calls[-1]["html_refresh_mode"] == "manual_run_once"
    assert daemon.health()["last_audit_html_snapshot_id"] == calls[-1]["runtime_snapshot_id"]

    with daemon._lock:  # noqa: SLF001 - audit cadence regression needs controlled clock state.
        daemon._last_audit_html_generated_at = datetime.now(UTC) - timedelta(seconds=301)  # noqa: SLF001
        for item in daemon._schedule.values():  # noqa: SLF001
            item["next_due_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    tick = daemon.scheduler_tick(db=db)
    assert tick["audit_html"]["generated"] is True
    assert calls[-1]["html_refresh_mode"] == "scheduled"
    assert daemon.health()["last_audit_html_refresh_mode"] == "scheduled"


def test_radar_runtime_audit_html_refreshes_on_health_transition(tmp_path) -> None:
    db = Database(tmp_path / "radar-runtime-audit-health.sqlite3")
    calls: list[dict[str, Any]] = []

    def fake_generator(*, db: Database, refresh_mode: str) -> dict[str, Any]:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "runtime_snapshot_id": _latest_runtime_id(db),
            "html_refresh_mode": refresh_mode,
        }
        calls.append(payload)
        return payload

    daemon = RadarRuntimeDaemon(audit_generator=fake_generator, audit_refresh_seconds=300)
    daemon.run_once(db=db, trigger_type="manual_full_sweep")
    calls.clear()

    with daemon._lock:  # noqa: SLF001 - audit transition regression needs controlled daemon state.
        daemon._last_audit_html_generated_at = datetime.now(UTC)  # noqa: SLF001
        daemon._last_audit_health_state = "healthy"  # noqa: SLF001
        daemon._last_error = "forced degraded state"  # noqa: SLF001
        for item in daemon._schedule.values():  # noqa: SLF001
            item["next_due_at"] = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    tick = daemon.scheduler_tick(db=db)
    assert tick["audit_html"]["generated"] is True
    assert calls[-1]["html_refresh_mode"] == "health_transition"
    assert daemon.health()["last_audit_html_error"] == ""


def test_radar_runtime_audit_html_generator_failure_is_non_fatal(tmp_path) -> None:
    db = Database(tmp_path / "radar-runtime-audit-failure.sqlite3")

    def failing_generator(*, db: Database, refresh_mode: str) -> dict[str, Any]:
        raise RuntimeError("audit html disk is unavailable")

    daemon = RadarRuntimeDaemon(audit_generator=failing_generator, audit_refresh_seconds=300)
    with daemon._lock:  # noqa: SLF001 - isolate audit failure from daemon lifecycle state.
        daemon._status = "running"  # noqa: SLF001
    result = daemon.run_once(db=db, trigger_type="manual_full_sweep")
    health = daemon.health()

    assert result["snapshot_id"]
    assert health["health_state"] == "healthy"
    assert "audit html disk is unavailable" in health["last_audit_html_error"]


def test_radar_runtime_score_bridge_uses_latest_p45_semantic_module_scores(tmp_path) -> None:
    db = Database(tmp_path / "radar-runtime-score-bridge.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="p45-final-score-bridge",
                module_id=P45_FINAL_ARTICLE_MODULE_ID,
                schema_version="p45.final.v1",
                payload={
                    "final_run_id": "p45-final-score-bridge",
                    "radar_module_scores": [
                        {
                            "radar_module": "kline_orderflow",
                            "module_score": -0.42,
                            "module_effective_score": -0.42,
                            "module_direction": "bearish",
                            "module_effective_direction": "bearish",
                            "signal_stage": "early_warning",
                            "btc_implication": "downside_shift_attempt",
                            "scores": {"btc_response_score": -55},
                            "pressure_drivers": ["vwap_rejection"],
                        }
                    ],
                },
            )
        )

    daemon = RadarRuntimeDaemon(audit_generator=lambda **_: {}, audit_refresh_seconds=300)
    result = daemon.run_once(db=db, trigger_type="manual_full_sweep")
    runtime = result["runtime"]
    module = next(item for item in runtime["modules"] if item["module_name"] == "kline_orderflow")

    assert module["module_score"] == -0.42
    assert module["module_effective_direction"] == "bearish"
    assert module["signal_stage"] == "early_warning"
    assert module["btc_response_score"] == -55
    assert module["score_source"] == "semantic_fallback.module_effective_score"
    assert module["source_freshness_state"] == module["source_freshness"]["state"]
    assert "source_missing_feature_count" in module
    assert "source_context_only_stale_count" in module
    assert runtime["btc_runtime_cockpit"]["schema_version"] == "p45.radar_runtime_cockpit.v2"
    assert runtime["btc_runtime_cockpit"]["module_contributions"]


def test_radar_runtime_source_freshness_detects_expired_features() -> None:
    payload = {
        "features": [
            {
                "metric_id": "btc_return_5m",
                "source_id": "binance-btcusdt-kline-5m",
                "freshness_status": "expired",
                "collection_freshness_status": "expired",
                "source_ts": "2026-05-29T02:00:00+00:00",
                "quality_blocking": True,
            },
            {
                "metric_id": "btc_return_1h",
                "source_id": "binance-btcusdt-kline-1h",
                "freshness_status": "fresh",
            },
        ]
    }

    freshness = _source_freshness_from_payload(payload)

    assert freshness["state"] == "expired"
    assert freshness["source_fresh"] is False
    assert freshness["checked_feature_count"] == 2
    assert freshness["expired_feature_count"] == 1
    assert freshness["sample"][0]["metric_id"] == "btc_return_5m"


def test_radar_runtime_source_gate_maps_fast_modules_to_binance_sources() -> None:
    mapping = source_ids_for_modules(["kline_orderflow", "derivatives_crowding"])

    assert mapping["source_group_ids"] == ["fast_btc_market"]
    assert "binance-btcusdt-kline-5m" in mapping["source_ids"]
    assert "binance-btcusdt-kline-15m" in mapping["source_ids"]
    assert "binance-btcusdt-kline-1h" in mapping["source_ids"]
    assert "binance-btcusdt-open-interest" in mapping["source_ids"]
    assert "binance-btcusdt-funding" in mapping["source_ids"]
    assert "binance-usdm-force-order-btcusdt" in mapping["source_ids"]
    assert "bybit-v5-all-liquidation-btcusdt" in mapping["source_ids"]


def test_radar_runtime_source_gate_maps_asia_and_macro_proxy_sources() -> None:
    fast = source_ids_for_modules(["asia_risk"])
    confirmation = source_ids_for_modules(["macro_radar", "treasury_credit"])

    assert "playwright-tradingview-usdjpy" in fast["source_ids"]
    assert "playwright-tradingview-hang-seng-tech" in fast["source_ids"]
    assert "fred-usdcnh-proxy" in fast["source_ids"]
    assert "playwright-tradingview-sp500" in confirmation["source_ids"]
    assert "playwright-tradingview-russell-2000" in confirmation["source_ids"]
    assert "ofr-fsi" in confirmation["source_ids"]
    assert "fred-hy-spread" in confirmation["source_ids"]


@pytest.mark.asyncio
async def test_radar_runtime_source_gate_runs_collect_inside_existing_event_loop(
    tmp_path,
    monkeypatch,
) -> None:
    db = Database(tmp_path / "radar-runtime-source-gate-loop.sqlite3")
    calls: list[dict[str, Any]] = []

    async def fake_collect_sources(**kwargs) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "run_id": kwargs["run_id"],
            "collected": len(kwargs["source_ids"]),
            "errors": [],
            "warnings": [],
        }

    monkeypatch.setattr(
        "onlybtc.radar_runtime.source_gate.collect_sources",
        fake_collect_sources,
    )

    result = run_source_refresh_gate(["kline_orderflow"], db=db)

    assert result["status"] == "success"
    assert result["refreshed_source_count"] == len(result["source_ids"])
    assert calls
    assert calls[0]["run_id"] == result["run_id"]
    assert calls[0]["source_ids"] == result["source_ids"]
    assert calls[0]["db"] is db


def test_radar_runtime_source_freshness_expected_lag_is_not_blocking_stale() -> None:
    payload = {
        "features": [
            {
                "metric_id": "fund_flow_expected_daily",
                "source_id": "fund-flow-derived",
                "freshness_status": "fresh",
                "collection_freshness_status": "fresh",
                "business_recency_status": "expected_lag",
                "quality_blocking": True,
            },
            {
                "metric_id": "context_only_old_macro",
                "source_id": "fred-slow-context",
                "freshness_status": "expired",
                "collection_freshness_status": "expired",
                "quality_blocking": False,
            },
        ]
    }

    freshness = _source_freshness_from_payload(payload)

    assert freshness["state"] == "expected_lag"
    assert freshness["expired_feature_count"] == 0
    assert freshness["stale_feature_count"] == 0
    assert freshness["expected_lag_feature_count"] == 1
    assert freshness["context_only_stale_count"] == 1


def test_radar_runtime_optional_missing_feature_does_not_block_source_freshness() -> None:
    payload = {
        "features": [
            {
                "metric_id": "rv_change_1d",
                "source_id": "deribit-btc-options",
                "available": False,
                "quality_blocking": False,
                "freshness_status": "missing",
                "selected_reason": "optional_context",
            }
        ]
    }

    freshness = _source_freshness_from_payload(payload, module_id="options_volatility")

    assert freshness["state"] == "fresh"
    assert freshness["source_fresh"] is True
    assert freshness["relevant_feature_count"] == 0
    assert freshness["context_only_stale_count"] == 1


def test_radar_runtime_fast_module_ignores_slow_context_stale_features() -> None:
    payload = {
        "features": [
            {
                "metric_id": "mempool_blocks_to_clear",
                "source_id": "clarkmoody-dashboard",
                "available": True,
                "quality_blocking": True,
                "freshness_status": "stale",
                "collection_freshness_status": "stale",
            },
            {
                "metric_id": "trade_price_acceptance_score_5m",
                "source_id": "binance-btcusdt-kline-5m",
                "available": True,
                "quality_blocking": True,
                "freshness_status": "fresh",
                "collection_freshness_status": "fresh",
            },
        ]
    }

    freshness = _source_freshness_from_payload(payload, module_id="trade_structure_flow")

    assert freshness["state"] == "fresh"
    assert freshness["source_fresh"] is True
    assert freshness["relevant_feature_count"] == 1
    assert freshness["context_only_stale_count"] == 1


def test_radar_runtime_liquidation_gap_is_optional_until_source_arrives() -> None:
    payload = {
        "features": [
            {
                "metric_id": "liquidation_impulse_z_15m",
                "source_id": "bybit-v5-all-liquidation-btcusdt",
                "available": False,
                "quality_blocking": True,
                "freshness_status": "missing",
            },
            {
                "metric_id": "funding_rate_8h_equiv_z",
                "source_id": "binance-btcusdt-funding",
                "available": True,
                "quality_blocking": True,
                "freshness_status": "fresh",
            },
        ]
    }

    freshness = _source_freshness_from_payload(payload, module_id="derivatives_crowding")

    assert freshness["state"] == "fresh"
    assert freshness["source_fresh"] is True
    assert freshness["relevant_feature_count"] == 1
    assert freshness["context_only_stale_count"] == 1
