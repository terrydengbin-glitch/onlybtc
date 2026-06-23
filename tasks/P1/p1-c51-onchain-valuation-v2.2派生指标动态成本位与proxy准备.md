# P1-C51 / Onchain Valuation v2.2 派生指标、动态成本位与 Proxy 准备

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 背景

`onchain_valuation` 当前已有 `mvrv_zscore`、`nupl`、`sopr`、`realized_price`、`sth_cost_basis`、`lth_cost_basis`、`whale_flow`、`miner_flow` 等字段，但模块要升级为 v2.2 后，P1 需要先把慢变量、快变量、BTC response residual 与 proxy 分级准备好。

v2.2 的核心不是判断 BTC 便宜还是贵，而是判断：

```text
链上成本基础、盈亏兑现、实现市值流入/流出，
是否正在确认、削弱、提前预警或反证 BTC 当前 4h-14d 趋势？
```

专业依据：

- MVRV / MVRV-Z 更适合判断市场相对 realized cap 的周期估值位置，不应单独触发短线方向。
- SOPR 衡量链上花费币的实现盈亏，SOPR = 1 是盈亏平衡位，适合判断盈利恢复、亏损兑现和利润兑现压力。
- STH/LTH 使用约 155 天持有期分界，STH 成本基础更接近中短期持有者压力位。
- Realized Cap 是按每枚币最后移动时价格计价的网络成本基础，适合判断链上资本沉淀。
- miner / whale 精确指标依赖实体标签，缺失时只能作为 proxy/context，不能作为硬确认信号。

## 目标

为 `p3.c52.onchain_valuation.v2.2` 准备可消费指标，使下游能区分：

```text
regime_score       = 慢变量，7d-90d 链上估值背景
trend_delta_score  = 快变量，4h-14d 趋势变化响应
```

## 范围

### 慢变量

```text
mvrv_zscore
mvrv_ratio
nupl
realized_cap
realized_price
lth_cost_basis
puell_multiple_proxy
miner_pressure_proxy
whale_pressure_proxy
```

### 快变量

```text
btc_vs_sth_cost_basis_pct
btc_vs_sth_cost_basis_z_365d
sth_cost_basis_distance_change_24h
btc_vs_realized_price_pct
btc_vs_lth_cost_basis_pct
sopr
a_sopr_optional
sth_sopr_optional
sopr_change_1d
sopr_z_90d
sopr_above_1_streak_days
sopr_below_1_streak_days
sopr_cross_1_direction
realized_cap_change_7d_pct
realized_cap_change_30d_pct
realized_cap_impulse_z_180d
btc_return_4h
btc_return_24h
btc_return_3d
btc_return_7d
onchain_expected_return_24h
onchain_residual_24h
onchain_residual_z_90d
```

### 动态 STH 成本位带宽

```text
sth_band_pct = max(
  1.2%,
  min(3.5%, btc_14d_realized_vol * 0.35)
)

upper_sth_band = sth_cost_basis * (1 + sth_band_pct)
lower_sth_band = sth_cost_basis * (1 - sth_band_pct)
```

## Proxy 分级

```text
tier_1_exact:
  realized_cap
  realized_price
  mvrv
  nupl
  sopr
  sth_cost_basis
  lth_cost_basis

tier_2_derived:
  realized_price = realized_cap / supply_current
  nupl = (market_cap - realized_cap) / market_cap
  mvrv = market_cap / realized_cap
  mvrv_z_proxy = (market_cap - realized_cap) / rolling_std(market_cap, 1460d)

tier_3_proxy:
  sth_cost_basis_proxy = 155d rolling vwap
  lth_cost_basis_proxy = 2y/4y realized price band
  puell_multiple_proxy = daily_issuance_usd / ma365(daily_issuance_usd)
  miner_pressure_proxy = puell_multiple_proxy + hashprice_z
  whale_pressure_proxy = large_tx_exchange_pressure_proxy
```

规则：

```text
tier_1 可以触发 confirmed_signal
tier_2 最多触发 fast_signal
tier_3 只能触发 early_warning 或 context
```

## 数据质量规则

```text
if sth_lth_source_stale_hours > 48:
  disable cost_basis_reclaim/rejection fast states
  data_quality_flags += ["sth_lth_cost_basis_stale"]

if mvrv_zscore_history_days < 365:
  use mvrv_ratio only
  data_quality_flags += ["mvrv_zscore_history_insufficient"]

if sopr_missing:
  disable profitability_recovery confirmed
  data_quality_flags += ["sopr_missing"]

if whale/miner exact data missing:
  do not fail module
  proxy_flags += ["provider_optional_missing"]

if proxy metric used:
  proxy_flags += ["proxy_metric_used"]
```

## DoD

- [ ] 慢变量与快变量均可写入 SQLite 并被 P2/P3 消费。
- [ ] `sth_band_pct`、`upper_sth_band`、`lower_sth_band` 可输出。
- [ ] `sopr_z_90d`、SOPR streak、SOPR cross direction 可输出。
- [ ] `realized_cap_impulse_z_180d` 可输出，有历史不足 fallback。
- [ ] `onchain_expected_return_24h`、`onchain_residual_24h`、`onchain_residual_z_90d` 可输出。
- [ ] tier_1/tier_2/tier_3 proxy flags 明确写入，不混作精确指标。
- [ ] whale/miner 缺失不导致模块失败，只降低 confidence。

## 关联任务

- P2-C34
- P3-C49
- P8-C26
- P9-C31
