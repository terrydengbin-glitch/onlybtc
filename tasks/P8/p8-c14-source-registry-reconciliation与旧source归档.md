# P8-C14 Source Registry Reconciliation 与旧 source 归档

## 状态

DONE

## 来源

P1-C22 真实数据全链路验收发现：

```text
SQLite has obsolete sources not in SOURCE_CONFIGS: ['glassnode-mvrv']
```

当前 `glassnode-mvrv` 已不在 `SOURCE_CONFIGS`，但仍残留在 SQLite `sources` 表里，导致 data quality snapshot 出现：

```text
missing: 1
```

## 所属 Phase

P8 SQLite 持久化层 / P1 数据源注册表 / P5 Data Quality 页面

## 问题定义

`ensure_source_registry()` 当前会新增或更新当前 `SOURCE_CONFIGS` 中的 source，但不会处理已经从注册表删除的旧 source。

因此数据库会出现 registry drift：

```text
SOURCE_CONFIGS 中没有
SQLite sources 表中仍存在
```

风险：

- data quality 被旧 source 拉低。
- Data Quality 页面显示不存在的旧源。
- Source Detail 可能展示不可维护源。
- 后续审计会持续误报 missing。

## 目标

建立 source registry reconciliation 机制：

1. 识别 SQLite 中存在但当前 `SOURCE_CONFIGS` 不存在的 source。
2. 不直接删除历史数据，避免破坏审计与历史回放。
3. 将旧 source 标记为 archived / inactive / deprecated。
4. data quality snapshot 默认只统计 active source。
5. UI 可在 Source Detail / Data Quality 中查看 archived source，但不参与健康分。

## 推荐实现

### 数据库字段

优先复用 `sources.metadata_json`：

```yaml
metadata_json:
  archived: true
  archived_at: 2026-05-20T...
  archive_reason: not_in_source_configs
```

如果后续需要更强约束，可新增字段：

```text
sources.is_active
sources.archived_at
```

当前任务优先不做破坏性迁移，先用 metadata。

### Reconciliation 服务

新增函数：

```python
reconcile_source_registry(session)
```

行为：

- 当前注册表内 source：`archived=false`。
- 数据库中额外 source：设置 `metadata_json.archived=true`。
- source health 可追加一条 archived 事件。

### Data Quality

`write_data_quality_snapshot()` 默认只统计 active source。

payload 增加：

```yaml
archived_sources:
  - glassnode-mvrv
registry_drift_count: 1
```

### P1-C22 Audit

继续检测 registry drift，但如果 source 已 archived：

- 不计入 blocking failure。
- 在问题清单中标注为 archived_info 或 low impact。

## DoD

- `glassnode-mvrv` 不再影响 data quality 的 missing 统计。
- `sources` 表保留旧 source 历史，不物理删除。
- data quality payload 可看到 archived source 清单。
- P1-C22 复跑后：
  - `freshness.missing` 不再因为 `glassnode-mvrv` 增加。
  - 问题清单不再把它作为 medium 风险。
- 测试覆盖：
  - registry 中删除的 source 会被 archived。
  - archived source 不参与 data quality score。
  - active source 仍正常统计。

## 验收命令

```powershell
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode mock --source-id binance-btcusdt
..\.venv\Scripts\python.exe -m onlybtc.cli sources-health
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
```

## 本次执行结果

已完成：

- 新增 `reconcile_source_registry()`。
- `ensure_source_registry()` 会自动归档不在 `SOURCE_CONFIGS` 中的旧 source。
- 旧 source 不物理删除，写入：

```yaml
metadata_json:
  archived: true
  archived_at: ...
  archive_reason: not_in_source_configs
status: archived
```

- `write_data_quality_snapshot()` 默认排除 archived source。
- data quality payload 增加：
  - `archived_sources`
  - `registry_drift_count`
- P1-C22 audit 不再把 archived source 作为 registry drift 问题。

本次处理结果：

- `glassnode-mvrv` 已被归档。
- data quality `missing` 不再被 `glassnode-mvrv` 污染。

验证：

```text
ruff: All checks passed
pytest: 42 passed
```
