# P3-C34 / Derivatives Long/Short Ratio 组合评分与挤压风险语义

## 状态

DONE

## 背景

P3-C32 已经修复 Funding + OI 的组合语义：Funding 温和 + OI flat 不再被误读成 bullish。但当前衍生品拥挤度仍缺少“多空仓位偏斜”输入，只能靠 Funding / OI 推断。

P1-C39 / P2-C24 会新增 Binance long/short ratio 指标。本任务负责把这些指标纳入 P3 derivatives_crowding 组合评分。

## 目标

1. 新增 long/short ratio 单项语义。
2. 将 top trader position ratio 接入拥挤风险评分。
3. 将 account ratio 与 position ratio 的分歧显式化。
4. 与 Funding / OI / price change 组合判断 long crowded、short crowded、squeeze risk。
5. 不把 long ratio 高简单等同 bullish。

## 核心规则

### 多头拥挤

```text
if top_long_short_position_ratio 高
and funding_state in funding_elevated/funding_hot
and oi_state == oi_rising:
    crowding_state = long_crowded
    module_effective_bias = mild_pressure
    trend_direction = neutral
```

### 空头拥挤

```text
if top_long_short_position_ratio 低
and funding_state == funding_negative
and oi_state == oi_rising:
    crowding_state = short_crowded
    module_effective_bias = squeeze_support
    trend_direction = neutral
```

### 多头偏斜但未拥挤

```text
if long_short_position_ratio 略高
and funding_state == funding_mild
and oi_state in oi_flat/oi_falling:
    crowding_state = balanced_or_mild_long_skew
    confirmation_state = unconfirmed
```

### 账户/仓位分歧

```text
if global_account_ratio 与 top_position_ratio 方向相反:
    positioning_conflict_level = high
    confidence_score *= 0.85
```

## 输出字段

在 derivatives_crowding 模块增加：

```json
{
  "positioning_state": "balanced|long_skew|short_skew|extreme_long|extreme_short",
  "top_positioning_state": "balanced|top_long_skew|top_short_skew|top_extreme_long|top_extreme_short",
  "positioning_conflict_level": "none|low|medium|high",
  "long_short_squeeze_risk": "none|long_squeeze_risk|short_squeeze_risk",
  "long_short_combo_applied": true
}
```

指标级增加：

```json
{
  "positioning_signal": "long_skew|short_skew|balanced",
  "crowding_contribution": "mild_support|mild_pressure|neutral|squeeze_support",
  "trend_confirmation": "confirmed|unconfirmed"
}
```

## DoD

- [ ] long/short ratio 高不直接等于 bullish。
- [ ] top trader position ratio 极端 + funding/OI 配合时能触发 crowded 状态。
- [ ] short skew + negative funding + rising OI 能触发 squeeze support。
- [ ] Funding/OI 原有 P3-C32 回归不破坏。
- [ ] P3 审计 HTML 显示 positioning state 与 squeeze risk。
- [ ] P3 测试覆盖至少 4 个样例：balanced、long_crowded、short_crowded、account/position conflict。

## 关联

P1-C39, P2-C24, P3-C32, P3-C33, P4.5-C24, P5-C41

## Completion Note

- Done: positioning_signal, crowding_contribution, positioning_scope, module positioning state, squeeze risk.
- Verified: new P3 regression and full P3 test file passed.
