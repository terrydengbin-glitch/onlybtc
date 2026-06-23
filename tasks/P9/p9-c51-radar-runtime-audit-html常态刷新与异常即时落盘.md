# P9-C51 / Radar Runtime Audit HTML 常态刷新与异常即时落盘

## 状态

DONE

## 背景

`reports/radar-runtime-audit-report.html` 当前是静态审计产物，只在执行 `scripts/generate_radar_runtime_audit_report.py` 或 P7 审计流程时更新。

Radar Runtime daemon 已经常驻运行，并按不同模块 cadence 产出 SQLite/API snapshot：

```text
fast modules: 60s
confirmation modules: 300s
regime modules: 1800s
```

但审计 HTML 不会随 daemon 常态更新，导致用户打开 `file:///E:/onlyBTC/reports/radar-runtime-audit-report.html` 时可能看到旧 snapshot，误以为实时状态仍是旧结论。

## 目标

把 Radar Runtime 审计 HTML 接入常驻 daemon 的低频落盘机制，使它成为“近实时审计快照”，同时保持它不参与业务判断。

核心目标：

```text
实时判断仍以 API / SQLite / UI 为准；
审计 HTML 每 5 分钟常态刷新；
health 变差或 watchdog 发现 stale 时即时刷新；
manual run once 后即时刷新；
HTML 顶部清楚显示 generated_at / runtime_snapshot_id / runtime_asof_ts / snapshot_age_sec / refresh_mode。
```

## 范围

涉及：

- Radar Runtime daemon tick / health transition
- `scripts/generate_radar_runtime_audit_report.py`
- `reports/radar-runtime-audit-report.html`
- `reports/radar-runtime-audit-report.md`
- daemon health / audit metadata
- 后端测试

不涉及：

- 修改 radar module 评分逻辑
- 修改 BTC cockpit 业务判断
- 修改 Event Window daemon
- 让前端 UI 直接读取 HTML

## 业务规则

### 常态刷新

```text
Radar Runtime daemon 启动后，第一次 bootstrap/full sweep 完成时立即生成 HTML。
之后每 300 秒生成一次 HTML。
常态刷新不应阻塞 scheduler tick 主链条。
生成失败必须记录 last_audit_html_error，但不能导致 daemon 退出。
```

### 异常即时刷新

以下情况必须绕过 300 秒间隔，立即刷新 HTML：

```text
health_state 从 healthy 变成 degraded/stale/failed
stale_reasons 从空变成非空
module_count / fresh_module_count 出现异常下降
watchdog 判断 snapshot stale
```

### 手动 run once 刷新

```text
/api/radar-runtime/run-once 完成后必须立即刷新 HTML。
refresh_mode = manual_run_once
```

### HTML 元数据

HTML 顶部必须显示：

```json
{
  "generated_at": "",
  "html_refresh_mode": "bootstrap|scheduled|health_transition|watchdog|manual_run_once",
  "runtime_snapshot_id": "",
  "runtime_asof_ts": "",
  "snapshot_age_sec": 0,
  "daemon_health_state": "",
  "module_count": 14,
  "fresh_module_count": 14,
  "stale_module_count": 0
}
```

### API / UI 边界

```text
UI 继续通过 /api/radar-runtime/* 读取实时数据。
HTML 只作为审计文件，不作为前端业务数据源。
Audit Reports 列表可链接该 HTML，但不得把 HTML 内容反向喂给 dashboard。
```

## 实现建议

新增或调整：

```text
backend/src/onlybtc/radar_runtime/daemon.py
  - last_audit_html_generated_at
  - last_audit_html_snapshot_id
  - last_audit_html_refresh_mode
  - last_audit_html_error
  - maybe_generate_audit_html(reason)

scripts/generate_radar_runtime_audit_report.py
  - generate(refresh_mode: str = "manual", runtime_snapshot_id: str | None = None)
  - 输出 runtime_asof_ts / snapshot_age_sec / refresh_mode
```

## DoD

- [x] Radar Runtime daemon bootstrap/full sweep 后会生成一次 `reports/radar-runtime-audit-report.html`。
- [x] daemon 常态运行时，HTML 至少每 300 秒刷新一次。
- [x] health_state 变差或 stale_reasons 出现时，HTML 不等 300 秒立即刷新。
- [x] `/api/radar-runtime/run-once` 完成后立即刷新 HTML。
- [x] HTML 顶部显示 `generated_at`、`html_refresh_mode`、`runtime_snapshot_id`、`runtime_asof_ts`、`snapshot_age_sec`。
- [x] daemon health 暴露 `last_audit_html_generated_at`、`last_audit_html_snapshot_id`、`last_audit_html_refresh_mode`、`last_audit_html_error`。
- [x] 生成 HTML 失败不会导致 daemon 崩溃，但会在 health 中可见。
- [x] 后端测试覆盖 scheduled refresh、manual refresh、health transition refresh、generator failure non-fatal。
- [x] `python -m pytest backend/tests/test_radar_runtime_daemon.py backend/tests/test_event_watchtower.py -q` 通过。
- [x] 手动观察：重启后 bootstrap 自动生成 HTML；manual run once 后 HTML 即时更新，且 `snapshot_age_sec=2`。

## Verification

- `python -m compileall backend/src/onlybtc/radar_runtime/audit_report.py backend/src/onlybtc/radar_runtime/daemon.py scripts/generate_radar_runtime_audit_report.py` passed.
- `python -m pytest backend/tests/test_radar_runtime_daemon.py -q` passed: 3 passed.
- `python -m pytest backend/tests/test_radar_runtime_daemon.py backend/tests/test_event_watchtower.py -q` passed: 14 passed, 2 warnings.
- `python scripts/generate_radar_runtime_audit_report.py` generated `reports/radar-runtime-audit-report.html` with `html_refresh_mode=manual_script`, `runtime_asof_ts`, and `snapshot_age_sec`.
- Backend restarted successfully. `/api/radar-runtime/daemon/health` reports `last_audit_html_generated_at`, `last_audit_html_snapshot_id`, `last_audit_html_refresh_mode`, and `last_audit_html_error`.
- `/api/radar-runtime/run-once` completed and refreshed HTML with `html_refresh_mode=manual_run_once`, `snapshot_age_sec=2`.

## 验收命令

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radar_runtime.py backend\tests\test_radar_runtime_daemon.py -q

Get-Item reports/radar-runtime-audit-report.html | Select FullName, LastWriteTime
Invoke-RestMethod http://127.0.0.1:8118/api/radar-runtime/daemon/health
```

## 依赖

- P1-C72 Radar Module Cadence Profile
- P2-C42 Radar Runtime Incremental Module Runner
- P8-C38 Radar Runtime SQLite Snapshot 持久化
- P9-C49 Radar Runtime Daemon Scheduler Health API
- P7-C27 Radar Runtime 全链路审计
