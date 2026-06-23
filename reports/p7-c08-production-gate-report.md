# P7-C08 Production Gate Report

- schema_version: `p7.c08.production_gate.v1`
- generated_at: `2026-06-22T23:39:54.492872+00:00`
- applied_to_production: `False`
- production_apply_allowed: `False`
- manual_gate_release_allowed: `True`
- overall_status: `manual_review`
- alert_count: `3`
- accepted_warning_count: `5`
- blocking_warning_count: `0`

## Guardrails

- gate_only
- does_not_apply_recommendations
- does_not_modify_runtime_config
- does_not_modify_state_machine
- does_not_emit_trading_advice
- requires_all_dod_checks_before_real_long_running_production

## Child Reports

| task | capability | present | status | applied | source_alerts | missing_fields |
|---|---|---:|---|---:|---:|---|
| P7-C01 | module_weight_calibration | True | healthy | False | 0 | - |
| P7-C02 | state_alert_threshold_calibration | True | healthy | False | 0 | - |
| P7-C03 | prompt_version_registry | True | healthy | False | 0 | - |
| P7-C04 | source_health_monitor | True | watch | False | 4 | - |
| P7-C05 | playwright_stability | True | manual_review | False | 2 | - |
| P7-C06 | cost_cache_rate_limit_retry | True | manual_review | False | 2 | - |
| P7-C07 | provider_permission_source_onboarding | True | manual_review | False | 2 | - |

## Alerts

| level | scope | alert_id | reason | action |
|---|---|---|---|---|
| watch | P7-C05 | child_status_manual_acceptance_required | playwright_stability | review_manual_acceptance_before_release |
| watch | P7-C06 | child_status_manual_acceptance_required | cost_cache_rate_limit_retry | review_manual_acceptance_before_release |
| watch | P7-C07 | child_status_manual_acceptance_required | provider_permission_source_onboarding | review_manual_acceptance_before_release |

## Manual Acceptance

- release_policy: `manual_review_required`
- accepted_warning_count: `5`
- blocking_warning_count: `0`

| task | classification | alert_id | reason | release_condition |
|---|---|---|---|---|
| P7-C05 | provider_locked | provider_auth_not_verified | glassnode: status not found | Keep login-required provider metrics degraded until the human profile is verified. |
| P7-C05 | accepted_manual_gate | playwright_recent_health_warnings | fxstreet-economic-calendar | Recent Playwright warning is observable and source health remains non-critical. |
| P7-C06 | accepted_manual_gate | p45_research_budget_gap | P4.5 research writer has timeout/retry but no explicit call/token budget | Do not expand production LLM usage until explicit P4.5 call/token budgets are reviewed. |
| P7-C07 | provider_locked | provider_permission_missing | openai,glassnode | Keep affected provider metrics missing/provider_locked until credentials or login state are verified. |
| P7-C07 | provider_locked | manual_login_session_unverified | glassnode | Keep affected provider metrics missing/provider_locked until credentials or login state are verified. |

## Production Mock Scenarios

| scenario | task | status | mock_signal | expected_behavior |
|---|---|---|---|---|
| mock_module_weight_quality_discount | P7-C01 | healthy | low_quality_module_payload_or_profile_shift | recommend_weights_without_mutating_registry |
| mock_threshold_walk_forward_gap | P7-C02 | healthy | missing_or_weak_walk_forward_evaluation | keep_production_apply_false_and_surface_evidence_gap |
| mock_prompt_hash_registry | P7-C03 | healthy | registered_prompt_versions_and_output_schema_hashes | record_prompt_diff_surface_without_changing_runtime_prompt |
| mock_source_freshness_and_quality_failure | P7-C04 | watch | stale_missing_or_failed_source_health_events | degrade_data_quality_and_block_confirmed_signal_if_critical |
| mock_playwright_timeout_captcha_or_layout_change | P7-C05 | manual_review | manual_login_or_playwright_source_unverified | warn_or_degrade_without_blocking_global_collection |
| mock_budget_retry_rate_limit_pressure | P7-C06 | manual_review | fallback_events_budget_gap_or_rate_limit_pressure | surface_budget_and_retry_controls_as_configurable_guardrails |
| mock_provider_locked_or_unverified_login | P7-C07 | manual_review | missing_api_key_or_unverified_manual_login_provider | mark_metric_missing_provider_locked_without_secret_exposure |

## DoD Checks

| check | status |
|---|---|
| all_required_reports_present | pass |
| all_child_reports_audit_only | pass |
| no_critical_child_status | pass |
| production_mock_scenarios_complete | pass |
| prompt_registry_valid | pass |
| source_health_not_critical | pass |
| playwright_failure_path_observable | pass |
| cost_controls_config_visible | pass |
| provider_permission_sanitized | pass |
| rollout_and_rollback_checklists_ready | pass |

## Rollout Checklist

- regenerate_p7_c01_to_c07_reports
- confirm_all_reports_applied_to_production_false
- review_weight_and_threshold_recommendations_with_human_owner
- confirm_prompt_registry_hashes_and_output_schemas
- confirm_source_health_has_no_critical_freshness_gap
- confirm_playwright_login_state_or_degrade_policy
- confirm_cost_budget_cache_rate_limit_settings
- confirm_provider_permissions_and_provider_locked_mapping
- run_p7_c08_gate_and_attach_json_md_report

## Rollback Checklist

- restore_module_weights_from_registry_base
- restore_state_alert_and_direct_trend_base_thresholds
- restore_previous_prompt_version_registry_reference
- disable_new_or_unverified_sources
- clear_or_quarantine_playwright_auth_artifacts_if_secret_exposure_is_suspected
- lower_source_participation_to_context_only_on_data_quality_warning
- restore_cost_budget_and_retry_defaults
- mark_provider_locked_metrics_missing_until_verified

## Notes

- This report is a production gate only.
- It does not apply any calibration recommendation.
- `production_apply_allowed=false` means real long-running production should stay blocked until failed checks are repaired.
