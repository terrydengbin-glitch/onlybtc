from __future__ import annotations

import json

from scripts.generate_p7_c08_production_gate_report import generate

from onlybtc.governance.p7_production_gate import (
    P7_REPORT_CONTRACTS,
    build_p7_production_gate_report,
)


def test_p7_gate_ready_when_all_child_reports_are_audit_only_and_healthy() -> None:
    report = build_p7_production_gate_report(child_reports=_child_reports())

    assert report["schema_version"] == "p7.c08.production_gate.v1"
    assert report["applied_to_production"] is False
    assert report["production_apply_allowed"] is True
    assert report["overall_status"] == "ready"
    assert len(report["production_mock_scenarios"]) == len(P7_REPORT_CONTRACTS)
    assert all(check["passed"] for check in report["dod_checks"])


def test_p7_gate_blocks_when_child_report_is_critical() -> None:
    child_reports = _child_reports()
    child_reports["P7-C04"]["overall_status"] = "critical"
    child_reports["P7-C04"]["alert_count"] = 1
    child_reports["P7-C04"]["alerts"] = [
        {
            "alert_id": "source_freshness_gap",
            "level": "critical",
            "scope": "freshness",
            "reason": "missing=1",
            "recommended_action": "repair_source_freshness",
        }
    ]

    report = build_p7_production_gate_report(child_reports=child_reports)
    failed = {check["check_id"] for check in report["dod_checks"] if not check["passed"]}

    assert report["production_apply_allowed"] is False
    assert report["overall_status"] == "blocked"
    assert "no_critical_child_status" in failed
    assert "source_health_not_critical" in failed


def test_p7_gate_blocks_when_child_report_was_applied_to_production() -> None:
    child_reports = _child_reports()
    child_reports["P7-C01"]["applied_to_production"] = True

    report = build_p7_production_gate_report(child_reports=child_reports)

    assert report["overall_status"] == "blocked"
    assert any(alert["alert_id"] == "child_report_production_applied" for alert in report["alerts"])


def test_p7_gate_classifies_remaining_warnings_as_manual_review() -> None:
    child_reports = _child_reports()
    child_reports["P7-C05"]["overall_status"] = "warning"
    child_reports["P7-C05"]["alert_count"] = 2
    child_reports["P7-C05"]["alerts"] = [
        {
            "alert_id": "provider_auth_not_verified",
            "level": "warning",
            "scope": "provider_auth",
            "reason": "glassnode: status not found",
            "recommended_action": "degrade_provider_to_health_warning_until_verified",
        },
        {
            "alert_id": "playwright_recent_health_warnings",
            "level": "warning",
            "scope": "source_health",
            "reason": "fxstreet-economic-calendar",
            "recommended_action": "inspect_artifacts_selectors_or_provider_auth",
        },
    ]
    child_reports["P7-C06"]["overall_status"] = "warning"
    child_reports["P7-C06"]["alert_count"] = 1
    child_reports["P7-C06"]["alerts"] = [
        {
            "alert_id": "p45_research_budget_gap",
            "level": "warning",
            "scope": "llm_budget",
            "reason": "P4.5 research writer has timeout/retry but no explicit call/token budget",
            "recommended_action": "add_p45_call_and_token_budget_before_production_llm_expansion",
        }
    ]
    child_reports["P7-C07"]["overall_status"] = "warning"
    child_reports["P7-C07"]["alert_count"] = 2
    child_reports["P7-C07"]["alerts"] = [
        {
            "alert_id": "provider_permission_missing",
            "level": "warning",
            "scope": "provider_permissions",
            "reason": "openai,glassnode",
            "recommended_action": "mark_affected_metrics_missing_provider_locked",
        },
        {
            "alert_id": "manual_login_session_unverified",
            "level": "warning",
            "scope": "provider_permissions",
            "reason": "glassnode",
            "recommended_action": "verify_session_before_using_login_required_sources",
        },
    ]

    report = build_p7_production_gate_report(child_reports=child_reports)
    by_task = {child["task_id"]: child for child in report["child_reports"]}

    assert report["overall_status"] == "manual_review"
    assert report["production_apply_allowed"] is False
    assert report["manual_gate_release_allowed"] is True
    assert report["blocking_warning_count"] == 0
    assert report["accepted_warning_count"] == 5
    assert by_task["P7-C05"]["status"] == "manual_review"
    assert by_task["P7-C06"]["status"] == "manual_review"
    assert by_task["P7-C07"]["status"] == "manual_review"
    assert all(check["passed"] for check in report["dod_checks"])
    assert {
        item["classification"] for item in report["manual_acceptance"]["items"]
    } == {"accepted_manual_gate", "provider_locked"}
    assert not any(alert["level"] == "warning" for alert in report["alerts"])


def test_p7_c08_report_generator_writes_json_and_md(tmp_path) -> None:
    json_path = tmp_path / "p7-c08-production-gate-report.json"
    md_path = tmp_path / "p7-c08-production-gate-report.md"

    report = generate(
        report_json=json_path,
        report_md=md_path,
        child_reports=_child_reports(),
        refresh_children=False,
    )
    written = json.loads(json_path.read_text(encoding="utf-8"))

    assert report["json_path"] == str(json_path)
    assert report["md_path"] == str(md_path)
    assert written["schema_version"] == "p7.c08.production_gate.v1"
    assert "manual_acceptance" in written
    assert md_path.exists()


def _child_reports() -> dict[str, dict]:
    return {
        "P7-C01": {
            "schema_version": "p7.c01.module_weight_calibration.v1",
            "applied_to_production": False,
            "recommended_weights": {"macro_radar": 1.0},
            "rollback": {"type": "restore_base_registry_weights"},
            "guardrails": ["recommendation_only"],
        },
        "P7-C02": {
            "schema_version": "p7.c02.state_alert_threshold_calibration.v1",
            "applied_to_production": False,
            "recommended_thresholds": {"direct_trend": {"acceptance": 70.0}},
            "rollback": {"type": "restore_base_thresholds"},
            "input_evaluation": {"has_valid_evaluation": True, "sample_count": 30},
        },
        "P7-C03": {
            "schema_version": "p7.c03.prompt_version_registry.v1",
            "applied_to_production": False,
            "entries": [{"prompt_id": "p45.llm_research_writer.article"}],
            "coverage": {"validation_passed": True},
            "guardrails": ["registry_only"],
        },
        "P7-C04": {
            "schema_version": "p7.c04.source_health_monitor.v1",
            "applied_to_production": False,
            "overall_status": "healthy",
            "alert_count": 0,
            "alerts": [],
            "downstream_policy": {"publish_gate_recommendation": "no_additional_gate_from_source_health"},
        },
        "P7-C05": {
            "schema_version": "p7.c05.playwright_stability.v1",
            "applied_to_production": False,
            "overall_status": "healthy",
            "alert_count": 0,
            "alerts": [],
            "artifact_policy": {"storage_state_reported_as_path_only": True},
            "provider_auth": [],
        },
        "P7-C06": {
            "schema_version": "p7.c06.cost_control_cache_rate_limit.v1",
            "applied_to_production": False,
            "overall_status": "healthy",
            "alert_count": 0,
            "alerts": [],
            "config": {"source_collection": {}},
            "cache": {"exists": True},
        },
        "P7-C07": {
            "schema_version": "p7.c07.provider_permission_source_onboarding.v1",
            "applied_to_production": False,
            "overall_status": "healthy",
            "alert_count": 0,
            "alerts": [],
            "provider_matrix": [],
            "source_onboarding": {"new_source_checklist": []},
            "provider_locked_policy": {"missing_reason": "provider_locked"},
        },
    }
