# P12-C06 / Data Source / Settings / Provider Governance Audit

## 状态

DONE

## Summary

审计数据源、Settings、Provider entitlement、fallback、freshness policy 与密钥治理，确认所有 source 的启用状态、授权状态、fallback、source_ts/collected_at、business recency 和 UI/报告可见性一致。

## Scope

- `/api/settings/runtime`
- `/api/settings/data-sources`
- `/api/settings/paths`
- Glassnode entitlement audit。
- Provider health and source freshness policies。
- 输出 `reports/p12-data-source-settings-provider-governance-audit.md/json`。

Out of scope:

- 不写入真实 API key。
- 不改变 provider entitlement 判断规则。

## Business Chain / Contract

- Required fields: `source_id`、`enabled`、`provider`、`fallback_source_id`、`freshness_policy`、`entitlement_status`、`source_ts`、`collected_at`、`business_recency_status`。
- Secrets must never appear in API payload, logs, reports, or UI。

## Implementation Plan

1. 读取 settings/data-sources/path contracts。
2. 对 provider health、Glassnode entitlement、fallback config 做矩阵。
3. 抽查 source freshness policy 是否匹配 provider 发布节奏。
4. 输出 source governance gap list。

## DoD

- 所有 source 有 governance 状态。
- paid/locked/missing-key/source-unavailable 状态可见且不泄密。
- fallback 与 freshness policy 有审计结论。

## Test Plan

```powershell
Invoke-RestMethod http://127.0.0.1:8118/api/settings/data-sources
Invoke-RestMethod http://127.0.0.1:8118/api/settings/providers/glassnode/entitlement/latest
```

## Risks / Notes

- Provider live 检查需避免高频请求和密钥泄漏。

## Execution Record

- Completed at: 2026-06-23
- Report JSON: `reports/p12-data-source-settings-provider-governance-audit.json`
- Report MD: `reports/p12-data-source-settings-provider-governance-audit.md`
- Result: `PASS` after P12-C09 source action endpoint completion.
- Evidence: `source_count=78`、`enabled_count=72`、`fallback_configured_count=9`、`freshness_policy_count=23`；secret hygiene pass。
- Finding: source governance UI source action endpoints are now implemented; secret hygiene remains pass.
- Follow-up: P12-C09 DONE.
- Verification:
  - `.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall`
