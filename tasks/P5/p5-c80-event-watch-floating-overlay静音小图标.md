# P5-C80 / Event Watch Floating Overlay 静音小图标

## 背景

P5-C79 已将 Event Watch high 浮窗按原型对齐，并增加 `Mute 15m`。但风险提示不应该在 mute 后完全消失。Event Window 的职责是提醒普通 radar trust 被降级，用户可以减少干扰，但不能彻底失去当前高风险状态入口。

## 目标

把 Event Watch 浮窗改成两态：

1. 展开态：完整 high 浮窗，显示事件、radar trust、permission modifier、风险说明、Mute/Open。
2. 静音态：Mute 后浮窗折叠为常驻小图标/小胶囊，显示 emergency level 和事件类型，可点击展开。

## 交互规则

- `Mute 15m` 后：
  - 不隐藏 Event Watch 状态。
  - 不隐藏 critical overlay 触发条件。
  - high 浮窗折叠为小图标。
  - 小图标继续可拖动。
  - 点击小图标立即展开完整浮窗。
- 静音到期后：
  - 若仍为 high，则自动恢复展开态。
  - 若已降级为 none/watch，则不显示。
- critical / event_lock / avoid_new_position：
  - 忽略 mute，小图标不能压住 critical overlay。
  - 仍显示居中 critical overlay。

## 边界

- 只修改 Event Watch global floating overlay。
- 不改 Event Watchtower 子页面主体布局。
- 不改 backend / API / SQLite。
- 不影响 BTC score 和 radar module 分数。

## DoD

- [x] Mute 后 high 浮窗变成小图标，而不是完全消失。
- [x] 小图标显示 level 和 event type。
- [x] 点击小图标可展开完整浮窗。
- [x] 小图标可拖动并复用现有位置存储。
- [x] critical overlay 不受 mute 影响。
- [x] 页面刷新后 mute 状态可恢复。
- [x] `npm run build` 通过。
