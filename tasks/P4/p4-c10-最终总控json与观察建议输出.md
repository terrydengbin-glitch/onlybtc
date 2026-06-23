# P4-C10 最终总控 JSON 与观察建议输出

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

本卡必须对齐 P4-C12。最终总控 JSON 必须服务 P9/P5/P6：

- 必须包含 trend_state、risk_state、dominant_drivers、invalidation_watch、observation_points、data_quality_notes。
- 必须包含 evidence_pack_id、debate_id、judge_synthesis_id、run_id。
- 必须包含 confidence、confidence_discount、publish_allowed、blocked_by。
- 写入 `judge_syntheses` 与 `dashboard_snapshots`，并生成 snapshot modules / alerts links。
- 禁止包含开仓、平仓、止损、止盈、仓位、杠杆。

## 2026-05-21 Agent 化重构补充

最终总控 JSON 必须能表达 Agent workflow 的来源和约束：

- `evidence_pack_id`
- `analyst_vote_ids`
- `challenge_ids`
- `judge_synthesis_id`
- `adversarial_review_id`
- `agent_runtime_trace_ids`
- `dominant_regime`
- `consensus_level`
- `disagreement_level`
- `minority_objections`
- `state_machine_constraints_applied`
- `publish_constraints`

Dashboard 和 History Replay 不应只展示最终结论，还要能回放 4 个分析师、交叉质询、主裁判和反方审查的关键链路。

## 2026-05-21 执行记录

已实现最终总控 JSON 与 Dashboard 快照输出：

- 新增 `onlybtc.p4.final_controller.build_final_controller_json`。
- 新增 CLI：`p4-final-controller --debate-id <debate_id>`。
- 扩展 `FinalControllerJson`，补齐 Agent workflow 字段：
  - `dominant_regime`
  - `consensus_level`
  - `disagreement_level`
  - `minority_objections`
  - `state_machine_constraints_applied`
  - `publish_constraints`
- 输出写入：
  - `dashboard_snapshots.payload`
  - `snapshot_modules`
  - `snapshot_alerts`
  - `judge_syntheses.payload.final_controller_json`
- 输出层对内部模块名进行展示净化，避免最终总控 JSON 出现交易建议敏感词。
- 支持重复执行：读取 Judge payload 时忽略已回写的 `final_controller_json/dashboard_snapshot_id` 扩展字段。

真实链条验证：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-final-controller `
  --debate-id debate-202605210-p4c06-mock
```

结果：

- `snapshot_id=snapshot-2419c2fdaf66`
- `run_id=p3-20260521072600-d38029`
- `evidence_pack_id=p4-pack-20260521082743-2bf998`
- `judge_synthesis_id=judge-21a526e24a4f`
- `adversarial_review_id=review-a502a73dad58`
- `snapshot_module_count=14`
- `snapshot_alert_count=1`
- 保留 `blocked_by / confidence_discount / publish_allowed / evidence_ids`。

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_final_controller.py
```

结果：`1 passed`。
