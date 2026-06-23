# P4-C27 Research Article Writer 两阶段中文研究报告生成器

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态
DONE

## 所属 Phase

P4 Agent 推理与总控融合 / P5 Dashboard 可读报告前置

## 背景

P4-C25 解决了 Article Writer 证据覆盖不足的问题，但当前文章仍偏“证据罗列 + 审计说明”，还不是高价值研究报告。真正有价值的文章应该解释状态、驱动、冲突、变化和观察重点，而不是把所有 evidence 平铺进正文。

## 任务目标

把 Article Writer 从“一步直接写文章”升级为“两阶段研究写作”：

1. 先把每个分析师的全量 evidence 压缩成结构化研究要点卡。
2. 再由最终写作 Agent 基于研究要点卡、Judge、Revision、Adversarial Review 和 Final Controller 写出高价值中文研究报告。

## 文章必须回答的问题

- 当前 BTC 状态是什么？
- 为什么是这个状态？
- 哪些证据最关键？
- 哪些证据互相冲突？
- 相比上一轮发生了什么变化？
- 接下来观察哪些事件/指标？
- 当前为什么只能观察、不能发布，或为什么可以进入发布候选？

## 实施范围

1. 新增 Analyst Research Brief schema
   - `analyst_id`
   - `headline`
   - `core_view`
   - `key_drivers`
   - `counter_evidence`
   - `changed_from_history`
   - `watch_items`
   - `confidence_rationale`
   - `evidence_ids`

2. 新增 Final Research Article schema 或扩展现有 schema
   - `executive_summary`
   - `market_state`
   - `driver_analysis`
   - `conflict_analysis`
   - `history_delta`
   - `event_watch`
   - `quality_and_runtime`
   - `final_observation`
   - `evidence_appendix`
   - `data_source_appendix`：保留文章后方的 evidence/data/source 明细，包括 `evidence_id`、`metric_id`、`source_id`、`value`、`quality_score`、`note`，用于人工复核。

3. 两阶段写作流程
   - Stage A：四个 analyst article writer 分别生成 research brief。
   - Stage B：final article writer 读取四个 brief 与总控链路，写正式研究报告。
   - Full evidence coverage 作为 appendix，不再打断正文。
   - 数据源明细必须保留在正式文章之后，作为“数据源与证据附录”，不能删除或吞并到正文摘要里。

4. Prompt 质量要求
   - 不允许只说“中性、观察、约束”。
   - 必须做“为什么”的解释。
   - 必须写冲突证据与权重。
   - 必须引用 evidence/data/history。
   - 必须把 runtime/fallback 作为可信度说明，不作为正文主轴。

5. DoD
   - 检查最终文章包含关键章节。
   - 检查每个章节有证据引用。
   - 检查正文长度、模块覆盖、history delta、conflict analysis。
   - 检查无交易建议、无买卖指令。

## 验收标准

- 最终文章读起来像研究报告，而不是 JSON 摘要或 evidence 清单。
- 文章明确给出“状态 + 原因 + 冲突 + 变化 + 观察清单”。
- Full evidence appendix 保留但不抢正文位置。
- 文章后方保留完整数据源附录，至少展示 `evidence_id / metric / source / value / quality / note`，效果等价于当前 HTML 中的 evidence list。
- Analyst brief 与 Final article 均可在 HTML 中单独查看。
- P4 DoD 通过。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

## 依赖

P4-C25、P4-C26
