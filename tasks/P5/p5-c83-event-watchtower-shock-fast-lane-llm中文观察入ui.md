# P5-C83 Event Watchtower Shock Fast Lane LLM 中文观察入 UI

## 目标

在 Event Watchtower 子页面的 Shock Fast Lane 卡片下方新增「LLM 中文观察」区块，展示突发冲击的中文摘要、原因、边界说明与 boundary pass。

## 边界

- UI 不直接读取 `event-window-shock-fast-lane-audit-report.html`。
- HTML 3 仍是审计文件，不参与业务流。
- 数据来自 FastAPI / SQLite payload 中的 `shock_fast_lane.llm_analysis`。
- 该解释不改变 BTC score、radar score、trend direction。

## DoD

1. `shock_fast_lane.llm_analysis` 包含 provider/status/summary_zh/risk_reason_zh/action_boundary_zh/boundary_pass。
2. Event Watchtower 的 Shock Fast Lane 卡片下方展示 LLM 中文观察。
3. 无冲击或无解释时显示 pending/fallback 文案。
4. `npm run build` 通过。
5. Event Window audit bundle 仍 PASS。
