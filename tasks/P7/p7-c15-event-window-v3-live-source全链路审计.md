# P7-C15 / Event Window v3 Live Source 全链路审计

## 状态

TODO

## Phase

P7 全链路审计

## 目标

在 live connector 接入后，严格审计 Event Window 是否真正拉到数据，而不是 embedded fallback。

## 审计范围

```text
P1-C57 official calendar
P1-C58 expectations / nowcast / FedWatch
P1-C59 actual / post-event reaction
P2-C40 shock fast lane
P3-C56 state machine / overlay
P8-C35 source fetch lineage / replay
P9-C43 source diagnostics API
P5 event watchtower page source status display
```

## 审计问题

```text
1. 是否存在至少一个 live official source success？
2. fallback 是否只在 live source 失败后使用？
3. source_quality 是否真实反映 live/partial/fallback/failed？
4. release window 内 actual 缺失是否会 blocked，而不是伪造数据？
5. shock fast lane 是否能写入非日历突发？
6. high/critical overlay 是否只由 live 或确认突发触发？
7. API 和 UI 是否能清楚展示数据源状态？
```

## DoD

- [ ] run once 后生成 live source audit report。
- [ ] SQLite fetch lineage 与 event_window_v3 snapshot 可互相追溯。
- [ ] `/api/event-window/latest`、`/api/event-window/sources/status`、dashboard 透传一致。
- [ ] fallback-only 不允许判定为 live pass。
- [ ] 输出 PASS / PARTIAL / FAIL，并列出阻断项。

## 输出

```text
reports/p7-c15-event-window-v3-live-source-audit.md
```

## 依赖

- P1-C57
- P1-C58
- P1-C59
- P2-C40
- P3-C56
- P8-C35
- P9-C43
