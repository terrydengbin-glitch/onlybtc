# P4-C16 P4 Agent 全链条重跑与审计 HTML

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 2026-05-21 执行记录

已实现 P4 Agent 全链条重跑与审计 HTML：

- 新增 `onlybtc.audit.p4_full_chain.run_p4_full_chain_audit`。
- 新增 CLI：`p4-full-audit`。
- 全链条顺序：P1/P2/P3 full audit -> P4-C05 -> P4-C06 -> P4-C07 -> P4-C08 -> P4-C09 -> P4-C10。
- 输出 `reports/p4-controller-audit-report.html`。
- P4 HTML 展示 run contract、上游 HTML、Evidence Pack coverage、Analyst matrix、votes、cross-exam、baseline、state machine、judge、adversarial review、final controller JSON 和 snapshot modules。

真实 CLI 验证：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit `
  --no-collect-live --run-mode mock --runtime-mode mock
```

结果：

- P1 HTML：`reports/p1-c22-真实数据全链路验收报告.html`
- P2 HTML：`reports/p2-radar-quality-report.html`
- P3 HTML：`reports/p3-algorithm-audit-report.html`
- P4 HTML：`reports/p4-controller-audit-report.html`
- `p2_radar_run_id=radar-20260521092334-9e1ce8`
- `p3_run_id=p3-20260521092334-87c13c`
- `evidence_pack_id=p4-pack-20260521092336-8615f4`
- `debate_id=debate-d60e56a30aa4`
- `judge_synthesis_id=judge-5ddb62716286`
- `adversarial_review_id=review-8f882fabb79c`
- `snapshot_id=snapshot-55cf48e5c216`

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p4_full_chain_audit.py
```

结果：`1 passed`。

## 2026-05-21 人类可读结论增强

本轮增量优化 P4-C16 审计 HTML：

- 4 个分析师必须分别输出人类可读结论，而不只展示 vote/confidence 表格。
- 每个分析师结论必须引用自己负责 Radar 板块内的 `evidence_id + data`。
- 每个分析师结论必须引用自己的 `analyst_history`，说明历史是否可用，以及本轮观点是否延续或变化。
- 最终观察建议必须输出一篇较详细的文章式总结，引用：
  - final controller 状态；
  - judge / adversarial review；
  - state machine constraints；
  - analyst evidence；
  - history evidence；
  - `evidence_id`、`metric_id`、`source_id`、`value`、`quality_score`。
- 文章和分析师结论仍禁止交易建议，不得输出开仓、平仓、止损、止盈、仓位、杠杆等内容。

## 2026-05-21 中文审计输出增强

本轮继续优化 P4-C16：

- P4 审计 HTML 的人类可读分析师结论必须使用中文输出。
- 最终观察建议文章必须使用中文输出。
- HTML 的核心标题与业务字段尽量中文化，便于人工复盘。
- 真实全链条执行后必须同时刷新 P1/P2/P3/P4 四份 HTML。

## 所属 Phase

P4 Agent 推理与总控融合 / P1-P2-P3-P8 全链条审计 / P5 Dashboard / P6 回放

## 背景

P1-C22、P2-C19、P3-C11 已分别具备独立审计 HTML。P4 Agent 化后，也必须具备同等可观测能力，证明本轮总控判断来自同一 run 的冻结证据、结构化分析、交叉质询、裁判合成和反方审查。

P4 审计不能只展示最终结论，必须展示每一步如何消费证据、如何处理分歧、哪些约束降低了 confidence。

## 业务目标

新增 P4 全链条重跑入口：

```text
P1-C22 full collection/report
  -> P2-C19 radar/report
  -> P3-C11 algorithm/report
  -> P4-C05 evidence pack
  -> P4-C06 analyst agents
  -> P4-C07 cross examination
  -> P4-C08 judge synthesis
  -> P4-C09 adversarial review
  -> P4-C10 final controller JSON
  -> reports/p4-controller-audit-report.html
```

## 审计 HTML 必须展示

- 本轮 `collect_run_id / p2_radar_run_id / p3_run_id / evidence_pack_id / debate_id / judge_synthesis_id`。
- P1/P2/P3 HTML 路径。
- Evidence Pack coverage：
  - Radar modules consumed count。
  - Radar feature items consumed count。
  - signed event metrics count。
  - uncovered metric count。
- 4 个 analyst coverage matrix。
- 每个 analyst 的输入 evidence 数量、输出 vote、confidence、missing evidence、key claims。
- analyst_history 是否可用，以及本轮观点变化。
- 交叉质询 challenge/revision 明细。
- 规则 baseline、状态机 hard constraints、P3 invalidation 约束。
- Judge Agent 采用/拒绝的观点、minority objection、confidence discount。
- 反方审查结果和 publish_allowed。
- 最终总控 JSON。

## DoD

- 运行一次 P4 全链条命令后，同时能看到 P1/P2/P3/P4 四份 HTML。
- P4 HTML 能证明所有最终 claim 都可追溯到 `evidence_id`。
- 若 P4 缺少任一上游 run 或 Evidence Pack coverage 不完整，审计 HTML 必须显式标红。
- mock runtime 与真实 OpenAI runtime 均可复用同一审计模板。
- P4-C16 通过前，不进入 P5/P9 的真实总控页面/API开发。
