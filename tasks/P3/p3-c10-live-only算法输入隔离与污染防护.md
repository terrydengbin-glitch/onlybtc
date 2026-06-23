# P3-C10 live-only 算法输入隔离与污染防护

## 状态

DONE

## 执行记录

- P3 pipeline、特征、异常、背离、反证、事件窗口、预警均已支持 `run_mode` 参数，默认 `live`。
- P3 调用雷达层时已传入 `run_mode=live`，默认不消费 mock/test 历史窗口。
- P3 输出的 feature / invalidation / alert payload 已补充 `run_mode` 与 `non_production`。
- 已增加 live/mock 混合样本回归测试，确认 P3 live-only 不被 mock 历史污染。
- 本轮真实 P3 运行通过：`run_mode=live`，14 个雷达模块完成分析；因 live 历史样本仍少，异常/背离阶段多数为 `not_enough_samples`，这是采集历史长度问题，不是链路断点。

## 所属 Phase

P3 算法敏感检测与预警系统

## 上游依赖

- P8-C16：`historical_window()` 支持 run_mode 过滤，默认 live。
- P1-C30：采集数据已写入 run_mode，P1-C22 能显示混用风险。

## 问题背景

P3 真实运行已经打通，但在历史库混入 mock/test 样本时会出现误报：

```text
mock btc_price = 108420.5
live btc_price = 77676.22
P3 误判 BTC 暴跌 28%+
```

这不是 P3 算法公式问题，而是输入窗口污染。P3 必须默认只消费 live 样本，并在发现混用风险时阻止 critical 级别输出。

## 任务目标

确保 P3 的：

- 特征计算
- 异常检测
- 背离检测
- 模块反证
- 总控反证
- 预警分级

默认全部只消费 live 数据。

## 需要修改

### 1. P3 pipeline 参数

扩展：

```python
run_p3_pipeline(run_mode: str = "live")
detect_anomalies(run_mode: str = "live")
detect_divergences(run_mode: str = "live")
```

CLI：

```powershell
..\.venv\Scripts\python.exe -m onlybtc.cli p3-run --run-mode live
..\.venv\Scripts\python.exe -m onlybtc.cli p3-run --run-mode all
```

要求：

- 默认 `live`。
- `all` 只允许用于测试/回放，并在输出中标记 `non_production=true`。

### 2. critical 防护

如果 P1-C22 / run-mode audit 发现：

```yaml
mixed_metric_ids_count > 0
unknown_metric_values > 0
```

则：

- P3 仍可生成 info/watch/warning。
- critical 必须降级为 warning。
- alert metadata 写入：

```yaml
critical_blocked_by:
  - run_mode_mixed_history
```

### 3. P3 输出可追溯 run_mode

所有 P3 写入的 `feature_values.metadata_json`、`invalidation_events.payload`、`algorithm_alerts` 对应 `alert_events.payload` 必须包含：

```yaml
run_mode: live
non_production: false
```

### 4. 回归测试

构造同一 metric 下：

```text
mock 高价样本
live 真实样本
```

验证：

- live-only 窗口不被 mock 污染。
- P3 异常数量不会因 mock 值暴增。
- `run_mode=all` 可以读取混合样本，但输出 `non_production=true`。

## DoD

- P3 默认只消费 live。
- P3 输出全部带 run_mode。
- mock/test 混入不会触发真实 critical。
- P3-C09 Mock 验收仍能显式用 mock/test 跑。
- 真实 `p3-run` 后 BTC price 不再出现 mock 污染导致的大幅假波动。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli db-run-mode-audit
..\.venv\Scripts\python.exe -m onlybtc.cli p3-run --run-mode live
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
```

## 追加链路检查记录

- 本次 P3 全链条复查发现 `check_module_invalidations()` 原先读取最新任意 `module_json_outputs`，而不是当前 P3 `run_id` 对应的 Radar 输出；连续或并发运行时可能误读上一轮模块证据。
- 已修复为按当前 `run_id` 读取 `module_json_outputs`。
- 已新增 same-run 回归测试，构造 stale radar run 后再执行 P3，确认 module invalidation 使用当前 P3 run 的 Radar JSON。
