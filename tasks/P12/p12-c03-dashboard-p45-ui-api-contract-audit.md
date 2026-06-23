# P12-C03 / Dashboard / P45 UI-API Contract Audit

## 状态

DONE

## Summary

审计 Dashboard 与 P4.5 API 契约，确认前端展示的 BTC card、事件窗口、雷达、证据、审计报告、设置/数据质量状态与后端 API 返回一致，解决“后端有数据但前端未显示/显示旧数据”的系统性风险。

## Scope

- Frontend Dashboard main view。
- P45 dashboard API、audit reports API、settings APIs。
- UI buttons: Run Full Chain、Audit Reports、Evidence、Radar、Event Window、Settings。
- 输出 `reports/p12-dashboard-ui-api-contract-audit.md/json`。

Out of scope:

- 不做大规模视觉重设计。
- 不修改策略逻辑。

## Business Chain / Contract

- Frontend must display `final_run_id`、`pack_id`、`module_id`、`source_id`、data quality、runtime readiness。
- API errors must be surfaced with endpoint and status。
- Audit report links must use FastAPI `/reports/*` URLs when files exist。

## Implementation Plan

1. 枚举 Dashboard 使用的 API endpoint。
2. 对比 API payload 与 Vue state mapping。
3. 用 Playwright 或截图检查关键面板是否展示最新 run。
4. 标注 missing field、stale field、UI fallback 和 API 500 风险。

## DoD

- Dashboard 关键区域均有 API contract 映射表。
- API error display 与 data-empty display 分离。
- 输出前端缺口清单和修复任务建议。

## Test Plan

```powershell
npm run build
powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall
```

## Risks / Notes

- 需要避免用静态 mock 当作 live runtime 证据。

## Execution Record

- Completed at: 2026-06-23
- Report JSON: `reports/p12-dashboard-ui-api-contract-audit.json`
- Report MD: `reports/p12-dashboard-ui-api-contract-audit.md`
- Result: `PASS` after P12-C09 source action endpoint completion.
- Evidence: Dashboard latest, run lineage, Radar, Event Window, Settings and audit reports are mapped to live API endpoints.
- Finding: frontend source action endpoints are now implemented as safe capability/dry-run contracts.
- Follow-up: P12-C09 DONE.
- Verification:
  - `.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall`
