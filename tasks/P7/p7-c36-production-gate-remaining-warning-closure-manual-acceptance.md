# P7-C36 Production Gate Remaining Warning Closure & Manual Acceptance

## 状态

DONE

## 所属 Phase

P7 动态校准与生产化增强

## 任务目标

收口 P7-C08 Production Gate 中剩余的 P7-C05 / P7-C06 / P7-C07 warning。将 warning 明确分类为 `must_fix`、`accepted_manual_gate` 或 `provider_locked`，避免生产门禁只暴露泛化 warning；同时保持自动生产 apply 关闭，只允许人工审阅后放行。

## 背景依据

- [P7-C05](p7-c05-playwright抓取稳定性增强.md)
- [P7-C06](p7-c06-成本控制缓存限流与重试.md)
- [P7-C07](p7-c07-权限审计与配置化新增数据源.md)
- [P7-C08](p7-c08-生产化校准mock与dod验收.md)
- [P7-C34](p7-c34-source-health-warning-severity-attribution-calibration.md)
- [P7-C35](p7-c35-radar-runtime-source-gate-async-collect-bridge.md)

## 实施范围

- 扩展 `backend/src/onlybtc/governance/p7_production_gate.py`。
- 对 P7-C05 / P7-C06 / P7-C07 的 child warning 增加 manual acceptance 分类。
- P7-C08 报告新增：
  - `manual_gate_release_allowed`
  - `manual_acceptance`
  - `blocking_warning_count`
  - `accepted_warning_count`
- 保留 `production_apply_allowed=false`，不自动应用任何配置、阈值、source 或 LLM runtime 变更。
- 不修改 source collection、Playwright 登录、provider secret、LLM 调用或前端 DTO。

## 输入

- `reports/p7-c05-playwright-stability-report.json`
- `reports/p7-c06-cost-control-cache-rate-limit-report.json`
- `reports/p7-c07-provider-permission-source-onboarding-report.json`
- P7-C08 production gate generator

## 输出

- P7-C08 剩余 warning 分类报告。
- 覆盖 manual acceptance 的单元测试。
- 刷新 `reports/p7-c08-production-gate-report.json/md`。

## 验收标准

- [x] P7-C05 provider auth / fresh-current Playwright warning 被分类为 `accepted_manual_gate` 或 `provider_locked`，不再作为泛化 blocking warning。
- [x] P7-C06 P4.5 research budget gap 被分类为 `accepted_manual_gate`，并要求人工 review before LLM expansion。
- [x] P7-C07 openai/glassnode 未配置被分类为 `provider_locked`，保持 affected metrics missing/provider_locked。
- [x] P7-C08 无 critical 且无 `must_fix` warning 时，`overall_status=manual_review`。
- [x] `production_apply_allowed=false`，`manual_gate_release_allowed=true`。
- [x] DoD checks 仍全部 pass，且 critical / applied-to-production 仍会 block。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_production_gate.py -q`
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c08_production_gate_report.py`

## 验证结果

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_production_gate.py -q` -> 5 passed.
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\governance\p7_production_gate.py scripts\generate_p7_c08_production_gate_report.py` -> passed.
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c08_production_gate_report.py` -> refreshed JSON/MD.
- `reports/p7-c08-production-gate-report.json` -> `overall_status=manual_review`, `production_apply_allowed=false`, `manual_gate_release_allowed=true`, `accepted_warning_count=5`, `blocking_warning_count=0`, failed DoD checks `[]`.
- Child statuses: `P7-C04=watch`, `P7-C05=manual_review`, `P7-C06=manual_review`, `P7-C07=manual_review`.

## 风险 / 回滚

- 风险：人工放行被误读为自动生产放开。处理方式：保留 `production_apply_allowed=false`，只新增 `manual_gate_release_allowed=true`。
- 回滚：恢复 P7-C08 对所有 child `overall_status=warning` 统一输出 gate warning。
