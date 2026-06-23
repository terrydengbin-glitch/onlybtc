# P7-C15 Event Window v3 Live Source Audit

审计时间：2026-05-28 01:34 Asia/Shanghai

## 结论

结果：PARTIAL PASS。

Event Window v3 已经不是 mock-only，也不是 embedded fallback-only。当前链条可以完成：

- daemon collect once
- SQLite snapshot/source fetch lineage 落库
- `/api/event-window/latest`
- `/api/event-window/sources/status`
- `/api/event-window/sources/fetches`
- 前端 Source Diagnostics / Fetch Lineage 消费

但不是 FULL PASS，因为仍有外部源断点：

- BLS 官方 schedule/ICS 当前返回 403 Access Denied。
- Cleveland Fed nowcast 页面可访问，但当前解析器未提取出 nowcast 数值。
- CME FedWatch 当前未参与非 FOMC active event；FOMC 场景仍需单独复测。
- Actual polling 当前处于 pre-release pending，尚未进入官方 actual 验证窗口。

## Run Once Snapshot

Active event:

- event_type: PCE
- title: Personal Income and Outlays
- release_time_utc: 2026-05-28T12:30:00+00:00
- source: BEA release schedule
- phase: high_alert
- emergency_level: high

Data quality:

- overall_source_mode: partial
- live_source_count: 3
- partial_source_count: 1
- fallback_source_count: 0
- failed_source_count: 1 in latest payload, 2 in accumulated source diagnostics

## Source Fetch Lineage

Live:

- `bea-release-schedule`: success, parsed 17 items
- `fed-fomc-calendar`: success, parsed 8 items
- `fed-rss`: success, parsed 12 items

Partial:

- `cleveland-fed-nowcast`: HTTP 200, parsed 0 numeric nowcast values

Failed:

- `bls-release-calendar`: HTTP 403 Access Denied
- `cme-fedwatch`: historical failed attempts remain in source diagnostics; current active PCE run does not call it

Fallback:

- No embedded official calendar fallback was used in the latest successful run.

## Chain Audit

P8-C35 source fetch lineage:

- PASS. `event_source_fetches` is persisted and replayable through repository/API.

P1-C57 official calendar live connector:

- PARTIAL PASS. BEA/Fed live sources work; BLS official schedule is blocked by upstream 403 and must be replaced with an allowed official/API path or an explicitly marked secondary source.

P1-C58 expectation / nowcast / FedWatch connector:

- PARTIAL PASS. Cleveland page is reachable and lineage is real, but value extraction is not yet good enough. Consensus provider is still missing.

P1-C59 actual polling / post-event reaction:

- PARTIAL PASS. Pre-release gating works; actual parsing and post-release reaction require a real post-event sample.

P2-C40 shock fast lane live connector:

- PARTIAL PASS. BTC market-dislocation lane works from local price history; trusted-news/official shock source expansion remains pending.

P3-C56 live-gated state machine:

- PASS. State machine downgraded/raised state from live calendar and does not treat missing consensus as actual value.

P9-C43 source diagnostics API:

- PASS. `/api/event-window/sources/status`, `/sources/fetches`, `/sources/{source_id}` are available.

P5-C68 source status UI:

- PASS. Event subpage consumes source status and fetch lineage without changing radar/topology pages.

## Required Follow-Up

1. Add a non-blocked BLS path:
   - BLS API for actual series values, plus either a secondary calendar source clearly marked `secondary_consensus_calendar`, or a maintained official release-date mapping with source lineage.
2. Improve Cleveland nowcast parser:
   - parse embedded JSON/table content instead of nearby free text.
3. Add consensus provider:
   - Trading Economics/Econoday/Bloomberg replacement if credentials exist; otherwise mark consensus missing honestly.
4. Add a post-event replay test:
   - wait for PCE release window, verify actual, BTC 5m/30m/2h response, and absorption/follow-through status.

