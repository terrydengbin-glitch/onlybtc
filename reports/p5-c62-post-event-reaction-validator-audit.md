# P5-C62 Post Event Reaction Validator Audit

> Status: PASS
> Timestamp: 2026-06-23

## Scope

This audit covers the Event Window post-event BTC reaction validator:

- BTC post-release returns at T+5m, T+30m, and T+2h.
- Reaction state classification: `pending`, `first_impulse`, `absorbed`,
  `followthrough`, `fakeout`, `insufficient_data`.
- Market context fields for realized volatility, OI, funding, basis, CVD proxy,
  and OFI/taker delta proxy.
- UI visibility for whether event lock can be released.

## Contract Evidence

- `build_post_event_reaction` now emits:
  `reaction_state`, `realized_volatility`, `oi_change`, `funding_rate`,
  `basis`, `cvd_proxy`, `ofi_proxy`, `event_lock_release_allowed`, and
  `event_lock_release_reason`.
- Surprise remains gated by `actual_status=available` and non-null consensus.
- Classification is based on BTC post-event behavior:
  absorbed if 30m retraces most of the 5m impulse, followthrough if 5m and
  30m move in the same direction, fakeout if the impulse reverses.
- Naive SQLite timestamps are interpreted as UTC for event-window return
  calculations.
- Frontend `BTC Reaction Check` now displays post-event reaction payload fields
  instead of only market-probe 1h/4h values.

## Verification

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "post_event_reaction or reaction_requires" -q
.\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\event_window\connectors\reactions.py backend\tests\test_event_watchtower.py
npm run build
```

Results:

- P5-C62 focused tests: `4 passed, 18 deselected`
- Compile check: passed
- Frontend production build: passed
