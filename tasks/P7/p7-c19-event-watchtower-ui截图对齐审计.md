# P7-C19 / Event Watchtower UI 截图对齐审计

## 状态

DONE

## Execution Record

### 2026-06-23 / Start

- P5-C73/P5-C74/P7-C18 均已完成，按顺序启动 P7-C19。
- 本任务为审计任务，默认不改业务逻辑；仅在发现 UI contract 破坏时做最小修复。
- 验证范围：Event Watchtower live/shock/critical/mock/source diagnostics，build、后端测试、HTML 1/2/3 生成、静态 UI contract 检查。

### 2026-06-23 / DONE

- `cd frontend && npm run build` 通过。
- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py -q` 通过：22 passed。
- HTML 1/2/3 均生成成功：
  - `reports/event-window-source-audit-report.html`
  - `reports/event-window-state-overlay-llm-audit-report.html`
  - `reports/event-window-shock-fast-lane-audit-report.html`
- 生成截图：
  - `reports/p7-c19-screenshots/event-watchtower-live-cli.png`
  - `reports/p7-c19-screenshots/event-watchtower-dev-mock-critical-cli.png`
- 静态 contract 检查通过：右侧 rail、主区域、direct_score_impact、mock dev gate、topbar/left rail 边界均符合任务要求。
- 审计报告：`reports/p7-c19-event-watchtower-ui-screenshot-alignment-audit.md`。

## Phase

P7 全链路审计

## 背景

P5-C73 / P5-C74 将 Event Watchtower 页面按截图原型进行精确布局对齐。需要专项审计确认：

```text
1. UI 是否真的包含截图里的右侧业务栏。
2. 内容是否来自真实 Event Window payload。
3. critical mock 是否被隔离。
4. 不破坏当前项目 UI 框架。
```

## 审计范围

检查：

```text
Event Watchtower 子页面
  -> status strip
  -> main grid
  -> right rail
  -> timeline stream
  -> source/provider diagnostics

Floating Alert / Critical Overlay
  -> high 浮窗
  -> critical 居中层
  -> mock 态隔离
```

## 必查项

```text
1. 右侧 rail 是否存在：
   - Shock Fast Lane
   - BTC Reaction Check
   - Calendar Mini
   - Dashboard Summary Widget

2. 主区域是否存在：
   - Current Alert
   - Expectation Drift
   - Active Event Timeline
   - Fed Speech / Policy Text
   - Timeline stream

3. 数据来源：
   - 不允许静态 mock 数字
   - fallback 文案必须是 pending / unavailable / no active shock
   - direct_score_impact=false 必须可见

4. 边界：
   - Event Window 只改 overlay / radar trust
   - 不直接改 BTC score
   - critical overlay 不写后端

5. 框架：
   - topbar 不变
   - left rail 不变
   - dashboard 其它 div 不变
   - radar/topology/alerts 不受 CSS 误伤
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

如可用浏览器截图工具，需补充截图：

```text
eventWatchtower live page
eventWatchtower shock tab
high floating alert
critical overlay synthetic/dev-only view
```

## DoD

- [x] build 通过。
- [x] event watchtower 后端测试通过。
- [x] HTML 1/2/3 可生成。
- [x] UI contract 检查通过。
- [x] 右侧 rail 四块均存在。
- [x] mock critical 默认不可见。
- [x] 本轮修改没有触碰其它页面业务结构。

## 依赖

- P5-C73
- P5-C74
- P7-C18
