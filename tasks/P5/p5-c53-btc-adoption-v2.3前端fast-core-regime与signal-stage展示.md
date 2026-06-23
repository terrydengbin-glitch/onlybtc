# P5-C53 / BTC Adoption v2.3 前端 Fast/Core/Regime 与 Signal Stage 展示

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

`btc_adoption.v2.3` 输出 fast/core/regime 三层分数、状态机、BTC response、proxy flags 与 invalidation conditions。前端 Radar Detail 需要避免把 early warning、context 或 hashrate/Lightning 慢变量展示成强方向。

## 目标

为 `btc_adoption` 增加 v2.3 专属展示：

```text
Signal / State
Fast Layer
Core Confirmation
Regime Context
Activity / Settlement
Fee / Mempool
Security / Lightning
BTC Response
Governance
```

## 展示优先级

```text
signal_stage
-> btc_adoption_state
-> btc_implication
-> module_direction
-> module_score
```

`early_warning`、`conflict`、`activity_spike_untrusted` 使用观察/冲突/低置信样式，不使用 confirmed bullish/bearish 强色。

## 区块字段

### Signal / State

```text
signal_stage
btc_adoption_state
btc_implication
module_direction
module_score
confidence_score
```

### Fast Layer

```text
fast_trend_score
btc_response_score
fee_mempool_score
short_activity_impulse_score
short_settlement_impulse_score
```

### Core Confirmation

```text
core_confirmation_score
activity_quality_score
settlement_demand_score
nvt_improvement_score
price_acceptance_score
```

### Regime Context

```text
regime_context_score
network_security_score
l2_adoption_score
miner_pressure_score
network_health_score
```

### States / Governance

```text
states.activity
states.settlement
states.fee_mempool
states.security
states.lightning
states.btc_response_confirmation
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
```

## DoD

- [ ] Radar Detail 显示 `btc_adoption.v2.3` 专属区块。
- [ ] fast/core/regime 三层分开展示。
- [ ] `signal_stage=conflict` 与 `activity_spike_untrusted` 不被显示成强方向。
- [ ] raw activity、hashrate、Lightning level 只显示为 context。
- [ ] proxy/data quality/invalidation 展示完整。
- [ ] 前端空字段容错，不因 v2.3 字段缺失崩溃。
- [ ] `npm run build` 通过。

## 关联任务

- P9-C32
- P4.5-C36
