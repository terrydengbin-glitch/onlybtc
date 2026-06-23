from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class SourceCadence:
    source_group: str
    normal_sec: int
    expectation_build_sec: int
    high_alert_sec: int
    event_lock_sec: int
    post_event_sec: int

    def interval_for_phase(self, phase: str) -> int:
        if phase == "event_lock":
            return self.event_lock_sec
        if phase in {"pre_event_high_alert", "release_pending", "release_surprise"}:
            return self.high_alert_sec
        if phase in {"post_event_reaction_check", "post_event_absorbed", "post_event_followthrough"}:
            return self.post_event_sec
        if phase in {"expectation_build", "expectation_drift_watch", "calendar_monitor"}:
            return self.expectation_build_sec
        return self.normal_sec


DEFAULT_SOURCE_CADENCE: tuple[SourceCadence, ...] = (
    SourceCadence("official_calendar", 21600, 3600, 900, 300, 900),
    SourceCadence("expectation_nowcast", 21600, 3600, 900, 300, 3600),
    SourceCadence("consensus_proxy", 21600, 3600, 900, 300, 900),
    SourceCadence("rate_probability", 3600, 900, 300, 60, 300),
    SourceCadence("fed_rss_official_text", 300, 300, 120, 60, 120),
    SourceCadence("shock_fast_lane", 180, 120, 60, 15, 60),
    SourceCadence("btc_reaction", 60, 60, 30, 10, 30),
    SourceCadence("actual_polling", 3600, 900, 300, 15, 60),
    SourceCadence("llm_speech_analyzer", 900, 600, 300, 120, 300),
)


def cadence_map(phase: str) -> dict[str, dict[str, Any]]:
    return {
        item.source_group: {
            "source_group": item.source_group,
            "interval_sec": item.interval_for_phase(phase),
            "phase": phase,
            "normal_sec": item.normal_sec,
            "expectation_build_sec": item.expectation_build_sec,
            "high_alert_sec": item.high_alert_sec,
            "event_lock_sec": item.event_lock_sec,
            "post_event_sec": item.post_event_sec,
        }
        for item in DEFAULT_SOURCE_CADENCE
    }


def phase_from_payload(payload: dict[str, Any] | None) -> str:
    if not payload:
        return "normal"
    state = payload.get("state") or {}
    active = payload.get("active_event") or {}
    state_name = str(state.get("event_window_state") or "")
    phase = str(active.get("phase") or "")
    if state_name in {
        "event_lock",
        "release_pending",
        "release_surprise",
        "post_event_reaction_check",
        "post_event_absorbed",
        "post_event_followthrough",
        "pre_event_high_alert",
        "expectation_drift_watch",
        "expectation_build",
        "calendar_monitor",
    }:
        return state_name
    if phase in {
        "event_lock",
        "high_alert",
        "post_event",
        "expectation_build",
        "calendar_awareness",
    }:
        return "pre_event_high_alert" if phase == "high_alert" else phase
    return "normal"


def initial_schedule(now: datetime | None = None, phase: str = "normal") -> dict[str, dict[str, Any]]:
    current = now or datetime.now(UTC)
    schedule: dict[str, dict[str, Any]] = {}
    for source_group, item in cadence_map(phase).items():
        schedule[source_group] = {
            **item,
            "last_attempt_at": None,
            "last_success_at": None,
            "next_due_at": current.isoformat(),
            "last_status": "pending",
            "last_fetch_id": "",
        }
    return schedule


def next_due_at(now: datetime, interval_sec: int) -> str:
    return (now + timedelta(seconds=max(interval_sec, 1))).isoformat()
