# P1-C53 / Asia Risk v2.3 派生指标、亚洲时段 BTC response 与 regional risk 准备

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 背景

`asia_risk` 需要从“亚洲宏观风险变量打分器”升级为“BTC 亚洲时段趋势确认 / 反证模块”。USDJPY、USDCNH、Nikkei、TOPIX、Hang Seng Tech、JGB、HIBOR 等原始 level 只能作为 context，不能直接决定 BTC 方向。

v2.3 的核心原则：

```text
亚洲风险变量只产生 pressure / support / warning。
BTC response、亚洲时段 price action、residual 才决定最终方向。
```

## 目标

为 `p3.c56.asia_risk.v2.3` 准备可消费的派生指标，让下游可以区分：

```text
BTC 亚洲时段自身强弱
JPY carry unwind pressure
CNH / 港股科技压力
Korea premium demand / stress / dislocation
HK BTC ETF flow 区域机构资金 proxy
BTC 对亚洲风险/顺风的接受、拒绝、反证
```

## 范围

### BTC 亚洲时段

```text
asia_session_btc_return_4h
asia_session_btc_return_8h
asia_session_btc_return_24h
asia_session_btc_return_4h_z
asia_session_btc_return_8h_z
asia_session_btc_volume_z_30d
asia_session_btc_realized_vol_z_30d
asia_session_downside_vol_z_30d
asia_session_high_break_flag
asia_session_low_break_flag
asia_session_vwap_distance_z
asia_session_range_position
asia_vs_us_session_return_spread
asia_vs_eu_us_volume_share
asia_session_trend_score
```

### JPY Carry

```text
usdjpy_return_4h
usdjpy_return_24h
usdjpy_return_z_60d
jpy_strength_shock_z
jgb_yield_shock_z
nikkei_downside_z
jpy_carry_unwind_pressure
```

### CNH / HK / Asia Equity

```text
usdcnh_return_4h
usdcnh_return_24h
usdcnh_return_z_60d
hstech_return_1d
hsi_return_1d
cnh_devaluation_pressure
asia_equity_downside_pressure
risk_off_pressure_score
```

### Korea Premium / HK ETF

```text
korea_premium_index
korea_premium_z_90d
korea_premium_change_24h_z
korea_premium_change_3d_z
korea_premium_state
hk_btc_etf_flow_1d_z
hk_btc_etf_flow_5d_z
regional_demand_score
```

### BTC Response

```text
asia_expected_btc_return_24h
asia_risk_residual_24h
asia_risk_residual_z_90d
btc_response_score
```

## Proxy 规则

```text
korea_premium tier_1:
  CryptoQuant Korea Premium Index

korea_premium tier_2_proxy:
  Upbit BTC/KRW / (Binance BTCUSDT * USDKRW) - 1

hk_btc_etf_flow tier_1:
  CoinGlass HK BTC ETF flow history

BTC Asia session:
  Binance/OKX 1h 或 15m kline 聚合 UTC+8 亚洲交易窗口
```

## 数据质量规则

```text
if FX data stale > 30m during Asia active window:
  disable usdjpy_return_4h and usdcnh_return_4h
  data_quality_flags += ["asia_fx_fast_data_stale"]

if equity market closed:
  use futures/proxy only
  asia_equity_downside_pressure contribution capped

if korea_premium unavailable:
  use proxy if possible
  proxy_flags += ["korea_premium_proxy_used"]

if hk_etf_flow unavailable:
  hk_btc_etf_flow_score = 0
  proxy_flags += ["hk_etf_flow_missing"]

if BTC kline missing or stale:
  disable confirmed signal inputs
  data_quality_flags += ["btc_response_unavailable"]
```

## DoD

- [ ] 上述派生指标可写入 SQLite，并被 P2/P3 消费。
- [ ] 原始亚洲风险 level 指标保留为 context，不直接破坏现有数据源。
- [ ] `asia_session_btc_return_4h/8h`、VWAP/range、break flags 可输出。
- [ ] `jpy_carry_unwind_pressure`、`cnh_devaluation_pressure`、`risk_off_pressure_score` 可输出。
- [ ] `korea_premium_state` 至少支持 missing/proxy/neutral 状态，不阻断模块。
- [ ] `asia_expected_btc_return_24h`、`asia_risk_residual_24h`、`asia_risk_residual_z_90d` 可输出。
- [ ] BTC kline 缺失时不允许下游 confirmed bullish / bearish。
- [ ] P1 采集、SQLite 持久化与历史窗口测试通过。

## 关联任务

- P2-C36
- P3-C51
- P8-C28
- P9-C33
