# P9-C50 / Event Watchtower Scheduler Due Gate 修复与审计

## 状态
DONE

## 背景

P1-C73 已经为 Event Window 二级日历源加入 throttle / backoff / cache guard，解决了 `faireconomy-ff-calendar-thisweek-json` 被 429 后继续高频请求的问题。

但在重启观察时发现另一个运行时断点：

```text
daemon health 中 source_cadence.next_due_at 显示官方源尚未到期；
但 backend 日志里 FRED / NYFed / DOL / BEA / Fed RSS 仍在约 1 分钟内重复请求。
```

这说明当前自动 scheduler tick 可能没有真正按 source cadence 跳过未到期 source，或者内部 collect_once 在自动模式下仍执行了 full sweep。

这不是数据源可用性问题，而是 **P9 daemon scheduler due gate** 问题。

## 目标

修复 Event Watchtower 自动运行链路，确保：

```text
自动运行 = 分频 scheduler tick，只执行 due source group；
手动 Event Window Run Once = full sweep，允许忽略 cadence；
启动 initial collect = 可执行一次 bootstrap full sweep，但之后必须进入 due-gated tick。
```

## 范围

涉及：

- Event Watchtower daemon scheduler loop
- source cadence / next_due_at 判定
- collect_once / collect_due_sources / full_sweep 入口边界
- daemon health / source diagnostics API
- audit bundle freshness 与 source fetch lineage

不涉及：

- 修改 Event Window 业务评分
- 修改 BTC / radar score
- 修改 P1 provider parser 本身
- 修改 UI 视觉布局

## 业务规则

### 自动 tick

自动 tick 必须：

```text
1. 读取每个 source_group 的 next_due_at。
2. 只运行 due source_group。
3. 对未到期 source_group 写入 skipped_not_due lineage 或 scheduler trace。
4. 不应发起未到期 source_group 的 HTTP 请求。
5. tick 后更新 due source_group 的 last_attempt_at / last_success_at / next_due_at。
```

### 手动 run once

手动 Event Window Run Once 必须：

```text
1. 标记 manual_full_sweep=true。
2. 忽略 cadence。
3. 跑完整 collect / analyze / persist / html bundle。
4. 不触发主 radar pipeline。
```

### 启动 bootstrap

启动时允许：

```text
startup -> bootstrap full sweep once
```

但必须：

```text
bootstrap 完成后写入 source_cadence 状态；
后续 tick 不允许继续 full sweep。
```

## API / 审计要求

`/api/event-window/daemon/health` 需要能看出：

```json
{
  "last_tick_mode": "bootstrap_full_sweep|scheduled_due_tick|manual_full_sweep",
  "next_due_sources": [],
  "last_due_sources": [],
  "last_skipped_sources": [],
  "manual_full_sweep_ignores_cadence": true
}
```

Source diagnostics / audit HTML 需要能审计：

```text
source requested because due
source skipped because not due
source requested because manual full sweep
source requested because bootstrap
```

## DoD

- [x] 自动 scheduler tick 不再请求未到期 official_calendar / expectation_nowcast / Fed RSS 等 source。
- [x] daemon health 显示 `last_tick_mode`、`last_due_sources`、`last_skipped_sources`。
- [x] 未到期 source 有可审计的 skip reason：`skipped_not_due`。
- [x] manual Event Window Run Once 仍能 full sweep，并标记 `manual_full_sweep=true`。
- [x] startup bootstrap full sweep 只发生一次，之后切换到 scheduled due tick。
- [x] source diagnostics / audit HTML 能展示 due / skipped / manual / bootstrap 原因。
- [x] 后端测试覆盖：bootstrap、scheduled due tick、manual full sweep、not-due skip。
- [x] 运行观察至少 2 个 tick，日志中未出现未到期二级/官方源重复请求。
- [x] `pytest backend/tests/test_event_watchtower*.py` 通过。
- [x] Event Window daemon health 为 healthy，watchdog 无 stale reason。

## Verification

- `python -m compileall backend/src/onlybtc/event_window/watchtower.py backend/src/onlybtc/event_window/daemon.py backend/src/onlybtc/db/repositories.py scripts/generate_event_window_source_audit_html.py` passed.
- `python -m pytest backend/tests/test_event_watchtower.py backend/tests/test_event_watchtower_offline.py -q` passed: 15 passed.
- Runtime observation after restart: bootstrap full sweep happened once; subsequent ticks requested market/BTC due groups only, while official calendar / expectation / Fed RSS stayed skipped until next due.
- `/api/event-window/daemon/health` reports healthy with `last_tick_mode`, `last_due_sources`, `last_skipped_sources`, `manual_full_sweep_ignores_cadence=true`.
- `/api/event-window/sources/status` reports `*-scheduler` rows with `status=skipped_not_due`, `source_group`, `skip_reason=next_due_at_in_future`.

## 验收观察命令

```powershell
Invoke-RestMethod http://127.0.0.1:8118/api/event-window/daemon/health
Invoke-RestMethod http://127.0.0.1:8118/api/event-window/sources/status
Get-Content .\backend-restart.err.log -Tail 160
```

## 依赖

- P9-C45
- P9-C48
- P1-C73
- P7-C21
