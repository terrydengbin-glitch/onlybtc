# P5-C74 Event Watchtower Critical Overlay Audit

## Status

DONE

## Scope

- Updated only Event Watchtower critical overlay helpers/template and `event-critical-*` styles.
- No backend state machine, API payload, BTC score, radar score, or unrelated modal behavior changed.

## Implementation

- Real critical overlay remains driven only by live payload:
  - `eventWindowState.emergency_level === critical`
  - or `eventWindowOverlay.trade_permission_modifier in [event_lock, avoid_new_position]`
- High state remains excluded from the critical overlay path and continues to use the floating alert path.
- Session dismiss remains frontend-only through `dismissedCriticalAlertKey`.
- Dismiss key includes `snapshot_id`, `valid_until`, `emergency_level`, and `trade_permission_modifier`, so new snapshots or validity changes invalidate the dismiss.
- Real overlay now displays:
  - event title
  - emergency level
  - event window state
  - trade permission modifier
  - ordinary radar trust
  - valid until
  - direct score impact
  - snapshot id
  - reason codes
  - Open Watchtower and Dismiss session actions
- Mock overlay is isolated behind local dev query flag:
  - `import.meta.env.DEV`
  - `?event_mock=critical`
  - suppressed when a real critical overlay is active
  - marked `MOCK / audit only`
  - does not read Event Window payload and does not write store/API/SQLite.

## Verification

```text
cd frontend
npm run build
```

Result:

```text
vue-tsc -b && vite build
✓ built
```

## Risk Notes

- Mock overlay is unavailable in production builds because it is gated by `import.meta.env.DEV`.
- Real overlay still uses existing live state semantics; this task did not alter emergency classification.
