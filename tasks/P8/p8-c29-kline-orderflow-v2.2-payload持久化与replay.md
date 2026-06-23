# P8-C29 / Kline Orderflow v2.2 payload 持久化与 replay

## 状态

DONE

## Phase

P8 SQLite、历史数据与持久化

## 背景

`kline_orderflow v2.2` 会新增多层结构化 payload，包括 `trend_sensitivity_score`、`trend_reliability_score`、`volatility_regime`、`key_levels`、`drivers`、`invalidation_conditions`。这些字段需要稳定持久化，并支持 history replay 与 radar detail 查询。

## 持久化字段

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
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
rejection_flags
data_quality_flags
invalidation_conditions
```

## Replay 要求

```text
history replay:
  能重放 v2.2 payload

legacy compatibility:
  旧版 kline_orderflow 字段仍可读取

missing fields:
  返回稳定空值，不破坏 API / 前端
```

## DoD

- [ ] v2.2 payload 可完整写入 radar module JSON。
- [ ] replay 查询能返回 v2.2 字段。
- [ ] 旧版 kline_orderflow 历史记录不因新字段缺失而失败。
- [ ] SQLite 相关测试通过。

## 关联任务

- P3-C52
- P9-C34
- P5-C55
