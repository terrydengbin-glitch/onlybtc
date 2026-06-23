from __future__ import annotations

from onlybtc.calibration.module_weights import (
    MAX_WEIGHT,
    MIN_WEIGHT,
    base_module_weights,
    build_module_weight_recommendation,
    build_profile_weights,
    quality_adjusted_weights,
)
from onlybtc.radars.registry import MODULE_WEIGHTS


def test_base_module_weights_are_normalized_without_mutating_registry() -> None:
    before = dict(MODULE_WEIGHTS)
    weights = base_module_weights()
    assert MODULE_WEIGHTS == before
    assert round(sum(weights.values()), 6) == 1.0
    assert all(MIN_WEIGHT <= value <= MAX_WEIGHT for value in weights.values())
    assert set(weights) == set(MODULE_WEIGHTS)


def test_event_window_profile_raises_event_and_options_weights() -> None:
    base = base_module_weights()
    profile = build_profile_weights("event_window", base)
    assert round(sum(profile.values()), 6) == 1.0
    assert profile["event_policy"] > base["event_policy"]
    assert profile["options_volatility"] > base["options_volatility"]


def test_quality_adjusted_weights_discount_low_quality_module_without_deleting_it() -> None:
    base = base_module_weights()
    adjusted, discounts = quality_adjusted_weights(
        base,
        [
            {"module_id": "event_policy", "module_quality_score": 0.4},
            {"module_id": "fund_flow", "module_quality_score": 0.95},
        ],
    )
    assert round(sum(adjusted.values()), 6) == 1.0
    assert "event_policy" in adjusted
    assert adjusted["event_policy"] < base["event_policy"]
    assert any(item["module_id"] == "event_policy" for item in discounts)


def test_recommendation_is_not_applied_to_production_and_has_rollback() -> None:
    recommendation = build_module_weight_recommendation(
        [{"module_id": "event_policy", "module_score": 0.8, "module_quality_score": 1.0}],
        profile="event_window",
    )
    assert recommendation["applied_to_production"] is False
    assert recommendation["selected_profile"] == "event_window"
    assert recommendation["confidence_discount"] > 0
    assert recommendation["rollback"]["weights"] == recommendation["base_weights"]
    assert "does_not_modify_registry" in recommendation["guardrails"]
