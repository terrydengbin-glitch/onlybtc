# P9-C58 Settings API Supersession Reconciliation

## 状态

DONE

## 所属 Phase

P9 FastAPI 聚合 API 与运维质控

## Summary

对齐 `P9-C14 Settings 配置聚合 API` 与 P10 配置治理已完成能力，避免后续 P9 主线重复实现 API Key、Provider Registry、LLM Routing、Provider Health 与密钥审计链路。

## Scope

- 盘点 `P9-C14` 原始 Settings 聚合 API 范围。
- 对齐 P10-C01 至 P10-C07 已完成的配置治理能力。
- 将 `P9-C14` 收窄为剩余 Settings 子域，不再覆盖 P10 已完成能力。
- 保留尚未完成的 data source refresh policy、runtime policy、paths/storage 等配置子域为后续任务范围。

## Business Chain / Contract

P10 已完成并验收：

- `GET /api/settings`：返回 provider registry、masked provider status、provider health、LLM routing、settings audit。
- `POST /api/settings/env`：安全写入 `.env`，保留未知行，写入后 reload settings。
- `POST /api/settings/reload`：刷新 Settings cache。
- `GET /api/settings/providers/health`：读取 provider health。
- `POST /api/settings/providers/{provider_id}/test`：单 provider 连通性测试。
- `POST /api/settings/providers/health/test-all`：批量连通性测试。
- `GET /api/settings/llm-routing`：读取 LLM route readiness。
- `GET /api/settings/audit`：读取脱敏设置操作审计。

这些能力已由 P10-C07 DoD 报告覆盖，不再作为 `P9-C14` 待实现范围。

## Remaining P9-C14 Scope

`P9-C14` 后续若继续推进，只处理 P10 未覆盖的 Settings 子域：

- 数据源刷新频率、启用状态、fallback 策略配置。
- runtime / scheduler / Run Once / 发布策略配置。
- paths / storage / maintenance 配置展示。
- 对上述子域补充 DTO、错误响应、权限审计与前端消费契约。

## DoD

- [x] 新增本对账任务卡。
- [x] `task index.md` 增加 `P9-C58`。
- [x] `P9-C14` 状态说明从通用 TODO 收窄为 P10 已覆盖 + P9 剩余范围。
- [x] 不修改运行时代码，不改变现有 API 行为。

## Test Plan

文档/任务卡对账，无运行时代码变更：

- 检查 `task index.md` 链接存在。
- 检查 `P9-C14` 与 `P10-C07` 任务卡引用一致。

## Risks / Notes

- 不将 `P9-C14` 整体标记 DONE，因为原始范围包含 P10 未覆盖的 data source / runtime / paths 配置子域。
- 后续进入 `P9-C01` 时，应把 P10 Settings API 作为既有契约输入，而不是重新设计密钥管理链路。
