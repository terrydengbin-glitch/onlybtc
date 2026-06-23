# P2-C41 / Event Window Shock Fast Lane 多窗口行情冲击判定

## 状态
DONE

## 背景

现有 shock lane 主要检查 BTC 5m return。此次 5 小时级别暴跌没有触发预警，说明单一 5m 窗口过窄：如果下跌分布在数小时内，5m return 可能不极端，但 1h/4h/24h 已经足以降低普通 radar 可信度。

## 目标

升级 shock fast lane，使其同时识别：

```text
5m / 15m 快速冲击
1h / 4h 持续性下跌或上涨
24h 背景级风险变化
行情冲击是否有 OI / funding / liquidation / cross-asset confirmation
```

## 判定逻辑

### fast dislocation

```text
abs(return_5m_z) >= 2
or abs(return_15m_z) >= 2
```

### sustained market shock

```text
abs(return_1h_z) >= 1.5
or abs(return_4h_z) >= 1.5
or abs(return_4h_pct) >= configurable_threshold
```

### slow crash watch

```text
return_4h < negative_threshold
and return_24h < negative_threshold
and 5m shock is mild
=> market_dislocation_watch / sustained_drawdown_watch
```

## 输出契约

```json
{
  "shock_type": "market_dislocation|crypto_native|cross_asset|policy|unknown",
  "emergency_level": "watch|high|critical",
  "confirmation_level": "market_dislocation|official_and_market|single_source|multi_source",
  "reason_codes": [
    "btc_1h_drop",
    "btc_4h_sustained_drawdown",
    "btc_24h_context_pressure"
  ],
  "evidence": {
    "btc_return_5m": 0,
    "btc_return_15m": 0,
    "btc_return_1h": 0,
    "btc_return_4h": 0,
    "btc_return_24h": 0,
    "btc_return_5m_z": null,
    "btc_return_1h_z": null,
    "btc_return_4h_z": null,
    "market_probe_source": ""
  }
}
```

## 关键边界

- Market shock 只改变 Event Window emergency overlay，不直接改 BTC score。
- 5m 没有极端波动时，1h/4h 仍可触发 watch/high。
- 如果缺少 independent market probe，可降级使用主 P1 `btc_return_*` 指标，但必须标记 `main_pipeline_metric_fallback`。
- 单一行情冲击不能自动解释成宏观事件，除非 official/trusted source 确认。

## DoD

- [x] shock lane 同时消费 5m / 15m / 1h / 4h / 24h return。
- [x] `_recent_btc_return` 不再只依赖最近 5 分钟 price ticks。
- [x] 当 price ticks 不足时，可使用 `btc_return_5m/15m/1h/4h/24h` metric fallback。
- [x] 4h 级别持续下跌可触发 `market_dislocation_watch` 或 `unscheduled_shock_watch`。
- [x] 输出 evidence 包含所有窗口 return、zscore、source_lineage。
- [x] 单元测试覆盖“5m mild、4h sharp drop”的漏报回归场景。

## 依赖

- P1-C69
- P2-C40


