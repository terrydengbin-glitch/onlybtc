# P12-C01 / System Full-chain Audit Master Plan 与 Evidence Inventory

## 状态

TODO

## Summary

建立 P12 系统级全链路审计总控，盘点业务链条、Dashboard、Radar、事件模块、数据源、SQLite、API、报告、CI 与运行态证据，形成统一审计范围、证据目录、执行顺序和最终验收口径。

## Scope

- P12 审计任务总控。
- 当前 repo、task index、reports、runtime endpoints、SQLite/current JSON 证据目录。
- 输出 `reports/p12-system-full-chain-audit-inventory.md/json`。

Out of scope:

- 不修改策略语义。
- 不修复具体模块 bug；发现问题时拆后续卡。

## Business Chain / Contract

- Chain: source collect -> source health/freshness -> radar modules -> P3/P4.5 decision -> evidence/report -> API -> Dashboard UI。
- Required ids: `run_id`、`final_run_id`、`pack_id`、`module_id`、`source_id`、`evidence_id`。
- Evidence must distinguish live runtime, replay snapshot, static acceptance report, and latest mutable artifact。

## Implementation Plan

1. 扫描 task index 与 P7/P9/P10/P11 关键验收卡。
2. 列出现有 reports、API endpoints、runtime current artifacts 与 SQLite tables。
3. 建立 P12 evidence inventory。
4. 定义 P12-C02 至 P12-C07 执行顺序和交付件。

## DoD

- P12 审计范围完整覆盖业务链、Dashboard、Radar、事件、数据源、SQLite/API/report lineage。
- 输出 inventory markdown/json。
- 明确每张子卡输入、输出、验收口径。

## Test Plan

```powershell
git status -sb
rg -n "P7-C|P9-C|P10-C|P11-C" "task index.md"
rg --files reports backend/src frontend/src scripts
```

## Risks / Notes

- 审计证据必须标注生成时间和 run scope，避免 stale latest 文件冒充当前证据。
