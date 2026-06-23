# P5-C66 / Dashboard 事件窗口 Summary Widget 改造

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

Dashboard 原有“预警 / 事件窗口”区域不适合承载完整 Event Watchtower。它应该改造成 summary widget：只展示当前最关键状态和跳转入口，详细信息交给独立子页面，全局紧急情况交给浮窗层。

## 目标

将 dashboard 的“预警 / 事件窗口”区改为：

```text
Event Watchtower Summary
```

展示：

```text
Emergency level
Active event / shock
Phase / countdown
Overlay modifier
Ordinary radar trust
Daemon status
Next release / valid_until
Open Watchtower button
```

## 展示规则

```text
none:
  compact neutral card

watch:
  amber accent

high:
  orange/red accent
  show trade_permission_modifier

critical:
  red/magenta accent
  widget 同步高亮，但打断用户由全局浮窗负责
```

## 边界

- 只改 dashboard 内事件窗口 summary widget。
- 不修改 radar div。
- 不修改 topology div。
- 不修改中央 BTC 卡。
- 不在 summary 里展示完整事件列表。

## 文案边界

- 不写 Event Watchtower 看多/看空 BTC。
- 写 `Radar trust: normal/reduced/low/blocked`。
- 写 `Overlay: watch_only / reduce_size / event_lock`。

## DoD

- [ ] Dashboard 事件窗口区域优先消费 `event_window_v3`。
- [ ] 无 event_window_v3 时保持旧事件窗口 fallback。
- [ ] Summary widget 展示 emergency_level、active_event、overlay、radar trust。
- [ ] Summary widget 展示 daemon running / paused / degraded。
- [ ] paused_by_user 时显示 Watchtower paused，不弹窗入口仍可进入子页面恢复。
- [ ] 有 `Open Watchtower` 跳转独立子页面。
- [ ] critical 状态 widget 高亮但不替代全局浮窗。
- [ ] `npm run build` 通过。

## 依赖

- P5-C63
- P5-C64
- P5-C65
- P9-C40
- P9-C41
