# P4-C19 GPT 独立验证子线与 P4 结果对照

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## Execution Record

2026-05-21 completed.

- Added standalone test script: `scripts/p4-gpt-independent-validation.py`.
- The script does not modify P1/P2/P3/P4 production code.
- The script reads latest SQLite P4 snapshot, final controller JSON, evidence pack, evidence items, analyst votes, challenges, judge synthesis, adversarial review, and report paths.
- The script exports context even when GPT cannot run:
  - `reports/p4-gpt-independent-validation-context.json`
- The independent validation was completed by current-session GPT/Codex direct reasoning over the exported context, without calling external OpenAI API.
- Generated reports:
  - `reports/p4-gpt-independent-validation-report.md`
  - `reports/p4-gpt-independent-validation-report.html`
- Validation conclusion:
  - P4 result is within expectation.
  - GPT independent judge agrees with `trend_state=constrained_watch`, `risk_state=event_watch`, `dominant_regime=constrained_event_watch`, `consensus_level=low`, `disagreement_level=medium`.
  - GPT confidence range `0.30-0.36` aligns with P4 confidence `0.3126`.
  - Runtime fallback is correctly exposed as `llm_runtime_integrity=fallback_used`.
- Suggested follow-up tasks:
  - P4-C20 CrossExamRevision 修正回合与 Judge 输入契约
  - P4-C21 反方审查 Revision 覆盖与发布门禁升级
  - P4-C22 Final Controller Revision Gate 与观察建议输出对齐
  - P4-C23 P4 审计 HTML Revision 链路可读化升级
  - P4-C24 Cross-exam LLM Schema Prompt 收敛
  - P4-C25 Kimi Provider 兼容性修复
  - P4-C26 Runtime Fallback Confidence Discount 显式化
- Verification:
  - `python -m py_compile scripts/p4-gpt-independent-validation.py` passed.
  - `ruff check scripts/p4-gpt-independent-validation.py` passed.

## 所属 Phase

P4 Agent 推理与总控融合 / P4-C18 全 Agent Runtime 治理 / 验证子线

## 背景

P4-C18 已经支持全 Agent `runtime_mode=llm`，并能把 provider 失败、schema miss、fallback、预算和 runtime integrity 写入 Final Controller JSON 与 P4 HTML。

为了验证 P4 主链输出是否符合业务预期，需要新增一条独立验证子线：由 GPT 读取同一轮 P1/P2/P3/P4 数据，独立模拟 4 个分析师、一次交叉辩论和一个主裁判推理，然后将 GPT 独立结论与 P4 主链结果对照。

这条子线不替代 P4 主链，不写入生产 final controller，只作为审计验证和模型质量复盘依据。

## 目标

- 读取同一 run 的 P1/P2/P3/P4 数据和 HTML / Final JSON。
- GPT 独立扮演 4 个分析师：
  - Macro & Event Analyst
  - Liquidity & Flow Analyst
  - Microstructure Analyst
  - On-chain & Market Structure Analyst
- GPT 独立模拟交叉质询：
  - 哪些分析师证据不足；
  - 哪些信号互相冲突；
  - 哪些结论被 P3 / state machine / run_mode integrity 约束。
- GPT 独立给出主裁判结论：
  - trend_state
  - risk_state
  - consensus_level
  - confidence
  - publish constraints
  - blocked_by
- 与当前 P4 Final Controller / P4 HTML 输出做对照：
  - 一致点；
  - 差异点；
  - 是否符合预期；
  - 哪些差异应转为后续任务。

## 输入

- 最新 P1-C22 HTML
- 最新 P2 Radar HTML
- 最新 P3 Algorithm HTML
- 最新 P4 Controller HTML
- 最新 `dashboard_snapshots.payload.final_controller_json`
- 最新 P4 Evidence Pack / Evidence Items
- 最新 P4 analyst votes / challenges / judge / adversarial review

## 输出

- `reports/p4-gpt-independent-validation-report.md`
- `reports/p4-gpt-independent-validation-report.html`
- 报告必须包含：
  - run id 对齐；
  - GPT 四分析师独立结论；
  - GPT 交叉质询；
  - GPT 主裁判结论；
  - P4 主链结果摘要；
  - GPT vs P4 对照矩阵；
  - 是否符合预期；
  - 后续建议任务。

## 验收标准

- 任务卡与 `task index.md` 同步。
- 开发文档同步该验证子线。
- GPT 独立验证报告生成。
- 报告必须明确引用 P1/P2/P3/P4 run id。
- 报告必须说明 GPT 独立判断与 P4 结果是否一致。
- 该验证不改变 P4 Final Controller 的生产输出。

## 不做

- 不改 P1/P2/P3/P4 主链算法。
- 不替代 P4 Agent 输出。
- 不新增交易建议。
- 不把 GPT 独立验证结果写回 dashboard snapshot。

## 依赖任务

P4-C16, P4-C17, P4-C18
