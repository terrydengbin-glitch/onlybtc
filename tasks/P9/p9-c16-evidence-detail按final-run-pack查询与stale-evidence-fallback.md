# P9-C16 Evidence Detail 按 final_run_id/pack_id 查询与 stale evidence fallback

## 状态

DONE

## Phase

P9 FastAPI 聚合 API 与运维质控

## 背景

当前 `GET /api/p45/evidence/{evidence_id}` 只在 latest P4.5 final 的 `metric_evidence` 中查找 evidence。由于 P3 evidence_id 每轮都会变化，页面刷新或历史链接中保留旧 `evidence_id` 时，后端会返回 404。

前端已有基于 `module_id + metric_id` 的 fallback，但该 fallback 依赖 latest evidence 已加载完成。刷新期间多个 endpoint 并发加载，顺序不稳定，仍可能暴露 404 API error。

## 根因

```text
URL 保留旧 evidence_id
  -> 刷新页面恢复 route context
  -> 调 GET /api/p45/evidence/{old_id}
  -> 后端只查 latest final
  -> latest final 已变成新 run
  -> old_id 不存在
  -> 404
```

## 目标

- Evidence detail 支持按 `final_run_id` 或 `pack_id` 查询历史快照。
- stale evidence_id 不再直接 404，可解析 module/metric 并返回最新等价 evidence。
- 响应中明确标记是否发生 stale fallback。
- 前端可根据响应更新 route context，避免重复请求旧 evidence_id。

## API 契约

### 请求

```text
GET /api/p45/evidence/{evidence_id}
GET /api/p45/evidence/{evidence_id}?final_run_id=p45final-...
GET /api/p45/evidence/{evidence_id}?pack_id=p45pack-...
GET /api/p45/evidence/{evidence_id}?allow_stale_fallback=true
```

### 响应

```json
{
  "schema_version": "p45.evidence_detail.v2",
  "run_lineage": {},
  "evidence": {},
  "resolution": {
    "status": "exact",
    "requested_evidence_id": "p3-score-...",
    "resolved_evidence_id": "p3-score-...",
    "resolved_by": "latest_exact",
    "stale": false,
    "warning": null
  }
}
```

`resolution.status` 枚举：

```text
exact
historical_exact
stale_metric_fallback
not_found
```

## fallback 策略

1. 若传入 `final_run_id`，优先查该 final 的 evidence。
2. 若传入 `pack_id`，查该 pack 的 evidence。
3. 若未传 run scope，查 latest completed final。
4. 若 exact 未命中且 `allow_stale_fallback=true`：
   - 从 evidence_id 或旧结构解析 `module_id/metric_id`。
   - 在 latest completed evidence 中找同 module + metric。
   - 返回 `resolution.status=stale_metric_fallback`。
5. 若仍未命中，返回 404，但错误体包含 `requested_evidence_id` 与可读原因。

## DoD

- 旧 evidence_id 在 latest run 变化后不会直接刷屏 404。
- 带 `final_run_id` 的历史 evidence link 能稳定打开历史详情。
- stale fallback 响应包含 requested/resolved evidence id。
- 前端可用 `resolved_evidence_id` 替换 URL 中的旧 evidence_id。
- FastAPI 测试覆盖 latest exact、historical exact、stale fallback、not found。

## 关联任务

P5-C37, P5-C36, P9-C03, P9-C09, P9-C15

## 执行记录

- `GET /api/p45/evidence/{evidence_id}` 增加：
  - `final_run_id`
  - `pack_id`
  - `allow_stale_fallback`
- Evidence detail 返回 `schema_version=p45.evidence_detail.v2` 和 `resolution`。
- exact 命中时返回 `exact/historical_exact`。
- stale id 未命中时，可按 `module_id + metric_id` 在 latest completed run 中解析为 `stale_metric_fallback`。
- `_latest_payload()` 增加 `id desc` 排序，避免同时间戳插入时 latest 不稳定。

## 验证结果

```text
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py -q
passed
```
