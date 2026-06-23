# P10-C02 FastAPI Settings 与密钥脱敏状态读取

## 状态

DONE

## 所属 Phase

P10 API Key 配置与密钥管理

## 任务目标

扩展 FastAPI settings，使 FRED、交易所、链上数据、期权数据、新闻源和多 LLM Provider 的 key 都可以从 `.env` 读取，并输出脱敏配置状态。

## 实施范围

- 扩展 `Settings`。
- 实现密钥脱敏：只展示前后少量字符或 `configured=true`。
- 支持 settings cache reload。
- 提供 provider 状态读取服务。

## 验收标准

- `.env` 中配置的 key 能被后端读取。
- API 返回脱敏状态，不返回完整 key。
- 修改 `.env` 后可刷新配置。

## 执行计划

- 扩展 `Settings` 读取规划 provider key。
- 增加 settings cache reload helper。
- 增加 `/api/settings/reload`。
- 复用 P10-C01 provider registry 输出脱敏状态。
- 增加测试覆盖 planned provider key、reload helper、API 不泄露原始 key。

## 执行记录

- `Settings` 增加规划 provider key：`glassnode_api_key`、`cryptoquant_api_key`、`coinglass_api_key`、`news_api_key`。
- 新增 `reload_settings()`，用于清理 settings cache 并重新读取 `.env` / 环境变量。
- `/api/settings/reload` 支持运行态刷新配置，并复用 `/api/settings` 的脱敏响应契约。
- Provider registry 已接入规划 provider 的 settings 字段，返回 `configured`、`masked_value`、`status`，不返回原始 key。
- 新增 `backend/tests/test_settings_provider_status.py` 覆盖 provider key 读取、脱敏、reload helper 与 reload API。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_settings_provider_status.py backend\tests\test_provider_registry.py backend\tests\test_api.py::test_health_endpoint backend\tests\test_p45_dashboard_api.py::test_p45_settings_masks_api_keys -q` -> 9 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\core\config.py backend\src\onlybtc\core\provider_registry.py backend\src\onlybtc\api\app.py` -> passed。
- 重启后端 `8118` 后，`GET /api/settings` 返回 `providers.schema_version=p10.c01.provider_registry.v1`、`provider_count=10`，未暴露原始 `*_api_key`。
- `POST /api/settings/reload` -> 200，并返回脱敏 settings summary。
- `/api/health` -> healthy；前端 `5188` -> 200。
