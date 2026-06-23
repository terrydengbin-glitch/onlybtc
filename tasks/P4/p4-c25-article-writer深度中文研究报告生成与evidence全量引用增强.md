# P4-C25 Article Writer 深度中文研究报告生成与 Evidence 全量引用增强

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 Agent 推理与总控融合 / P5 Dashboard 可读报告前置

## 任务目标

升级 P4 Article Writer，让四个分析师文章与最终观察文章从“短审计摘要”升级为“深度中文研究报告”，并确保文章生成能够消费当前 Evidence Pack 的全量证据、数据、历史记录、交叉质询、Revision、Judge synthesis 与 Adversarial Review。

目标不是让 LLM 自由发挥，而是让 LLM 基于完整 evidence + data 写出人类可读、证据充分、结构完整的研究报告。

## 背景与发现

2026-05-21 检查 `reports/p4-controller-audit-report.html` 后确认：

- Article Writer 已经接入 LLM Agent：
  - `article_runtime_mode=llm`
  - `article_status=completed`
  - `article_writer_agent`
  - `provider=deepseek`
  - `model=deepseek-reasoner`
  - `fallback=false`
- 文章引用的 evidence 全部属于当前 pack，没有串包。
- 但 evidence 覆盖明显不足：

```text
pack_id=p4-pack-20260521125600-174b29
pack_total=126
available=122
article_unique_evidence_ids=45
article_ids_in_pack=45
article_ids_not_in_pack=0
pack_ids_not_in_article_count=81
coverage_total_pct=0.357
coverage_available_pct=0.336
```

四个分析师 vote evidence 被文章引用覆盖也偏低：

```text
macro_event_analyst: vote_evidence=35, used_in_article=10, coverage=0.286
liquidity_flow_analyst: vote_evidence=20, used_in_article=6, coverage=0.300
leverage_microstructure_analyst: vote_evidence=21, used_in_article=7, coverage=0.333
onchain_market_structure_analyst: vote_evidence=20, used_in_article=5, coverage=0.250
```

代码根因：

- `p4_full_chain._analyst_narratives()` 当前每个分析师只取 `top_evidence = _top_evidence(..., limit=5)`。
- `article_writer._analyst_article_context()` 只把 `top_evidence` 传给 LLM。
- `_mock_analyst_article()` 的 `evidence_citations` 也只取 `top_evidence[:5]`。
- 最终文章主要消费 analyst articles，而不是完整 Evidence Pack、Challenge、Revision、Judge 与 Adversarial Review。

因此当前问题不是“没调用 LLM”，而是“LLM Article Agent 没有拿到足够完整的 evidence 上下文，prompt 也偏短审计摘要”。

## 业务原则

- 文章必须基于当前 frozen Evidence Pack，不允许新增外部事实。
- 文章可以精炼，但不能只使用 top 5 evidence 代表整个分析师模块。
- 每个分析师至少应覆盖：
  - 自己负责的全部 Radar modules
  - primary_signal
  - supporting/risk/event/quality/audit context
  - historical analyst record
  - fallback / data quality / run scope
  - challenge / revision 中与自己相关的内容
- 最终观察文章必须覆盖：
  - 四个分析师观点
  - 主要一致点与分歧点
  - 交叉质询与修正结果
  - Judge synthesis 接受/拒绝/少数意见
  - Adversarial Review gate
  - Final Controller publish scope / blocked_by
  - Data Quality vs Production Readiness
- 引用必须使用当前 pack 的 `evidence_id`，不得串包。
- 深度文章仍然不能输出交易建议、仓位、杠杆、止损、买卖指令。

## 实施范围

1. Evidence Pack 全量文章上下文
   - `analyst_narratives` 增加：
     - `all_evidence`
     - `evidence_by_module`
     - `primary_signal_evidence`
     - `context_evidence`
     - `risk_quality_event_evidence`
     - `missing_or_provider_required_evidence`
   - 保留 `top_evidence`，但只能作为摘要，不再作为唯一输入。

2. Article Writer prompt 升级
   - Analyst article prompt 要求：
     - 每个负责 module 至少有一段。
     - 每段必须引用 evidence/data。
     - 必须解释当前值、方向、质量、历史变化、fallback/run scope。
   - Final article prompt 要求：
     - 生成完整研究报告。
     - 包含摘要、模块分歧、证据链、历史延续、反方质询、门控结论。
     - 明确“观察级/发布门控”。

3. Challenge / Revision / Judge / Review 注入文章上下文
   - Article context 增加：
     - `challenge_rows`
     - `revision_rows`
     - `judge_claims`
     - `minority_objections`
     - `adversarial_findings`
   - 每个分析师文章只看到与自己相关的 challenge/revision。
   - Final article 看到完整审议链。

4. Evidence 引用覆盖门槛
   - Analyst article：
     - 至少覆盖该分析师 vote evidence 的 70%，或每个 module 至少 3 条核心证据。
   - Final article：
     - 至少覆盖四个分析师文章引用 evidence 的并集。
     - 必须引用 P3 event evidence、history evidence、revision evidence。
   - HTML / DoD 输出 coverage matrix。

5. HTML 展示升级
   - 新增 `Article Evidence Coverage` 区块：
     - pack evidence count
     - article evidence count
     - analyst vote evidence coverage
     - missing high-quality evidence table
   - 新增“完整研究报告”区块，与 JSON appendix 分离。
   - 保留 runtime trace，显示是否 LLM/fallback。

6. 成本与长度控制
   - 引入分层上下文：
     - per analyst full context
     - final compressed but evidence-rich context
   - 对 evidence 列表按 module/role 分组，而不是盲目塞长列表。
   - 保留 token budget summary。

## 输入

- `EvidenceItem` 全量 pack
- `llm_model_votes`
- `llm_challenges`
- `llm_revisions`
- `judge_syntheses`
- `adversarial_reviews`
- Final Controller JSON
- Analyst history evidence
- P1/P2/P3 run scope 与 quality metadata

## 输出

- 深度中文 Analyst Articles
- 深度中文 Final Observation Article
- Article Evidence Coverage Matrix
- P4 HTML 完整研究报告区块
- P4 DoD 新增文章覆盖检查

## 验收标准

- Article Writer runtime 仍为 `llm`，且 `fallback=false` 时文章必须显著长于短摘要。
- 文章引用 evidence 全部属于当前 pack。
- Analyst article 覆盖每个分析师负责的所有 Radar modules。
- 每个分析师文章覆盖其 vote evidence 的比例达到目标，或明确列出未覆盖原因。
- Final article 覆盖：
  - 四个分析师结论
  - challenge/revision
  - judge minority objections
  - adversarial gate
  - final publish scope
- HTML 显示 article evidence coverage。
- 不输出交易建议、仓位、杠杆、止损或买卖指令。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_article_writer.py backend/tests/test_p4_full_chain_audit.py backend/tests/test_p4_dod.py -q
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode mock --article-runtime-mode mock
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

## 依赖任务

P4-C17、P4-C18、P4-C20、P4-C21、P4-C22、P4-C23、P4-C24、P3-C15、P5-C08、P5-C11

## 执行记录

2026-05-21 已完成。

- `Article Writer` 输入从 `top_evidence` 扩展为 `all_evidence`、`evidence_by_module` 与 full evidence index。
- Analyst article 与 final article 增加 evidence coverage 后处理，确保当前 pack 证据可追踪。
- P4 HTML 增加 `Article Evidence Coverage` 区块。
- P4 DoD 增加 `article_evidence_coverage_complete` 检查，并将交易术语检查收敛到面向发布的字段，避免 runtime error 内部日志误伤。
- 最新 live+LLM 报告：`reports/p4-controller-audit-report.html`
  - `article_runtime_mode=llm`
  - `article_status=completed`
  - `article_writer_agent provider=deepseek model=deepseek-reasoner`
  - `coverage_pct=1.0`
  - P4 DoD：18/18 passed
- 验证：
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q` -> 102 passed
  - `.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests` -> passed
  - `.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check` -> passed

## 备注

本卡不改变 P1/P2/P3/P4 的决策逻辑，只增强文章生成的证据输入、写作深度、引用覆盖与 HTML 可读性。LLM 仍必须服从 Final Controller 与 State Machine，不得覆盖 hard constraints。
