# P5-C51 / Fund Flow v2.2 四区块确认/拒绝状态展示

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

`fund_flow.v2.2` 会输出 ETF demand、stablecoin liquidity、exchange supply、BTC response 四个子状态。前端不能只显示 `module_effective_direction`，否则会重复 P5-C39 已修过的“fund_flow 被误读为纯 bullish”问题。

## 目标

在 Vue3 Radar Detail 中为 `fund_flow` 增加 v2.2 专属展示：

```text
ETF 边际需求
稳定币美元流动性
BTC 可交易供给
BTC response / acceptance / rejection
```

## 展示优先级

模块标签优先级：

```text
fund_flow_state
-> btc_implication
-> trend_state
-> module_effective_direction
-> module_direction
```

warning / rejection 使用 mixed 或 warning 视觉，不用纯 support 绿。

## 四区块

### ETF Demand

展示：

```text
state
flow_1d_z
flow_3d_usd
flow_7d_usd
inflow_streak_days
outflow_streak_days
flow_acceleration_3d
```

### Stablecoin Liquidity

展示：

```text
state
mcap_change_7d
mcap_change_30d
ssr_z_180d
```

### Exchange Supply

展示：

```text
state
btc_exchange_netflow_1d
btc_exchange_netflow_7d
btc_exchange_netflow_z_60d
large_single_transfer_flag
internal_transfer_risk_flag
```

### BTC Response

展示：

```text
state
btc_return_4h
btc_return_24h
expected_return_24h
residual_24h
residual_z_60d
```

## 文案要求

- `btc_rejecting_flow_tailwind` 显示为“资金流顺风被 BTC 拒绝”。
- `btc_resisting_flow_headwind` 显示为“BTC 抵抗资金流逆风”。
- `etf_outflow_warning` 显示为“ETF 流出预警”，不能显示为 confirmed bearish。
- `stablecoin_liquidity_tailwind` 显示为“流动性背景支持”，不能显示为强多。
- `exchange_flow_untrusted` 必须突出数据质量降权。

## DoD

- [ ] Radar Detail 展示 `fund_flow_v22` 或等价 v2.2 contract。
- [ ] 四区块字段齐备，缺失时有空态。
- [ ] Dashboard 节点标签优先显示复合状态。
- [ ] warning/rejection 不使用纯 bullish/bearish 误导色。
- [ ] `npm run build` 通过。

## 关联任务

- P4.5-C34
- P9-C30
