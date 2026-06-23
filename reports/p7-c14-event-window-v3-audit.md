# P7-C14 Event Window v3 全链路审计

## 结论

本次 run once 后，Event Window / Policy Shock Watchtower v3 的基础链路通过：

- 独立 daemon 可运行，并可随 FastAPI 启动保持常驻。
- 手动 run once 可生成 `p45.event_window.v3` snapshot。
- SQLite 独立事件表可落库 calendar / expectation / official text / LLM analysis / post reaction / alerts。
- P4.5 final payload 可透传 `event_window_v3`。
- FastAPI `/api/event-window/*` 与 `/api/p45/dashboard/latest` 可读取同一类契约。
- Vue3 前端构建通过，事件子页面、全局浮窗和 daemon 开关具备可用链路。

但当前仍是“链路 pass / 数据源 fallback”状态，不是最终实时官方源 pass。官方 Fed/BLS/BEA/Cleveland Fed/CME FedWatch 的 live connector 仍需后续替换 embedded fallback。

## Run Once 结果

```text
snapshot_id: evt-20260527164013-f71ee16b
schema_version: p45.event_window.v3
event_window_state: pre_event_high_alert
trade_permission_modifier: watch_only
```

随后恢复 FastAPI 内部 daemon，生成并对齐最新 API snapshot：

```text
snapshot_id: evt-20260527164155-d7a8af18
daemon_status: running
default_enabled: true
event_window_state: pre_event_high_alert
emergency_level: high
active_event: Personal Income and Outlays
direct_score_impact: false
```

## SQLite 审计

当前事件表已有记录：

```text
event_watchtower_snapshots: 11
event_calendar_items: 4
event_expectation_snapshots: 10
event_official_text_items: 1
event_llm_analyses: 1
event_shock_lane_items: 0
event_post_reaction_snapshots: 10
event_alerts: 10
```

`shock_lane_items = 0` 是当前没有检测到非日历突发冲击，不是链路失败。

## 契约审计

`/api/event-window/latest` 返回：

```text
schema_version: p45.event_window.v3
direct_score_impact: false
state.event_window_state: pre_event_high_alert
state.emergency_level: high
overlay.trade_permission_modifier: watch_only
overlay.ordinary_radar_trust: low
active_event.event_type: PCE
active_event.title: Personal Income and Outlays
post_event_reaction.followthrough: pending
data_quality_flags:
  - embedded_official_calendar_fallback
  - live_expectation_connectors_pending
```

这符合设计：事件层只叠加 emergency overlay，不直接修改 radar score。

## API 审计

已验证端点：

```text
GET  /api/event-window/latest
GET  /api/event-window/calendar
GET  /api/event-window/timeline
GET  /api/event-window/alerts
GET  /api/event-window/post-event-reaction
GET  /api/event-window/speeches
GET  /api/event-window/daemon/status
POST /api/event-window/daemon/resume
GET  /api/p45/dashboard/latest
```

`/api/p45/dashboard/latest` 已返回：

```text
schema: p45.event_window.v3
snapshot: evt-20260527164155-d7a8af18
state: pre_event_high_alert
overlay: watch_only
emergency: high
active: Personal Income and Outlays
direct_score_impact: false
```

## 前端审计

已确认：

- 左侧导航新增事件子页面。
- 事件子页面读取 Event Window API。
- high / critical 事件可触发全局浮窗。
- 浮窗支持拖动、点击进入事件页、双击重置位置。
- daemon 开关默认打开，并支持 pause / resume。
- Vue3 build 通过。

## 测试

```text
pytest backend/tests/test_event_watchtower.py backend/tests/test_db.py -q
9 passed
```

```text
ruff check backend/src/onlybtc/event_window backend/src/onlybtc/api/event_window.py backend/tests/test_event_watchtower.py
All checks passed
```

```text
npm run build
passed
```

测试中有 FastAPI `@app.on_event("startup")` deprecation warning；功能可用，后续可迁移到 lifespan。

## 剩余边界

- 官方事件日历、预期、nowcast、FedWatch 当前仍是 embedded fallback，不是 live connector。
- LLM analyzer 已按契约预留，但当前只输出 `not_policy_relevant` fallback。
- PCE 尚未发布，所以 post-event actual / surprise / BTC reaction 仍为 `pending`。
- 当前没有 unscheduled shock，因此 shock fast lane 为空。
- 历史 alert 中早期有少量 `HIGH Â· ...` 编码遗留；最新 alert 已使用 ASCII 标题，不再新增该问题。

## 判定

基础链路、契约、SQLite、FastAPI、P4.5 透传、Vue3 构建：PASS。

实时官方数据源完整性：PARTIAL，等待 live connectors 接入。
