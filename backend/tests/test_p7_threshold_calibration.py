from __future__ import annotations

from onlybtc.calibration.thresholds import (
    base_thresholds,
    build_state_alert_threshold_recommendation,
)
from onlybtc.direct_trend.state_machine import DEFAULT_THRESHOLDS


def test_base_direct_trend_thresholds_mirror_production_defaults() -> None:
    thresholds = base_thresholds()
    assert thresholds["direct_trend"] == DEFAULT_THRESHOLDS
    assert thresholds["p4_state_machine"]["critical_publish_confidence"] == 0.62
    assert thresholds["p4_alerts"]["data_quality_confidence_cap"] == 0.45


def test_overconfident_bucket_raises_acceptance_trust_and_critical_publish() -> None:
    recommendation = build_state_alert_threshold_recommendation(_evaluation_report())
    base = recommendation["base_thresholds"]
    recommended = recommendation["recommended_thresholds"]
    assert recommendation["applied_to_production"] is False
    assert recommended["direct_trend"]["acceptance"] > base["direct_trend"]["acceptance"]
    assert recommended["direct_trend"]["trust"] > base["direct_trend"]["trust"]
    assert (
        recommended["p4_state_machine"]["critical_publish_confidence"]
        > base["p4_state_machine"]["critical_publish_confidence"]
    )
    assert recommended["direct_trend_confidence_caps"]["70-85"] == 65.0


def test_missing_evaluation_keeps_base_thresholds_and_records_gap() -> None:
    recommendation = build_state_alert_threshold_recommendation(None)
    assert recommendation["recommended_thresholds"] == recommendation["base_thresholds"]
    assert recommendation["input_evaluation"]["has_valid_evaluation"] is False
    assert any(item["scope"] == "evaluation" for item in recommendation["evidence_gaps"])
    assert "does_not_modify_state_machine" in recommendation["guardrails"]


def test_threshold_recommendations_stay_within_bounds_and_have_rollback() -> None:
    recommendation = build_state_alert_threshold_recommendation(_evaluation_report())
    direct = recommendation["recommended_thresholds"]["direct_trend"]
    p4 = recommendation["recommended_thresholds"]["p4_state_machine"]
    assert all(0.0 <= value <= 100.0 for value in direct.values())
    assert all(0.0 <= value <= 1.0 for value in p4.values())
    assert recommendation["rollback"]["thresholds"] == recommendation["base_thresholds"]


def _evaluation_report() -> dict:
    return {
        "overall_status": "PASS",
        "evaluation": {
            "status": "PASS",
            "valid_sample_count": 70,
            "metrics": {
                "event_window_robustness": {
                    "status": "PASS",
                    "value": None,
                    "sample_count": 0,
                    "coverage_status": "not_applicable",
                    "reason": "no_event_window_samples_in_current_history",
                },
                "lead_time_hours": {
                    "status": "PASS",
                    "value": None,
                    "sample_count": 0,
                    "coverage_status": "not_applicable",
                    "reason": "no_4h_lead_samples_in_current_history",
                },
            },
            "calibration_buckets": [
                {
                    "bucket": "70-85",
                    "count": 70,
                    "success_rate": 0.12857142857142856,
                    "expected": 0.78,
                }
            ],
        },
    }
