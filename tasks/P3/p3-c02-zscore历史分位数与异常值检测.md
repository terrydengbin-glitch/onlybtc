# P3-C02 Z-score、历史分位数与异常值检测

## 状态

DONE

## 实现结果

已在 `backend/src/onlybtc/algorithms/p3.py` 实现 `detect_anomalies()`。

算法只读取 P1/P8 的 `metric_values` 与 `historical_window()`，不直接访问 provider。每个异常候选写入：

```yaml
table: feature_values
module_id: p3_anomaly_engine
feature_id: "{metric_id}.anomaly"
metadata:
  metric_id
  source_id
  source_run_id
  anomaly_type
  severity
  zscore
  percentile
  velocity
  freshness_status
  quality_score
  source_conflict_present
  evidence
```

## 覆盖类型

- `zscore_spike`
- `percentile_extreme`
- `velocity_shock`
- `freshness_anomaly`

## 质量规则

- 低质量数据最高只生成 `info/watch`。
- 多源冲突存在时最高先进入 `watch`。
- 异常只是候选证据，不直接等于 alert，交给 P3-C06 汇总分级。

## 验收

- P3 专项测试通过。
- 后端全量测试通过：51 passed。
- Ruff 通过。

