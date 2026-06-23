# P8-C18 / BTC Total State v2 结构化 payload 持久化与回放兼容

## 状态
DONE

## 背景

P3-C41 会在 `btc_total_state` 中输出更深的结构化字段：

```text
price_state
perp_state
cycle_context
audit_context
btc_short_term_state
context_notes
audit_notes
```

SQLite 当前以 JSON payload 为主，原则上可兼容，但仍需要明确持久化、历史回放和查询层如何处理 v1/v2 profile。

## 目标

确保 `btc_total_state v2` 在 SQLite 中可追溯、可回放、可被 API 查询。

## 范围

- `module_json_outputs.payload`
- `feature_values.metadata_json`
- history replay / latest query repository
- v1/v2 profile 兼容读取

## DoD

- 新 v2 字段能完整写入并从 SQLite 读回。
- 历史 v1 run 不因缺少 v2 字段导致 API 或 UI 崩溃。
- History Replay 能展示 v2 profile，并对 v1 输出 fallback summary。
- 不需要新增表时，不做 schema migration；如确需 migration，必须补 Alembic 与测试。
- P8 / API repository 相关测试通过。

## 执行记录

- `module_json_outputs.payload` 与 `feature_values.metadata_json` 继续使用 JSON payload 承载 v2 结构，无需 schema migration。
- `backend/src/onlybtc/api/p45_dashboard.py` 的 history replay 增加投影后的 `radar_modules`，历史页可直接消费 `btc_total_state_v2`。
- v2 历史 final payload 可从 SQLite 原样读回 `btc_total_state_explanation` 与分层 module 字段。
- v1 历史 run 缺少 v2 字段时，history replay 仍返回兼容 `btc_total_state_v2` 壳，字段为 `None`。

## 测试记录

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py backend\tests\test_p45_evidence_pack.py -q
19 passed
```
