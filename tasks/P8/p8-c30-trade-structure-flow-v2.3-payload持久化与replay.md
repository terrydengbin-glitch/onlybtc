# P8-C30 / Trade Structure Flow v2.3 payload 持久化与 replay

## 状态

DONE

## Phase

P8 SQLite、历史数据与持久化

## 背景

`trade_structure_flow v2.3` 会新增多周期、状态优先级、scores、states、data_quality_flags、proxy_flags 与 invalidation_conditions。SQLite 与 replay 需要完整保留结构化 payload，确保 dashboard、radar detail、历史回放和审计报告读取同一份契约。

## 目标

保证以下结构在 P3/P4.5/P9/P5 中可持久化与回放：

```text
trade_structure_state
signal_stage
btc_implication
scores
multi_horizon
states
support_drivers / pressure_drivers / conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
trade_structure_flow_v23
```

## DoD

- [ ] P3 module payload 写入 SQLite 后可完整读取。
- [ ] History replay 不丢失 v2.3 嵌套结构。
- [ ] 旧 v1/v2 payload replay 兼容，不因缺少 v2.3 字段报错。
- [ ] 审计脚本可检查 v2.3 关键字段存在性。
- [ ] Run once 后 SQLite 中能查到 `trade_structure_flow_v23` 或等价契约。

## 关联任务

- P3-C53
- P9-C35
- P5-C56
