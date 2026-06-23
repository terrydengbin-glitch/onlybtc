from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from onlybtc.db import schema
from onlybtc.db.session import database

PRICE_METRIC_IDS = ["btc_price", "btc_close"]
CONTEXT_METRIC_IDS = {
    "oi_change": ["btc_open_interest", "open_interest", "btc_oi_change_1h_pct"],
    "funding_rate": ["btc_funding_rate", "funding_rate_8h_equiv_z"],
    "basis": ["btc_basis", "basis", "annualized_basis"],
    "cvd_proxy": ["cvd_slope_z", "btc_direct_trend.orderflow_acceptance.cvd_slope_z"],
    "ofi_proxy": ["ofi_proxy", "taker_delta_quote", "btc_direct_trend.orderflow_acceptance.taker_delta_quote"],
}


def build_post_event_reaction(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    release_time = datetime.fromisoformat(
        str(event.get("release_time_utc") or event.get("release_time"))
    )
    if release_time.tzinfo is None:
        release_time = release_time.replace(tzinfo=UTC)
    if now < release_time:
        return _pending(event, now)
    returns = _btc_returns_after(release_time)
    context = _reaction_context_after(release_time)
    consensus = _to_float((event.get("expectation") or {}).get("consensus"))
    actual_snapshot = (event.get("actual_snapshot") or {}) if isinstance(event, dict) else {}
    actual_status = actual_snapshot.get("actual_status", "pending")
    observations = (actual_snapshot.get("observations") or []) if actual_status == "available" else []
    first_observation = observations[0] if observations else {}
    actual = _to_float(first_observation.get("latest_observation"))
    surprise_raw = None if actual is None or consensus is None else actual - consensus
    followthrough = "pending"
    reaction_state = "pending"
    if returns.get("btc_return_30m") is not None:
        r5 = returns.get("btc_return_5m") or 0.0
        r30 = returns.get("btc_return_30m") or 0.0
        if abs(r5) > 0 and abs(r30) < abs(r5) * 0.35:
            followthrough = "absorbed"
        elif r5 * r30 > 0:
            followthrough = "followthrough"
        else:
            followthrough = "fakeout"
        reaction_state = followthrough
    elif returns.get("btc_return_5m") is not None:
        reaction_state = "first_impulse"
    elif returns.get("btc_return_2h") is None:
        reaction_state = "insufficient_data"
    unlock_allowed = reaction_state in {"absorbed", "fakeout"}
    return {
        "reaction_id": f"rxn-{event['event_id']}-{now.strftime('%Y%m%d%H%M')}",
        "event_id": event["event_id"],
        "snapshot_ts": now.isoformat(),
        "actual": actual,
        "consensus": consensus,
        "surprise_raw": surprise_raw,
        "surprise_z": None,
        "btc_return_5m": returns.get("btc_return_5m"),
        "btc_return_30m": returns.get("btc_return_30m"),
        "btc_return_2h": returns.get("btc_return_2h"),
        "btc_absorbed_shock": followthrough == "absorbed" if followthrough != "pending" else None,
        "followthrough": followthrough,
        "reaction_state": reaction_state,
        "realized_volatility": context.get("realized_volatility"),
        "oi_change": context.get("oi_change"),
        "funding_rate": context.get("funding_rate"),
        "basis": context.get("basis"),
        "cvd_proxy": context.get("cvd_proxy"),
        "ofi_proxy": context.get("ofi_proxy"),
        "event_lock_release_allowed": unlock_allowed,
        "event_lock_release_reason": _event_lock_release_reason(reaction_state),
        "actual_status": actual_status,
        "data_quality_flags": _reaction_flags(actual, consensus, actual_snapshot),
    }


def _reaction_flags(
    actual: float | None,
    consensus: float | None,
    actual_snapshot: dict[str, Any],
) -> list[str]:
    flags = []
    if actual is None:
        flags.append("official_actual_pending")
    if consensus is None:
        flags.append("consensus_missing_surprise_disabled")
    if actual_snapshot.get("fallback_used"):
        flags.append("actual_provider_fallback_used")
    return flags


def _pending(event: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "reaction_id": f"rxn-{event['event_id']}-{now.strftime('%Y%m%d%H%M')}",
        "event_id": event["event_id"],
        "snapshot_ts": now.isoformat(),
        "actual": None,
        "consensus": None,
        "surprise_raw": None,
        "surprise_z": None,
        "btc_return_5m": None,
        "btc_return_30m": None,
        "btc_return_2h": None,
        "btc_absorbed_shock": None,
        "followthrough": "pending",
        "reaction_state": "pending",
        "realized_volatility": None,
        "oi_change": None,
        "funding_rate": None,
        "basis": None,
        "cvd_proxy": None,
        "ofi_proxy": None,
        "event_lock_release_allowed": False,
        "event_lock_release_reason": "pre_release_reaction_pending",
        "data_quality_flags": ["pre_release_reaction_pending"],
    }


def _btc_returns_after(release_time: datetime) -> dict[str, float | None]:
    result = {"btc_return_5m": None, "btc_return_30m": None, "btc_return_2h": None}
    try:
        with database.session() as session:
            rows = (
                session.query(schema.MetricValue)
                .filter(schema.MetricValue.metric_id.in_(PRICE_METRIC_IDS))
                .filter(schema.MetricValue.ts >= release_time)
                .order_by(schema.MetricValue.ts.asc())
                .limit(2000)
                .all()
            )
    except Exception:
        return result
    if not rows:
        return result
    base = float(rows[0].value)
    for key, minutes in (("btc_return_5m", 5), ("btc_return_30m", 30), ("btc_return_2h", 120)):
        target = _utc_timestamp(release_time) + minutes * 60
        row = next((item for item in rows if _utc_timestamp(item.ts) >= target), None)
        if row is not None and base:
            result[key] = float(row.value) / base - 1.0
    return result


def _reaction_context_after(release_time: datetime) -> dict[str, float | None]:
    result = {
        "realized_volatility": None,
        "oi_change": None,
        "funding_rate": None,
        "basis": None,
        "cvd_proxy": None,
        "ofi_proxy": None,
    }
    try:
        with database.session() as session:
            rows = (
                session.query(schema.MetricValue)
                .filter(
                    schema.MetricValue.metric_id.in_(
                        PRICE_METRIC_IDS
                        + [
                            metric_id
                            for metric_ids in CONTEXT_METRIC_IDS.values()
                            for metric_id in metric_ids
                        ]
                    )
                )
                .filter(schema.MetricValue.ts >= release_time)
                .filter(schema.MetricValue.ts <= release_time + _hours(2))
                .order_by(schema.MetricValue.metric_id.asc(), schema.MetricValue.ts.asc())
                .limit(5000)
                .all()
            )
    except Exception:
        return result
    price_rows = [row for row in rows if row.metric_id in PRICE_METRIC_IDS]
    result["realized_volatility"] = _realized_volatility(price_rows)
    for output_key, metric_ids in CONTEXT_METRIC_IDS.items():
        metric_rows = [row for row in rows if row.metric_id in metric_ids]
        if not metric_rows:
            continue
        if output_key in {"oi_change", "cvd_proxy", "ofi_proxy"}:
            result[output_key] = _window_change(metric_rows)
        else:
            result[output_key] = _latest_value(metric_rows)
    return result


def _realized_volatility(rows: list[schema.MetricValue]) -> float | None:
    values = [float(row.value) for row in sorted(rows, key=lambda row: row.ts) if row.value]
    if len(values) < 3:
        return None
    returns = [values[index] / values[index - 1] - 1.0 for index in range(1, len(values)) if values[index - 1]]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / len(returns)
    return round(math.sqrt(variance), 6)


def _window_change(rows: list[schema.MetricValue]) -> float | None:
    ordered = sorted(rows, key=lambda row: row.ts)
    if len(ordered) < 2:
        return _to_float(ordered[-1].value) if ordered else None
    first = _to_float(ordered[0].value)
    last = _to_float(ordered[-1].value)
    if first is None or last is None:
        return None
    if first:
        return round(last / first - 1.0, 6)
    return round(last - first, 6)


def _latest_value(rows: list[schema.MetricValue]) -> float | None:
    ordered = sorted(rows, key=lambda row: row.ts)
    return _to_float(ordered[-1].value) if ordered else None


def _event_lock_release_reason(reaction_state: str) -> str:
    if reaction_state == "absorbed":
        return "shock_absorbed_reaction_can_release_event_lock"
    if reaction_state == "fakeout":
        return "initial_impulse_reversed_reaction_can_release_event_lock"
    if reaction_state == "followthrough":
        return "policy_or_macro_shock_followthrough_keep_event_lock"
    if reaction_state == "first_impulse":
        return "first_impulse_only_wait_for_30m_confirmation"
    if reaction_state == "insufficient_data":
        return "insufficient_post_event_market_data"
    return "post_event_reaction_pending"


def _utc_timestamp(value: datetime) -> float:
    normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
    return normalized.timestamp()


def _hours(value: int | float):
    from datetime import timedelta

    return timedelta(hours=value)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
