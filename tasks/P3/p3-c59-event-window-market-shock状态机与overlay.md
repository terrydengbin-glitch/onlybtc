# P3-C59 / Event Window Market Shock 状态机与 Overlay 升级

## 状态
DONE

## 背景

Event Window 的定位不是预测 BTC 多空，而是判断普通 radar 何时暂时不可信。市场自身出现快速或持续冲击时，即使没有官方日历事件，也应该进入 watch/high/critical overlay，降低普通趋势判断可信度。

## 目标

把 P2-C41 的多窗口 market shock 接入 Event Window state machine 与 emergency overlay。

## 新增状态 / reason code

```text
market_dislocation_watch
market_dislocation_high_alert
sustained_drawdown_watch
sustained_drawdown_high_alert
crypto_native_market_shock
market_shock_absorbed
market_shock_followthrough
```

## 状态优先级

```text
data_quality_blocked
> unscheduled_shock_confirmed
> event_lock
> market_dislocation_high_alert
> sustained_drawdown_high_alert
> release_surprise
> policy_repricing_shock
> pre_event_high_alert
> expectation_drift_watch
> calendar_monitor
> event_neutral
```

## Overlay 映射

```text
watch:
  trade_permission_modifier = reduce_size
  ordinary_radar_trust = reduced

high:
  trade_permission_modifier = watch_only
  ordinary_radar_trust = low

critical:
  trade_permission_modifier = event_lock / avoid_new_position
  ordinary_radar_trust = blocked
```

## 关键边界

- 不直接修改主 BTC cockpit score。
- 不输出 BTC bullish/bearish。
- 如果市场冲击与 scheduled event 同时存在，状态机要保留两者 reason code，但按优先级决定 headline state。
- 如果冲击后 BTC 30m/2h 快速收回，则转为 `market_shock_absorbed`，overlay 可降级。

## DoD

- [x] P2-C41 shock item 可进入 Event Window state machine。
- [x] 5h/4h 累积下跌场景触发 high/watch overlay，而非 event_neutral。
- [x] overlay 只改变 trade permission / radar trust / confidence cap。
- [x] 状态输出包含 reason_codes、valid_until、source_lineage。
- [x] post-event / post-shock reaction 可将 followthrough 与 absorbed 分开。
- [x] 回归测试覆盖无官方事件但 BTC 暴跌的场景。

## 依赖

- P2-C41
- P3-C56


