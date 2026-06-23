# P4-C24 Final Controller 发布门控语义一致性与观察级输出治理

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 Agent 推理与总控融合 / P5 Dashboard 可视化前置

## 任务目标

修复 P4 Final Controller 在 `blocked_by` 存在时仍输出 `publish_allowed=true`、`publish_scope=publish_candidate` 的语义不一致问题，统一状态机、Judge、Adversarial Review、Final Controller、中文文章和审计 HTML 对“发布/观察/阻断”的口径。

本卡要确保：

```text
State Machine hard constraints
  -> Judge blocked_by / confidence discount
  -> Adversarial Review gate
  -> Final Controller publish_allowed / publish_scope
  -> Article Writer 中文表述
  -> P4 DoD / HTML / P5 Dashboard 字段
```

在同一套语义下表达，不再出现“正文说仅观察，但 JSON 仍是 publish_candidate”的冲突。

## 背景依据

2026-05-21 真实 P1/P2/P3/P4 LLM 全链条运行中发现：

- P4 HTML 中文最终观察文章输出：
  - “状态机应用了事件窗口发布约束、主要信号证据缺失及运行模式完整性失效三项限制，导致关键发布被阻止，仅允许观察级发布。”
- 同一份 Final Controller JSON 却输出：
  - `publish_allowed=true`
  - `publish_scope=publish_candidate`
  - `watch_only=false`
  - `dashboard_only=false`
  - `blocked_by=["event_window_publish_constraint","missing_primary_signal_evidence","run_mode_integrity_invalidation"]`

这说明 LLM 文章层已经读懂了 hard constraints，但确定性发布门控层没有把 `blocked_by` 反向映射到 `publish_allowed/publish_scope`。

## 问题根因

当前链路中存在三处语义不一致：

1. `run_state_machine()`
   - 已正确产生 `blocked_by`、`critical_publish_allowed=false`、`state_transition_allowed=false`。
   - 但仍固定返回 `publish_allowed=true`，语义更像“允许生成观察输出”，而不是“允许发布”。

2. `run_judge_synthesis()`
   - 直接继承 `state.publish_allowed`，导致 Judge 在 hard constraints 存在时仍保留 `publish_allowed=true`。

3. `build_final_controller_json()`
   - 只在 `adversarial_review_missing/failed` 或 `revision_gate_failed` 时关闭发布。
   - 没有把 `blocked_by` 作为发布门控条件。
   - `_publish_scope()` 先看 `publish_allowed`，导致 `blocked_by` 非空仍进入 `publish_candidate`。

同时还存在一处可读化语义混淆：

4. Data Quality 与 Production Readiness 混用
   - 当前文章会写“证据包数据质量评分为 0.914，整体可信度较高”。
   - 但同一段又写“运行模式混合（live/mock）导致 0.569 信心折扣，最终综合信心 0.3039”。
   - 这两句话本身不矛盾，但缺少明确拆分：
     - `data_quality_score` 表示已进入 Evidence Pack 的源数据质量、freshness、business recency 等质量。
     - `run_mode_integrity` / `production_readiness` 表示本轮是否满足真实生产发布条件。
   - 当 live/mock 混用触发 `run_mode_integrity_invalidation` 时，即使 `data_quality_score` 较高，也只能说明“已入包数据本身较干净”，不能说明“本轮可发布可信”。

## 业务原则

- `publish_allowed` 表示是否允许进入正式发布候选，不等于是否允许生成审计报告或观察文章。
- `blocked_by` 非空时，不能输出 `publish_scope=publish_candidate`。
- `critical_publish_allowed=false` 时，必须在 Final Controller 和 HTML 中显示为观察级或 Dashboard-only。
- `run_mode_integrity_invalidation` 是生产发布硬约束，不能被 LLM 文章或反方审查通过覆盖。
- Adversarial Review `passed=true` 只代表审查链条完整，不代表发布门禁自动放行。
- P5 Dashboard 只能消费一致的门控字段，不能再靠读中文文章推断真实状态。
- `data_quality_score` 与 `production_readiness` 必须分开表达：
  - 数据质量高不等于生产发布可用。
  - live/mock 混用、历史 fallback 过多、run-mode integrity 失效必须单独进入发布门控和文章解释。

## 实施范围

1. State Machine 语义拆分
   - 明确区分：
     - `analysis_output_allowed`
     - `critical_publish_allowed`
     - `state_transition_allowed`
     - `publish_allowed`
   - 对旧字段保持兼容，但 Final Controller 以 hard gate 为准。

2. Judge Synthesis 对齐
   - Judge 可继续记录 `blocked_by` 与 confidence discount。
   - `publish_allowed` 不应在 `blocked_by` 非空时保持 true。
   - 若保留观察输出，应通过 `watch_only` 或 `publish_scope` 表达。

3. Final Controller 门控修复
   - `blocked_by` 非空时：
     - `publish_allowed=false`
     - `publish_scope=watch_only` 或 `dashboard_only`
     - `watch_only=true`
     - `publish_block_reason` 必须列出 hard constraints
   - `revision_gate_failed` 时进入 `dashboard_only`。
   - `adversarial_review_failed/missing` 时进入 `dashboard_only` 或 `blocked`。
   - 无 hard constraints 且 revision/adversarial gate 通过时，才允许 `publish_candidate`。

4. Article Writer 表述对齐
   - 中文文章不能再出现“发布虽被允许，但受到阻塞”这类语义冲突。
   - 应明确写：
     - “本轮仅生成观察级输出”
     - “不进入正式发布候选”
     - “原因：...”
   - 数据质量段落必须拆成两层：
     - Evidence Pack 数据质量：例如 `data_quality_score=0.914`。
     - 生产发布完整性：例如 `run_mode_integrity_invalidation`、live/mock 混用数量、confidence discount。
   - 当生产完整性失败时，文章必须写明：
     - “数据源字段质量较高，但本轮生产发布完整性不足。”
     - “最终信心折扣主要来自 run-mode / fallback / hard constraint，而不是单个数据源 freshness 失败。”

5. P4 HTML 可读化对齐
   - 顶部卡片显示：
     - `Publish Scope`
     - `Publish Allowed`
     - `Critical Publish Allowed`
     - `Blocked By`
   - 如果 `blocked_by` 非空但 `publish_scope=publish_candidate`，HTML/DoD 必须失败。

6. P4 DoD 增强
   - 新增检查：
     - `blocked_by_nonempty_blocks_publish_candidate`
     - `publish_scope_matches_blocked_by`
     - `watch_only_matches_publish_scope`
     - `article_publish_semantics_consistent`

7. 回归验证
   - 用最新真实 run 的 `debate_id` 重新生成 Final Controller。
   - 再跑一次 P4 DoD。
   - 必要时跑 P4 full audit mock/llm 验证 HTML。

## 输入

- `state_machine` 输出
- `judge_synthesis`
- `adversarial_review`
- `CrossExamRevision`
- Final Controller JSON
- Article Writer 中文文章
- `reports/p4-controller-audit-report.html`

## 输出

- 修复后的 Final Controller JSON
- 一致的 `publish_allowed/publish_scope/watch_only/dashboard_only/blocked_by`
- P4 HTML 中同步显示观察级输出状态
- P4 DoD 新增门控一致性检查

## 验收标准

- `blocked_by` 非空时，不得输出 `publish_scope=publish_candidate`。
- `run_mode_integrity_invalidation` 存在时，必须阻断正式发布候选。
- `publish_allowed=false` 时，中文文章必须解释为观察级输出，而不是发布候选。
- 数据质量段落必须区分 `data_quality_score` 和 `production_readiness/run_mode_integrity`，不得把“源数据质量高”写成“本轮结论可发布可信”。
- `adversarial_review.passed=true` 不会覆盖 hard constraints。
- P4 HTML 顶部摘要、最终总控摘要、最终观察文章、JSON 附录四处口径一致。
- P4 DoD 新增门控一致性检查通过。
- 不影响 P1/P2/P3 数据生产链路。
- 不输出交易建议、仓位、杠杆、止损或买卖指令。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_state_machine.py backend/tests/test_p4_judge.py backend/tests/test_p4_final_controller.py backend/tests/test_p4_full_chain_audit.py -q
.\.venv\Scripts\python.exe -m onlybtc.cli p4-final-controller --debate-id <latest_debate_id>
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --no-collect-live --run-mode live --runtime-mode mock --article-runtime-mode mock
```

真实 LLM 验证在 mock 链路通过后执行：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
```

## 依赖任务

P4-C10、P4-C16、P4-C17、P4-C18、P4-C20、P4-C21、P4-C22、P4-C23、P5-C11

## 备注

本卡不是调整 LLM 观点，而是修复确定性发布门控的业务语义。LLM 可以参与解释，但不能覆盖 State Machine / P3 invalidation / P8 run-mode integrity 的 hard constraints。

## 2026-05-21 执行记录

已完成：

- State Machine 新增 `analysis_output_allowed=true`，并将 `publish_allowed` 改为只在 `critical_publish_allowed=true` 时放行。
- Judge / Adversarial Review / Final Controller 继承 hard constraints 后，`blocked_by` 非空时不再进入正式发布候选。
- Final Controller 修复：
  - `blocked_by` 非空 -> `publish_allowed=false`
  - `publish_scope=watch_only`
  - `watch_only=true`
  - `publish_block_reason` 保留 hard constraints
- Data Quality 与 Production Readiness 拆分：
  - `data_quality_score` 仍表示 Evidence Pack 数据质量。
  - `production_readiness=blocked_by_run_mode_integrity` 明确表示运行模式完整性阻断发布。
  - 中文文章不再把“数据质量高”写成“可发布可信”。
- Article Writer prompt 增加发布语义约束：
  - `blocked_by` 非空时必须写成观察级 / audit-only。
  - 不允许把 `publish_allowed=false` 描述成可发布。
- P4 DoD 增加并通过：
  - `blocked_by_nonempty_blocks_publish_candidate`
  - `publish_scope_matches_blocked_by`
  - `watch_only_matches_publish_scope`
  - `article_publish_semantics_consistent`

验证结果：

```text
pytest backend/tests -q
100 passed

ruff check backend/src backend/tests
All checks passed

p4-dod-check
status=passed, passed_count=17, failed_count=0
```

真实 P1/P2/P3/P4 live + LLM 全链条已完成：

```text
collect_run_id=collect-20260521122557-494801
p2_radar_run_id=radar-20260521122726-45f5ed
p3_run_id=p3-20260521122727-98d47b
evidence_pack_id=p4-pack-20260521122729-d59a8a
debate_id=debate-cbf62bc386c8
judge_synthesis_id=judge-9dda0ce988c9
adversarial_review_id=review-b3a512f920d3
snapshot_id=snapshot-b96fcbece15d
publish_allowed=false
publish_scope=watch_only
blocked_by=event_window_publish_constraint, missing_primary_signal_evidence, run_mode_integrity_invalidation
```

输出 HTML：

- `reports/p1-c22-真实数据全链路验收报告.html`
- `reports/p2-radar-quality-report.html`
- `reports/p3-algorithm-audit-report.html`
- `reports/p4-controller-audit-report.html`
