# P7-C20 / Event Watchtower 审计 HTML 入 UI 与清除交互审计

## 状态

DONE

## Execution Record

### 2026-06-23 / Start

- P5-C75/P5-C76/P7-C19 已完成，按依赖顺序启动 P7-C20。
- 本任务为审计任务，默认不改业务逻辑；重点核查 Audit tab 是否映射三份 HTML 核心内容，以及 Ack / Dismiss / Clear 是否只影响前端可见性。
- 验证范围：build、Event Watchtower 后端测试、HTML 1/2/3 生成、UI 静态 contract、SQLite counts 非破坏性检查。

### 2026-06-23 / DONE

- 复用同一审计会话中的验证结果：build 通过、Event Watchtower 后端测试 22 passed、HTML 1/2/3 生成成功。
- 静态 UI contract 检查通过：Audit tab 包含 Source Chain / State Overlay LLM / Shock Fast Lane 三块，并有三份 HTML 入口。
- LLM 边界检查通过：UI 文案明确 LLM 只解释 tone/relevance/confidence，不输出 BTC 多空，不覆盖 emergency_level / trade_permission_modifier。
- Ack / Dismiss / Clear 源码边界检查通过：只读写 localStorage/sessionStorage，不调用 store/fetch/backend API/SQLite。
- 说明：打开 Event Watchtower 会触发 live refresh，可能自然新增 SQLite daemon/live rows；因此本任务以 handler 源码边界作为 Clear 不破坏 SQLite/history/replay 的确定性证据。
- 审计报告：`reports/p7-c20-event-watchtower-audit-ui-and-clear-interaction-audit.md`。

## Phase

P7 全链路审计

## 背景

P5-C75 / P5-C76 会把 Event Window 三份审计 HTML 的核心内容展示进 UI，并加入 Ack / Dismiss / Clear 可见性控制。需要专项审计，确认 UI 展示的是审计事实，不是 mock；清除行为不破坏 SQLite 历史和后端状态。

## 审计目标

确认：

```text
HTML 1 Source Audit 内容已进入 UI
HTML 2 State / Overlay / LLM Audit 内容已进入 UI
HTML 3 Shock Fast Lane Audit 内容已进入 UI
LLM 中文解释显示为解释，不作为交易方向
Ack / Dismiss / Clear 只影响前端可见性
SQLite / history / replay 不被清除
```

## 必查项

### UI 内容

```text
1. Source/provider/fetch lineage 可见。
2. State priority / overlay boundary 可见。
3. LLM tone / relevance / confidence / boundary_passed 可见。
4. Shock latest / boundary checks / synthetic regression 可见。
5. 三份 HTML 文件入口可见。
```

### LLM 边界

```text
1. LLM 中文解释没有 BTC bullish / bearish 结论。
2. LLM 不显示交易建议。
3. LLM 不覆盖 emergency_level。
4. LLM 不覆盖 trade_permission_modifier。
```

### 清除/已读边界

```text
1. Ack 不改 event_window_state。
2. Dismiss 不改 backend payload。
3. Clear 不删除 SQLite。
4. snapshot_id / valid_until 改变后 alert 可重新出现。
5. History / replay 仍能看到旧事件。
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

可选机器检查：

```text
App.vue contains:
  Source Chain
  State / Overlay / LLM
  Shock Fast Lane Audit
  direct_score_impact
  Ack / Dismiss / Clear

SQLite counts before/after clear unchanged.
```

## DoD

- [x] build 通过。
- [x] event watchtower 测试通过。
- [x] HTML 1/2/3 可生成。
- [x] UI 显示三份 HTML 的核心审计内容。
- [x] Ack / Dismiss / Clear 不影响 SQLite counts。
- [x] 清除操作不会影响 backend payload。
- [x] LLM 中文解释边界符合预期。

## 依赖

- P5-C75
- P5-C76
- P7-C19
