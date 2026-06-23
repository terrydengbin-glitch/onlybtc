# P12-C02 / Business Chain Contract Audit

## 状态

DONE

## Summary

审计 onlyBTC 从数据采集到最终 BTC 决策卡的业务链条是否闭环，重点确认 source freshness、radar score、P3/P4.5 接受度、evidence pack、LLM appendix、Dashboard 展示之间的字段契约和语义一致性。

## Scope

- P1 source collection / source health。
- P2/P3 radar feature and scoring。
- P4.5 final writer / evidence pack / LLM analyst lineage。
- Dashboard latest run / decision card / lineage side panel。
- 输出 `reports/p12-business-chain-contract-audit.md/json`。

Out of scope:

- 不重调策略参数。
- 不改变评分权重。

## Business Chain / Contract

- Required fields: `run_id`、`final_run_id`、`pack_id`、`module_id`、`source_id`、`evidence_id`、`asof_ts`、`source_ts`、`collected_at`、`freshness_status`、`accepted_status`。
- Must verify no stale evidence is shown as current run evidence。
- Must verify final decision card can trace back to module and source evidence。

## Implementation Plan

1. 从最新 full chain / runtime state 抽取 run lineage。
2. 追踪 BTC card -> P4.5 final -> evidence pack -> radar module -> source freshness。
3. 检查字段缺失、scope 混用、stale fallback 未标注等问题。
4. 输出问题分级：blocking / warning / info。

## DoD

- 给出完整业务链路矩阵。
- 每个关键 UI 字段都有上游 evidence 或明确 pending/stale 标记。
- 发现的问题拆成后续修复卡。

## Test Plan

```powershell
Invoke-RestMethod http://127.0.0.1:8118/api/p45/dashboard
Invoke-RestMethod http://127.0.0.1:8118/api/p45/audit-reports/latest
```

## Risks / Notes

- 如果当前 daemon 未运行，先用已有 SQLite/reports 做离线审计，并标注 runtime unavailable。

## Execution Record

- Completed at: 2026-06-23
- Report JSON: `reports/p12-business-chain-contract-audit.json`
- Report MD: `reports/p12-business-chain-contract-audit.md`
- Result: `PASS` after P12-C08 UI label hardening.
- Evidence: latest P4.5 lineage is traceable through `collect_run_id`、`p2_radar_run_id`、`p3_run_id`、`pack_id`、`final_run_id`。
- Finding: frozen P4.5 final lineage and live radar runtime snapshot can represent different runtime moments; UI now separates both chains.
- Follow-up: P12-C08 DONE.
- Verification:
  - `.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall`
