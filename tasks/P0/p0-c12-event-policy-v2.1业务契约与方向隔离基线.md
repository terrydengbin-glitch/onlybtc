# P0-C12 / Event Policy v2.1 业务契约与方向隔离基线

## 状态
DONE

## 背景

`event_policy` 的目标不是判断 BTC 涨跌，而是处理 CPI、FOMC、PCE、NFP、Fed speech 与 blackout 等事件窗口带来的交易许可变化。

本卡定义跨 P1/P2/P3/P4.5/P8 的业务契约，避免后续实现把事件倒计时误写成方向 alpha。

## 核心定位

```text
event_policy = event_risk_and_trade_permission
forbidden_purpose = directional_alpha
```

它只回答：

```text
现在能不能做？
能做几成仓？
能不能追突破？
要不要等数据落地？
```

它不回答：

```text
BTC 要涨还是要跌
```

## 链条分工

```text
P1:
  准备事件时间、事件阶段、发布后 digest 与 surprise 可用上下文。

P2:
  将 event_policy 指标统一标记为 context_risk / risk-only role。

P3:
  输出 p3.c43.event_policy.v2.1 profile 和可执行 trade_gate。

P4.5:
  报告层只写事件门控、等待数据落地、风险锁定，不写方向判断。

P8:
  持久化 event_policy v2.1 payload，并保证 replay/API 兼容旧 run。
```

## 硬约束

```text
module_direction = neutral
module_score = 0
module_effective_score = 0
affects_direction = false
```

`event_policy` 不得进入：

```text
directional_score
bullish/bearish majority vote
support_drivers
pressure_drivers
```

只能影响：

```text
risk_score
confidence_adjustment
trade_permission
position_size_multiplier
breakout_permission
wait_for_data_landing
```

## DoD

- P0 契约明确 `event_policy` 是事件风险门控器，不是方向模块。
- 下游任务卡均引用本契约。
- `blackout_active` 被定义为 context amplifier，不是独立 hard gate。
- `trade_gate` 被定义为下游可执行动作字段。
- 任务执行顺序明确为 P1 -> P2 -> P3 -> P8 -> P4.5。
