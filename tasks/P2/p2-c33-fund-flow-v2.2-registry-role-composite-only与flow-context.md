# P2-C33 / Fund Flow v2.2 registry role、composite-only 与 flow-context

## 状态

DONE

## Phase

P2 Radar 指标与模块层

## 背景

`fund_flow` 已完成 P2-C23 的 ETF 绝对方向与边际改善语义前移，避免把 ETF 净流出收窄误写成 bullish。但 v2.2 要进一步把 P2 从简单加权评分升级成状态机输入层：原始 level 只提供上下文，真正参与状态机的是 ETF 多窗口、稳定币 regime、交易所供给 z-score 与 BTC response residual。

## 目标

为 `fund_flow.v2.2` 建立 P2 registry 契约：

```text
原始资金流 level 不直接做单因子方向判断；
P2 只负责提供角色、质量、窗口、语义边界和状态机输入。
```

## 指标角色调整

原始 level 降级：

```text
stablecoin_supply                   -> composite_only
stablecoin_total_mcap               -> composite_only
btc_exchange_balance                -> context_only
exchange_balance_delta_1d_proxy     -> supply_pressure_context
etf_net_flow_usd                    -> fast_flow_signal
```

状态机输入：

```text
etf_flow_1d_z_60d                   -> fast_flow_signal
etf_flow_3d_z_60d                   -> demand_momentum
etf_flow_7d_z_60d                   -> demand_persistence
etf_inflow_streak_days              -> persistence_bonus
etf_outflow_streak_days             -> pressure_warning
etf_flow_acceleration_3d            -> demand_acceleration
etf_flow_reversal_2d                -> reversal_warning
etf_flow_shock_flag                 -> shock_warning

stablecoin_mcap_change_7d_z_120d    -> liquidity_regime
stablecoin_mcap_change_30d_z_180d   -> liquidity_regime
ssr_z_180d                          -> liquidity_buying_power

btc_exchange_netflow_z_60d          -> supply_pressure_context
btc_exchange_netflow_z_180d         -> supply_pressure_context
large_single_transfer_flag          -> data_quality_context
internal_transfer_risk_flag         -> data_quality_context
exchange_flow_confirmed             -> confirmed_supply_signal

fund_flow_residual_z_60d            -> btc_response_veto
```

## P2 输出增量

模块级 payload 增加：

```json
{
  "fund_flow_profile_version": "p2.c33.fund_flow.v2.2",
  "fund_flow_absolute_direction": "bearish|neutral|bullish",
  "fund_flow_marginal_direction": "worsening|stable|improving|strengthening|weakening",
  "fund_flow_conflict_level": "none|low|medium|high",
  "fund_flow_state": "bullish|bullish_but_weakening|neutral_mixed|bearish_but_improving|bearish",
  "etf_source_quality": {
    "source_count": 0,
    "cross_source_diff_pct": 0,
    "mismatch": false
  }
}
```

ETF feature 继续保留：

```json
{
  "flow_state": "bearish_outflow|neutral|bullish_inflow",
  "marginal_state": "pressure_easing|pressure_worsening|inflow_strengthening|inflow_weakening|stable|null",
  "marginal_direction": "improving|worsening|strengthening|weakening|stable"
}
```

## 禁止项

- ETF 净流出不得输出 `direction=bullish`。
- 稳定币供应 level 不得单独输出强 bullish。
- 单日交易所余额下降不得直接输出 confirmed bullish。
- `large_single_transfer_flag=true` 时不得把 exchange outflow/inflow 作为 confirmed supply signal。

## DoD

- [ ] `fund_flow` registry 覆盖 v2.2 指标角色与 horizon tags。
- [ ] 原始 level 指标不直接成为 driver。
- [ ] ETF 绝对方向与边际方向保留 P2-C23 防误导契约。
- [ ] P2 module payload 输出 source quality、conflict level 和 state。
- [ ] P2 audit 能看出 fast / confirmation / rejection 输入字段是否齐备。

## 关联任务

- P1-C50
- P3-C48
- P9-C30
