# P1-C62 Event Window BLS Calendar Fallback Mesh Audit

> Status: PASS
> Timestamp: 2026-06-23

## Scope

This audit covers the Event Window v3.1 BLS calendar fallback mesh:

- Official BLS calendar events keep `source_tier=official`.
- BLS access-blocked diagnostics use `provider_failed_access_blocked`.
- FRED release dates remain `source_tier=official_mirror`.
- Manual override events are versioned and labeled as `manual_override`.
- UI can show the active BLS blocked fallback notice.

## Contract Evidence

- BLS disabled/access-denied fetches now report:
  `status=failed`, `error_code=provider_failed_access_blocked`,
  `provider=bls_release_calendar`, `blocked_provider=bls-release-calendar`,
  and `confidence=0.0`.
- FRED mirror events include `provider=fred_bls_release_calendar`,
  `original_authority=BLS`, `calendar_confidence=0.86`,
  `fallback_used=true`, and source lineage showing blocked BLS plus active mirror.
- Manual override events include `override_version`, `updated_at`, and
  `source_note`, plus source lineage showing blocked BLS plus active manual fallback.
- BLS ICS official success events include `provider=bls_release_calendar`,
  `original_authority=BLS`, `calendar_confidence=0.95`, and `fallback_used=false`.
- Frontend summary source note now displays:
  `BLS official blocked, using mirror source ...`,
  `BLS official blocked, using secondary source ...`, or
  `BLS official blocked, using manual override ...` when the active event is a fallback.

## Verification

Commands:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "bls_calendar" -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "actual_provider or reaction_requires or bls_calendar" -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower_offline.py -q
npm run build
```

Results:

- P1-C62 focused tests: `4 passed`
- P1-C61/P1-C62 combined focused tests: `8 passed, 11 deselected`
- Event Watchtower offline regression: `4 passed`
- Frontend production build: passed
