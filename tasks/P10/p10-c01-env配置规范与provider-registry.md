# P10-C01 .env 配置规范与 Provider Registry

## 状态

DONE

## 所属 Phase

P10 API Key 配置与密钥管理

## 任务目标

建立统一 provider registry，明确所有外部 API、LLM Provider 与配置项如何通过 `.env` 和 UI 管理。

## 实施范围

- 定义 `.env.example`。
- 统一命名：`ONLYBTC_FRED_API_KEY`、`ONLYBTC_DEEPSEEK_API_KEY`、`ONLYBTC_QWEN_API_KEY`、`ONLYBTC_VOLCANO_API_KEY`、`ONLYBTC_KIMI_API_KEY` 等。
- Provider registry 字段：provider_id、name、category、env_key、required、supports_test、docs_url、masked_value、configured。
- 区分数据源 provider 与 LLM provider。
- 支持后续新增 Glassnode、CryptoQuant、Deribit、Coinglass、News API 等。

## 输出

- Provider registry 代码或配置文件。
- `.env.example`。
- Provider 分类规范。
- `/api/settings` 可消费的脱敏 provider registry payload。

## 验收标准

- 所有当前与规划中的 API Key 都有标准 env key。
- registry 可被 P9 API 与 P5 弹窗消费。
- 不在仓库中写入真实 key。
- provider payload 只暴露 `configured` / `masked_value`，不暴露原始 key。

## 执行记录

- 新增 `backend/src/onlybtc/core/provider_registry.py`。
- 新增 `backend/tests/test_provider_registry.py`。
- `/api/settings` 增加 `providers` payload，schema 为 `p10.c01.provider_registry.v1`。
- `.env.example` 增加规划 provider key：`ONLYBTC_GLASSNODE_API_KEY`、`ONLYBTC_CRYPTOQUANT_API_KEY`、`ONLYBTC_COINGLASS_API_KEY`、`ONLYBTC_NEWS_API_KEY`。
- 当前 registry 覆盖 provider：FRED、DeepSeek、OpenAI、Qwen、Volcano、Kimi、Glassnode、CryptoQuant、Coinglass、News API。
- 运行态验证：`/api/settings` 返回 provider registry，未暴露原始 `*_api_key` 字段。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_provider_registry.py backend\tests\test_p45_dashboard_api.py::test_p45_settings_masks_api_keys -q` -> 5 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\core\provider_registry.py backend\src\onlybtc\api\p45_dashboard.py` -> passed。
- 重启后端 `8118` 后，`/api/settings` 返回 `providers.schema_version=p10.c01.provider_registry.v1`。
- `/api/health` -> healthy；前端 `5188` -> 200。
