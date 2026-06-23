# P2-C42 Radar Runtime Incremental Module Runner

Status: DONE

## Background

Radar Runtime Daemon needs to refresh radar modules by cadence group. The current P2 audit path expects one full run with all 14 modules, while the runtime path must support scheduled partial runs.

## Goal

Add an incremental module runner contract for P2:

```text
scheduled tick -> due module ids -> analyze selected modules -> persist module snapshots
manual full sweep -> all 14 modules -> persist full runtime snapshot
```

## Rules

1. Scheduled partial runs are valid runtime updates and must not be treated as P2 audit failures.
2. Manual full sweep must still verify 14/14 modules.
3. Every refreshed module must produce a module_snapshot_id.
4. Latest dashboard aggregation must be able to combine snapshots from different module runs.
5. P2 full-chain audit remains available for full deterministic validation.

## DoD

1. P2 runner supports module_ids input and returns module-level payloads.
2. Scheduled partial run records trigger_type=scheduled.
3. Manual full sweep records trigger_type=manual_full_sweep.
4. P2 audit HTML distinguishes scheduled partial from manual full sweep.
5. Downstream P8/P9 can persist and expose module snapshots.
