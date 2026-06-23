# P2-C36 / Asia Risk v2.3 Registry context-only 与 BTC response 治理

## 状态

DONE

## Phase

P2 雷达指标注册与语义治理

## 背景

`asia_risk v2.3` 不允许 USDJPY、USDCNH、Nikkei、HSTECH 等原始 level 直接决定 BTC 方向。P2 需要把原始 level 降级为 context/composite only，并只允许派生后的 pressure、regional demand、BTC response 指标参与状态机。

## 目标

重构 `asia_risk` 的 Registry 规则，让模块语义符合：

```text
risk_off_pressure_score 只表示风险强度，不等于 bearish。
BTC response 和 Asia session price action 才能决定 module_direction。
```

## 原始字段降级

```text
usdjpy              -> context_only
usdcnh              -> context_only
nikkei              -> context_only
topix               -> context_only
hang_seng_tech      -> context_only
jgb_10y             -> context_only
hibor               -> context_only
```

## 方向可消费字段

```text
asia_session_trend_score
asia_session_btc_return_4h_z
asia_session_btc_return_8h_z
asia_session_vwap_distance_z
asia_session_range_position

risk_off_pressure_score
jpy_carry_unwind_pressure
cnh_devaluation_pressure
asia_equity_downside_pressure

regional_demand_score
korea_premium_state
hk_btc_etf_flow_1d_z
hk_btc_etf_flow_5d_z

btc_response_score
asia_expected_btc_return_24h
asia_risk_residual_24h
asia_risk_residual_z_90d
```

## Registry 语义要求

```text
raw FX/equity/yield level:
  affects_signal = false
  driver_eligible = false
  role = context_only

risk pressure metrics:
  affects_signal = false or risk_context only
  affects_risk_flags = true
  role = pressure_context

BTC response metrics:
  affects_signal = true
  driver_eligible = true
  role = btc_response_confirmation

regional demand metrics:
  affects_signal = true
  driver_eligible = true
  role = regional_demand_context
```

## DoD

- [ ] 原始 USDJPY/USDCNH/Nikkei/HSTECH/JGB/HIBOR 不再直接参与 bullish/bearish 分数。
- [ ] `risk_off_pressure_score` 不被映射为直接 bearish。
- [ ] BTC response / residual 相关字段可成为 driver。
- [ ] Korea premium proxy 标记为 proxy 时不能单独触发 confirmed signal。
- [ ] P2 radar quality 报告中 `asia_risk` 覆盖率稳定，缺失 optional 不导致模块失败。
- [ ] P2/P3 相关测试通过。

## 关联任务

- P1-C53
- P3-C51
- P9-C33
