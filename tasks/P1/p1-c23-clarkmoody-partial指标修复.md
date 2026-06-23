# P1-C23 Clark Moody partial 指标修复

## 状态

DONE

## 来源

P1-C22 真实数据全链路验收发现：

```text
collect_run_id: collect-20260520115005-17fe5e
source_id: clarkmoody-dashboard
```

本轮 live 采集未产出 3 个低优先级指标，但历史库存在旧值，因此被标记为 `partial`：

- `lightning_tor_capacity_pct`
- `bitcoin_tor_nodes_pct`
- `fees_vs_reward_pct`

## 所属 Phase

P1 数据源与历史数据底座 / P8 SQLite / P2 BTC 采用率与交易结构辅助指标

## 问题定义

Clark Moody 页面可以访问，主采集源本轮成功，且大多数指标成功写入；问题集中在 parser 对百分比字段的提取稳定性。

当前风险：

- 历史旧值会让 UI 看起来有数据，但本轮真实采集没有产出。
- P1-C22 已能识别 `partial`，但源头 parser 仍需修复。
- 这 3 个指标当前不进入核心雷达判断，影响较低，但会影响数据质量说明与 Source Detail。

## 修复目标

1. 修复 `_parse_clarkmoody_dashboard` 对以下字段的真实页面解析：
   - `lightning_tor_capacity_pct`
   - `bitcoin_tor_nodes_pct`
   - `fees_vs_reward_pct`
2. 增加 parser 单元测试，覆盖 Clark Moody 真实页面常见文本结构。
3. live 采集本轮必须写入这 3 个 metric。
4. P1-C22 复跑后，这 3 个指标的 `sqlite_status` 必须从 `partial` 变为 `stored`。

## 实现要求

### Parser

优先增强文本解析规则，不引入 OCR。

需要兼容：

- `Percentage Tor Capacity`
- `Percentage Tor Nodes`
- `Avg. Fees vs. Reward`
- 页面中百分号前后换行、空格、逗号、小数的情况。

### 数据质量

成功解析后，沿用 Clark Moody 当前质量分：

```yaml
source_id: clarkmoody-dashboard
quality_score: 0.84
refresh_minutes: 10
```

如果字段解析不到：

- 不应写入旧值。
- 应在 source raw payload 或 parser missing 字段中留下可审计信息。

## DoD

- `clarkmoody-dashboard` live 采集可写入 3 个缺失指标。
- `metric_values.run_id` 等于本轮 collect run_id。
- `metric-window lightning_tor_capacity_pct` 可返回 fresh/stored 数据。
- P1-C22 复跑后失败清单不再包含这 3 个指标。
- 测试通过：

```powershell
..\.venv\Scripts\python.exe -m ruff check src tests
..\.venv\Scripts\python.exe -m pytest
```

## 验收命令

```powershell
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id clarkmoody-dashboard
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window lightning_tor_capacity_pct
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window bitcoin_tor_nodes_pct
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window fees_vs_reward_pct
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit
```

## 本次执行结果

已完成：

- 增强 Clark Moody parser 的百分比字段解析。
- 修复 `%` 无法被 `_parse_clarkmoody_value()` 正确清理的问题。
- 增加 compact percentage rows 测试。
- live 单源采集验证通过。

本轮已成功写入：

- `lightning_tor_capacity_pct`
- `bitcoin_tor_nodes_pct`
- `fees_vs_reward_pct`

P1-C22 复跑结果：

```text
failed_count: 0
sqlite_status: stored 101
```

验证：

```text
ruff: All checks passed
pytest: 42 passed
```
