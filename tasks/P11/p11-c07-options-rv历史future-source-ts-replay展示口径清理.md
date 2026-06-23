# P11-C07 / Options RV 历史 future source_ts replay 展示口径清理

## 状态

DONE

## 背景

Run once 审计发现历史 replay / evidence 中仍可见旧的 `options_rv` future `source_ts`：

```text
options_rv source_ts = 2026-05-25T23:59:59.999000
collected_at = 2026-05-25T11:04:13.983099
available = false
is_stale = true
freshness_status = expired
```

该指标已被标记为 unavailable/stale，当前不阻塞方向结论，但历史展示仍可能让用户误以为系统正在使用未来 K 线。

## 目标

统一处理 Options RV 历史 future `source_ts` 的 replay 展示口径，避免用户误解。

## 已完成

- API evidence projection 增加 legacy future `source_ts` 检测。
- 当 `metric_id=options_rv` 且 `source_ts > collected_at` 时：
  - 标记 `legacy_future_source_ts = true`
  - 标记 `freshness_display_status = legacy_stale_future_source_ts`
  - 增加 `freshness_display_note`
  - 强制展示层按 unavailable/stale 处理
- 前端 Evidence 详情与 freshness 行展示 legacy note。

## DoD

- 历史 replay 不再把旧 future `source_ts` 展示成可用当前数据。
- 若保留旧记录，UI/API 必须明确标注 legacy stale / expired。
- 新 run 不再产生 `source_ts > collected_at` 的 `options_rv`。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
npm run build
```
