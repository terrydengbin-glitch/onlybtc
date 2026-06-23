from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from onlybtc.api.contracts import ok_response
from onlybtc.db.repositories import EventWatchtowerRepository
from onlybtc.db.session import database
from onlybtc.event_window import EVENT_WINDOW_SCHEMA_VERSION, event_watchtower_daemon

router = APIRouter(prefix="/api/event-window", tags=["event-window"])
SOURCE_DIAGNOSTICS_SCHEMA_VERSION = "p45.event_window.source_diagnostics.v1"


def _latest_or_collect() -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        latest = EventWatchtowerRepository(session).latest_snapshot()
    if latest is not None:
        return latest
    return event_watchtower_daemon.collect_once()


def _payload_for_api(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    fallback = dict(payload.get("shock_fast_lane") or {})
    existing_llm = fallback.get("llm_analysis")
    if not _is_deepseek_success(existing_llm):
        recent_llm = _recent_deepseek_shock_llm(payload)
        if recent_llm:
            fallback["llm_analysis"] = recent_llm
    normalized["shock_fast_lane"] = _normalize_shock_fast_lane(
        None,
        fallback=fallback,
        latest_item_from_sqlite=False,
    )
    return normalized


def _is_deepseek_success(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return str(value.get("provider") or "").lower() == "deepseek" and str(
        value.get("status") or ""
    ).lower() == "success"


def _recent_deepseek_shock_llm(payload: dict[str, Any]) -> dict[str, Any] | None:
    current_lane = payload.get("shock_fast_lane") or {}
    current_type = str(current_lane.get("shock_type") or "")
    current_window = str((current_lane.get("evidence") or {}).get("primary_window") or "")
    database.init_schema()
    with database.session() as session:
        snapshots = EventWatchtowerRepository(session).list_snapshots(limit=40)
    for snapshot in snapshots:
        lane = snapshot.get("shock_fast_lane") or {}
        llm = lane.get("llm_analysis")
        if not _is_deepseek_success(llm):
            continue
        snapshot_type = str(lane.get("shock_type") or "")
        snapshot_window = str((lane.get("evidence") or {}).get("primary_window") or "")
        if current_type and snapshot_type and current_type != snapshot_type:
            continue
        if current_window and snapshot_window and current_window != snapshot_window:
            continue
        reused = dict(llm)
        reused["analysis_source"] = "recent_snapshot_deepseek"
        reused["source_snapshot_id"] = snapshot.get("snapshot_id")
        reused["source_asof_ts"] = snapshot.get("asof_ts")
        return reused
    return None


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _event_phase(time_to_event_sec: int) -> str:
    if -7200 <= time_to_event_sec <= 7200:
        return "event_lock"
    if 0 < time_to_event_sec <= 86400:
        return "high_alert"
    if 0 < time_to_event_sec <= 7 * 86400:
        return "expectation_build"
    if time_to_event_sec < -7200:
        return "post_event"
    return "calendar_awareness"


def _enrich_calendar_items(items: list[dict[str, Any]], *, asof: datetime) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        release_ts = _parse_ts(
            item.get("release_time_utc") or item.get("release_time") or item.get("release_time_et")
        )
        if release_ts is None:
            item.setdefault("time_to_event_sec", None)
            item.setdefault("phase", "calendar_unknown")
            enriched.append(item)
            continue
        time_to_event_sec = int((release_ts - asof).total_seconds())
        item["release_time"] = release_ts.isoformat()
        item["release_time_utc"] = release_ts.isoformat()
        item["time_to_event_sec"] = time_to_event_sec
        item["phase"] = item.get("phase") or _event_phase(time_to_event_sec)
        enriched.append(item)
    return sorted(
        enriched,
        key=lambda item: (
            _parse_ts(item.get("release_time_utc") or item.get("release_time")) or datetime.max.replace(tzinfo=UTC)
        ),
    )


def _normalize_shock_fast_lane(
    item: dict[str, Any] | None,
    *,
    fallback: dict[str, Any] | None = None,
    latest_item_from_sqlite: bool = False,
) -> dict[str, Any]:
    fallback = dict(fallback or {})
    raw = dict(item or {})
    source = raw or fallback
    evidence = source.get("evidence")
    if not isinstance(evidence, (dict, list)):
        evidence = {}
    shock_detected = bool(raw) or bool(fallback.get("shock_detected"))
    emergency_level = str(source.get("emergency_level") or ("watch" if shock_detected else "none"))
    confirmation_level = str(source.get("confirmation_level") or ("single_source" if shock_detected else "none"))
    summary = str(
        source.get("summary")
        or source.get("raw_title")
        or fallback.get("summary")
        or ("No active shock detected." if not shock_detected else "Shock item detected.")
    )
    llm_analysis = source.get("llm_analysis") or fallback.get("llm_analysis") or {}
    if not isinstance(llm_analysis, dict):
        llm_analysis = {}
    if not llm_analysis:
        llm_analysis = {
            "provider": "deterministic",
            "status": "pending" if not shock_detected else "success",
            "summary_zh": (
                "当前没有确认的突发冲击，Shock Fast Lane 维持监控状态。"
                if not shock_detected
                else f"检测到 {source.get('shock_type', 'unknown')} 突发冲击，事件窗口覆盖层已接管普通雷达信任。"
            ),
            "risk_reason_zh": "该说明来自结构化 shock payload，不读取审计 HTML 文件。",
            "action_boundary_zh": "只解释事件窗口覆盖层，不改变 BTC score、radar score 或趋势方向。",
            "boundary_pass": True,
        }
    llm_analysis = _sanitize_shock_llm_analysis(llm_analysis, source, shock_detected=shock_detected)
    return {
        "shock_detected": shock_detected,
        "shock_type": str(source.get("shock_type") or ("unknown" if shock_detected else "none")),
        "emergency_level": emergency_level,
        "confirmation_level": confirmation_level,
        "source_count": int(source.get("source_count") or 0),
        "market_dislocation": bool(source.get("market_dislocation")),
        "btc_microstructure_confirmation": bool(source.get("btc_microstructure_confirmation")),
        "rumor_risk": bool(source.get("rumor_risk")),
        "reason_codes": list(source.get("reason_codes") or []),
        "evidence": evidence,
        "summary": summary,
        "llm_analysis": llm_analysis,
        "latest_item": raw,
        "latest_item_from_sqlite": latest_item_from_sqlite,
    }


def _sanitize_shock_llm_analysis(
    llm_analysis: dict[str, Any],
    source: dict[str, Any],
    *,
    shock_detected: bool,
) -> dict[str, Any]:
    summary_zh = str(llm_analysis.get("summary_zh") or "")
    has_mojibake = any(marker in summary_zh for marker in ("褰", "妫", "绐", "閫"))
    if not has_mojibake and llm_analysis.get("summary_zh"):
        llm_analysis.setdefault("boundary_pass", llm_analysis.get("boundary_passed", True))
        llm_analysis.setdefault("analysis_source", "snapshot_payload")
        return llm_analysis
    if not shock_detected:
        return {
            "provider": "deterministic",
            "status": "pending",
            "summary_zh": "当前没有确认的突发冲击，Shock Fast Lane 维持监控状态。",
            "risk_reason_zh": "官方突发、可信来源数量和 BTC 市场错位证据尚未达到触发阈值。",
            "action_boundary_zh": "该区块只解释事件窗口覆盖层，不改变 BTC score、radar score 或趋势方向。",
            "boundary_pass": True,
            "analysis_source": "api_fallback",
        }
    evidence = source.get("evidence") or {}
    primary = str(evidence.get("primary_window") or "market")
    try:
        primary_return = float(evidence.get("primary_return") or 0.0)
    except (TypeError, ValueError):
        primary_return = 0.0
    direction_word = "下跌" if primary_return < 0 else "上涨"
    shock_type = str(source.get("shock_type") or "unknown")
    level = str(source.get("emergency_level") or "watch")
    confirmation = str(source.get("confirmation_level") or "none")
    return {
        "provider": "deterministic",
        "status": "success",
        "summary_zh": f"检测到 {shock_type} 突发冲击，事件窗口覆盖层已接管普通雷达信任。",
        "risk_reason_zh": (
            f"主要证据来自 {primary} 窗口的 BTC 市场{direction_word}错位，"
            f"事件等级为 {level}，确认方式为 {confirmation}。"
        ),
        "action_boundary_zh": "只解释事件窗口覆盖层，不改变 BTC score、radar score 或趋势方向。",
        "boundary_pass": True,
        "analysis_source": "api_fallback",
    }


@router.get("/latest")
def latest() -> dict[str, Any]:
    return ok_response(
        {"event_window": _payload_for_api(_latest_or_collect())},
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/active")
def active() -> dict[str, Any]:
    payload = _latest_or_collect()
    return ok_response(
        {
            "active_event": payload.get("active_event") or {},
            "state": payload.get("state") or {},
            "overlay": payload.get("overlay") or {},
        },
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/shock-lane/latest")
def shock_lane_latest() -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        repo = EventWatchtowerRepository(session)
        latest_shock = repo.latest_shock()
        latest_snapshot = repo.latest_snapshot() or {}
    fallback = latest_snapshot.get("shock_fast_lane") or {}
    if not _is_deepseek_success(fallback.get("llm_analysis")):
        recent_llm = _recent_deepseek_shock_llm(latest_snapshot)
        if recent_llm:
            fallback = dict(fallback)
            fallback["llm_analysis"] = recent_llm
    return ok_response(
        {
            "shock_fast_lane": _normalize_shock_fast_lane(
                latest_shock,
                fallback=fallback,
                latest_item_from_sqlite=bool(latest_shock),
            )
        },
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/shock-lane/history")
def shock_lane_history(limit: int = 100) -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).list_shocks(limit=limit)
    return ok_response(
        {"count": len(items), "items": items}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.get("/market-probe/latest")
def market_probe_latest() -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        probe = EventWatchtowerRepository(session).latest_market_probe()
    return ok_response(
        {"market_probe": probe or (_latest_or_collect().get("market_probe") or {})},
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/market-probe/history")
def market_probe_history(limit: int = 100) -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).list_market_probes(limit=limit)
    return ok_response(
        {"count": len(items), "items": items},
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/history")
def history(limit: int = 100) -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).list_snapshots(limit=limit)
    return ok_response(
        {"count": len(items), "items": items}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.get("/post-event-reaction")
def post_event_reaction(event_id: str | None = None, limit: int = 100) -> dict[str, Any]:
    payload = _latest_or_collect()
    if event_id:
        database.init_schema()
        with database.session() as session:
            items = EventWatchtowerRepository(session).event_reactions(event_id, limit=limit)
        return ok_response(
            {"event_id": event_id, "count": len(items), "items": items},
            schema_version=EVENT_WINDOW_SCHEMA_VERSION,
        )
    return ok_response(
        {"post_event_reaction": payload.get("post_event_reaction") or {}},
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/calendar")
def calendar(limit: int = 100) -> dict[str, Any]:
    payload = _latest_or_collect()
    asof = _parse_ts(payload.get("asof_ts")) or datetime.now(UTC)
    snapshot_items = [dict(item) for item in (payload.get("calendar_items") or [])]
    if snapshot_items:
        items = _enrich_calendar_items(snapshot_items, asof=asof)[:limit]
        return ok_response(
            {
                "count": len(items),
                "items": items,
                "snapshot_id": payload.get("snapshot_id"),
                "asof_ts": asof.isoformat(),
                "source": "latest_snapshot",
            },
            schema_version=EVENT_WINDOW_SCHEMA_VERSION,
        )
    database.init_schema()
    with database.session() as session:
        persisted = EventWatchtowerRepository(session).list_calendar(limit=limit)
    items = _enrich_calendar_items(persisted, asof=asof)[:limit]
    return ok_response(
        {
            "count": len(items),
            "items": items,
            "snapshot_id": payload.get("snapshot_id"),
            "asof_ts": asof.isoformat(),
            "source": "persisted_calendar_fallback",
        },
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/timeline")
def timeline(limit: int = 200) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).timeline(limit=limit)
    return ok_response(
        {"count": len(items), "items": items}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.get("/events/{event_id}")
def event_detail(event_id: str) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        item = EventWatchtowerRepository(session).get_event(event_id)
    if item is None:
        raise HTTPException(status_code=404, detail="event not found")
    return ok_response({"event": item}, schema_version=EVENT_WINDOW_SCHEMA_VERSION)


@router.get("/events/{event_id}/expectations")
def event_expectations(event_id: str, limit: int = 200) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).event_expectations(event_id, limit=limit)
    return ok_response(
        {"event_id": event_id, "count": len(items), "items": items},
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/events/{event_id}/reaction")
def event_reaction(event_id: str, limit: int = 200) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).event_reactions(event_id, limit=limit)
    return ok_response(
        {"event_id": event_id, "count": len(items), "items": items},
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/speeches")
def speeches(limit: int = 100) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).list_speeches(limit=limit)
    return ok_response(
        {"count": len(items), "items": items}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.get("/sources/status")
def source_status() -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        diagnostics = EventWatchtowerRepository(session).source_diagnostics()
    return ok_response(diagnostics, schema_version=SOURCE_DIAGNOSTICS_SCHEMA_VERSION)


@router.get("/sources/fetches")
def source_fetches(limit: int = 100) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).list_source_fetches(limit=limit)
    return ok_response(
        {"count": len(items), "items": items},
        schema_version=SOURCE_DIAGNOSTICS_SCHEMA_VERSION,
    )


@router.get("/sources/{source_id}")
def source_detail(source_id: str, limit: int = 100) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        repo = EventWatchtowerRepository(session)
        diagnostics = repo.source_diagnostics()
        fetches = repo.list_source_fetches(source_id=source_id, limit=limit)
    source = next(
        (item for item in diagnostics.get("sources", []) if item.get("source_id") == source_id),
        None,
    )
    if source is None and not fetches:
        raise HTTPException(status_code=404, detail="source not found")
    return ok_response(
        {"source": source or {"source_id": source_id}, "fetches": fetches},
        schema_version=SOURCE_DIAGNOSTICS_SCHEMA_VERSION,
    )


@router.get("/speeches/{text_id}")
def speech_detail(text_id: str) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        item = EventWatchtowerRepository(session).get_speech(text_id)
    if item is None:
        raise HTTPException(status_code=404, detail="speech not found")
    return ok_response({"speech": item}, schema_version=EVENT_WINDOW_SCHEMA_VERSION)


@router.get("/alerts")
def alerts(status: str | None = None, limit: int = 100) -> dict[str, Any]:
    _latest_or_collect()
    database.init_schema()
    with database.session() as session:
        items = EventWatchtowerRepository(session).list_alerts(status=status, limit=limit)
    return ok_response(
        {"count": len(items), "items": items}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: str) -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        item = EventWatchtowerRepository(session).ack_alert(alert_id)
    if item is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return ok_response({"alert": item}, schema_version=EVENT_WINDOW_SCHEMA_VERSION)


@router.post("/alerts/{alert_id}/mute")
def mute_alert(alert_id: str, minutes: int = 60) -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        item = EventWatchtowerRepository(session).mute_alert(
            alert_id,
            datetime.now(UTC) + timedelta(minutes=max(minutes, 1)),
        )
    if item is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return ok_response({"alert": item}, schema_version=EVENT_WINDOW_SCHEMA_VERSION)


@router.get("/daemon/status")
def daemon_status() -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        repo = EventWatchtowerRepository(session)
        scheduler_state = repo.scheduler_state()
        latest_probe = repo.latest_market_probe()
    return ok_response(
        {
            "daemon": dict(
                event_watchtower_daemon.status(),
                persisted_scheduler_state=scheduler_state,
                persisted_latest_market_probe=latest_probe or {},
            )
        },
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/daemon/health")
def daemon_health() -> dict[str, Any]:
    database.init_schema()
    with database.session() as session:
        repo = EventWatchtowerRepository(session)
        scheduler_state = repo.scheduler_state()
        latest_probe = repo.latest_market_probe()
    health_payload = dict(
        event_watchtower_daemon.health(),
        persisted_scheduler_state=scheduler_state,
        persisted_latest_market_probe=latest_probe or {},
    )
    return ok_response(
        {
            "healthy": health_payload.get("health_state") == "healthy",
            "daemon": health_payload,
            "watchdog": health_payload.get("watchdog") or {},
            "runtime_code_version": health_payload.get("runtime_code_version"),
        },
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    status = event_watchtower_daemon.health()
    healthy = status.get("health_state") == "healthy"
    return ok_response(
        {
            "healthy": healthy,
            "daemon": status,
            "runtime_code_version": status.get("runtime_code_version"),
        },
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.post("/run-once")
def run_once() -> dict[str, Any]:
    payload = event_watchtower_daemon.collect_once(
        manual_full_sweep=True,
        trigger="manual_event_window_run_once",
    )
    return ok_response(
        {
            "event_window": payload,
            "daemon": event_watchtower_daemon.status(),
            "manual_full_sweep": True,
            "snapshot_id": payload.get("snapshot_id"),
            "asof_ts": payload.get("asof_ts"),
        },
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.post("/daemon/tick")
def daemon_tick() -> dict[str, Any]:
    return ok_response(
        {"tick": event_watchtower_daemon.scheduler_tick(), "daemon": event_watchtower_daemon.status()},
        schema_version=EVENT_WINDOW_SCHEMA_VERSION,
    )


@router.post("/audit-bundle/run")
def audit_bundle_run() -> dict[str, Any]:
    result = _run_audit_bundle()
    return ok_response({"audit_bundle": result}, schema_version=EVENT_WINDOW_SCHEMA_VERSION)


@router.get("/audit-bundle/latest")
def audit_bundle_latest() -> dict[str, Any]:
    result = _evaluate_audit_bundle()
    return ok_response({"audit_bundle": result}, schema_version=EVENT_WINDOW_SCHEMA_VERSION)


@router.post("/daemon/start")
def daemon_start() -> dict[str, Any]:
    return ok_response(
        {"daemon": event_watchtower_daemon.start()}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.post("/daemon/stop")
def daemon_stop() -> dict[str, Any]:
    return ok_response(
        {"daemon": event_watchtower_daemon.stop()}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.post("/daemon/pause")
def daemon_pause() -> dict[str, Any]:
    return ok_response(
        {"daemon": event_watchtower_daemon.pause()}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


@router.post("/daemon/resume")
def daemon_resume() -> dict[str, Any]:
    return ok_response(
        {"daemon": event_watchtower_daemon.resume()}, schema_version=EVENT_WINDOW_SCHEMA_VERSION
    )


def _run_audit_bundle() -> dict[str, Any]:
    script_path = Path(__file__).resolve().parents[4] / "scripts" / "run_event_window_audit_bundle.py"
    spec = importlib.util.spec_from_file_location("run_event_window_audit_bundle", script_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=500, detail="audit bundle runner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_bundle()


def _evaluate_audit_bundle() -> dict[str, Any]:
    script_path = Path(__file__).resolve().parents[4] / "scripts" / "run_event_window_audit_bundle.py"
    spec = importlib.util.spec_from_file_location("run_event_window_audit_bundle", script_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=500, detail="audit bundle runner unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate_latest_bundle()
