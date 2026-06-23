from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from onlybtc.p45.cockpit import normalize_module_signals


SCHEMA_VERSION = "p45.btc_timescale_judge.v2.1"
SCHEMA_VERSION_V22 = "p45.btc_timescale_judge.v2.2"

HORIZON_WEIGHTS: dict[str, dict[str, float]] = {
    "4h": {
        "kline_orderflow": 0.30,
        "trade_structure_flow": 0.30,
        "derivatives_crowding": 0.25,
        "asia_risk": 0.15,
    },
    "24h": {
        "kline_orderflow": 0.20,
        "trade_structure_flow": 0.20,
        "derivatives_crowding": 0.25,
        "fund_flow": 0.20,
        "macro_radar": 0.15,
    },
    "3d": {
        "fund_flow": 0.25,
        "macro_radar": 0.25,
        "treasury_credit": 0.15,
        "dollar_liquidity": 0.15,
        "crypto_breadth": 0.10,
        "options_volatility": 0.10,
    },
    "7d": {
        "onchain_valuation": 0.25,
        "btc_adoption": 0.15,
        "macro_radar": 0.20,
        "dollar_liquidity": 0.15,
        "fund_flow": 0.15,
        "event_policy": 0.10,
    },
}

HORIZON_ROLES = {
    "4h": "fast_sensing",
    "24h": "short_trend_confirmation",
    "3d": "flow_macro_confirmation",
    "7d": "regime_background",
}

ACCEPTANCE_MULTIPLIER = {
    "accepted": 1.00,
    "fragile": 0.70,
    "unconfirmed": 0.45,
    "rejected": 0.15,
    "blocked": 0.00,
}

TRIGGER_STAGES = {"fast_signal", "confirmed_signal"}
FAST_RESPONSE_MODULES = {"kline_orderflow", "trade_structure_flow", "derivatives_crowding"}
REGIME_ONLY_MODULES = {"onchain_valuation", "btc_adoption", "event_policy"}


def build_btc_timescale_judge(
    *,
    btc_trend_cockpit: dict[str, Any] | None,
    modules: list[dict[str, Any]],
    contract_validation: dict[str, Any] | None = None,
    data_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cockpit = btc_trend_cockpit or {}
    module_signals = list(cockpit.get("module_signals") or normalize_module_signals(modules))
    horizons = {
        horizon: _build_horizon(horizon, module_signals, contract_validation, data_quality)
        for horizon in ("4h", "24h", "3d", "7d")
    }
    cross_horizon = _cross_horizon_arbiter(horizons, contract_validation, data_quality)
    return {
        "schema_version": SCHEMA_VERSION,
        "asof_ts": datetime.now(UTC).isoformat(),
        "base_symbol": "BTCUSDT",
        "horizons": horizons,
        "cross_horizon": cross_horizon,
        "legacy_horizon": cockpit.get("horizon") or {},
    }


def build_btc_timescale_judge_v22(
    *,
    direct_trend_state: dict[str, Any] | None,
    legacy_judge: dict[str, Any],
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    state = direct_trend_state or {}
    state_horizons = state.get("horizons") or {}
    legacy_horizons = legacy_judge.get("horizons") or {}
    horizons = {
        "4h": _v22_direct_horizon("4h", state_horizons.get("4h"), modules),
        "1d": _v22_direct_horizon("1d", state_horizons.get("1d"), modules),
        "3d": _v22_legacy_horizon("3d", legacy_horizons.get("3d")),
        "7d": _v22_legacy_horizon("7d", legacy_horizons.get("7d")),
    }
    return {
        "schema_version": SCHEMA_VERSION_V22,
        "fallback_schema_version": SCHEMA_VERSION,
        "snapshot_id": state.get("state_run_id")
        or f"v22-fallback-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
        "asof_ts": state.get("asof_ts") or datetime.now(UTC).isoformat(),
        "base_symbol": "BTCUSDT",
        "source_layer": "direct_evidence_state_machine" if direct_trend_state else "legacy_v21_fallback",
        "evidence_run_id": state.get("evidence_run_id"),
        "registry_run_id": state.get("registry_run_id"),
        "state_run_id": state.get("state_run_id"),
        "horizons": horizons,
        "cross_horizon": _v22_cross_horizon(horizons, legacy_judge.get("cross_horizon") or {}),
        "legacy_horizon_aliases": {"24h": "1d"},
        "freshness_summary": state.get("freshness_summary") or {},
        "source_fresh": state.get("source_fresh", "unknown"),
        "fallback_used": direct_trend_state is None,
        "fallback_reason": "missing_direct_trend_state_machine" if direct_trend_state is None else None,
        "legacy_v21_cross_horizon": legacy_judge.get("cross_horizon") or {},
    }


def _v22_direct_horizon(
    horizon: str,
    state_horizon: dict[str, Any] | None,
    modules: list[dict[str, Any]],
) -> dict[str, Any]:
    state_horizon = state_horizon or {}
    evidence = state_horizon.get("evidence") or []
    source_window = _source_window(evidence)
    default_state = "range_chop" if horizon == "4h" else "range_compression_before_expansion"
    return {
        "state": state_horizon.get("state") or default_state,
        "direction": state_horizon.get("direction") or "neutral",
        "direction_score": float(state_horizon.get("direction_score") or 0.0),
        "acceptance_score": float(state_horizon.get("acceptance_score") or 0.0),
        "trust_score": float(state_horizon.get("trust_score") or 0.0),
        "display_score": float(state_horizon.get("display_score") or 0.0),
        "direct_evidence": _direct_evidence_groups(evidence),
        "radar_context": _radar_context(state_horizon, modules),
        "event_trust": {
            "event_trust_cap": state_horizon.get("event_trust_cap"),
            "trust_score": state_horizon.get("trust_score"),
            "policy": "trust_cap_only_no_direction_delta",
        },
        "next_confirmation": _v22_next_confirmation(horizon, state_horizon),
        "invalidation": _v22_invalidation(horizon, state_horizon),
        "source_fresh": _horizon_source_fresh(state_horizon),
        "runtime_fresh": True,
        "freshness_summary": state_horizon.get("freshness_summary") or {},
        "fallback_used": not bool(state_horizon),
        "fallback_reason": "missing_direct_horizon_state" if not state_horizon else None,
        "snapshot_id": f"{horizon}:{source_window.get('max_source_asof_ts') or 'missing'}",
        "asof_ts": source_window.get("max_source_asof_ts"),
        "source_window": source_window,
        "semantic_flags": state_horizon.get("semantic_flags") or [],
        "reason": state_horizon.get("reason"),
    }


def _v22_legacy_horizon(horizon: str, legacy: dict[str, Any] | None) -> dict[str, Any]:
    legacy = legacy or {}
    return {
        "state": legacy.get("signal_stage") or "legacy_context",
        "direction": legacy.get("direction") or "neutral",
        "direction_score": round(float(legacy.get("raw_score") or 0.0) * 100.0, 2),
        "acceptance_score": (legacy.get("acceptance") or {}).get("score", 0.0),
        "trust_score": legacy.get("confidence_score", 0.0),
        "display_score": round(float(legacy.get("effective_score") or 0.0) * 100.0, 2),
        "direct_evidence": {},
        "radar_context": {
            "bias": 0.0,
            "status": "legacy_context",
            "used_modules": [
                item.get("module_id")
                for bucket in (legacy.get("evidence") or {}).values()
                for item in bucket
            ],
        },
        "event_trust": {},
        "next_confirmation": legacy.get("next_confirmation_triggers") or [],
        "invalidation": legacy.get("next_invalidation_triggers") or [],
        "source_fresh": "legacy_unknown",
        "runtime_fresh": True,
        "freshness_summary": {},
        "fallback_used": True,
        "fallback_reason": f"{horizon}_uses_v21_radar_context_until_direct_contract_exists",
        "snapshot_id": f"{horizon}:legacy-v21",
        "source_window": {},
        "semantic_flags": [],
        "reason": legacy.get("summary"),
    }


def _direct_evidence_groups(evidence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {
        "price_structure": {},
        "orderflow_acceptance": {},
        "derivatives_positioning": {},
        "volatility_liquidity": {},
        "btc_residual_cross_asset": {},
        "event_overlay_context": {},
    }
    for item in evidence:
        feature_id = str(item.get("feature_id") or "")
        category = _category_from_feature(feature_id)
        feature_name = feature_id.rsplit(".", 1)[-1]
        groups.setdefault(category, {})[feature_name] = {
            "value": item.get("value"),
            "score": item.get("score"),
            "role": item.get("role"),
            "freshness_state": item.get("freshness_state"),
            "semantic_state": item.get("semantic_state"),
            "source_asof_ts": item.get("source_asof_ts"),
            "valid_until": item.get("valid_until"),
        }
    return groups


def _category_from_feature(feature_id: str) -> str:
    parts = feature_id.split(".")
    return parts[1] if len(parts) >= 3 else "unknown"


def _radar_context(state_horizon: dict[str, Any], modules: list[dict[str, Any]]) -> dict[str, Any]:
    bias = _clip(float(state_horizon.get("radar_context_bias") or 0.0), -15.0, 15.0)
    conflict = float(state_horizon.get("conflict_score") or 0.0)
    if conflict >= 35:
        status = "conflicting"
    elif bias >= 2:
        status = "confirming"
    elif bias <= -2:
        status = "degrading"
    else:
        status = "neutral"
    return {
        "bias": round(bias, 2),
        "status": status,
        "used_modules": [
            str(item.get("radar_module") or item.get("module_name"))
            for item in modules
            if item.get("radar_module") or item.get("module_name")
        ],
        "max_bias": 15,
        "policy": "confirm_conflict_degrade_only",
    }


def _v22_next_confirmation(horizon: str, state_horizon: dict[str, Any]) -> list[str]:
    state = str(state_horizon.get("state") or "")
    if horizon == "4h" and state != "fast_trend_acceptance":
        return ["orderflow acceptance aligns", "direct evidence agreement reaches 3 categories"]
    if horizon == "1d" and state != "trend_accepted":
        return ["24h price acceptance improves", "residual and derivatives persistence align"]
    return ["maintain direct evidence freshness", "avoid opposite acceptance conflict"]


def _v22_invalidation(horizon: str, state_horizon: dict[str, Any]) -> list[str]:
    direction = str(state_horizon.get("direction") or "neutral")
    if direction == "neutral":
        return ["direct evidence remains mixed or weak"]
    if horizon == "4h":
        return ["CVD/taker delta flips against price", "price_oi_interaction_state rejects the move"]
    return ["residual_semantic flips", "event trust cap blocks confirmation"]


def _source_window(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = [_parse_dt(item.get("source_asof_ts")) for item in evidence]
    timestamps = [item for item in timestamps if item is not None]
    if not timestamps:
        return {
            "min_source_asof_ts": None,
            "max_source_asof_ts": None,
            "max_source_lag_sec": None,
        }
    min_ts = min(timestamps)
    max_ts = max(timestamps)
    return {
        "min_source_asof_ts": min_ts.isoformat(),
        "max_source_asof_ts": max_ts.isoformat(),
        "max_source_lag_sec": round((max_ts - min_ts).total_seconds(), 3),
    }


def _horizon_source_fresh(state_horizon: dict[str, Any]) -> bool | str:
    freshness = state_horizon.get("freshness_summary") or {}
    if freshness.get("blocked_evidence") or freshness.get("stale_evidence"):
        return False
    if freshness.get("missing_evidence"):
        return "partial"
    return True


def _v22_cross_horizon(
    horizons: dict[str, dict[str, Any]],
    legacy_cross: dict[str, Any],
) -> dict[str, Any]:
    h1d = horizons["1d"]
    h4 = horizons["4h"]
    if h1d["state"] == "trend_accepted" and h1d["direction"] in {"bullish", "bearish"}:
        return {
            "dominant_horizon": "1d",
            "alignment": "direct_accepted",
            "headline_direction": h1d["direction"],
            "headline_stage": "confirmed",
            "why_not_stronger": "1d direct trend is accepted; 3d/7d still legacy context.",
            "why_not_reversed": "Need opposite accepted direct 1d evidence.",
        }
    if h4["state"] == "fast_trend_acceptance" and h4["direction"] in {"bullish", "bearish"}:
        return {
            "dominant_horizon": "4h",
            "alignment": "building",
            "headline_direction": h4["direction"],
            "headline_stage": "watch",
            "why_not_stronger": "4h direct trend needs 1d acceptance.",
            "why_not_reversed": "No accepted opposite 1d direct evidence.",
        }
    return {
        "dominant_horizon": legacy_cross.get("dominant_horizon", "1d"),
        "alignment": "direct_mixed",
        "headline_direction": h1d["direction"]
        if h1d["direction"] != "neutral"
        else legacy_cross.get("headline_direction", "neutral"),
        "headline_stage": "watch",
        "why_not_stronger": "Direct 4h/1d evidence is not accepted enough for confirmation.",
        "why_not_reversed": "Reversal requires accepted opposite direct evidence.",
    }


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            return None
    return None


def _build_horizon(
    horizon: str,
    signals: list[dict[str, Any]],
    contract_validation: dict[str, Any] | None,
    data_quality: dict[str, Any] | None,
) -> dict[str, Any]:
    weights = HORIZON_WEIGHTS[horizon]
    by_module = {str(item.get("module_name") or ""): item for item in signals}
    evidence = {
        "trigger_eligible": [],
        "confirmation": [],
        "context_only": [],
        "regime_only": [],
        "rejected": [],
        "quality_discounted": [],
    }
    raw_score = 0.0
    total_weight = 0.0
    sensitivity = 0.0
    stability = 0.0
    quality_penalty = 0.0

    for module_name, weight in weights.items():
        signal = by_module.get(module_name)
        if not signal:
            continue
        bucket = _evidence_bucket(horizon, signal)
        item = _evidence_item(signal, weight, bucket)
        evidence[bucket].append(item)
        contribution = _horizon_contribution(signal, bucket) * weight
        raw_score += contribution
        total_weight += weight
        if bucket in {"trigger_eligible", "rejected"}:
            sensitivity += abs(contribution)
        if bucket in {"confirmation", "regime_only"}:
            stability += abs(contribution)
        if bucket == "quality_discounted":
            quality_penalty += 8.0

    raw_score = _clip(raw_score / total_weight if total_weight else 0.0, -1.0, 1.0)
    acceptance = compute_btc_acceptance(horizon, list(by_module.values()), raw_score, contract_validation, data_quality)
    effective_score = _clip(raw_score * ACCEPTANCE_MULTIPLIER[acceptance["state"]], -1.0, 1.0)
    stage = _signal_stage(horizon, effective_score, acceptance)
    direction = _direction(effective_score)
    confidence = _confidence(effective_score, acceptance, quality_penalty)
    if _blocking(contract_validation, data_quality):
        stage = "blocked"
        direction = "neutral"
        effective_score = 0.0
        confidence = 0.0

    return {
        "role": HORIZON_ROLES[horizon],
        "direction": direction,
        "signal_stage": stage,
        "raw_score": round(raw_score, 4),
        "effective_score": round(effective_score, 4),
        "confidence_score": round(confidence, 2),
        "sensitivity_score": round(_clip(sensitivity * 100.0, 0.0, 100.0), 2),
        "stability_score": round(_clip(stability * 100.0, 0.0, 100.0), 2),
        "acceptance": acceptance,
        "evidence": evidence,
        "next_confirmation_triggers": _next_confirmation(horizon, direction, acceptance, evidence),
        "next_invalidation_triggers": _next_invalidation(horizon, direction, acceptance, evidence),
        "data_quality_flags": _data_quality_flags(signals, data_quality)[:12],
        "summary": _summary(horizon, direction, stage, acceptance, evidence),
    }


def compute_btc_acceptance(
    horizon: str,
    signals: list[dict[str, Any]],
    raw_score: float,
    contract_validation: dict[str, Any] | None = None,
    data_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if _blocking(contract_validation, data_quality):
        return _acceptance("blocked", 0.0, None, None, None, None)

    relevant = _acceptance_relevant_signals(horizon, signals)
    response_values = [
        _normalize_response(item.get("btc_response_score"))
        for item in relevant
        if item.get("btc_response_score") is not None
    ]
    residual_values = [
        _normalize_residual(item.get("residual"))
        for item in relevant
        if item.get("residual") is not None
    ]
    price_acceptance = _avg(response_values)
    residual = _avg(residual_values)
    flow_values = [
        _clip(float(item.get("contribution") or 0.0), -1.0, 1.0)
        for item in relevant
        if item.get("module_name") in FAST_RESPONSE_MODULES
    ]
    flow_acceptance = _avg(flow_values)

    if price_acceptance is None and residual is None and flow_acceptance is None:
        return _acceptance("blocked", 0.0, None, None, None, None)

    # Missing price/flow data can still remain usable for 7d regime, but not for confirmed short horizons.
    btc_response = _avg([item for item in (price_acceptance, residual, flow_acceptance) if item is not None])
    raw_sign = _sign(raw_score)
    aligned = 0
    opposed = 0
    for value in (price_acceptance, residual, flow_acceptance):
        if value is None or raw_sign == 0:
            continue
        if value * raw_sign >= 0.15:
            aligned += 1
        elif value * raw_sign <= -0.15:
            opposed += 1

    if opposed >= 1 and aligned == 0:
        state = "rejected"
    elif opposed >= 1:
        state = "fragile"
    elif aligned >= 2:
        state = "accepted"
    elif aligned == 1:
        state = "fragile"
    else:
        state = "unconfirmed"

    if horizon in {"4h", "24h"} and price_acceptance is None and flow_acceptance is None:
        state = "blocked"
    score = _acceptance_score(state, btc_response)
    return _acceptance(
        state,
        score,
        btc_response,
        residual,
        price_acceptance,
        flow_acceptance,
    )


def _acceptance(
    state: str,
    score: float,
    btc_response: float | None,
    residual: float | None,
    price: float | None,
    flow: float | None,
) -> dict[str, Any]:
    return {
        "state": state,
        "score": round(score, 2),
        "btc_response_score": _round_score(btc_response),
        "residual_score": _round_score(residual),
        "price_acceptance_score": _round_score(price),
        "flow_acceptance_score": _round_score(flow),
    }


def _acceptance_relevant_signals(horizon: str, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    modules = set(HORIZON_WEIGHTS[horizon])
    if horizon == "24h":
        modules.update(HORIZON_WEIGHTS["4h"])
    if horizon == "3d":
        modules.update({"derivatives_crowding", "fund_flow"})
    if horizon == "7d":
        modules.update({"fund_flow", "macro_radar", "onchain_valuation", "btc_adoption"})
    return [item for item in signals if item.get("module_name") in modules]


def _evidence_bucket(horizon: str, signal: dict[str, Any]) -> str:
    quality = str(signal.get("quality_status") or "partial")
    accepted = str(signal.get("accepted_status") or "unknown")
    stage = str(signal.get("signal_stage") or "none")
    module = str(signal.get("module_name") or "")
    direction = str(signal.get("effective_direction") or "neutral")
    if quality in {"failed", "stale"}:
        return "quality_discounted"
    if accepted == "rejected":
        return "rejected"
    if horizon == "7d" or module in REGIME_ONLY_MODULES:
        return "regime_only"
    if direction not in {"bullish", "bearish"}:
        return "context_only"
    if stage in TRIGGER_STAGES and accepted == "accepted":
        return "trigger_eligible"
    if stage in {"early_warning", "fast_signal", "confirmed_signal"}:
        return "confirmation"
    return "context_only"


def _horizon_contribution(signal: dict[str, Any], bucket: str) -> float:
    contribution = float(signal.get("contribution") or 0.0)
    if bucket == "trigger_eligible":
        return contribution
    if bucket == "confirmation":
        return contribution * 0.45
    if bucket in {"context_only", "regime_only"}:
        return contribution * 0.25
    if bucket == "quality_discounted":
        return contribution * 0.15
    if bucket == "rejected":
        return -abs(contribution) if contribution >= 0 else abs(contribution)
    return 0.0


def _evidence_item(signal: dict[str, Any], weight: float, bucket: str) -> dict[str, Any]:
    return {
        "module_id": signal.get("module_name"),
        "direction": signal.get("effective_direction"),
        "signal_stage": signal.get("signal_stage"),
        "btc_implication": signal.get("btc_implication"),
        "accepted_status": signal.get("accepted_status"),
        "quality_status": signal.get("quality_status"),
        "contribution": signal.get("contribution"),
        "weight": weight,
        "bucket": bucket,
        "support_drivers": signal.get("support_drivers") or [],
        "pressure_drivers": signal.get("pressure_drivers") or [],
        "data_quality_flags": signal.get("data_quality_flags") or [],
    }


def _cross_horizon_arbiter(
    horizons: dict[str, dict[str, Any]],
    contract_validation: dict[str, Any] | None,
    data_quality: dict[str, Any] | None,
) -> dict[str, Any]:
    if _blocking(contract_validation, data_quality):
        return {
            "dominant_horizon": "24h",
            "alignment": "blocked",
            "headline_direction": "neutral",
            "headline_stage": "blocked",
            "why_not_stronger": "Data quality or contract validation blocks horizon confirmation.",
            "why_not_reversed": "No valid BTC acceptance gate is available.",
        }
    h24 = horizons["24h"]
    d3 = horizons["3d"]
    d7 = horizons["7d"]
    h4 = horizons["4h"]
    h24_dir = str(h24.get("direction") or "neutral")
    d3_dir = str(d3.get("direction") or "neutral")
    d7_dir = str(d7.get("direction") or "neutral")
    h4_dir = str(h4.get("direction") or "neutral")
    h24_accepted = _accepted(h24)
    d3_accepted = _accepted(d3)

    if h24_dir in {"bullish", "bearish"} and h24_dir == d3_dir and h24_accepted and d3_accepted:
        return {
            "dominant_horizon": "24h",
            "alignment": "aligned",
            "headline_direction": h24_dir,
            "headline_stage": "confirmed",
            "why_not_stronger": "24h and 3d are aligned and BTC acceptance is confirmed.",
            "why_not_reversed": "Reversal requires accepted opposite 24h/3d evidence.",
        }
    if h4_dir in {"bullish", "bearish"} and h24_dir == "neutral":
        return {
            "dominant_horizon": "4h",
            "alignment": "divergent",
            "headline_direction": h4_dir,
            "headline_stage": "watch",
            "why_not_stronger": "4h can only create watch state until 24h accepts the move.",
            "why_not_reversed": "3d/7d have not confirmed a reversal.",
        }
    if h24_dir in {"bullish", "bearish"} and d3_dir in {"bullish", "bearish"} and h24_dir != d3_dir:
        return {
            "dominant_horizon": "24h",
            "alignment": "conflict",
            "headline_direction": "neutral",
            "headline_stage": "conflict",
            "why_not_stronger": "24h and 3d disagree, so headline cannot upgrade.",
            "why_not_reversed": "One horizon must lose acceptance before reversal is valid.",
        }
    if h24_dir in {"bullish", "bearish"} and d7_dir in {"bullish", "bearish"} and h24_dir != d7_dir:
        return {
            "dominant_horizon": "24h",
            "alignment": "divergent",
            "headline_direction": h24_dir,
            "headline_stage": "watch",
            "why_not_stronger": "7d is regime context and does not override 24h, but it caps conviction.",
            "why_not_reversed": "Need 3d acceptance in the same direction as 24h.",
        }
    return {
        "dominant_horizon": "24h" if abs(float(h24.get("effective_score") or 0.0)) >= abs(float(d3.get("effective_score") or 0.0)) else "3d",
        "alignment": "aligned" if h24_dir == d3_dir and h24_dir != "neutral" else "divergent" if h24_dir != d3_dir else "blocked" if h24.get("signal_stage") == "blocked" else "aligned",
        "headline_direction": h24_dir if h24_dir != "neutral" else d3_dir if d3_dir != "neutral" else "neutral",
        "headline_stage": "watch" if h24_dir != "neutral" or d3_dir != "neutral" else "blocked" if h24.get("signal_stage") == "blocked" else "watch",
        "why_not_stronger": "Need 24h and 3d same-direction acceptance for confirmed headline.",
        "why_not_reversed": "No accepted opposite multi-horizon evidence yet.",
    }


def _accepted(horizon: dict[str, Any]) -> bool:
    return str((horizon.get("acceptance") or {}).get("state") or "") == "accepted"


def _signal_stage(horizon: str, score: float, acceptance: dict[str, Any]) -> str:
    if str(acceptance.get("state")) == "blocked":
        return "blocked"
    if str(acceptance.get("state")) == "rejected":
        return "rejected"
    mag = abs(score)
    if horizon == "4h":
        if mag >= 0.30:
            return "fast_signal"
        if mag >= 0.12:
            return "early_warning"
        return "none"
    if mag >= 0.45 and acceptance.get("state") == "accepted":
        return "confirmed_signal"
    if mag >= 0.30:
        return "fast_signal"
    if mag >= 0.15:
        return "early_warning"
    return "none"


def _direction(score: float) -> str:
    if score >= 0.15:
        return "bullish"
    if score <= -0.15:
        return "bearish"
    return "neutral"


def _confidence(score: float, acceptance: dict[str, Any], quality_penalty: float) -> float:
    state = str(acceptance.get("state") or "unconfirmed")
    base = {
        "accepted": 68.0,
        "fragile": 58.0,
        "unconfirmed": 48.0,
        "rejected": 42.0,
        "blocked": 0.0,
    }.get(state, 45.0)
    return _clip(base + min(18.0, abs(score) * 35.0) - quality_penalty, 0.0, 100.0)


def _next_confirmation(
    horizon: str,
    direction: str,
    acceptance: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
) -> list[str]:
    if acceptance.get("state") == "blocked":
        return ["restore BTC response, residual and data-quality inputs"]
    if horizon == "4h":
        return ["24h accepts the 4h fast move", "orderflow and residual remain same-direction"]
    if horizon == "24h":
        return ["4h fast layer remains aligned", "BTC acceptance stays accepted", "fund flow or derivatives do not reject the move"]
    if horizon == "3d":
        return ["fund flow and macro remain same-direction", "BTC residual confirms the 3d pressure/support"]
    return ["24h/3d do not invalidate the regime", "fund flow persistence and on-chain/adoption context remain stable"]


def _next_invalidation(
    horizon: str,
    direction: str,
    acceptance: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
) -> list[str]:
    rejected = [str(item.get("module_id")) for item in evidence.get("rejected", []) if item.get("module_id")]
    if rejected:
        return [f"rejection persists in {', '.join(rejected[:2])}"]
    if direction == "neutral":
        return ["new same-direction evidence breaks neutral only after BTC acceptance"]
    return ["BTC residual flips against the horizon", "price/flow acceptance rejects the current direction"]


def _summary(
    horizon: str,
    direction: str,
    stage: str,
    acceptance: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
) -> str:
    support = _modules(evidence, positive=True)
    pressure = _modules(evidence, positive=False)
    acceptance_state = str(acceptance.get("state") or "unconfirmed")
    if horizon == "4h":
        prefix = "4h fast layer"
    elif horizon == "24h":
        prefix = "24h short trend"
    elif horizon == "3d":
        prefix = "3d flow/macro layer"
    else:
        prefix = "7d regime layer"
    return (
        f"{prefix}: {direction}; stage {stage}; BTC acceptance {acceptance_state}. "
        f"Support {', '.join(support[:2]) or 'none'}; pressure {', '.join(pressure[:2]) or 'none'}."
    )


def _modules(evidence: dict[str, list[dict[str, Any]]], *, positive: bool) -> list[str]:
    items = [
        item
        for bucket in ("trigger_eligible", "confirmation", "regime_only", "context_only")
        for item in evidence.get(bucket, [])
    ]
    return [
        str(item.get("module_id"))
        for item in items
        if (float(item.get("contribution") or 0.0) > 0 if positive else float(item.get("contribution") or 0.0) < 0)
    ]


def _data_quality_flags(signals: list[dict[str, Any]], data_quality: dict[str, Any] | None) -> list[Any]:
    flags: list[Any] = []
    for item in signals:
        flags.extend(item.get("data_quality_flags") or [])
    if data_quality:
        for key in ("status", "unavailable_metric_count", "missing_freshness_count"):
            value = data_quality.get(key)
            if value not in (None, 0, "ok", "passed"):
                flags.append({key: value})
    return flags


def _blocking(contract_validation: dict[str, Any] | None, data_quality: dict[str, Any] | None) -> bool:
    if str((contract_validation or {}).get("status") or "passed") not in {"passed", "ok"}:
        return True
    status = str((data_quality or {}).get("status") or "").lower()
    if status in {"failed", "blocked"}:
        return True
    unavailable = _num((data_quality or {}).get("unavailable_metric_count"))
    return unavailable >= 100


def _normalize_response(value: Any) -> float:
    number = _num(value)
    if abs(number) > 1.5:
        number = number / 100.0
    return _clip(number, -1.0, 1.0)


def _normalize_residual(value: Any) -> float:
    number = _num(value)
    if abs(number) > 1.5:
        number = number / 3.0
    return _clip(number, -1.0, 1.0)


def _acceptance_score(state: str, response: float | None) -> float:
    baseline = {
        "accepted": 72.0,
        "fragile": 55.0,
        "unconfirmed": 42.0,
        "rejected": 22.0,
        "blocked": 0.0,
    }.get(state, 40.0)
    if response is None:
        return baseline
    return _clip(baseline + abs(response) * 18.0, 0.0, 100.0)


def _round_score(value: float | None) -> float | None:
    return round(value * 100.0, 2) if value is not None else None


def _avg(values: list[float | None]) -> float | None:
    items = [float(value) for value in values if value is not None]
    if not items:
        return None
    return sum(items) / len(items)


def _sign(value: float) -> int:
    if value > 0.05:
        return 1
    if value < -0.05:
        return -1
    return 0


def _num(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
