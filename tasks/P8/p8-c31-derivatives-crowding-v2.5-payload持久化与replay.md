# P8-C31 / Derivatives Crowding v2.5 payload 持久化与 replay

## 状态

DONE

## Phase

P8 SQLite 持久化与 replay

## 背景

`derivatives_crowding v2.5` 会新增 trend_prior、scores、states、hysteresis、proxy_flags、data_quality_flags 与 invalidation_conditions。SQLite 与 replay 需要完整保留结构化 payload，确保 dashboard、radar detail、历史回放和审计报告读取同一份契约。

## 范围

- `module_json_outputs.payload`
- `feature_values.metadata_json`
- radar detail replay
- dashboard latest
- historical run replay

## DoD

- [ ] v2.5 payload 完整落库。
- [ ] replay 可恢复 `trend_prior`、`scores`、`states`、`derivatives_state`。
- [ ] 历史 v1/v2 字段兼容。
- [ ] SQLite 查询不丢失 nested JSON。
- [ ] 审计脚本能验证 latest run 与 replay run 一致。

## 依赖

- P3-C54
- P9-C36
- P5-C57
