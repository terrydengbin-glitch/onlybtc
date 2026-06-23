# P2-C34 / Onchain Valuation v2.2 Registry 慢快变量与 Proxy Governance

## 状态

DONE

## Phase

P2 Radar 指标与模块层

## 背景

`onchain_valuation.v2.2` 不能再让 MVRV、NUPL、Realized Price、STH/LTH 成本位等原始 level 指标直接输出单因子 bullish/bearish。P2 需要把指标角色改成可组合语义：慢变量服务 `regime_score`，快变量服务 `trend_delta_score`，proxy 只做辅助。

## 目标

为 `onchain_valuation` 建立 v2.2 registry 角色：

```text
slow regime context
fast trend delta
cost basis reaction
profit realization delta
realized cap impulse
btc response veto
proxy governance
```

## Registry 角色调整

原始 level 改为 context/composite：

```text
realized_price       -> context_only
sth_cost_basis       -> context_only
lth_cost_basis       -> context_only
realized_cap         -> composite_only
mvrv_zscore          -> valuation_regime
mvrv_ratio           -> valuation_regime
nupl                 -> valuation_regime
sopr                 -> profit_realization_context
```

真正参与状态机的指标：

```text
btc_vs_sth_cost_basis_pct
btc_vs_sth_cost_basis_z_365d
sth_cost_basis_distance_change_24h
sopr_change_1d
sopr_z_90d
sopr_above_1_streak_days
sopr_below_1_streak_days
sopr_cross_1_direction
realized_cap_impulse_z_180d
onchain_residual_z_90d
```

Proxy 角色：

```text
puell_multiple_proxy        -> miner_pressure_context
miner_pressure_proxy        -> risk_context
whale_pressure_proxy        -> risk_context
sth_cost_basis_proxy        -> proxy_context
lth_cost_basis_proxy        -> proxy_context
```

## 禁止规则

```text
MVRV/NUPL 不允许单独触发 confirmed_signal
SOPR crossing 1 不允许单独触发 confirmed_signal
tier_3_proxy 不允许触发 confirmed_signal
whale/miner provider_optional_missing 不允许降低 radar 到 failed
```

## DoD

- [ ] `onchain_valuation` registry 输出 v2.2 指标角色。
- [ ] 原始 level 指标不再直接给短线方向分。
- [ ] 快变量指标进入 P3 semantic profile 的可消费字段。
- [ ] proxy tier 可被 P3/P4.5/P5 识别。
- [ ] MVRV/NUPL 单因子方向误导被测试覆盖。
- [ ] P2 radar 输出保留与旧字段兼容的基础 evidence。

## 关联任务

- P1-C51
- P3-C49
- P4.5-C35
