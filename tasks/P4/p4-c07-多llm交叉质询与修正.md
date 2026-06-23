# P4-C07 Analyst Agent 交叉质询与修正

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

本卡必须对齐 P4-C12。交叉质询必须围绕结构化证据：

- challenge 必须引用 evidence_id 或 invalidation condition_id。
- 重点检查 source conflict、business recency、run_mode integrity、P3 alert/invalidation 是否被忽略。
- 修正前后 vote 必须记录 changed=true/false 与 reason。
- 质询结果写入 `llm_rounds` 和 `llm_challenges`。
- 分歧本身必须作为风险信号传给主裁判。

## 2026-05-21 Agent 化重构补充

交叉质询从“多个模型互聊”升级为受控 Cross-examination workflow：

```text
4 analyst outputs
  -> challenge generation
  -> challenged analyst revision
  -> disagreement matrix
  -> judge input
```

质询可以由专门的 `cross_examiner_agent` 执行，也可以由规则层先生成候选 challenge，再交给 runtime adapter 校验和改写。

每条 challenge 必须包含 `challenge_id / from_agent / to_agent / challenge_type / claim_under_review / evidence_ids / severity / required_response`。

每条 revision 必须包含 `challenge_id / responding_agent / changed / previous_vote / revised_vote / previous_confidence / revised_confidence / accepted_points / rejected_points / reason / evidence_ids`。

如果某个分析师拒绝修正，必须说明拒绝依据，并把该分歧传给 P4-C08 Judge Agent。

## 2026-05-21 执行结果

已完成 P4-C07 第一版受控交叉质询：

- 新增 `backend/src/onlybtc/p4/cross_exam.py`
  - `run_cross_examination()`
  - 读取同一 `debate_id` 的 4 个 analyst votes；
  - 消费 P4-C03 rule baseline；
  - 消费 P4-C04 state machine；
  - 生成 `CrossExamChallenge`；
  - 写入 `llm_challenges`；
  - 写入第 2 轮 `llm_rounds(round_type="cross_examination")`。
- 新增 CLI：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-cross-exam --pack-id <pack_id> --debate-id <debate_id>
```

- 新增测试 `backend/tests/test_p4_cross_exam.py`，验证：
  - 交叉质询读取 analyst votes；
  - 结合 baseline/state machine 生成 challenge；
  - challenge 必须有 evidence ids；
  - `llm_challenges` 入库；
  - `llm_rounds` 第 2 轮入库。

真实库验收：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-cross-exam `
  --pack-id p4-pack-20260521082743-2bf998 `
  --debate-id debate-202605210-p4c06-mock
```

结果摘要：

- `status=completed`
- `pack_id=p4-pack-20260521082743-2bf998`
- `debate_id=debate-202605210-p4c06-mock`
- `run_id=p3-20260521072600-d38029`
- `challenge_count=6`
- state machine context：
  - `trend_state=constrained_watch`
  - `risk_state=event_watch`
  - `critical_publish_allowed=false`
  - `blocked_by=[event_window_publish_constraint, missing_primary_signal_evidence, run_mode_integrity_invalidation]`

本轮 6 条 challenge 主要来自：

- 4 个 analyst 的 mock confidence=0.5 低于独立分析阈值；
- `macro_event_analyst` scope 有缺失 evidence；
- `onchain_market_structure_analyst` scope 有缺失 evidence。

说明：

- 本版先采用“规则生成 + Schema 校验 + 入库”的受控流程，不让 LLM 自由互聊。
- 如果后续 analyst 给出 bullish/bearish/risk_off 或过高 confidence，而状态机有 hard block，本模块会生成 `ignored_invalidation` challenge。
- 修正回合的真实 Agent revision 将在后续增量或 P4-C08 前置中接入，但挑战结构和入库链路已就绪。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_cross_exam.py backend/tests/test_p4_state_machine.py backend/tests/test_p4_rule_baseline.py backend/tests/test_p4_analyst_executor.py backend/tests/test_p4_agent_runtime.py backend/tests/test_p4_prompts.py backend/tests/test_p4_schemas.py backend/tests/test_p4_evidence_pack.py backend/tests/test_p4_radar_coverage.py -q
.\.venv\Scripts\ruff.exe check backend/src/onlybtc/p4 backend/src/onlybtc/cli.py backend/tests/test_p4_cross_exam.py
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

结果：

- P4 相关测试：`18 passed`
- 全量后端测试：`92 passed`
- `ruff: All checks passed`
