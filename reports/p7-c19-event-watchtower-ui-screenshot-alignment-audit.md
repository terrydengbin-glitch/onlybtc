# P7-C19 Event Watchtower UI Screenshot Alignment Audit

## Status

DONE

## Scope

- Audited Event Watchtower UI alignment after P5-C73/P5-C74.
- No production UI/business code changes were required in this audit task.
- Temporary Vite dev server was started on `127.0.0.1:5199` for screenshots and then stopped.

## Verification

### Frontend Build

```text
cd frontend
npm run build
```

Result:

```text
vue-tsc -b && vite build
✓ built
```

### Backend Event Watchtower Tests

```text
$env:PYTHONPATH='backend/src'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py -q
```

Result:

```text
22 passed, 2 warnings in 194.74s
```

### HTML 1/2/3 Generation

```text
$env:PYTHONPATH='backend/src'
.\.venv\Scripts\python.exe scripts\generate_event_window_source_audit_html.py
.\.venv\Scripts\python.exe scripts\generate_event_window_state_overlay_llm_audit_html.py
.\.venv\Scripts\python.exe scripts\generate_event_window_shock_fast_lane_audit_html.py
```

Generated:

- `reports/event-window-source-audit-report.html`
- `reports/event-window-state-overlay-llm-audit-report.html`
- `reports/event-window-shock-fast-lane-audit-report.html`

## Screenshot Evidence

- `reports/p7-c19-screenshots/event-watchtower-live-cli.png`
- `reports/p7-c19-screenshots/event-watchtower-dev-mock-critical-cli.png`

The Live screenshot confirms:

- Event Watchtower page shell renders inside the existing topbar/left rail framework.
- Status strip is present.
- Main content contains Current Alert, Expectation Drift, Active Event Timeline, Fed Speech / Policy Text, and Timeline stream.
- Right rail is present and starts with Shock Fast Lane and BTC Reaction Check; lower rail cards are present in DOM and full-page capture.
- `direct_score_impact=false` is visible.
- Visibility controls are visible and explicitly local-only.

The dev mock screenshot confirms:

- `CRITICAL MOCK STATE` is visibly labelled `MOCK / audit only`.
- It is enabled only by dev query flag.
- It states that it does not read Event Window payload, write store state, or change BTC/radar scores.

## Static Contract Checks

Confirmed in `frontend/src/App.vue` / `frontend/src/styles.css`:

- Right rail class: `event-live-side`.
- Calendar Mini month grid: `event-calendar-mini-month`.
- Mock overlay gate: `import.meta.env.DEV` plus `?event_mock=critical`.
- Mock overlay suppressed when a real critical overlay is active.
- Real critical overlay copy states Event Window does not directly modify BTC score.
- Event Watchtower visibility controls state that they do not modify Event Window state, SQLite history, BTC score, or radar score.
- Topbar and left rail are still defined as app shell elements; Event Watchtower changes remain scoped under `event-watchtower-page` / `event-*` classes.

## Result

PASS.

No UI contract break was found in this audit.
