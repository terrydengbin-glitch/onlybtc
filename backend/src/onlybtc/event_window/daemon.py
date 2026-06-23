from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Lock, Thread
from typing import Any

from onlybtc.core.config import get_settings
from onlybtc.db.repositories import EventWatchtowerRepository
from onlybtc.db.session import Database, database
from onlybtc.event_window.cadence import cadence_map, initial_schedule, next_due_at, phase_from_payload
from onlybtc.event_window.watchtower import EVENT_WINDOW_RUNTIME_VERSION, build_event_window_payload

STATUS_SCHEMA_VERSION = "p9.event_watchtower.status.v2"
SNAPSHOT_STALE_SECONDS = 180
TICK_STALE_SECONDS = 60
MARKET_PROBE_STALE_SECONDS = 30


class EventWatchtowerDaemon:
    def __init__(self) -> None:
        self._lock = Lock()
        self._collect_lock = Lock()
        self._status = "stopped"
        self._enabled = True
        self._last_started_at: datetime | None = None
        self._last_snapshot_id = ""
        self._last_tick_at: datetime | None = None
        self._last_full_sweep_at: datetime | None = None
        self._last_payload: dict[str, Any] | None = None
        self._last_error = ""
        self._last_tick_mode = "not_started"
        self._last_due_sources: list[str] = []
        self._last_skipped_sources: list[str] = []
        self._last_watchdog_check_at: datetime | None = None
        self._last_watchdog_recovery_at: datetime | None = None
        self._watchdog_recovery_attempt_count = 0
        self._scheduler_enabled = get_settings().event_window_scheduler_enabled
        self._cadence_profile = get_settings().event_window_cadence_profile
        self._schedule = initial_schedule(phase="normal")
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self, *, db: Database = database, auto: bool = False) -> dict[str, Any]:
        with self._lock:
            self._enabled = True
            self._status = "running"
            self._last_started_at = datetime.now(UTC)
            self._scheduler_enabled = get_settings().event_window_scheduler_enabled
        payload = self.collect_once(db=db, manual_full_sweep=True, trigger="startup_auto" if auto else "start")
        self._ensure_thread(db=db)
        return dict(self.status(), auto=auto, last_snapshot_id=payload.get("snapshot_id"))

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._enabled = False
            self._status = "stopped"
            self._stop_event.set()
        return self.status()

    def pause(self) -> dict[str, Any]:
        with self._lock:
            self._enabled = False
            self._status = "paused_by_user"
        return self.status()

    def resume(self, *, db: Database = database) -> dict[str, Any]:
        return self.start(db=db, auto=False)

    def status(self) -> dict[str, Any]:
        return self.health()

    def health(self, *, attempt_recovery: bool = True) -> dict[str, Any]:
        with self._lock:
            now = datetime.now(UTC)
            self._last_watchdog_check_at = now
            last_tick_age_sec = int((now - self._last_tick_at).total_seconds()) if self._last_tick_at else None
            last_snapshot_at = _parse_dt((self._last_payload or {}).get("asof_ts"))
            last_snapshot_age_sec = (
                int((now - last_snapshot_at).total_seconds()) if last_snapshot_at else None
            )
            last_market_probe_at = None
            if self._last_payload:
                last_market_probe_at = (
                    (self._last_payload.get("market_probe") or {}).get("collected_at")
                    or (self._last_payload.get("daemon") or {}).get("last_market_probe_at")
                )
            market_probe_age_sec = None
            parsed_market_probe = _parse_dt(last_market_probe_at)
            if parsed_market_probe:
                market_probe_age_sec = int((now - parsed_market_probe).total_seconds())
            btc_reaction_interval = int(
                (self._schedule.get("btc_reaction") or {}).get("interval_sec")
                or get_settings().event_window_scheduler_tick_seconds
                or 15
            )
            market_probe_threshold_sec = max(MARKET_PROBE_STALE_SECONDS, btc_reaction_interval * 2)
            stale_reasons: list[str] = []
            if last_tick_age_sec is None:
                stale_reasons.append("no_scheduler_tick_yet")
            elif last_tick_age_sec > TICK_STALE_SECONDS:
                stale_reasons.append("scheduler_tick_stale")
            if last_snapshot_age_sec is None:
                stale_reasons.append("no_snapshot_yet")
            elif last_snapshot_age_sec > SNAPSHOT_STALE_SECONDS:
                stale_reasons.append("event_window_snapshot_stale")
            if market_probe_age_sec is None:
                stale_reasons.append("market_probe_missing")
            elif market_probe_age_sec > market_probe_threshold_sec:
                stale_reasons.append("market_probe_stale")
            next_due_sources = [
                source_group
                for source_group, item in self._schedule.items()
                if _parse_dt(item.get("next_due_at")) and _parse_dt(item.get("next_due_at")) <= now
            ]
            health_state = self._health_state(stale_reasons)
            effective_status = health_state if health_state in {"stale", "failed", "paused_by_user"} else self._status
            watchdog = {
                "enabled": True,
                "last_check_at": self._last_watchdog_check_at.isoformat(),
                "last_recovery_at": self._last_watchdog_recovery_at.isoformat()
                if self._last_watchdog_recovery_at
                else None,
                "recovery_attempt_count": self._watchdog_recovery_attempt_count,
                "stale_reasons": stale_reasons,
                "thresholds": {
                    "last_tick_max_age_sec": TICK_STALE_SECONDS,
                    "snapshot_max_age_sec": SNAPSHOT_STALE_SECONDS,
                    "market_probe_max_age_sec": market_probe_threshold_sec,
                },
            }
            should_recover = (
                attempt_recovery
                and health_state in {"stale", "failed"}
                and self._status != "paused_by_user"
                and self._enabled
                and self._scheduler_enabled
            )
            if should_recover and not (self._thread and self._thread.is_alive()):
                self._watchdog_recovery_attempt_count += 1
                self._last_watchdog_recovery_at = now
            payload = {
                "status": effective_status,
                "raw_status": self._status,
                "health_state": health_state,
                "enabled": self._enabled,
                "scheduler_enabled": self._scheduler_enabled,
                "runtime_code_version": EVENT_WINDOW_RUNTIME_VERSION,
                "status_schema_version": STATUS_SCHEMA_VERSION,
                "last_started_at": self._last_started_at.isoformat()
                if self._last_started_at
                else None,
                "last_tick_at": self._last_tick_at.isoformat() if self._last_tick_at else None,
                "last_tick_age_sec": last_tick_age_sec,
                "last_snapshot_age_sec": last_snapshot_age_sec,
                "last_market_probe_at": last_market_probe_at,
                "market_probe_age_sec": market_probe_age_sec,
                "last_full_sweep_at": self._last_full_sweep_at.isoformat()
                if self._last_full_sweep_at
                else None,
                "last_snapshot_id": self._last_snapshot_id,
                "last_error": self._last_error,
                "last_tick_mode": self._last_tick_mode,
                "last_due_sources": self._last_due_sources,
                "last_skipped_sources": self._last_skipped_sources,
                "stale_reasons": stale_reasons,
                "watchdog": watchdog,
                "collection_mode": "standalone_daemon",
                "default_enabled": True,
                "cadence_profile": self._cadence_profile,
                "manual_full_sweep_ignores_cadence": (
                    get_settings().event_window_manual_full_sweep_ignores_cadence
                ),
                "next_due_sources": next_due_sources,
                "source_cadence": self._schedule,
            }
        if should_recover:
            self._ensure_thread(db=database)
            return self.health(attempt_recovery=False)
        return payload

    def _health_state(self, stale_reasons: list[str]) -> str:
        if self._status == "paused_by_user":
            return "paused_by_user"
        if self._status in {"stopped", "failed"}:
            return "failed"
        if self._last_error:
            return "degraded"
        if any(reason in stale_reasons for reason in {"scheduler_tick_stale", "event_window_snapshot_stale"}):
            return "stale"
        if stale_reasons:
            return "degraded"
        return "healthy"

    def collect_once(
        self,
        *,
        db: Database = database,
        manual_full_sweep: bool = False,
        trigger: str = "manual_collect_once",
        due_source_groups: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            status = self._status if self._status != "stopped" else "running"
            enabled = self._enabled
            scheduler_enabled = self._scheduler_enabled
        self._collect_lock.acquire()
        try:
            due_groups_for_builder = None if manual_full_sweep else list(due_source_groups or [])
            previous_payload = None if manual_full_sweep else self._last_payload
            payload = build_event_window_payload(
                daemon_status=status,
                daemon_enabled=enabled,
                due_source_groups=due_groups_for_builder,
                previous_payload=previous_payload,
                trigger=trigger,
            )
            now = _parse_dt(payload.get("asof_ts")) or datetime.now(UTC)
            with self._lock:
                self._last_tick_at = now
                if manual_full_sweep:
                    self._last_full_sweep_at = now
                phase = phase_from_payload(payload)
                due_groups = list(self._schedule) if manual_full_sweep else list(due_source_groups or [])
                skipped_groups = sorted(set(self._schedule) - set(due_groups))
                self._last_tick_mode = (
                    "manual_full_sweep"
                    if manual_full_sweep and trigger != "startup_auto"
                    else "bootstrap_full_sweep"
                    if manual_full_sweep
                    else "scheduled_due_tick"
                )
                self._last_due_sources = list(due_groups)
                self._last_skipped_sources = [] if manual_full_sweep else skipped_groups
                cadence = cadence_map(phase)
                for source_group, cadence_item in cadence.items():
                    existing = self._schedule.get(source_group, {})
                    interval_sec = int(cadence_item.get("interval_sec") or 300)
                    if manual_full_sweep or source_group in due_groups:
                        self._schedule[source_group] = {
                            **cadence_item,
                            "cadence_profile": self._cadence_profile,
                            "last_attempt_at": now.isoformat(),
                            "last_success_at": now.isoformat(),
                            "next_due_at": next_due_at(now, interval_sec),
                            "last_status": "success",
                            "last_fetch_id": payload.get("snapshot_id", ""),
                        }
                    else:
                        self._schedule[source_group] = {
                            **cadence_item,
                            "cadence_profile": self._cadence_profile,
                            "last_attempt_at": existing.get("last_attempt_at"),
                            "last_success_at": existing.get("last_success_at"),
                            "next_due_at": existing.get("next_due_at") or next_due_at(now, interval_sec),
                            "last_status": existing.get("last_status", "pending"),
                            "last_fetch_id": existing.get("last_fetch_id", ""),
                        }
                daemon_meta = payload.setdefault("daemon", {})
                daemon_meta.update(
                    {
                        "status": status,
                        "enabled": enabled,
                        "scheduler_enabled": scheduler_enabled,
                        "collection_mode": "standalone_daemon",
                        "trigger": trigger,
                        "last_tick_mode": self._last_tick_mode,
                        "manual_full_sweep": manual_full_sweep,
                        "due_source_groups": due_groups,
                        "skipped_source_groups": self._last_skipped_sources,
                        "last_tick_at": self._last_tick_at.isoformat(),
                        "last_full_sweep_at": self._last_full_sweep_at.isoformat()
                        if self._last_full_sweep_at
                        else None,
                        "cadence_profile": self._cadence_profile,
                        "source_cadence": self._schedule,
                        "next_due_sources": self._due_source_groups(now),
                    }
                )
            db.init_schema()
            with db.session() as session:
                repo = EventWatchtowerRepository(session)
                saved = repo.save_snapshot(payload)
                repo.upsert_scheduler_state(self._schedule, cadence_profile=self._cadence_profile)
            with self._lock:
                self._last_snapshot_id = str(saved.get("snapshot_id") or "")
                self._last_payload = saved
                self._last_error = ""
            return saved
        finally:
            self._collect_lock.release()

    def scheduler_tick(self, *, db: Database = database) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._lock:
            self._last_tick_at = now
        with self._lock:
            if not self._enabled or self._status == "paused_by_user":
                paused = True
            else:
                paused = False
            if paused:
                due: list[str] = []
            else:
                due = self._due_source_groups(now)
        if paused:
            with self._lock:
                self._last_tick_mode = "scheduler_paused"
                self._last_due_sources = []
                self._last_skipped_sources = sorted(self._schedule)
            return {"ran": False, "reason": "daemon_paused", "daemon": self.status()}
        if not due:
            with self._lock:
                self._last_tick_mode = "scheduled_noop"
                self._last_due_sources = []
                self._last_skipped_sources = sorted(self._schedule)
            return {"ran": False, "reason": "nothing_due", "daemon": self.status()}
        payload = self.collect_once(
            db=db,
            manual_full_sweep=False,
            trigger="scheduler_tick",
            due_source_groups=due,
        )
        return {"ran": True, "due_source_groups": due, "snapshot_id": payload.get("snapshot_id")}

    def _due_source_groups(self, now: datetime) -> list[str]:
        due: list[str] = []
        for source_group, item in self._schedule.items():
            next_due = _parse_dt(item.get("next_due_at"))
            if next_due is None or next_due <= now:
                due.append(source_group)
        return due

    def _ensure_thread(self, *, db: Database) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._scheduler_loop,
            kwargs={"db": db},
            daemon=True,
            name="event-watchtower-scheduler",
        )
        self._thread.start()

    def _scheduler_loop(self, *, db: Database) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    should_run = self._enabled and self._scheduler_enabled and self._status == "running"
                if should_run:
                    self.scheduler_tick(db=db)
            except Exception:
                with self._lock:
                    self._status = "degraded"
                    self._last_error = "scheduler_tick_failed"
            self._stop_event.wait(get_settings().event_window_scheduler_tick_seconds)


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


event_watchtower_daemon = EventWatchtowerDaemon()
