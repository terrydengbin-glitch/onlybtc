from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from onlybtc.radars.registry import RADAR_MODULES

SCHEMA_VERSION = "p1.c72.radar_cadence_profile.v1"

FAST_MODULES = {"kline_orderflow", "trade_structure_flow", "derivatives_crowding", "asia_risk"}
CONFIRMATION_MODULES = {"fund_flow", "treasury_credit", "macro_radar", "dollar_liquidity"}
REGIME_MODULES = {
    "onchain_valuation",
    "btc_adoption",
    "crypto_breadth",
    "options_volatility",
    "event_policy",
    "btc_total_state",
}


def cadence_profile() -> list[dict[str, Any]]:
    profile: list[dict[str, Any]] = []
    for module in RADAR_MODULES:
        module_id = module.module_id
        if module_id in FAST_MODULES:
            group = "fast"
            interval = 60
            ttl = 180
            hard = 420
            horizon = "4h_24h"
            freshness_role = "trigger_eligible"
        elif module_id in CONFIRMATION_MODULES:
            group = "confirmation"
            interval = 300
            ttl = 900
            hard = 1800
            horizon = "24h_3d"
            freshness_role = "confirmation"
        else:
            group = "regime"
            interval = 1800
            ttl = 7200
            hard = 21600
            horizon = "3d_7d"
            freshness_role = "context_regime"
        profile.append(
            {
                "schema_version": SCHEMA_VERSION,
                "module_name": module_id,
                "cadence_group": group,
                "interval_sec": interval,
                "ttl_sec": ttl,
                "hard_stale_sec": hard,
                "horizon": horizon,
                "freshness_role": freshness_role,
                "direction_authority": "accepted_runtime_snapshot_only",
            }
        )
    return profile


def profile_by_module() -> dict[str, dict[str, Any]]:
    return {item["module_name"]: item for item in cadence_profile()}


def initial_schedule(now: datetime | None = None) -> dict[str, dict[str, Any]]:
    now = now or datetime.now(UTC)
    return {
        item["module_name"]: {
            **item,
            "next_due_at": now.isoformat(),
            "last_attempt_at": None,
            "last_success_at": None,
            "last_status": "pending",
            "last_snapshot_id": "",
        }
        for item in cadence_profile()
    }


def next_due_at(now: datetime, interval_sec: int) -> str:
    return (now + timedelta(seconds=interval_sec)).isoformat()


def due_modules(schedule: dict[str, dict[str, Any]], now: datetime, *, force_all: bool = False) -> list[str]:
    if force_all:
        return sorted(schedule)
    due: list[str] = []
    for module_name, item in schedule.items():
        next_due = _parse_dt(item.get("next_due_at"))
        if next_due is None or next_due <= now:
            due.append(module_name)
    return sorted(due)


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

