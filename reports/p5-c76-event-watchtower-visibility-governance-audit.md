# P5-C76 Event Watchtower Visibility Governance Audit

## Status

DONE

## Scope

- Updated only Event Watchtower frontend visibility behavior and dedicated styles.
- Did not call backend alert ack/mute APIs.
- Did not delete or mutate SQLite history, replay data, Event Window state, BTC score, or radar score.

## Implementation

- Added local/session visibility storage:
  - `onlybtc:event-window:ack:v1` in `localStorage`
  - `onlybtc:event-window:hidden:v1` in `sessionStorage`
  - `onlybtc:event-window:critical-dismiss:v1` in `sessionStorage`
- Visibility key includes:
  - `snapshot_id`
  - `valid_until`
  - `event_window_state`
  - `emergency_level`
- Critical overlay dismiss key also includes `trade_permission_modifier`.
- Added Event Watchtower visibility controls:
  - `Ack current alert`
  - `Dismiss session`
  - `Show hidden / restore`
  - `Clear visible`
- Added explicit boundary copy:
  - Visibility controls do not modify Event Window state, SQLite history, BTC score, or radar score.
- Floating alert:
  - can be dismissed for the current session by visibility key.
  - automatically returns when snapshot/state/validity/emergency changes.
- Current Alert:
  - ack marks it as read without hiding it.
  - hidden state shows a local-only placeholder while keeping status strip, right rail, dashboard summary, and audit state visible.
- Critical overlay:
  - session dismiss is persisted in `sessionStorage`.
  - page state remains visible after dismiss.
  - new snapshot/validity/state/emergency/permission changes invalidate the dismiss key.
- Clear visible:
  - disabled for critical/event-lock states.
  - only hides the current non-critical alert in frontend session state.

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

- Ack is intentionally local UI state, not a backend event resolution.
- Clear visible does not affect Event Window timeline, history, replay, source fetches, or SQLite rows.
