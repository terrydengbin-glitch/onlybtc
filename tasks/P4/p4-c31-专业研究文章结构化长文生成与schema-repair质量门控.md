# P4-C31 专业研究文章结构化长文生成与 Schema Repair 质量门控

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态
LEGACY

## Legacy Closure（2026-06-23）

本卡属于旧 P4 Agent / CrossExam / Judge controller 链路。P4.5 已通过 Radar Scored Analyst Writer、P4.5 Report v2、P6 article replay / DoD 等主线完成当前生产文章与回放契约。

后续除非明确要求维护旧 P4，否则不再按本卡推进生产实现；旧 P4 仅保留历史回看、调试和人工对比用途。新文章质量、Evidence Pack、History Replay、DoD 验收应继续走 P4.5 / P6 主线。

## 所属 Phase
P4 Agent 推理与总控融合 / P5 Dashboard 可读报告前置

## 背景
P4-C29 已经接入趋势洞察字段，P4-C30 已经修复 provider-required 缺口和事件窗口 monitor 的硬阻断语义。但最新 `reports/p4-controller-audit-report.html` 仍然不像专业研究文章：

- 主文章标题直接变成“1. 宏观环境：权益偏强但金融压力边际收紧”，不像完整研究报告标题。
- `summary`、`executive_summary`、`market_state`、`final_observation` 多处重复同一段宏观文字。
- 4 个分析师文章里出现 `Runtime schema repair applied`，说明 LLM 返回了局部 section 或不完整 JSON，被 runtime 自动补字段。
- 正文大量罗列 evidence_id，但缺少“为什么这些数据组合成趋势判断”的推理链。
- 最终报告没有稳定输出多层结构：核心结论、趋势变化、驱动拆解、冲突权重、风险情景、验证/反证条件、未来观察路径。
- Judge 阶段仍出现 fallback：`judge_agent: guardrail_failed: Unknown evidence ids...`，导致最终文章上下文质量被削弱。

这说明问题已经从“有没有 LLM”进入“LLM 文章契约是否足够专业、repair 是否过度容忍低质量输出”的阶段。

## 当前根因

### 1. Schema repair 过度宽容
当前 Article Runtime 即使 LLM 只返回一个局部 section，也会自动 wrap 成完整 `AnalystReadableArticle` 或 `FinalObservationArticle`。这样虽然 `article_status=completed`，但正文质量可能很低。

### 2. Prompt 没有强制“长文结构”
Prompt 要求填字段，但没有强约束：

- 每个字段必须承担不同功能。
- final article 必须综合 4 个分析师，而不是只复述宏观段落。
- 必须写“数据变化 -> 机制解释 -> 趋势含义 -> 验证条件”。
- 必须有足够长度和章节完整度。

### 3. Article Context 没有给足“专业写作脚手架”
当前 context 有 evidence 和 trend_frame，但缺少面向文章生成的二次整理：

- `market_thesis`
- `trend_change_map`
- `driver_hierarchy`
- `cross_module_conflicts`
- `sensitivity_watchlist`
- `scenario_tree`
- `what_changed_since_last_run`
- `data_quality_boundary`

### 4. HTML 渲染重复字段
HTML 按字段顺序逐个输出，若 LLM 把同一段塞进多个字段，页面会重复。需要做字段去重和 section 分层。

### 5. Judge fallback 污染最终上下文
本轮 `judge_agent` 因 unknown evidence ids guardrail fallback。虽然文章 writer 成功，但最终文章拿到的 judge synthesis 不是完全 LLM 结果，专业综合能力下降。

## 任务目标
把 P4 文章从“可读 evidence 摘要”升级为“专业研究文章”：

1. 最终文章必须像完整研究报告，而不是字段拼接。
2. 4 个分析师文章必须结合本模块数据，解释趋势变化和机制。
3. LLM 局部输出不能被静默 repair 成 completed。
4. Schema repair 只能修格式，不能掩盖内容质量不足。
5. Judge unknown evidence id fallback 需要修复或降级为可恢复 repair。
6. HTML 正文要去重、分层，并把 appendix 放到正文之后。

## 实施范围

### 1. Article Quality Gate
新增文章质量门控：

- `summary`、`executive_summary`、`market_state`、`final_observation` 不得高度重复。
- final article 必须包含至少 6 个有效章节。
- analyst article 必须包含趋势洞察、关键数据、冲突/反证、观察清单。
- final article 必须引用 4 个分析师观点。
- 出现 `Runtime schema repair applied` 时不能直接判定高质量完成。
- 局部 section wrap repair 应标记 `completed_with_quality_warnings` 或失败重试。

### 2. Professional Research Prompt
重写文章 prompt，要求中文专业研究结构：

1. 核心结论：一句话说明当前 BTC 趋势、强度和最重要变化。
2. 数据总览：说明本轮最关键的 5-8 个数据变化。
3. 机制推理：解释宏观、流动性、微观结构、链上之间如何传导。
4. 分歧与冲突：解释多空证据冲突，给权重排序。
5. 敏感信号：说明哪些指标最容易先变。
6. 情景树：看涨、看跌、中性震荡分别需要什么触发。
7. 反证条件：哪些数据会推翻当前判断。
8. 观察路径：24h / 3d / 7d 具体看什么。
9. 数据边界：说明低质量、fallback、provider-required 的影响。

### 3. Article Context Builder
在 Article Writer 前新增研究写作上下文：

- `market_thesis`
- `driver_hierarchy`
- `cross_module_conflicts`
- `trend_change_map`
- `sensitive_signal_table`
- `scenario_tree`
- `invalidation_table`
- `analyst_consensus_delta`

这些结构由 deterministic code 从 evidence、analyst articles、judge、review 中整理，LLM 负责写作和推理表达。

### 4. Schema 扩展或约束
强化 `FinalObservationArticle`：

- `title` 必须是研究报告标题，不能是章节标题。
- `summary` 必须是综合摘要，不能只描述单一模块。
- `sections` 至少覆盖宏观、流动性、微观结构、链上、冲突、情景、观察路径。
- `evidence_citations` 与正文关键判断必须对应。

### 5. HTML 去重与分层
HTML 渲染时：

- 对重复字段做 hash 去重。
- 正文只展示研究字段和有效 sections。
- `data_source_appendix` 单独折叠/置后。
- `Runtime schema repair applied` 只放 Audit Appendix，不放正文。

### 6. Judge Evidence Repair
修复 `judge_agent` unknown evidence ids：

- 对 judge 输出的 evidence_ids 做 allowed set 过滤或 repair。
- 如果 Judge 引用了跨分析师 evidence，应确保 prompt allowed_evidence_ids 包含全 pack evidence。
- fallback 不应轻易污染最终报告；需要区分 `judge_repaired` 和 `judge_fallback`。

## 验收标准

- P4 主文章不再出现多个字段重复同一段。
- P4 主文章标题是完整研究报告标题，不是章节标题。
- 4 个分析师文章不再在正文显示 `Runtime schema repair applied`。
- final article 至少 6 个有效章节，覆盖宏观、流动性、微观结构、链上、冲突和情景。
- 文章能明确回答：
  - 当前趋势是什么？
  - 哪些数据正在变化？
  - 为什么这些变化重要？
  - 哪些信号最敏感？
  - 什么条件会确认或推翻判断？
- Judge 阶段不再因 allowed evidence id 范围过窄触发 fallback。
- P4 DoD 增加文章质量门控并通过。

## 验证命令
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

## 依赖
P4-C29, P4-C30
