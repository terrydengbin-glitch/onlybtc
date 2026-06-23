from __future__ import annotations

from typing import Any


SCHEMA_VERSION = "p45.btc_trend_cockpit.v2"

FAST_MODULES = {"kline_orderflow", "trade_structure_flow", "derivatives_crowding", "asia_risk"}
CONFIRMATION_MODULES = {"fund_flow", "treasury_credit", "macro_radar", "dollar_liquidity"}
REGIME_MODULES = {
    "onchain_valuation",
    "btc_adoption",
    "crypto_breadth",
    "options_volatility",
    "event_policy",
}
CONTROLLER_MODULES = {"btc_total_state", "aggregation_audit", "contract_validation", "data_quality"}

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

STAGE_MULTIPLIER = {
    "none": 0.20,
    "early_warning": 0.35,
    "fast_signal": 0.65,
    "confirmed_signal": 1.00,
    "rejected": -0.50,
    "conflict": 0.25,
}
QUALITY_MULTIPLIER = {"passed": 1.00, "partial": 0.70, "stale": 0.40, "failed": 0.00}
ACCEPTED_MULTIPLIER = {
    "accepted": 1.00,
    "unconfirmed": 0.55,
    "fragile": 0.35,
    "rejected": -0.30,
    "unknown": 0.50,
}


def build_btc_trend_cockpit(
    modules: list[dict[str, Any]],
    contract_validation: dict[str, Any] | None = None,
    data_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    module_signals = normalize_module_signals(modules)
    layer_scores = _layer_scores(module_signals)
    horizon = _horizon_views(module_signals)
    support = _support_score(module_signals)
    pressure = _pressure_score(module_signals)
    conflict = min(support, pressure) + _conflict_bonus(module_signals)
    rejection = _rejection_score(module_signals)
    acceptance = _trend_acceptance_score(module_signals)
    data_penalty = _data_quality_penalty(module_signals, data_quality)
    controller_score = _controller_score(contract_validation, data_quality, module_signals)

    blocking = _is_blocked(contract_validation, data_quality, module_signals)
    headline = _headline_state(
        layer_scores=layer_scores,
        support_score=support,
        pressure_score=pressure,
        conflict_score=conflict,
        trend_acceptance_score=acceptance,
        blocking=blocking,
        support_modules=_directional_module_count(module_signals, "bullish"),
        pressure_modules=_directional_module_count(module_signals, "bearish"),
    )
    btc_direction = _btc_direction(headline)
    trend_phase = _trend_phase(headline, acceptance, layer_scores)
    trend_quality = _trend_quality(headline, acceptance)

    support_modules = _dominant_modules(module_signals, want_positive=True)
    pressure_modules = _dominant_modules(module_signals, want_positive=False)
    rejection_modules = [
        item["module_name"] for item in module_signals if item["accepted_status"] == "rejected"
    ][:5]
    conflict_modules = [
        item["module_name"]
        for item in module_signals
        if item["signal_stage"] == "conflict" or item["effective_direction"] == "conflict"
    ][:5]

    return {
        "schema_version": SCHEMA_VERSION,
        "headline_state": headline,
        "btc_direction": btc_direction,
        "btc_strength": _strength(headline, layer_scores, acceptance),
        "trend_phase": trend_phase,
        "trend_quality": trend_quality,
        "trade_permission": _trade_permission(headline, trend_quality),
        "confidence_score": _confidence_score(acceptance, conflict, data_penalty, blocking),
        "sensitivity_score": _score_0_100(abs(layer_scores["fast_net_score"])),
        "stability_score": _score_0_100(abs(layer_scores["confirmation_net_score"]) * 0.6 + abs(layer_scores["regime_net_score"]) * 0.4),
        "horizon": horizon,
        "scores": {
            "fast_net_score": round(layer_scores["fast_net_score"], 4),
            "confirmation_net_score": round(layer_scores["confirmation_net_score"], 4),
            "regime_net_score": round(layer_scores["regime_net_score"], 4),
            "controller_score": round(controller_score, 4),
            "support_score": round(support, 4),
            "pressure_score": round(pressure, 4),
            "conflict_score": round(min(1.0, conflict), 4),
            "rejection_score": round(rejection, 4),
            "trend_acceptance_score": round(acceptance, 2),
            "data_quality_penalty": round(data_penalty, 2),
        },
        "module_signals": module_signals,
        "dominant_support_modules": support_modules,
        "dominant_pressure_modules": pressure_modules,
        "dominant_rejection_modules": rejection_modules,
        "conflict_modules": conflict_modules,
        "next_confirmation_triggers": _next_confirmation_triggers(headline, pressure_modules, support_modules),
        "next_invalidation_triggers": _next_invalidation_triggers(headline, rejection_modules),
        "watch_flags": _watch_flags(headline, module_signals),
        "data_quality_flags": _data_quality_flags(module_signals, data_quality),
        "ui_summary": _ui_summary(
            headline=headline,
            btc_direction=btc_direction,
            layer_scores=layer_scores,
            support_modules=support_modules,
            pressure_modules=pressure_modules,
            conflict_modules=conflict_modules,
            acceptance=acceptance,
        ),
    }


def normalize_module_signals(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_module_signal(module) for module in modules if module.get("radar_module")]


def _normalize_module_signal(module: dict[str, Any]) -> dict[str, Any]:
    profile = module.get("module_semantic_profile")
    if not isinstance(profile, dict):
        profile = {}
    module_name = str(module.get("radar_module") or "")
    raw_direction = _direction_value(
        _pick(module, profile, "module_direction")
        or _pick(module, profile, "module_effective_direction")
    )
    effective_direction = _direction_value(
        _pick(module, profile, "module_effective_direction")
        or _pick(module, profile, "module_direction")
    )
    signal_stage = _signal_stage(module, profile)
    score = _normalized_score(
        _pick(module, profile, "module_effective_score")
        if _pick(module, profile, "module_effective_score") is not None
        else _pick(module, profile, "module_score"),
        effective_direction,
    )
    btc_implication = str(_pick(module, profile, "btc_implication") or "")
    btc_response_score = _extract_btc_response_score(module, profile)
    residual = _extract_residual(module, profile)
    quality_status = _quality_status(module, profile)
    accepted_status = _accepted_status(effective_direction, btc_implication, btc_response_score, residual)
    stage_multiplier = STAGE_MULTIPLIER.get(signal_stage, STAGE_MULTIPLIER["none"])
    quality_multiplier = QUALITY_MULTIPLIER.get(quality_status, QUALITY_MULTIPLIER["partial"])
    accepted_multiplier = ACCEPTED_MULTIPLIER.get(accepted_status, ACCEPTED_MULTIPLIER["unknown"])
    contribution = (
        _direction_sign(effective_direction)
        * abs(score)
        * stage_multiplier
        * quality_multiplier
        * accepted_multiplier
    )
    if effective_direction == "conflict" or signal_stage == "conflict":
        contribution *= 0.25
    return {
        "module_name": module_name,
        "layer": _module_layer(module_name),
        "horizon": _primary_horizon(module_name),
        "raw_direction": raw_direction,
        "effective_direction": effective_direction,
        "signal_stage": signal_stage,
        "module_score": round(score, 4),
        "effective_score": round(score, 4),
        "btc_implication": btc_implication,
        "btc_response_score": btc_response_score,
        "residual": residual,
        "support_drivers": _driver_list(_pick(module, profile, "support_drivers")),
        "pressure_drivers": _driver_list(_pick(module, profile, "pressure_drivers")),
        "conflict_drivers": _driver_list(_pick(module, profile, "conflict_drivers")),
        "data_quality_flags": _driver_list(_pick(module, profile, "data_quality_flags")),
        "quality_status": quality_status,
        "accepted_status": accepted_status,
        "contribution": round(contribution, 4),
    }


def _pick(module: dict[str, Any], profile: dict[str, Any], key: str) -> Any:
    return module.get(key) if module.get(key) is not None else profile.get(key)


def _module_layer(module_name: str) -> str:
    if module_name in FAST_MODULES:
        return "fast"
    if module_name in CONFIRMATION_MODULES:
        return "confirmation"
    if module_name in REGIME_MODULES:
        return "regime"
    if module_name in CONTROLLER_MODULES:
        return "controller"
    return "regime"


def _primary_horizon(module_name: str) -> str:
    if module_name in {"kline_orderflow", "trade_structure_flow", "derivatives_crowding", "asia_risk"}:
        return "4h"
    if module_name in {"fund_flow", "macro_radar", "treasury_credit", "dollar_liquidity"}:
        return "3d"
    return "7d"


def _direction_value(value: Any) -> str:
    text = str(value or "neutral").lower()
    if "bull" in text:
        return "bullish"
    if "bear" in text:
        return "bearish"
    if "conflict" in text or "mixed" in text:
        return "conflict"
    if "reject" in text:
        return "rejected"
    return "neutral"


def _direction_sign(direction: str) -> float:
    if direction == "bullish":
        return 1.0
    if direction == "bearish":
        return -1.0
    return 0.0


def _normalized_score(value: Any, direction: str) -> float:
    number = _to_float(value)
    if number is None:
        number = 0.25 * _direction_sign(direction)
    if abs(number) > 1.5:
        number = number / 100.0
    if direction in {"bullish", "bearish"} and abs(number) < 0.05:
        number = 0.20 * _direction_sign(direction)
    if direction == "bearish" and number > 0:
        number = -number
    if direction == "bullish" and number < 0:
        number = abs(number)
    return _clip(number, -1.0, 1.0)


def _signal_stage(module: dict[str, Any], profile: dict[str, Any]) -> str:
    raw = str(_pick(module, profile, "signal_stage") or "").lower()
    if raw in {"early_warning", "fast_signal", "confirmed_signal", "rejected", "conflict", "none"}:
        return raw
    state_text = " ".join(
        str(_pick(module, profile, key) or "")
        for key in (
            "fund_flow_state",
            "treasury_credit_state",
            "onchain_valuation_state",
            "btc_adoption_state",
            "asia_risk_state",
            "kline_orderflow_state",
            "trade_structure_state",
            "derivatives_state",
        )
    ).lower()
    if "confirmed" in state_text:
        return "confirmed_signal"
    if "warning" in state_text:
        return "early_warning"
    if "fast" in state_text or "shift" in state_text:
        return "fast_signal"
    if "reject" in state_text:
        return "rejected"
    if "conflict" in state_text:
        return "conflict"
    return "none"


def _quality_status(module: dict[str, Any], profile: dict[str, Any]) -> str:
    flags = _driver_list(_pick(module, profile, "data_quality_flags"))
    if any("missing" in str(flag) or "unavailable" in str(flag) for flag in flags):
        return "failed"
    if any("stale" in str(flag) for flag in flags):
        return "stale"
    quality = _to_float(module.get("module_quality_score") or _pick(module, profile, "confidence_score"))
    if quality is not None and quality > 1.5:
        quality = quality / 100.0
    if quality is None or quality >= 0.65:
        return "passed"
    if quality >= 0.40:
        return "partial"
    return "failed"


def _accepted_status(
    direction: str,
    btc_implication: str,
    btc_response_score: float | None,
    residual: float | None,
) -> str:
    implication = btc_implication.lower()
    if "reject" in implication or "internal_weakness" in implication:
        return "rejected"
    if "conflict" in implication:
        return "fragile"
    if "confirmed" in implication or "accepted" in implication or "strength" in implication:
        return "accepted"
    sign = _direction_sign(direction)
    if sign == 0:
        return "unknown"
    evidence: list[float] = []
    if btc_response_score is not None:
        evidence.append(_clip(btc_response_score / 100.0 if abs(btc_response_score) > 1.5 else btc_response_score, -1.0, 1.0))
    if residual is not None:
        evidence.append(_clip(residual / 3.0 if abs(residual) > 1.5 else residual, -1.0, 1.0))
    if not evidence:
        return "unknown"
    aligned = sum(1 for item in evidence if item * sign > 0.15)
    opposed = sum(1 for item in evidence if item * sign < -0.15)
    if aligned and not opposed:
        return "accepted"
    if opposed:
        return "rejected"
    return "unconfirmed"


def _extract_btc_response_score(module: dict[str, Any], profile: dict[str, Any]) -> float | None:
    for source in (module, profile):
        scores = source.get("scores")
        if isinstance(scores, dict):
            for key in (
                "btc_response_score",
                "btc_acceptance_score",
                "price_acceptance_score",
                "trend_acceptance_score",
            ):
                value = _to_float(scores.get(key))
                if value is not None:
                    return value
        for key in ("btc_response_score", "btc_acceptance_score", "price_acceptance_score", "trend_acceptance_score"):
            value = _to_float(source.get(key))
            if value is not None:
                return value
    return None


def _extract_residual(module: dict[str, Any], profile: dict[str, Any]) -> float | None:
    for source in (module, profile):
        for key in (
            "derivatives_residual_z",
            "trade_structure_residual_z",
            "asia_risk_residual_z_90d",
            "orderflow_residual_z_60",
            "fund_flow_residual_z_60d",
            "onchain_residual_z_90d",
            "adoption_residual_z_90d",
            "btc_residual_24h",
        ):
            value = _to_float(source.get(key))
            if value is not None:
                return value
        nested = source.get("btc_response_confirmation")
        if isinstance(nested, dict):
            for key in ("residual_z_90d", "residual_z_60d", "btc_residual_24h", "residual_24h"):
                value = _to_float(nested.get(key))
                if value is not None:
                    return value
        states = source.get("states")
        if isinstance(states, dict):
            for nested in states.values():
                if isinstance(nested, dict):
                    for key in ("residual_z_90d", "residual_z_60d", "residual_24h"):
                        value = _to_float(nested.get(key))
                        if value is not None:
                            return value
    return None


def _driver_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _layer_scores(signals: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "fast_net_score": _average_contribution(signals, "fast"),
        "confirmation_net_score": _average_contribution(signals, "confirmation"),
        "regime_net_score": _average_contribution(signals, "regime"),
    }


def _average_contribution(signals: list[dict[str, Any]], layer: str) -> float:
    items = [float(item["contribution"]) for item in signals if item["layer"] == layer]
    if not items:
        return 0.0
    return _clip(sum(items) / max(1.0, len(items)), -1.0, 1.0)


def _horizon_views(signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_module = {item["module_name"]: item for item in signals}
    result: dict[str, dict[str, Any]] = {}
    for horizon, weights in HORIZON_WEIGHTS.items():
        score = 0.0
        total = 0.0
        drivers: list[str] = []
        rejectors: list[str] = []
        for module_name, weight in weights.items():
            signal = by_module.get(module_name)
            if not signal:
                continue
            score += float(signal["contribution"]) * weight
            total += weight
            if float(signal["contribution"]) > 0:
                drivers.append(module_name)
            if float(signal["contribution"]) < 0:
                rejectors.append(module_name)
        normalized = _clip(score / total if total else 0.0, -1.0, 1.0)
        result[horizon] = {
            "direction": _signed_direction(normalized),
            "stage": _horizon_stage(normalized),
            "score": round(normalized, 4),
            "drivers": drivers[:5],
            "rejectors": rejectors[:5],
        }
    return result


def _support_score(signals: list[dict[str, Any]]) -> float:
    return _clip(sum(max(0.0, float(item["contribution"])) for item in signals), 0.0, 1.0)


def _pressure_score(signals: list[dict[str, Any]]) -> float:
    return _clip(sum(abs(min(0.0, float(item["contribution"]))) for item in signals), 0.0, 1.0)


def _conflict_bonus(signals: list[dict[str, Any]]) -> float:
    return min(0.5, sum(0.1 for item in signals if item["signal_stage"] == "conflict" or item["effective_direction"] == "conflict"))


def _rejection_score(signals: list[dict[str, Any]]) -> float:
    return _clip(sum(0.2 for item in signals if item["accepted_status"] == "rejected"), 0.0, 1.0)


def _trend_acceptance_score(signals: list[dict[str, Any]]) -> float:
    fast = [item for item in signals if item["layer"] == "fast"]
    accepted = sum(1 for item in signals if item["accepted_status"] == "accepted")
    rejected = sum(1 for item in signals if item["accepted_status"] == "rejected")
    response_values = [
        abs(float(item["btc_response_score"]))
        for item in signals
        if item.get("btc_response_score") is not None
    ]
    price_response = min(100.0, sum(response_values) / len(response_values)) if response_values else 45.0
    residual_alignment = 70.0 if accepted > rejected else 30.0 if rejected > accepted else 50.0
    orderflow_confirmation = 65.0 if any(item["accepted_status"] == "accepted" for item in fast) else 40.0
    continuation = 70.0 if sum(1 for item in signals if item["signal_stage"] == "confirmed_signal") >= 2 else 45.0
    score = (
        0.35 * price_response
        + 0.25 * residual_alignment
        + 0.25 * orderflow_confirmation
        + 0.15 * continuation
    )
    return _clip(score, 0.0, 100.0)


def _data_quality_penalty(signals: list[dict[str, Any]], data_quality: dict[str, Any] | None) -> float:
    failed = sum(1 for item in signals if item["quality_status"] == "failed")
    stale = sum(1 for item in signals if item["quality_status"] == "stale")
    unavailable = _to_float((data_quality or {}).get("unavailable_metric_count")) or 0.0
    return min(40.0, failed * 10.0 + stale * 5.0 + min(10.0, unavailable))


def _controller_score(
    contract_validation: dict[str, Any] | None,
    data_quality: dict[str, Any] | None,
    signals: list[dict[str, Any]],
) -> float:
    score = 1.0
    if str((contract_validation or {}).get("status") or "passed") != "passed":
        score -= 0.6
    if _data_quality_penalty(signals, data_quality) >= 30:
        score -= 0.4
    return _clip(score, 0.0, 1.0)


def _is_blocked(
    contract_validation: dict[str, Any] | None,
    data_quality: dict[str, Any] | None,
    signals: list[dict[str, Any]],
) -> bool:
    if str((contract_validation or {}).get("status") or "passed") not in {"passed", "ok"}:
        return True
    if _data_quality_penalty(signals, data_quality) >= 35:
        return True
    fast_available = sum(1 for item in signals if item["layer"] == "fast" and item["quality_status"] != "failed")
    return bool(signals) and fast_available == 0


def _headline_state(
    *,
    layer_scores: dict[str, float],
    support_score: float,
    pressure_score: float,
    conflict_score: float,
    trend_acceptance_score: float,
    blocking: bool,
    support_modules: int,
    pressure_modules: int,
) -> str:
    fast = layer_scores["fast_net_score"]
    confirmation = layer_scores["confirmation_net_score"]
    if blocking:
        return "blocked"
    if support_score >= 0.35 and pressure_score >= 0.35:
        return "conflict"
    if conflict_score >= 0.35 or fast * confirmation < -0.02:
        return "conflict"
    if fast >= 0.30 and confirmation >= 0.20 and trend_acceptance_score >= 65 and support_modules >= 2 and pressure_score < 0.45:
        return "confirmed_bullish"
    if fast <= -0.30 and confirmation <= -0.20 and trend_acceptance_score >= 65 and pressure_modules >= 2 and support_score < 0.45:
        return "confirmed_bearish"
    if fast >= 0.25 or confirmation >= 0.25:
        return "bullish_watch"
    if fast <= -0.25 or confirmation <= -0.25:
        return "bearish_watch"
    return "neutral"


def _directional_module_count(signals: list[dict[str, Any]], direction: str) -> int:
    return sum(
        1
        for item in signals
        if item["effective_direction"] == direction and item["accepted_status"] != "rejected"
    )


def _btc_direction(headline: str) -> str:
    if "bullish" in headline:
        return "bullish"
    if "bearish" in headline:
        return "bearish"
    return "neutral"


def _trend_phase(headline: str, acceptance: float, layer_scores: dict[str, float]) -> str:
    if headline == "blocked":
        return "neutral"
    if headline == "conflict":
        return "conflict"
    if headline.startswith("confirmed"):
        return "confirmed_signal"
    if "watch" in headline:
        return "fast_signal" if abs(layer_scores["fast_net_score"]) >= 0.25 else "confirmation_pending"
    if acceptance < 25:
        return "rejected"
    return "neutral"


def _trend_quality(headline: str, acceptance: float) -> str:
    if headline == "blocked":
        return "blocked"
    if headline == "conflict":
        return "mixed"
    if acceptance >= 65:
        return "accepted"
    if acceptance >= 45:
        return "unconfirmed"
    if acceptance >= 25:
        return "fragile"
    return "rejected"


def _strength(headline: str, layer_scores: dict[str, float], acceptance: float) -> str:
    if headline in {"blocked", "neutral", "conflict"}:
        return "none"
    magnitude = max(abs(layer_scores["fast_net_score"]), abs(layer_scores["confirmation_net_score"]))
    if acceptance >= 70 and magnitude >= 0.45:
        return "strong"
    if magnitude >= 0.25:
        return "medium"
    return "weak"


def _trade_permission(headline: str, trend_quality: str) -> str:
    if headline == "blocked":
        return "blocked"
    if headline in {"conflict", "neutral"}:
        return "watch_only"
    if headline.startswith("confirmed") and trend_quality == "accepted":
        return "small_size"
    if "watch" in headline:
        return "watch_only"
    return "watch_only"


def _confidence_score(acceptance: float, conflict: float, data_penalty: float, blocking: bool) -> float:
    if blocking:
        return 0.0
    return round(_clip(55.0 + acceptance * 0.35 - conflict * 25.0 - data_penalty, 0.0, 100.0), 2)


def _dominant_modules(signals: list[dict[str, Any]], want_positive: bool) -> list[str]:
    items = sorted(
        signals,
        key=lambda item: abs(float(item["contribution"])),
        reverse=True,
    )
    return [
        item["module_name"]
        for item in items
        if (float(item["contribution"]) > 0 if want_positive else float(item["contribution"]) < 0)
    ][:5]


def _next_confirmation_triggers(
    headline: str,
    pressure_modules: list[str],
    support_modules: list[str],
) -> list[str]:
    if headline == "bearish_watch":
        return ["15m/1h orderflow remains negative", "BTC residual turns negative", "at least two pressure modules stay aligned"]
    if headline == "bullish_watch":
        return ["fast layer remains positive", "fund flow or macro confirms support", "BTC residual stays positive"]
    if headline == "conflict":
        return ["support/pressure imbalance resolves", "BTC response confirms one side"]
    if headline == "neutral":
        return ["fast layer produces same-direction signal", "confirmation layer follows"]
    return [f"watch dominant modules: {', '.join((support_modules or pressure_modules)[:2])}"]


def _next_invalidation_triggers(headline: str, rejection_modules: list[str]) -> list[str]:
    if headline.startswith("confirmed"):
        return ["trend acceptance drops below 45", "dominant drivers flip direction", "data quality becomes blocking"]
    if "watch" in headline:
        return ["BTC rejects the watch direction", "residual moves against the signal"]
    if rejection_modules:
        return [f"rejection persists in {', '.join(rejection_modules[:2])}"]
    return ["new conflicting fast-layer evidence appears"]


def _watch_flags(headline: str, signals: list[dict[str, Any]]) -> list[str]:
    flags = []
    if headline in {"bearish_watch", "bullish_watch"}:
        flags.append("watch_state_not_confirmed")
    if any(item["accepted_status"] == "rejected" for item in signals):
        flags.append("btc_rejection_present")
    if any(item["quality_status"] in {"stale", "failed"} for item in signals):
        flags.append("module_data_quality_downgrade")
    return flags


def _data_quality_flags(signals: list[dict[str, Any]], data_quality: dict[str, Any] | None) -> list[Any]:
    flags: list[Any] = []
    for item in signals:
        flags.extend(item.get("data_quality_flags") or [])
    if data_quality:
        for key in ("status", "unavailable_metric_count", "missing_freshness_count"):
            value = data_quality.get(key)
            if value not in (None, 0, "ok", "passed"):
                flags.append({key: value})
    return flags[:20]


def _ui_summary(
    *,
    headline: str,
    btc_direction: str,
    layer_scores: dict[str, float],
    support_modules: list[str],
    pressure_modules: list[str],
    conflict_modules: list[str],
    acceptance: float,
) -> dict[str, str]:
    return {
        "fast_read": f"Fast layer score {layer_scores['fast_net_score']:+.2f}; direction {btc_direction}.",
        "confirmation_read": f"Confirmation layer score {layer_scores['confirmation_net_score']:+.2f}; acceptance {acceptance:.0f}.",
        "main_pressure": ", ".join(pressure_modules[:2]) or "No dominant pressure module.",
        "main_support": ", ".join(support_modules[:2]) or "No dominant support module.",
        "why_not_strong": _why_not_strong(headline, acceptance, conflict_modules),
        "next_trigger": "Need BTC response, residual and at least two aligned modules to upgrade.",
        "invalidation": "Invalid if BTC rejects the direction, residual flips, or data quality blocks.",
    }


def _why_not_strong(headline: str, acceptance: float, conflict_modules: list[str]) -> str:
    if headline.startswith("confirmed"):
        return "Trend is confirmed but still monitored for residual and data-quality deterioration."
    if headline == "conflict":
        return "Support and pressure coexist; no strong direction until conflict resolves."
    if acceptance < 65:
        return "BTC has not fully accepted the surrounding module pressure/support."
    if conflict_modules:
        return f"Conflict modules remain: {', '.join(conflict_modules[:2])}."
    return "Not enough same-direction modules for a strong headline."


def _signed_direction(score: float) -> str:
    if score >= 0.10:
        return "bullish"
    if score <= -0.10:
        return "bearish"
    return "neutral"


def _horizon_stage(score: float) -> str:
    mag = abs(score)
    if mag >= 0.35:
        return "confirmed_signal"
    if mag >= 0.20:
        return "fast_signal"
    if mag >= 0.10:
        return "early_warning"
    return "none"


def _score_0_100(value: float) -> float:
    return round(_clip(value, 0.0, 1.0) * 100.0, 2)


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
