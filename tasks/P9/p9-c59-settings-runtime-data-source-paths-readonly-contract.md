# P9-C59 Settings Runtime/Data Source/Paths Read-only Contract

## 状态

DONE

## 执行记录（2026-06-23）

- 新增 `backend/src/onlybtc/core/settings_contract.py`。
- `/api/settings` 新增 `settings_contract`、`runtime`、`data_sources`、`paths` 子域。
- 新增独立 API：
  - `GET /api/settings/runtime`
  - `GET /api/settings/data-sources`
  - `GET /api/settings/paths`
- 新增 `backend/tests/test_settings_contract.py`。
- 当前在线 smoke：
  - `/api/settings/runtime` -> `schema_version=p9.c59.settings_contract.v1`、`read_only=true`
  - `/api/settings/data-sources` -> `source_count=78`、`enabled_count=72`、`fallback_configured_count=9`、`freshness_policy_count=23`
  - `/api/settings/paths` -> `path_count=14`
  - `/api/settings` -> includes `settings_contract.schema_version=p9.c59.settings_contract.v1`

## 所属 Phase

P9 FastAPI 聚合 API 与运维质控

## 前置任务

P9-C14、P9-C58、P10-C01 至 P10-C08、P1-C72、P9-C54。

## Summary

P10 已覆盖 API Key、Provider Registry、LLM Routing、Provider Health 与密钥审计。P9-C14 剩余范围收窄为 Settings 中非密钥子域的可展示契约：runtime/scheduler、source collection policy、paths/storage/maintenance。本卡先提供只读 DTO 与 API，不提供 PATCH 写入，避免没有持久化存储时制造“可更新但不生效”的假配置。

## Scope

- 在 `/api/settings` 中补充 `runtime`、`data_sources`、`paths` 与只读 mutation policy。
- 新增独立读取 API：
  - `GET /api/settings/runtime`
  - `GET /api/settings/data-sources`
  - `GET /api/settings/paths`
- data source DTO 读取 `SOURCE_CONFIGS`、freshness policy、fallback source、collectable/derived-only 状态与 source gate 分组。
- runtime DTO 读取 scheduler、source collector、LLM fallback、P4/P4.5 runtime 默认值。
- paths DTO 读取 PathResolver，并展示路径是否存在。

## Out Of Scope

- 不实现 `PATCH /api/settings/data-sources/{source_id}`。
- 不实现 `PATCH /api/settings/runtime`。
- 不把运行时内存状态误写成持久配置。
- 不返回 API key、cookie、token 或 Authorization header。

## Business Chain / Contract

- Upstream：`Settings`、`PathResolver`、`SOURCE_CONFIGS`、radar runtime cadence/source gate。
- API：Settings Center 和 Data Quality 可读取只读配置契约。
- Downstream：前端可以展示当前调度、刷新、fallback 与路径状态；后续写入型任务必须先定义持久化配置存储和审计。

关键字段：

```text
schema_version
read_only
mutation_policy
runtime.scheduler
runtime.source_collection
data_sources.items[].source_id
data_sources.items[].enabled
data_sources.items[].fallback_source_id
paths.items[].exists
```

## Implementation Plan

1. DONE：新增 settings contract builder。
2. DONE：将 runtime/data_sources/paths payload 注入 `/api/settings`。
3. DONE：新增三个独立 GET API。
4. DONE：增加测试覆盖脱敏、source counts、paths、API 函数。
5. DONE：验证在线 `/api/settings` 与新增 endpoints。

## DoD

- [x] `/api/settings` 包含 runtime/data_sources/paths 子域。
- [x] 三个独立 GET API 可用。
- [x] 所有 payload 不泄露密钥。
- [x] data source DTO 明确 enabled、fallback、freshness policy、derived-only。
- [x] mutation policy 明确只读，避免前端误以为 PATCH 已可用。
- [x] P9-C14 可从 SPLIT 收口。

## Test Plan

- `.venv\Scripts\python.exe -m pytest backend/tests/test_settings_contract.py backend/tests/test_p45_dashboard_api.py::test_p45_settings_masks_api_keys backend/tests/test_provider_health.py backend/tests/test_settings_provider_status.py backend/tests/test_env_settings_update.py backend/tests/test_settings_audit.py -q` -> 20 passed。
- `.venv\Scripts\python.exe -m compileall backend/src/onlybtc/core/settings_contract.py backend/src/onlybtc/api/p45_dashboard.py backend/src/onlybtc/api/app.py` -> passed。
- `.venv\Scripts\python.exe -m ruff check --select I,F backend/src/onlybtc/core/settings_contract.py backend/src/onlybtc/api/p45_dashboard.py backend/src/onlybtc/api/app.py backend/tests/test_settings_contract.py` -> passed。
- `.venv\Scripts\python.exe -m ruff check backend/src/onlybtc/core/settings_contract.py backend/tests/test_settings_contract.py` -> passed。

## Rollback / Risk Notes

- 只读契约不改变运行配置和采集行为，回滚风险低。
- 最大风险是误暴露密钥；测试必须检查 key/token/secret 不出现在 payload 中。
