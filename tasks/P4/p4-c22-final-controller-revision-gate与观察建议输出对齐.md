# P4-C22 Final Controller Revision Gate 与观察建议输出对齐

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 Agent 推理与总控融合

## 任务目标

在 P4-C20 `CrossExamRevision` 与 P4-C21 反方审查 Revision Gate 接入后，升级 P4-C10 最终总控 JSON 与观察建议输出，确保最终产物不只消费初始 Analyst votes 和 Judge synthesis，还要消费完整的：

```text
CrossExamRevision
  -> Judge revised synthesis
  -> Adversarial Revision Gate
  -> Final Controller JSON
  -> 中文观察建议文章
  -> Dashboard Snapshot / P5
```

本卡不重开 P4-C10，而是作为 P4-C10 后续对齐卡，补齐 revision gate 后的最终输出契约。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P4-C10 最终总控 JSON 与观察建议输出
- P4-C17 提示词驱动中文文章生成与审计 HTML 可读化
- P4-C18 全 Agent 真实 Runtime 切换与成本失败降级治理
- P4-C20 CrossExamRevision 修正回合与 Judge 输入契约
- P4-C21 反方审查 Revision 覆盖与发布门禁升级
- P5-C01 / P5-C08 / P5-C11 Dashboard、Article、LLM Debate 页面

## 业务原则

Final Controller 是最终对外输出的唯一状态契约，必须忠实反映前面所有审议与门禁。

- 不允许 Final Controller 忽略 revision gate 后继续输出宽松 `publish_allowed=true`。
- 不允许观察建议文章只解释初始 Analyst 观点，而不解释修正和反方审查。
- 不允许 P5 需要自己推断 watch-only、dashboard-only 或 blocked 状态。
- 所有发布/展示状态必须来自结构化字段。
- 输出仍然是观察与风险总结，不是交易建议。

## 实施范围

1. Final Controller JSON 字段升级
   - 新增或确认以下字段：
     - `revision_integrity`
     - `revision_round_count`
     - `unresolved_challenge_count`
     - `unresolved_high_challenge_count`
     - `revision_required_fixes`
     - `adversarial_publish_gate_reason`
     - `watch_only`
     - `dashboard_only`
     - `publish_scope`
     - `publish_block_reason`
     - `revised_vote_matrix_summary`
   - 保留并继续输出：
     - `evidence_pack_id`
     - `debate_id`
     - `judge_synthesis_id`
     - `snapshot_id`
     - `blocked_by`
     - `publish_allowed`
     - `llm_runtime_integrity`
     - `fallback_used`
     - `fallback_reasons`
     - `llm_budget_summary`

2. Publish Scope 与 Watch-only 语义治理
   - 明确发布范围：
     - `publish_allowed=true`：允许进入文章/外部发布候选。
     - `watch_only=true`：只允许 Dashboard / 内部观察展示。
     - `dashboard_only=true`：只更新 Dashboard，不生成对外文章。
     - `publish_allowed=false`：发布阻断。
   - hard block、unresolved high challenge、revision gate fail、runtime integrity fail 必须降级发布范围。

3. 观察建议文章升级
   - 中文最终观察建议必须解释：
     - 哪些 Analyst 在 revision 后改变了观点或 confidence；
     - 哪些 challenge 被接受；
     - 哪些 challenge 被拒绝，以及拒绝依据；
     - Judge 为什么接受/拒绝修正；
     - 反方审查为什么允许、watch-only 或阻断发布；
     - 当前输出适合 Dashboard-only、watch-only 还是 publish candidate。
   - 每个关键结论仍必须引用 evidence + data + history。

4. Dashboard Snapshot / P5 契约
   - `dashboard_snapshots.payload` 必须包含 revision gate 字段。
   - P5 Dashboard / Article / LLM Debate 不需要重新推断最终状态。
   - P5-C11 可展示 challenge -> revision -> judge -> adversarial -> final controller。

5. P4 HTML 审计
   - P4 HTML 的 Final Controller 区块展示 revision gate 摘要。
   - 中文文章区展示 revision 后的观察建议。
   - Runtime Matrix 中保留 revision / adversarial / article 的 fallback 信息。

## 输入

- CrossExamRevision 结果
- revised vote/confidence matrix
- Judge synthesis
- Adversarial Review / Revision Gate
- Final Controller 当前 JSON
- Article Writer 输出
- Dashboard snapshot payload

## 输出

- 升级后的 Final Controller JSON。
- 升级后的中文观察建议。
- 升级后的 dashboard snapshot payload。
- P4 HTML 可读展示 revision gate 与 publish scope。
- P5 可直接消费的最终状态字段。

## 验收标准

- Final Controller 能反映 P4-C20/P4-C21 的 revision gate 结果。
- unresolved high/critical challenge 存在时，不得 `publish_allowed=true`。
- revision gate fail 时必须输出 `publish_block_reason` 或 `watch_only`。
- 中文观察建议必须解释修正回合与反方审查结果。
- P5 不需要通过自由文本解析判断发布范围。
- P4 DoD 增加 Final Controller revision gate 字段检查。
- P4 full audit HTML 展示 revision gate、publish scope 和最终观察建议。
- 不输出交易建议、仓位、杠杆、止损或买卖语言。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_final_controller.py backend/tests/test_p4_article_writer.py backend/tests/test_p4_adversarial_review.py backend/tests/test_p4_judge.py -q
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --no-collect-live --run-mode live --runtime-mode mock --article-runtime-mode mock
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

真实 LLM 验证在 P4-C20 / P4-C21 mock 链路通过后执行。

## 依赖任务

P4-C10、P4-C17、P4-C18、P4-C20、P4-C21、P5-C08、P5-C11

## 备注

本卡合并治理 “Publish Scope 与 Watch-only 语义”。最终发布状态必须在 Final Controller JSON 里结构化表达，不能让 P5 或文章层自行猜测。

## 2026-05-21 执行记录

已完成：

- Final Controller JSON 新增：
  - `revision_ids`
  - `revision_integrity`
  - `revision_round_count`
  - `unresolved_challenge_count`
  - `unresolved_high_challenge_count`
  - `revision_required_fixes`
  - `adversarial_publish_gate_reason`
  - `watch_only`
  - `dashboard_only`
  - `publish_scope`
  - `publish_block_reason`
  - `revised_vote_matrix_summary`
- `dashboard_snapshots.payload` 已包含 revision gate 字段。
- `p4-dod-check` 已增加 revision 字段与 revision rows 检查。
- Final JSON 内部展示字段已做嵌套脱敏，避免 P4/P5 暴露不合规交易词片段。

验证：

- P4 full audit mock run：
  - `snapshot_id=snapshot-90283f07d614`
  - `publish_scope=publish_candidate`
  - `revision_integrity=passed`
- `p4-dod-check`: `status=passed`、`passed_count=13`、`failed_count=0`
- 后端全量测试：`100 passed`
- P4 相关测试：`17 passed`
- Ruff：`All checks passed`
