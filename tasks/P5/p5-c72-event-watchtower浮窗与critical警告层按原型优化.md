# P5-C72 / Event Watchtower 浮窗与 Critical 警告层按原型优化

## 状态

 DONE

## Phase

P5 Vue3 前端展示

## 背景

当前项目已有 `event-floating-alert`，并支持拖动和双击归位。原型要求 Event Window 在高优先级事件时能快速覆盖普通视图：`high` 使用可移动浮窗提示，`critical` 使用更强的居中警告层。

本任务只优化 **Event Window 的浮窗 / 警告窗**，不改变普通 radar 分数、不改变页面路由框架。

## 目标

实现两级前端提醒：

```text
high / watch_only:
  可拖动浮窗
  默认靠上居中或用户保存位置
  点击进入 Event Watchtower 子页面

critical / event_lock / avoid_new_position:
  居中 Critical Overlay
  z-index 高于所有页面层
  有闪耀/脉冲边框
  可进入 Event Watchtower
  可本会话 dismiss，但不改变后端状态
```

## 边界

允许修改：

```text
frontend/src/App.vue 的 event-floating-alert 相关模板与交互
frontend/src/styles.css 的 event-floating-alert / event-critical-overlay 样式
localStorage 中浮窗位置和本会话 dismiss 状态
```

禁止修改：

```text
后端 state machine
event_window_v3 payload
BTC score / radar score
其它页面 modal / evidence drawer / dashboard panel
```

## 展示规则

```text
emergency_level = high:
  显示 event-floating-alert
  class = high / mixed / warning
  不显示 critical overlay

emergency_level = critical:
  显示 event-floating-alert
  同时显示 event-critical-overlay

trade_permission_modifier in [event_lock, avoid_new_position]:
  即使 emergency_level 字段异常，也显示 critical overlay
```

## 交互规则

1. 浮窗可拖动，位置保存在 `localStorage`。
2. 浮窗双击归位。
3. 浮窗点击打开 `eventWatchtower` 子页面。
4. Critical overlay 的 dismiss 只在当前浏览器会话生效。
5. Dismiss 不调用后端，不修改 `event_window_state`。
6. 当 `snapshot_id` 或 `valid_until` 变化时，critical dismiss 自动失效。

## UI 要求

1. 浮窗不遮挡 topbar 主要按钮。
2. Critical overlay 必须高于 radar/topology/dashboard 所有层。
3. 文案必须明确：
   - 事件名
   - emergency level
   - overlay modifier
   - ordinary radar trust
   - valid_until
   - `does not overwrite BTC score`
4. 颜色必须与项目现有 `alertTone()` 语义一致。

## DoD

- [x] high 状态显示可拖动浮窗。
- [x] critical / event_lock 状态显示居中 critical overlay。
- [x] 浮窗点击进入 Event Watchtower 子页面。
- [x] 浮窗拖动、双击归位可用。
- [x] critical dismiss 仅本会话有效，不修改后端状态。
- [x] 文案清楚说明 Event Window 只改 overlay / radar trust，不直接改 BTC score。
- [x] `npm run build` 通过。

## 依赖

- P5-C64
- P5-C66
- P5-C71
