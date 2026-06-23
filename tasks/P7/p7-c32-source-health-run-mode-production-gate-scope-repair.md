# P7-C32 Source Health Run Mode Production Gate Scope Repair

## 状态

DONE

## 所属 Phase

P7 动态校准与生产化增强

## 任务目标

修复 P7-C08 暴露的 `run_mode_mixing_production_blocker`：P7-C04 Source Health / Data Quality 当前仍按全库 `metric_values` 统计 live/mock/test/unknown 混合，导致历史 mock/test 数据误伤当前生产门禁。本任务将 Data Quality 的 run mode summary 对齐 P8-C17 / P3-C15：当前 run 混入才 hard block，历史混用只作为 warning / hygiene context。

## 背景依据

- [P7-C08](p7-c08-生产化校准mock与dod验收.md)
- [P8-C16](../P8/p8-c16-run-mode隔离与历史窗口过滤底座.md)
- [P8-C17](../P8/p8-c17-run-mode历史混用归档与生产窗口审计口径治理.md)
- [P3-C15](../P3/p3-c15-run-mode-integrity按同run作用域校准与历史mock隔离.md)

## 实施范围

- `write_data_quality_snapshot()` 传入当前 `run_id` 给 run mode summary。
- `_run_mode_summary()` 输出：
  - `current_run`
  - `history`
  - `default_query_scope=live_only`
  - `history_replay_all_requires_explicit_run_mode=true`
- 兼容旧字段：
  - `live_metric_values`
  - `mock_metric_values`
  - `test_metric_values`
  - `unknown_metric_values`
  - `mixed_metric_ids`
  - `production_blocker`
- `production_blocker` 只根据当前 run 的 mock/test/unknown 或当前 run 内 mixed metrics 判断。
- 历史混用输出 `history_contamination_warning=true`，不能阻断 clean live current run。
- 刷新 P7-C04 与 P7-C08 报告，确认 C08 不再因历史混用被 hard block。

## 输入

- `MetricValue.run_id`
- `MetricValue.run_mode`
- `DataQualitySnapshot.payload.run_mode_summary`
- P7-C04 source health monitor
- P7-C08 production gate

## 输出

- 修复后的 `backend/src/onlybtc/sources/service.py` run mode summary。
- 新增/更新测试覆盖 current run clean + history mixed、current run mixed blocker。
- 刷新 `reports/p7-c04-source-health-monitor-report.json/md`。
- 刷新 `reports/p7-c08-production-gate-report.json/md`。

## 验收标准

- [x] 当前 run 只有 live，历史库存在 mock/test/unknown 时，`production_blocker=false`。
- [x] 当前 run 混入 mock/test/unknown 时，`production_blocker=true`。
- [x] `run_mode_summary.history_contamination_warning=true` 能保留历史混用提示。
- [x] P7-C04 不再因为历史混用误判 `run_mode_mixing_production_blocker`。
- [x] P7-C08 不再因为 P7-C04 source health historical run_mode mixing 被 hard block。
- [x] 不改变 `historical_window()` 默认 live-only 语义。
- [x] 不删除历史 mock/test 数据，不伪造 live 数据。

## 执行记录

- `write_data_quality_snapshot()` 已把当前 `run_id` 传给 `_run_mode_summary()`。
- `_run_mode_summary()` 已拆分：
  - `current_run`
  - `history`
  - `history_contamination_warning`
  - `default_query_scope=live_only`
  - `history_replay_all_requires_explicit_run_mode=true`
- 兼容旧字段仍保留：`live_metric_values`、`mock_metric_values`、`test_metric_values`、`unknown_metric_values`、`mixed_metric_ids`、`production_blocker`。
- `production_blocker` 现在只由 current run 非 live 值或 current run mixed metrics 决定；历史混用只保留 warning。
- P7-C04 governance 报告现在优先选择带 scoped run mode summary 的 DataQualitySnapshot，避免较新的 legacy snapshot 误伤生产门禁。
- 已重启 onlyBTC 后端/前端：
  - 后端：`http://127.0.0.1:8118`
  - 前端：`http://127.0.0.1:5188`
- 当前报告结果：
  - P7-C04：`overall_status=warning`，无 `run_mode_mixing_production_blocker`。
  - P7-C08：`overall_status=warning`，`failed DoD checks=[]`，P7-C04 子状态为 `warning`。
  - `production_apply_allowed=False` 仍保留，因为 C04/C05/C06/C07 还有 warning，需要人工或后续任务处理。

## 验证结果

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_p7_source_health_monitor.py backend\tests\test_p7_production_gate.py -q` -> 68 passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\sources\service.py backend\src\onlybtc\governance\source_health.py` -> passed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c04_source_health_monitor_report.py` -> refreshed。
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c08_production_gate_report.py` -> refreshed。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_p7_source_health_monitor.py -q`
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c04_source_health_monitor_report.py`
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c08_production_gate_report.py`

## 风险 / 回滚

- 风险：前端仍读取旧字段。处理方式：保留旧字段兼容，并新增 nested summary。
- 回滚：恢复 `_run_mode_summary(session)` 的旧全库统计逻辑，但这会重新引入历史 mock 误伤生产门禁。
