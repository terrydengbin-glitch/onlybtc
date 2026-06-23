# P4-C20 CrossExamRevision 修正回合与 Judge 输入契约

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 Agent 推理与总控融合

## 任务目标

在 P4-C07 已完成的 `CrossExamChallenge` 基础上，补齐真正的 Analyst Agent 二次修正回合。

当前 P4 交叉质询已经能生成 challenge、写入 `llm_challenges`，并由 Judge 消费 challenge 形成 `rejected_claims / minority_objections / confidence_discount`。但被质询的 4 个 Analyst Agent 尚未逐条正式回应 challenge，也没有把 `changed=true/false`、`revised_vote`、`revised_confidence` 作为 Judge 的结构化输入。

本卡目标是把 P4 从：

```text
Analyst votes -> CrossExamChallenge -> Judge
```

升级为：

```text
Analyst votes
  -> CrossExamChallenge
  -> CrossExamRevision by challenged analysts
  -> revised vote/confidence matrix
  -> Judge synthesis
  -> Adversarial Review
```

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P4-C01 Analyst Agent 输入输出 Schema
- P4-C06 4 分析师 Agent 独立分析执行器
- P4-C07 Analyst Agent 交叉质询与修正
- P4-C08 Judge Agent 主裁判合成与分歧处理
- P4-C09 反方审查机制
- P4-C18 全 Agent 真实 Runtime 切换与成本失败降级治理

## 业务原则

交叉质询不是多模型自由聊天，而是审计式修正。

- 每个被质询 Analyst 必须逐条回应指向自己的 challenge。
- 回应必须引用当前 Evidence Pack 内的 `evidence_id`。
- 接受质询时必须说明如何修改 vote/confidence 或风险标注。
- 拒绝质询时必须说明拒绝依据，并保留为 Judge 的 disagreement input。
- 修正回合不得引入外部事实，不得输出交易建议。
- 状态机 hard block、P3 反证、run_mode integrity、source conflict、fallback、business recency 不能被 Analyst 忽略。

## 回合策略

默认 1 个正式修正回合，最大 2 个修正回合。

```yaml
cross_exam_revision_policy:
  default_rounds: 1
  max_rounds: 2
  escalation_only: true
  stop_when:
    - all_high_challenges_answered
    - no_vote_or_confidence_change
    - judge_can_synthesize
  force_second_round_when:
    - unresolved_high_or_critical_challenge
    - ignored_state_machine_block
    - missing_evidence_after_revision
    - adversarial_review_requires_fix
```

不允许无限多轮。超过 2 轮会增加成本、schema 失败、观点漂移和 P5 可视化复杂度。

## 实施范围

1. Revision Schema 落地
   - 复用或扩展 `CrossExamRevision`：
     - `challenge_id`
     - `responding_agent`
     - `changed`
     - `previous_vote`
     - `revised_vote`
     - `previous_confidence`
     - `revised_confidence`
     - `accepted_points`
     - `rejected_points`
     - `reason`
     - `evidence_ids`
   - 必须通过 Pydantic / JSON Schema 校验。

2. Revision Runtime
   - 新增或扩展 P4 runtime：
     - 读取 `llm_challenges`
     - 按 `to_agent` 分组发送给对应 Analyst Agent
     - 生成 `CrossExamRevision`
     - 支持 `runtime_mode=mock|llm`
     - 支持 fallback、timeout、retry、budget trace
   - 每个 Analyst 只回应指向自己的 challenge。

3. SQLite / 审计持久化
   - revision 必须可落库。
   - 可选实现方式：
     - 新增 `llm_revisions` 表；或
     - 以 `llm_rounds(round_type="cross_exam_revision")` 保存 round summary，并在 `llm_model_votes.changed` / payload 中保留最终修正。
   - 推荐新增独立 revision 存储，便于 P5 LLM Debate 展示。

4. Judge 输入升级
   - `run_judge_synthesis()` 必须读取 revisions。
   - Judge 输入从 `votes + challenges` 升级为 `original_votes + challenges + revisions + revised_vote_matrix`。
   - Judge 必须区分：
     - 已接受并修正的 challenge
     - 被拒绝但有证据解释的 challenge
     - 未回应或 schema fallback 的 challenge
   - 未回应 high/critical challenge 必须进入 confidence discount 或 publish block。

5. Adversarial Review 升级
   - 反方审查检查 material challenge 是否被 revision 回应。
   - 若 high/critical challenge 没有 revision，必须要求修复或阻断发布。
   - 若 Analyst 拒绝修正但 evidence 不足，必须进入 required_fixes。

6. P4 HTML / P5 可视化准备
   - P4 审计 HTML 增加 CrossExamRevision 区块。
   - 每条 challenge 展示：
     - target analyst
     - challenge type/severity
     - accepted/rejected
     - changed
     - previous -> revised vote/confidence
     - evidence_ids
   - P5-C11 LLM Debate 可直接消费。

## 输入

- `evidence_packs`
- `llm_model_votes`
- `llm_challenges`
- P4 rule baseline
- P4 state machine
- P3 invalidations / alerts
- Analyst history memory

## 输出

- CrossExamRevision 结构化结果。
- revised vote/confidence matrix。
- Judge synthesis 输入中包含 revisions。
- P4 HTML 显示 challenge -> revision -> judge 的链路。
- Runtime trace 中包含 revision agent 的 provider/model/fallback/latency。

## 验收标准

- 每个 medium/high/critical challenge 都有 revision 或明确 fallback reason。
- revision 必须声明 `changed=true/false`。
- `changed=true` 时必须展示 previous 与 revised vote/confidence。
- `changed=false` 时必须给出 evidence-backed rejection reason。
- Judge synthesis 使用 revised matrix，而不是只使用初始 votes。
- Adversarial Review 能识别未回应的 material challenge。
- P4 DoD 增加 revision coverage 检查。
- P4 full audit 生成的 HTML 可读展示修正回合。
- 不出现交易建议、仓位、杠杆、止损或买卖语言。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_cross_exam.py backend/tests/test_p4_judge.py backend/tests/test_p4_adversarial_review.py backend/tests/test_p4_agent_runtime.py backend/tests/test_p4_schemas.py -q
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --no-collect-live --run-mode live --runtime-mode mock --article-runtime-mode mock
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

真实 LLM 验证可在 mock 通过后执行：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --no-collect-live --run-mode live --runtime-mode llm --article-runtime-mode llm
```

## 依赖任务

P4-C01、P4-C06、P4-C07、P4-C08、P4-C09、P4-C18、P5-C11

## 备注

本任务是 P4-C07 的必要补完。它不改变“Judge 不简单投票”的原则，而是让 Judge 能看到每个 Analyst 面对质询后的真实修正轨迹。

## 2026-05-21 执行记录

已完成：

- 新增 `llm_revisions` SQLite 持久化表。
- 新增 `onlybtc.p4.cross_exam_revision.run_cross_exam_revisions()`。
- 新增 CLI：`p4-cross-exam-revisions`。
- P4 full chain 已在 cross-exam 与 judge 之间执行 revision 回合。
- Revision mock/LLM runtime 支持 `runtime_mode=mock|llm`、fallback 与 runtime trace。
- Judge synthesis 已消费 revised vote/confidence matrix，并在 payload 中保留 `revision_summary`。

验证：

- P4 full audit mock run：
  - `evidence_pack_id=p4-pack-20260521113814-04f1e6`
  - `debate_id=debate-7bcad74bb428`
  - `judge_synthesis_id=judge-5f3596da1266`
  - `snapshot_id=snapshot-90283f07d614`
- `p4-dod-check`: `status=passed`、`passed_count=13`、`failed_count=0`
- 后端全量测试：`100 passed`
- P4 相关测试：`17 passed`
- Ruff：`All checks passed`
