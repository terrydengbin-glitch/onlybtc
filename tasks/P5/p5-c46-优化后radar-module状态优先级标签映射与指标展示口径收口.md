# P5-C46 / 优化后 Radar Module 状态优先级、标签映射与指标展示口径收口

## 状态

DONE

## 背景

近期已完成多个 Radar Module 专项语义优化：

```text
btc_total_state v2
options_volatility v2.1
event_policy v2.1
trade_structure_flow v1
derivatives_crowding v2
fund_flow v1
kline_orderflow v1
```

后端已经输出专项状态字段，但前端 `moduleDisplayState()` / `moduleDisplayLabel()` / `moduleDisplayShortLabel()` 仍存在少量展示优先级和标签映射缺口。

当前审计发现：

```text
trade_structure_flow:
  trade_structure_state = bearish_confirmation
  trend_state/display_state = neutral_wait_confirm
```

前端应优先展示专项状态 `trade_structure_state`，避免被旧 `trend_state` 或 direction fallback 盖掉。

另有：

```text
options_volatility:
  vol_neutral / vol_expansion_risk / pinning_likely 等完整 label 映射不足

event_policy:
  event_neutral / caution / hard_lock / post_digest 等 gate 状态完整 label 映射不足
```

## 目标

收口优化后 Radar Module 的前端状态展示口径：

```text
专项状态 > display_state > trend_state > module_state > effective_direction > module_direction
```

但对已明确治理过的模块，专项状态必须绝对优先：

```text
btc_total_state:
  btc_short_term_state

options_volatility:
  options_short_term_state

event_policy:
  event_short_term_state

trade_structure_flow:
  trade_structure_state

fund_flow:
  fund_flow_state

derivatives_crowding:
  long_short_squeeze_risk / crowding_state / positioning_state
```

## 范围

### 前端

修改：

```text
frontend/src/App.vue
```

重点函数：

```text
moduleDisplayState()
moduleDisplayLabel()
moduleDisplayShortLabel()
moduleDisplayClass()
```

必须补齐：

```text
bearish_confirmation
event_neutral
event_caution
event_hard_lock
event_post_digest
vol_neutral
vol_expansion_risk
pinning_likely
downside_protection_bid
tail_risk_elevated
large_expiry_near
pinning_before_expiry_vol_after
vol_expansion_risk_with_structure_resistance
```

### 不在范围

- 不改后端 P3 / P4.5 评分逻辑。
- 不改 Radar module 权重。
- 不改 P2 registry。
- 不做页面大改版。

## DoD

- `trade_structure_flow` 当前样本前端主标签显示 `bearish_confirmation`，不再被 `neutral_wait_confirm` 覆盖。
- `options_volatility` 的 `vol_neutral` 等状态有中文完整标签和短标签。
- `event_policy` 的 `event_neutral` / 风险窗口状态有中文完整标签和短标签。
- 复合状态的颜色语义正确：
  - `bearish_confirmation` 为 pressure/bear。
  - `event_*` 为 mixed/wait 或 neutral，不显示成 bullish/bearish alpha。
  - `vol_*` 主要为 mixed/risk，不显示成方向 alpha。
- 指标面板继续展示 `value / metric_score / metric_effective_score / quality`，不回退。
- `npm run build` 通过。

## Tests

```powershell
npm run build
```
