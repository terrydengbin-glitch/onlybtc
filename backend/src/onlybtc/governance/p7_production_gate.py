from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from onlybtc.core.paths import paths

SCHEMA_VERSION = "p7.c08.production_gate.v1"


@dataclass(frozen=True)
class P7ReportContract:
    task_id: str
    capability: str
    report_name: str
    expected_schema: str
    required_fields: tuple[str, ...]
    scenario_id: str
    mock_signal: str
    expected_behavior: str


P7_REPORT_CONTRACTS: tuple[P7ReportContract, ...] = (
    P7ReportContract(
        task_id="P7-C01",
        capability="module_weight_calibration",
        report_name="p7-c01-module-weight-calibration-report.json",
        expected_schema="p7.c01.module_weight_calibration.v1",
        required_fields=("recommended_weights", "rollback", "guardrails"),
        scenario_id="mock_module_weight_quality_discount",
        mock_signal="low_quality_module_payload_or_profile_shift",
        expected_behavior="recommend_weights_without_mutating_registry",
    ),
    P7ReportContract(
        task_id="P7-C02",
        capability="state_alert_threshold_calibration",
        report_name="p7-c02-state-alert-threshold-calibration-report.json",
        expected_schema="p7.c02.state_alert_threshold_calibration.v1",
        required_fields=("recommended_thresholds", "rollback", "input_evaluation"),
        scenario_id="mock_threshold_walk_forward_gap",
        mock_signal="missing_or_weak_walk_forward_evaluation",
        expected_behavior="keep_production_apply_false_and_surface_evidence_gap",
    ),
    P7ReportContract(
        task_id="P7-C03",
        capability="prompt_version_registry",
        report_name="p7-c03-prompt-version-management-report.json",
        expected_schema="p7.c03.prompt_version_registry.v1",
        required_fields=("entries", "coverage", "guardrails"),
        scenario_id="mock_prompt_hash_registry",
        mock_signal="registered_prompt_versions_and_output_schema_hashes",
        expected_behavior="record_prompt_diff_surface_without_changing_runtime_prompt",
    ),
    P7ReportContract(
        task_id="P7-C04",
        capability="source_health_monitor",
        report_name="p7-c04-source-health-monitor-report.json",
        expected_schema="p7.c04.source_health_monitor.v1",
        required_fields=("overall_status", "alerts", "downstream_policy"),
        scenario_id="mock_source_freshness_and_quality_failure",
        mock_signal="stale_missing_or_failed_source_health_events",
        expected_behavior="degrade_data_quality_and_block_confirmed_signal_if_critical",
    ),
    P7ReportContract(
        task_id="P7-C05",
        capability="playwright_stability",
        report_name="p7-c05-playwright-stability-report.json",
        expected_schema="p7.c05.playwright_stability.v1",
        required_fields=("overall_status", "alerts", "artifact_policy", "provider_auth"),
        scenario_id="mock_playwright_timeout_captcha_or_layout_change",
        mock_signal="manual_login_or_playwright_source_unverified",
        expected_behavior="warn_or_degrade_without_blocking_global_collection",
    ),
    P7ReportContract(
        task_id="P7-C06",
        capability="cost_cache_rate_limit_retry",
        report_name="p7-c06-cost-control-cache-rate-limit-report.json",
        expected_schema="p7.c06.cost_control_cache_rate_limit.v1",
        required_fields=("overall_status", "alerts", "config", "cache"),
        scenario_id="mock_budget_retry_rate_limit_pressure",
        mock_signal="fallback_events_budget_gap_or_rate_limit_pressure",
        expected_behavior="surface_budget_and_retry_controls_as_configurable_guardrails",
    ),
    P7ReportContract(
        task_id="P7-C07",
        capability="provider_permission_source_onboarding",
        report_name="p7-c07-provider-permission-source-onboarding-report.json",
        expected_schema="p7.c07.provider_permission_source_onboarding.v1",
        required_fields=("provider_matrix", "source_onboarding", "provider_locked_policy"),
        scenario_id="mock_provider_locked_or_unverified_login",
        mock_signal="missing_api_key_or_unverified_manual_login_provider",
        expected_behavior="mark_metric_missing_provider_locked_without_secret_exposure",
    ),
)


def build_p7_production_gate_report(
    *,
    report_dir: Path | None = None,
    child_reports: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report_dir = report_dir or paths.project_root / "reports"
    child_summaries = [
        _summarize_child(contract, _child_payload(contract, report_dir, child_reports))
        for contract in P7_REPORT_CONTRACTS
    ]
    scenarios = [_scenario_summary(summary) for summary in child_summaries]
    dod = _dod_checks(child_summaries, scenarios)
    alerts = _gate_alerts(child_summaries, dod)
    manual_acceptance = _manual_acceptance_summary(child_summaries)
    overall_status = _overall_status(alerts, manual_acceptance)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "applied_to_production": False,
        "production_apply_allowed": overall_status == "ready",
        "manual_gate_release_allowed": overall_status in {"ready", "manual_review"},
        "overall_status": overall_status,
        "alert_count": len(alerts),
        "alerts": alerts,
        "manual_acceptance": manual_acceptance,
        "accepted_warning_count": manual_acceptance["accepted_warning_count"],
        "blocking_warning_count": manual_acceptance["blocking_warning_count"],
        "child_reports": child_summaries,
        "production_mock_scenarios": scenarios,
        "dod_checks": dod,
        "rollout_checklist": _rollout_checklist(),
        "rollback_checklist": _rollback_checklist(child_summaries),
        "guardrails": [
            "gate_only",
            "does_not_apply_recommendations",
            "does_not_modify_runtime_config",
            "does_not_modify_state_machine",
            "does_not_emit_trading_advice",
            "requires_all_dod_checks_before_real_long_running_production",
        ],
    }


def _child_payload(
    contract: P7ReportContract,
    report_dir: Path,
    child_reports: dict[str, dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if child_reports is not None:
        return child_reports.get(contract.task_id)
    path = report_dir / contract.report_name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize_child(
    contract: P7ReportContract,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if payload is None:
        return {
            "task_id": contract.task_id,
            "capability": contract.capability,
            "report_name": contract.report_name,
            "present": False,
            "status": "critical",
            "applied_to_production": None,
            "schema_version": None,
            "missing_fields": list(contract.required_fields),
            "alerts": [
                {
                    "alert_id": "child_report_missing",
                    "level": "critical",
                    "scope": contract.task_id,
                    "reason": contract.report_name,
                    "recommended_action": "generate_child_report_before_p7_c08_gate",
                }
            ],
        }
    missing_fields = [field for field in contract.required_fields if field not in payload]
    alerts = _child_alerts(contract, payload, missing_fields)
    status = _child_status(contract, payload, alerts)
    manual_acceptance = _classify_child_manual_acceptance(contract, payload, status)
    if (
        status == "warning"
        and manual_acceptance["blocking_warning_count"] == 0
        and manual_acceptance["accepted_warning_count"] > 0
    ):
        status = "manual_review"
        alerts = [_downgrade_warning_to_manual_review(alert) for alert in alerts]
    return {
        "task_id": contract.task_id,
        "capability": contract.capability,
        "report_name": contract.report_name,
        "present": True,
        "status": status,
        "applied_to_production": payload.get("applied_to_production"),
        "schema_version": payload.get("schema_version"),
        "missing_fields": missing_fields,
        "alerts": alerts,
        "source_alert_count": int(payload.get("alert_count") or len(payload.get("alerts") or [])),
        "manual_acceptance": manual_acceptance,
    }


def _child_alerts(
    contract: P7ReportContract,
    payload: dict[str, Any],
    missing_fields: list[str],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if payload.get("schema_version") != contract.expected_schema:
        alerts.append(
            {
                "alert_id": "child_schema_mismatch",
                "level": "critical",
                "scope": contract.task_id,
                "reason": f"expected={contract.expected_schema}; actual={payload.get('schema_version')}",
                "recommended_action": "regenerate_or_migrate_child_report_schema",
            }
        )
    if payload.get("applied_to_production") is not False:
        alerts.append(
            {
                "alert_id": "child_report_production_applied",
                "level": "critical",
                "scope": contract.task_id,
                "reason": f"applied_to_production={payload.get('applied_to_production')}",
                "recommended_action": "rollback_or_mark_report_as_audit_only_before_gate",
            }
        )
    if missing_fields:
        alerts.append(
            {
                "alert_id": "child_required_fields_missing",
                "level": "critical",
                "scope": contract.task_id,
                "reason": ",".join(missing_fields),
                "recommended_action": "restore_required_report_contract_fields",
            }
        )
    source_status = str(payload.get("overall_status") or "")
    if source_status == "critical":
        alerts.append(
            {
                "alert_id": "child_status_critical",
                "level": "critical",
                "scope": contract.task_id,
                "reason": contract.capability,
                "recommended_action": "repair_child_report_blockers_before_production_apply",
            }
        )
    elif source_status == "warning":
        alerts.append(
            {
                "alert_id": "child_status_warning",
                "level": "warning",
                "scope": contract.task_id,
                "reason": contract.capability,
                "recommended_action": "resolve_or_accept_warning_with_manual_gate_note",
            }
        )
    if contract.task_id == "P7-C02":
        evaluation = payload.get("input_evaluation") or {}
        if not evaluation.get("has_valid_evaluation"):
            alerts.append(
                {
                    "alert_id": "threshold_evaluation_gap",
                    "level": "warning",
                    "scope": contract.task_id,
                    "reason": "missing_valid_walk_forward_samples",
                    "recommended_action": "run_p7_c31_or_equivalent_walk_forward_before_threshold_apply",
                }
            )
    if contract.task_id == "P7-C03":
        coverage = payload.get("coverage") or {}
        if coverage.get("validation_passed") is not True:
            alerts.append(
                {
                    "alert_id": "prompt_registry_validation_failed",
                    "level": "critical",
                    "scope": contract.task_id,
                    "reason": "coverage.validation_passed_false",
                    "recommended_action": "repair_prompt_registry_before_p7_gate",
                }
            )
    return alerts


def _child_status(
    contract: P7ReportContract,
    payload: dict[str, Any],
    alerts: list[dict[str, Any]],
) -> str:
    levels = {alert["level"] for alert in alerts}
    if "critical" in levels:
        return "critical"
    if "warning" in levels:
        return "warning"
    if payload.get("overall_status"):
        return str(payload["overall_status"])
    if contract.task_id == "P7-C03":
        return "healthy" if (payload.get("coverage") or {}).get("validation_passed") else "critical"
    return "healthy"


def _scenario_summary(child: dict[str, Any]) -> dict[str, Any]:
    contract = next(item for item in P7_REPORT_CONTRACTS if item.task_id == child["task_id"])
    return {
        "scenario_id": contract.scenario_id,
        "task_id": contract.task_id,
        "capability": contract.capability,
        "mock_signal": contract.mock_signal,
        "expected_behavior": contract.expected_behavior,
        "status": child["status"],
        "gate_behavior": _scenario_gate_behavior(child),
    }


def _scenario_gate_behavior(child: dict[str, Any]) -> str:
    if child["status"] == "critical":
        return "block_production_apply"
    if child["status"] == "manual_review":
        return "manual_acceptance_required"
    return "record_and_continue_audit"


def _dod_checks(
    child_summaries: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_task = {child["task_id"]: child for child in child_summaries}
    return [
        _check("all_required_reports_present", all(child["present"] for child in child_summaries)),
        _check(
            "all_child_reports_audit_only",
            all(child.get("applied_to_production") is False for child in child_summaries),
        ),
        _check(
            "no_critical_child_status",
            all(child["status"] != "critical" for child in child_summaries),
        ),
        _check("production_mock_scenarios_complete", len(scenarios) == len(P7_REPORT_CONTRACTS)),
        _check(
            "prompt_registry_valid",
            by_task.get("P7-C03", {}).get("status") not in {"critical"},
        ),
        _check(
            "source_health_not_critical",
            by_task.get("P7-C04", {}).get("status") != "critical",
        ),
        _check(
            "playwright_failure_path_observable",
            by_task.get("P7-C05", {}).get("present") is True,
        ),
        _check(
            "cost_controls_config_visible",
            by_task.get("P7-C06", {}).get("present") is True,
        ),
        _check(
            "provider_permission_sanitized",
            by_task.get("P7-C07", {}).get("present") is True
            and by_task.get("P7-C07", {}).get("status") != "critical",
        ),
        _check("rollout_and_rollback_checklists_ready", True),
    ]


def _check(check_id: str, passed: bool) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": bool(passed),
        "status": "pass" if passed else "fail",
    }


def _gate_alerts(
    child_summaries: list[dict[str, Any]],
    dod_checks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for child in child_summaries:
        for alert in child["alerts"]:
            alerts.append({**alert, "child_task_id": child["task_id"]})
    failed_checks = [check["check_id"] for check in dod_checks if not check["passed"]]
    if failed_checks:
        level = "critical" if "no_critical_child_status" in failed_checks else "warning"
        alerts.append(
            {
                "alert_id": "p7_dod_checks_failed",
                "level": level,
                "scope": "p7_production_gate",
                "reason": ",".join(failed_checks),
                "recommended_action": "complete_failed_dod_checks_before_real_long_running_production",
            }
        )
    return alerts


def _overall_status(
    alerts: list[dict[str, Any]],
    manual_acceptance: dict[str, Any] | None = None,
) -> str:
    levels = {alert["level"] for alert in alerts}
    if "critical" in levels:
        return "blocked"
    if "warning" in levels:
        return "warning"
    if manual_acceptance and manual_acceptance.get("accepted_warning_count", 0) > 0:
        return "manual_review"
    if "watch" in levels:
        return "watch"
    return "ready"


def _classify_child_manual_acceptance(
    contract: P7ReportContract,
    payload: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    items = [
        _manual_acceptance_item(contract, alert)
        for alert in payload.get("alerts") or []
        if str(alert.get("level") or "") == "warning"
    ]
    blocking = [item for item in items if item["classification"] == "must_fix"]
    accepted = [item for item in items if item["classification"] != "must_fix"]
    return {
        "task_id": contract.task_id,
        "capability": contract.capability,
        "status_before_acceptance": status,
        "release_policy": (
            "block_until_repaired"
            if blocking
            else "manual_review_required"
            if accepted
            else "no_manual_acceptance_needed"
        ),
        "accepted_warning_count": len(accepted),
        "blocking_warning_count": len(blocking),
        "items": items,
    }


def _manual_acceptance_item(
    contract: P7ReportContract,
    alert: dict[str, Any],
) -> dict[str, Any]:
    classification, release_condition = _manual_warning_classification(contract, alert)
    return {
        "task_id": contract.task_id,
        "capability": contract.capability,
        "alert_id": alert.get("alert_id"),
        "source_level": alert.get("level"),
        "scope": alert.get("scope"),
        "reason": alert.get("reason"),
        "recommended_action": alert.get("recommended_action"),
        "classification": classification,
        "release_condition": release_condition,
    }


def _manual_warning_classification(
    contract: P7ReportContract,
    alert: dict[str, Any],
) -> tuple[str, str]:
    alert_id = str(alert.get("alert_id") or "")
    if contract.task_id == "P7-C05":
        if alert_id == "provider_auth_not_verified":
            return (
                "provider_locked",
                "Keep login-required provider metrics degraded until the human profile is verified.",
            )
        if alert_id == "playwright_recent_health_warnings":
            return (
                "accepted_manual_gate",
                "Recent Playwright warning is observable and source health remains non-critical.",
            )
    if contract.task_id == "P7-C06":
        if alert_id == "p45_research_budget_gap":
            return (
                "accepted_manual_gate",
                "Do not expand production LLM usage until explicit P4.5 call/token budgets are reviewed.",
            )
        if alert_id == "fallback_events_present":
            return (
                "accepted_manual_gate",
                "Fallback events are visible with quality discount and reviewed before cost-sensitive rollout.",
            )
    if contract.task_id == "P7-C07":
        if alert_id in {"provider_permission_missing", "manual_login_session_unverified"}:
            return (
                "provider_locked",
                "Keep affected provider metrics missing/provider_locked until credentials or login state are verified.",
            )
    return ("must_fix", "Repair this warning before manual production release.")


def _downgrade_warning_to_manual_review(alert: dict[str, Any]) -> dict[str, Any]:
    if alert.get("alert_id") != "child_status_warning":
        return alert
    return {
        **alert,
        "alert_id": "child_status_manual_acceptance_required",
        "level": "watch",
        "recommended_action": "review_manual_acceptance_before_release",
    }


def _manual_acceptance_summary(child_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    children = [child.get("manual_acceptance") or {} for child in child_summaries]
    items = [item for child in children for item in child.get("items") or []]
    blocking = [item for item in items if item["classification"] == "must_fix"]
    accepted = [item for item in items if item["classification"] != "must_fix"]
    return {
        "schema_version": "p7.c36.manual_acceptance.v1",
        "release_policy": (
            "block_until_must_fix_warnings_resolved"
            if blocking
            else "manual_review_required"
            if accepted
            else "no_manual_acceptance_needed"
        ),
        "accepted_warning_count": len(accepted),
        "blocking_warning_count": len(blocking),
        "items": items,
        "guardrails": [
            "manual_acceptance_does_not_apply_production_changes",
            "provider_locked_metrics_remain_missing_until_verified",
            "llm_budget_expansion_requires_human_review",
            "critical_child_status_still_blocks_release",
        ],
    }


def _rollout_checklist() -> list[str]:
    return [
        "regenerate_p7_c01_to_c07_reports",
        "confirm_all_reports_applied_to_production_false",
        "review_weight_and_threshold_recommendations_with_human_owner",
        "confirm_prompt_registry_hashes_and_output_schemas",
        "confirm_source_health_has_no_critical_freshness_gap",
        "confirm_playwright_login_state_or_degrade_policy",
        "confirm_cost_budget_cache_rate_limit_settings",
        "confirm_provider_permissions_and_provider_locked_mapping",
        "run_p7_c08_gate_and_attach_json_md_report",
    ]


def _rollback_checklist(child_summaries: list[dict[str, Any]]) -> list[str]:
    checklist = [
        "restore_module_weights_from_registry_base",
        "restore_state_alert_and_direct_trend_base_thresholds",
        "restore_previous_prompt_version_registry_reference",
        "disable_new_or_unverified_sources",
        "clear_or_quarantine_playwright_auth_artifacts_if_secret_exposure_is_suspected",
        "lower_source_participation_to_context_only_on_data_quality_warning",
        "restore_cost_budget_and_retry_defaults",
        "mark_provider_locked_metrics_missing_until_verified",
    ]
    if any(child["status"] == "critical" for child in child_summaries):
        checklist.append("block_real_long_running_production_until_critical_children_are_repaired")
    return checklist
