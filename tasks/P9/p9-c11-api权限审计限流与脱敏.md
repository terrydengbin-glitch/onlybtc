# P9-C11 API 权限、审计、限流与脱敏

## 状态

DONE

## 当前架构对齐（2026-05-22）

P9 API 必须保护 P4.5 LLM provider 配置和数据源密钥。任何 Settings、Run Logs、Source Detail、LLM Detail 接口都不得返回 API key 明文。

日志和响应中涉及外部请求 URL 时，应避免泄露 key query 参数。LLM payload 可以返回 provider/model/status/latency/error，但不能返回完整 prompt 中的密钥或环境变量。

Legacy P4 数据若通过 API 暴露，必须标记为 `legacy_p4_reference`，避免前端误用为当前主结论。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

为 API 提供基础权限、审计日志、限流和敏感数据脱敏。

## SQLite 依赖

- audit_logs
- rate_limit_events
- raw_observations

## 实施范围

- 手动动作审计：Run Once、alert silence、rerun module、refresh source、calibration note。
- Raw response 脱敏。
- API rate limit。
- 错误信息不得泄露密钥。

## 验收标准

- [x] 所有写操作进入 audit_logs。
- [x] API key / cookie / token 不出现在响应中。
- [x] 限流响应可被 Data Quality / Run Logs 追踪。

## 执行记录（2026-06-23）

- 新增 `onlybtc.api.security`。
- 新增 SQLite 表 `audit_logs`，记录 API 写操作：
  - `event_id`
  - `action`
  - `path`
  - `method`
  - `status`
  - `status_code`
  - `actor`
  - `client_host`
  - `request_id`
  - `metadata_json`
- FastAPI 增加 `api_security_middleware`：
  - 对 `POST/PUT/PATCH/DELETE /api/*` 写入 `audit_logs`。
  - 对 JSON response 做递归脱敏。
  - 对 API 请求做轻量滑窗限流。
  - 限流返回标准 API error envelope，错误码 `api_rate_limited`。
- API 限流事件复用 `rate_limit_events`，`source_id` 形如 `api:/api/p45/dashboard/latest`。
- `p45_dashboard.latest_runs()` 增加 `api_security` 聚合段，使 Run Logs 可追踪最近 API audit 和 rate limit event。
- Data Quality 已通过既有 `rate_limit_events` 聚合读取 API rate limit event。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_api_security.py backend\tests\test_api.py::test_run_once_endpoint backend\tests\test_api.py::test_events_sse_once_endpoint -q` -> 5 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\api\security.py backend\src\onlybtc\api\app.py backend\src\onlybtc\api\p45_dashboard.py backend\src\onlybtc\db\schema.py backend\tests\test_api_security.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\api\security.py backend\src\onlybtc\api\app.py backend\src\onlybtc\api\p45_dashboard.py backend\src\onlybtc\db\schema.py backend\tests\test_api_security.py --select I,F` -> passed。
- Online smoke：
  - `GET /api/health` -> healthy。
  - `POST /api/run-once` 后，`GET /api/p45/runs/latest` 可见 `api_security.audit_logs[0].path == "/api/run-once"`。
  - `GET /api/events?once=true` 仍返回 `text/event-stream` 和 `event: p45_run_update`。

## Notes

- 本卡实现的是本地运维 API 的基础 guardrail，不新增用户登录/权限模型。
- SSE `/api/events`、健康检查 `/api/health` 和 `/reports/` 不进入 API 限流，避免影响页面实时订阅和报告访问。
