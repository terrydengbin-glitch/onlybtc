# P4-C28 P4 HTML Research View 与 Audit Appendix 分层可读化

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态
DONE

## 所属 Phase

P4 Agent 推理与总控融合 / P5 Dashboard 可读报告前置

## 背景

当前 `p4-controller-audit-report.html` 同时承载正式文章、runtime trace、coverage matrix、raw JSON、fallback reason 和 DoD 审计信息。信息是完整的，但层级混在一起，导致用户第一眼看到的是审计噪音，而不是有价值的研究结论。

## 任务目标

将 P4 HTML 从“调试审计页”升级为“研究报告优先、审计 appendix 支撑”的分层页面。

## 推荐页面结构

1. Research Report
   - 最终研究报告正文
   - 当前状态卡片
   - 关键驱动
   - 冲突证据
   - 历史变化
   - 观察清单

2. Analyst Briefs
   - 四个分析师研究要点卡
   - 每个 brief 展示结论、关键证据、反向证据、历史变化

3. Decision Chain
   - Analyst vote
   - Cross-exam challenge
   - Revision result
   - Judge synthesis
   - Adversarial review
   - Final Controller gate

4. Audit Appendix
   - Evidence Coverage Matrix
   - Data Source Appendix：文章后保留 evidence list 明细，展示 `evidence_id`、`metric_id`、`source_id`、`value`、`quality_score`、`note`
   - Runtime Trace
   - Fallback / Repair / Retry Summary
   - Raw Final JSON
   - Raw Evidence list

## 实施范围

- 调整 `p4_full_chain` HTML 渲染顺序。
- 将 runtime stack trace 从正文区移到 appendix。
- coverage appendix 默认折叠或放后面。
- 正文区优先展示 final research article。
- 在 final research article 后追加“数据源与证据附录”，保留当前 evidence list 类似的逐条数据源明细。
- 增加锚点目录，便于跳转。
- 保留所有审计数据，不删除，只改变可读层级。
- 为 P5 Dashboard 后续消费准备结构化 HTML 区块 id。

## 验收标准

- 打开 HTML 第一屏能看到正式研究结论，而不是 runtime table。
- 正式文章与审计 appendix 明确分离。
- 正式文章后仍能看到完整数据源明细，包括 evidence id、metric、source、value、quality、note，便于人工复核。
- runtime/fallback 只在正文中作为短质量说明，详细错误只在 appendix。
- Article Evidence Coverage Matrix 仍保留。
- Raw JSON 仍保留。
- P4 DoD 通过。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

## 依赖

P4-C25、P4-C26、P4-C27
