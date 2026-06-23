# P5-C71 / Event Watchtower 子页面按原型重排

## 状态

 DONE

## Phase

P5 Vue3 前端展示

## 背景

`reports/event-watchtower-ui-design.html` 已经给出 Event Window / Policy Shock Watchtower 的高保真原型。当前项目里已经有 `eventWatchtower` 子页面，但仍偏“数据块堆叠”，需要按原型改成更清晰的事件哨兵页面。

本任务只优化 **Event Window 子页面内部布局**，不修改项目顶栏、左侧导航、Dashboard 其它 div、Radar 子页面、Topology 子页面、P3 Alerts 页面。

## 目标

在现有 Vue3 框架内，把 `activePage === 'eventWatchtower'` 页面重排为：

```text
Event Watchtower
  -> tabs: Live / Calendar / Timeline / Speeches / Shock Lane / History
  -> status strip: Emergency / Radar Trust / Overlay / Active Event
  -> main grid:
       Current Alert
       Expectation Drift
       Active Event Timeline
       Fed Speech / Policy Text
       Shock Fast Lane
       BTC Reaction Check
       Source Diagnostics
```

页面必须继续消费真实 API / store payload：

```text
eventWindow
eventWindowTimeline
eventWindowCalendar
eventWindowAlerts
eventWindowDaemon
eventWindowSources
eventWindowSourceFetches
event_window_v3
```

不得引入 mock 数据。

## 边界

允许修改：

```text
frontend/src/App.vue 中 eventWatchtower article 内部结构
frontend/src/styles.css 中 event-watchtower 相关 class
必要的 computed helper，仅服务 eventWatchtower 子页面
```

禁止修改：

```text
topbar / shell / rail 全局壳层
dashboard 其它 panel
radar / topology / alerts / evidence / settings 页面
后端 API 契约
run once 链条
```

## UI 要求

1. 子页面视觉风格必须跟现有 onlyBTC 深色框架一致。
2. 卡片圆角保持 8px 或以下。
3. 不使用营销式 hero，不使用大面积渐变装饰。
4. 状态颜色遵循当前项目语义：
   - `critical/high`：红/橙警告
   - `watch`：黄色
   - `none/normal`：蓝灰/中性
   - `live/ok/running`：青绿
   - `quality/proxy`：紫色
5. 页面顶部必须明确显示：
   - `emergency_level`
   - `event_window_state`
   - `trade_permission_modifier`
   - `ordinary_radar_trust`
   - `direct_score_impact=false`
   - daemon status / pause resume
6. 页面中必须显示数据源状态，但不能把非官方源伪装成官方 live。

## 数据绑定

Live tab 至少展示：

```text
Current Alert:
  eventWindowState.emergency_level
  eventWindowState.event_window_state
  eventWindowState.reason_codes
  eventWindowState.valid_until

Overlay:
  eventWindowOverlay.trade_permission_modifier
  eventWindowOverlay.ordinary_radar_trust
  eventWindowOverlay.confidence_cap
  eventWatchtowerPayload.direct_score_impact

Active Event:
  eventWindowActive.title
  eventWindowActive.event_type
  eventWindowActive.phase
  eventWindowActive.release_time
  eventWindowActive.time_to_event_sec

Shock Fast Lane:
  eventWindowShockLane.shock_detected
  eventWindowShockLane.shock_type
  eventWindowShockLane.confirmation_level
  eventWindowShockLane.source_count
  eventWindowShockLane.market_dislocation
  eventWindowShockLane.btc_microstructure_confirmation

BTC Reaction:
  post_event_reaction.btc_return_5m
  post_event_reaction.btc_return_30m
  post_event_reaction.btc_return_2h
  post_event_reaction.btc_absorbed_shock
  post_event_reaction.followthrough
```

## DoD

- [x] Event Watchtower 子页面布局按原型重排。
- [x] 页面仍在现有 app shell 内，不新增独立 HTML 外壳。
- [x] 子页面不使用 mock 数据。
- [x] daemon 开关仍可用，默认展示当前状态。
- [x] `direct_score_impact=false` 在页面中可见。
- [x] source / provider / proxy / missing 状态可见。
- [x] `npm run build` 通过。

## 依赖

- P5-C65
- P5-C66
- P5-C68
- P5-C69
- P5-C70
