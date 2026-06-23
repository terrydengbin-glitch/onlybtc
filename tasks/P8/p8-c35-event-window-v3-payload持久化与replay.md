# P8-C35 / Event Window v3 Payload、Source Fetch 与 Replay

## 状态

TODO

## Phase

P8 SQLite、历史数据与持久化

## 当前断点

当前已经有事件业务表，但缺少 source-fetch 级别的审计明细。用户无法区分：

```text
live official success
official failed -> fallback
provider missing key
parser failed
rate limited
network timeout
```

## 目标

补齐 Event Window 专属 source fetch lineage，让子页面和审计报告能明确显示“是否真正拉到数据”。

## 新增/扩展字段

可复用现有表，也可新增轻量表：

```text
event_source_fetches:
  fetch_id
  source_id
  source_tier
  endpoint_url
  started_at
  finished_at
  status = success|partial|failed|fallback_used|skipped
  http_status
  error_code
  error_message
  payload_hash
  parsed_item_count
  fallback_used
```

## DoD

- [ ] 每个 connector fetch 都有 fetch lineage。
- [ ] API 可返回最新 source diagnostics。
- [ ] fallback 使用必须可追溯到失败的 live source。
- [ ] replay 能复现当时 event_window_v3 和 source fetch 状态。
- [ ] 子页面可显示 source mode：live / partial / fallback / failed。
- [ ] 测试覆盖 live success、fallback、network fail、parser fail、history replay。

## 依赖

- P1-C57
- P1-C58
- P1-C59
- P9-C43
