# P5-C54 / Asia Risk v2.3 前端四区块与 BTC response 展示

## 状态

DONE

## Phase

P5 Vue3 前端展示

## 背景

`asia_risk.v2.3` 前端不能只展示总分或旧版 risk composite。需要把模块拆成四块：Asia session、Risk pressure、Regional demand、BTC response，让用户看到方向为什么由 BTC response 决定。

## 目标

Radar Detail 中为 `asia_risk` 增加 v2.3 专用展示。

## 展示结构

```text
Header:
  module_direction
  module_score_signed
  signal_stage
  asia_risk_state
  btc_implication

Cards:
  Asia Session Trend
  Risk-off Pressure
  Regional Demand
  BTC Response Confirmation

Flags:
  support_drivers
  pressure_drivers
  conflict_drivers
  early_warning_flags
  data_quality_flags
  proxy_flags
  invalidation_conditions
```

## 卡片字段

```text
Asia Session Trend:
  asia_session_btc_return_4h_z
  asia_session_btc_return_8h_z
  asia_session_vwap_distance_z
  asia_session_range_position
  high_break_flag
  low_break_flag

Risk-off Pressure:
  risk_off_pressure_score
  jpy_carry_unwind_pressure
  cnh_devaluation_pressure
  asia_equity_downside_pressure

Regional Demand:
  regional_demand_score
  korea_premium_state
  hk_btc_etf_flow_1d_z
  hk_btc_etf_flow_5d_z

BTC Response:
  btc_response_score
  asia_risk_residual_z_90d
  btc_implication
```

## 文案边界

```text
risk pressure high != bearish
early_warning != confirmed signal
premium proxy != official premium
missing HK ETF flow != module failure
```

## DoD

- [ ] Radar Detail 可以识别 `p3.c56.asia_risk.v2.3`。
- [ ] 前端展示四区块，不再只展示旧版 composite。
- [ ] 缺失 optional 字段时卡片稳定显示空态。
- [ ] `signal_stage=conflict/early_warning` 有清晰标签。
- [ ] `npm run build` 通过。

## 关联任务

- P9-C33
- P4.5-C37
