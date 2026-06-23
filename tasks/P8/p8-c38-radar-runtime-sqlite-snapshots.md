# P8-C38 Radar Runtime SQLite Snapshots and Replay

Status: DONE

## Background

Radar Runtime needs durable module-level snapshots, not only one final full-chain payload. Module refresh results, freshness state, failures, and participation policy must be stored for UI, replay, and audit.

## Goal

Add SQLite support for:

```text
radar_runtime_snapshots
radar_module_snapshots
radar_metric_snapshots
radar_runtime_scheduler_state
```

## Minimum Fields

```text
runtime_snapshot_id
module_snapshot_id
module_name
cadence_group
trigger_type: scheduled|manual_full_sweep|retry|startup
asof_ts
collected_at
last_success_at
ttl_sec
age_sec
freshness_state
participation_policy
payload_json
source_lineage_json
error_json
```

## Replay Requirements

1. Query the latest 14 module snapshots as of a timestamp.
2. Query historical refresh sequence by module_name.
3. Rebuild a BTC cockpit runtime snapshot for a past timestamp.
4. Distinguish scheduled tick from manual full sweep.

## DoD

1. Every module refresh writes a complete snapshot.
2. Every cockpit runtime aggregation writes a complete payload.
3. SQLite latest and API latest point to the same snapshot.
4. Replay can reproduce freshness state and participation policy.
5. Failed module runs are stored and not silently dropped.
6. Event Window independent SQLite / timeline is not overwritten.
