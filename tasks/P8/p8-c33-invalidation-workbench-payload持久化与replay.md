# P8-C33 Invalidation Workbench payload 持久化与 replay

状态：DONE

## 目标

确保 `invalidation_workbench.v2` 随 P4.5 final payload 持久化到 SQLite，并支持 latest 与 history replay 读取同一份验证台快照。

## 持久化范围

```text
final_payload.invalidation_workbench
schema_version
run_lineage
current_thesis
validation_state
scores
btc_response
module_evidence_matrix
rule_groups
triggered_rules
armed_rules
blocked_rules
timeline
payload_hash / cockpit_payload_hash
```

## Replay 要求

1. 按 `final_run_id` 查询时返回当时对应的 `invalidation_workbench`。
2. 按 latest 查询时返回最新 final payload 中的 `invalidation_workbench`。
3. history replay 不允许重新计算当前规则覆盖历史结果。
4. `cockpit_payload_hash` 用于追踪 Workbench 输入是否来自同一份 BTC Cockpit。

## DoD

1. run once 后 SQLite final payload 中包含 `invalidation_workbench.schema_version = p45.invalidation_workbench.v2`。
2. `/api/p45/invalidation/latest` 与 SQLite latest payload 一致。
3. history replay 能读到历史 `invalidation_workbench`。
4. replay 时 `validation_state` 与当时 payload 一致，不被当前规则重算污染。
5. P8 persistence / replay targeted tests 通过。
