# P5-C15 Run Logs 运行日志页

## 状态

DONE

## 当前架构对齐（2026-05-22）

Run Logs 页必须展示 P4.5 一键全链条状态，而不是只展示 P0 mock run。

FastAPI 读取：`GET /api/p45/runs/latest`、`GET /api/runs/{run_id}`。

日志阶段必须覆盖：P1 collect、P2 radar、P3 algorithm/scored evidence、P4.5 evidence pack、P4.5 deterministic final、LLM research、LLM analysts、HTML/API refresh。

LLM 失败时展示 `completed_with_llm_errors`，并说明 deterministic 主报告仍可用。

Run Logs 同时承担审计报告索引职责。用户必须能在同一 run 下打开 P1/P2/P3/P4.5 的 HTML 报告，查看原始数据、Radar 质检、P3 审计和 P4.5 研究报告。

## 所属 Phase

P5 Dashboard 全量可视化

## 任务目标

实现全流程运行审计页，展示 Run Once、定时任务、worker、stage、失败重试和产物链接。

## UI 依据

- [ui方案-p5-dashboard.md](../../ui方案-p5-dashboard.md)
- `ui-references/p5-run-logs-page-*.png`

## FastAPI 依赖

- P9-C07：`GET /api/runs`
- P9-C07：`GET /api/runs/{run_id}`
- P9-C07：`POST /api/run-once`

## SQLite 依赖

- runs
- run_stages
- worker_heartbeats
- run_logs
- retry_records

## 实施范围

- Current Run Status。
- Run Timeline。
- Task History、Retry Records、Failure Analysis。
- Stage Details、Live Logs、Worker Execution。
- 展示 P1/P2/P3/P4.5 全链条产物链接：P1 HTML、P2 HTML、P3 HTML、P4.5 HTML、GPT independent validation 如存在。
- 单独提供 `Audit Reports` 区块，列出报告类型、文件路径、生成时间、run_id、状态、打开链接。
- 报告链接只用于审计查看，不作为 Vue3 数据渲染来源。
- 对 LLM provider timeout、schema fallback、source HTTP 403、manual reauth required 做结构化展示。

## 验收标准

- Run Once 运行中必须有 progress。
- 失败原因必须能定位 source_id / module_id / stage_name。
- 产物链接可跳转 Evidence、LLM Appendix、Article、Alerts、History。
- 产物链接可打开 P1/P2/P3/P4.5 原始 HTML 报告。
- 同一 run 的所有子 run_id 必须集中展示，不能让用户到日志里手工找。

## 完成记录

- `frontend/src/App.vue`：Run Logs 页面新增 Run Lineage 总览，集中展示 collect / p2 radar / p3 / pack / article / final / LLM run_id。
- `frontend/src/App.vue`：阶段卡片补齐 stage_id、更新时间、source/module/metric/error scope、非阻塞 LLM 降级说明和阶段报告按钮。
- `frontend/src/App.vue`：Audit Reports 区块补齐报告类型、phase、大小、更新时间、路径和 FastAPI `/reports/` 打开链接。
- `frontend/src/App.vue`：新增 warnings/errors 展示，区分 degraded-but-auditable 与 blocking failures。
- `frontend/src/styles.css`：补齐 Run Logs lineage、issue、stage metadata、audit report 的响应式布局。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
