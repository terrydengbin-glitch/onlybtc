# P5-C18 History Replay 历史回放页

## 状态

DONE

## 当前架构对齐（2026-05-22）

History Replay 以历史 P4.5 `final_run_id` 为锚点回放完整链路。

FastAPI 读取：`GET /api/p45/history`、`GET /api/p45/history/{final_run_id}`。

回放必须冻结：final payload、evidence pack payload、analyst articles、LLM research/analyst payload、run lineage。历史模式必须明显标记，不得误导为实时状态。

## 所属 Phase

P5 Dashboard 全量可视化

## 任务目标

实现历史判断复盘与反馈学习页，回放当时 Dashboard、Evidence、LLM Appendix、Article、Alerts 和后续评分。

## UI 依据

- [ui方案-p5-dashboard.md](../../ui方案-p5-dashboard.md)
- `ui-references/p5-history-replay-page-*.png`

## FastAPI 依赖

- P9-C09：`GET /api/replay/snapshots`
- P9-C09：`GET /api/p45/history/{final_run_id}`

## SQLite 依赖

- P4.5 historical final payload
- P4.5 historical evidence pack payload
- P4.5 historical LLM appendix payload
- replay_scores
- calibration_notes

## 实施范围

- Historical Mode 顶栏。
- Timeline。
- Historical Snapshot Replay。
- Replay Analysis。
- Evidence/LLM/Article/Run Logs 历史链接。
- 回放当时的 P4.5 final payload、Radar outputs、P3 alerts/invalidation、Evidence Pack、LLM Appendix、中文文章。
- 保留当时的 `run_mode`、`runtime_mode`、fallback 与 data quality 状态，不用当前最新状态覆盖。

## 验收标准

- 历史模式必须明显，不误导为实时。
- Replay 只读 snapshot，不读当前实时状态。
- 使用 Signal Validity / Alert Validity / Confidence Calibration，不使用 Call Accuracy。
- 实时 SSE/WebSocket 推送不能污染历史模式页面状态。

## 完成记录

- `frontend/src/App.vue`：History Replay 页面新增历史快照列表，可按 `final_run_id` 调用 `GET /api/p45/history/{final_run_id}`。
- `frontend/src/App.vue`：历史模式顶栏明确显示 `historical mode` / `latest mode`，并提供 Freeze Current Run 与 Exit Replay。
- `frontend/src/App.vue`：回放页展示 frozen final payload 的 decision、confidence、runtime、article、run lineage、analyst count 和 audit reports。
- `frontend/src/App.vue`：Replay Analysis 使用 Signal Validity / Alert Validity / Confidence Calibration 文案，不使用 Call Accuracy。
- `frontend/src/styles.css`：补齐 History Replay hero、action row、snapshot layout、audit report 的响应式样式。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
