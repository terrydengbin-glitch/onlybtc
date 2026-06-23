# P5-C84 Event Watchtower Shock LLM 同源入库与 UI 对齐修复

## 背景

Event Watchtower 子页面的 Shock Fast Lane 已新增「LLM 中文观察」，但当前 UI 显示为 pending，而审计 HTML 3 `event-window-shock-fast-lane-audit-report.html` 中已经有 DeepSeek 的中文解释。这说明业务链条存在同源断点：

```text
HTML 3 审计生成器可以拿到 DeepSeek 解释
但业务 payload / SQLite snapshot / FastAPI latest 没有同一份解释
前端只能显示 pending / fallback
```

另外，当前后端 fallback 中文文案存在编码乱码，不能作为 UI 兜底展示。

## 目标

让 Shock Fast Lane 的 LLM 中文解释进入同一个业务 snapshot，并通过 FastAPI 供 UI 展示，确保 UI 与 HTML 3 审计解释同源、同 snapshot、同 asof。

## 范围

- Event Window / Shock Fast Lane 业务链条。
- `shock_fast_lane.llm_analysis` 的生成、持久化、API 透传、前端展示。
- HTML 3 仍是审计文件，不允许前端直接读取 HTML。

## 非目标

- 不让 LLM 直接改变 BTC score、radar score、trend direction。
- 不把 HTML 3 作为业务数据源。
- 不改 radar/topology 页面。

## 修复要求

1. 修复 `watchtower.py` / API fallback 中的中文乱码。
2. `shock_fast_lane.llm_analysis` 必须包含：
   - `provider`
   - `status`
   - `summary_zh`
   - `risk_reason_zh`
   - `action_boundary_zh`
   - `boundary_pass`
   - `analysis_source`
   - `snapshot_id`
3. 如果 DeepSeek 可用，run once / audit bundle 生成的 Shock LLM 解释必须回写到同一个 SQLite snapshot payload。
4. 如果 DeepSeek 不可用，必须使用清晰中文 deterministic fallback，并标记 `provider=deterministic`。
5. `/api/event-window/latest` 返回的 `event_window.shock_fast_lane.llm_analysis` 不能是 pending，除非确实没有 shock。
6. `/api/event-window/shock-lane/latest` 返回的 `shock_fast_lane.llm_analysis` 必须与 latest snapshot 中的解释一致。
7. UI 的 Shock Fast Lane「LLM 中文观察」只读 API payload，不读 HTML 文件。
8. HTML 3 与 UI 使用同一个 snapshot_id/asof_ts 时，中文解释摘要必须一致或显式标记来源差异。

## DoD

1. Event Window run once 后，SQLite latest snapshot 包含 `shock_fast_lane.llm_analysis`。
2. FastAPI `/api/event-window/latest` 可读到非乱码中文解释。
3. FastAPI `/api/event-window/shock-lane/latest` 可读到非乱码中文解释。
4. Event Watchtower UI 显示 `deepseek/success` 或 `deterministic/success`，不再错误显示 pending。
5. HTML 3 审计仍 PASS。
6. `scripts/run_event_window_audit_bundle.py` 仍 PASS。
7. `npm run build` 通过。
8. 后端 Event Window 离线测试通过。
