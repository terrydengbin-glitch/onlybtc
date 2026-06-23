# P9-C36 / Derivatives Crowding v2.5 API 透传与契约

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

FastAPI dashboard 和 radar detail 需要透传 `derivatives_crowding v2.5` 的 trend prior、趋势接受分数、拥挤脆弱分数、squeeze risk、states 与解释边界，避免前端继续依赖旧的 funding/OI/crowding 简化字段。

## 输出字段

```text
semantic_profile_version
signal_stage
derivatives_state
btc_implication
trend_prior
scores
states
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
derivatives_crowding_v25
```

## DoD

- [ ] `/api/p45/radar-modules/derivatives_crowding` 透传 v2.5 contract。
- [ ] `/api/p45/dashboard/latest` 透传 `derivatives_crowding_explanation`。
- [ ] API 保持旧字段兼容。
- [ ] 集成测试覆盖 detail 和 dashboard。
- [ ] 缺失 v2.5 payload 时优雅 fallback 到旧 contract。

## 依赖

- P3-C54
- P8-C31
- P5-C57
