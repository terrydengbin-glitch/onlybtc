# P9-C07 Run Logs 聚合 API 与 Run Once 触发接口

## 状态

DONE

## 当前架构对齐（2026-05-22）

Run Once API 必须触发 P4.5 全链条，不再使用 P0 mock run 作为生产入口。

新增/调整 API：

- `POST /api/p45/run-full-with-llm`
- `GET /api/p45/runs/latest`
- `GET /api/runs/{run_id}`
- `GET /api/p45/audit-reports/latest`
- `GET /api/runs/{run_id}/audit-reports`

返回必须包含 P1/P2/P3/P4.5/LLM 子阶段、报告路径、run lineage、`completed_with_llm_errors` 降级状态、LLM provider/model/latency/error。

API 需要返回审计报告索引 `audit_reports`，供 Dashboard 与 Run Logs 展示原始 HTML 报告入口。前端只打开这些链接，不解析 HTML。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现运行日志页 API 和 Run Once 手动触发接口。

## API

- `GET /api/runs/{run_id}`
- `POST /api/p45/run-full-with-llm`
- `GET /api/p45/runs/latest`
- `GET /api/p45/audit-reports/latest`
- `GET /api/runs/{run_id}/audit-reports`

## SQLite 依赖

- runs
- run_stages
- worker_heartbeats
- run_logs
- retry_records
- report artifact paths from P1/P2/P3/P4.5 pipeline

## Vue3 对应任务

- P5-C07
- P5-C15

## 验收标准

- [x] Run Once 生产入口为 `POST /api/p45/run-full-with-llm/jobs`，创建 `job_run_id` 并进入 P4.5 full-chain job。
- [x] Legacy `POST /api/run-once` 保留 mock 兼容，并显式返回 `deprecated` / `legacy_mock` 标记。
- [x] Run Logs API 返回 stage、worker、失败重试占位和产物链接。
- [x] Run Logs API 返回 `audit_reports`：`phase`、`report_type`、`path`、`url`、`run_id`、`created_at`、`status`。
- [x] 运行中 progress 可被前端通过 `/api/p45/run-full-with-llm/jobs/{job_run_id}` 轮询更新。

## 执行记录（2026-06-23）

- `latest_runs()` 增加：
  - `run_lineage`
  - `run_id`
  - `run_status`
  - `progress`
  - `logs`
  - scoped `audit_reports`
- `_run_stages()` 增加：
  - `worker_id`
  - `retry_count`
  - `failed_retry_count`
- `audit_reports()` 增加：
  - `report_type`
  - `url`
  - `run_id`
  - `created_at`
  - `status`
- `p45_jobs.job_status()` 增加：
  - `llm_errors`
  - `audit_reports`
  - stage `worker_id`
  - log `metadata`
- Legacy `/api/run-once` 增加 `run_entrypoint=legacy_mock`、`deprecated=true`、`production_entrypoint=/api/p45/run-full-with-llm/jobs`。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py::test_p45_job_status_uses_runtime_tables backend\tests\test_p45_dashboard_api.py::test_p45_latest_runs_exposes_stage_lineage backend\tests\test_api.py::test_run_once_endpoint -q` -> 3 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\p45_dashboard.py backend\src\onlybtc\api\p45_jobs.py backend\src\onlybtc\api\app.py backend\tests\test_p45_dashboard_api.py backend\tests\test_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\p45_jobs.py backend\src\onlybtc\api\app.py backend\tests\test_p45_dashboard_api.py backend\tests\test_api.py --select I,F` -> passed。

## Notes

- 本卡不改变 P4.5 full-chain 执行语义，只补 Run Logs / Audit Reports DTO 与 legacy mock 入口标记。
- FastAPI `on_event` deprecation warning 属既有启动机制提示，非本卡范围。
