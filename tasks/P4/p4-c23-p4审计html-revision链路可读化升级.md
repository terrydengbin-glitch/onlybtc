# P4-C23 P4 审计 HTML Revision 链路可读化升级

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 Agent 推理与总控融合 / P5 Dashboard 可视化前置

## 任务目标

在 P4-C20、P4-C21、P4-C22 接入后，升级 `reports/p4-controller-audit-report.html`，让 P4 审计 HTML 从“JSON 与表格可见”进一步升级为“人类可读的完整审议链路”。

本卡是 P4-C17 审计 HTML 可读化的升级版，重点补齐：

```text
Analyst 初始观点
  -> CrossExamChallenge
  -> CrossExamRevision
  -> Judge revised synthesis
  -> Adversarial Revision Gate
  -> Final Controller publish scope
  -> 中文观察建议
```

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P4-C16 P4 Agent 全链条重跑与审计 HTML
- P4-C17 提示词驱动中文文章生成与审计 HTML 可读化
- P4-C18 全 Agent 真实 Runtime 切换与成本失败降级治理
- P4-C20 CrossExamRevision 修正回合与 Judge 输入契约
- P4-C21 反方审查 Revision 覆盖与发布门禁升级
- P4-C22 Final Controller Revision Gate 与观察建议输出对齐
- P5-C11 LLM Debate 多模型讨论页

## 业务原则

P4 审计 HTML 是本地审计与 P5 页面设计的共同基准，不应只是数据库 dump。

- 人类应能从 HTML 直接看懂本轮为什么得出最终结论。
- 每个关键结论必须能看到 evidence/data/history 引用。
- 每个 challenge 必须能看到对应 revision 或 fallback reason。
- 每个发布门禁必须能看到原因。
- JSON 仍保留，但应放在可读摘要之后。

## 实施范围

1. Run Lineage 总览升级
   - 展示：
     - `collect_run_id`
     - `p2_radar_run_id`
     - `p3_run_id`
     - `evidence_pack_id`
     - `debate_id`
     - `judge_synthesis_id`
     - `adversarial_review_id`
     - `snapshot_id`
     - `runtime_mode`
     - `article_runtime_mode`
   - 明确本轮是否同 run、是否使用 historical fallback。

2. Analyst 初始观点区
   - 展示 4 个 Analyst：
     - 负责 Radar 模块
     - 初始 vote/confidence
     - 关键 evidence/data
     - history delta
     - data quality / fallback discount

3. CrossExam Challenge -> Revision 区
   - 按 Analyst 分组展示 challenge。
   - 每条 challenge 展示：
     - challenge type
     - severity
     - claim under review
     - required response
     - evidence_ids
   - 每条 revision 展示：
     - changed=true/false
     - previous vote/confidence
     - revised vote/confidence
     - accepted/rejected points
     - reason
     - evidence_ids
   - 无 revision 时展示 fallback reason 或 unresolved 状态。

4. Judge revised synthesis 区
   - 展示 Judge 如何消费 revision：
     - accepted claims
     - rejected claims
     - minority objections
     - confidence discount
     - revised matrix summary
     - blocked_by
   - 明确 Judge 不是简单投票。

5. Adversarial Revision Gate 区
   - 展示：
     - revision coverage
     - unresolved challenge count
     - required fixes
     - publish gate decision
     - watch-only / dashboard-only / blocked reason
   - 如果审查失败，页面顶部必须有醒目的非交易化阻断提示。

6. Final Controller / 中文观察建议区
   - 展示结构化 final state：
     - trend_state
     - risk_state
     - confidence
     - publish_allowed
     - watch_only
     - dashboard_only
     - publish_scope
     - publish_block_reason
   - 展示中文观察建议文章，并引用 evidence + revision + adversarial gate。

7. Runtime Matrix 升级
   - 展示每个 Agent 的 provider/model/fallback/latency/error。
   - 增加 revision runtime。
   - fallback 不再只放 JSON，必须人类可读。

8. JSON 附录
   - 保留原始 JSON 表格/折叠区。
   - 长字段必须可折叠或换行，避免 `changed_fields` 一类字段挤成一团。

## 输入

- P4 full audit context
- `llm_model_votes`
- `llm_challenges`
- `CrossExamRevision`
- `judge_syntheses`
- `adversarial_reviews`
- Final Controller JSON
- Article Writer 输出
- Runtime results

## 输出

- 升级后的 `reports/p4-controller-audit-report.html`
- P4 HTML 中新增 revision chain / adversarial gate / publish scope 可读区块
- P5-C11 可复用的展示字段基线

## 验收标准

- 打开 HTML 后，无需读 JSON 也能理解本轮结论来源。
- 每个 high/critical challenge 都能看到 revision 或 unresolved/fallback reason。
- Judge 是否消费 revision 可见。
- 反方审查发布门禁可见。
- Final Controller 的 publish scope 可见。
- 中文观察建议解释 revision 与反方审查。
- 长 JSON 字段不挤压布局，表格可读。
- P4 full audit 真实跑一次后刷新 P1/P2/P3/P4 HTML。
- 不输出交易建议、仓位、杠杆、止损或买卖语言。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_full_audit.py backend/tests/test_p4_final_controller.py backend/tests/test_p4_article_writer.py -q
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --no-collect-live --run-mode live --runtime-mode mock --article-runtime-mode mock
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

真实 LLM 验证在 P4-C20/P4-C21/P4-C22 mock 链路通过后执行。

## 依赖任务

P4-C16、P4-C17、P4-C18、P4-C20、P4-C21、P4-C22、P5-C11

## 备注

本卡只定义审计 HTML 升级，不改变 P4 推理结果。推理契约由 P4-C20/P4-C21/P4-C22 负责，本卡负责让审计结果真正可读、可追溯、可用于 P5 页面设计。

## 2026-05-21 执行记录

已完成：

- `reports/p4-controller-audit-report.html` 新增：
  - `交叉质询 Revision`
  - `Revision Gate / Publish Scope`
  - Final Controller revision gate 字段展示
  - runtime matrix 中 `cross_exam_revision`
- HTML 可见：
  - `revision_integrity`
  - `publish_scope`
  - `unresolved_challenge_count`
  - `unresolved_high_challenge_count`
  - `revision_required_fixes`
  - `publish_block_reason`
- 长 JSON 继续使用 `pre-wrap / overflow-wrap:anywhere`，避免挤压布局。

验证：

- 最新 HTML：`reports/p4-controller-audit-report.html`
- HTML 已包含：
  - `交叉质询 Revision`
  - `Revision Gate / Publish Scope`
  - `revision_integrity`
  - `publish_scope`
- `p4-dod-check`: `status=passed`、`passed_count=13`、`failed_count=0`
- 后端全量测试：`100 passed`
- P4 相关测试：`17 passed`
- Ruff：`All checks passed`
