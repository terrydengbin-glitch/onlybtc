# P9-C13 API Mock / DoD Report

- schema_version: `p9.c13.api_mock_dod_report.v1`
- generated_at: `2026-06-23T07:39:57.818428+00:00`
- overall_status: `passed`
- mock_endpoint: `/api/mock/p9-c13/scenarios`
- openapi_snapshot: `E:\onlyBTC\reports\p9-c13-openapi-snapshot.json`
- frontend_dto_snapshot: `E:\onlyBTC\reports\p9-c13-frontend-dto-snapshot.json`

## Checks

| status | check | description |
|---|---|---|
| PASS | required_openapi_paths_present | All P5 page APIs are present in OpenAPI. |
| PASS | frontend_p45_endpoints_present | Frontend DTO layer references P45 page APIs. |
| PASS | mock_scenarios_present | Required API mock scenarios are available. |
| PASS | mock_scenarios_use_report_v2 | Mock fixtures use P4.5 Report v2. |
| PASS | mock_scenarios_redacted | Mock fixtures do not expose plaintext secrets. |
| PASS | error_contract_exposed | Frontend error DTO contract is present. |
| PASS | sse_contract_exposed | Realtime SSE endpoint is present. |
| PASS | api_security_mock_route_exposed | P9-C13 API mock endpoint is present. |
| PASS | path_resolver_report_paths | Reports are written under the project reports directory. |

## Mock Scenarios

- `normal_run`
- `contract_warning_run`
- `llm_completed_run`
- `llm_completed_with_llm_errors_run`
- `data_quality_degraded_run`
- `historical_replay_run`
- `legacy_p4_reference_run`
