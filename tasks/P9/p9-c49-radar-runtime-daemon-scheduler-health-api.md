# P9-C49 Radar Runtime Daemon Scheduler Health API

Status: DONE

## Background

The BTC center card and 14 radar modules need a resident Radar Runtime Daemon. It should work like Event Watchtower: cadence scheduler, manual run once, heartbeat, watchdog, health API, and runtime version guard.

## Goal

Add Radar Runtime Daemon and APIs:

```text
FastAPI startup
  -> start radar_runtime_daemon by default
  -> scheduler tick by cadence profile
  -> run due module groups
  -> persist module snapshots
  -> rebuild BTC cockpit runtime snapshot
  -> expose health / status / run once APIs
```

## API Proposal

```text
GET  /api/radar-runtime/daemon/health
GET  /api/radar-runtime/daemon/status
POST /api/radar-runtime/run-once
POST /api/radar-runtime/daemon/pause
POST /api/radar-runtime/daemon/resume
POST /api/radar-runtime/daemon/tick
GET  /api/radar-runtime/modules/latest
GET  /api/radar-runtime/cockpit/latest
```

## Health Contract

```json
{
  "runtime_version": "radar_runtime.v1",
  "enabled": true,
  "health_state": "healthy|degraded|stale|failed|paused_by_user",
  "heartbeat_at": "",
  "heartbeat_age_sec": 0,
  "watchdog": {
    "status": "ok|warning|failed",
    "stale_reasons": [],
    "recovery_attempt_count": 0
  },
  "scheduler": {
    "last_tick_at": "",
    "next_due": []
  }
}
```

## DoD

1. Radar Runtime Daemon starts by default with FastAPI.
2. Cadence-based scheduler tick is supported.
3. Manual full sweep is supported and is separate from P4.5 full-chain run once.
4. Health outputs healthy, degraded, stale, failed, paused_by_user.
5. Watchdog outputs stale reasons, thresholds, and recovery attempts.
6. Module-level heartbeat and cockpit snapshot age are separated.
7. Daemon stale does not directly change BTC score, but blocks confirmed_signal.
8. APIs return latest module runtime snapshots and cockpit runtime snapshot.
