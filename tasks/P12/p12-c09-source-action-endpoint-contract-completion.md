# P12-C09 / Source Action Endpoint Contract Completion

## 状态

DONE

## Summary

P12-C03/P12-C06 发现前端引用 `/api/sources/{source_id}/auth-state`、`last-capture`、`open-verify-window`、`retry-collect`，但后端当前未提供这些 endpoint。该任务补齐后端契约或按 capability metadata 禁用相关 UI 动作。

## Scope

- Backend `/api/sources/*` endpoint contract。
- Frontend source detail/action controls。
- Settings/data source governance UI。
- API error display 与 disabled reason。

Out of scope:

- 不接入新的真实 provider。
- 不写入真实 API key。

## Business Chain / Contract

- Required fields: `source_id`、`capability`、`enabled`、`auth_state`、`last_capture`、`retry_allowed`、`disabled_reason`。
- 对 paid/locked/missing-key/source-unavailable 必须返回可展示的分类状态。
- Secret values 不得出现在 API payload、日志、报告或 UI。

## Implementation Plan

1. 决定四个 source action endpoint 是后端实现还是 UI capability-gated。
2. 若实现 endpoint，返回统一 `onlybtc.api.v1` response shape。
3. 若暂不实现，前端根据 capability metadata 隐藏或禁用按钮。
4. 增加 API/前端契约测试。

## DoD

- P12-C03/P12-C06 中 source action gap 清零。
- 用户点击 source 详情不再触发 404/500/未实现动作。
- Secret hygiene 仍为 pass。

## Test Plan

```powershell
.\.venv\Scripts\pytest.exe backend\tests\test_api_contracts.py backend\tests\test_settings_contract.py
npm run build
.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py
```

## Risks / Notes

- retry collect 可能触发外部 provider 请求，默认应先实现 dry-run/capability status，再开放真实重试。

## Execution Record

- Completed at: 2026-06-23
- Backend: `backend/src/onlybtc/api/app.py`
- Tests: `backend/tests/test_api_contracts.py`
- Result: P12-C03 and P12-C06 upgraded to `PASS`; source action gaps are empty.
- Implemented endpoints:
  - `GET /api/sources/{source_id}/auth-state`
  - `GET /api/sources/{source_id}/last-capture`
  - `POST /api/sources/{source_id}/open-verify-window`
  - `POST /api/sources/{source_id}/retry-collect`
- Contract behavior: endpoints expose capability/auth/last_capture state; mutation-style actions return `dry_run` or `disabled` and `external_side_effect=false`.
- Secret hygiene: pass; last capture payload remains redacted.
- Verification:
  - `.\.venv\Scripts\pytest.exe backend\tests\test_api_contracts.py backend\tests\test_settings_contract.py`
  - `.\.venv\Scripts\ruff.exe check backend\src\onlybtc\api\app.py backend\tests\test_api_contracts.py`
  - `npm run build`
  - `.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall`
