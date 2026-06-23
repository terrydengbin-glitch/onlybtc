# P12-C05 / Event Window / Event Watchtower Full-chain Audit

- status: `PASS`
- generated_at: `2026-06-23T12:06:45Z`
- schema_version: `p12.c05.event_window_watchtower_audit.v1`

## Key Evidence

### daemon

```json
{
  "status": "ok",
  "health_state": "healthy",
  "runtime_code_version": "event_watchtower.v3.2.market-shock",
  "last_snapshot_id": "evt-20260623120645-c39cbbf0",
  "last_tick_age_sec": 0,
  "market_probe_age_sec": 23
}
```

### event_counts

```json
{
  "calendar": 30,
  "timeline": 100,
  "alerts": 30,
  "sources": 43,
  "fetches": 40
}
```

### endpoint_summary

```json
{
  "/api/event-window/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 77,
    "url": "http://127.0.0.1:8118/api/event-window/latest"
  },
  "/api/event-window/active": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 9,
    "url": "http://127.0.0.1:8118/api/event-window/active"
  },
  "/api/event-window/calendar?limit=30": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 29,
    "url": "http://127.0.0.1:8118/api/event-window/calendar?limit=30"
  },
  "/api/event-window/timeline?limit=100": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 73,
    "url": "http://127.0.0.1:8118/api/event-window/timeline?limit=100"
  },
  "/api/event-window/alerts?limit=30": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 33,
    "url": "http://127.0.0.1:8118/api/event-window/alerts?limit=30"
  },
  "/api/event-window/sources/status": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 3594,
    "url": "http://127.0.0.1:8118/api/event-window/sources/status"
  },
  "/api/event-window/sources/fetches?limit=40": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 23,
    "url": "http://127.0.0.1:8118/api/event-window/sources/fetches?limit=40"
  },
  "/api/event-window/daemon/status": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 8,
    "url": "http://127.0.0.1:8118/api/event-window/daemon/status"
  },
  "/api/event-window/daemon/health": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 25,
    "url": "http://127.0.0.1:8118/api/event-window/daemon/health"
  },
  "/api/event-window/market-probe/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 6,
    "url": "http://127.0.0.1:8118/api/event-window/market-probe/latest"
  },
  "/api/event-window/shock-lane/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 75,
    "url": "http://127.0.0.1:8118/api/event-window/shock-lane/latest"
  }
}
```

## Issues

- No blocking or warning issues found.

## Full JSON

See `p12-event-window-watchtower-audit.json`.
