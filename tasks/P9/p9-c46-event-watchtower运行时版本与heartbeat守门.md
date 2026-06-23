# P9-C46 / Event Watchtower 运行时版本与 Heartbeat 守门

## 状态
DONE

## 背景

本轮排查发现，FastAPI 进程可能仍加载旧版 Event Watchtower daemon：`/api/event-window/daemon/status` 未返回 scheduler 字段，且 latest snapshot 停留在数小时前。即使代码已经具备 scheduler，运行时没有重启或没有正确启动常驻轮询，也会导致 UI 显示“daemon running”，但实际事件窗口没有持续更新。

## 目标

让 Event Watchtower 的运行状态可被机器审计，避免旧进程、旧代码、无 heartbeat、无 scheduler tick 时继续显示为健康。

## 范围

- FastAPI startup 与 Event Watchtower daemon 启动链路
- `/api/event-window/daemon/status`
- `/api/event-window/health` 或等价健康检查输出
- daemon heartbeat / runtime version / scheduler status

## 关键要求

1. FastAPI 启动时必须启动 Event Watchtower 常驻 daemon，而不是只执行一次 `collect_once`。
2. daemon status 必须包含当前运行时代码版本和 schema version。
3. scheduler tick、manual full sweep、latest persisted snapshot 三者必须分开展示。
4. 如果 status 缺少当前版本字段，UI/API 必须能标记为 `runtime_stale_or_old_process`。
5. snapshot 超过 stale 阈值时，不能继续显示 `daemon running` 健康态。

## 建议输出

```json
{
  "status": "running|degraded|stale|paused_by_user|stopped",
  "collection_mode": "standalone_daemon",
  "scheduler_enabled": true,
  "runtime_code_version": "event_watchtower.v3.2.market-shock",
  "status_schema_version": "p9.event_watchtower.status.v2",
  "last_tick_at": "",
  "last_market_probe_at": "",
  "last_full_sweep_at": "",
  "last_snapshot_id": "",
  "last_snapshot_age_sec": 0,
  "source_cadence": {},
  "stale_reasons": []
}
```

## DoD

- [x] `/api/event-window/daemon/status` 返回 `scheduler_enabled`、`last_tick_at`、`source_cadence`、`runtime_code_version`。
- [x] FastAPI 重启后 60 秒内至少写入一次 Event Watchtower heartbeat。
- [x] latest snapshot 超过 stale 阈值时，status 变为 `stale` 或 `degraded`。
- [x] old process / old schema 可被检测并输出 `runtime_stale_or_old_process`。
- [x] status 不使用 mock 字段伪装健康。
- [x] 自动 daemon 与主 radar run once 解耦。
- [x] 单元或 smoke 测试覆盖 startup、heartbeat、stale status。

## 依赖

- P9-C41
- P9-C45
- P5-C77


