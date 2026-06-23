# P8-C37 / Event Window Market Probe 持久化与 Replay

## 状态
DONE

## 背景

Event Window 的 UI、API、HTML 审计都应来自 SQLite snapshot，而不是内存或临时 JSON。当前 source snapshot 已有持久化，但市场冲击探针、daemon heartbeat、multi-window shock evidence 需要可回放，才能解释“为什么当时没有预警”。

## 目标

为 Event Window market probe 与 shock evidence 增加 SQLite 持久化与 replay 能力。

## 建议表 / payload

可以新增独立表，也可以扩展现有 Event Watchtower snapshot 子表：

```text
event_market_probes
event_daemon_heartbeats
event_shock_evidence
```

最低字段：

```text
snapshot_id
probe_id / evidence_id
collected_at
source
symbol
payload_json
payload_hash
freshness_sec
data_quality_flags
```

## 关键要求

1. 每次 market probe 都要可追溯。
2. 每个 shock item 都能追到对应 market probe 或 fallback metric。
3. replay 时不重新抓取行情。
4. HTML 1/2/3 bundle 能显示同一 snapshot 下的 market probe evidence。

## DoD

- [x] market probe snapshot 写入 SQLite。
- [x] daemon heartbeat 写入 SQLite 或可从 snapshot chain 推导。
- [x] shock evidence 写入 SQLite，包含多窗口 return。
- [x] `/api/event-window/history` 可返回历史 market probe / shock evidence 摘要。
- [x] replay 指定 snapshot_id 时不调用外部数据源。
- [x] 审计 HTML 显示 market probe payload_hash 和 source_lineage。

## 依赖

- P1-C69
- P2-C41
- P7-C21


