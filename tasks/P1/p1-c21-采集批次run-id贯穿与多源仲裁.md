# P1-C21 采集批次 run_id 贯穿与多源仲裁

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座 / P8 SQLite 事件库 / P2 雷达消费

## 任务定位

补齐数据采集链路中的两个关键能力：

1. `run_id` 贯穿：同一轮采集产生的 `source_runs`、`raw_observations`、`metric_values`、`data_quality_snapshots` 必须能串起来。
2. 多源仲裁：同一个 `metric_id` 由多个 source 提供时，Radar 默认消费仲裁后的 selected source，不能把不同 source 混成一条趋势。

## 已完成实现

- `collect_sources()` 每轮生成 `collect-YYYYMMDDHHMMSS-xxxxxx` 格式的采集批次 ID。
- `source_runs.run_id`、`raw_observations.run_id`、`metric_values.run_id`、`data_quality_snapshots.run_id` 写入同一批次 ID。
- `persist_collection_result()` 支持外部传入 `run_id`，兼容直接写入测试。
- `historical_window(metric_id)` 默认按 source 分组，逐源构建窗口，再按规则仲裁。
- `historical_window(metric_id, source_id=...)` 仍返回指定 source 的单源窗口。
- `HistoricalWindow` 增加：
  - `selected_reason`
  - `candidates`
  - `conflict`
- Radar 默认消费 selected source，并把多源冲突写入 `conflicting_evidence.source_conflicts`。
- Lightning capacity 源优先级已显式设置：
  - `mempool-lightning-network-stats`: `priority=30`
  - `clarkmoody-dashboard`: `priority=40`

## 仲裁规则

优先级从高到低：

1. `freshness_status`: `fresh > stale > expired > missing`
2. `source.priority`: 数字越小优先级越高
3. `effective_quality_score`: 越高越优先
4. `age_seconds`: 越新越优先

## 冲突检测

同一指标多个 fresh/stale source 与 selected source 的相对差异超过阈值时，写入 conflict：

- `low`: `relative_diff > 2%`
- `medium`: `relative_diff > 5%`
- `high`: `relative_diff > 10%`

输出结构示例：

```yaml
conflict:
  detected: true
  items:
    - metric_id: lightning_capacity_btc
      primary_source: mempool-lightning-network-stats
      conflicting_source: clarkmoody-dashboard
      relative_diff: 0.031
      severity: low
```

## 验收结果

已通过：

```powershell
..\.venv\Scripts\python.exe -m ruff check src tests
..\.venv\Scripts\python.exe -m pytest
```

全量结果：

```text
ruff: All checks passed
pytest: 37 passed
```

## 手工验收

已执行：

```powershell
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode mock --source-id mempool-lightning-network-stats --source-id clarkmoody-dashboard
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window lightning_capacity_btc
..\.venv\Scripts\python.exe -m onlybtc.cli analyze-radars --module-id btc_adoption
```

验收观察：

- `collect-sources` 返回 `run_id`，且 `data_quality.run_id` 与采集批次一致。
- `metric-window lightning_capacity_btc` 返回 selected source、candidates、conflict。
- `analyze-radars --module-id btc_adoption` 可正常消费仲裁后的指标窗口。

## 后续影响

Evidence、Radar Detail、History Replay、Run Logs 可以按 `run_id` 精确追踪：

- 这次判断用了哪一轮采集。
- 每个 source 的 raw observation 是什么。
- 每个 metric 来自哪个 source。
- 为什么选择这个 source。
- 多源之间是否存在冲突。
