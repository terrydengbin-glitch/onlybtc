# P5-C45 / Event Policy v2.1 trade_gate 与事件风险窗口前端展示对齐

## 状态
DONE

## 背景

后端 `event_policy` 已升级为 `p3.c43.event_policy.v2.1`，详情接口 `/api/p45/radar-modules/event_policy` 已透传：

```text
event_policy_v21
event_window_phase
event_short_term_state
event_risk_lock_level
dominant_event_type
nearest_event_type
nearest_event_hours
trade_gate
context_notes
```

但前端当前只对 `btc_total_state` 和 `options_volatility` 做了专项结构化展示。`event_policy` 仍主要走通用 Radar Detail 展示，用户难以直接看到“能不能开仓、能不能加仓、能不能追突破、仓位倍数是多少”。

## 目标

Radar Detail 对 `event_policy` 增加专项展示，不再把它理解为方向模块，而是展示为事件风险门控器。

顶部状态建议：

```text
Event Gate: {event_short_term_state}
phase {event_window_phase} · lock {event_risk_lock_level}
```

页面拆成四块：

```text
1. 事件窗口
   dominant_event_type
   nearest_event_type
   nearest_event_hours
   event_window_phase

2. 交易门控
   allow_new_position
   allow_add_position
   allow_breakout_entry
   allow_market_entry
   position_size_multiplier
   reason_code

3. 风险锁定
   event_risk_lock_level
   risk_score
   confidence_adjustment
   penalty_channel

4. 上下文说明
   context_notes
   summary
```

## UI 约束

- 不显示 `Event Policy: Bullish / Bearish`。
- 不把 CPI/FOMC/PCE/NFP/Fed speech/blackout 放入方向驱动列表。
- `blackout_active` 只显示为 context amplifier，不显示为独立 hard lock。
- `trade_gate` 使用明确动作展示，例如：

```text
New position: allowed / blocked
Add position: allowed / blocked
Breakout entry: allowed / blocked
Market entry: allowed / blocked
Size multiplier: 0.7
Reason: PRE_CPI_24H_CAUTION
```

## DoD

- `event_policy` Radar Detail 使用四区块展示。
- 前端能从 `event_policy_v21` 或 `module_semantic_profile` fallback 读取字段。
- 顶部 module summary 使用 event gate 语义，而不是 direction 语义。
- `trade_gate` 字段缺失时使用安全默认展示，不报错。
- 移动端与桌面端文本不溢出、不重叠。
- 前端 build 通过。

## Tests

```powershell
npm run build
```
