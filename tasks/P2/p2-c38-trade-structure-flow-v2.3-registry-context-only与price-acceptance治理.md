# P2-C38 / Trade Structure Flow v2.3 Registry context-only 与 price acceptance 治理

## 状态

DONE

## Phase

P2 Radar 指标与模块层

## 背景

`trade_structure_flow v2.3` 必须防止成交量、taker buy/sell、funding、OI、清算等单因子直接进入 BTC 方向判断。P2 需要把原始 level 降级为 context，并只允许 price acceptance、standardized residual、spot/perp quality、liquidation response 等组合字段参与方向。

## 目标

重构 `trade_structure_flow` registry：

```text
raw level/context -> affects_signal=false
structure pressure -> warning/context
price acceptance + residual -> directional confirmation
liquidation snapshot -> cannot trigger confirmed alone
```

## 指标角色

### Context-only

```text
exchange_spot_volume
taker_buy_sell_ratio
btc_funding_rate
btc_open_interest
futures_basis
liquidation_long_usd
liquidation_short_usd
best_bid
best_ask
mid_price
orderbook depth raw levels
```

### Direction-eligible composite metrics

```text
price_acceptance_score
aggressive_flow_score
liquidity_directional_score
spot_perp_quality_score
leverage_structure_score
liquidation_response_score
residual_confirmation_score
trade_structure_residual_z
btc_return_z_5m
btc_return_z_15m
btc_return_z_1h
```

## DoD

- [ ] 成交量不能单独触发 bullish/bearish。
- [ ] taker buy/sell ratio 不能单独触发方向。
- [ ] funding positive 不能单独 bullish。
- [ ] OI rising 不能单独 bullish/bearish。
- [ ] liquidation spike 不能单独 confirmed_signal。
- [ ] liquidity thinning 只能 early_warning，除非 BTC response 同向确认。
- [ ] P2 registry 测试覆盖 raw/context 与 composite/directional 边界。

## 关联任务

- P1-C55
- P3-C53
- P9-C35
