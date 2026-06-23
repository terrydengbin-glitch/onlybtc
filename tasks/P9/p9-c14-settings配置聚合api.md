# P9-C14 Settings 配置聚合 API

## 状态

DONE

## Final Closure（2026-06-23）

P9-C14 已完成收口：

- P10-C01 至 P10-C08 覆盖 API Key、Provider Registry、Provider Health、LLM Routing、密钥审计、Glassnode entitlement audit。
- P9-C59 覆盖 P10 未覆盖的非密钥 Settings 子域，只读暴露 runtime/scheduler、data source policy、paths/storage/maintenance。
- 写入型 `PATCH /api/settings/data-sources/{source_id}` 与 `PATCH /api/settings/runtime` 未在本卡实现，原因是需要先建立持久化配置存储、operator auth、settings audit 与 runtime reload/restart policy；P9-C59 已在 mutation policy 中显式声明 read-only，避免前端误判。
- 因此 P9-C14 原始范围已被 P10 + P9-C59 覆盖或显式转为未来独立写入契约，不再作为开放主线任务保留。

## 当前架构对齐（2026-05-22）

Settings API 必须暴露 P4.5 运行配置摘要，并脱敏所有 key。

返回字段：`p45_research_provider`、DeepSeek model、`p45_research_timeout_seconds`、`p45_research_max_retries`、default `run_mode`、default `runtime_mode`、default `llm_runtime_mode`、configured provider health summary。

禁止返回 API key 明文。

## 对账更新（2026-06-23）

P10-C01 至 P10-C07 已完成 Settings/API Key/Provider/LLM Routing/Health/Audit 主链路，并由 `reports/p10-c07-api-settings-dod-report.*` 验收通过。

本卡不再重复覆盖以下 P10 已完成能力：

- Provider Registry 与 `.env.example` key 规范。
- `GET /api/settings` 的 provider registry、masked provider status、provider health、LLM routing、settings audit。
- `POST /api/settings/env` 安全写入 `.env`、保留未知行、写入后 reload。
- `POST /api/settings/reload`。
- Provider 单测/批量连通性测试。
- LLM Provider route readiness。
- 密钥操作审计与脱敏日志。

剩余范围收窄为 P10 未覆盖的 Settings 子域：数据源刷新频率/启用/fallback 策略、runtime/scheduler/Run Once/发布策略、paths/storage/maintenance 配置展示，以及这些子域的 DTO、错误响应和前端消费契约。

对账任务：`P9-C58 Settings API Supersession Reconciliation`。

## 所属 Phase

P9 FastAPI 页面聚合 API 与前后端契约

## 任务目标

为 Settings 设置中心提供后端聚合接口，支持 API Key、数据源、LLM Provider、雷达阈值、运行策略、发布策略、路径与系统维护配置的读取、更新、测试和审计。

## 背景依据

- [开发文档.md](../../开发文档.md)
- P5-C22 Settings 设置中心页面
- P10 API Key 配置与密钥管理

## 实施范围

- `GET /api/settings`：读取 Settings Center 全量配置状态。
- `GET /api/settings/providers`：读取 provider registry 与脱敏配置状态。
- `POST /api/settings/providers/{provider_id}`：更新 provider 配置。
- `POST /api/settings/providers/{provider_id}/test`：测试连接。
- `DELETE /api/settings/providers/{provider_id}`：清空 provider 配置。
- `PATCH /api/settings/data-sources/{source_id}`：更新数据源刷新频率、启用状态、fallback 策略。
- `PATCH /api/settings/runtime`：更新调度、Run Once、发布策略等运行配置。
- `GET /api/settings/paths`：读取路径与存储配置。
- 所有响应必须脱敏，不返回完整 key。
- 写入 `.env` 后刷新 settings cache 或标记需要重启。
- 记录配置操作日志，不记录明文 key。

## 输入

- P10 provider registry。
- `.env` / 环境变量配置。
- P1 source registry。
- P3/P7 阈值配置。
- P4 LLM provider 配置。
- Path Resolver。

## 输出

- Settings DTO。
- FastAPI 路由。
- provider 测试结果 schema。
- 数据源配置 schema。
- 集成测试与 mock 响应。

## 验收标准

- 前端可读取 Settings Center 全量配置状态。
- 保存 FRED key 后，live FRED 采集可读取新配置。
- LLM Provider key 可保存并被 P4 模型路由读取。
- 数据源刷新频率与启用状态可被调度器读取。
- 所有响应均不泄露完整密钥。
- 操作失败时返回明确错误码和用户可读错误。

## 依赖任务

P10-C01、P10-C02、P10-C03、P10-C04、P10-C05、P10-C06、P9-C11

## 备注

Settings API 不直接承担业务推理，只管理配置状态、连通性测试与审计。
