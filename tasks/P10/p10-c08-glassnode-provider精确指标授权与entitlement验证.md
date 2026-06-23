# P10-C08 Glassnode Provider 精确指标授权与 Entitlement 验证

## 状态

DONE

## 执行记录（2026-06-23）

- 新增 `backend/src/onlybtc/core/glassnode_entitlement.py`，提供 Glassnode entitlement audit runner。
- 新增 `scripts/generate_glassnode_entitlement_report.py`，输出：
  - `reports/glassnode-provider-entitlement-report.json`
  - `reports/glassnode-provider-entitlement-report.md`
- 新增 API：
  - `GET /api/settings/providers/glassnode/entitlement/latest`
  - `POST /api/settings/providers/glassnode/entitlement/audit?mode=dry_run|mock`
- 新增测试 `backend/tests/test_glassnode_entitlement.py`，覆盖 missing key、available、unauthorized、rate_limited、not_found、schema_changed、报告写入与脱敏。
- 当前本机未配置 `ONLYBTC_GLASSNODE_API_KEY`，dry-run report 正确输出 `overall_status=provider_locked`、`available_count=0`、`locked_count=7`，未写生产 metric。
- 已重启后端 `8118`，当前监听进程为 onlyBTC uvicorn，PID 18744。

## 所属 Phase

P10 API Key 配置与密钥管理

## 前置任务

P1-C14、P1-C15、P1-C17、P7-C07、P10-C01、P10-C04、P10-C06。

## Summary

P1-C14 的公开 Glassnode 页面采集已经完成；剩余问题不是免费源补齐，而是 Glassnode API key、登录态和订阅权限能否稳定提供精确链上指标。本任务专门验证 entitlement，不允许用 403/429、空值或页面文案伪造生产指标。

## Scope

- 验证 `ONLYBTC_GLASSNODE_API_KEY` 是否可通过 Settings / Provider Registry 配置、脱敏展示和 health probe。
- 建立 Glassnode entitlement audit runner，按指标逐项记录 `available`、`unauthorized`、`rate_limited`、`not_found`、`schema_changed`。
- 覆盖 P1-C14 剩余高价值指标：`realized_price` 变体、`sth_cost_basis`、`lth_cost_basis`、`whale_flow`、`miner_flow`、`stablecoin_exchange_inflow`、精确 `exchange_netflow`。
- 区分 API key 模式与 manual-login Playwright session 模式。
- 输出审计报告到 `reports/glassnode-provider-entitlement-report.json/md`。

## Out Of Scope

- 不购买、绕过或共享 Glassnode 账号。
- 不保存用户密码，不把 session cookie 写入 git 追踪路径。
- 不把 provider-locked 指标写成默认值、估算值或 LLM 推断值。
- 不替换 P1-C15/P1-C17 已经完成的免费/半自动替代源，除非 entitlement audit 明确证明 Glassnode 精确源可稳定使用。

## Business Chain / Contract

- Upstream：Settings `.env`、Provider Registry、Provider Health、manual-login session metadata。
- Source Layer：Glassnode API 或经过用户本地验证态的 Playwright session。
- SQLite / Metrics：只有 `available` 且 schema/recency/quality 通过的指标才允许进入生产 metric。
- API：Provider Health 与 Data Quality 必须展示 locked/unauthorized/rate-limited，不返回明文 key 或 token。
- Downstream：P2 radar、P4.5 final decision、P6 replay 只能消费带 source lineage 和 quality flag 的指标。

关键字段：

```text
provider_id
auth_method
metric_id
endpoint
entitlement_status
http_status
business_ts
collected_at
quality
source_id
locked_reason
```

## Implementation Plan

1. DONE：读取 P10 provider registry / health 现状，确认 Glassnode key 配置和测试入口。
2. DONE：新增 entitlement audit runner，支持 mock fixture 与真实 dry-run。
3. DONE：为每个目标指标定义 endpoint、期望字段、freshness policy、生产写入开关。
4. DONE：报告 unauthorized / rate_limited / schema_changed，不抛 500，不写假 metric。
5. DONE：增加单元测试覆盖 key missing、unauthorized、available、schema_changed、redaction。
6. DONE：默认只做审计和报告；真实 key 可用后仍需单独 review production write candidates。

## DoD

- [x] `glassnode` provider 在 Settings / Provider Health 中可配置、可测试、可脱敏。
- [x] entitlement runner 输出 JSON 与 MD 报告。
- [x] 缺 key、401/403、429、schema change 不会中断主系统。
- [x] 不泄露 API key、cookie、Authorization header。
- [x] 只有明确可用的指标才进入生产写入候选清单。
- [x] P1-C14 剩余登录/订阅权限问题不再阻塞 P1/P2/P4.5/P6 主线。

## Test Plan

- `.venv\Scripts\python.exe -m pytest backend/tests/test_glassnode_entitlement.py backend/tests/test_provider_health.py backend/tests/test_provider_registry.py backend/tests/test_p7_provider_permissions.py -q` -> 19 passed。
- `.venv\Scripts\python.exe -m compileall backend/src/onlybtc/core/glassnode_entitlement.py backend/src/onlybtc/api/app.py scripts/generate_glassnode_entitlement_report.py` -> passed。
- `GET /api/health` -> healthy。
- `GET /api/settings/providers/glassnode/entitlement/latest` -> `schema_version=p10.c08.glassnode_entitlement.v1`。
- `POST /api/settings/providers/glassnode/entitlement/audit?mode=mock` -> `available_count=1`、`locked_count=6`。
- `POST /api/settings/providers/glassnode/entitlement/audit?mode=dry_run` -> `overall_status=provider_locked`、`available_count=0`、`locked_count=7`。

## Rollback / Risk Notes

- 默认审计模式不写生产 metric，回滚只需移除 runner / report endpoint。
- 最大风险是把 provider locked 误判为可用；测试必须覆盖 401/403/429 与空 payload。
- manual-login session 只能引用本地 profile metadata，不能输出 cookie 或浏览器存储内容。
