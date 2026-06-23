from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event, Lock, Thread
from typing import Any

from onlybtc.db.repositories import RadarRuntimeRepository
from onlybtc.db.session import Database, database
from onlybtc.radar_runtime.audit_report import generate_radar_runtime_audit_report
from onlybtc.radar_runtime.profile import due_modules, initial_schedule, next_due_at
from onlybtc.radar_runtime.service import build_runtime_snapshot, run_full_sweep, run_incremental_modules

STATUS_SCHEMA_VERSION = "p9.radar_runtime.status.v1"
TICK_SECONDS = 15
TICK_STALE_SECONDS = 90
SNAPSHOT_STALE_SECONDS = 420
AUDIT_HTML_REFRESH_SECONDS = 300


class RadarRuntimeDaemon:
    def __init__(
        self,
        *,
        audit_generator: Callable[..., dict[str, Any]] = generate_radar_runtime_audit_report,
        audit_refresh_seconds: int = AUDIT_HTML_REFRESH_SECONDS,
    ) -> None:
        self._lock = Lock()
        self._collect_lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._status = "stopped"
        self._enabled = True
        self._scheduler_enabled = True
        self._last_started_at: datetime | None = None
        self._last_tick_at: datetime | None = None
        self._last_full_sweep_at: datetime | None = None
        self._last_snapshot_id = ""
        self._last_error = ""
        self._schedule = initial_schedule()
        self._audit_generator = audit_generator
        self._audit_refresh_seconds = audit_refresh_seconds
        self._last_audit_html_generated_at: datetime | None = None
        self._last_audit_html_snapshot_id = ""
        self._last_audit_html_refresh_mode = ""
        self._last_audit_html_error = ""
        self._last_audit_health_state = ""
        self._last_audit_stale_signature = ""

    def start(self, *, db: Database = database, auto: bool = False) -> dict[str, Any]:
        with self._lock:
            self._enabled = True
            self._status = "running"
            self._last_started_at = datetime.now(UTC)
        try:
            payload = self.run_once(db=db, trigger_type="startup_auto" if auto else "start")
            self._last_snapshot_id = str(payload.get("snapshot_id") or "")
        except Exception as exc:
            with self._lock:
                self._status = "degraded"
                self._last_error = str(exc)
        self._ensure_thread(db=db)
        return self.health()

    def pause(self) -> dict[str, Any]:
        with self._lock:
            self._enabled = False
            self._status = "paused_by_user"
        return self.health()

    def resume(self, *, db: Database = database) -> dict[str, Any]:
        return self.start(db=db, auto=False)

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._enabled = False
            self._status = "stopped"
            self._stop_event.set()
        return self.health()

    def status(self) -> dict[str, Any]:
        return self.health()

    def health(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._lock:
            last_tick_age = int((now - self._last_tick_at).total_seconds()) if self._last_tick_at else None
            last_snapshot_age = None
            if self._last_snapshot_id:
                last_snapshot_age = last_tick_age
            stale_reasons: list[str] = []
            if last_tick_age is None:
                stale_reasons.append("no_scheduler_tick_yet")
            elif last_tick_age > TICK_STALE_SECONDS:
                stale_reasons.append("scheduler_tick_stale")
            if self._last_snapshot_id and last_snapshot_age and last_snapshot_age > SNAPSHOT_STALE_SECONDS:
                stale_reasons.append("radar_runtime_snapshot_stale")
            if self._last_error:
                health_state = "degraded"
            elif self._status in {"stopped", "failed"}:
                health_state = "failed"
            elif self._status == "paused_by_user":
                health_state = "paused_by_user"
            elif stale_reasons:
                health_state = "stale"
            else:
                health_state = "healthy"
            next_due = due_modules(self._schedule, now)
            sqlite_lock_state = (
                "degraded"
                if "database is locked" in str(self._last_error).lower()
                else "ok"
            )
            return {
                "status": health_state if health_state in {"stale", "failed"} else self._status,
                "raw_status": self._status,
                "health_state": health_state,
                "enabled": self._enabled,
                "scheduler_enabled": self._scheduler_enabled,
                "status_schema_version": STATUS_SCHEMA_VERSION,
                "collection_mode": "standalone_radar_runtime_daemon",
                "last_started_at": self._last_started_at.isoformat() if self._last_started_at else None,
                "last_tick_at": self._last_tick_at.isoformat() if self._last_tick_at else None,
                "last_tick_age_sec": last_tick_age,
                "last_full_sweep_at": self._last_full_sweep_at.isoformat() if self._last_full_sweep_at else None,
                "last_snapshot_id": self._last_snapshot_id,
                "last_error": self._last_error,
                "runtime_fresh": not stale_reasons and not self._last_error,
                "source_fresh": None,
                "sqlite_lock_state": sqlite_lock_state,
                "last_audit_html_generated_at": (
                    self._last_audit_html_generated_at.isoformat()
                    if self._last_audit_html_generated_at
                    else None
                ),
                "last_audit_html_snapshot_id": self._last_audit_html_snapshot_id,
                "last_audit_html_refresh_mode": self._last_audit_html_refresh_mode,
                "last_audit_html_error": self._last_audit_html_error,
                "audit_html_refresh_seconds": self._audit_refresh_seconds,
                "stale_reasons": stale_reasons,
                "next_due_modules": next_due,
                "module_cadence": self._schedule,
                "watchdog": {
                    "enabled": True,
                    "thresholds": {
                        "last_tick_max_age_sec": TICK_STALE_SECONDS,
                        "snapshot_max_age_sec": SNAPSHOT_STALE_SECONDS,
                    },
                    "stale_reasons": stale_reasons,
                },
            }

    def run_once(self, *, db: Database = database, trigger_type: str = "manual_full_sweep") -> dict[str, Any]:
        with self._collect_lock:
            result = run_full_sweep(trigger_type=trigger_type, db=db)
            now = datetime.now(UTC)
            with self._lock:
                self._last_tick_at = now
                self._last_full_sweep_at = now
                self._last_snapshot_id = str(result.get("snapshot_id") or "")
                self._last_error = ""
                self._mark_success(list(self._schedule), now, self._last_snapshot_id)
            self._persist_schedule(db)
            self._maybe_generate_audit_html(
                db=db,
                refresh_mode="manual_run_once" if trigger_type == "manual_full_sweep" else "bootstrap",
                force=True,
            )
            return result

    def scheduler_tick(self, *, db: Database = database) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._lock:
            self._last_tick_at = now
            if not self._enabled or self._status == "paused_by_user":
                paused = True
                due: list[str] = []
            else:
                paused = False
                due = due_modules(self._schedule, now)
        if paused:
            return {"ran": False, "reason": "daemon_paused", "daemon": self.health()}
        if not due:
            runtime = build_runtime_snapshot(trigger_type="scheduler_tick_noop", db=db)
            with self._lock:
                self._last_snapshot_id = str(runtime.get("runtime_snapshot_id") or self._last_snapshot_id)
            audit = self._maybe_generate_audit_html(db=db, refresh_mode="scheduled")
            return {
                "ran": False,
                "reason": "nothing_due",
                "snapshot_id": self._last_snapshot_id,
                "audit_html": audit,
            }
        with self._collect_lock:
            run_incremental_modules(due, trigger_type="scheduler_tick", db=db)
            runtime = build_runtime_snapshot(trigger_type="scheduler_tick", db=db)
            with self._lock:
                self._last_snapshot_id = str(runtime.get("runtime_snapshot_id") or "")
                self._last_error = ""
                self._mark_success(due, now, self._last_snapshot_id)
            self._persist_schedule(db)
            audit = self._maybe_generate_audit_html(db=db, refresh_mode="scheduled")
            return {
                "ran": True,
                "due_modules": due,
                "snapshot_id": self._last_snapshot_id,
                "audit_html": audit,
            }

    def _mark_success(self, modules: list[str], now: datetime, snapshot_id: str) -> None:
        for module_name in modules:
            item = self._schedule.get(module_name)
            if not item:
                continue
            interval = int(item.get("interval_sec") or 300)
            self._schedule[module_name] = {
                **item,
                "last_attempt_at": now.isoformat(),
                "last_success_at": now.isoformat(),
                "next_due_at": next_due_at(now, interval),
                "last_status": "success",
                "last_snapshot_id": snapshot_id,
            }

    def _persist_schedule(self, db: Database) -> None:
        db.init_schema()
        with db.session() as session:
            RadarRuntimeRepository(session).upsert_scheduler_state(self._schedule)

    def _maybe_generate_audit_html(
        self,
        *,
        db: Database,
        refresh_mode: str,
        force: bool = False,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        health = self.health()
        current_health_state = str(health.get("health_state") or "")
        stale_signature = "|".join(str(item) for item in health.get("stale_reasons") or [])
        with self._lock:
            interval_due = (
                self._last_audit_html_generated_at is None
                or (now - self._last_audit_html_generated_at).total_seconds()
                >= self._audit_refresh_seconds
            )
            health_transition = (
                bool(self._last_audit_health_state)
                and self._last_audit_health_state == "healthy"
                and current_health_state in {"degraded", "stale", "failed"}
            )
            stale_transition = (
                bool(stale_signature)
                and stale_signature != self._last_audit_stale_signature
            )
            should_generate = force or interval_due or health_transition or stale_transition
        if not should_generate:
            return {"generated": False, "reason": "not_due"}
        effective_mode = refresh_mode
        if not force and health_transition:
            effective_mode = "health_transition"
        elif not force and stale_transition:
            effective_mode = "watchdog"
        try:
            report = self._audit_generator(db=db, refresh_mode=effective_mode)
        except Exception as exc:  # pragma: no cover - exact generator failures are covered by daemon state.
            with self._lock:
                self._last_audit_html_error = str(exc)
                self._last_audit_health_state = current_health_state
                self._last_audit_stale_signature = stale_signature
            return {"generated": False, "reason": "generator_failed", "error": str(exc)}
        generated_at = _parse_dt(report.get("generated_at")) or now
        with self._lock:
            self._last_audit_html_generated_at = generated_at
            self._last_audit_html_snapshot_id = str(report.get("runtime_snapshot_id") or "")
            self._last_audit_html_refresh_mode = effective_mode
            self._last_audit_html_error = ""
            self._last_audit_health_state = current_health_state
            self._last_audit_stale_signature = stale_signature
        return {
            "generated": True,
            "refresh_mode": effective_mode,
            "runtime_snapshot_id": report.get("runtime_snapshot_id"),
            "generated_at": report.get("generated_at"),
        }

    def _ensure_thread(self, *, db: Database) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._scheduler_loop,
            kwargs={"db": db},
            daemon=True,
            name="radar-runtime-scheduler",
        )
        self._thread.start()

    def _scheduler_loop(self, *, db: Database) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    should_run = self._enabled and self._scheduler_enabled and self._status == "running"
                if should_run:
                    self.scheduler_tick(db=db)
            except Exception as exc:
                with self._lock:
                    self._status = "degraded"
                    self._last_error = str(exc)
                self._maybe_generate_audit_html(db=db, refresh_mode="error", force=True)
            self._stop_event.wait(TICK_SECONDS)


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


radar_runtime_daemon = RadarRuntimeDaemon()
