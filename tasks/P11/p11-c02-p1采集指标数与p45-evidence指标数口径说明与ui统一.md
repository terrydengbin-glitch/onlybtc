# P11-C02 / P1 采集指标数与 P4.5 Evidence 指标数口径说明与 UI 统一

## 状态：DONE

## 背景

P1 采集指标数与 P4.5 Evidence 指标数可能不同。原因通常是派生指标、评分 evidence、不可用边界指标、复合语义指标的统计口径不同，不代表采集丢失或 evidence 重复。

## 目标

让 Dashboard / Data Quality 明确展示两个口径：

- P1 collected metrics
- P4.5 scored evidence

并提供机器可读的 count audit 解释。

## 已完成

- `p45.data_quality.v1` 新增顶层 `metric_count_audit`。
- `data_quality.metric_count_audit` 同步包含相同内容，便于前端兼容读取。
- 字段包括：
  - `collected_metric_count`
  - `scored_evidence_count`
  - `derived_metric_count`
  - `unavailable_metric_count`
  - `count_explanation`
- Data Quality UI 增加 collected metrics / scored evidence / derived metrics / unavailable 的明确标签。

## DoD

- [x] P1 页面/质检页明确显示采集指标数口径。
- [x] P4.5 / Data Quality 明确显示 scored Evidence 指标数口径。
- [x] 数量不同时显示为口径差异，不产生 error。
- [x] API payload 有机器可读 `metric_count_audit`。
- [x] Dashboard 不再把两个口径混成一个“指标数量”。

## 验证

```text
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
18 passed

npm run build
passed
```
