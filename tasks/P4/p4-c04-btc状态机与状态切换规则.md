# P4-C04 BTC 状态机与状态切换规则

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.


## 状态

DONE

## 所属 Phase

P4

## 任务目标

围绕《开发文档.md》中对应 Phase 的设计，完成本任务所描述的能力建设，并保证产物可以被后续 Phase 复用。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 明确本任务涉及的数据结构、接口、组件、任务或配置。
- 遵守 evidence + data、历史窗口、数据质量、反证机制和预警边界。
- 不输出交易建议，不引入开仓、止损、仓位或杠杆逻辑。

## 输入

- 上游 Phase 或前置任务产物。
- 开发文档中对应模块、雷达、总控、预警或 Dashboard 规范。

## 输出

- 可运行或可复用的代码、配置、Schema、接口、组件或文档。
- 必要的测试、验证记录或运行说明。

## 验收标准

- 与《开发文档.md》的总体架构一致。
- 任务产物能被后续任务引用。
- 关键状态、错误和数据质量可观测。
- 不绕过状态机、反方审查、预警等级或数据质量约束。

## 依赖任务

TBD

## 备注

TBD

## 2026-05-21 全链条对齐补充

本卡必须对齐 P4-C12。状态机必须消费 P3 的真实预警与反证：

- 输入包含 P3 alert level、event window、invalidation status、run_mode integrity。
- `run_mode_integrity_invalidation=triggered` 时禁止 critical 自动发布。
- 总控状态切换必须有 evidence ids 和 state transition reason。
- LLM 只能解释状态机结果，不能绕过状态机切换到更激进状态。
- 状态机输出必须进入 `judge_syntheses.payload` 和 `dashboard_snapshots.payload`。

## 2026-05-21 Agent 化重构补充

状态机是 Judge Agent 的硬边界。P4-C04 输出必须进入：

- analyst input 的 `global_context.state_machine_constraints`。
- Judge Agent 的 `state_machine_constraints_applied`。
- 反方审查的 hard gate。
- 最终总控 JSON 的 `blocked_by / publish_allowed / risk_state`。

若状态机与某个 Analyst Agent 的观点冲突，冲突必须作为 P4-C07 challenge 或 P4-C08 minority/rejected rationale 记录。

## 2026-05-21 执行结果

已完成 P4-C04 第一版 BTC 状态机：

- 新增 `backend/src/onlybtc/p4/state_machine.py`
  - `run_state_machine()`
  - 消费 P4-C03 `build_rule_baseline()` 输出；
  - 查询同 run 的 P3 `invalidation_events`；
  - 输出 `trend_state / risk_state / state_transition_allowed / critical_publish_allowed / publish_allowed / blocked_by / state_transition_reason / state_machine_constraints_applied / evidence_ids`。
- 新增 CLI：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-state-machine --pack-id <pack_id>
```

- 新增测试 `backend/tests/test_p4_state_machine.py`，验证：
  - event window 与 missing primary signal 会阻断 critical publish；
  - `run_mode_integrity_invalidation=triggered` 会阻断 critical publish；
  - 状态机输出带 evidence ids 与 constraints；
  - hard constraints 进入 `blocked_by`。

真实库验收：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-state-machine --pack-id p4-pack-20260521082743-2bf998
```

结果摘要：

- `schema_version=p4.state_machine.v1`
- `pack_id=p4-pack-20260521082743-2bf998`
- `controller_run_id=p3-20260521072600-d38029`
- `baseline_signal=mixed`
- `baseline_confidence=0.536`
- `trend_state=constrained_watch`
- `risk_state=event_watch`
- `state_transition_allowed=false`
- `critical_publish_allowed=false`
- `publish_allowed=true`
- `blocked_by`：
  - `event_window_publish_constraint`
  - `missing_primary_signal_evidence`
  - `run_mode_integrity_invalidation`

解释：

- 当前不是“禁止任何发布”，而是禁止 critical/强状态切换发布。
- Judge Agent 后续必须把这些 hard constraints 纳入 `state_machine_constraints_applied`，不能覆盖。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_state_machine.py backend/tests/test_p4_rule_baseline.py backend/tests/test_p4_analyst_executor.py backend/tests/test_p4_agent_runtime.py backend/tests/test_p4_prompts.py backend/tests/test_p4_schemas.py backend/tests/test_p4_evidence_pack.py backend/tests/test_p4_radar_coverage.py -q
.\.venv\Scripts\ruff.exe check backend/src/onlybtc/p4 backend/src/onlybtc/cli.py backend/tests/test_p4_state_machine.py
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

结果：

- P4 相关测试：`17 passed`
- 全量后端测试：`91 passed`
- `ruff: All checks passed`
