# P7-C20 Event Watchtower Audit UI And Clear Interaction Audit

## Status

DONE

## Scope

- Audited P5-C75 Audit tab mapping and P5-C76 visibility controls.
- No production UI/business code changes were required in this audit task.
- The attempted browser interaction proof was not retained because Playwright runner did not discover the temporary spec in this workspace; the final audit uses deterministic build/test/html generation plus source-level contract checks.

## Reused Verification From Same Audit Session

P7-C19 was executed immediately before this task in the same session, after P5-C75/P5-C76 were complete.

Verified:

- `cd frontend && npm run build` passed.
- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py -q` passed: `22 passed`.
- HTML 1/2/3 generated:
  - `reports/event-window-source-audit-report.html`
  - `reports/event-window-state-overlay-llm-audit-report.html`
  - `reports/event-window-shock-fast-lane-audit-report.html`

## UI Audit Mapping

Confirmed in `frontend/src/App.vue`:

- `Source Chain Audit`
  - source mode counts
  - source quality
  - provider confidence
  - provider tiers
  - fetch lineage rows
  - HTML 1 entry button
- `State / Overlay / LLM Audit`
  - event window state
  - state priority
  - emergency level
  - reason codes
  - valid until
  - trade permission modifier
  - confidence cap
  - ordinary radar trust
  - `direct_score_impact=false`
  - forbidden keys pass/fail
  - LLM provider/status/tone/confidence/relevance/speaker/boundary/violations
  - HTML 2 entry button
- `Shock Fast Lane Audit`
  - shock detected/type/confirmation/source count
  - market dislocation
  - BTC microstructure confirmation
  - rumor risk
  - event window impact
  - boundary checks
  - synthetic regression status
  - LLM Chinese explanation
  - HTML 3 entry button

## LLM Boundary

Confirmed UI copy:

- LLM only classifies tone, relevance, and confidence.
- LLM does not output BTC bullish/bearish.
- LLM does not modify `emergency_level`.
- LLM does not modify `trade_permission_modifier`.
- Chinese shock explanation is presented as explanation/attribution, not trading direction.

## Ack / Dismiss / Clear Boundary

Confirmed handlers:

- `ackCurrentEventAlert`
  - writes only `onlybtc:event-window:ack:v1` in `localStorage`
  - does not call `store`, `fetch`, backend API, or SQLite
- `hideCurrentEventAlertForSession`
  - writes only `onlybtc:event-window:hidden:v1` in `sessionStorage`
  - does not call `store`, `fetch`, backend API, or SQLite
- `dismissEventFloatingAlertSession`
  - delegates to session hidden state only
- `clearVisibleNonCriticalEventAlerts`
  - blocks critical/event-lock states
  - delegates to session hidden state only
- `restoreEventWindowHiddenAlerts`
  - clears browser storage visibility state only

The visibility key includes:

- `snapshot_id`
- `valid_until`
- `event_window_state`
- `emergency_level`

Critical dismiss additionally includes `trade_permission_modifier`.

## SQLite / History / Replay Safety

The Clear/Ack/Dismiss handlers contain no backend mutation path. They do not call:

- backend alert ack/mute APIs
- destructive API endpoints
- SQLite repository methods
- history/replay deletion paths

Important audit note:

- Opening Event Watchtower can naturally trigger `refreshEventWindowLatest`, which may persist new daemon/live rows.
- Therefore page-load before/after SQLite counts are not a valid proof for Clear behavior unless live refresh is fully disabled.
- The relevant Clear behavior is source-level local-only visibility, which is confirmed.

## Result

PASS.

No audit HTML mapping or visibility-control contract break was found.
