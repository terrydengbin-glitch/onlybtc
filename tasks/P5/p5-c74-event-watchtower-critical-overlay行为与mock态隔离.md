# P5-C74 / Event Watchtower Critical Overlay 行为与 Mock 态隔离

## 状态

DONE

## Execution Record

### 2026-06-23 / Start

- P5-C73 已完成，按依赖顺序启动 P5-C74。
- 范围限定为 Event Watchtower critical overlay 相关 helper/template/style，不改后端状态机、API payload、BTC score、radar score。
- 目标是确认真实 critical overlay 只由真实 payload 触发；high 只走浮窗；mock/audit overlay 默认不可见并显式隔离。

### 2026-06-23 / DONE

- 真实 critical overlay 保持只由 `emergency_level=critical` 或 `trade_permission_modifier in [event_lock, avoid_new_position]` 触发。
- high 状态继续走 floating alert，不进入 critical overlay。
- 增加 dev-only mock overlay 隔离：仅 `import.meta.env.DEV && ?event_mock=critical` 显示，且真实 critical overlay 激活时不叠加 mock。
- 真实 overlay 补齐 event title、state、permission、radar trust、valid_until、direct_score_impact、snapshot_id、reason_codes、Open Watchtower、Dismiss session。
- Dismiss key 已包含 snapshot_id / valid_until / emergency_level / trade_permission_modifier，快照或有效期变化后自动失效。
- 验证：`cd frontend && npm run build` 通过。
- 审计报告：`reports/p5-c74-event-watchtower-critical-overlay-audit.md`。

## Phase

P5 Vue3 前端展示

## 背景

截图原型中有 `CRITICAL MOCK STATE` 居中弹层，用于展示 critical 行为。但生产 UI 里不能让 mock 状态混入真实事件判断，也不能让 mock 文案误导用户。

本任务负责把 critical overlay 的真实态和开发/审计 mock 态隔离。

## 目标

实现：

```text
真实 critical overlay:
  仅由 event_window_v3 的 emergency_level=critical
  或 overlay.trade_permission_modifier in [event_lock, avoid_new_position] 触发

审计 mock overlay:
  只能在显式 dev/audit flag 下显示
  文案必须标记 mock / audit only
  不进入用户默认 live 页面
```

## 边界

允许修改：

```text
frontend/src/App.vue 中 event critical overlay 相关模板和 helper
frontend/src/styles.css 中 event-critical-* class
```

禁止修改：

```text
Event Window 后端状态机
API payload
BTC score / radar score
其它页面 modal
```

## 真实 Overlay 内容

真实 critical overlay 必须展示：

```text
event title
emergency_level
event_window_state
trade_permission_modifier
ordinary_radar_trust
valid_until
direct_score_impact=false
reason_codes
Open Watchtower
Dismiss session
```

## Mock / Audit Overlay 规则

如果需要保留截图中的 mock 层：

```text
1. 只能通过本地 dev flag 显示，例如 ?event_mock=critical 或 local dev helper。
2. 默认生产路径不显示。
3. 文案必须是 “MOCK / audit only”。
4. mock 不得读取/覆盖 eventWindowState。
5. mock 不得写入 SQLite / store / API。
```

## DoD

- [x] 真实 critical overlay 只由真实 payload 触发。
- [x] high 状态不显示 critical overlay，只显示浮窗。
- [x] mock / audit overlay 默认不可见。
- [x] Dismiss session 只在当前前端会话生效。
- [x] snapshot_id / valid_until 变化后 dismiss 自动失效。
- [x] 文案明确“不直接改 BTC score”。
- [x] `npm run build` 通过。

## 依赖

- P5-C72
- P5-C73
