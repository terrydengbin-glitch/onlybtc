# P3-C06 预警等级 info/watch/warning/critical

## 状态

DONE

## 实现结果

已在 `backend/src/onlybtc/algorithms/p3.py` 实现 `generate_algorithm_alerts()`。

预警候选来自：

- P3-C02 anomaly
- P3-C03 divergence
- P3-C04/P3-C05 invalidation
- P3-C08 event window

输出写入：

```yaml
tables:
  - algorithm_alerts
  - alert_events
fields:
  alert_id
  run_id
  level
  state
  title
  summary
  evidence_count
  cooldown_until
```

## 分级约束

- 单点低质量数据不能触发 critical。
- warning 至少需要多个证据或反证支持。
- critical 需要多证据、总控反证或重大事件窗口。
- 事件窗口可单独生成提醒，但会带 `risk_lock` 说明。

## 验收

- 四级预警可持久化。
- 每条预警可以追溯 evidence refs。
- 可供 P5 Alerts 页面展示。

