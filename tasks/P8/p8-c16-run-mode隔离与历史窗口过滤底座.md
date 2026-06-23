# P8-C16 run_mode 隔离与历史窗口过滤底座

## 状态

DONE

## 执行记录

- 已为 `source_runs.mode`、`raw_observations.mode`、`metric_values.run_mode` 增加 SQLite/ORM 字段与兼容迁移。
- 已将 `metric_values` 唯一身份扩展为 `metric_id + ts + source_id + run_mode`，避免 live/mock/test 同时间戳互相冲突。
- 已将 `historical_window()` 默认改为 `run_mode="live"`，并支持 `run_mode="all"` 用于调试与回放。
- 已新增 `db-run-mode-audit` 与 `db-archive-non-live` 命令。
- 已补充测试覆盖 live/mock 混合历史窗口过滤。

## 所属 Phase

P8 SQLite 数据库与持久化层

## 问题背景

真实 P3 跑通后发现一个生产级风险：历史库中同时存在 `mock/test/live` 样本，`historical_window()` 在没有区分采集模式时会把 mock/test 样本混入真实窗口，导致 BTC 价格、异常检测、背离检测和预警等级被污染。

典型现象：

```text
btc_price 同一 source_id 下混入 108420.5 mock 值与 77676.22 live 值
P3 误判 change_24h = -28.36%
```

## 任务目标

在 SQLite 层建立 run mode 隔离能力，让后续 P1/P2/P3 默认只消费真实 `live` 数据，同时保留 mock/test 数据用于测试与回放。

## 需要修改

### 1. Schema / ORM

为采集链路补充 mode 追溯字段：

```yaml
source_runs:
  mode: live/mock/test

raw_observations:
  mode: live/mock/test

metric_values:
  run_mode: live/mock/test
```

兼容策略：

- 旧数据没有 mode 时标记为 `unknown`。
- 后续窗口查询默认只取 `run_mode = live`。
- mock/test 仍可通过显式参数读取。

### 2. 历史窗口过滤契约

扩展 `historical_window()`：

```python
historical_window(
    metric_id: str,
    source_id: str | None = None,
    limit: int = 90,
    run_mode: str = "live",
)
```

规则：

- 默认 `run_mode="live"`。
- `run_mode="all"` 仅用于调试、测试、History Replay。
- P2/P3 不允许隐式读取 all。

### 3. 归档 / 清理命令

新增 CLI：

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli db-archive-non-live
..\.venv\Scripts\python.exe -m onlybtc.cli db-run-mode-audit
```

用途：

- 识别 `unknown/mock/test` 样本。
- 给旧 mock 数据补标或归档。
- 输出受影响 metric/source/run_id。

### 4. 索引

为高频查询增加索引：

```sql
metric_values(metric_id, source_id, run_mode, ts)
source_runs(run_id, mode)
raw_observations(source_id, run_id, mode)
```

## DoD

- `metric_values` 可追溯采集 mode。
- `historical_window()` 默认只返回 live 样本。
- P2/P3 不改调用参数也不会消费 mock/test。
- 提供一次性归档/补标命令。
- 测试覆盖 live/mock 混合窗口，确认 live-only 不被污染。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli db-run-mode-audit
..\.venv\Scripts\python.exe -m onlybtc.cli p3-run
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check src tests
```
