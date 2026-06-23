# P5-C76 / Event Watchtower 事件 Ack、清除与可见性治理

## 状态

DONE

## Execution Record

### 2026-06-23 / Start

- P5-C73/P5-C74/P5-C75 已完成，按依赖顺序启动 P5-C76。
- 范围限定为 Event Watchtower 前端可见性治理；不调用 destructive backend API，不删除 SQLite，不修改 event_window_state / emergency_level / trade_permission_modifier / ordinary_radar_trust / BTC score / radar score。
- 当前后端存在 alert ack/mute API，但本任务按卡片边界只做浏览器会话/本地可见性状态。

### 2026-06-23 / DONE

- 增加 `onlybtc:event-window:ack:v1` / `hidden:v1` / `critical-dismiss:v1` 本地可见性状态。
- visibility key 包含 snapshot_id、valid_until、event_window_state、emergency_level；critical dismiss key 额外包含 trade_permission_modifier。
- Event Watchtower 页面新增 Ack current alert、Dismiss session、Show hidden / restore、Clear visible 控制条。
- Floating alert 支持当前会话 dismiss；snapshot/state/validity/emergency 变化后自动恢复。
- Critical overlay dismiss 持久到 sessionStorage；dismiss 后页面状态、右侧 rail、Dashboard Summary、Audit 仍显示真实 critical 状态。
- Clear visible 仅对 non-critical 生效，不删除 SQLite/history/replay，不调用后端 destructive API。
- 验证：`cd frontend && npm run build` 通过。
- 审计报告：`reports/p5-c76-event-watchtower-visibility-governance-audit.md`。

## Phase

P5 Vue3 前端展示

## 背景

用户需要在 Event Window UI 里处理“事件清掉 / 已读 / 暂时隐藏 / 恢复显示”的交互。这里必须区分前端可见性操作和真实后端事件状态：

```text
Dismiss / Ack:
  只是前端会话或用户可见性，不改变 event_window_state

Event resolved / expired:
  必须由后端 valid_until、state machine、event phase 或 source 更新决定

Clear all:
  不能删除 SQLite 历史，最多清前端已读/隐藏状态
```

## 目标

为 Event Watchtower UI 增加安全的事件可见性控制：

```text
Ack current alert
Dismiss floating alert for session
Dismiss critical overlay for session
Show hidden / restore
Clear visible non-critical alerts
```

## 交互规则

### Ack Current Alert

```text
作用：
  标记当前 snapshot / alert 已读

边界：
  不修改后端 event_window_state
  不修改 emergency_level
  不修改 trade_permission_modifier
  不修改 ordinary_radar_trust
  不修改 BTC score
```

### Dismiss Floating Alert

```text
作用：
  当前浏览器会话隐藏浮窗

恢复：
  snapshot_id / valid_until / emergency_level 变化后自动恢复
```

### Dismiss Critical Overlay

```text
作用：
  当前浏览器会话隐藏居中 critical 层

限制：
  不隐藏右侧 rail 状态
  不隐藏 Event Watchtower 页面状态
  不隐藏 Dashboard Summary 状态
```

### Clear Visible Non-critical Alerts

```text
作用：
  清除前端当前可见的 watch/high 非 critical 提醒列表

禁止：
  不删除 SQLite
  不调用 destructive backend API
  不影响 history / replay
```

## 存储建议

使用 localStorage/sessionStorage：

```text
onlybtc:event-window:ack:v1
onlybtc:event-window:hidden:v1
onlybtc:event-window:critical-dismiss:v1
```

key 必须包含：

```text
snapshot_id
valid_until
event_window_state
emergency_level
```

## UI 展示

在 Event Watchtower 页面加入：

```text
Ack
Dismiss session
Show hidden
Clear visible
```

并显示边界文案：

```text
Visibility controls do not modify Event Window state, SQLite history, BTC score, or radar score.
```

## DoD

- [x] Ack / Dismiss / Clear 只影响前端可见性。
- [x] critical overlay dismiss 后，Event Watchtower 页面仍显示 critical 状态。
- [x] snapshot_id / valid_until 变化后 dismiss 自动失效。
- [x] Clear 不删除 SQLite / history / replay。
- [x] UI 明确说明这些操作不改变 BTC score / radar score。
- [x] `npm run build` 通过。

## 依赖

- P5-C72
- P5-C74
- P5-C75
