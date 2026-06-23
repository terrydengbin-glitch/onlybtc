# P12-C08 / Frozen Final Lineage vs Live Runtime Freshness UI Label Hardening

## 状态

DONE

## Summary

P12-C02 发现 P4.5 final lineage 与 live radar runtime snapshot 可能来自不同运行时刻。该任务将 Dashboard 中 frozen final run 与 live runtime freshness 的标签、提示和 drilldown 契约分离，避免用户把实时雷达健康状态误读为 final card 的原始证据时间。

## Scope

- Dashboard BTC card / lineage side panel。
- Radar runtime freshness chips。
- P4.5 final frozen snapshot label。
- 历史回放与 latest view 的文案区别。

Out of scope:

- 不改 P4.5 策略输出。
- 不改 radar runtime freshness 计算。

## Business Chain / Contract

- `final_run_id`、`pack_id`、`collect_run_id` 属于 frozen final lineage。
- `radar-runtime-* snapshot_id`、`runtime_fresh`、`source_fresh` 属于 live runtime health。
- UI 必须同时展示二者，但不能混成一个 freshness 结论。

## Implementation Plan

1. 梳理 Dashboard 中 final lineage 与 runtime freshness 的 computed/mapping。
2. 增加 frozen/live 分区标签或 tooltip。
3. 更新 API error/fallback display，确保 historical replay 不污染 latest runtime。
4. 增加前端 build 与必要契约检查。

## DoD

- 用户能清楚看到 final card 的 frozen run 时间与 live runtime freshness 是两条证据链。
- P12-C02 warning 可关闭或降为 info。
- `npm run build` 通过。

## Test Plan

```powershell
npm run build
.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py
```

## Risks / Notes

- 只做观测和标签硬化，不改变策略语义。

## Execution Record

- Completed at: 2026-06-23
- Frontend: `frontend/src/App.vue`
- Audit runner: `scripts/run_p12_system_audit.py`
- Result: P12-C02 upgraded from `PARTIAL PASS` to `PASS` with `freshness_ui_separated=true`.
- UI contract: topbar, Run Lineage board, and right-side drawer now separate `frozen final lineage` from `Live Runtime Freshness` / `live radar heartbeat`.
- Verification:
  - `npm run build`
  - `.\.venv\Scripts\python.exe -m py_compile scripts\run_p12_system_audit.py`
  - `.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py`
