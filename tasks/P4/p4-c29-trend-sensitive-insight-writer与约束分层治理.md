# P4-C29 Trend Sensitive Insight Writer 与约束分层治理

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态
DONE

## 所属 Phase
P4 Agent 推理与总控融合 / P5 Dashboard 可读报告前置

## 背景
当前 `reports/p4-controller-audit-report.html` 已经接入 LLM Article Writer，但正文仍然偏“审计门控摘要”：大量篇幅解释 `publish_allowed=false`、`watch_only`、`fallback_used`、`event_window_publish_constraint`，而不是先回答趋势问题。

本轮检查发现，问题不只是提示词长度，而是 P4 业务链条在 `Evidence Pack -> Article Writer` 之间缺少一层趋势洞察加工：证据被直接罗列给 LLM，LLM 容易复述模块证据和约束，难以稳定输出“变化、敏感信号、冲突权重、验证条件、情景推演”。

用户明确要求：文章可以讨论仓位、杠杆仓位、风险暴露、拥挤度、资金费率、期权墙、gamma、delta 等专业市场结构概念；禁止的是直接交易指令，例如建议开仓、平仓、买入、卖出、止损价、止盈价、仓位比例等。

## 当前链条断点
```text
P1/P2/P3/P8 数据
  -> P4 Evidence Pack
  -> 4 Analyst Evidence Slice
  -> Analyst Vote / CrossExam / Judge / Adversarial
  -> deterministic analyst_conclusion
  -> Article Writer Prompt
  -> AnalystReadableArticle / FinalObservationArticle
  -> p4-controller-audit-report.html
```

断点位于：

1. `Evidence Pack -> analyst_conclusion`：只拼接 top evidence 和总控约束，没有生成趋势变化框架。
2. `analyst_conclusion -> Article Writer`：把 `blocked_by`、`watch_only`、审计状态放到正文主轴，压过趋势判断。
3. `top_evidence` 排序：当前按质量和强度排序，缺少对敏感指标、短周期指标、冲突指标、历史变化指标的优先级。
4. Schema：缺少稳定承载趋势洞察的字段，LLM 输出容易变成段落复述。
5. Guardrail：把专业市场结构术语误当成交易建议，导致文章 `completed_with_errors`，触发 fallback/repair。
6. HTML：研究正文和审计附录已分层，但正文仍展示大量修复痕迹、证据清单和约束语句。

## 任务目标
把 P4 Article Writer 从“审计合规优先”升级为“趋势敏感推理优先，审计约束分层呈现”：

1. 四个分析师文章先输出趋势洞察、敏感变化、领先信号、冲突权重、反身性风险和验证条件。
2. 最终观察文章形成中文研究报告，而不是 gate summary。
3. 发布门控、runtime、fallback、DoD、证据覆盖等信息放到“可信度说明/审计附录”，不能压倒正文。
4. 保留数据源与 evidence appendix，确保每个关键判断可以回溯到 evidence_id、metric、source、value、quality。
5. 允许专业市场结构术语，继续禁止直接交易指令。

## 实施内容

### 1. Trend Insight Frame
在 P4 文章上下文中，为每个分析师和最终文章生成结构化趋势框架：

- `trend_impulse`：当前趋势冲量，说明方向、强度、可信度。
- `marginal_change`：相对上一轮/历史上下文的边际变化。
- `sensitive_signals`：最容易领先变化的指标，如 funding、OI、taker ratio、ETF flow、stablecoin supply、VIX、DXY、event window。
- `conflict_weighting`：多空冲突里哪一侧更敏感、更可能先被验证。
- `scenario_map`：至少包含 bullish / bearish / neutral-watch 三类情景及触发条件。
- `invalidation_conditions`：哪些数据变化会推翻当前判断。
- `watch_horizon`：24h / 3d / 7d 需要观察的指标与阈值方向。

### 2. Evidence 选择优化
保留全量 appendix，但正文优先给 LLM：

- 高强度证据。
- 快速变化证据。
- 和上一轮不同的证据。
- 与主方向冲突但可能反转判断的证据。
- 事件窗口和 P3 风险证据。

### 3. Prompt 重写
Article Writer 提示词增加硬性写作顺序：

1. 先给趋势判断和最重要变化。
2. 再解释数据证据和冲突权重。
3. 再给情景地图、验证/反证条件、观察周期。
4. 最后单独说明可信度、发布约束、runtime 状态。

### 4. Schema 扩展
`AnalystReadableArticle` 与 `FinalObservationArticle` 增加字段：

- `trend_insight`
- `marginal_change`
- `sensitive_signals`
- `early_warning_signals`
- `conflict_weighting`
- `scenario_map`
- `invalidation_conditions`
- `watch_horizon`
- `confidence_explanation`
- `audit_constraints_summary`

### 5. Guardrail 分层
允许研究表达：

- 仓位、杠杆仓位、风险暴露、拥挤度、资金费率、期权墙、gamma、delta、清算压力、流动性缺口。

禁止直接指令：

- 建议开仓、建议平仓、买入、卖出、做多、做空、加仓到某比例、减仓到某比例、止损设在、止盈设在、目标价执行等。

### 6. HTML 呈现
Research Report 和 Analyst Research Briefs 先展示：

1. 趋势洞察。
2. 敏感信号。
3. 冲突权重。
4. 情景地图。
5. 验证/反证条件。
6. 可信度与约束摘要。
7. 数据源 appendix。

Audit Appendix 保留完整运行链、DoD、runtime、fallback、raw evidence。

## 验收结果

- `backend/tests` 通过：109 passed。
- `ruff check backend/src backend/tests` 通过。
- P4 全链条 LLM 审计已生成 `reports/p4-controller-audit-report.html`。
- Article Runtime：`article_runtime_mode=llm`，`status=completed`，`errors=-`。
- P4 DoD：19/19 passed。
- 文章正文已出现趋势洞察、边际变化、冲突权重、敏感信号、情景地图、反证条件和观察周期。

## 验证命令
```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

## 依赖
P4-C25, P4-C26, P4-C27, P4-C28
