# P7-C34 Source Health Warning Severity Attribution Calibration

## 状态

DONE

## 所属 Phase

P7 动态校准与生产化增强

## 任务目标

校准 P7-C04 Source Health Monitor 的 warning 归因：当 recent source health events 只有 `warning` 状态且数据仍 fresh/current 时，应作为 `watch` 暴露，不应把 P7-C04 提升到上线前 warning；只有 error、stale/expired/missing、业务 recency lagging/outdated 或明确 provider/auth 问题才保持 warning/critical。

## 背景依据

- [P7-C04](p7-c04-数据源健康监控与告警.md)
- [P7-C08](p7-c08-生产化校准mock与dod验收.md)
- [P7-C32](p7-c32-source-health-run-mode-production-gate-scope-repair.md)

## 实施范围

- 调整 `backend/src/onlybtc/governance/source_health.py` 中 `recent_source_health_events` alert 的 severity。
- 对 recent warning events 增加归因：
  - `error` -> critical。
  - `stale/expired/missing` 或 message 含对应 freshness -> warning。
  - `business_recency=lagging/outdated/provider_stale_suspect` -> warning。
  - 仅 quality warning 且 `collection_freshness=fresh`、`business_recency=current/expected_lag` -> watch。
- 报告继续展示 source list 和 recommended_action，不隐藏 warning events。
- 不修改 source collection、SQLite schema、前端 API DTO 或状态机。

## 输入

- `SourceHealthEvent.status`
- `SourceHealthEvent.message`
- P7-C04 source health report
- P7-C08 production gate

## 输出

- 修正后的 source health alert severity。
- 覆盖 error、fresh/current quality warning、stale warning 的单元测试。
- 刷新 `reports/p7-c04-source-health-monitor-report.json/md`。
- 刷新 `reports/p7-c08-production-gate-report.json/md`。

## 验收标准

- [x] recent error event 仍产生 critical。
- [x] recent stale/expired/missing event 仍产生 warning。
- [x] fresh/current 的 quality warning 降为 watch。
- [x] P7-C04 当前报告不因 fresh/current quality warning 被提升到 warning。
- [x] P7-C08 child P7-C04 不再是 warning，仅保留 watch 上下文。
- [x] 不降低 run_mode、missing/expired、provider auth 问题的门禁强度。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_source_health_monitor.py backend\tests\test_p7_production_gate.py -q`
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c04_source_health_monitor_report.py`
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c08_production_gate_report.py`

## 验证结果

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_source_health_monitor.py backend\tests\test_radar_runtime_daemon.py backend\tests\test_p7_production_gate.py backend\tests\test_logging.py -q` -> 27 passed.
- `reports/p7-c04-source-health-monitor-report.json` -> `overall_status=watch`, latest run `radar-runtime-source-20260622230746-aac4d0`, freshness `fresh=72/stale=0/expired=0/missing=0`, business recency `lagging=0`.
- `reports/p7-c08-production-gate-report.json` -> child `P7-C04=watch`; all DoD checks passed. Remaining production gate warning comes from P7-C05/P7-C06/P7-C07, not P7-C04.

## 风险 / 回滚

- 风险：低质量但 fresh/current 的 warning 被误读为完全健康。处理方式：保留 `watch` alert 和 source 列表。
- 回滚：恢复 recent warning events 固定 `warning` 级别。
