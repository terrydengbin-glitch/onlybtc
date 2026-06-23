# P9-C10 SSE/WebSocket 实时推送与前端订阅

## 状态

DONE

## 当前架构对齐（2026-05-22）

实时推送阶段事件以 P4.5 全链条为准：

```text
collecting -> radar_analysis -> p3_scoring -> p45_pack -> p45_final -> llm_research -> llm_analysts -> html_api_refresh -> completed
```

事件 payload 必须带 `run_id`、当前 stage、lineage、status、error、report paths、LLM latency summary。LLM 错误不应中断 deterministic final 的完成事件。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

实现 Dashboard、Run Once、Data Quality、Alerts 的实时推送能力。

## API

- `GET /api/events`

## SQLite 依赖

- runs
- run_stages
- P4.5 final payload / dashboard DTO refresh event
- algorithm_alerts
- data_quality_snapshots

## Vue3 对应任务

- P5-C20

## 验收标准

- [x] Dashboard 可实时收到 snapshot/update 事件。
- [x] Run Once / P4.5 full-chain job 可实时收到 stage progress。
- [x] History Replay 不订阅实时覆盖。
- [x] 断线重连后可恢复当前状态；现有 polling 作为 fallback。
- [x] LLM 错误通过 `llm_latency_summary.llm_errors` 随事件透传，不中断 deterministic final。

## 执行记录（2026-06-23）

- 新增 `GET /api/events` SSE endpoint。
- SSE payload schema：`p9.c10.events.v1`。
- 事件类型：`p45_run_update`。
- Payload 包含：
  - `run_id`
  - `current_stage`
  - `lineage`
  - `status`
  - `error`
  - `report_paths`
  - `llm_latency_summary`
  - `job`
  - `data_quality`
  - `alerts`
  - `recoverable`
- `GET /api/events?once=true` 支持首帧测试与断线恢复探测。
- 前端 store 增加：
  - `eventStreamStatus`
  - `eventStreamLastEvent`
  - `startEventStream()`
  - `stopEventStream()`
- `refreshLatest()` 在 latest 模式下幂等启动 SSE。
- `loadHistory()` 进入历史模式时关闭 SSE，避免 latest 实时事件覆盖 frozen replay。
- 现有 job polling 保留为 SSE 断线 fallback。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_api.py::test_events_sse_once_endpoint backend\tests\test_api.py::test_run_once_endpoint -q` -> 2 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\app.py backend\tests\test_api.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\app.py backend\tests\test_api.py --select I,F` -> passed。
- `npm run build` -> passed。

## Notes

- 本卡选择 SSE 而不是 WebSocket，满足 dashboard/job progress 单向实时更新，复杂度更低。
- FastAPI `on_event` deprecation warning 是既有启动机制提示，非本卡范围。
