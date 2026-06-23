# P4-C21 反方审查 Revision 覆盖与发布门禁升级

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 Agent 推理与总控融合

## 任务目标

在 P4-C20 接入 `CrossExamRevision` 后，升级 P4-C09 反方审查机制，让反方审查不只检查 Judge 是否保留 challenge，还要检查：

- 每条 material challenge 是否被对应 Analyst 正式回应；
- Analyst 的 revision 是否有 evidence-backed reason；
- Judge 是否消费了 revised vote/confidence matrix；
- 未回应或回应不足的 high/critical challenge 是否进入发布门禁。

当前 P4-C09 已接入主链，能检查 `votes + challenges + judge_synthesis`。本卡要把它升级为：

```text
votes
  -> challenges
  -> revisions
  -> judge synthesis
  -> adversarial review
  -> publish gate
```

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P4-C09 反方审查机制
- P4-C20 CrossExamRevision 修正回合与 Judge 输入契约
- P4-C18 全 Agent 真实 Runtime 切换与成本失败降级治理
- P5-C11 LLM Debate 多模型讨论页

## 业务原则

反方审查是最终发布前硬门禁，不是附加解释。

- high/critical challenge 没有 revision 时，默认不得发布。
- revision 拒绝修正但证据不足时，必须要求修复。
- Judge 未消费 revised matrix 时，必须要求修复。
- runtime fallback 可以允许链路继续，但必须进入 confidence discount、HTML 和 Final Controller。
- 反方审查不得生成新交易观点，只能检查证据、链路和约束是否完整。

## 实施范围

1. Revision Coverage 检查
   - 按 `challenge_id` 检查是否存在 revision。
   - medium/high/critical challenge 必须有 revision 或明确 fallback reason。
   - high/critical challenge 缺 revision 时，`required_fixes` 必须包含阻断项。

2. Revision Quality 检查
   - `changed=true` 时检查：
     - `previous_vote` 与 `revised_vote`
     - `previous_confidence` 与 `revised_confidence`
     - `accepted_points`
     - `evidence_ids`
   - `changed=false` 时检查：
     - `rejected_points`
     - `reason`
     - `evidence_ids`
   - evidence 缺失或使用 `no-evidence-id-available` 时必须失败。

3. Judge Consumption 检查
   - Judge payload 必须包含 revision summary 或 revised matrix lineage。
   - Judge 的 `accepted_claims / rejected_claims / minority_objections` 必须能追溯到 revision。
   - 如果 Analyst revised confidence 明显降低，Judge 不能继续使用旧 confidence。
   - 如果 Analyst 拒绝 high challenge，Judge 必须将其保留为 disagreement/minority objection。

4. Publish Gate 升级
   - 以下情况必须 `publish_allowed=false` 或 watch-only：
     - unresolved high/critical challenge
     - missing revision evidence
     - Judge did not consume revisions
     - runtime fallback hides material revision failure
     - hard state-machine block remains active
   - Final Controller 必须记录：
     - `revision_integrity`
     - `unresolved_challenge_count`
     - `revision_required_fixes`
     - `adversarial_publish_gate_reason`

5. HTML / P5 展示准备
   - P4 HTML 增加 Adversarial Revision Gate 区块。
   - 展示 challenge -> revision -> judge -> adversarial decision 的完整链路。
   - P5-C11 LLM Debate 页面可直接展示 revision coverage 与发布门禁状态。

## 输入

- `llm_model_votes`
- `llm_challenges`
- `CrossExamRevision` 输出
- `judge_syntheses`
- `runtime_results`
- P4 state machine constraints
- Final Controller JSON

## 输出

- 升级后的 `adversarial_reviews` payload。
- `required_fixes` 包含 revision coverage / judge consumption 检查结果。
- Final Controller 可见 revision gate 字段。
- P4 HTML 可读展示反方审查门禁。

## 验收标准

- high/critical challenge 缺 revision 时，反方审查必须失败。
- revision 无 evidence_id 时，反方审查必须失败。
- Judge 未消费 revised matrix 时，反方审查必须失败或要求修复。
- `changed=false` 且拒绝理由无证据时，反方审查必须失败。
- runtime fallback 导致 revision 不完整时，必须进入 `llm_runtime_integrity` 或 revision integrity。
- P4 full audit HTML 能展示 Revision Gate。
- P4 DoD 增加 adversarial revision gate 检查。
- 不输出交易建议、仓位、杠杆、止损或买卖语言。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_adversarial_review.py backend/tests/test_p4_cross_exam.py backend/tests/test_p4_judge.py backend/tests/test_p4_final_controller.py -q
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --no-collect-live --run-mode live --runtime-mode mock --article-runtime-mode mock
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

真实 LLM 验证在 P4-C20 mock 链路通过后执行。

## 依赖任务

P4-C09、P4-C18、P4-C20、P5-C11

## 备注

本卡不替代 P4-C20。P4-C20 负责生成 revision；P4-C21 负责审查 revision 是否完整、是否被 Judge 消费，以及是否允许发布。

## 2026-05-21 执行记录

已完成：

- `run_adversarial_review()` 已读取 `llm_revisions`。
- 新增 revision coverage gate：
  - high/critical challenge 缺 revision 时失败；
  - revision 缺 evidence 时失败；
  - `changed=false` 但无 rejected_points 时失败；
  - Judge 未保留 `revision_summary` 时失败。
- 反方审查 findings / required_fixes 已能体现 revision gate。
- Final Controller 可读取反方审查 revision gate 结果。

验证：

- P4 full audit mock run：
  - `adversarial_review_id=review-aece62e6c216`
  - `revision_integrity=passed`
- `p4-dod-check`: `status=passed`、`passed_count=13`、`failed_count=0`
- 后端全量测试：`100 passed`
- P4 相关测试：`17 passed`
- Ruff：`All checks passed`
