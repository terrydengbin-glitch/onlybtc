# P3-C15 Run Mode Integrity 按同 run 作用域校准与历史 mock 隔离

## 状态

DONE

## 所属 Phase

P3 算法预警与反证系统 / P1-P2-P3-P4 同 run 数据契约

## 任务目标

修复 P3 `run_mode_integrity_invalidation` 当前按全库 `metric_values` 扫描导致的历史 mock 误伤问题，确保 live 全链条只按本轮 `collect_run_id / p2_radar_run_id / p3_run_id` 的同 run 数据判断生产完整性。

live 模式原则：

```text
live run
  -> 只能消费本 run 真实采集值进入生产链条
  -> 不允许 mock/test/unknown 进入本 run 的发布判断
  -> 历史数据回顾例外，但必须标记为 history/audit context
  -> 历史 mock 污染只能作为数据库卫生提示，不能阻断本轮 clean live run
```

## 背景与发现

2026-05-21 P4-C24 live + LLM 全链条后，P4 正确降级为 `watch_only`，原因来自 P3：

```text
condition_id=run_mode_integrity_invalidation
status=triggered
action=block_critical_publish
reason_code=run_mode_mixed_history
```

进一步检查发现，最新本轮采集实际是干净的：

```text
collect_run_id=collect-20260521122557-494801
current collect metric_values:
live=128
mock=0
current collect mixed_metric_ids=0

P2 feature scopes:
current_run=114
provider_required=4

P3 feature scopes:
current_run=1176
provider_required=4
```

但 P3 `_run_mode_risk(db)` 当前扫全库 `metric_values`：

```text
whole database metric_values:
live=1594
mock=11304
mixed_metric_ids_count=111
```

因此历史 mock replay / 历史测试数据被误算成本轮 live 的生产风险，导致当前 clean live run 被误触发 hard block。

## 问题根因

当前 P3 有三处口径过宽：

1. `onlybtc.algorithms.p3._run_mode_risk(db)`
   - 未接收 `collect_run_id` / `run_id`。
   - 直接扫描全库 `MetricValue.run_mode`。
   - 历史 mock 记录会影响任意后续 live run。

2. `check_global_invalidations()`
   - 调用 `_run_mode_risk(db)` 时没有传入本轮 run lineage。
   - `run_mode_integrity_invalidation` 无法区分：
     - current_run production risk
     - database historical contamination

3. P1-C22 / P3 HTML 叙事
   - 当前 run_mode summary 容易把“全库历史污染”写成“本轮 live 混入 mock”。
   - 需要拆成：
     - current_run_run_mode_summary
     - historical_database_run_mode_summary

## 业务原则

- live 模式不允许 mock/test/unknown 进入当前生产链路。
- live 模式允许历史回顾，但历史数据必须是：
  - `history_context`
  - `audit_context`
  - `historical_fallback`
  - 或明确标记 `non_production_history`
- 历史 mock 数据可以用于回放测试、样本统计、审计提示，但不能作为当前 live 发布门禁的 hard blocker。
- 当前 run 的 production readiness 必须以本轮 lineage 为准：
  - `collect_run_id`
  - `p2_radar_run_id`
  - `p3_run_id`
  - Feature metadata 中的 `source_run_id / feature_run_scope`
- 若本轮 live 中发现 mock/test/unknown，则必须触发 `run_mode_integrity_invalidation`。
- 若仅全库历史存在 mock，但本轮 current_run 全 live，则不得触发 hard block，只能在 HTML 中提示历史数据库含 mock。

## 实施范围

1. P3 run_mode risk 作用域重构
   - `_run_mode_risk()` 增加参数：
     - `collect_run_id`
     - `p3_run_id`
     - `scope="current_run" | "database_history"`
   - current_run 模式只统计：
     - `MetricValue.run_id == collect_run_id`
     - 或 P3/P2 feature metadata 中 `source_run_id == collect_run_id`
   - 输出：
     - `current_run_counts`
     - `current_run_mixed_metric_ids`
     - `database_history_counts`
     - `database_history_mixed_metric_ids`
     - `production_blocker`
     - `history_contamination_warning`

2. `check_global_invalidations()` 对齐
   - 接收并传递 `collect_run_id`。
   - `run_mode_integrity_invalidation` 仅根据 current_run scope 触发。
   - database history mock 只进入 payload 的 warning 字段。

3. P3 pipeline 对齐
   - `run_p3_pipeline()` 调用 `check_global_invalidations()` 时传入 `collect_run_id`。
   - `generate_algorithm_alerts()` / `_alert_candidates()` 如使用 run_mode risk，也必须使用 current_run scope。

4. P1/P3 HTML 叙事对齐
   - P1-C22 / P3 HTML 中显示两套摘要：
     - 当前 run mode integrity
     - 历史数据库污染提示
   - 不再把历史 mock 直接写成本轮 live 混入。

5. P4 下游验证
   - P4-C24 门控不变。
   - 当 P3 不再误触发 hard block 时，P4 不应因为历史 mock 自动 `watch_only`。
   - 若仍有 event/missing-primary constraints，则 P4 可继续 watch_only，但原因必须真实。

## 输入

- `MetricValue.run_id / run_mode`
- P2 `FeatureValue.metadata_json.source_run_id / feature_run_scope`
- P3 `FeatureValue.metadata_json.source_run_id / feature_run_scope`
- `collect_run_id`
- `p2_radar_run_id`
- `p3_run_id`
- P1/P2/P3/P4 HTML 审计上下文

## 输出

- 修正后的 P3 `run_mode_integrity_invalidation`
- current-run scoped run mode risk payload
- database-history mock contamination warning
- P3 HTML 中清晰区分当前 run 与历史库污染
- P4 final JSON 不再被历史 mock 误阻断

## 验收标准

- 最新 clean live collect：
  - `MetricValue.run_id == collect_run_id` 中 `mock=0/test=0/unknown=0`
  - 不触发 `run_mode_integrity_invalidation`
- 若当前 live collect 出现 mock/test/unknown：
  - 必须触发 `run_mode_integrity_invalidation`
  - `publish_impact=block_critical_publish`
- 全库历史存在 mock：
  - 只能显示 `history_contamination_warning=true`
  - 不影响当前 run `production_blocker`
- P3 HTML 必须展示：
  - current_run live/mock/test/unknown counts
  - current_run mixed metrics
  - database_history live/mock/test/unknown counts
  - database_history contamination warning
- P4 full audit 真实跑一次后：
  - `run_mode_integrity_invalidation` 不再因历史 mock 误触发
  - P4 `blocked_by` 只保留真实 hard constraints
- 不影响 P1/P2/P4/P8 现有审计字段。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3*.py backend/tests/test_p4_final_controller.py backend/tests/test_p4_full_chain_audit.py -q
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode mock --article-runtime-mode mock
.\.venv\Scripts\python.exe -m onlybtc.cli p4-dod-check
```

真实 LLM 验证在 mock 链路通过后执行：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p4-full-audit --run-mode live --runtime-mode llm --article-runtime-mode llm
```

## 依赖任务

P1-C22、P2-C21、P3-C10、P3-C13、P3-C14、P4-C24、P8 run-mode/history replay 相关治理

## 备注

本卡修的是 run-mode integrity 的作用域，不是放松 live 生产要求。live 当前 run 一旦真的混入 mock/test/unknown，仍必须硬阻断；只有历史数据库中残留的 mock 不应误伤当前 clean live run。

## 完成记录

已完成并验证：

- `_run_mode_risk(db, collect_run_id=...)` 已按 current run 作用域统计 `MetricValue.run_id == collect_run_id`。
- payload 已输出：
  - `current_run_counts`
  - `current_run_mixed_metric_ids`
  - `database_history_counts`
  - `database_history_mixed_metric_ids`
  - `production_blocker`
  - `history_contamination_warning`
- `check_global_invalidations()` 已传递 `collect_run_id`，`run_mode_integrity_invalidation` 只根据 current run 的 `production_blocker` 触发。
- 历史库存在 mock 时，只保留 `history_contamination_warning=true`，不阻断 clean live run。
- 当前 run 混入 mock/test/unknown 时，仍触发 `block_critical_publish`。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py -q
```

结果：`13 passed`。
