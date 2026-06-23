# P8-C27 / BTC Adoption v2.3 Payload 持久化与 Replay

## 状态

DONE

## Phase

P8 SQLite、历史数据与持久化

## 背景

`btc_adoption.v2.3` 输出 fast/core/regime 分数、状态机、BTC response residual、proxy/data quality flags 和 invalidation conditions。SQLite 与 replay 必须完整保存这些结构，避免历史回放时丢失语义。

## 目标

保证 `btc_adoption` v2.3 的 P3 semantic payload 可完整写入、读取、回放，并被 P4.5/P9/P5 消费。

## 范围

```text
semantic_profile_version
module_direction
module_score
confidence_score
signal_stage
btc_adoption_state
btc_implication
timeframe
scores
states
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
```

## DoD

- [ ] P3 输出的 v2.3 payload 可完整写入 SQLite。
- [ ] replay 查询可取回完整 payload，不丢失 nested scores/states。
- [ ] 旧版 `btc_adoption` payload 仍兼容，不导致历史回放失败。
- [ ] P8 repository 查询测试通过。
- [ ] run once 后 audit report 可看到 v2.3 payload。

## 关联任务

- P1-C52
- P2-C35
- P3-C50
- P9-C32
