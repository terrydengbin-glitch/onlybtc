# P3-C35 / Kline 极小 effective 方向 Deadband 与展示口径修复

## 状态

DONE

## 背景

最新一轮审计中，`kline_orderflow` 已经正确输出：

- `trend_state = neutral_wait_confirm`
- `module_state = internal_conflict`
- `risk_score` 较高，表示短线结构仍需确认

但同时存在一个展示口径问题：

- `module_effective_score = 0.0032`
- `module_effective_direction = bullish`

这个分数极小，不应被前端、P4.5 文章或 Radar Detail 展示成明确 bullish。否则会让用户误以为 Kline 已经给出偏多确认。

## 目标

1. 为 `kline_orderflow` 增加 effective direction deadband。
2. 极小正分只允许表达为 `neutral` 或 `mild_support`，不能显示为 `bullish`。
3. 保留 `trend_state = neutral_wait_confirm` 作为主语义。
4. 前端和 P4.5 读取时优先使用 `trend_state / module_state / module_effective_bias`，避免直接把极小分数方向当结论。

## 不改范围

- 不修改 P1 kline 派生指标采集。
- 不修改 P2 指标注册。
- 不修改 Kline composite 原始打分公式。
- 不改变 `btc_return_1h / btc_return_24h / close_position` 等单项指标分数。

## 规则

### Kline Effective Deadband

```text
if abs(module_effective_score) < 0.05:
    module_effective_direction = neutral
    module_effective_bias = neutral

elif 0.05 <= module_effective_score < 0.12:
    module_effective_direction = neutral
    module_effective_bias = mild_support

elif -0.12 < module_effective_score <= -0.05:
    module_effective_direction = neutral
    module_effective_bias = mild_pressure

elif module_effective_score >= 0.12:
    module_effective_direction = bullish
    module_effective_bias = support

elif module_effective_score <= -0.12:
    module_effective_direction = bearish
    module_effective_bias = pressure
```

### 展示优先级

```text
kline primary display =
  trend_state
  -> module_state
  -> module_effective_bias
  -> module_effective_direction
```

当 `trend_state = neutral_wait_confirm` 时，即使 `module_effective_score > 0`，也不能直接展示为 bullish。

## 验收样例

输入：

```json
{
  "module": "kline_orderflow",
  "module_effective_score": 0.0032,
  "trend_state": "neutral_wait_confirm",
  "module_state": "internal_conflict"
}
```

期望输出：

```json
{
  "module_effective_direction": "neutral",
  "module_effective_bias": "neutral",
  "display_state": "neutral_wait_confirm"
}
```

## DoD

- [ ] `abs(module_effective_score) < 0.05` 时，不得输出 `module_effective_direction = bullish/bearish`。
- [ ] Kline 卡片主标签优先显示 `等待确认 / neutral_wait_confirm`，不显示极小分数 bullish。
- [ ] P4.5 horizon / article 不把极小 Kline effective 正分写成“短线偏多确认”。
- [ ] Radar Detail 中仍保留单项指标真实方向和分数，方便审计。
- [ ] 增加回归测试覆盖 `0.0032 -> neutral` 样例。

## 关联

P3-C29, P3-C31, P4.5-C21, P5-C38

## Completion Note

- Done: `kline_orderflow` 增加 effective direction deadband，`abs(module_effective_score) < 0.12` 不再输出 bullish/bearish。
- Done: Kline module semantic profile 透出 `module_effective_bias` 与 `display_state`，极小正分显示为 neutral。
- Verified: P3 pipeline、P4.5 writer/html 回归测试通过。
