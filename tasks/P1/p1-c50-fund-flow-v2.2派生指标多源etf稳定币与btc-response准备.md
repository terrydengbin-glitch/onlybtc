# P1-C50 / Fund Flow v2.2 派生指标、多源 ETF、稳定币与 BTC response 准备

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 背景

`fund_flow` 当前已覆盖 `etf_net_flow`、`etf_flow_7d`、`stablecoin_supply`、`exchange_balance_delta_1d_proxy`，并已有 ETF 绝对方向与边际改善的防误导语义。但 v2.2 需要把模块升级为资金流确认/反证模块，P1 必须先准备更敏感的多窗口、z-score、streak、acceleration、交易所供给异常降权与 BTC response residual。

专业依据：

- ETF flow 是 BTC 机构边际需求的核心输入，但不能只看单日正负。
- CoinGlass ETF flow history 可提供每日净流入/流出、收盘价与 ticker 分项，适合做 1d/3d/7d/20d 多窗口。
- Farside 可作为交叉校验源，但需保留自动表格误差风险。
- Glassnode/CryptoQuant 的 exchange balance / netflow 适合判断可交易供给，但短期大额转账需识别内部转账风险。
- SSR 与稳定币供应代表链上美元购买力背景，不直接等于买入 BTC。

## 目标

为 `p3.c50.fund_flow.v2.2` 准备 P1 可消费指标，使下游能判断：

```text
ETF、稳定币与交易所供给变化之后，BTC 是否正在接受、拒绝或抵抗资金流信号。
```

## 范围

新增或派生以下指标。

### ETF

```text
etf_net_flow_usd
etf_flow_2d_usd
etf_flow_3d_usd
etf_flow_5d_usd
etf_flow_7d_usd
etf_flow_20d_usd
etf_flow_1d_z_60d
etf_flow_3d_z_60d
etf_flow_7d_z_60d
etf_inflow_streak_days
etf_outflow_streak_days
etf_flow_acceleration_3d
etf_flow_reversal_2d
etf_flow_shock_flag
etf_flow_data_source_count
etf_flow_cross_source_diff_pct
```

### Stablecoin / SSR

```text
stablecoin_total_mcap
stablecoin_mcap_change_1d
stablecoin_mcap_change_7d
stablecoin_mcap_change_30d
stablecoin_mcap_z_60d
stablecoin_mcap_change_7d_z_120d
stablecoin_mcap_change_30d_z_180d
ssr
ssr_z_180d
ssr_change_7d
stablecoin_exchange_netflow_1d_optional
stablecoin_exchange_netflow_7d_optional
stablecoin_liquidity_regime
```

### BTC Exchange Supply

```text
btc_exchange_balance
btc_exchange_balance_change_1d
btc_exchange_balance_change_7d
btc_exchange_netflow_1d
btc_exchange_netflow_7d
btc_exchange_netflow_z_60d
btc_exchange_netflow_z_180d
large_single_transfer_flag
internal_transfer_risk_flag
exchange_metric_revision_risk
exchange_flow_confirmed
```

### BTC Response

```text
btc_return_4h
btc_return_12h
btc_return_24h
btc_return_3d
btc_volume_z_24h
btc_realized_vol_24h
btc_realized_vol_7d
fund_flow_expected_return_24h
fund_flow_residual_24h
fund_flow_residual_z_60d
```

## 派生规则

```text
etf_flow_acceleration_3d =
  etf_flow_3d_usd - previous_etf_flow_3d_usd

etf_flow_reversal_2d =
  sign(etf_net_flow_today) != sign(etf_net_flow_yesterday)
  and abs(etf_net_flow_today) > rolling_abs_flow_median_60d

etf_flow_shock_flag =
  abs(etf_flow_1d_z_60d) >= 2
  or abs(etf_net_flow_usd) >= rolling_abs_flow_p90_120d
```

BTC residual 使用 rolling robust regression 或 rule-based fallback：

```text
btc_return_24h =
  beta_0
  + beta_1 * etf_flow_1d_z_60d
  + beta_2 * etf_flow_3d_z_60d
  + beta_3 * stablecoin_mcap_change_7d_z_120d
  + beta_4 * (-btc_exchange_netflow_z_60d)
  + error

fund_flow_residual_24h =
  btc_return_24h - fund_flow_expected_return_24h
```

## 数据质量规则

```text
ETF flow stale > 36h:
  disable fast ETF state
  data_quality_flags += ["etf_flow_stale"]

ETF source diff > 15%:
  data_quality_flags += ["etf_cross_source_mismatch"]

stablecoin history < 60d:
  disable z-score
  use 7d/30d raw change only

exchange flow abs z >= 2 and single transfer dominates:
  large_single_transfer_flag = true
  internal_transfer_risk_flag = true

fund_flow_residual model sample < 90d:
  use rule-based fallback
  data_quality_flags += ["fund_flow_residual_model_sample_low"]
```

## DoD

- [ ] ETF 1d/2d/3d/5d/7d/20d 多窗口进入 SQLite。
- [ ] ETF z-score、streak、acceleration、reversal、shock flag 可被 P2/P3 消费。
- [ ] CoinGlass 与 Farside/现有源可输出交叉源数量与差异率。
- [ ] 稳定币供应、变化率、SSR 与 liquidity regime 可被 P3 消费。
- [ ] 交易所 BTC 供给指标能识别大额单笔/内部转账风险并降权。
- [ ] `fund_flow_expected_return_24h`、`fund_flow_residual_24h`、`fund_flow_residual_z_60d` 有可靠 fallback。
- [ ] P1/P2/P3 同 run lineage 不混用历史 mock 数据。

## 关联任务

- P2-C33
- P3-C48
- P8-C25
- P9-C30
