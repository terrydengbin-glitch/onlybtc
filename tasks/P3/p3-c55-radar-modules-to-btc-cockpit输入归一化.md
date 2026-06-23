# P3-C55 Radar Modules to BTC Cockpit 输入归一化

状态：DONE

## 目标

为 `btc_trend_cockpit.v2` 建立 radar module 输入归一化层，把 14 个已优化 radar modules 转成统一 `module_signal[]`。中心 BTC 卡不直接读取 raw metric，不把 `risk_score`、`pressure_score` 或单一模块结论机械转成 BTC 方向。

## 输出契约

```json
{
  "module_name": "",
  "layer": "fast|confirmation|regime|controller",
  "horizon": "4h|24h|3d|7d",
  "raw_direction": "bullish|bearish|neutral|mixed",
  "effective_direction": "bullish|bearish|neutral|conflict|rejected",
  "signal_stage": "none|early_warning|fast_signal|confirmed_signal|rejected|conflict",
  "module_score": 0,
  "effective_score": 0,
  "btc_implication": "",
  "btc_response_score": null,
  "residual": null,
  "support_drivers": [],
  "pressure_drivers": [],
  "conflict_drivers": [],
  "data_quality_flags": [],
  "quality_status": "passed|partial|stale|failed",
  "accepted_status": "accepted|unconfirmed|fragile|rejected|unknown"
}
```

## 分层

```text
fast:
  kline_orderflow, trade_structure_flow, derivatives_crowding, asia_risk

confirmation:
  fund_flow, treasury_credit, macro_radar, dollar_liquidity

regime:
  onchain_valuation, btc_adoption, crypto_breadth, options_volatility, event_policy

controller:
  btc_total_state, aggregation_audit, contract_validation, data_quality
```

## 归一化规则

```text
stage_multiplier:
  early_warning = 0.35
  fast_signal = 0.65
  confirmed_signal = 1.00
  rejected = -0.50
  conflict = 0.25

quality_multiplier:
  passed = 1.00
  partial = 0.70
  stale = 0.40
  failed = 0.00

accepted_multiplier:
  accepted = 1.00
  unconfirmed = 0.55
  fragile = 0.35
  rejected = -0.30
  unknown = 0.50
```

## DoD

1. 新增或复用归一化 helper，输出 `module_signal[]`。
2. 14 个已优化 radar modules 都能映射到 layer/horizon。
3. 原始 level / raw metric 不被中心归一化层直接消费。
4. `risk_score` 高不等于 bearish，`pressure_score` 高不等于 bearish。
5. 单一强模块只能产生 contribution，不能产生中心 confirmed。
6. data quality failed / stale 时 contribution 正确降权。
7. targeted pytest 通过。
