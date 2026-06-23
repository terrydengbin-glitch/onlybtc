# P9-C01 API DTO、错误响应与前后端契约

## 状态

DONE

## 当前架构对齐（2026-05-22）

API DTO 契约以 P4.5 Report v2 为最新业务主线。所有 P5 页面 API 必须返回稳定 DTO，不让前端直接读取 SQLite 表结构或 HTML。

统一错误响应必须包含：`status`、`code`、`message`、`run_id`、`stage`、`recoverable`、`details`。涉及 LLM 失败时，若 deterministic P4.5 主报告成功，应返回 `completed_with_llm_errors`，不是整体 failed。

所有 P4.5 页面 DTO 必须携带 run lineage：`collect_run_id / p2_radar_run_id / p3_run_id / pack_id / final_run_id`。

## 边界更新（2026-06-23）

本卡收口为 P9 API 基础契约层：

- 统一 ok/missing/error envelope。
- 统一 HTTPException 与 validation error 响应。
- 提供 Pydantic contract model，供后续页面聚合 API 复用。
- 页面级具体 DTO 继续由 `P9-C02` 至 `P9-C13` 分卡落地。

P10 已完成的 Settings/API Key/Provider/LLM/Audit 能力不在本卡重复实现，见 `P9-C58 Settings API Supersession Reconciliation`。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

建立所有页面聚合 API 的 DTO、错误响应、分页、时间模式和 id 跳转规范。

## SQLite 依赖

- P8-C10 Repository 层。

## Vue3 依赖

- P5-C20 API Client。

## 实施范围

- DTO 命名与 UI 文档一致。
- 错误响应包含 error_code、message、source_id / module_id / run_id / stage_name。
- realtime 与 historical mode 明确分离。
- id 字段标准：final_run_id、pack_id、run_id、source_id、module_id、evidence_id、llm_research_run_id、llm_analyst_run_id、article_id、alert_id。旧 `snapshot_id` / `debate_id` 仅用于 legacy P4 兼容。

## 验收标准

- [x] 基础 ok/missing/error envelope 有稳定字段。
- [x] `HTTPException` 不再返回 FastAPI 默认 `{"detail": ...}`，统一为 P9 error contract。
- [x] request validation error 统一为 P9 error contract。
- [x] error response 有 Pydantic schema validation。
- [x] 涉及 LLM 失败时，既有 full-chain 逻辑继续保留 `completed_with_llm_errors`。
- [x] 页面级具体 DTO 由后续 P9 页面卡继续承接，避免本卡无限扩张。

## 执行记录（2026-06-23）

- 新增 `ApiErrorItem`、`ApiErrorResponse`、`ApiOkEnvelope`。
- 新增 `http_exception_handler` 与 `validation_exception_handler`。
- FastAPI app 注册 HTTP/validation/global exception handlers。
- 新增 `backend/tests/test_api_contracts.py` 覆盖 404 与 422 contract shape。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_api_contracts.py backend\tests\test_api.py backend\tests\test_p45_dashboard_api.py::test_p45_dashboard_bundle_exposes_final_view_and_lineage -q` -> 7 passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\contracts.py backend\src\onlybtc\api\app.py backend\tests\test_api_contracts.py` -> passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\contracts.py backend\src\onlybtc\api\app.py backend\tests\test_api_contracts.py` -> passed。
