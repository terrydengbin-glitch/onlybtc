# P7-C35 Radar Runtime Source Gate Async Collect Bridge

## 状态

DONE

## 所属 Phase

P7 动态校准与生产化增强

## 任务目标

修复 Radar Runtime Source Refresh Gate 在 FastAPI startup / event loop 上下文中调用 async `collect_sources()` 时出现 `coroutine was never awaited` 的问题，确保 targeted source refresh 真正执行并写入 current-run DataQualitySnapshot，而不是被旧数据或历史窗口误导。

## 背景依据

- [P7-C28](p7-c28-radar-runtime-stale-feature-targeted-repair-audit.md)
- [P7-C34](p7-c34-source-health-warning-severity-attribution-calibration.md)
- 后端启动日志：`RuntimeWarning: coroutine 'collect_sources' was never awaited`

## 实施范围

- 保留 `run_source_refresh_gate()` 同步契约。
- 增加安全 bridge：
  - 无 running event loop 时，继续 `asyncio.run()`。
  - 有 running event loop 时，在短线程中运行独立 event loop 并等待结果。
- 确保 coroutine 只在确定执行路径后创建，不再产生 unawaited coroutine warning。
- 新增测试覆盖 running event loop 场景。
- 刷新 P7-C04/P7-C08 报告，确认 source gate 不再写旧 schema/失败快照。

## 输入

- `radar_runtime.source_gate.run_source_refresh_gate()`
- `sources.service.collect_sources()`
- Radar Runtime daemon startup / run-once / scheduler tick

## 输出

- 修复后的 async collect bridge。
- 单元测试覆盖 event loop context。
- 刷新 source health / production gate 报告。

## 验收标准

- [x] 在 running event loop 中调用 `run_source_refresh_gate()` 不抛 `asyncio.run()` 相关错误。
- [x] 不再产生 `collect_sources coroutine was never awaited` warning。
- [x] source_refresh_gate 返回 success/partial/failed 的正常 payload。
- [x] 不改变 collect_sources 的 run_id/source_id/mode/db 参数契约。
- [x] P7-C04/P7-C08 报告使用 scoped current-run source snapshot。

## 验证

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_radar_runtime_daemon.py -q`
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c04_source_health_monitor_report.py`
- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe scripts\generate_p7_c08_production_gate_report.py`

## 验证结果

- `PYTHONPATH=backend/src .\.venv\Scripts\python.exe -m pytest backend\tests\test_p7_source_health_monitor.py backend\tests\test_radar_runtime_daemon.py backend\tests\test_p7_production_gate.py backend\tests\test_logging.py -q` -> 27 passed.
- Local `run_full_sweep(trigger_type='p7_c35_source_gate_validation')` returned `last_source_refresh_gate.status=success`, `collect_mode=live`, `refreshed_source_count=68`, `failed_source_count=0`.
- Latest DataQualitySnapshot chain is scoped current-run: `radar-runtime-source-20260622230746-aac4d0`, `fresh=72/stale=0/expired=0/missing=0`, `business_lagging=0`.

## 风险 / 回滚

- 风险：短线程 bridge 会阻塞当前调用直到 collect 完成。当前同步契约本来就是阻塞式，行为一致。
- 回滚：恢复直接 `asyncio.run()`，但会重新触发 event loop 上下文失败。
