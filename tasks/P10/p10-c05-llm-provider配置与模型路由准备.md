# P10-C05 LLM Provider 配置与模型路由准备

## 状态

DONE

## 所属 Phase

P10 API Key 配置与密钥管理

## 任务目标

为 P4 多 LLM 讨论准备 provider 配置与模型路由，使 DeepSeek、Qwen、火山、Kimi 等模型可以统一配置、测试和调用。

## 实施范围

- Provider：DeepSeek、Qwen、火山、Kimi。
- 配置字段：api_key、base_url、model、enabled、timeout、max_tokens、temperature。
- 支持 mock provider。
- 支持 provider disabled 时自动跳过。

## 验收标准

- P4 能按 provider registry 发现可用 LLM。
- 未配置 key 的模型不会参与真实调用。
- mock 模式可完整跑通多 LLM 流程。

## 2026-05-21 P4 Agent Runtime 对齐补充

P4 已从“多 LLM 模型盲审”升级为“4 个 Analyst Agent + Cross-examination Agent + Judge Agent”。因此 P10-C05 的 provider 配置不再等同于业务角色，而是给 P4-C15 Runtime Adapter 提供可测试的模型路由。

`.env` 需要支持直接填写 4 个 LLM Provider API，方便本地测试：

```env
ONLYBTC_DEEPSEEK_API_KEY=
ONLYBTC_DEEPSEEK_BASE_URL=https://api.deepseek.com
ONLYBTC_DEEPSEEK_MODEL=deepseek-reasoner
ONLYBTC_DEEPSEEK_ENABLE_THINKING=true

ONLYBTC_QWEN_API_KEY=
ONLYBTC_QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ONLYBTC_QWEN_MODEL=qwen3.6-max-preview
ONLYBTC_QWEN_ENABLE_THINKING=true

ONLYBTC_VOLCANO_API_KEY=
# Volcengine console: https://www.volcengine.com/
# Ark OpenAI-compatible API base_url must use the API host below, not the website URL.
ONLYBTC_VOLCANO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ONLYBTC_VOLCANO_MODEL=doubao-seed-2-0-pro-260215
ONLYBTC_VOLCANO_ENABLE_THINKING=true

ONLYBTC_KIMI_API_KEY=
ONLYBTC_KIMI_BASE_URL=https://api.moonshot.cn/v1
ONLYBTC_KIMI_MODEL=kimi-k2.6
ONLYBTC_KIMI_ENABLE_THINKING=true
```

同时为 OpenAI Agents SDK 执行层预留：

```env
ONLYBTC_OPENAI_API_KEY=
ONLYBTC_OPENAI_BASE_URL=https://api.openai.com/v1
ONLYBTC_OPENAI_MODEL=gpt-4.1-mini
```

P4 Agent 默认路由通过 `.env` 配置：

```env
ONLYBTC_P4_MACRO_EVENT_PROVIDER=deepseek
ONLYBTC_P4_LIQUIDITY_FLOW_PROVIDER=qwen
ONLYBTC_P4_LEVERAGE_MICROSTRUCTURE_PROVIDER=volcano
ONLYBTC_P4_ONCHAIN_MARKET_STRUCTURE_PROVIDER=kimi
ONLYBTC_P4_JUDGE_PROVIDER=openai
ONLYBTC_P4_CROSS_EXAM_PROVIDER=openai
ONLYBTC_P4_USE_MOCK_LLM=true
```

要求：

- 未填写 API key 的 provider 必须视为 disabled。
- `ONLYBTC_P4_USE_MOCK_LLM=true` 时不触发真实模型调用。
- P4-C15 可读取这些字段生成 runtime routing，但不能把 provider 名称当成业务分析师角色。

## 执行记录

- 新增 `backend/src/onlybtc/core/llm_routing.py`，输出 LLM routing 契约 `p10.c05.llm_routing.v1`。
- `/api/settings` 增加 `llm_routing` payload。
- 新增 `GET /api/settings/llm-routing`。
- `ProviderConfig` 增加：
  - `enabled`
  - `disabled_reason`
  - `timeout_seconds`
  - `max_tokens`
  - `temperature`
- `Settings` 增加：
  - `p4_llm_max_tokens_per_call`
  - `p4_llm_temperature`
- P4 OpenAI-compatible runtime 使用统一 `temperature` / `max_tokens`。
- Provider disabled 规则对齐 registry：空值与 placeholder key 都视为未配置。
- `.env.example` 补齐 P4 LLM runtime 参数与 adversarial/article route。
- 前端 Settings / LLM Providers 页面展示：
  - mock mode / fallback policy / timeout / max tokens / temperature
  - provider readiness
  - P4 Agent Routes
- routing payload 只暴露 `api_key_configured` 布尔状态，不暴露明文 key。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_llm_routing.py backend\tests\test_p4_agent_runtime.py backend\tests\test_provider_health.py backend\tests\test_provider_registry.py backend\tests\test_p45_dashboard_api.py::test_p45_settings_masks_api_keys -q` -> 26 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\core\llm_routing.py backend\src\onlybtc\core\config.py backend\src\onlybtc\p4\agent_runtime.py backend\src\onlybtc\api\app.py backend\src\onlybtc\api\p45_dashboard.py` -> passed。
- `npm run build` -> passed。
- 重启后端 `8118` 后：
  - `/api/settings/llm-routing` -> `schema_version=p10.c05.llm_routing.v1`，`providers=5`，`routes=8`。
  - `/api/settings` -> includes `llm_routing`。
  - `/api/health` -> 200；前端 `5188` -> 200。
  - 后端日志未发现 Traceback / ERROR / RuntimeWarning。
