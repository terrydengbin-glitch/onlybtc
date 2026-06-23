# P4-C14 LLM 分析师历史记忆 SQLite 持久化与本轮调用契约

> Legacy note: This task belongs to the old P4 Agent/CrossExam/Judge controller chain. After P4.5 is established, P4 is kept only for history, review, and debugging; new production work should use P3-C16 + P4.5 Radar Scored Analyst Writer unless legacy P4 maintenance is explicitly requested.






## 状态

DONE

## 所属 Phase

P4 LLM 推理与总控融合 / P8 SQLite / P6 历史回放与评分 / P5 LLM Debate 可视化

## 背景

P4-C05 Evidence Pack 生成器已经可以冻结同一 run 的全量 Radar features 与 P3 event evidence。但如果 4 个 LLM 分析师每次只看本轮数据，而无法读取自己之前的判断，就会出现“断层思考”：

- 上一轮已经关注的风险，本轮无法知道是否延续、缓和或加剧。
- 上一轮模型给出的 vote/confidence，本轮无法比较变化。
- 交叉质询与主裁判无法判断某个分析师是否频繁摇摆或忽略历史反证。

因此需要为 4 个分析师建立 SQLite 历史记忆契约，并确保本轮 Evidence Pack 可以正确调用。

## 业务目标

每次 P4 运行时：

```text
previous llm_model_votes / llm_debates
  -> analyst_history evidence items
  -> current Evidence Pack
  -> analyst-specific prompt input
  -> new llm_model_votes
  -> next run memory
```

目标不是让历史观点覆盖本轮数据，而是让 LLM：

- 知道自己上次判断是什么。
- 知道上次 confidence 和本轮是否需要调整。
- 能解释观点变化：延续、修正、反转或降级。
- 能识别过去关注点是否被本轮数据验证或否定。

## SQLite 契约

### 历史来源表

使用现有 P8 表：

- `llm_debates`
- `llm_model_votes`
- `llm_rounds`
- `llm_challenges`
- `judge_syntheses`
- `adversarial_reviews`

本阶段优先读取：

```yaml
llm_model_votes:
  debate_id
  model_name
  vote
  confidence
  evidence_ids
  changed
  created_at

llm_debates:
  debate_id
  run_id
  consensus_score
  disagreement_level
  final_state
  publish_allowed
```

### 本轮写入要求

后续 P4-C06/P4-C07/P4-C08 执行真实或 mock LLM 后，必须把每个分析师本轮输出写回：

```yaml
llm_model_votes:
  debate_id: current_debate_id
  model_name: macro_event_analyst | liquidity_flow_analyst | leverage_microstructure_analyst | onchain_market_structure_analyst
  vote
  confidence
  evidence_ids
  changed
```

这样下一轮 P4-C05 可以从 SQLite 正确读取历史。

## Evidence Pack 调用契约

P4-C05 必须为每个分析师生成 1 条 `analyst_history` evidence item：

```yaml
source_layer: analyst_history
assigned_analyst
history_available: true | false
history_limit
history:
  - debate_id
    run_id
    vote
    confidence
    evidence_ids
    changed
    final_state
    consensus_score
    disagreement_level
    created_at
```

如果没有历史记录，也必须生成 cold-start evidence：

```yaml
history_available: false
history: []
claim: "{analyst} has no prior persisted vote; start with explicit cold-start context."
```

## Prompt 使用边界

分析师 prompt 必须把历史记忆作为“分析连续性上下文”，而不是主证据：

- 历史 vote 可以帮助说明观点变化，但不能覆盖本轮 P2/P3 evidence。
- 如果历史观点与本轮数据冲突，必须以本轮 frozen Evidence Pack 为准。
- 如果本轮数据不足，应引用历史作为观察线索，并降低 confidence。
- 不允许凭历史观点输出交易建议。

## 当前实现结果

2026-05-21 已完成：

- `onlybtc.p4.evidence_pack.build_p4_evidence_pack()` 已从 SQLite `llm_model_votes` + `llm_debates` 读取分析师历史。
- 每个 Evidence Pack 固定生成 4 条 `analyst_history` evidence item。
- 无历史时生成 cold-start evidence，保证本轮 prompt 能明确知道“历史为空”。
- 单测 `backend/tests/test_p4_evidence_pack.py` 已验证：
  - 历史 vote 写入 SQLite 后；
  - 本轮 P4 Evidence Pack 能读取；
  - `macro_event_analyst` 的历史 vote 能进入 `analyst_history` evidence。

真实库当前生成结果：

- `pack_id=p4-pack-20260521074431-c5e25a`
- `analyst_history_evidence_count=4`
- `evidence_item_count=126`

## DoD

- 每个分析师历史记忆来自 SQLite，而不是内存变量或 prompt 临时拼接。
- 每个 Evidence Pack 必须生成 4 条 `analyst_history` evidence。
- 本轮 P4 prompt input 只能读取当前 Evidence Pack 中的 `analyst_history`，不能直接查询最新数据库绕过冻结。
- P4-C06/P4-C07/P4-C08 后续必须把本轮分析师输出写回 `llm_model_votes`。
- 历史记忆只能辅助连续性分析，不能覆盖本轮证据。
- 测试覆盖历史写入 SQLite 后被本轮 Evidence Pack 正确读取。
