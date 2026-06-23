# P7-C08 生产化校准 Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P7 动态校准与生产化增强

## 任务目标

用 mock 生产场景验证动态权重、阈值校准、prompt 版本、数据源健康、抓取稳定性、成本控制和权限审计。P7-C08 是整体系统上线前门禁。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 验证模块权重可基于回测评分调整。
- 验证状态机阈值和预警阈值可配置、可回滚。
- 验证 prompt 版本管理和模型输出差异记录。
- 验证 Playwright 抓取失败、超时、验证码、页面变更降级路径。
- 验证缓存、限流、重试、成本控制。
- 验证新增数据源的权限、审计和配置化流程。

## 输入

P7-C01 至 P7-C07，P6-C07 replay scores，P8/P9/P5 全链路 mock。

## 输出

- production mock scenarios。
- calibration test report。
- rollout / rollback checklist。
- P7 DoD 验收清单。
- Governance module：`backend/src/onlybtc/governance/p7_production_gate.py`。
- 报告生成脚本：`scripts/generate_p7_c08_production_gate_report.py`。
- 测试：`backend/tests/test_p7_production_gate.py`。
- 报告：`reports/p7-c08-production-gate-report.json/md`。

## 验收标准

- 阈值和权重调整有审计记录，可回滚。
- 抓取失败不会阻断全系统，能触发数据质量降权。
- 成本与限流策略可在配置中调整。
- 新增数据源必须经过 schema、source health、权限审计。
- P7 DoD 全部通过后，才允许进入真实长期运行。
- [x] 报告明确 `applied_to_production=false`。
- [x] P7-C01 至 P7-C07 的治理报告/能力都被纳入 gate。
- [x] Production mock scenarios 覆盖权重、阈值、prompt、source health、Playwright、成本、权限。
- [x] Rollout checklist 和 rollback checklist 可被后续生产化任务直接引用。
- [x] Warning 状态能被保留为上线前待处理项，不被误判为 production apply。
- [x] 测试覆盖子报告聚合、mock scenario、DoD gate、报告生成。

## 执行记录

- 新增 `backend/src/onlybtc/governance/p7_production_gate.py`，聚合 P7-C01 至 P7-C07 子报告，输出 child report 状态、production mock scenarios、DoD checks、rollout/rollback checklist。
- 新增 `scripts/generate_p7_c08_production_gate_report.py`，按顺序刷新 C01-C07 报告后生成 `reports/p7-c08-production-gate-report.json/md`。
- 新增 `backend/tests/test_p7_production_gate.py`，覆盖 ready gate、critical blocker、production-applied blocker、报告生成。
- 当前 C08 报告结果：`overall_status=warning`，`production_apply_allowed=False`，`alert_count=4`。
- 当前阻断项：
  - P7 DoD failed checks：无。
  - P7-C04 `run_mode_mixing_production_blocker` 已由 P7-C32 修复，历史 mock/test 混用只保留为 `history_contamination_warning`。
- 当前 warning 项：
  - `P7-C04 source_health_monitor`：source freshness / fallback / registry drift / recent source health warning。
  - `P7-C05 playwright_stability`：登录态/Playwright 稳定性 warning。
  - `P7-C06 cost_cache_rate_limit_retry`：预算/fallback warning。
  - `P7-C07 provider_permission_source_onboarding`：OpenAI/Glassnode 权限或登录态 warning。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_production_gate.py -q` -> 4 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c08_production_gate_report.py` -> 生成 JSON/MD 报告。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\governance scripts\generate_p7_c08_production_gate_report.py` -> passed。

## 依赖任务

P7-C01、P7-C02、P7-C03、P7-C04、P7-C05、P7-C06、P7-C07

## 备注

P7 的核心不是新增功能，而是让系统在真实噪音、失败和成本约束下还能稳定运行。
