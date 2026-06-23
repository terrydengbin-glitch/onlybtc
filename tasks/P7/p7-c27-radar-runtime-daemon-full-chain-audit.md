# P7-C27 Radar Runtime Daemon Full Chain Audit

Status: DONE

## Background

Radar Runtime Daemon changes the main chain from synchronized full-chain batches into resident cadence-based updates. This needs strict audit across P1, P3, P4.5, P5, P8, and P9.

## Audit Scope

```text
P1 cadence profile
P8 SQLite snapshots / replay
P9 daemon / scheduler / health API
P3 freshness state machine
P4.5 cockpit fresh snapshot aggregator
P5 runtime health UI
Event Window independence boundary
```

## Checks

1. Daemon starts with FastAPI and stays resident.
2. Heartbeat, watchdog, and health state update correctly.
3. Scheduler refreshes modules by cadence group.
4. Manual Radar Runtime run once performs one full sweep.
5. SQLite latest, API latest, and UI latest share the same runtime snapshot.
6. Stale modules cannot participate in confirmed_signal.
7. Stale confirmation modules downgrade BTC confirmation.
8. Event Window overlay changes only trade permission / radar trust, not radar score.
9. Replay can reconstruct a BTC cockpit runtime snapshot.

## Output

```text
reports/radar-runtime-audit-report.html
reports/radar-runtime-audit-summary.md
```

## DoD

1. Audit report shows runtime_version, snapshot_id, and asof_ts.
2. Audit checks daemon health, scheduler, SQLite, API, and UI contracts.
3. Stale confirmation module scenario blocks confirmed_signal.
4. Fresh fast module plus stale regime module only lowers confidence.
5. Run once produces an audit snapshot consistent with SQLite latest.
6. Audit result is PASS, PARTIAL PASS, or FAIL.
