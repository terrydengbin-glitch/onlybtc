# P12-C04 / Radar Runtime / Module Score Full-chain Audit

- status: `PASS`
- generated_at: `2026-06-23T12:06:45Z`
- schema_version: `p12.c04.radar_runtime_module_score_audit.v1`

## Key Evidence

### daemon

```json
{
  "status": "ok",
  "health_state": "healthy",
  "runtime_fresh": true,
  "source_fresh": true,
  "last_snapshot_id": "radar-runtime-20260623120615-c0f25071",
  "sqlite_lock_state": "ok"
}
```

### cockpit_summary

```json
{
  "schema_version": null,
  "snapshot_id": null,
  "direction": null,
  "score": null
}
```

### endpoint_summary

```json
{
  "/api/radar-runtime/daemon/status": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 67,
    "url": "http://127.0.0.1:8118/api/radar-runtime/daemon/status"
  },
  "/api/radar-runtime/daemon/health": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 4,
    "url": "http://127.0.0.1:8118/api/radar-runtime/daemon/health"
  },
  "/api/radar-runtime/modules/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 574,
    "url": "http://127.0.0.1:8118/api/radar-runtime/modules/latest"
  },
  "/api/radar-runtime/cockpit/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 364,
    "url": "http://127.0.0.1:8118/api/radar-runtime/cockpit/latest"
  }
}
```

## Issues

- No blocking or warning issues found.

## Full JSON

See `p12-radar-runtime-module-score-audit.json`.
