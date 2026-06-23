# P8-C38 Radar Runtime Snapshots 与 Replay

状态：TODO

## 背景

当前 BTC 主卡和 14 个 radar modules 主要跟随 full chain 同步更新，这不符合真实业务节奏。快变量、确认变量、慢变量的信息半衰期不同，必须像 Event Window 一样持久化分频 runtime snapshot。

## 目标

新增 Radar Runtime 持久化层，用 SQLite 保存：

```text
radar runtime daemon snapshot
module runtime snapshot
cockpit aggregate snapshot
module freshness / cadence / health
manual full sweep lineage
```

## 核心表建议

```text
radar_runtime_snapshots
radar_module_runtime_snapshots
radar_cockpit_runtime_snapshots
radar_runtime_scheduler_state
radar_runtime_health_events
```

## DoD

1. 每个 radar module 可以独立保存最新 snapshot。
2. snapshot 包含 `module_id / asof_ts / cadence_group / ttl_sec / freshness_state / participates_in_cockpit`。
3. BTC cockpit aggregate snapshot 可追踪所消费的 module snapshot ids。
4. 支持按 timestamp / snapshot_id replay。
5. stale module 不覆盖 fresh module。
6. manual full sweep 与 daemon tick lineage 分开。
7. 不破坏现有 P8 payload/replay 表。
