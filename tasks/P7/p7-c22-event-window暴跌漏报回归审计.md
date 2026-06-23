# P7-C22 / Event Window 暴跌漏报回归审计

## 状态
DONE

## 背景

用户反馈 BTC 在约 5 小时内暴跌，但 Event Window 没有任何预警。本轮排查发现：daemon snapshot stale、shock lane 只看 5m return、market probe 不独立，是主要断点。

## 目标

建立一个可重复的回归审计，证明修复后 Event Window 能捕捉：

```text
5m 不极端
1h/4h 明显下跌
24h 背景转弱
无官方突发文本
```

这种 sustained market shock 场景。

## 审计场景

```json
{
  "btc_return_5m": -0.002,
  "btc_return_15m": -0.0025,
  "btc_return_1h": -0.014,
  "btc_return_4h": -0.016,
  "btc_return_24h": -0.032,
  "official_shock": false,
  "calendar_event_lock": false
}
```

期望输出：

```text
event_window_state = sustained_drawdown_watch 或 market_dislocation_high_alert
emergency_level = watch/high
ordinary_radar_trust = reduced/low
trade_permission_modifier = reduce_size/watch_only
direct_score_impact = false
```

## 输出报告

```text
reports/event-window-market-shock-regression-audit.html
reports/event-window-market-shock-regression-audit.json
```

## DoD

- [x] 审计能复现旧逻辑为何不触发。
- [x] 审计能验证新逻辑多窗口触发。
- [x] 报告显示 daemon heartbeat、snapshot freshness、market probe freshness。
- [x] 报告显示 shock evidence source：independent_probe 或 metric_fallback。
- [x] 报告确认 Event Window 不修改 BTC score。
- [x] 如果 market probe 缺失，审计必须 FAIL，而不是 PASS。
- [x] run once / audit bundle 能包含该回归摘要。

## 依赖

- P1-C69
- P2-C41
- P3-C59
- P5-C78


