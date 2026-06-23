# P1-C61 Event Window BLS Actual Provider Audit

> Status: PASS
> Timestamp: 2026-06-23

## Scope

This audit covers the P1-C61 contract for Event Window v3.1 actual polling:

- BLS Public Data API is the official actual provider.
- FRED fredgraph CSV is an official mirror fallback.
- Stale historical observations must not be promoted as the current release actual.
- Post-event surprise can only be calculated when `actual_status=available`.

## Contract Evidence

- `collect_actual_snapshot` now projects top-level actual contract fields:
  `provider`, `source_tier`, `metric_group`, `latest_observation`,
  `previous_observation`, `observation_date`, `release_ts`,
  `actual_status`, `fallback_used`, and `source_lineage`.
- Source lineage includes `provider`, `source_tier`, `fallback_used`,
  `confidence`, and `blocked_provider` for failed BLS paths.
- CPI/NFP/PPI observations are accepted only when the latest observation
  is at least the prior release month. JOLTS uses a two-month lag.
- Older BLS/FRED observations are reported as `actual_not_released` and keep
  the snapshot in `not_released`.
- `build_post_event_reaction` ignores observations unless
  `actual_status == "available"`.

## Verification

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "actual_provider or reaction_requires" -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower_offline.py -q
.\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\event_window\connectors\actuals.py backend\src\onlybtc\event_window\connectors\reactions.py backend\tests\test_event_watchtower.py
```

Results:

- P1-C61 focused tests: `4 passed, 11 deselected`
- Event Watchtower offline regression: `4 passed`
- Compile check: passed

Note: full `backend\tests\test_event_watchtower.py` was not used as the
completion gate because existing live connector tests can block on external
providers. The P1-C61 deterministic provider/reaction contract is covered by
mocked provider responses.
