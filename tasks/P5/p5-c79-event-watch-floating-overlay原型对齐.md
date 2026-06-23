# P5-C79 / Event Watch Floating Overlay 原型对齐

## 背景

Event Window 是独立的事实/冲击监控层，不是 radar module。当前浮窗已经能展示 high/critical 状态，但样式和信息层级还没有完全对齐原型：浮窗应作为实时趋势可信度提示，只有 critical / event_lock 才进入居中强弹窗。

## 目标

把全局 Event Watch 浮窗按原型对齐为紧凑高优先级提示卡：

- high：右下/可拖动浮窗，提示 ordinary radar trust 降级和 trade permission modifier。
- critical / event_lock / avoid_new_position：居中 Critical overlay。
- 浮窗只使用 FastAPI / SQLite live payload，不使用 mock 或审计 HTML。

## 边界

- 只修改 Event Watch 全局浮窗和 critical overlay 范围。
- 不修改 radar/topology/主 BTC 卡/其他 dashboard div。
- 不改变 Event Window 业务评分，不直接影响 BTC score。

## 输入字段

- `event_window.state.emergency_level`
- `event_window.state.event_window_state`
- `event_window.state.reason_codes`
- `event_window.state.valid_until`
- `event_window.overlay.trade_permission_modifier`
- `event_window.overlay.ordinary_radar_trust`
- `event_window.active_event.title`
- `event_window.active_event.event_type`
- `event_window.active_event.time_to_event_sec`
- `event_window.direct_score_impact`

## UI 要求

### High 浮窗

显示：

```text
EVENT WATCH · HIGH
PCE in T-6.3h · radar trust low
watch_only

Inflation upside risk is building before release.
Ordinary radar trend continuation is downgraded until release + 30m.

Mute 15m   Open
```

### Critical Overlay

触发条件：

```text
emergency_level == critical
or trade_permission_modifier in [event_lock, avoid_new_position]
```

要求：

- 居中显示。
- 边框/阴影更强。
- 需要用户 dismiss 或打开 Watchtower。
- 必须说明：Event Window 只修改 emergency overlay / radar trust，不覆盖 BTC score。

## DoD

- [x] high 状态只显示可拖动 floating alert，不显示 centered critical overlay。
- [x] critical / event_lock 状态显示 centered overlay。
- [x] 浮窗字段来自 Event Window live payload。
- [x] 浮窗显示 event type、time to event、radar trust、permission modifier。
- [x] 浮窗支持 `Mute 15m` 和 `Open`。
- [x] Mute 不影响 Event Watchtower 子页面状态。
- [x] 仍支持拖动和双击归位。
- [x] `npm run build` 通过。
