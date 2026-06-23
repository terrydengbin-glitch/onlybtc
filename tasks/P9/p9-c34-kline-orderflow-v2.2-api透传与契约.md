# P9-C34 / Kline Orderflow v2.2 API 透传与契约

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

`kline_orderflow v2.2` 的核心字段需要透传给 Dashboard、Radar Detail、Evidence 和 P4.5 报告层。API 不能只返回旧版 module score，而要返回 sensitivity/reliability、VWAP/range key levels、主动流接受/拒绝状态和 invalidation conditions。

## API 字段

```text
semantic_profile_version
module_direction
module_score
trend_sensitivity_score
trend_reliability_score
confidence_score
signal_stage
volatility_regime
kline_orderflow_state
btc_implication
scores
key_levels
drivers
invalidation_conditions
```

## 契约边界

```text
early_warning 不应被 API 映射为 confirmed direction
taker buy ratio 高不应被 headline 解释为 BTC bullish
taker sell ratio 高不应被 headline 解释为 BTC bearish
shock_vol 下如果未 confirmed，API 必须保留 stage 语义
```

## DoD

- [ ] Dashboard 聚合 API 可返回 v2.2 字段或等价结构。
- [ ] Radar Detail API 可完整返回 scores/key_levels/drivers/invalidation。
- [ ] 缺失字段返回稳定空值，不导致前端崩溃。
- [ ] API 测试覆盖 v2.2 payload。
- [ ] FastAPI 测试通过。

## 关联任务

- P3-C52
- P8-C29
- P4.5-C38
- P5-C55
