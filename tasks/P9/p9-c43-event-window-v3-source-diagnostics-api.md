# P9-C43 / Event Window v3 Source Diagnostics API

## 状态

TODO

## Phase

P9 FastAPI、dashboard 与契约透传

## 背景

当前 `/api/event-window/latest` 能返回业务 payload，但用户无法直接判断每个 source 是 live、fallback、failed 还是 placeholder。

## 目标

新增 source diagnostics API，让 UI 和审计能明确回答：

```text
有没有真正拉到官方数据？
哪个源失败了？
为什么 fallback？
上次成功是什么时候？
下一次采集是什么时候？
```

## API

```text
GET /api/event-window/sources/status
GET /api/event-window/sources/fetches?limit=100
GET /api/event-window/sources/{source_id}
```

## 输出契约

```json
{
  "schema_version": "p45.event_window.source_diagnostics.v1",
  "summary": {
    "live_source_count": 0,
    "partial_source_count": 0,
    "fallback_source_count": 0,
    "failed_source_count": 0,
    "overall_source_mode": "live|partial|fallback|failed"
  },
  "sources": [
    {
      "source_id": "",
      "source_tier": "official|expectation|market|fallback",
      "status": "success|partial|failed|fallback_used|skipped",
      "last_success_at": "",
      "last_attempt_at": "",
      "last_error": "",
      "parsed_item_count": 0,
      "fallback_used": false
    }
  ]
}
```

## DoD

- [ ] 子页面能用该 API 显示 live/fallback/failed。
- [ ] latest payload 可带 summary，但详细 fetch history 走独立 API。
- [ ] fallback-only 时 UI 不再误显示 official live。
- [ ] API 测试覆盖空状态、live success、fallback、failed。

## 依赖

- P8-C35
- P1-C57
- P1-C58
- P1-C59
