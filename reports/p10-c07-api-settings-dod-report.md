# P10-C07 API Settings DoD Report

- status: passed
- generated_at: 2026-06-23T06:31:08.699202+00:00
- schema_version: p10.c07.api_settings_dod_report.v1

## Checks
- PASS mock_fred_key_masked
- PASS mock_llm_key_in_registry
- PASS mock_llm_key_in_routing
- PASS provider_success_failure_covered
- PASS provider_probe_redacted
- PASS audit_event_recorded
- PASS unknown_env_preserved
- PASS frontend_settings_mock_wired

## Runtime Checks
- settings_schema: p45.settings.v1
- audit_schema: p10.c06.settings_key_audit.v1
- llm_routing_schema: p10.c05.llm_routing.v1
- provider_health_schema: p10.c04.provider_health.v1
- frontend_reachable: True

## Guardrails
- mock_env_only
- no_plaintext_secret_values
- provider_success_and_failure_paths_covered
- frontend_settings_controls_wired
- p10_blocks_real_paid_provider_usage_until_dod_passes
