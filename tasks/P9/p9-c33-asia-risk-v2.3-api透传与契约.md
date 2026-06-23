# P9-C33 / Asia Risk v2.3 API 透传与契约

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

`asia_risk.v2.3` 的核心字段需要透传给 Dashboard、Radar Detail、Evidence 和 P4.5 报告层。API 不应只返回旧版 module score，而要返回 risk pressure、regional demand、BTC response、signal stage、invalidation conditions。

## 目标

FastAPI dashboard/radar detail API 完整透传 `p3.c56.asia_risk.v2.3` 契约。

## API 字段

```text
semantic_profile_version
module_direction
module_score_signed
confidence_score
signal_stage
asia_risk_state
btc_implication

scores.risk_off_pressure_score
scores.asia_session_trend_score
scores.regional_demand_score
scores.btc_response_score
scores.jpy_carry_unwind_pressure
scores.cnh_devaluation_pressure
scores.asia_equity_downside_pressure
scores.data_quality_penalty

btc_response.asia_session_btc_return_4h_z
btc_response.asia_session_btc_return_8h_z
btc_response.asia_session_vwap_distance_z
btc_response.asia_session_range_position
btc_response.asia_risk_residual_z_90d
btc_response.low_break_flag
btc_response.high_break_flag

states.jpy_carry
states.cnh_pressure
states.asia_equities
states.korea_premium
states.hk_etf_flow
states.btc_response_confirmation

support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
```

## 契约边界

```text
signal_stage=early_warning 不应被 API 映射为 confirmed direction
risk_off_pressure_score 高不应被 headline 文案解释为 BTC bearish
korea_premium proxy 不应被展示为精确官方 premium
missing hk_etf_flow 应稳定返回空值与 proxy flag
```

## DoD

- [ ] Dashboard 聚合 API 可返回 `asia_risk_v23` 或等价 v2.3 字段。
- [ ] Radar Detail API 可完整返回 scores/states/btc_response/flags/invalidation。
- [ ] 缺失字段时返回稳定空值，不导致前端崩溃。
- [ ] API 测试覆盖 v2.3 payload。
- [ ] FastAPI 测试通过。

## 关联任务

- P3-C51
- P8-C28
- P4.5-C37
- P5-C54
