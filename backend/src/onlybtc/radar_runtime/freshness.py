from __future__ import annotations

from typing import Any


def freshness_state(
    *,
    age_sec: int | None,
    ttl_sec: int,
    hard_stale_sec: int,
    cadence_group: str,
    last_status: str = "success",
) -> dict[str, Any]:
    if last_status != "success":
        state = "failed"
    elif age_sec is None:
        state = "missing"
    elif age_sec <= ttl_sec:
        state = "fresh"
    elif age_sec <= hard_stale_sec:
        state = "stale"
    else:
        state = "hard_stale"

    if state == "fresh":
        policy = "full"
    elif state == "stale" and cadence_group == "fast":
        policy = "lower_sensitivity"
    elif state == "stale" and cadence_group == "confirmation":
        policy = "block_confirmed_signal"
    elif state == "stale":
        policy = "context_only"
    elif state in {"missing", "failed", "hard_stale"} and cadence_group == "regime":
        policy = "context_only"
    else:
        policy = "disabled"

    return {
        "freshness_state": state,
        "participation_policy": policy,
        "can_trigger": state == "fresh" and cadence_group in {"fast", "confirmation"},
        "can_confirm": state == "fresh" and cadence_group == "confirmation",
        "is_context_only": policy == "context_only",
    }

