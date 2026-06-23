# P8-C28 / Asia Risk v2.3 payload 持久化与 replay

## 状态

DONE

## Phase

P8 SQLite、历史数据与持久化

## 背景

`asia_risk.v2.3` 会输出多层结构化 payload，包括 scores、btc_response、states、drivers、flags、invalidation_conditions。P8 需要保证这些字段可被 SQLite 保存、历史回放和 dashboard snapshot 消费。

## 目标

确保 `p3.c56.asia_risk.v2.3` payload 在当前表结构中稳定持久化，并兼容历史 replay。

## 持久化字段

```text
semantic_profile_version
module_direction
module_score_signed
confidence_score
signal_stage
asia_risk_state
btc_implication
scores
btc_response
states
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
```

## Replay 边界

```text
missing optional hk_etf_flow:
  replay 不失败，返回 proxy_flags

missing korea_premium:
  replay 不失败，korea_premium.state = missing

missing btc_response:
  module_direction = neutral
  signal_stage = none
```

## DoD

- [ ] `module_json_outputs` 可保存 v2.3 完整 payload。
- [ ] Dashboard snapshot / replay 不丢失 `asia_risk_state`、`signal_stage`、`btc_response`。
- [ ] optional 字段缺失不导致 JSON schema 崩溃。
- [ ] replay 测试覆盖 missing/proxy 场景。
- [ ] SQLite 相关测试通过。

## 关联任务

- P3-C51
- P9-C33
- P5-C54
