# P5-C73 / Event Watchtower 按截图三栏布局精确对齐

## 状态

DONE

## Execution Record

### 2026-06-23 / Start

- 用户要求继续，接 P5-C62 后启动 P5-C73。
- 范围限定为 Event Watchtower Vue3 子页面布局和专属样式，不改后端 API/schema，不改 BTC score/radar score。
- 当前 UI 已有 live grid 和右侧内容雏形；本次重点补齐截图式固定右 rail、真实 calendar mini month grid、Current Alert / Expectation Drift / Timeline / Fed Speech 信息层级。

### 2026-06-23 / DONE

- `frontend/src/App.vue` 增加 Event Watchtower 专属 Calendar Mini 月份聚合 helper，数据来自 `eventWindowCalendar` / active event release time。
- Live 页主区域补齐 Current Alert、Expectation Drift、Active Event Timeline、Fed Speech / Policy Text、Timeline Stream 的字段层级。
- 右侧 rail 补齐 Shock Fast Lane、BTC Reaction Check、Calendar Mini、Dashboard Summary Widget，并将当前页 Open Watchtower 按钮置为 disabled。
- `frontend/src/styles.css` 将右 rail 固定到 320-380px 桌面宽度，窄屏下沉；Calendar Mini 改成 7 列月份格并按事件重要性着色。
- 验证：`cd frontend && npm run build` 通过。
- 审计报告：`reports/p5-c73-event-watchtower-three-column-layout-audit.md`。

## Phase

P5 Vue3 前端展示

## 背景

P5-C71 已完成 Event Watchtower 子页面初步重排，但实际 UI 仍未与 `reports/event-watchtower-ui-design.html` / 用户截图对齐：右侧突发事件、BTC 反应、Calendar Mini、Dashboard Summary Widget 没有形成固定右栏；Live 主视图也没有按截图里的信息层级组织。

本任务是 **Event Window 子页面 UI 精确对齐任务**，不是新增业务算法。

## 目标

在现有 app shell 内，把 `eventWatchtower` 子页面调整为截图中的三栏结构：

```text
Event Watchtower Page
  Header:
    title / subtitle
    high alert / daemon state / heartbeat

  Tabs:
    Live / Calendar / Timeline / Speeches / Shock Lane / History

  Status Strip:
    Emergency Level
    Radar Trust
    Overlay
    Active Event

  Main Area:
    Left + Center content grid
      Current Alert
      Expectation Drift
      Active Event Timeline
      Fed Speech / Policy Text
      Timeline stream

    Right Rail
      Shock Fast Lane
      BTC Reaction Check
      Calendar Mini
      Dashboard Summary Widget
```

## 边界

允许修改：

```text
frontend/src/App.vue 的 eventWatchtower article 内部模板
frontend/src/styles.css 中 event-watchtower / event-* 专属 class
必要 computed helper，仅服务 eventWatchtower 页面
```

禁止修改：

```text
topbar
left rail
dashboard 其它 panel
radar / topology / alerts / evidence / settings 页面
后端 API / schema
BTC score / radar score
```

## 右侧 Rail 必须展示

### 1. Shock Fast Lane

字段来自：

```text
eventWindowShockLane.shock_detected
eventWindowShockLane.shock_type
eventWindowShockLane.confirmation_level
eventWindowShockLane.source_count
eventWindowShockLane.market_dislocation
eventWindowShockLane.btc_microstructure_confirmation
eventWindowShockLane.rumor_risk
```

显示要求：

```text
无突发时：
  标题: Shock Fast Lane
  badge: none
  正文说明 no official unscheduled policy shock / source_count below threshold / market stable

有突发时：
  根据 emergency_level 着色
  显示 confirmation_level、source_count、market / micro 状态
```

### 2. BTC Reaction Check

字段来自：

```text
eventWindowPostReaction.btc_return_5m
eventWindowPostReaction.btc_return_30m
eventWindowPostReaction.btc_return_2h
eventWindowPostReaction.btc_absorbed_shock
eventWindowPostReaction.followthrough
```

显示为三行：

```text
5m  first impulse after actual
30m absorption check / fakeout continuation
2h  follow-through / event trend acceptance
```

如果没有 actual / post event：

```text
waiting release / pending / pending
```

### 3. Calendar Mini

数据来自 `eventWindowCalendar`，不是 mock。

显示要求：

```text
按当前月份或 active_event release_time 所在月份显示 mini grid
高影响事件用黄色/红色边框
至少显示日期 + event_type 短标签，如 PCE / NFP / FOMC
```

### 4. Dashboard Summary Widget

这是 dashboard 预警/事件窗口的小卡片在事件子页面中的对照版本。

显示：

```text
emergency_level
active event short label
trade_permission_modifier
ordinary_radar_trust
Open Watchtower button 可以禁用或指向当前页
```

## 主区域必须展示

### Current Alert

显示：

```text
event title
event_window_state
emergency_level
reason_codes
trade_permission_modifier
valid_until
direct_score_impact=false
```

### Expectation Drift

显示：

```text
nowcast gap
expectation_drift_1d
expectation_drift_3d
rate_cut_prob_drift_1d / prediction_market_odds
```

### Active Event Timeline

至少显示前 3 个高优先级事件：

```text
time-to-event
title
source / event_type / phase
importance badge
```

### Fed Speech / Policy Text

显示：

```text
speaker
tone
policy_relevance
tone_confidence
LLM boundary: no BTC direction
```

### Timeline Stream

显示 eventWindowTimeline 最新 rows，按 level 着色：

```text
expectation snapshot
alert raised
daemon heartbeat
source fetch
shock lane
```

## UI 规则

1. 不要全页大块红色背景；红色只用于 critical/high 的边框、标题和局部状态。
2. 右侧 rail 宽度约 320-380px，可响应式下沉。
3. 卡片保持 8px border radius 或以下。
4. 所有按钮/卡片文本不能溢出。
5. 不使用 mock 文案替代真实字段；fallback 文案必须写成 pending / unavailable / no active shock。

## DoD

- [x] Event Watchtower 页面形成截图式三栏布局。
- [x] 右侧 rail 包含 Shock Fast Lane / BTC Reaction Check / Calendar Mini / Dashboard Summary Widget。
- [x] 主区域包含 Current Alert / Expectation Drift / Active Event Timeline / Fed Speech / Timeline Stream。
- [x] 所有内容来自 event window store/API，不使用静态 mock 数据。
- [x] `direct_score_impact=false` 可见。
- [x] 页面不影响 topbar、left rail、dashboard、radar、topology、alerts。
- [x] `npm run build` 通过。

## 依赖

- P5-C71
- P5-C72
- P2-C40
- P3-C56
