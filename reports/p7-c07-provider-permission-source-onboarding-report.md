# P7-C07 Provider Permission / Source Onboarding Report

- schema_version: `p7.c07.provider_permission_source_onboarding.v1`
- generated_at: `2026-06-23T09:21:37.162932+00:00`
- applied_to_production: `False`
- overall_status: `warning`
- alert_count: `2`
- source_count: `78`
- login_required_count: `3`
- sensitive_scan_passed: `True`

## Guardrails

- audit_only
- does_not_read_secret_values
- does_not_write_provider_tokens
- does_not_modify_source_registry
- does_not_modify_state_machine
- does_not_emit_trading_advice
- requires_p7_c08_before_production_apply

## Alerts

| level | scope | alert_id | reason | action |
|---|---|---|---|---|
| warning | provider_permissions | provider_permission_missing | openai,glassnode | mark_affected_metrics_missing_provider_locked |
| warning | provider_permissions | manual_login_session_unverified | glassnode | verify_session_before_using_login_required_sources |

## Provider Matrix

| provider | auth_method | configured | verified | permission | allowed | exposed |
|---|---|---:|---:|---|---|---:|
| deepseek | api_key | True | True | llm_runtime | p4_p45_llm_runtime | False |
| fred | api_key | True | True | public_data_api | fred_source_metrics | False |
| kimi | api_key | True | True | llm_runtime | p4_agent_runtime | False |
| openai | api_key | False | False | llm_runtime | p4_agent_runtime | False |
| qwen | api_key | True | True | llm_runtime | p4_agent_runtime | False |
| volcano | api_key | True | True | llm_runtime | p4_agent_runtime | False |
| glassnode | manual_login_playwright | False | False | session_cookie_page_access | 8 metrics | False |
| oauth_session_placeholder | oauth/session | False | False | not_configured | 0 metrics | False |

## Onboarding Checklist

- declare_source_id_name_kind_group_method_metrics
- declare_auth_method_and_provider_id_if_needed
- declare_requires_login
- declare_requires_paid_plan
- declare_playwright_fallback_allowed
- declare_freshness_policy
- declare_quality_score_or_quality_policy
- register_source_health_visibility
- register_p5_settings_visibility
- ensure_provider_locked_maps_to_missing_not_default_value

## Filesystem Safety

- env_file_ignored: `True`
- env_wildcard_ignored: `True`
- playwright_artifacts_ignored: `True`

## Provider Locked Policy

- metric_status: `missing`
- missing_reason: `provider_locked`
- forbidden_behavior: `do_not_fabricate_default_metric_values`

## Notes

- This report is audit-only and does not read secret values.
- Provider permission status is safe for Source Detail / Data Quality display.
- Login/session providers must be stricter than public API providers.
