# P9-C48 Event Watchtower Daemon Heartbeat / Watchdog / Health 加固

状态：DONE

## 背景

Event Window 是独立常驻 daemon，不依赖主 radar pipeline。当前 `/api/event-window/daemon/status` 已经能返回 `running`、`last_tick_at`、`last_snapshot_age_sec`、`market_probe_age_sec`、`source_cadence` 等字段，但还缺少更硬的 watchdog 语义：

- 进程活着不代表 scheduler tick 正常。
- snapshot 更新不代表 BTC market probe 正常。
- source fetch success 不代表 high/critical alert pipeline 没卡住。
- UI 需要明确知道 daemon 是 `healthy / degraded / stale / restarting / failed`，而不是只显示 running。

因此需要为 Event Watchtower 增加 heartbeat 持久化、watchdog health 判定、自动恢复和审计输出。

## 目标

新增 Event Watchtower daemon health layer：

```text
FastAPI startup
  -> start event_watchtower_daemon
  -> heartbeat writer
  -> watchdog checker
  -> health API
  -> UI health strip / stale warning
```

核心原则：

```text
daemon status = process + scheduler + snapshot + market_probe + source_fetch + alert_pipeline
```

不能只靠进程是否存在判断健康。

## 范围

- Event Watchtower daemon runtime
- SQLite heartbeat / health snapshot
- `/api/event-window/daemon/status`
- `/api/event-window/daemon/health`
- Event Watchtower UI health 显示
- P7 audit / regression

## 后端要求

### 1. Heartbeat 持久化

新增或复用 SQLite 表，记录：

```json
{
  "heartbeat_id": "",
  "daemon_name": "event_watchtower",
  "runtime_code_version": "",
  "pid": 0,
  "started_at": "",
  "heartbeat_ts": "",
  "last_tick_at": "",
  "last_snapshot_id": "",
  "last_snapshot_age_sec": 0,
  "last_market_probe_at": "",
  "market_probe_age_sec": 0,
  "scheduler_enabled": true,
  "source_cadence": {},
  "health_state": "healthy|degraded|stale|failed|paused_by_user",
  "stale_reasons": []
}
```

### 2. Watchdog 判定

Health 状态规则：

```text
healthy:
  scheduler_enabled = true
  last_tick_age <= 2 * min_due_interval
  last_snapshot_age <= 2 * expected_snapshot_interval
  market_probe_age <= 2 * btc_reaction_sec
  last_error empty

degraded:
  部分 source failed / fallback
  market_probe_age 超阈值但 snapshot 仍更新
  source fetch 连续失败但非 critical

stale:
  last_tick_age 超阈值
  last_snapshot_age 超阈值
  market_probe_age 超阈值且 shock_fast_lane 依赖 market probe

failed:
  daemon loop exception 连续超过阈值
  scheduler stopped unexpectedly
  SQLite 写入失败

paused_by_user:
  用户主动暂停，不算故障，但 UI 必须明确显示
```

### 3. Watchdog 自愈

```text
if health_state in stale/failed and paused_by_user == false:
  attempt_restart_scheduler()
  write watchdog_recovery event
  keep latest snapshot readable
```

要求：

- 自愈不能触发主 radar run once。
- 自愈不能清空历史数据。
- 自愈失败必须进入 `failed` 并保留 `last_error`。

### 4. API 契约

`GET /api/event-window/daemon/status` 继续兼容旧字段，并新增：

```json
{
  "daemon": {
    "health_state": "healthy|degraded|stale|failed|paused_by_user",
    "watchdog": {
      "enabled": true,
      "last_check_at": "",
      "last_recovery_at": "",
      "recovery_attempt_count": 0,
      "stale_reasons": [],
      "thresholds": {
        "last_tick_max_age_sec": 60,
        "snapshot_max_age_sec": 120,
        "market_probe_max_age_sec": 15
      }
    }
  }
}
```

新增：

```text
GET /api/event-window/daemon/health
```

返回机器审计友好的 health payload。

## UI 要求

Event Watchtower 子页面顶部增加 health strip：

```text
Daemon Health: healthy / degraded / stale / failed / paused
Heartbeat: 12s ago
Market Probe: 5s ago
Last Snapshot: 38s ago
Watchdog: enabled
```

显示规则：

- `healthy`：青绿色
- `degraded`：黄色
- `stale`：橙色
- `failed`：红色
- `paused_by_user`：蓝灰色

如果 `stale/failed`：

- 浮窗不直接消失。
- UI 显示 stale reason。
- 提供 `Run Event Once` 和 `Resume Daemon` 操作入口。

## P7 审计要求

新增 Event Watchtower daemon health audit：

```text
1. daemon running 但 last_tick stale => FAIL
2. daemon running 但 market_probe stale => FAIL
3. paused_by_user 不算 FAIL，但必须可见
4. watchdog recovery event 必须入 timeline
5. health_state 必须与 stale_reasons 一致
6. API status / health / latest 三者 snapshot_id 和 heartbeat 时间一致
```

## DoD

- [x] SQLite 持久化 daemon scheduler / latest snapshot / market probe，health 从同源状态生成。
- [x] `/api/event-window/daemon/status` 返回 `health_state` 和 `watchdog`。
- [x] `/api/event-window/daemon/health` 可独立返回 health payload。
- [x] Watchdog 能识别 last_tick / snapshot / market_probe stale。
- [x] Watchdog 在非 paused 状态下可尝试恢复 scheduler thread。
- [x] Watchdog recovery 通过 `last_recovery_at / recovery_attempt_count` 可审计。
- [x] UI 显示 daemon health strip 和 stale reasons。
- [x] stale/failed 时浮窗不因状态刷新而突然消失。
- [x] 单元测试覆盖 healthy / degraded / stale / paused_by_user。
- [x] P7 audit 可通过 health endpoint 检测 daemon 假 running。
- [x] `npm run build` 通过。

## 关联任务

- P9-C41 Event Watchtower Daemon 常驻运行与推送
- P9-C45 Event Watchtower 分频轮询 Scheduler 与 Manual Full Sweep
- P9-C46 Event Watchtower 运行时版本与 Heartbeat 守门
- P5-C78 Daemon Stale 与 Market Shock UI
- P7-C22 暴跌漏报回归审计
