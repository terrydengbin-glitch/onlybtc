from __future__ import annotations

from fastapi import APIRouter

from onlybtc.db.repositories import RadarRuntimeRepository
from onlybtc.db.session import database
from onlybtc.direct_trend.replay import replay_timescale_judge
from onlybtc.radar_runtime.daemon import radar_runtime_daemon
from onlybtc.radar_runtime.service import latest_module_payloads, latest_runtime_payload

router = APIRouter(prefix="/api/radar-runtime", tags=["radar-runtime"])


@router.get("/daemon/health")
def daemon_health() -> dict[str, object]:
    return {"status": "ok", "daemon": radar_runtime_daemon.health()}


@router.get("/daemon/status")
def daemon_status() -> dict[str, object]:
    database.init_schema()
    with database.session() as session:
        repo = RadarRuntimeRepository(session)
        persisted = repo.scheduler_state()
        latest_runtime = repo.latest_runtime_snapshot() or {}
    health = latest_runtime.get("health") if isinstance(latest_runtime.get("health"), dict) else {}
    cockpit = (
        latest_runtime.get("btc_runtime_cockpit")
        if isinstance(latest_runtime.get("btc_runtime_cockpit"), dict)
        else {}
    )
    return {
        "status": "ok",
        "daemon": {
            **radar_runtime_daemon.status(),
            "runtime_fresh": bool(health.get("runtime_fresh")),
            "source_fresh": bool(health.get("source_fresh")),
            "source_freshness_state": health.get("source_freshness_state"),
            "latest_runtime_snapshot_id": latest_runtime.get("runtime_snapshot_id"),
            "latest_runtime_asof_ts": latest_runtime.get("asof_ts"),
            "latest_runtime_health": health,
            "latest_runtime_cockpit_status": {
                "runtime_fresh": cockpit.get("runtime_fresh"),
                "source_fresh": cockpit.get("source_fresh"),
                "source_freshness_state": cockpit.get("source_freshness_state"),
                "headline_stage": cockpit.get("headline_stage"),
                "trend_quality": cockpit.get("trend_quality"),
            },
            "persisted_scheduler_state": persisted,
        },
    }


@router.post("/daemon/pause")
def daemon_pause() -> dict[str, object]:
    return {"status": "ok", "daemon": radar_runtime_daemon.pause()}


@router.post("/daemon/resume")
def daemon_resume() -> dict[str, object]:
    return {"status": "ok", "daemon": radar_runtime_daemon.resume()}


@router.post("/daemon/tick")
def daemon_tick() -> dict[str, object]:
    return {"status": "ok", "result": radar_runtime_daemon.scheduler_tick()}


@router.post("/run-once")
def run_once() -> dict[str, object]:
    result = radar_runtime_daemon.run_once(trigger_type="manual_full_sweep")
    return {
        "status": "ok",
        "result": result,
        "runtime": result.get("runtime"),
        "daemon": radar_runtime_daemon.health(),
    }


@router.get("/modules/latest")
def modules_latest() -> dict[str, object]:
    modules = latest_module_payloads()
    return {"status": "ok", "count": len(modules), "modules": modules}


@router.get("/cockpit/latest")
def cockpit_latest() -> dict[str, object]:
    runtime = latest_runtime_payload()
    replay = replay_timescale_judge(latest=True) or {}
    payload = replay.get("payload") or {}
    return {
        "status": "ok" if runtime else "missing",
        "runtime": runtime,
        "btc_runtime_cockpit": (runtime or {}).get("btc_runtime_cockpit"),
        "btc_timescale_judge": payload,
        "btc_timescale_replay_snapshot": {
            key: replay.get(key)
            for key in (
                "snapshot_id",
                "run_id",
                "asof_ts",
                "schema_version",
                "source_window",
                "freshness_summary",
                "fallback_used",
                "fallback_reason",
            )
        }
        if replay
        else {},
        "direct_trend_api": _direct_trend_api_contract(payload, runtime),
    }


def _direct_trend_api_contract(
    judge: dict[str, object],
    runtime: dict[str, object] | None,
) -> dict[str, object]:
    horizons = judge.get("horizons") if isinstance(judge.get("horizons"), dict) else {}
    h4 = horizons.get("4h") if isinstance(horizons.get("4h"), dict) else {}
    h1d = horizons.get("1d") if isinstance(horizons.get("1d"), dict) else {}
    health = (runtime or {}).get("health") if isinstance((runtime or {}).get("health"), dict) else {}
    return {
        "schema_version": judge.get("schema_version"),
        "snapshot_id": judge.get("snapshot_id"),
        "asof_ts": judge.get("asof_ts"),
        "runtime_fresh": health.get("runtime_fresh"),
        "source_fresh": judge.get("source_fresh"),
        "fallback_used": bool(judge.get("fallback_used")),
        "fallback_reason": judge.get("fallback_reason"),
        "freshness_summary": judge.get("freshness_summary") or {},
        "horizons": {
            "4h": _horizon_contract(h4),
            "1d": _horizon_contract(h1d),
        },
    }


def _horizon_contract(horizon: dict[str, object]) -> dict[str, object]:
    radar_context = (
        horizon.get("radar_context") if isinstance(horizon.get("radar_context"), dict) else {}
    )
    event_trust = horizon.get("event_trust") if isinstance(horizon.get("event_trust"), dict) else {}
    return {
        "state": horizon.get("state") or horizon.get("timescale_state"),
        "direct_trend_direction_score": _first_present(
            horizon,
            "direct_trend_direction_score",
            "direction_score",
        ),
        "direct_trend_acceptance_score": _first_present(
            horizon,
            "direct_trend_acceptance_score",
            "acceptance_score",
        ),
        "direct_trend_trust_score": _first_present(
            horizon,
            "direct_trend_trust_score",
            "trust_score",
        ),
        "direct_trend_display_score": horizon.get("display_score"),
        "event_trust_cap": _first_present(
            horizon,
            "event_trust_cap",
            default=event_trust.get("event_trust_cap"),
        ),
        "radar_context_bias": _first_present(
            horizon,
            "radar_context_bias",
            default=radar_context.get("bias"),
        ),
        "runtime_fresh": horizon.get("runtime_fresh"),
        "source_fresh": horizon.get("source_fresh"),
        "source_window": horizon.get("source_window") or {},
        "freshness_summary": horizon.get("freshness_summary") or {},
        "fallback_used": bool(horizon.get("fallback_used")),
        "fallback_reason": horizon.get("fallback_reason"),
    }


def _first_present(payload: dict[str, object], *keys: str, default: object = None) -> object:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return default
