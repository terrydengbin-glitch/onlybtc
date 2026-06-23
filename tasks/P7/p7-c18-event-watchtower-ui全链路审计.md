# P7-C18 / Event Watchtower UI 全链路审计

## 状态

 DONE

## Phase

P7 全链路审计

## 背景

P5-C71 / P5-C72 会把 Event Window 子页面、浮窗和 critical 警告层按 `reports/event-watchtower-ui-design.html` 对齐。需要一张 P7 审计任务确认 UI 没有破坏现有项目框架，并且展示内容全部来自真实 Event Window payload。

## 目标

审计完整链条：

```text
Event Window daemon / run once
  -> SQLite snapshot / timeline / source fetches
  -> FastAPI event-window APIs
  -> Vue store
  -> Event Watchtower 子页面
  -> Dashboard Summary
  -> floating alert / critical overlay
```

## 审计范围

必须检查：

```text
1. Event Watchtower 子页面字段是否来自真实 API/store，不是 mock。
2. direct_score_impact 是否始终显示并保持 false。
3. high / critical / watch 的颜色与 overlay 语义是否一致。
4. daemon pause / resume 是否可见且不影响其它页面。
5. Source / Provider / Proxy / Missing 状态是否可见。
6. 浮窗是否可移动、双击归位、点击进入子页面。
7. critical overlay 是否只由 critical / event_lock / avoid_new_position 触发。
8. 子页面改造是否没有破坏 topbar、rail、dashboard、radar、topology、alerts 页面。
```

## 验证命令

```powershell
npm run build

$env:PYTHONPATH='backend/src'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py -q

$env:PYTHONPATH='backend/src'
.\.venv\Scripts\python.exe scripts\generate_event_window_source_audit_html.py
.\.venv\Scripts\python.exe scripts\generate_event_window_state_overlay_llm_audit_html.py
.\.venv\Scripts\python.exe scripts\generate_event_window_shock_fast_lane_audit_html.py
```

如已有 Playwright / screenshot 工具可用，补充截图审计：

```text
Event Watchtower 页面
Dashboard Summary
high 浮窗
critical overlay
```

## DoD

- [x] `npm run build` 通过。
- [x] `backend/tests/test_event_watchtower.py` 通过。
- [x] HTML 1/2/3 可重新生成。
- [x] Event Watchtower 页面无 mock 文案替代真实字段。
- [x] Dashboard Summary、子页面、浮窗读取同一份 `event_window_v3` 语义。
- [x] critical overlay 不修改后端状态、不修改 BTC score。
- [x] 其它页面布局未被本次 CSS 误伤。

## 依赖

- P5-C71
- P5-C72
- P2-C40
- P3-C56
- P7-C17
