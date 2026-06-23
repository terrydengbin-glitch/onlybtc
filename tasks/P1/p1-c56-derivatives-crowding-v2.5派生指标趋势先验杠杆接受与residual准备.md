# P1-C56 / Derivatives Crowding v2.5 派生指标、趋势先验、杠杆接受与 residual 准备

## 状态

DONE

## Phase

P1 数据源接入与派生层

## 背景

`derivatives_crowding` 需要从“funding / OI / long-short / liquidation 拥挤度模块”升级为 `p3.c60.derivatives_crowding.v2.5` 的 Derivatives Trend Acceptance Engine。核心是判断 BTC 当前趋势是否被杠杆市场接受、放大、削弱或反证，而不是把 funding、OI、多空比、清算 spike 当作单独方向。

## 目标

为 P2/P3 准备可消费的派生指标：

```text
trend_prior:
  btc_trend_state
  trend_strength_z
  trend_confidence
  trend_age_bars
  volatility_regime

funding:
  funding_rate_8h_equiv
  funding_rate_8h_equiv_z
  funding_shock_z_8h
  funding_acceleration_z_24h
  predicted_funding_z
  funding_time_to_settlement_min
  funding_persistence_count

open_interest:
  oi_impulse_z_15m
  oi_impulse_z_1h
  oi_impulse_z_4h
  oi_price_efficiency
  oi_participation_type
  oi_participation_type_score
  oi_source_coverage_score

positioning:
  global_account_ratio_z
  top_account_ratio_z
  top_position_ratio_z
  top_vs_global_positioning_gap_z
  retail_crowding_score
  smart_money_divergence_score

liquidation:
  liquidation_impulse_z_15m
  liquidation_impulse_z_1h
  post_liquidation_return_15m
  post_liquidation_return_1h
  liquidation_followthrough_score
  liquidation_absorption_score

btc_response:
  btc_response_z_15m
  btc_response_z_1h
  btc_response_z_4h
  derivatives_pressure_z
  derivatives_expected_return_z
  derivatives_residual_z
  derivatives_acceptance_score
  derivatives_rejection_score
```

## 实现要点

- Funding 必须标准化为 8h equivalent，不能直接使用 raw funding。
- 变化类指标优先使用 robust z-score：rolling median + MAD。
- Binance OI 历史只有近月窗口时，60d/90d z-score 必须来自本地持久化样本；不足时输出 data quality flag。
- `trend_prior` 优先消费 `kline_orderflow` / `btc_total_state`，缺失时用 BTC slope 和 realized volatility fallback。
- OI 必须通过 `oi_price_efficiency` 和 `oi_participation_type` 表达价格接受。

## DoD

- [ ] P1 输出 v2.5 所需核心派生指标。
- [ ] 原始 funding / OI / long-short / liquidation level 仍保留，但不作为方向派生。
- [ ] Funding 统一为 8h equivalent。
- [ ] `oi_price_efficiency` 与 `oi_participation_type` 可用于 P3 状态机。
- [ ] liquidation 区分 follow-through 与 absorbed。
- [ ] 本地历史不足时输出 `insufficient_local_derivatives_history`。
- [ ] 单交易所 OI 输出 `single_exchange_oi` proxy flag。
- [ ] 测试覆盖 P1 派生与 fallback。

## 依赖

- P2-C39
- P3-C54
- P8-C31
- P9-C36

## Done Notes

- Implemented derivatives v2.5 P1 metrics for trend prior, BTC response z-scores, funding 8h-equivalent normalization, OI participation proxies, positioning scores, liquidation impulse/response and standardized residual.
- Raw funding/OI/long-short/liquidation level fields remain context inputs; v2.5 direction uses acceptance/residual fields.
- Validation: targeted P3 tests, P45 projection tests, broad backend suite and frontend build passed.
