# P2-C39 / Derivatives Crowding v2.5 Registry context-only 与趋势接受治理

## 状态

DONE

## Phase

P2 Radar 指标与模块层

## 背景

`derivatives_crowding v2.5` 必须防止 funding、OI、多空比、清算 spike 单独进入 BTC 方向判断。P2 需要把原始 level 降级为 context，并只允许趋势先验、BTC response、OI price efficiency、funding/basis 标准化、清算反应和 residual 等组合字段参与方向。

## 目标

原始字段降级：

```text
btc_funding_rate                         -> context_only
btc_open_interest                        -> context_only
global_long_short_account_ratio          -> context_only
top_trader_long_short_account_ratio      -> context_only
top_trader_long_short_position_ratio     -> context_only
liquidation_long_usd                     -> context_only
liquidation_short_usd                    -> context_only
```

参与方向字段：

```text
btc_trend_prior_score
btc_response_z_15m
btc_response_z_1h
btc_response_z_4h
oi_impulse_z_15m
oi_impulse_z_1h
oi_price_efficiency
oi_participation_type_score
funding_rate_8h_equiv_z
funding_acceleration_z_24h
predicted_funding_z
funding_persistence_score
basis_impulse_z_1h
perp_spot_premium_z
basis_acceptance_score
top_vs_global_positioning_gap_z
retail_crowding_score
smart_money_divergence_score
liquidation_impulse_z_15m
liquidation_followthrough_score
liquidation_absorption_score
derivatives_acceptance_score
derivatives_rejection_score
derivatives_residual_z
```

## 语义边界

- `crowding_fragility_score` 高不等于 bearish。
- Funding positive / negative 不允许单独触发方向。
- OI rising 不允许单独触发方向。
- Long/short ratio 只能作为 positioning context 或组合输入。
- Liquidation spike 必须通过 follow-through / absorbed 后才可影响方向。

## DoD

- [ ] 原始 level 全部 `affects_signal=false`。
- [ ] v2.5 派生字段 role、weight、driver eligibility 完整。
- [ ] top trader account ratio 与 top trader position ratio 分开治理。
- [ ] `oi_price_efficiency` / `derivatives_residual_z` 参与方向。
- [ ] Registry 输出可被 P3-C54 消费。
- [ ] 回归测试确认 funding/OI/long-short/liquidation 单因子不会成为 driver。

## 依赖

- P1-C56
- P3-C54
- P9-C36
