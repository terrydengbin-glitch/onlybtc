# P9-C24 / BTC Total State v2 API 透传与契约

## 状态
DONE

## 背景

P3-C41 与 P4.5-C26 会产生 `btc_total_state v2` 分层结构。P5 前端需要通过 Radar Module Detail / Dashboard API 获取这些字段，不能只拿到平铺的 module_score 与 top_contributors。

## 目标

API 透传 `btc_total_state v2`：

```text
price_state
perp_state
cycle_context
audit_context
btc_short_term_state
direction_driver_scope
context_only_scope
context_notes
audit_notes
```

## 契约要求

- `/api/p45/radar-modules/btc_total_state` 返回完整 v2 字段。
- Dashboard API 可消费 `btc_short_term_state` 和 summary。
- v1 历史数据缺字段时返回 null / fallback，不报错。
- 不把 Halving / Block Height 作为 direction drivers 返回。

## DoD

- API detail contract tests 覆盖 v2 字段。
- API 对 v1/v2 历史 run 兼容。
- Frontend 不需要解析 P3 内部原始 payload 才能展示四区块。
- P9 tests 通过。

## 执行记录

- `backend/src/onlybtc/api/p45_dashboard.py` 为 `btc_total_state` 增加 `btc_total_state_v2` 归一化投影。
- API detail/dashboard 顶层透传 `price_state / perp_state / cycle_context / audit_context / btc_short_term_state / context_notes / audit_notes`。
- `support_drivers / pressure_drivers` 过滤 `btc_halving_estimated_days / btc_halving_blocks_remaining / btc_block_height`。
- v1 历史 payload 缺少 v2 字段时，`btc_total_state_v2` 保持键存在并返回 `None`，避免前端直接解析 P3 原始 payload。

## 测试记录

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
16 passed

.\.venv\Scripts\python.exe -m pytest backend\tests\test_api.py backend\tests\test_p45_dashboard_api.py -q
20 passed
```
