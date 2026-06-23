from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from onlybtc.db import schema
from onlybtc.db.session import database
from onlybtc.event_window.connectors.common import clean_text, stable_hash

OFFICIAL_CRITICAL_PATTERNS = re.compile(
    r"\b(emergency|unscheduled|intermeeting|extraordinary|systemic|"
    r"enforcement action|trading suspension|stablecoin|bank failure|"
    r"market disruption|sanction|settlement|cease-and-desist)\b",
    re.IGNORECASE,
)
OFFICIAL_WATCH_PATTERNS = re.compile(
    r"\b(statement|press release|policy|supervision|regulation|"
    r"testimony|remarks|monetary policy|financial stability)\b",
    re.IGNORECASE,
)


def collect_shock_fast_lane(
    now: datetime,
    *,
    official_text_items: list[dict[str, Any]] | None = None,
    market_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Collect normalized unscheduled shocks.

    The fast lane deliberately reuses already-collected official text items
    where possible so the daemon does not hit official sites at a much higher
    cadence than the calendar/text collectors.
    """

    official_shocks = collect_official_shocks(now, official_text_items or [])
    market_shocks = collect_market_shocks(now, market_probe=market_probe)
    shocks = sorted(
        [*official_shocks, *market_shocks],
        key=lambda item: (
            _level_rank(str(item.get("emergency_level") or "watch")),
            str(item.get("detected_at") or ""),
        ),
        reverse=True,
    )
    return {"shock_items": shocks, "source_fetches": []}


def collect_official_shocks(
    now: datetime,
    official_text_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    shocks: list[dict[str, Any]] = []
    recent_cutoff = now - timedelta(hours=24)
    for item in official_text_items:
        published_at = _parse_ts(item.get("published_at")) or now
        if published_at < recent_cutoff:
            continue
        title = clean_text(str(item.get("title") or ""))
        raw_text = clean_text(str(item.get("raw_text") or ""))
        combined = f"{title} {raw_text}"
        if not combined.strip() or not _is_policy_relevant_official_text(combined):
            continue
        source_url = str(item.get("url") or "")
        source_hash = str(item.get("text_hash") or stable_hash(combined))
        level = "critical" if OFFICIAL_CRITICAL_PATTERNS.search(combined) else "high"
        shock_type = _official_shock_type(combined, source_url)
        shocks.append(
            _normalize_shock_item(
                {
                    "shock_id": f"shock-official-{source_hash[:16]}",
                    "detected_at": now.isoformat(),
                    "shock_type": shock_type,
                    "emergency_level": level,
                    "confirmation_level": "official",
                    "source_count": 1,
                    "official_confirmed": True,
                    "market_dislocation": False,
                    "btc_microstructure_confirmation": False,
                    "cross_asset_confirmation": False,
                    "rumor_risk": False,
                    "raw_title": title or "Official shock item",
                    "raw_url": source_url,
                    "source_hash": source_hash,
                    "published_at": published_at.isoformat(),
                    "reason_codes": ["official_source_hit"],
                    "source_lineage": [
                        {
                            "source_id": str(item.get("source_name") or "official_text"),
                            "source_tier": str(item.get("source_tier") or "official"),
                            "url": source_url,
                            "source_hash": source_hash,
                        }
                    ],
                    "evidence": {},
                    "data_quality_flags": [],
                }
            )
        )
    return shocks


def collect_market_shocks(
    now: datetime,
    *,
    market_probe: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    window = _market_window_evidence(now, market_probe=market_probe)
    returns = window["returns"]
    zscores = window["zscores"]
    primary_key, primary_return, primary_z = _primary_market_move(returns, zscores)
    if primary_return is None:
        return []
    abs_return = abs(primary_return)
    effective_z = primary_z if primary_z is not None else _fallback_effective_z(primary_key, abs_return)
    sustained = primary_key in {"1h", "4h", "24h"}
    if effective_z < 2.0 and abs_return < _window_abs_threshold(primary_key):
        return []
    has_confirmation = False
    if sustained and (effective_z >= 2.0 or abs_return >= _window_abs_threshold(primary_key)):
        has_confirmation = True
    level = (
        "critical"
        if (effective_z >= 3.5 or abs_return >= _critical_abs_threshold(primary_key)) and has_confirmation
        else ("high" if effective_z >= 2.0 or abs_return >= _window_abs_threshold(primary_key) else "watch")
    )
    reason_codes = [f"btc_{primary_key}_market_dislocation"]
    if sustained:
        reason_codes.append("sustained_drawdown_watch" if primary_return < 0 else "sustained_rally_watch")
    if returns.get("24h") is not None and abs(float(returns["24h"])) >= 0.03:
        reason_codes.append("btc_24h_context_pressure")
    return [
        _normalize_shock_item(
            {
                "shock_id": f"shock-btc-{primary_key}-{now.strftime('%Y%m%d%H%M')}",
                "detected_at": now.isoformat(),
                "shock_type": "crypto_native",
                "emergency_level": level,
                "confirmation_level": "market_dislocation",
                "source_count": 1,
                "official_confirmed": False,
                "market_dislocation": True,
                "btc_microstructure_confirmation": has_confirmation,
                "cross_asset_confirmation": False,
                "rumor_risk": False,
                "raw_title": f"BTC {primary_key} market dislocation",
                "raw_url": "",
                "source_hash": stable_hash(
                    f"btc-{primary_key}-{now.strftime('%Y%m%d%H%M')}-{primary_return}"
                ),
                "published_at": now.isoformat(),
                "reason_codes": reason_codes,
                "source_lineage": [
                    {
                        "source_id": str(window.get("source_id") or "btc_market_probe"),
                        "source_tier": str(window.get("source_tier") or "market_live"),
                        "market_probe_id": window.get("market_probe_id"),
                        "primary_window": primary_key,
                        "primary_return": primary_return,
                        "primary_return_z": primary_z,
                    }
                ],
                "evidence": {
                    "primary_window": primary_key,
                    "primary_return": primary_return,
                    "primary_return_z": primary_z,
                    "btc_return_5m": returns.get("5m"),
                    "btc_return_15m": returns.get("15m"),
                    "btc_return_1h": returns.get("1h"),
                    "btc_return_4h": returns.get("4h"),
                    "btc_return_24h": returns.get("24h"),
                    "btc_return_5m_z": zscores.get("5m"),
                    "btc_return_15m_z": zscores.get("15m"),
                    "btc_return_1h_z": zscores.get("1h"),
                    "btc_return_4h_z": zscores.get("4h"),
                    "btc_return_24h_z": zscores.get("24h"),
                    "oi_change_15m_z": None,
                    "liquidation_z": None,
                    "dxy_move_z": None,
                    "us2y_move_z": None,
                    "ndx_move_z": None,
                },
                "data_quality_flags": sorted(
                    set(["oi_liquidation_confirmation_missing", *window["data_quality_flags"]])
                ),
            }
        )
    ]


def _normalize_shock_item(item: dict[str, Any]) -> dict[str, Any]:
    level = _classify_level(item)
    item["emergency_level"] = level
    item.setdefault("confirmation_level", "single_source")
    item.setdefault("source_count", 0)
    item.setdefault("official_confirmed", False)
    item.setdefault("market_dislocation", False)
    item.setdefault("btc_microstructure_confirmation", False)
    item.setdefault("cross_asset_confirmation", False)
    item.setdefault("rumor_risk", False)
    item.setdefault("raw_title", "")
    item.setdefault("raw_url", "")
    item.setdefault("source_hash", stable_hash(item))
    item.setdefault("published_at", item.get("detected_at"))
    item.setdefault("reason_codes", [])
    item.setdefault("source_lineage", [])
    item.setdefault("evidence", {})
    item.setdefault("data_quality_flags", [])
    item["direct_score_impact"] = False
    if item.get("rumor_risk") and level == "critical":
        item["emergency_level"] = "watch"
        item["data_quality_flags"] = [
            *list(item.get("data_quality_flags") or []),
            "rumor_downgraded_from_critical",
        ]
    return item


def _classify_level(item: dict[str, Any]) -> str:
    requested = str(item.get("emergency_level") or "watch")
    if item.get("rumor_risk"):
        return "watch"
    if item.get("official_confirmed") and requested in {"critical", "high"}:
        return requested
    evidence = item.get("evidence") or {}
    primary_window = str(evidence.get("primary_window") or "5m")
    btc_z = _to_float(evidence.get("primary_return_z") or evidence.get("btc_return_5m_z"))
    btc_return = abs(_to_float(evidence.get("primary_return") or evidence.get("btc_return_5m")) or 0.0)
    confirmed = bool(
        item.get("btc_microstructure_confirmation")
        or item.get("cross_asset_confirmation")
        or evidence.get("oi_change_15m_z") is not None
        or evidence.get("liquidation_z") is not None
    )
    if (btc_z is not None and btc_z >= 3.5 or btc_return >= _critical_abs_threshold(primary_window)) and confirmed:
        return "critical"
    if requested == "critical" and not confirmed and item.get("market_dislocation"):
        return "high"
    if requested in {"critical", "high"}:
        return requested
    if item.get("market_dislocation") and (
        btc_z is None or btc_z >= 2.0 or btc_return >= _window_abs_threshold(primary_window)
    ):
        return "high"
    return "watch"


def _market_window_evidence(
    now: datetime,
    *,
    market_probe: dict[str, Any] | None,
) -> dict[str, Any]:
    returns: dict[str, float | None] = {}
    zscores: dict[str, float | None] = {}
    flags: list[str] = []
    source_id = "btc_market_probe"
    source_tier = "market_live"
    probe_id = None
    if market_probe:
        probe_id = market_probe.get("market_probe_id")
        source_id = str(market_probe.get("source") or "btc_market_probe")
        source_tier = "market_live"
        probe_returns = market_probe.get("returns") or {}
        probe_z = market_probe.get("return_zscores") or {}
        for key in ("5m", "15m", "1h", "4h", "24h"):
            returns[key] = _to_float(probe_returns.get(key))
            zscores[key] = _to_float(probe_z.get(key))
        flags.extend(str(item) for item in market_probe.get("data_quality_flags") or [])
    for key, minutes in (("5m", 5), ("15m", 15), ("1h", 60), ("4h", 240), ("24h", 1440)):
        if returns.get(key) is None:
            returns[key] = _metric_return(key) or _recent_btc_return(now, minutes=minutes)
            if returns.get(key) is not None:
                flags.append(f"{key}_main_pipeline_metric_fallback")
        if zscores.get(key) is None:
            zscores[key] = _recent_btc_return_z(now, minutes=minutes)
    if all(value is None for value in returns.values()):
        flags.append("market_probe_missing")
    return {
        "returns": returns,
        "zscores": zscores,
        "source_id": source_id,
        "source_tier": source_tier,
        "market_probe_id": probe_id,
        "data_quality_flags": flags,
    }


def _primary_market_move(
    returns: dict[str, float | None],
    zscores: dict[str, float | None],
) -> tuple[str, float | None, float | None]:
    best_key = "5m"
    best_return: float | None = None
    best_z: float | None = None
    best_score = -1.0
    for key in ("5m", "15m", "1h", "4h", "24h"):
        value = returns.get(key)
        if value is None:
            continue
        z = zscores.get(key)
        score = z if z is not None else _fallback_effective_z(key, abs(value))
        if abs(value) >= _window_abs_threshold(key):
            score += 0.5
        if score > best_score:
            best_key, best_return, best_z, best_score = key, value, z, score
    return best_key, best_return, best_z


def _window_abs_threshold(window: str) -> float:
    return {
        "5m": 0.015,
        "15m": 0.02,
        "1h": 0.012,
        "4h": 0.015,
        "24h": 0.03,
    }.get(window, 0.02)


def _critical_abs_threshold(window: str) -> float:
    return {
        "5m": 0.04,
        "15m": 0.05,
        "1h": 0.035,
        "4h": 0.045,
        "24h": 0.07,
    }.get(window, 0.05)


def _fallback_effective_z(window: str, abs_return: float) -> float:
    scale = {
        "5m": 0.0075,
        "15m": 0.010,
        "1h": 0.008,
        "4h": 0.010,
        "24h": 0.018,
    }.get(window, 0.01)
    return abs_return / scale if scale else 0.0


def _metric_return(window: str) -> float | None:
    metric_id = {
        "5m": "btc_return_5m",
        "15m": "btc_return_15m",
        "1h": "btc_return_1h",
        "4h": "btc_return_4h",
        "24h": "btc_return_24h",
    }.get(window)
    if not metric_id:
        return None
    try:
        with database.session() as session:
            row = (
                session.query(schema.MetricValue)
                .filter(schema.MetricValue.metric_id == metric_id)
                .order_by(schema.MetricValue.ts.desc())
                .limit(1)
                .one_or_none()
            )
    except Exception:
        return None
    return _to_float(row.value) if row else None


def _is_policy_relevant_official_text(text: str) -> bool:
    return bool(OFFICIAL_CRITICAL_PATTERNS.search(text) or OFFICIAL_WATCH_PATTERNS.search(text))


def _official_shock_type(text: str, url: str) -> str:
    combined = f"{text} {url}".lower()
    if "sec.gov" in combined or "enforcement" in combined or "regulation" in combined:
        return "regulatory"
    if "treasury" in combined or "sanction" in combined:
        return "policy"
    if "stablecoin" in combined:
        return "stablecoin"
    if "exchange" in combined or "trading suspension" in combined:
        return "exchange"
    return "policy"


def _level_rank(level: str) -> int:
    return {"critical": 3, "high": 2, "watch": 1}.get(level, 0)


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_ts(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _recent_btc_return(now: datetime, minutes: int) -> float | None:
    start = now - timedelta(minutes=minutes)
    try:
        with database.session() as session:
            rows = (
                session.query(schema.MetricValue)
                .filter(schema.MetricValue.metric_id.in_(["btc_price", "btc_close"]))
                .filter(schema.MetricValue.ts >= start)
                .order_by(schema.MetricValue.ts.asc())
                .limit(100)
                .all()
            )
    except Exception:
        return None
    if len(rows) < 2:
        return None
    first = float(rows[0].value)
    last = float(rows[-1].value)
    if not first:
        return None
    return last / first - 1.0


def _recent_btc_return_z(now: datetime, minutes: int) -> float | None:
    sample_window = now - timedelta(hours=12)
    try:
        with database.session() as session:
            rows = (
                session.query(schema.MetricValue)
                .filter(schema.MetricValue.metric_id.in_(["btc_price", "btc_close"]))
                .filter(schema.MetricValue.ts >= sample_window)
                .order_by(schema.MetricValue.ts.asc())
                .limit(1000)
                .all()
            )
    except Exception:
        return None
    if len(rows) < 8:
        return None
    returns: list[float] = []
    step = max(1, int(minutes))
    values = [(row.ts, float(row.value)) for row in rows if row.value]
    for idx in range(step, len(values)):
        first = values[idx - step][1]
        last = values[idx][1]
        if first:
            returns.append(abs(last / first - 1.0))
    latest = _recent_btc_return(now, minutes)
    if latest is None or not returns:
        return None
    returns_sorted = sorted(returns)
    median = returns_sorted[len(returns_sorted) // 2]
    if median <= 0:
        return None
    return abs(latest) / median
