# P9-C35 / Trade Structure Flow v2.3 API 透传与契约

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

FastAPI dashboard 和 radar detail 需要透传 `trade_structure_flow v2.3` 的状态机、scores、多周期结论和解释边界，避免前端继续依赖旧的 aggressive_flow/liquidation 简化字段。

## 目标

API 透传：

```text
semantic_profile_version
module_direction
module_score
confidence_score
signal_stage
trade_structure_state
btc_implication
scores
multi_horizon
states
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
trade_structure_flow_v23
```

## DoD

- [ ] `/api/p45/radar-modules/trade_structure_flow` 返回 v2.3 字段。
- [ ] `/api/p45/dashboard/latest` 的 radar module 列表包含 v2.3 摘要字段。
- [ ] 旧字段保持兼容，前端已有 trade_structure_flow 组件不崩。
- [ ] API 测试覆盖 detail/dashboard 两条路径。
- [ ] 缺字段时 graceful fallback，不返回 500。

## 关联任务

- P3-C53
- P8-C30
- P5-C56
