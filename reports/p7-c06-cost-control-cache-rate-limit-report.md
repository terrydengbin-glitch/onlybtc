# P7-C06 Cost Control / Cache / Rate Limit Report

- schema_version: `p7.c06.cost_control_cache_rate_limit.v1`
- generated_at: `2026-06-22T23:39:54.457122+00:00`
- applied_to_production: `False`
- overall_status: `warning`
- alert_count: `2`

## Guardrails

- audit_only
- does_not_modify_runtime_settings
- does_not_call_external_providers
- does_not_cache_secrets
- does_not_modify_state_machine
- does_not_emit_trading_advice
- requires_p7_c08_before_production_apply

## Alerts

| level | scope | alert_id | reason | action |
|---|---|---|---|---|
| warning | llm_budget | p45_research_budget_gap | P4.5 research writer has timeout/retry but no explicit call/token budget | add_p45_call_and_token_budget_before_production_llm_expansion |
| watch | fallback | fallback_events_present | fallback_event_count=105 | audit_fallback_cost_and_quality_discount |

## Config Summary

- source_collection: `{"timeout_seconds": 15.0, "http_concurrency": 6, "playwright_concurrency": 1, "official_concurrency": 3, "fred_concurrency": 3, "source_max_retries": 1, "source_retry_backoff_seconds": 0.75, "source_failure_gate_threshold": 12, "source_min_current_metrics": 80}`
- fred_throttle: `{"batch_size": 5, "inter_batch_delay_ms": 500, "per_request_jitter_ms": 120, "api_max_attempts": 3, "api_backoff_seconds": 0.8}`
- p4_llm_budget: `{"timeout_seconds": 90.0, "max_retries": 1, "max_calls_per_run": 32, "max_estimated_tokens_per_run": 200000, "fallback_policy": "fallback", "has_explicit_call_budget": true, "has_explicit_token_budget": true}`
- p45_research_budget: `{"provider": "deepseek", "timeout_seconds": 180.0, "max_retries": 1, "has_explicit_call_budget": false, "has_explicit_token_budget": false}`

## Cache

- path: `E:\onlyBTC\cache`
- exists: `True`
- file_count: `398`
- total_bytes: `66709060`

## Rate Limit Events

- none

## Fallback Summary

- fallback_event_count: `105`

## Notes

- This report is audit-only and does not modify runtime settings.
- P4 has explicit call and token budget guards.
- P4.5 research timeout/retry exists, but explicit call/token budget is reported as a governance gap until configured.
