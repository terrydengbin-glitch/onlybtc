from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from onlybtc.radars.registry import MODULE_WEIGHTS

SCHEMA_VERSION = "p7.c01.module_weight_calibration.v1"
MIN_WEIGHT = 0.02
MAX_WEIGHT = 0.16

PROFILE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "base": {},
    "macro_shock": {
        "macro_radar": 1.35,
        "dollar_liquidity": 1.3,
        "treasury_credit": 1.25,
        "event_policy": 1.2,
        "options_volatility": 1.1,
    },
    "bull_trend": {
        "fund_flow": 1.35,
        "btc_adoption": 1.25,
        "kline_orderflow": 1.2,
        "trade_structure_flow": 1.15,
        "crypto_breadth": 1.15,
    },
    "leverage_crowding": {
        "derivatives_crowding": 1.35,
        "trade_structure_flow": 1.25,
        "options_volatility": 1.2,
        "kline_orderflow": 1.15,
        "event_policy": 1.1,
    },
    "event_window": {
        "event_policy": 1.45,
        "options_volatility": 1.25,
        "macro_radar": 1.15,
        "dollar_liquidity": 1.1,
    },
}

PROFILE_CONFIDENCE_DISCOUNTS: dict[str, float] = {
    "base": 0.0,
    "macro_shock": 0.04,
    "bull_trend": 0.0,
    "leverage_crowding": 0.05,
    "event_window": 0.10,
}


def base_module_weights() -> dict[str, float]:
    return normalize_weights(dict(MODULE_WEIGHTS))


def normalize_weights(
    weights: dict[str, float],
    *,
    min_weight: float = MIN_WEIGHT,
    max_weight: float = MAX_WEIGHT,
) -> dict[str, float]:
    clipped = {
        module_id: min(max(float(weight), min_weight), max_weight)
        for module_id, weight in weights.items()
    }
    total = sum(clipped.values())
    if total <= 0:
        equal = round(1.0 / max(len(clipped), 1), 6)
        return {module_id: equal for module_id in clipped}
    normalized = {module_id: weight / total for module_id, weight in clipped.items()}
    return _rebalance_caps(normalized, min_weight=min_weight, max_weight=max_weight)


def build_profile_weights(profile: str, base: dict[str, float] | None = None) -> dict[str, float]:
    base_weights = dict(base or base_module_weights())
    multipliers = PROFILE_MULTIPLIERS.get(profile)
    if multipliers is None:
        raise KeyError(f"Unknown module weight profile: {profile}")
    adjusted = {
        module_id: weight * float(multipliers.get(module_id, 1.0))
        for module_id, weight in base_weights.items()
    }
    return normalize_weights(adjusted)


def quality_adjusted_weights(
    weights: dict[str, float],
    modules: list[dict[str, Any]],
    *,
    floor: float = 0.55,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    quality_by_module = {
        str(module.get("module_id") or module.get("module") or module.get("id")): _module_quality(module)
        for module in modules
    }
    adjusted: dict[str, float] = {}
    discounts: list[dict[str, Any]] = []
    for module_id, weight in weights.items():
        quality = quality_by_module.get(module_id)
        if quality is None:
            adjusted[module_id] = weight
            continue
        multiplier = max(float(quality), floor)
        adjusted[module_id] = weight * multiplier
        if multiplier < 0.85:
            discounts.append(
                {
                    "module_id": module_id,
                    "quality": round(float(quality), 4),
                    "applied_multiplier": round(multiplier, 4),
                    "reason": "module_quality_score_below_0.85",
                }
            )
    return normalize_weights(adjusted), discounts


def choose_profile(modules: list[dict[str, Any]]) -> dict[str, Any]:
    scores = {
        "macro_shock": _profile_signal(
            modules,
            ["macro_radar", "dollar_liquidity", "treasury_credit", "event_policy"],
        ),
        "bull_trend": _profile_signal(
            modules,
            ["fund_flow", "btc_adoption", "kline_orderflow", "trade_structure_flow", "crypto_breadth"],
            positive_only=True,
        ),
        "leverage_crowding": _profile_signal(
            modules,
            ["derivatives_crowding", "trade_structure_flow", "options_volatility", "kline_orderflow"],
        ),
        "event_window": _profile_signal(modules, ["event_policy", "options_volatility", "macro_radar"]),
    }
    if not modules:
        return {
            "profile": "base",
            "reason": "no_latest_module_payload",
            "profile_scores": scores,
        }
    profile = max(scores, key=scores.get)
    if scores[profile] < 0.25:
        return {
            "profile": "base",
            "reason": "no_profile_signal_above_threshold",
            "profile_scores": scores,
        }
    return {
        "profile": profile,
        "reason": f"{profile}_score_dominant",
        "profile_scores": scores,
    }


def build_module_weight_recommendation(
    modules: list[dict[str, Any]] | None = None,
    *,
    profile: str | None = None,
) -> dict[str, Any]:
    module_rows = list(modules or [])
    base = base_module_weights()
    selected = {"profile": profile, "reason": "manual_profile", "profile_scores": {}}
    if profile is None:
        selected = choose_profile(module_rows)
        profile = str(selected["profile"])
    profile_weights = build_profile_weights(profile, base)
    recommended, discounts = quality_adjusted_weights(profile_weights, module_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "applied_to_production": False,
        "production_source": "onlybtc.radars.registry.MODULE_WEIGHTS",
        "selected_profile": profile,
        "profile_reason": selected.get("reason"),
        "profile_scores": selected.get("profile_scores", {}),
        "confidence_discount": PROFILE_CONFIDENCE_DISCOUNTS.get(profile, 0.0),
        "base_weights": base,
        "profile_weights": profile_weights,
        "recommended_weights": recommended,
        "quality_discounts": discounts,
        "rollback": {
            "type": "restore_base_registry_weights",
            "weights": base,
        },
        "guardrails": [
            "recommendation_only",
            "does_not_modify_registry",
            "does_not_modify_state_machine",
            "does_not_emit_trading_advice",
            "requires_p7_c08_before_production_apply",
        ],
    }


def _rebalance_caps(
    weights: dict[str, float],
    *,
    min_weight: float,
    max_weight: float,
) -> dict[str, float]:
    result = dict(weights)
    for _ in range(12):
        changed = False
        fixed: dict[str, float] = {}
        floating: dict[str, float] = {}
        for module_id, weight in result.items():
            if weight < min_weight:
                fixed[module_id] = min_weight
                changed = True
            elif weight > max_weight:
                fixed[module_id] = max_weight
                changed = True
            else:
                floating[module_id] = weight
        remaining = max(1.0 - sum(fixed.values()), 0.0)
        floating_total = sum(floating.values())
        if floating and floating_total > 0:
            result = {
                **fixed,
                **{module_id: weight / floating_total * remaining for module_id, weight in floating.items()},
            }
        else:
            result = fixed
        if not changed:
            break
    total = sum(result.values())
    normalized = {module_id: round(weight / total, 6) for module_id, weight in result.items()}
    drift = round(1.0 - sum(normalized.values()), 6)
    if normalized and drift:
        largest = max(normalized, key=normalized.get)
        normalized[largest] = round(normalized[largest] + drift, 6)
    return dict(sorted(normalized.items()))


def _module_quality(module: dict[str, Any]) -> float:
    for key in ("module_quality_score", "quality_score", "source_quality_score", "confidence_score"):
        value = module.get(key)
        if value is None:
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score > 1.0:
            return max(min(score / 100.0, 1.0), 0.0)
        return max(min(score, 1.0), 0.0)
    flags = module.get("data_quality_flags") or []
    return 0.72 if flags else 1.0


def _profile_signal(
    modules: list[dict[str, Any]],
    module_ids: list[str],
    *,
    positive_only: bool = False,
) -> float:
    values: list[float] = []
    wanted = set(module_ids)
    for module in modules:
        module_id = str(module.get("module_id") or module.get("module") or module.get("id") or "")
        if module_id not in wanted:
            continue
        raw = _numeric(
            module.get("module_effective_score")
            or module.get("module_score")
            or module.get("score")
            or module.get("direction_score")
        )
        if raw is None:
            raw = _numeric(module.get("risk_score"))
        if raw is None:
            continue
        scaled = raw / 100.0 if abs(raw) > 1 else raw
        values.append(max(scaled, 0.0) if positive_only else abs(scaled))
    return round(sum(values) / len(module_ids), 6) if module_ids else 0.0


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
