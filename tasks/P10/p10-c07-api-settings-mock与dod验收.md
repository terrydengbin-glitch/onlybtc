# P10-C07 API Settings Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P10 API Key 配置与密钥管理

## 任务目标

用 mock provider 和临时 `.env` 验证 API Settings 配置链路，P10 未通过不得进入真实 LLM 调用和付费数据源调用。

## 实施范围

- mock `.env` 文件。
- provider registry fixture。
- API Settings API 测试。
- 前端弹窗 mock。
- 脱敏与审计测试。

## 验收标准

- mock FRED key 保存后可读取脱敏状态。
- mock LLM key 保存后可进入 provider registry。
- 连接测试成功/失败路径均覆盖。
- 后端测试、ruff、前端 build 通过。

## 执行记录

- 新增 `backend/tests/test_p10_api_settings_dod.py`，覆盖 P10 Settings mock 验收链。
- 新增 `scripts/generate_p10_c07_api_settings_dod_report.py`。
- 输出验收报告：
  - `reports/p10-c07-api-settings-dod-report.json`
  - `reports/p10-c07-api-settings-dod-report.md`
  - `reports/p10-c07-api-settings-dod-report.html`
- Mock `.env` 验收内容：
  - 保存 `ONLYBTC_FRED_API_KEY` 后 provider registry 显示 configured + masked。
  - 保存 `ONLYBTC_DEEPSEEK_API_KEY` 后 LLM provider registry / routing 可发现。
  - unknown env line 保留。
  - audit event 写入且不包含明文 key。
- Provider health mock 验收内容：
  - fake success -> `healthy`。
  - fake failure -> `failed`。
  - success/failure payload 均不含 mock secret。
- Frontend mock 验收内容：
  - `updateSettingsEnv`、`testProviderHealth`、`getSettingsAudit` 已接入。
  - Settings 页面包含 Provider Readiness 与 Recent Key Audit。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p10_api_settings_dod.py backend\tests\test_provider_registry.py backend\tests\test_settings_provider_status.py backend\tests\test_env_settings_update.py backend\tests\test_provider_health.py backend\tests\test_llm_routing.py backend\tests\test_settings_audit.py backend\tests\test_logging.py backend\tests\test_p45_dashboard_api.py::test_p45_settings_masks_api_keys -q` -> 28 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\core\env_writer.py backend\src\onlybtc\core\llm_routing.py scripts\generate_p10_c07_api_settings_dod_report.py` -> passed。
- `.\.venv\Scripts\python.exe -m ruff check backend\src\onlybtc\core\provider_registry.py backend\src\onlybtc\core\config.py backend\src\onlybtc\core\env_writer.py backend\src\onlybtc\core\provider_health.py backend\src\onlybtc\core\llm_routing.py backend\src\onlybtc\core\settings_audit.py backend\src\onlybtc\api\app.py backend\tests\test_p10_api_settings_dod.py backend\tests\test_settings_audit.py scripts\generate_p10_c07_api_settings_dod_report.py` -> passed。
- `npm run build` -> passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p10_c07_api_settings_dod_report.py` -> `status=passed`。
- Report JSON schema: `p10.c07.api_settings_dod_report.v1`，8/8 checks passed。
- Runtime: backend `8118` -> 200；frontend `5188` -> 200。

## Notes

- Ruff validation is scoped to P10-owned/new settings files plus API entrypoint. `backend/src/onlybtc/api/p45_dashboard.py` still contains pre-existing historical E501 long-line debt outside this card's scope.
