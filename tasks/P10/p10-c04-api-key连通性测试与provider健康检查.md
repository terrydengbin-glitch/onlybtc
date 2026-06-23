# P10-C04 API Key 连通性测试与 Provider 健康检查

## 状态

DONE

## 所属 Phase

P10 API Key 配置与密钥管理

## 任务目标

为每个 provider 提供连接测试和健康状态，供 API Settings、Data Quality、Run Once 使用。

## 实施范围

- FRED：调用轻量 series observations 测试。
- Binance/交易所：公共接口或认证接口测试。
- 链上/期权/news provider：按 provider 能力测试。
- LLM Provider：调用轻量模型列表或空 prompt 测试。
- 记录 last_tested_at、status、latency_ms、error_message。

## 验收标准

- API Settings 弹窗可触发单个 provider 测试。
- 测试结果可被 Data Quality 页面消费。
- 测试失败不会中断主系统。

## 执行记录

- 新增 `backend/src/onlybtc/core/provider_health.py`，统一 provider health snapshot 与轻量连接测试。
- 新增状态契约 `p10.c04.provider_health.v1`：
  - `provider_id`
  - `status`
  - `configured`
  - `supports_test`
  - `last_tested_at`
  - `latency_ms`
  - `http_status`
  - `error_message`
- `/api/settings` 增加 `provider_health` payload，供 Settings 与 Data Quality 页面消费。
- 新增 API：
  - `GET /api/settings/providers/health`
  - `POST /api/settings/providers/{provider_id}/test`
  - `POST /api/settings/providers/health/test-all`
- Provider 探测规则：
  - FRED：轻量 `series/observations`。
  - LLM Provider：OpenAI-compatible `/models`。
  - Glassnode：轻量 BTC close metric endpoint。
  - 未集成 provider 返回 `unsupported`，不抛系统错误。
- 前端 Settings / API Keys 页面显示 provider health，并支持单个 provider `Test`。
- 错误信息会脱敏 `api_key` / bearer token；响应不返回明文 key。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_provider_health.py backend\tests\test_provider_registry.py backend\tests\test_settings_provider_status.py backend\tests\test_env_settings_update.py backend\tests\test_p45_dashboard_api.py::test_p45_settings_masks_api_keys -q` -> 17 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\core\provider_health.py backend\src\onlybtc\api\app.py backend\src\onlybtc\api\p45_dashboard.py` -> passed。
- `npm run build` -> passed。
- 重启后端 `8118` 后：
  - `/api/settings/providers/health` -> `schema_version=p10.c04.provider_health.v1`，`provider_count=10`。
  - `/api/settings` -> includes `provider_health`。
  - `POST /api/settings/providers/cryptoquant/test` -> `status=unsupported`，无 500。
  - `/api/settings` 的 `llm` payload 未暴露 `api_key` / `secret` / `token` 字段。
- 前端 `5188` -> 200；后端日志未发现 Traceback / ERROR / RuntimeWarning。
