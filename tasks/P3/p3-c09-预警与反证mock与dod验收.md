# P3-C09 预警与反证 Mock 与 DoD 验收

## 状态

DONE

## 实现结果

已新增 P3 全链路入口：

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli p3-run
```

`p3-run` 串联：

1. P3-C01 历史特征。
2. P2 雷达分析。
3. P3-C02 异常检测。
4. P3-C03 背离检测。
5. P3-C04 模块级反证。
6. P3-C05 总控级反证。
7. P3-C08 事件窗口。
8. P3-C06/C07 预警生成与生命周期。

## SQLite 验收

已验证写入：

- `feature_values`
- `radar_outputs`
- `module_json_outputs`
- `invalidation_conditions`
- `invalidation_events`
- `algorithm_alerts`
- `alert_events`

## 测试覆盖

新增：

```text
backend/tests/test_p3_pipeline.py
```

覆盖场景：

- funding/OI 异常。
- 资金流与价格背离。
- CPI T-1 事件窗口。
- 模块级/总控级反证写入。
- alert 创建、冷却、复用、升级/降级事件。

## Phase Gate

验收通过：

- P3 专项测试：4 passed。
- 后端全量测试：51 passed。
- Ruff：All checks passed。

P3 可以进入 P4。
