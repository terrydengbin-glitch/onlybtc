from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from onlybtc.direct_trend.state_machine import DEFAULT_THRESHOLDS

SCHEMA_VERSION = "p7.c02.state_alert_threshold_calibration.v1"

P4_STATE_MACHINE_BASE_THRESHOLDS: dict[str, float] = {
    "low_baseline_confidence": 0.50,
    "critical_publish_confidence": 0.62,
    "trend_candidate_confidence": 0.50,
    "warning_aggregate_abs_score": 0.35,
}

P4_ALERT_BASE_THRESHOLDS: dict[str, float] = {
    "watch_confidence": 0.45,
    "data_quality_confidence_cap": 0.45,
    "run_mode_integrity_alert_level": 1.0,
    "blocked_alert_level": 0.25,
}

THRESHOLD_RANGES: dict[str, tuple[float, float]] = {
    "p4_state_machine.low_baseline_confidence": (0.0, 1.0),
    "p4_state_machine.critical_publish_confidence": (0.0, 1.0),
    "p4_state_machine.trend_candidate_confidence": (0.0, 1.0),
    "p4_state_machine.warning_aggregate_abs_score": (0.0, 1.0),
    "p4_alerts.watch_confidence": (0.0, 1.0),
    "p4_alerts.data_quality_confidence_cap": (0.0, 1.0),
    "p4_alerts.run_mode_integrity_alert_level": (0.0, 3.0),
    "p4_alerts.blocked_alert_level": (0.0, 3.0),
}

for _key in DEFAULT_THRESHOLDS:
    THRESHOLD_RANGES[f"direct_trend.{_key}"] = (0.0, 100.0)


def base_thresholds() -> dict[str, dict[str, float]]:
    return {
        "p4_state_machine": deepcopy(P4_STATE_MACHINE_BASE_THRESHOLDS),
        "p4_alerts": deepcopy(P4_ALERT_BASE_THRESHOLDS),
        "direct_trend": deepcopy(DEFAULT_THRESHOLDS),
    }


def build_state_alert_threshold_recommendation(
    evaluation_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = base_thresholds()
    recommended = deepcopy(base)
    evaluation = summarize_direct_trend_evaluation(evaluation_report)
    adjustments: list[dict[str, Any]] = []
    evidence_gaps = _evidence_gaps(evaluation)

    overconfidence = _overconfidence_signal(evaluation)
    if overconfidence:
        severity = overconfidence["severity"]
        direct_delta = 10.0 if severity == "severe" else 5.0
        critical_delta = 0.05 if severity == "severe" else 0.03
        confidence_cap = 65.0 if severity == "severe" else 70.0
        _raise_threshold(
            recommended,
            "direct_trend",
            "acceptance",
            direct_delta,
            adjustments,
            reason=overconfidence["reason"],
        )
        _raise_threshold(
            recommended,
            "direct_trend",
            "trust",
            direct_delta,
            adjustments,
            reason=overconfidence["reason"],
        )
        _raise_threshold(
            recommended,
            "direct_trend",
            "strong_direction",
            direct_delta / 2.0,
            adjustments,
            reason=overconfidence["reason"],
        )
        _raise_threshold(
            recommended,
            "p4_state_machine",
            "critical_publish_confidence",
            critical_delta,
            adjustments,
            reason=overconfidence["reason"],
        )
        recommended.setdefault("direct_trend_confidence_caps", {})[
            overconfidence["bucket"]
        ] = confidence_cap
        adjustments.append(
            {
                "scope": "direct_trend_confidence_caps",
                "key": overconfidence["bucket"],
                "base": None,
                "recommended": confidence_cap,
                "delta": None,
                "reason": overconfidence["reason"],
            }
        )

    if not evaluation["has_valid_evaluation"]:
        adjustments.append(
            {
                "scope": "all",
                "key": "production_apply",
                "base": False,
                "recommended": False,
                "delta": None,
                "reason": "missing_or_invalid_evaluation_report",
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "applied_to_production": False,
        "production_sources": {
            "p4_state_machine": "onlybtc.p4.state_machine",
            "p4_alerts": "onlybtc.p4.final_controller",
            "direct_trend": "onlybtc.direct_trend.state_machine.DEFAULT_THRESHOLDS",
        },
        "input_evaluation": evaluation,
        "base_thresholds": base,
        "recommended_thresholds": _bounded_thresholds(recommended),
        "adjustments": adjustments,
        "evidence_gaps": evidence_gaps,
        "rollback": {
            "type": "restore_base_thresholds",
            "thresholds": base,
        },
        "guardrails": [
            "recommendation_only",
            "does_not_modify_state_machine",
            "does_not_modify_alert_controller",
            "does_not_modify_direct_trend_thresholds",
            "does_not_emit_trading_advice",
            "does_not_relax_warning_sensitivity_without_p7_c08",
            "requires_p7_c08_before_production_apply",
        ],
    }


def summarize_direct_trend_evaluation(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {
            "has_valid_evaluation": False,
            "overall_status": "missing",
            "sample_count": 0,
            "metrics": {},
            "calibration_buckets": [],
            "notes": ["evaluation_report_missing"],
        }
    evaluation = report.get("evaluation") or {}
    metrics = evaluation.get("metrics") or {}
    sample_count = int(
        evaluation.get("valid_sample_count")
        or (report.get("sample_builder") or {}).get("sample_count")
        or 0
    )
    return {
        "has_valid_evaluation": bool(sample_count and evaluation.get("status") != "missing"),
        "overall_status": str(report.get("overall_status") or evaluation.get("status") or "unknown"),
        "sample_count": sample_count,
        "split_policy": evaluation.get("split_policy") or {},
        "metrics": {
            key: _metric_summary(value)
            for key, value in metrics.items()
            if isinstance(value, dict)
        },
        "calibration_buckets": [
            {
                "bucket": str(bucket.get("bucket")),
                "count": int(bucket.get("count") or 0),
                "success_rate": _optional_float(bucket.get("success_rate")),
                "expected": _optional_float(bucket.get("expected")),
            }
            for bucket in evaluation.get("calibration_buckets") or []
            if isinstance(bucket, dict)
        ],
        "notes": [],
    }


def _metric_summary(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": metric.get("status"),
        "value": metric.get("value"),
        "sample_count": int(metric.get("sample_count") or 0),
        "coverage_status": metric.get("coverage_status"),
        "reason": metric.get("reason"),
    }


def _overconfidence_signal(evaluation: dict[str, Any]) -> dict[str, Any] | None:
    for bucket in evaluation.get("calibration_buckets") or []:
        count = int(bucket.get("count") or 0)
        success = bucket.get("success_rate")
        expected = bucket.get("expected")
        if count <= 0 or success is None or expected is None or expected <= 0:
            continue
        ratio = float(success) / float(expected)
        if ratio < 0.50:
            return {
                "bucket": bucket["bucket"],
                "severity": "severe",
                "reason": (
                    f"confidence_bucket_{bucket['bucket']}_success_rate_"
                    f"{float(success):.4f}_below_expected_{float(expected):.4f}"
                ),
            }
        if ratio < 0.75:
            return {
                "bucket": bucket["bucket"],
                "severity": "moderate",
                "reason": (
                    f"confidence_bucket_{bucket['bucket']}_success_rate_"
                    f"{float(success):.4f}_below_expected_{float(expected):.4f}"
                ),
            }
    return None


def _evidence_gaps(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if not evaluation.get("has_valid_evaluation"):
        gaps.append({"scope": "evaluation", "reason": "missing_valid_walk_forward_samples"})
    metrics = evaluation.get("metrics") or {}
    for name in ("lead_time_hours", "event_window_robustness"):
        metric = metrics.get(name) or {}
        if metric.get("coverage_status") == "not_applicable" or int(metric.get("sample_count") or 0) == 0:
            gaps.append(
                {
                    "scope": name,
                    "reason": metric.get("reason") or "no_covered_samples",
                }
            )
    return gaps


def _raise_threshold(
    thresholds: dict[str, Any],
    scope: str,
    key: str,
    delta: float,
    adjustments: list[dict[str, Any]],
    *,
    reason: str,
) -> None:
    base = float(thresholds[scope][key])
    range_key = f"{scope}.{key}"
    low, high = THRESHOLD_RANGES[range_key]
    recommended = round(min(max(base + delta, low), high), 6)
    thresholds[scope][key] = recommended
    adjustments.append(
        {
            "scope": scope,
            "key": key,
            "base": base,
            "recommended": recommended,
            "delta": round(recommended - base, 6),
            "reason": reason,
        }
    )


def _bounded_thresholds(thresholds: dict[str, Any]) -> dict[str, Any]:
    bounded = deepcopy(thresholds)
    for scope, values in list(bounded.items()):
        if not isinstance(values, dict):
            continue
        for key, value in list(values.items()):
            range_key = f"{scope}.{key}"
            if range_key not in THRESHOLD_RANGES:
                continue
            low, high = THRESHOLD_RANGES[range_key]
            values[key] = round(min(max(float(value), low), high), 6)
    return bounded


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
