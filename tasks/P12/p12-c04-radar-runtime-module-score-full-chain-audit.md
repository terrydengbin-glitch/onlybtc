# P12-C04 / Radar Runtime / Module Score Full-chain Audit

## 状态

DONE

## Summary

审计 14 个 Radar modules、runtime scheduler、module score、freshness gate、BTC trend cockpit 与 direct trend judge 的全链路一致性，确认模块分数来源、方向、接受度、source freshness 与 Dashboard 展示一致。

## Scope

- Radar runtime daemon。
- 14 radar modules。
- Source refresh gate。
- BTC trend cockpit / timescale judge。
- Runtime SQLite snapshots and latest API。
- 输出 `reports/p12-radar-runtime-module-score-audit.md/json/html`。

Out of scope:

- 不调整 module weights。
- 不改变 trend judge 阈值。

## Business Chain / Contract

- Required fields: `module_id`、`module_name`、`module_score`、`effective_score`、`module_direction`、`signal_stage`、`score_source`、`freshness_state`、`source_freshness`。
- Must separate runtime freshness from source freshness。
- Must verify all 14 modules either fresh/expected_lag or explicitly degraded。

## Implementation Plan

1. 读取 runtime latest snapshot 和 module snapshots。
2. 对每个 module 校验 score source、freshness policy、accepted status。
3. 对 BTC cockpit 聚合分数和 module contribution 做反算抽检。
4. 输出 module-by-module audit table。

## DoD

- 14 modules 全部有审计结论。
- 任何 score/freshness/source mismatch 都有 evidence。
- Runtime latest report policy 与 archive evidence 区分清楚。

## Test Plan

```powershell
Invoke-RestMethod http://127.0.0.1:8118/api/radar-runtime/latest
Invoke-RestMethod http://127.0.0.1:8118/api/radar-runtime/daemon/status
```

## Risks / Notes

- Latest mutable report 不再纳入 git；审计要生成带 P12 名称的静态报告。

## Execution Record

- Completed at: 2026-06-23
- Report JSON: `reports/p12-radar-runtime-module-score-audit.json`
- Report MD: `reports/p12-radar-runtime-module-score-audit.md`
- Report HTML: `reports/p12-radar-runtime-module-score-audit.html`
- Result: `PASS`
- Evidence: Radar daemon is healthy, runtime/source freshness are true, SQLite lock state is ok, and 14 modules are present.
- Verification:
  - `.\.venv\Scripts\python.exe scripts\run_p12_system_audit.py`
  - `powershell -ExecutionPolicy Bypass -File .\scripts\fresh_clone_smoke.ps1 -SkipInstall`
