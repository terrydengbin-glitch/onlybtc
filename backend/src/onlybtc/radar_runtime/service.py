from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.repositories import RadarRuntimeRepository
from onlybtc.db.session import Database, database
from onlybtc.p45.cockpit import build_btc_trend_cockpit
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID
from onlybtc.radar_runtime.freshness import freshness_state
from onlybtc.radar_runtime.profile import initial_schedule, next_due_at, profile_by_module
from onlybtc.radar_runtime.source_gate import run_source_refresh_gate, source_group_for_module
from onlybtc.radars.service import analyze_radars

RUNTIME_SCHEMA_VERSION = "p45.radar_runtime.v1"
SOURCE_FRESHNESS_SCHEMA_VERSION = "p9.c53.source_freshness.v1"
FRESH_SOURCE_STATES = {"fresh", "ok", "live", "current"}
PARTIAL_SOURCE_STATES = {"partial", "partial_live", "expected_lag", "pending", "lagging", "outdated"}
STALE_SOURCE_STATES = {"stale", "expired", "hard_stale", "missing", "unavailable", "failed"}
SOURCE_STALE_SAMPLE_LIMIT = 8
FAST_CONTEXT_SOURCE_IDS = {
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
}
OPTIONAL_LIVE_PREFIXES = ("liquidation_",)
OPTIONAL_DERIVED_SUFFIXES = ("_percentile_252d",)


def run_incremental_modules(
    module_ids: list[str],
    *,
    trigger_type: str = "scheduler_tick",
    db: Database = database,
) -> dict[str, Any]:
    if not module_ids:
        return {"run_id": "", "analyzed": 0, "module_snapshots": []}
    run_id = f"radar-runtime-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    source_refresh_gate = run_source_refresh_gate(module_ids, db=db)
    result = analyze_radars(
        module_ids=module_ids,
        run_id=run_id,
        run_mode="live",
        historical_fallback=True,
        db=db,
    )
    profiles = profile_by_module()
    now = datetime.now(UTC)
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput).where(schema.ModuleJsonOutput.run_id == run_id)
        ).all()
        semantic_index = _latest_semantic_module_index(session)
        repo = RadarRuntimeRepository(session)
        snapshots: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row.payload)
            module_id = row.module_id
            semantic = semantic_index.get(module_id, {})
            profile = profiles.get(module_id, {})
            age_sec = 0
            fresh = freshness_state(
                age_sec=age_sec,
                ttl_sec=int(profile.get("ttl_sec") or 300),
                hard_stale_sec=int(profile.get("hard_stale_sec") or 900),
                cadence_group=str(profile.get("cadence_group") or "confirmation"),
            )
            score_info = _score_from_payload(payload, semantic)
            module_score = score_info["score"]
            direction_info = _direction_from_payload(payload, semantic, module_score)
            stage_info = _signal_stage_from_payload(payload, semantic)
            source_freshness = _source_freshness_from_payload(payload, module_id=module_id)
            snapshot = {
                "schema_version": "p2.c42.radar_module_runtime_snapshot.v1",
                "module_snapshot_id": (
                    f"radar-module-{module_id}-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
                ),
                "module_name": module_id,
                "module_id": module_id,
                "run_id": run_id,
                "trigger_type": trigger_type,
                "asof_ts": now.isoformat(),
                "collected_at": now.isoformat(),
                "last_success_at": now.isoformat(),
                "cadence_group": profile.get("cadence_group", "confirmation"),
                "source_group_id": source_group_for_module(module_id),
                "source_refresh_gate": source_refresh_gate,
                "source_refresh_status": source_refresh_gate.get("status"),
                "ttl_sec": profile.get("ttl_sec", 300),
                "hard_stale_sec": profile.get("hard_stale_sec", 900),
                "age_sec": age_sec,
                "freshness_state": fresh["freshness_state"],
                "runtime_fresh": fresh["freshness_state"] == "fresh",
                "runtime_freshness": {
                    "state": fresh["freshness_state"],
                    "participation_policy": fresh["participation_policy"],
                    "age_sec": age_sec,
                },
                "source_fresh": source_freshness["state"] == "fresh",
                "source_freshness_state": source_freshness["state"],
                "source_blocking_feature_count": source_freshness.get("blocking_feature_count", 0),
                "source_expired_feature_count": source_freshness.get("expired_feature_count", 0),
                "source_stale_feature_count": source_freshness.get("stale_feature_count", 0),
                "source_missing_feature_count": source_freshness.get("missing_feature_count", 0),
                "source_expected_lag_feature_count": source_freshness.get("expected_lag_feature_count", 0),
                "source_context_only_stale_count": source_freshness.get("context_only_stale_count", 0),
                "source_freshness": source_freshness,
                "runtime_participation_policy": fresh["participation_policy"],
                "participation_policy": _effective_participation_policy(
                    fresh["participation_policy"],
                    source_freshness,
                ),
                "module_direction": direction_info["raw_direction"],
                "module_effective_direction": direction_info["effective_direction"],
                "signal_stage": stage_info["signal_stage"],
                "btc_implication": _pick_payload_value(payload, semantic, "btc_implication"),
                "btc_response_score": _extract_btc_response_score(payload, semantic),
                "residual": _extract_residual(payload, semantic),
                "module_score": module_score,
                "module_effective_score": score_info["effective_score"],
                "score_source": score_info["score_source"],
                "score_explanation": score_info["score_explanation"],
                "support_drivers": _driver_list(_pick_payload_value(payload, semantic, "support_drivers")),
                "pressure_drivers": _driver_list(_pick_payload_value(payload, semantic, "pressure_drivers")),
                "conflict_drivers": _driver_list(_pick_payload_value(payload, semantic, "conflict_drivers")),
                "data_quality_flags": _driver_list(_pick_payload_value(payload, semantic, "data_quality_flags")),
                "module_payload": payload,
                "module_semantic_profile": semantic,
                "profile": profile,
                "error_json": {},
            }
            snapshots.append(repo.save_module_snapshot(snapshot))
    return {
        **result,
        "runtime_schema_version": "p2.c42.incremental_runner.v1",
        "source_refresh_gate": source_refresh_gate,
        "module_snapshots": snapshots,
    }


def build_runtime_snapshot(
    *,
    trigger_type: str = "scheduler_tick",
    db: Database = database,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    profiles = profile_by_module()
    db.init_schema()
    with db.session() as session:
        repo = RadarRuntimeRepository(session)
        modules = repo.latest_module_snapshots()
        refreshed: list[dict[str, Any]] = []
        for item in modules:
            module_id = str(item.get("module_name") or item.get("module_id") or "")
            last_success = _parse_dt(item.get("last_success_at") or item.get("asof_ts"))
            age_sec = int((now - last_success).total_seconds()) if last_success else None
            profile = profiles.get(module_id, item.get("profile") or {})
            fresh = freshness_state(
                age_sec=age_sec,
                ttl_sec=int(profile.get("ttl_sec") or item.get("ttl_sec") or 300),
                hard_stale_sec=int(profile.get("hard_stale_sec") or item.get("hard_stale_sec") or 900),
                cadence_group=str(profile.get("cadence_group") or item.get("cadence_group") or "confirmation"),
                last_status="success",
            )
            source_freshness = _source_freshness_from_payload(
                item.get("module_payload") or item,
                module_id=module_id,
            )
            refreshed.append(
                {
                    **item,
                    "source_group_id": item.get("source_group_id") or source_group_for_module(module_id),
                    "age_sec": age_sec,
                    "freshness_state": fresh["freshness_state"],
                    "runtime_fresh": fresh["freshness_state"] == "fresh",
                    "runtime_freshness": {
                        "state": fresh["freshness_state"],
                        "participation_policy": fresh["participation_policy"],
                        "age_sec": age_sec,
                    },
                    "source_fresh": source_freshness["state"] == "fresh",
                    "source_freshness_state": source_freshness["state"],
                    "source_blocking_feature_count": source_freshness.get("blocking_feature_count", 0),
                    "source_expired_feature_count": source_freshness.get("expired_feature_count", 0),
                    "source_stale_feature_count": source_freshness.get("stale_feature_count", 0),
                    "source_missing_feature_count": source_freshness.get("missing_feature_count", 0),
                    "source_expected_lag_feature_count": source_freshness.get("expected_lag_feature_count", 0),
                    "source_context_only_stale_count": source_freshness.get("context_only_stale_count", 0),
                    "source_freshness": source_freshness,
                    "runtime_participation_policy": fresh["participation_policy"],
                    "participation_policy": _effective_participation_policy(
                        fresh["participation_policy"],
                        source_freshness,
                    ),
                }
            )
        health = _health_from_modules(refreshed)
        last_source_refresh_gate = _latest_source_refresh_gate(refreshed)
        payload = {
            "schema_version": RUNTIME_SCHEMA_VERSION,
            "runtime_snapshot_id": f"radar-runtime-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            "asof_ts": now.isoformat(),
            "trigger_type": trigger_type,
            "health": health,
            "last_source_refresh_gate": last_source_refresh_gate,
            "cadence_profile": list(profiles.values()),
            "modules": refreshed,
            "btc_runtime_cockpit": _runtime_cockpit(refreshed, health),
        }
        saved = repo.save_runtime_snapshot(payload)
    return saved


def run_full_sweep(*, trigger_type: str = "manual_full_sweep", db: Database = database) -> dict[str, Any]:
    modules = list(profile_by_module())
    incremental = run_incremental_modules(modules, trigger_type=trigger_type, db=db)
    runtime = build_runtime_snapshot(trigger_type=trigger_type, db=db)
    now = datetime.now(UTC)
    schedule = initial_schedule(now)
    for module_name, item in schedule.items():
        interval = int(item.get("interval_sec") or 300)
        schedule[module_name] = {
            **item,
            "last_attempt_at": now.isoformat(),
            "last_success_at": now.isoformat(),
            "next_due_at": next_due_at(now, interval),
            "last_status": "success",
            "last_snapshot_id": runtime.get("runtime_snapshot_id", ""),
        }
    db.init_schema()
    with db.session() as session:
        RadarRuntimeRepository(session).upsert_scheduler_state(schedule)
    return {"incremental": incremental, "runtime": runtime, "snapshot_id": runtime.get("runtime_snapshot_id")}


def latest_runtime_payload(*, db: Database = database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        return RadarRuntimeRepository(session).latest_runtime_snapshot()


def latest_module_payloads(*, db: Database = database) -> list[dict[str, Any]]:
    db.init_schema()
    with db.session() as session:
        return RadarRuntimeRepository(session).latest_module_snapshots()


def _latest_semantic_module_index(session: Any) -> dict[str, dict[str, Any]]:
    row = session.scalar(
        select(schema.ModuleJsonOutput)
        .where(schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID)
        .order_by(schema.ModuleJsonOutput.created_at.desc())
        .limit(1)
    )
    payload = dict(row.payload) if row else {}
    index: dict[str, dict[str, Any]] = {}
    for item in payload.get("radar_module_scores") or []:
        if not isinstance(item, dict):
            continue
        module_id = str(item.get("radar_module") or item.get("module_id") or "")
        if module_id:
            index[module_id] = dict(item)
    return index


def _score_from_payload(payload: dict[str, Any], semantic: dict[str, Any] | None = None) -> dict[str, Any]:
    semantic = semantic or {}
    for source_name, source in (("runtime_payload", payload), ("semantic_fallback", semantic)):
        for score_source, value in _score_candidates(source_name, source):
            numeric = _to_float(value)
            if numeric is None:
                continue
            score = _normalize_score(numeric)
            if score == 0.0 and source_name == "runtime_payload":
                continue
            return {
                "score": score,
                "effective_score": score,
                "score_source": score_source,
                "score_explanation": f"module_score mapped from {score_source}",
            }
    return {
        "score": 0.0,
        "effective_score": 0.0,
        "score_source": "missing",
        "score_explanation": "no runtime or semantic module score available",
    }


def _score_candidates(source_name: str, source: dict[str, Any]) -> list[tuple[str, Any]]:
    candidates: list[tuple[str, Any]] = []
    profile = source.get("module_semantic_profile")
    if isinstance(profile, dict):
        for key in ("module_effective_score", "module_score"):
            candidates.append((f"{source_name}.module_semantic_profile.{key}", profile.get(key)))
    for key in ("module_effective_score", "module_score", "score", "strength"):
        candidates.append((f"{source_name}.{key}", source.get(key)))
    scores = source.get("scores")
    if isinstance(scores, dict):
        for key in (
            "module_effective_score",
            "module_score",
            "trend_acceptance_score",
            "btc_response_score",
            "price_acceptance_score",
        ):
            candidates.append((f"{source_name}.scores.{key}", scores.get(key)))
    return candidates


def _direction_from_payload(
    payload: dict[str, Any],
    semantic: dict[str, Any] | None = None,
    score: float | None = None,
) -> dict[str, str]:
    semantic = semantic or {}
    raw = _first_direction_value(
        (payload, ("module_direction", "direction", "signal", "module_bias")),
        (semantic, ("module_direction", "direction", "signal", "module_bias")),
    )
    effective = _first_direction_value(
        (payload, ("module_effective_direction", "effective_direction", "module_direction", "direction", "signal", "module_bias")),
        (semantic, ("module_effective_direction", "effective_direction", "module_direction", "direction", "signal", "module_bias")),
    )
    if effective is None and score is not None:
        effective = "bullish" if score > 0.0001 else "bearish" if score < -0.0001 else "neutral"
    if raw is None:
        raw = effective or "neutral"
    return {
        "raw_direction": _direction_value(raw),
        "effective_direction": _direction_value(effective),
    }


def _first_direction_value(*sources: tuple[dict[str, Any], tuple[str, ...]]) -> Any:
    neutral: Any = None
    for source, keys in sources:
        for key in keys:
            value = source.get(key)
            if value is None:
                continue
            direction = _direction_value(value)
            if direction != "neutral":
                return value
            neutral = neutral if neutral is not None else value
    return neutral


def _signal_stage_from_payload(payload: dict[str, Any], semantic: dict[str, Any] | None = None) -> dict[str, str]:
    value = _pick_payload_value(
        payload,
        semantic or {},
        "signal_stage",
        "stage",
        "display_state",
        "confirmation_status",
    )
    text = str(value or "").lower()
    if "confirmed" in text:
        stage = "confirmed_signal"
    elif "fast" in text:
        stage = "fast_signal"
    elif "early" in text or "warning" in text or "watch" in text:
        stage = "early_warning"
    elif "reject" in text:
        stage = "rejected"
    elif "conflict" in text:
        stage = "conflict"
    else:
        stage = "none"
    return {"signal_stage": stage}


def _pick_payload_value(payload: dict[str, Any], semantic: dict[str, Any], *keys: str) -> Any:
    sources: list[dict[str, Any]] = [payload, semantic]
    for source in (payload, semantic):
        profile = source.get("module_semantic_profile")
        if isinstance(profile, dict):
            sources.append(profile)
    for source in sources:
        for key in keys:
            if source.get(key) is not None:
                return source.get(key)
    return None


def _extract_btc_response_score(payload: dict[str, Any], semantic: dict[str, Any]) -> float | None:
    for source in (payload, semantic, semantic.get("module_semantic_profile") or {}):
        if not isinstance(source, dict):
            continue
        scores = source.get("scores")
        if isinstance(scores, dict):
            for key in (
                "btc_response_score",
                "btc_acceptance_score",
                "price_acceptance_score",
                "trend_acceptance_score",
            ):
                value = _to_float(scores.get(key))
                if value is not None:
                    return value
        for key in ("btc_response_score", "btc_acceptance_score", "price_acceptance_score", "trend_acceptance_score"):
            value = _to_float(source.get(key))
            if value is not None:
                return value
    return None


def _extract_residual(payload: dict[str, Any], semantic: dict[str, Any]) -> float | None:
    keys = (
        "derivatives_residual_z",
        "trade_structure_residual_z",
        "asia_risk_residual_z_90d",
        "orderflow_residual_z_60",
        "fund_flow_residual_z_60d",
        "onchain_residual_z_90d",
        "adoption_residual_z_90d",
        "btc_residual_24h",
    )
    for source in (payload, semantic, semantic.get("module_semantic_profile") or {}):
        if not isinstance(source, dict):
            continue
        for key in keys:
            value = _to_float(source.get(key))
            if value is not None:
                return value
        nested = source.get("btc_response_confirmation")
        if isinstance(nested, dict):
            for key in ("residual_z_90d", "residual_z_60d", "btc_residual_24h", "residual_24h"):
                value = _to_float(nested.get(key))
                if value is not None:
                    return value
        states = source.get("states")
        if isinstance(states, dict):
            for nested in states.values():
                if isinstance(nested, dict):
                    for key in ("residual_z_90d", "residual_z_60d", "residual_24h"):
                        value = _to_float(nested.get(key))
                        if value is not None:
                            return value
    return None


def _driver_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_score(value: float) -> float:
    if abs(value) > 1.5:
        value = value / 100.0
    return round(max(-1.0, min(1.0, value)), 4)


def _direction_value(value: Any) -> str:
    text = str(value or "neutral").lower()
    if "bull" in text or "support" in text or "upside" in text:
        return "bullish"
    if "bear" in text or "pressure" in text or "downside" in text:
        return "bearish"
    if "conflict" in text or "mixed" in text:
        return "conflict"
    return "neutral"


def _health_from_modules(modules: list[dict[str, Any]]) -> dict[str, Any]:
    fresh = [m for m in modules if m.get("freshness_state") == "fresh"]
    stale = [m for m in modules if m.get("freshness_state") in {"stale", "hard_stale"}]
    disabled = [m for m in modules if m.get("runtime_participation_policy") == "disabled"]
    source_fresh = [
        m for m in modules if (m.get("source_freshness") or {}).get("state") == "fresh"
    ]
    source_partial = [
        m
        for m in modules
        if (m.get("source_freshness") or {}).get("state")
        in {"partial", "partial_live", "expected_lag"}
    ]
    source_stale = [
        m for m in modules if (m.get("source_freshness") or {}).get("state") == "stale"
    ]
    source_expired = [
        m for m in modules if (m.get("source_freshness") or {}).get("state") == "expired"
    ]
    source_missing = [
        m for m in modules if (m.get("source_freshness") or {}).get("state") == "missing"
    ]
    missing_count = max(len(profile_by_module()) - len(modules), 0)
    if missing_count or disabled or source_expired or source_missing:
        health_state = "degraded"
    elif stale or source_stale:
        health_state = "stale"
    else:
        health_state = "healthy"
    return {
        "health_state": health_state,
        "runtime_fresh": not stale and not missing_count and not disabled,
        "source_fresh": not source_stale and not source_expired and not source_missing,
        "source_freshness_state": _aggregate_source_freshness_state(modules),
        "module_count": len(modules),
        "expected_module_count": len(profile_by_module()),
        "fresh_module_count": len(fresh),
        "stale_module_count": len(stale),
        "missing_module_count": missing_count,
        "disabled_module_count": len(disabled),
        "source_fresh_module_count": len(source_fresh),
        "source_partial_module_count": len(source_partial),
        "source_stale_module_count": len(source_stale),
        "source_expired_module_count": len(source_expired),
        "source_missing_module_count": len(source_missing),
        "source_stale_modules": [str(m.get("module_name") or m.get("module_id")) for m in source_stale[:8]],
        "source_expired_modules": [str(m.get("module_name") or m.get("module_id")) for m in source_expired[:8]],
        "source_missing_modules": [str(m.get("module_name") or m.get("module_id")) for m in source_missing[:8]],
    }


def _latest_source_refresh_gate(modules: list[dict[str, Any]]) -> dict[str, Any]:
    gates = [
        item.get("source_refresh_gate")
        for item in modules
        if isinstance(item.get("source_refresh_gate"), dict)
    ]
    if not gates:
        return {}
    return max(gates, key=lambda gate: str(gate.get("finished_at") or gate.get("started_at") or ""))


def _runtime_cockpit(modules: list[dict[str, Any]], health: dict[str, Any]) -> dict[str, Any]:
    cockpit_modules = [_cockpit_module_record(item) for item in modules]
    cockpit = build_btc_trend_cockpit(
        cockpit_modules,
        contract_validation={"status": "passed"},
        data_quality={"status": "ok", "metric_count": len(cockpit_modules)},
    )
    scores = cockpit.get("scores") or {}
    module_signals = cockpit.get("module_signals") or []
    support = [
        {
            "module": item.get("module_name"),
            "direction": item.get("effective_direction"),
            "score": item.get("module_score"),
            "contribution": item.get("contribution"),
        }
        for item in module_signals
        if float(item.get("contribution") or 0.0) > 0
    ]
    pressure = [
        {
            "module": item.get("module_name"),
            "direction": item.get("effective_direction"),
            "score": item.get("module_score"),
            "contribution": item.get("contribution"),
        }
        for item in module_signals
        if float(item.get("contribution") or 0.0) < 0
    ]
    context = [
        {
            "module": str(item.get("module_name") or item.get("module_id")),
            "direction": item.get("module_effective_direction") or item.get("module_direction"),
            "score": item.get("module_score"),
            "policy": item.get("participation_policy"),
        }
        for item in modules
        if item.get("participation_policy") in {"context_only", "disabled"}
    ]
    net = (
        float(scores.get("fast_net_score") or 0.0)
        + float(scores.get("confirmation_net_score") or 0.0)
        + float(scores.get("regime_net_score") or 0.0)
    )
    if health.get("missing_module_count") or health.get("disabled_module_count"):
        stage = "watch"
        quality = "degraded"
    elif not health.get("source_fresh", True):
        stage = "watch"
        quality = str(health.get("source_freshness_state") or "source_stale")
    elif abs(net) < 0.15:
        stage = "neutral"
        quality = "mixed"
    else:
        stage = "fast_signal"
        quality = "fresh"
    return {
        "schema_version": "p45.radar_runtime_cockpit.v2",
        "runtime_driven": True,
        "runtime_fresh": bool(health.get("runtime_fresh")),
        "source_fresh": bool(health.get("source_fresh")),
        "source_freshness_state": health.get("source_freshness_state"),
        "headline_stage": stage,
        "trend_quality": quality,
        "net_score": round(net, 4),
        "scores": scores,
        "fast_net_score": scores.get("fast_net_score"),
        "confirmation_net_score": scores.get("confirmation_net_score"),
        "regime_net_score": scores.get("regime_net_score"),
        "support_score": scores.get("support_score"),
        "pressure_score": scores.get("pressure_score"),
        "trend_acceptance_score": scores.get("trend_acceptance_score"),
        "module_contributions": module_signals,
        "dominant_support_modules": support[:4],
        "dominant_pressure_modules": pressure[:4],
        "context_only_modules": context[:6],
        "why_not_confirmed": (
            "runtime source data is stale or missing; confirmed_signal remains blocked"
            if not health.get("source_fresh", True)
            else
            "runtime missing or stale modules block confirmed_signal"
            if health.get("health_state") != "healthy"
            else "confirmed_signal still requires P4.5 acceptance/residual gate"
        ),
    }


def _cockpit_module_record(item: dict[str, Any]) -> dict[str, Any]:
    semantic = item.get("module_semantic_profile")
    if not isinstance(semantic, dict):
        semantic = {}
    module_id = str(item.get("module_name") or item.get("module_id") or semantic.get("radar_module") or "")
    record = {
        **semantic,
        "radar_module": module_id,
        "module_id": module_id,
        "module_score": item.get("module_score"),
        "module_effective_score": item.get("module_effective_score", item.get("module_score")),
        "module_direction": item.get("module_direction"),
        "module_effective_direction": item.get("module_effective_direction", item.get("module_direction")),
        "signal_stage": item.get("signal_stage"),
        "btc_implication": item.get("btc_implication"),
        "scores": {
            **(semantic.get("scores") if isinstance(semantic.get("scores"), dict) else {}),
            **({"btc_response_score": item.get("btc_response_score")} if item.get("btc_response_score") is not None else {}),
        },
        "support_drivers": item.get("support_drivers") or semantic.get("support_drivers") or [],
        "pressure_drivers": item.get("pressure_drivers") or semantic.get("pressure_drivers") or [],
        "conflict_drivers": item.get("conflict_drivers") or semantic.get("conflict_drivers") or [],
        "data_quality_flags": item.get("data_quality_flags") or semantic.get("data_quality_flags") or [],
        "runtime_score_source": item.get("score_source"),
        "runtime_score_explanation": item.get("score_explanation"),
        "runtime_freshness": item.get("runtime_freshness"),
        "source_freshness": item.get("source_freshness"),
        "participation_policy": item.get("participation_policy"),
    }
    if item.get("residual") is not None:
        record["btc_residual_24h"] = item.get("residual")
    return record


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _source_freshness_from_payload(payload: dict[str, Any], module_id: str | None = None) -> dict[str, Any]:
    features = list(_iter_feature_records(payload))
    checked = len(features)
    relevant = _relevant_feature_records(features, module_id=module_id)
    expired: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    expected_lag: list[dict[str, Any]] = []
    context_only_stale: list[dict[str, Any]] = []
    blocking = 0
    for feature in relevant:
        quality_blocking = bool(feature.get("quality_blocking"))
        if quality_blocking:
            blocking += 1
        state = _feature_freshness_state(feature)
        if state == "expired":
            expired.append(feature)
        elif state == "stale":
            stale.append(feature)
        elif state == "missing":
            missing.append(feature)
        elif state == "expected_lag":
            expected_lag.append(feature)
        elif state == "partial":
            partial.append(feature)
    relevant_ids = {id(item) for item in relevant}
    for feature in features:
        if id(feature) in relevant_ids:
            continue
        state = _feature_freshness_state(feature)
        if state in {"expired", "stale", "missing"}:
            context_only_stale.append(feature)
    if expired:
        state = "expired"
        source_fresh = False
    elif stale:
        state = "stale"
        source_fresh = False
    elif missing:
        state = "missing"
        source_fresh = False
    elif expected_lag:
        state = "expected_lag"
        source_fresh = False
    elif partial:
        state = "partial_live"
        source_fresh = False
    else:
        state = "fresh"
        source_fresh = True
    samples = expired + stale + missing + expected_lag + partial
    return {
        "schema_version": SOURCE_FRESHNESS_SCHEMA_VERSION,
        "state": state,
        "source_fresh": source_fresh,
        "checked_feature_count": checked,
        "relevant_feature_count": len(relevant),
        "blocking_feature_count": blocking,
        "expired_feature_count": len(expired),
        "stale_feature_count": len(stale),
        "missing_feature_count": len(missing),
        "expected_lag_feature_count": len(expected_lag),
        "partial_feature_count": len(partial),
        "context_only_stale_count": len(context_only_stale),
        "sample": [_feature_sample(item) for item in samples[:SOURCE_STALE_SAMPLE_LIMIT]],
        "context_only_stale_sample": [
            _feature_sample(item) for item in context_only_stale[:SOURCE_STALE_SAMPLE_LIMIT]
        ],
    }


def _relevant_feature_records(
    features: list[dict[str, Any]],
    module_id: str | None = None,
) -> list[dict[str, Any]]:
    blocking = [
        item
        for item in features
        if item.get("quality_blocking") is True
        and _is_runtime_blocking_feature(item, module_id=module_id)
    ]
    if blocking:
        return blocking
    selected = [
        item
        for item in features
        if (
            bool(item.get("selected_reason"))
            or item.get("current_run_has_value") is True
            or str(item.get("feature_run_scope") or "").startswith("current")
        )
        and _is_runtime_blocking_feature(item, module_id=module_id)
    ]
    return selected


def _is_runtime_blocking_feature(feature: dict[str, Any], module_id: str | None = None) -> bool:
    metric_id = str(feature.get("metric_id") or "")
    source_id = str(feature.get("source_id") or "")
    if feature.get("quality_blocking") is False:
        return False
    if module_id in {"trade_structure_flow", "kline_orderflow", "derivatives_crowding", "asia_risk"}:
        if source_id in FAST_CONTEXT_SOURCE_IDS:
            return False
    if not source_id and metric_id.endswith(OPTIONAL_DERIVED_SUFFIXES):
        return False
    if feature.get("available") is False and metric_id.startswith(OPTIONAL_LIVE_PREFIXES):
        return False
    if source_id.endswith("-derived") and feature.get("available") is False:
        return False
    return True


def _iter_feature_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if _looks_like_feature(value):
            records.append(value)
        for child in value.values():
            records.extend(_iter_feature_records(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_iter_feature_records(child))
    return records


def _looks_like_feature(value: dict[str, Any]) -> bool:
    keys = {
        "metric_id",
        "source_id",
        "freshness_status",
        "collection_freshness_status",
        "business_recency_status",
        "source_ts",
        "collected_at",
    }
    return bool(keys.intersection(value))


def _feature_freshness_state(feature: dict[str, Any]) -> str:
    if feature.get("available") is False:
        return "missing"
    freshness_state_value = str(feature.get("freshness_status") or "").lower()
    collection_state = str(feature.get("collection_freshness_status") or "").lower()
    business_state = str(feature.get("business_recency_status") or "").lower()
    freshness_states = [freshness_state_value, collection_state]
    if any("expired" in state or "hard_stale" in state for state in freshness_states):
        return "expired"
    if any(
        state in STALE_SOURCE_STATES or "hard_stale" in state or "failed" in state
        for state in freshness_states
    ):
        return "stale"
    if any("missing" in state or "unavailable" in state for state in freshness_states):
        return "missing"
    if "provider_stale_suspect" in business_state:
        return "stale"
    if business_state in {"expected_lag", "lagging", "outdated"}:
        return "expected_lag"
    if feature.get("is_stale") is True:
        return "partial"
    if any(state in PARTIAL_SOURCE_STATES or "partial" in state for state in freshness_states):
        return "partial"
    return "fresh"


def _feature_sample(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": feature.get("metric_id"),
        "source_id": feature.get("source_id"),
        "freshness_status": feature.get("freshness_status"),
        "collection_freshness_status": feature.get("collection_freshness_status"),
        "business_recency_status": feature.get("business_recency_status"),
        "source_ts": feature.get("source_ts"),
        "collected_at": feature.get("collected_at"),
        "available": feature.get("available"),
        "is_stale": feature.get("is_stale"),
        "quality_blocking": feature.get("quality_blocking"),
    }


def _effective_participation_policy(runtime_policy: Any, source_freshness: dict[str, Any]) -> str:
    runtime = str(runtime_policy or "full")
    state = str(source_freshness.get("state") or "fresh")
    if runtime == "disabled":
        return runtime
    if state in {"expired", "missing"}:
        return "disabled"
    if state == "stale":
        return "context_only"
    if state in {"partial", "partial_live", "expected_lag"}:
        return "quality_discounted"
    return runtime


def _aggregate_source_freshness_state(modules: list[dict[str, Any]]) -> str:
    states = [str((m.get("source_freshness") or {}).get("state") or "missing") for m in modules]
    if not states:
        return "missing"
    for state in ("expired", "stale", "missing", "partial_live", "expected_lag", "partial"):
        if state in states:
            return state
    return "fresh"
