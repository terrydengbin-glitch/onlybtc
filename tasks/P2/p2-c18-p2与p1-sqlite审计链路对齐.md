# P2-C18 P2 与 P1/SQLite/审计链路对齐

## 状态

DONE

## 所属 Phase

P2 全量雷达模块 / P1 数据源 / P8 SQLite / P1-C22 审计

## 任务目标

在 P1 新增真实数据源、run_id、多源仲裁、freshness policy、中文 HTML 审计之后，重新对齐 P2 雷达层，确保每个雷达都只消费 P1/P8 标准输出，并能被 P1-C22 审计验证。

## 统一业务链路

```text
P1 数据源采集
  -> raw_observations / metric_values
  -> historical_window(metric_id)
  -> P2 radar feature
  -> radar_outputs / feature_values / module_json_outputs
  -> P1-C22 中文 HTML 审计
  -> P5 Dashboard / Evidence / Radar Detail
```

## P2 必须遵守的输入契约

每个雷达指标必须从 `historical_window(metric_id)` 获取：

```yaml
required_fields:
  - metric_id
  - source_id
  - current
  - change_24h
  - quality_score
  - effective_quality_score
  - collection_freshness_status
  - business_recency_status
  - freshness_policy
  - selected_reason
  - candidates
  - conflict
```

P2 不允许直接读取 provider、Playwright artifact、FRED response 或 raw payload。

## SQLite 对齐要求

- P2 输出必须写入 `radar_outputs`。
- 每个指标 feature 必须写入 `feature_values`。
- 每个模块完整 JSON 必须写入 `module_json_outputs`。
- `run_id` 必须贯穿一次 radar 分析。
- P2 输出中保留 P1 选出的主源与 fallback/cross-check 关系。

## P1-C22 审计对齐要求

每次 P2 变更后必须复跑：

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit
```

验收看 HTML：

```text
reports/p1-c22-真实数据全链路验收报告.html
```

要求：

- P2 使用的指标显示 `SQLite 状态=已写入`。
- P2 使用的指标显示 `Radar 是否消费=是`。
- 若有多源冲突，不能隐藏，必须进入 Evidence / Radar Detail。
- 若 freshness 过期，雷达 feature 进入 invalidation_signals。

## 本轮对齐结果

- `macro_radar` 已接入 P1-C29 的实时市场指标。
- P2-C02 已更新宏观雷达指标清单。
- P2-C15 已补充 P1/P8/P1-C22 统一验收约束。
- P2-C17 已从 TODO 更新为 DONE，并记录实际权重与消费规则。
- 后端测试补充了 `macro_radar` 消费 P1-C29 指标的回归用例。

## DoD

- P2 任务卡明确 P1/P8/SQLite/P1-C22 审计契约。
- `macro_radar` 实际消费新增实时市场指标。
- `pytest` 通过。
- `ruff` 通过。
- P1-C22 中文 HTML 报告能显示新增指标的雷达消费状态。
