# P11-C01 / Source Health recent_failed 当前 run 与历史窗口口径分离

## 状态：DONE

## 背景

Data Quality / Source Health 里的 `recent_failed_run_count` 容易被理解成“本轮采集失败数”。实际它混有当前 run 的失败、当前 run 的 warning，以及历史窗口里的失败记录。

## 目标

拆分 Source Health 展示口径：

- 当前 run failure
- 当前 run warning
- 历史窗口 failure
- legacy `recent_failed_run_count` 继续保留，但不再作为“本轮失败数”解释

## 已完成

- `p45.data_quality.v1` 新增：
  - `source_health.current_run_id`
  - `source_health.current_run_source_count`
  - `source_health.current_run_failed_count`
  - `source_health.current_run_warning_count`
  - `source_health.history_recent_failed_count`
  - `source_health.current_run_failed_sources`
  - `source_health.current_run_warning_sources`
  - `source_health.history_recent_failed_sources`
  - `source_health.recent_failed_scope`
- 保留 legacy `recent_failed_sources` 字段形状，避免破坏旧调用方。
- warning 状态不再因为带 `error_message` 就被计为 failure。
- Data Quality UI 增加 current failures / current warnings / history failures 口径展示。

## DoD

- [x] Data Quality payload 区分当前 run failure、当前 run warning、历史窗口 failure。
- [x] 当前 run warning 不混同为 failure。
- [x] 历史失败只出现在 history/recent history 口径。
- [x] 页面不再把 `recent_failed_run_count` 解释成本轮失败数。
- [x] API / 前端测试通过。

## 验证

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
18 passed

npm run build
passed
```
