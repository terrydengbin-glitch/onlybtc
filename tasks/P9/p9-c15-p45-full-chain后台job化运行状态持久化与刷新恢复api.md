# P9-C15 P4.5 Full Chain 后台 Job 化、运行状态持久化与刷新恢复 API

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

当前 `POST /api/p45/run-full-with-llm` 是长请求，浏览器刷新会切断前端请求生命周期。刷新后前端只能重新读取 latest payload，无法知道刚才那条 P1/P2/P3/P4.5/LLM 全链条是否仍在运行、跑到哪个阶段、是否已完成。

这会导致 Run Logs 页面显示旧 latest run，或者一边使用旧 route context，一边请求新旧不一致的阶段数据。

## 根因

```text
点击 Run Full Chain
  -> 前端发起长 POST /api/p45/run-full-with-llm
  -> 后端同步等待整条 pipeline 完成
  -> 用户刷新页面
  -> 前端 state.running / runResult 丢失
  -> 新页面只能读取 latest final payload
  -> 无法恢复当前 running job
```

数据库已有 `runs`、`run_stages`、`run_logs`、`worker_heartbeats` 表，但 P4.5 Full Chain 真实 pipeline 尚未完整接入运行状态持久化。

## 目标

- 将 P4.5 Full Chain 从“浏览器长请求绑定”改成“后台 job + 可轮询状态”。
- 每次触发全链条运行时生成稳定 `job_run_id`。
- 将 P1/P2/P3/P4.5/LLM 阶段状态写入 SQLite `runs/run_stages/run_logs`。
- 刷新页面后可通过 `job_run_id` 或 latest running job 恢复运行态。
- latest completed payload 与 running job 状态分离，避免半成品污染 Dashboard。

## 实施范围

### API

- `POST /api/p45/run-full-with-llm/jobs`
  - 启动后台 job。
  - 立即返回 `job_run_id`、`status=running`、初始 stage。
- `GET /api/p45/run-full-with-llm/jobs/{job_run_id}`
  - 返回 job 当前状态、stage 列表、run lineage、错误、审计报告链接。
- `GET /api/p45/run-full-with-llm/jobs/latest`
  - 返回最近一个 running/queued job；若没有 running job，可返回最近 completed job。
- 保留旧 `POST /api/p45/run-full-with-llm` 兼容接口，但前端新流程优先使用 job API。

### SQLite

- 复用现有 `runs`、`run_stages`、`run_logs` 表。
- 不新增表，除非现有 schema 无法表达 job 结果。
- `run_id` 使用 `p45job-YYYYMMDDHHMMSS-xxxxxx` 或等价稳定 ID。
- stage 建议：

```text
p1_collect
p2_radar
p3_scoring
p45_final
p45_llm_research
p45_llm_analysts
audit_reports
completed
```

### 后端运行边界

- 后台 job 运行期间，latest Dashboard 仍只读取最后一个 completed P4.5 final。
- running 状态只通过 job API 暴露。
- job 失败时写入 `status=failed`、`current_stage`、错误摘要和日志。

## 输出契约

```json
{
  "job_run_id": "p45job-...",
  "status": "running",
  "current_stage": "p3_scoring",
  "started_at": "...",
  "completed_at": null,
  "run_lineage": {
    "collect_run_id": "...",
    "p2_radar_run_id": "...",
    "p3_run_id": null,
    "final_run_id": null
  },
  "stages": [
    {
      "stage_id": "p1_collect",
      "label": "P1 collect",
      "status": "completed",
      "run_id": "collect-...",
      "started_at": "...",
      "completed_at": "...",
      "error": null
    }
  ],
  "audit_reports": []
}
```

## DoD

- 刷新页面不会中断后端 job 状态可见性。
- `GET /jobs/latest` 能恢复 running job。
- Run Logs 可显示真实 running/completed/failed stage。
- latest Dashboard 不读取半成品，只读取最近 completed final。
- 旧 `/api/p45/run-full-with-llm` 兼容，不破坏现有脚本。
- FastAPI 测试覆盖：启动 job、查询 running、查询 completed、失败状态、无 running job。

## 关联任务

P5-C37, P9-C07, P9-C10, P9-C16, P8-C05, P4.5-C17

## 执行记录

- 新增 `backend/src/onlybtc/api/p45_jobs.py`，复用 SQLite `runs/run_stages/run_logs` 保存 P4.5 Full Chain job。
- 新增后台 job API：
  - `POST /api/p45/run-full-with-llm/jobs`
  - `GET /api/p45/run-full-with-llm/jobs/latest`
  - `GET /api/p45/run-full-with-llm/jobs/{job_run_id}`
- Job stage 覆盖 `p1_collect / p2_radar / p3_scoring / p45_final / p45_llm_research / p45_llm_analysts / audit_reports`。
- 旧 `POST /api/p45/run-full-with-llm` 保留兼容。
- 调整 `RunState` domain model，允许 P4.5 job 自定义 trigger/status/stage 字符串，避免旧 mock stage 枚举阻塞真实 P4.5 job。

## 验证结果

```text
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py backend/tests/test_p3_pipeline.py backend/tests/test_p45_final_writer.py backend/tests/test_p45_html_report.py backend/tests/test_p45_evidence_pack.py -q
passed

npm run build
passed
```
