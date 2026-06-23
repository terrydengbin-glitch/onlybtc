# P9-C13 FastAPI API Mock 与 DoD 验收

## 状态

DONE

## 当前架构对齐（2026-05-22）

API mock fixture 必须按 P4.5 Report v2 构造，不再按旧 P4 Debate 构造。

必须提供：正常 run、contract warning run、LLM completed run、LLM completed_with_llm_errors run、data quality degraded run、historical replay run、legacy P4 reference run。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

用 mock repository 和 seed database 验证所有页面聚合 API、实时推送、Run Once 触发、权限审计和错误响应。P9-C13 未通过，不进入 P5 页面联调。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 覆盖 Dashboard、BTC Overview、Article、Evidence、LLM Appendix、Alerts、Invalidation、Data Quality、Run Logs、Source Detail、Radar Detail、History Replay API。
- 验证 API DTO、错误响应、分页、过滤、历史模式。
- 验证 SSE / WebSocket 实时推送。
- 验证 Run Once 触发接口、幂等、防重复运行。
- 验证 API 权限、审计、限流、脱敏。
- 验证静态资源、导出文件路径通过 Path Resolver。

## 输入

P9-C01 至 P9-C12，P8-C13 seed database，P0-C10 Path Resolver。

## 输出

- [x] API mock server。
- [x] contract test report。
- [x] OpenAPI / DTO snapshot。
- [x] P9 DoD 验收清单。

## 验收标准

- [x] 所有 P5 页面都有对应可用 API。
- [x] API 不暴露数据库表结构，只返回页面 DTO。
- [x] mock repository 与真实 SQLite repository 的 DTO 一致。
- [x] 历史模式不读取当前实时状态。
- [x] 错误、限流、数据缺失、权限不足都有稳定响应。
- [x] P9 DoD 全部通过后，才允许进入 P5 页面联调。

## 执行记录（2026-06-23）

- 新增 P9-C13 mock fixture：
  - `backend/src/onlybtc/api/mock_fixtures.py`
  - `backend/src/onlybtc/api/mock.py`
- 新增 API mock endpoint：
  - `GET /api/mock/p9-c13/scenarios`
- Mock scenarios 覆盖：
  - `normal_run`
  - `contract_warning_run`
  - `llm_completed_run`
  - `llm_completed_with_llm_errors_run`
  - `data_quality_degraded_run`
  - `historical_replay_run`
  - `legacy_p4_reference_run`
- 新增 DoD 报告生成器：
  - `scripts/generate_p9_c13_api_mock_dod_report.py`
- 输出报告：
  - `reports/p9-c13-api-mock-dod-report.json`
  - `reports/p9-c13-api-mock-dod-report.md`
  - `reports/p9-c13-api-mock-dod-report.html`
  - `reports/p9-c13-openapi-snapshot.json`
  - `reports/p9-c13-frontend-dto-snapshot.json`
- 报告状态：`overall_status = passed`，`failed_checks = 0`。

## 验证

- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p9_c13_api_mock_dod.py -q` -> 3 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m pytest backend\tests\test_p9_c13_api_mock_dod.py backend\tests\test_p9_fastapi_page_contract.py backend\tests\test_api_security.py -q` -> 9 passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\mock.py backend\src\onlybtc\api\mock_fixtures.py scripts\generate_p9_c13_api_mock_dod_report.py backend\tests\test_p9_c13_api_mock_dod.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\mock.py backend\src\onlybtc\api\mock_fixtures.py scripts\generate_p9_c13_api_mock_dod_report.py backend\tests\test_p9_c13_api_mock_dod.py --select I,F` -> passed。
- `PYTHONPATH=backend/src;backend/tests .\.venv\Scripts\python.exe scripts\generate_p9_c13_api_mock_dod_report.py` -> reports generated。
- Online smoke：
  - `GET /api/health` -> healthy。
  - `GET /api/mock/p9-c13/scenarios` -> `schema_version=p9.c13.api_mock.v1`，`scenario_count=7`。

## Notes

- Mock endpoint 只提供契约样例，不改变真实 P4.5 runtime / SQLite repository 路径。
- P9-C13 报告将 OpenAPI 与前端 DTO snapshot 固化到 `reports/`，作为进入 P5 页面联调的证据。

## 依赖任务

P9-C01、P9-C02、P9-C03、P9-C04、P9-C05、P9-C06、P9-C07、P9-C08、P9-C09、P9-C10、P9-C11、P9-C12、P8-C13、P0-C10

## 备注

P9 的核心验收标准是“前端只看契约也能开发”，而不是后端内部实现完成多少。
