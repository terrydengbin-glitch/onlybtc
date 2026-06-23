# P4-C17 提示词驱动中文文章生成与审计 HTML 可读化

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## Execution Record

2026-05-21 completed.

- Added P4 article writer schemas: `EvidenceCitation`, `ReadableArticleSection`, `AnalystReadableArticle`, `FinalObservationArticle`.
- Added `article_writer_agent` prompt builders and OpenAI-compatible Chat Completions runtime.
- Added `ONLYBTC_P4_ARTICLE_PROVIDER` routing through `p4_article_provider`; current run used DeepSeek.
- Added `onlybtc.p4.article_writer.generate_readable_articles()` with mock and real LLM modes.
- Integrated article output into `p4-full-audit` and `reports/p4-controller-audit-report.html`.
- Added CLI and script option: `--article-runtime-mode mock|llm`.
- Added schema, guardrail, and P4 full-chain tests for article output.

Latest validation:

- Real LLM article run: `article_runtime_mode=llm`, `article_status=completed`.
- Latest run ids:
  - `p2_radar_run_id=radar-20260521101515-8edd1c`
  - `p3_run_id=p3-20260521101515-e62105`
  - `evidence_pack_id=p4-pack-20260521101517-0e4f83`
  - `debate_id=debate-687a1c1a4296`
  - `judge_synthesis_id=judge-586f03691e22`
  - `adversarial_review_id=review-3760ab0360bc`
  - `snapshot_id=snapshot-7a65e3cfef84`
- HTML refreshed:
  - `reports/p1-c22-真实数据全链路验收报告.html`
  - `reports/p2-radar-quality-report.html`
  - `reports/p3-algorithm-audit-report.html`
  - `reports/p4-controller-audit-report.html`
- `p4-dod-check`: `status=passed`, `passed_count=12`, `failed_count=0`.
- Tests: `backend/tests/test_p4_article_writer.py`, `test_p4_full_chain_audit.py`, `test_p4_agent_runtime.py`, `test_p4_prompts.py`, `test_p4_schemas.py` all passed.

## 所属 Phase

P4 Agent 推理与总控融合 / P4-C16 审计 HTML / P5 Dashboard / P6 回放

## 背景

当前 `reports/p4-controller-audit-report.html` 已经能展示 P1/P2/P3/P4 run contract、Evidence Pack、4 个分析师、交叉质询、主裁判、反方审查和 Final Controller JSON。

但目前“人类可读”部分仍然主要是模板拼接，读起来接近 JSON 解释器输出，不像真正面向人的分析文章。下一步需要在现有结构化 JSON、Evidence Pack、history 和 final controller 基础上，新增提示词驱动的中文文章生成能力。

本卡不改变 P1/P2/P3/P8 数据链，不绕过 P4-C03/P4-C04/P4-C09 约束，只在 P4-C16 审计 HTML 中增加文章化表达层。

## 目标

新增 P4 中文文章生成器：

- 基于 frozen Evidence Pack、analyst outputs、judge synthesis、adversarial review、final controller JSON 生成中文长文。
- 4 个分析师分别输出面向人的中文小结，而不是 JSON 字段堆叠。
- 最终观察建议输出完整文章，字数可以较多，结构清晰，适合人工阅读和 P5/P6 复用。
- 所有文章段落必须引用 `evidence_id + data`，包括 `metric_id / source_id / value / quality_score / source_run_id`。
- 必须引用 `analyst_history`，说明历史观点、连续性、变化或缺失。
- 文章必须保留 state machine、run_mode integrity、event window、adversarial review 等约束。
- 禁止输出交易建议，不允许开仓、平仓、止损、止盈、仓位、杠杆等内容。

## 输入

- `evidence_packs`
- `evidence_items`
- `llm_model_votes`
- `llm_challenges`
- `judge_syntheses.payload`
- `adversarial_reviews`
- `dashboard_snapshots.payload.final_controller_json`
- P4-C16 full audit context

## 输出

- 文章生成 Prompt 模板。
- 结构化中文文章输出 Schema。
- P4 full audit 中新增中文文章生成步骤。
- `reports/p4-controller-audit-report.html` 新增真正人类可读的中文文章区块：
  - `四位分析师中文文章`
  - `主裁判与反方审查总结`
  - `最终观察建议文章`
  - `证据引用索引`
- 必要测试，确保文章中包含 evidence 引用、history 引用、状态约束，且不包含交易建议敏感词。

## 建议实现范围

### 1. Prompt 模板

新增 `onlybtc.p4.article_prompts` 或复用 `p4.prompts`：

- `build_analyst_article_prompt(analyst_context)`
- `build_final_observation_article_prompt(controller_context)`

Prompt 必须明确：

- 只能使用输入 JSON 中的事实。
- 每个判断必须附至少一个 `evidence_id`。
- 写作语言为中文。
- 用“观察 / 风险 / 证据 / 历史变化 / 仍需关注”表达，不得给交易动作。

### 2. 文章输出 Schema

新增或扩展 P4 schema：

- `AnalystReadableArticle`
- `FinalObservationArticle`
- `EvidenceCitation`

字段建议：

- `title`
- `summary`
- `sections`
- `evidence_citations`
- `history_references`
- `state_constraints`
- `data_quality_notes`
- `prohibited_advice_check`

### 3. Runtime 策略

第一阶段可以用 deterministic/mock writer 生成中文文章，保证测试稳定。

第二阶段再允许接入真实 LLM runtime：

- mock writer 和真实 LLM 必须共用同一个 prompt/schema/guardrail。
- 真实 LLM 输出必须通过 schema 校验。
- guardrail 必须拦截无 evidence 的结论和交易建议。

### 4. P4-C16 审计 HTML 集成

在 `p4_full_chain.py` 中新增文章生成上下文：

- 每位分析师对应自己的 Radar module evidence slice。
- 每位分析师对应自己的 `analyst_history` evidence。
- Final article 消费 final controller JSON、judge、review、state constraints、四位分析师文章。

HTML 中文章区块必须放在表格和 JSON 之前，便于人先读结论，再查证据。

## 验收标准

- `p4-full-audit` 后 P1/P2/P3/P4 四份 HTML 均刷新。
- P4 HTML 中存在真正中文文章，不是 JSON 字段拼接。
- 4 个分析师文章均包含：
  - 中文标题；
  - 中文结论；
  - evidence 引用；
  - data 引用；
  - history 引用。
- 最终观察建议文章包含：
  - 总控状态；
  - 主裁判判断；
  - 反方审查结果；
  - 状态机约束；
  - 4 个分析师分歧或一致性；
  - evidence citation index。
- DoD 继续通过：`p4-dod-check` passed。
- P4 测试组通过。
- 全后端测试通过。
- Ruff 通过。

## 不做

- 不接入 P5/P9 页面开发。
- 不改变 P1/P2/P3 指标计算。
- 不把文章输出作为新的交易建议。
- 不允许 LLM 自行补充外部事实。

## 依赖任务

P4-C01、P4-C02、P4-C05、P4-C06、P4-C08、P4-C09、P4-C10、P4-C15、P4-C16

## 执行顺序建议

1. 先做 deterministic/mock 中文文章 writer。
2. 接入 P4-C16 HTML。
3. 增加文章 schema 与 guardrail 测试。
4. 跑 `p4-full-audit --run-mode live --runtime-mode mock`。
5. 再评估是否用真实 LLM runtime 生成文章。
