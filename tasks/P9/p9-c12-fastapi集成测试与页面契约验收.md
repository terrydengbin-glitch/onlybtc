# P9-C12 FastAPI 集成测试与页面契约验收

## 状态

DONE

## 当前架构对齐（2026-05-22）

FastAPI 集成测试必须以 P4.5 Report v2 最新链路为基线。

测试覆盖：`/api/p45/dashboard/latest`、`/api/p45/overview/latest`、`/api/p45/radar-modules/latest`、`/api/p45/radar-modules/{module_id}`、`/api/p45/evidence`、`/api/p45/articles/latest`、`/api/p45/llm/latest`、`/api/p45/invalidation/latest`、`/api/data-quality/latest`、`/api/p45/run-full-with-llm`。

契约断言必须覆盖 run lineage、final_view 一致性、contract_validation、118 evidence 字段覆盖、LLM internal_reference。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

建立 FastAPI 聚合 API 的集成测试和页面契约验收，保证 Vue3 页面能稳定消费。

## SQLite 依赖

- P8-C12 seed data。

## 实施范围

- 每个页面 API 至少一条成功用例。
- realtime / historical mode 分离测试。
- 错误响应测试。
- 脱敏测试。
- Run Once 触发与查询测试。

## 验收标准

- [x] P5 所有页面均可使用 seed data 渲染。
- [x] API schema 与前端 DTO 一致。
- [x] 历史回放 API 不读取实时表。
- [x] 集成测试可在本地一键运行。

## 执行记录（2026-06-23）

- 新增 `backend/tests/test_p9_fastapi_page_contract.py`。
- 通过 `FastAPI TestClient` 覆盖页面聚合端点：
  - `/api/p45/dashboard/latest`
  - `/api/p45/overview/latest`
  - `/api/p45/radar-modules/latest`
  - `/api/p45/radar-modules/{module_id}`
  - `/api/p45/evidence`
  - `/api/p45/articles/latest`
  - `/api/p45/llm/latest`
  - `/api/p45/invalidation/latest`
  - `/api/data-quality/latest`
  - `/api/p45/runs/latest`
- 覆盖历史/实时分离：
  - `/api/p45/history/{final_run_id}` 返回 read-only historical payload。
  - `/api/events?once=true` 仍返回 realtime SSE。
- 覆盖错误响应和脱敏：
  - 404 error envelope 可被前端 `ApiClientError` 消费。
  - query 中的 `api_key` 不进入响应。
- 覆盖 `/api/p45/run-full-with-llm` response lineage 和脱敏契约。
- 增加 LLM `internal_reference` seed 断言。
- 验证 evidence item 覆盖页面消费字段：`evidence_id`、`radar_module`、`metric_id`、`metric_effective_score`、`claim`、`data`、`interpretation`。

## 验证

- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p9_fastapi_page_contract.py backend\tests\test_api_contracts.py -q` -> 5 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m compileall backend\tests\test_p9_fastapi_page_contract.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\tests\test_p9_fastapi_page_contract.py --select I,F` -> passed。
- `npm run build` -> passed。

## Notes

- 本卡使用临时 SQLite seed DB 绑定 FastAPI 路由，避免污染当前生产/开发数据。
- FastAPI `on_event` deprecation warning 是既有启动机制提示，非本卡范围。
