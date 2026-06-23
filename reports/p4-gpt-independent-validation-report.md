# P4-C19 GPT 独立验证报告

生成时间：2026-05-21T10:51:39Z

说明：本报告由 Codex/GPT 在当前会话中直接读取 `reports/p4-gpt-independent-validation-context.json` 后进行独立推理生成。它只用于验证子线，不写回 `dashboard_snapshots`，不改变 P4 Final Controller。

## Run ID 对齐

- `collect_run_id`: `collect-20260521100506-68eb68`
- `p2_radar_run_id`: `radar-20260521103359-757537`
- `p3_run_id`: `p3-20260521103359-2cbc40`
- `evidence_pack_id`: `p4-pack-20260521103401-711b43`
- `debate_id`: `debate-d4dc22e7e5c1`
- `snapshot_id`: `snapshot-3ae5eb0bec31`
- P4 主链 runtime: `runtime_mode=llm`
- P4 runtime integrity: `llm_runtime_integrity=fallback_used`
- P4 final state: `trend_state=constrained_watch`, `risk_state=event_watch`
- P4 confidence: `0.3126`
- P4 blocked_by: `event_window_publish_constraint`, `missing_primary_signal_evidence`, `run_mode_integrity_invalidation`

## GPT 四分析师独立结论

### 1. Macro & Event Analyst

独立结论：`neutral`，建议置信度 `0.50-0.55`。

核心证据：

- `ev-401-711b43-00017`: `ofr_fsi=-2.604`，方向 `neutral`，quality `0.96`。
- `ev-401-711b43-00009`: `vix=18.06`，方向 `neutral`，quality `0.95`。
- `ev-401-711b43-00010`: `nasdaq=26270.36`，方向 `bullish`，strength `0.006`，quality `0.95`。
- `ev-401-711b43-00091`: `usdjpy=158.69`，方向 `neutral`，quality `0.95`。
- `ev-401-711b43-00092`: `jgb_10y=2.515`，方向 `neutral`，quality `0.95`。
- `ev-401-711b43-00093`: `nikkei=59804.41`，方向 `mixed`，quality `0.95`。

判断：宏观数据质量高，但方向不统一。Nasdaq 的轻微 bullish 信号太弱，不能覆盖 OFR/VIX/JPY/JGB 的中性状态，也不能绕过事件窗口约束。因此独立判断与 P4 的 `macro_event_analyst vote=neutral, confidence=0.55` 基本一致。

### 2. Liquidity & Flow Analyst

独立结论：`neutral`，建议置信度 `0.45-0.52`。

核心证据：

- `ev-401-711b43-00018`: Fed balance sheet `6728502.0`，方向 `neutral`，quality `0.95`。
- `ev-401-711b43-00019`: bank reserves `3102810.0`，方向 `neutral`，quality `0.95`。
- `ev-401-711b43-00020`: ON RRP `24.867`，方向 `mixed`，quality `0.95`。
- `ev-401-711b43-00021`: SOFR `3.51`，方向 `neutral`，quality `0.95`。
- `ev-401-711b43-00022`: TGA `807420.0`，方向 `mixed`，quality `0.95`。
- `ev-401-711b43-00041`: BTC transaction count `676439.0`，方向 `bullish`，quality `0.92`。
- `ev-401-711b43-00043`: BTC hashrate `1032197697.48`，方向 `bullish`，quality `0.92`。

判断：美元流动性主轴偏中性/混合，BTC adoption 局部偏 bullish，但无法改变流动性总判断。P4 主链中该分析师发生 provider timeout 后 fallback，最终 `vote=neutral, confidence=0.5` 是合理的。需要注意的是 fallback_used 应持续降低该分析师输出权重。

### 3. Microstructure Analyst

独立结论：`mixed`，建议置信度 `0.35-0.45`。

核心证据：

- `ev-401-711b43-00067`: taker buy/sell ratio `0.4564`，方向 `bearish`，strength `0.2`，quality `0.81`。
- `ev-401-711b43-00034`: BTC funding rate `0.00005733`，方向 `bearish`，strength `0.1147`，quality `0.81`。
- `ev-401-711b43-00035`: BTC open interest `101513.159`，方向 `bearish`，strength `0.025`，quality `0.81`。
- `ev-401-711b43-00068`: futures basis `-0.0004218799`，方向 `bullish`，strength `0.0219`，quality `0.81`。
- `ev-401-711b43-00066`: exchange spot volume `860595526.01`，方向 `bullish`，strength `0.01`，quality `0.81`。
- `ev-401-711b43-00081`: options skew `7.9028`，方向 `mixed`，quality `0.73`。

判断：短线微观结构内部分歧最明显。主动卖压和资金费率偏 bearish，但 basis/spot volume/IV/RV 又提供局部 bullish 支撑。质量分数也低于宏观和流动性证据。独立判断应是 `mixed` 而不是 `neutral`，并需要低置信度。P4 主链输出 `mixed, confidence=0.4` 符合预期。

### 4. On-chain & Market Structure Analyst

独立结论：`neutral`，但短线结构偏弱，建议置信度 `0.45-0.50`。

核心证据：

- `ev-401-711b43-00031`: BTC 1h open `77924.63`，方向 `neutral`，strength `0.287`，quality `0.96`。
- `ev-401-711b43-00030`: BTC 1h volume `277.92731`，方向 `bearish`，strength `0.25`，quality `0.96`。
- `ev-401-711b43-00029`: BTC 1h close `77633.02`，方向 `bearish`，quality `0.96`。
- `ev-401-711b43-00002`: BTC 1h close `77633.02`，方向 `bearish`，quality `0.96`。
- `ev-401-711b43-00090`: sector heat / fear-greed `29.0`，方向 `mixed`，quality `0.86`。
- `ev-401-711b43-00058`: realized price `54202.87`，方向 `neutral`，quality `0.86`。

判断：1h orderflow 偏 bearish，但它是短周期价格结构，不能单独覆盖 BTC total state / on-chain valuation 的中性背景。该分析师在真实链路中 Kimi HTTP 400 后 fallback，因此 P4 的 `neutral, confidence=0.5` 可以接受，但应保留 runtime fallback 风险。

## GPT 交叉质询

1. 对 Microstructure：`confidence=0.4` 合理，但需要说明 bearish 主信号强于 bullish 抵消项。若把 taker ratio `0.4564` 权重提高，短线风险可能被低估。

2. 对 Liquidity：美元流动性主轴中性，但 BTC adoption 局部 bullish 证据没有进入最终方向，需说明这些 adoption 证据是中长期背景，不应覆盖短线 P4 状态。

3. 对 Macro：`macro_event_analyst scope has missing_count=2` 是有效质询。即便高质量宏观数据较多，缺口仍应进入 confidence discount。

4. 对 On-chain：短线 K-line bearish 与 on-chain neutral 之间存在时间尺度冲突。P4 把它合成为 neutral 是合理，但 confidence 不应高于 0.5。

5. 对全链路 runtime：`llm_runtime_integrity=fallback_used` 是主风险。流动性 timeout、Kimi HTTP 400、cross-exam schema miss、adversarial reviewer 无 OpenAI key 都不应被静默吞掉。P4 已把它们写入 `fallback_reasons`，符合 P4-C18 预期。

## GPT 主裁判结论

- GPT 独立 trend_state: `constrained_watch`
- GPT 独立 risk_state: `event_watch`
- GPT 独立 dominant_regime: `constrained_event_watch`
- GPT 独立 consensus_level: `low`
- GPT 独立 disagreement_level: `medium`
- GPT 独立 confidence: `0.30-0.36`
- GPT 独立 publish_allowed: 仅允许审计/观察类发布，不应允许关键状态切换
- GPT 独立 blocked_by:
  - `event_window_publish_constraint`
  - `missing_primary_signal_evidence`
  - `run_mode_integrity_invalidation`
  - `llm_runtime_integrity_fallback_used`，作为附加审计风险，不一定进入原 blocked_by，但必须进入 confidence discount / report

主裁判推理：四个分析师没有形成方向性共识。宏观、流动性、链上结构偏中性，微观结构为 mixed 且低置信度。P3/state machine 的事件窗口约束和 run_mode integrity block 是硬约束，应优先于任何单个分析师方向。runtime fallback 不是市场信号，但会降低输出可信度。因此最终只能是约束观察，而不是 bullish/bearish/risk_off 的主动状态。

## P4 主链结果摘要

P4 Final Controller 输出：

- `trend_state=constrained_watch`
- `risk_state=event_watch`
- `dominant_regime=constrained_event_watch`
- `consensus_level=low`
- `disagreement_level=medium`
- `confidence=0.3126`
- `confidence_discount=0.569`
- `publish_allowed=true`
- `blocked_by=[event_window_publish_constraint, missing_primary_signal_evidence, run_mode_integrity_invalidation]`
- `runtime_mode=llm`
- `llm_runtime_integrity=fallback_used`
- `fallback_used=true`

四个 P4 分析师输出：

| 分析师 | P4 vote | P4 confidence | GPT 独立判断 | 对齐情况 |
|---|---:|---:|---|---|
| Macro & Event | neutral | 0.55 | neutral / 0.50-0.55 | 一致 |
| Liquidity & Flow | neutral | 0.50 | neutral / 0.45-0.52 | 一致，但需保留 timeout fallback 风险 |
| Microstructure | mixed | 0.40 | mixed / 0.35-0.45 | 一致 |
| On-chain & Market Structure | neutral | 0.50 | neutral / 0.45-0.50 | 一致，但需保留 Kimi 400 fallback 风险 |

## GPT vs P4 对照矩阵

| 项目 | GPT 独立推理 | P4 主链结果 | 是否符合预期 |
|---|---|---|---|
| trend_state | `constrained_watch` | `constrained_watch` | 是 |
| risk_state | `event_watch` | `event_watch` | 是 |
| dominant_regime | `constrained_event_watch` | `constrained_event_watch` | 是 |
| consensus_level | `low` | `low` | 是 |
| disagreement_level | `medium` | `medium` | 是 |
| confidence | `0.30-0.36` | `0.3126` | 是 |
| blocked_by | event window / missing primary signal / run mode integrity | 同三项 | 是 |
| runtime 风险 | 应暴露 fallback_used | `llm_runtime_integrity=fallback_used` | 是 |
| 分析师方向 | 3 neutral + 1 mixed | 3 neutral + 1 mixed | 是 |
| publish 语义 | 只应是观察/审计发布，不应状态切换 | `publish_allowed=true` 但 blocked_by 保留 | 基本符合，建议 UI 文案明确“watch-only” |

## 是否符合预期

结论：本轮 P4 主链结果整体符合预期。

理由：

1. 数据层没有形成强方向共识。宏观与流动性偏中性，链上短线偏弱但不够覆盖长期结构，微观结构 mixed。

2. P3/state machine 的硬约束足够强，尤其是 `event_window_publish_constraint`、`missing_primary_signal_evidence` 和 `run_mode_integrity_invalidation`，这些约束应优先于单个分析师的方向性信号。

3. P4 的 confidence `0.3126` 落在 GPT 独立建议区间 `0.30-0.36`，说明 confidence discount 没有明显偏离。

4. P4-C18 的 runtime 治理生效：provider timeout、Kimi 400、cross-exam schema miss、OpenAI key 缺失没有被静默吞掉，而是进入 `fallback_reasons` 和 HTML。

5. P4 没有给出交易动作式结论，而是维持观察状态，符合项目的 no-trading-advice 和审计输出定位。

## 发现的边界问题

1. `publish_allowed=true` 容易被误读。虽然 `blocked_by` 已保留，但对人类读者来说，建议后续增加 `publish_scope=watch_only/audit_only` 或在 HTML 中明确“允许审计发布，不允许关键状态发布/状态切换”。

2. `llm_runtime_integrity=fallback_used` 已暴露，但没有直接进入 `blocked_by`。这不一定是错误，因为 runtime fallback 是推理质量风险，不是市场状态风险；但它应该继续进入 confidence discount 和审计高亮。

3. Cross-exam LLM 输出 schema miss 说明 prompt 仍可继续收紧。尤其需要强制模型返回单个 `CrossExamChallenge`，不能返回包裹对象。

4. Kimi HTTP 400 需要单独排查：可能是模型名、请求体、上下文长度或 provider 参数不兼容。

## 后续建议任务

建议新增或追加任务：

1. `P4-C20 Publish Scope 与 Watch-only 语义治理`
   - 区分 `publish_allowed` 与 `critical_publish_allowed/state_transition_allowed`。
   - Final JSON 增加 `publish_scope`，例如 `audit_only`、`watch_only`、`normal`。

2. `P4-C21 Cross-exam LLM Schema Prompt 收敛`
   - 强制返回单个 `CrossExamChallenge`。
   - 对 schema miss 做二次 JSON repair。
   - 把 repeated fallback 计入 cross-exam quality score。

3. `P4-C22 Kimi Provider 兼容性修复`
   - 检查 `kimi-k2.6` 模型名、base_url、max context、response format。
   - 给 Kimi provider 加 provider-specific payload adapter。

4. `P4-C23 Runtime Fallback Confidence Discount 显式化`
   - 将 fallback_used 对 confidence 的影响显式写入 Final Controller。
   - HTML 展示 fallback 对最终 confidence 的折扣贡献。

## 最终判断

GPT 独立验证认为：P4 主链输出符合本轮 P1/P2/P3/P4 数据和约束。最终 `constrained_watch + event_watch + low consensus + medium disagreement + low confidence` 是合理结果。当前最值得优化的不是市场结论本身，而是 publish scope 文案、cross-exam schema 约束、Kimi provider 兼容性和 fallback 对 confidence 的显式折扣。
