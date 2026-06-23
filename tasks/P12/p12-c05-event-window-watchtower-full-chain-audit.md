# P12-C05 / Event Window / Event Watchtower Full-chain Audit

## 状态

DONE

## Summary

审计 Event Window v3、Event Watchtower daemon、calendar/timeline/alerts/source diagnostics/shock lane 的全链路，确认事件日历、actual 发布轮询、market probe、shock fast lane 与 Dashboard 事件窗展示一致。

## Scope

- Event Window API。
- Event Watchtower daemon and scheduler。
- Calendar、timeline、alerts、source diagnostics、shock lane。
- Event-related SQLite tables and reports。
- 输出 `reports/p12-event-window-watchtower-audit.md/json/html`。

Out of scope:

- 不新增事件 provider。
- 不调整事件冲击阈值。

## Business Chain / Contract

- Required fields: `event_id`、`source_id`、`event_time`、`release_status`、`actual_status`、`importance`、`shock_state`、`market_probe_status`。
- UI must distinguish pending event, active watchtower, source unavailable, and post-event reaction。

## Implementation Plan

1. 枚举 Event Window / Watchtower endpoints。
2. 检查 daemon status、scheduler heartbeat 和 source diagnostics。
3. 对 timeline/calendar/alerts 数据做一致性抽检。
4. 对 shock lane recent events 做 evidence trace。

## DoD

- 事件模块 API/UI/SQLite/report lineage 有完整矩阵。
- API 500 或 source unavailable 必须有分类和修复建议。
- 输出后续修复任务卡建议。

## Test Plan

```powershell
Invoke-RestMethod http://127.0.0.1:8118/api/event-window/latest
Invoke-RestMethod http://127.0.0.1:8118/api/event-window/daemon/status
```

## Risks / Notes

- 事件 provider 有外部网络不稳定因素，审计需区分 provider failure 和 contract bug。

## Execution Record

- Completed at: 2026-06-23
- Report JSON: `reports/p12-event-window-watchtower-audit.json`
- Report MD: `reports/p12-event-window-watchtower-audit.md`
- Report HTML: `reports/p12-event-window-watchtower-audit.html`
- Result: `PASS`
- Evidence: Event Watchtower daemon is healthy; calendar/timeline/alerts/source fetch endpoints returned live rows without API 500.
- Verification:
  - `.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall`
