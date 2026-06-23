# P9-C21 / Data Quality recent_failed 统计口径修复

## 状态

DONE

## 背景

最新一轮审计中，`/api/data-quality/latest` 返回：

```json
{
  "source_count": 67,
  "status_counts": {
    "healthy": 66,
    "archived": 1
  },
  "recent_run_count": 200,
  "recent_failed_run_count": 200
}
```

但 `recent_failed_sources` 里的条目实际显示：

```json
{
  "status": "healthy",
  "error_message": null
}
```

这说明 `recent_failed_run_count` / `recent_failed_sources` 的统计口径不正确：它很可能统计了 recent runs 总数，或者没有按失败状态过滤，导致 Data Quality 页面误报大量失败。

## 目标

1. 修复 Data Quality API 的 recent failed 统计。
2. `recent_failed_run_count` 只统计真正失败、降级失败或 error 不为空的 source run。
3. `recent_failed_sources` 只返回失败条目，不返回 healthy 条目。
4. 保留 `recent_run_count` 作为总样本数。
5. 前端 Data Quality 页面不再误报“200 个失败”。

## 不改范围

- 不修改 P1 采集逻辑。
- 不修改 source health 表结构，除非现有字段无法表达失败状态。
- 不修改 P8 SQLite schema。
- 不影响 History Replay 的历史 run 展示。

## 统计规则

### recent_run_count

```text
recent_run_count = 最近 N 条 source run 总数
```

### recent_failed_run_count

```text
recent_failed_run_count =
  count(source_run where
    status in ["failed", "error", "degraded", "unhealthy"]
    or error_message is not null
  )
```

### recent_failed_sources

```text
recent_failed_sources =
  recent source runs filtered by the same failure predicate
```

禁止把以下状态计入 failed：

```text
healthy
archived
selected
fallback_selected
data_boundary
```

## API 契约

`/api/data-quality/latest` 返回：

```json
{
  "source_health": {
    "recent_run_count": 200,
    "recent_failed_run_count": 0,
    "recent_failed_sources": []
  }
}
```

如果确实有失败：

```json
{
  "recent_failed_sources": [
    {
      "source_id": "xxx",
      "run_id": "collect-xxx",
      "mode": "live",
      "status": "failed",
      "error_message": "..."
    }
  ]
}
```

## DoD

- [ ] latest run 中 healthy source 不再进入 `recent_failed_sources`。
- [ ] `recent_failed_run_count` 与 `recent_failed_sources.length` 口径一致。
- [ ] `status_counts.healthy = 66` 时，不得同时显示 200 个 failed。
- [ ] Data Quality 页面不再误报失败数量。
- [ ] 增加 API 回归测试：healthy 条目不计 failed，failed/error 条目计 failed。
- [ ] 不影响 `source_count / status_counts / data_quality.contract_validation` 现有字段。

## 关联

P9-C06, P8-C09, P5-C14

## Completion Note

- Done: `/api/data-quality/latest` 的 `recent_failed_run_count` 只统计 failed/error/degraded/unhealthy 或存在 error_message 的 source run。
- Done: `recent_failed_sources` 不再包含 healthy source run。
- Verified: P9 dashboard API、source health 回归测试通过。
