# P3-C36 / Kline trend_state 优先展示与 module_effective_bias 取分修复

## 状态

DONE

## 背景

最新一轮审计中，`kline_orderflow` 输出：

```text
module_effective_score = 0.1505
module_effective_direction = bullish
trend_state = neutral_wait_confirm
module_effective_bias = neutral
```

其中 `module_effective_direction = bullish` 在分数上可以成立，但 `trend_state = neutral_wait_confirm` 才是 Kline 模块的主语义：短线有支撑，但量价结构尚未确认趋势。

同时 `module_effective_bias = neutral` 与 `module_effective_score = 0.1505` 不一致，说明 Kline semantic profile 在生成 `module_effective_bias` 时没有拿到真实 `module_effective_score`，或取分字段顺序错误。

## 目标

1. Kline 模块展示主语义优先使用 `trend_state / kline_trend_state`。
2. 当 `trend_state = neutral_wait_confirm` 时，不允许文章或前端把 Kline 写成“短线 bullish confirmed”。
3. 修复 `module_effective_bias` 取分逻辑，使其基于真实 `module_effective_score`。
4. `module_effective_score = 0.1505` 时，`module_effective_bias` 应输出 `support` 或 `mild_support`，不能是 `neutral`。
5. 保留 `module_effective_direction` 作为数值方向字段，但不得作为 Kline 主展示标签。

## 不改范围

- 不修改 P1 Kline 派生指标。
- 不修改 P2 指标注册。
- 不修改 Kline composite 打分公式。
- 不修改 P4.5 final_view 聚合公式。
- 不修改前端布局，只保证 API 字段语义正确。

## 规则

### Kline 主展示优先级

```text
kline_display_state =
  kline_trend_state
  -> trend_state
  -> module_state
  -> module_effective_bias
  -> module_effective_direction
```

### Kline 文案规则

```text
if trend_state == neutral_wait_confirm and module_effective_score > 0:
    wording = "短线有支撑，但结构仍待确认"

if trend_state == bullish_confirmation:
    wording = "短线量价确认偏多"

if trend_state == bearish_pressure:
    wording = "短线放量下跌确认压力"
```

### module_effective_bias 取分

```text
module_effective_bias must use module_effective_score from scored module aggregation.

if abs(module_effective_score) < 0.05:
    neutral
elif 0.05 <= abs(module_effective_score) < 0.12:
    mild_support / mild_pressure
else:
    support / pressure
```

## 验收样例

输入：

```json
{
  "radar_module": "kline_orderflow",
  "module_effective_score": 0.1505,
  "module_effective_direction": "bullish",
  "trend_state": "neutral_wait_confirm"
}
```

期望：

```json
{
  "module_effective_bias": "support",
  "display_state": "neutral_wait_confirm",
  "display_summary": "短线有支撑，但结构仍待确认"
}
```

## DoD

- [ ] `module_effective_bias` 与 `module_effective_score` 一致。
- [ ] `module_effective_score = 0.1505` 不再输出 `module_effective_bias = neutral`。
- [ ] `trend_state = neutral_wait_confirm` 时，Kline 主展示不使用 `module_effective_direction = bullish`。
- [ ] P4.5 / Dashboard 文案能表达“短线有支撑，但等待确认”。
- [ ] 增加回归测试覆盖本轮样例。

## 关联

P3-C29, P3-C31, P3-C35, P5-C38

## Completion Note

- Done: P3 module aggregation now exposes `module_effective_score` to semantic profile generation.
- Done: Kline semantic profile now derives `module_effective_bias` from the real effective score.
- Done: Added `display_state` and `display_summary` so `neutral_wait_confirm` remains the primary Kline display state even when numeric effective direction is bullish.
- Verified: P3 pipeline, P4.5 writer/html, and P45 dashboard API regression tests passed.
