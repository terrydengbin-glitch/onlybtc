# P9-C32 / BTC Adoption v2.3 API 透传与契约

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

`btc_adoption.v2.3` 的核心字段需要透传给 Dashboard、Radar Detail、Evidence 与 P4.5 报告层。API 不应只返回旧版 module score，而要返回 fast/core/regime、状态机、flags 和 invalidation conditions。

## 目标

FastAPI dashboard/radar detail API 完整透传 `p3.c54.btc_adoption.v2.3` 合约。

## API 字段

```text
semantic_profile_version
module_direction
module_score
confidence_score
timeframe
signal_stage
btc_adoption_state
btc_implication
scores.fast_trend_score
scores.core_confirmation_score
scores.regime_context_score
scores.activity_quality_score
scores.settlement_demand_score
scores.fee_mempool_score
scores.network_security_score
scores.l2_adoption_score
scores.btc_response_score
scores.data_quality_penalty
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

## 契约边界

```text
signal_stage=early_warning 不应被 API 映射为 confirmed direction
signal_stage=conflict 时 module_direction 默认 neutral，除非 P3 已明确输出极端 btc_response
raw active address / tx count / hashrate level 不作为 headline driver
```

## DoD

- [ ] `/api/dashboard` 或当前 dashboard 聚合 API 可返回 v2.3 字段。
- [ ] Radar Detail API 可完整返回 scores/states/flags/invalidation。
- [ ] 缺失字段时返回稳定空值，不导致前端崩溃。
- [ ] API 测试覆盖 v2.3 payload。
- [ ] FastAPI 测试通过。

## 关联任务

- P3-C50
- P8-C27
- P4.5-C36
- P5-C53
