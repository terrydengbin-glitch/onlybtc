from __future__ import annotations

from typing import Any

TIER_CONFIDENCE = {
    "official": 0.95,
    "official_nowcast": 0.90,
    "official_mirror": 0.86,
    "fed_research_tool": 0.84,
    "secondary_consensus": 0.78,
    "secondary_calendar": 0.76,
    "secondary_calendar_free_export": 0.80,
    "secondary_consensus_actual_free": 0.72,
    "secondary_consensus_actual_free_crosscheck": 0.74,
    "secondary_consensus_free_crosscheck": 0.70,
    "secondary_api": 0.74,
    "market_implied_proxy": 0.65,
    "prediction_market": 0.70,
    "manual_override": 0.45,
    "fallback": 0.35,
}


def build_provider_confidence(
    active_event: dict[str, Any] | None,
    source_fetches: list[dict[str, Any]],
    expectation_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    event_type = str((active_event or {}).get("event_type") or "").upper()
    expectation = expectation_snapshot or {}
    successful = [
        item for item in source_fetches
        if item.get("status") in {"success", "fallback_used", "partial"}
    ]
    tier_counts: dict[str, int] = {}
    for item in source_fetches:
        tier = str(item.get("source_tier") or "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    calendar_confidence = _best_confidence(
        successful,
        {
            "official",
            "official_mirror",
            "secondary_calendar",
            "secondary_calendar_free_export",
            "manual_override",
            "fallback",
        },
    )
    if active_event and active_event.get("source_tier") == "official_mirror":
        calendar_confidence = max(calendar_confidence, 0.86)
    if active_event and active_event.get("source_tier") == "manual_override":
        calendar_confidence = max(calendar_confidence, 0.45)

    consensus_status = str(expectation.get("consensus_status") or "missing")
    consensus_confidence = {
        "secondary_confirmed": 0.78,
        "secondary_unconfirmed": 0.45,
        "ok": 0.90,
        "missing": 0.0,
    }.get(consensus_status, 0.0)

    nowcast_confidence = _best_confidence(successful, {"official_nowcast"})
    if event_type not in {"CPI", "PCE"}:
        nowcast_confidence = 0.0

    market_implied = expectation.get("market_implied")
    rate_probability_confidence = 0.0
    if isinstance(market_implied, dict):
        if market_implied.get("fedwatch_proxy_used"):
            rate_probability_confidence = 0.65
        if (market_implied.get("atlanta_fed_mpt") or {}).get("available"):
            rate_probability_confidence = max(rate_probability_confidence, 0.84)
    if event_type != "FOMC":
        rate_probability_confidence = 0.0

    prediction = expectation.get("prediction_market_odds") or {}
    prediction_market_confidence = 0.0
    if prediction.get("status") == "available":
        prediction_market_confidence = 0.70
    elif prediction.get("status") == "available_low_liquidity":
        prediction_market_confidence = 0.45

    actual_confidence = 0.0
    actual_snapshot = (active_event or {}).get("actual_snapshot") or {}
    if actual_snapshot.get("actual_status") == "available":
        actual_confidence = 0.95
    elif actual_snapshot.get("actual_status") == "not_released":
        actual_confidence = 0.0

    disabled = _disabled_capabilities(
        event_type,
        consensus_status,
        rate_probability_confidence,
        prediction_market_confidence,
        actual_snapshot,
    )
    lineage_mode = _lineage_mode(
        calendar_confidence,
        consensus_confidence,
        prediction_market_confidence,
    )
    return {
        "calendar_confidence": round(calendar_confidence, 2),
        "consensus_confidence": round(consensus_confidence, 2),
        "nowcast_confidence": round(nowcast_confidence, 2),
        "actual_confidence": round(actual_confidence, 2),
        "rate_probability_confidence": round(rate_probability_confidence, 2),
        "prediction_market_confidence": round(prediction_market_confidence, 2),
        "provider_tier_counts": tier_counts,
        "disabled_capabilities": disabled,
        "source_conflicts": [],
        "lineage_mode": lineage_mode,
        "functional_live": lineage_mode
        in {"official_plus_secondary_confirmed", "official_mirror_partial_live", "partial_live"},
        "blocked": False,
        "confidence_note": _lineage_confidence_note(lineage_mode),
    }


def _best_confidence(items: list[dict[str, Any]], tiers: set[str]) -> float:
    score = 0.0
    for item in items:
        tier = str(item.get("source_tier") or "")
        if tier not in tiers:
            continue
        item_score = TIER_CONFIDENCE.get(tier, 0.0)
        if item.get("status") == "partial":
            item_score *= 0.7
        if item.get("status") == "failed":
            item_score = 0.0
        score = max(score, item_score)
    return score


def _disabled_capabilities(
    event_type: str,
    consensus_status: str,
    rate_probability_confidence: float,
    prediction_market_confidence: float,
    actual_snapshot: dict[str, Any],
) -> list[str]:
    disabled: list[str] = []
    if consensus_status not in {"ok", "secondary_confirmed"}:
        disabled.append("official_surprise_disabled")
        disabled.append("consensus_unconfirmed")
    if event_type == "FOMC" and rate_probability_confidence < 0.8:
        disabled.append("official_fedwatch_unavailable")
    if prediction_market_confidence and prediction_market_confidence < 0.7:
        disabled.append("prediction_market_low_liquidity")
    if actual_snapshot.get("actual_status") in {"provider_failed"}:
        disabled.append("official_actual_unavailable")
    return sorted(set(disabled))


def _lineage_mode(
    calendar_confidence: float,
    consensus_confidence: float,
    prediction_market_confidence: float,
) -> str:
    if calendar_confidence >= 0.9 and consensus_confidence >= 0.75:
        return "official_plus_secondary_confirmed"
    if calendar_confidence >= 0.8:
        return "official_mirror_partial_live"
    if prediction_market_confidence >= 0.7:
        return "prediction_market_watch"
    return "partial_live"


def _lineage_confidence_note(lineage_mode: str) -> str:
    if lineage_mode == "official_plus_secondary_confirmed":
        return "official calendar and secondary consensus are both confirmed."
    if lineage_mode == "official_mirror_partial_live":
        return (
            "official mirror calendar is live; unavailable consensus or actual fields "
            "only disable their specific calculations."
        )
    if lineage_mode == "partial_live":
        return (
            "partial live coverage is operational for monitoring; missing fields are "
            "capability-scoped."
        )
    if lineage_mode == "prediction_market_watch":
        return "prediction market data can warn on repricing, but it is not an official fact source."
    return "provider lineage requires manual review."
