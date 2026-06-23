# P5-C58 中央 BTC 卡片 v2 趋势驾驶舱展示

状态：DONE

## 目标

中心 BTC 卡读取优先级：

```text
1. btc_trend_cockpit.v2
2. fallback decision_card
3. fallback btc_total_state
```

展示结构升级为 7 个区域：

```text
1. Fast Read
2. Confirmation
3. Main Pressure
4. Main Support
5. Conflict / Why Not Strong
6. Next Trigger
7. Invalidation
```

## 状态视觉映射

```text
confirmed_bullish: 绿色强状态
bullish_watch: 绿色弱状态
neutral: 灰蓝状态
bearish_watch: 橙红弱状态
confirmed_bearish: 红色强状态
conflict: 黄色/紫色冲突状态
blocked: 灰色禁用状态
```

## 防误导要求

1. 不显示“ETF 流出所以 BTC 看空”这类单因子句式。
2. 不把 funding/OI/risk score 直接渲染为最终方向原因。
3. 必须显示 `trend_quality` 或等价的 acceptance/readiness 信息。
4. 有 conflict 时必须解释为什么不能升级为强方向。
5. blocked 时必须显示数据/契约原因。

## DoD

1. 中央 BTC 卡优先消费 `btc_trend_cockpit`。
2. 缺失 cockpit 时 fallback 到旧卡片，不白屏。
3. 7 个区域至少有可用空态和正常态。
4. `headline_state`、`trend_phase`、`trend_quality` 显示准确。
5. 文本在当前 dashboard 尺寸内不溢出、不遮挡。
6. `npm run build` 通过。
7. P5 dashboard contract / smoke 测试通过。
