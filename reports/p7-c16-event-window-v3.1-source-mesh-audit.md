# P7-C16 / Event Window v3.1 Source Mesh Audit

## Result

PARTIAL PASS.

The Event Window source mesh is now live-aware rather than mock-only:

- BEA schedule: live official, parsed 17 items.
- Fed FOMC calendar: live official, parsed 8 items.
- Fed RSS: live official, parsed 12 items.
- Cleveland Fed nowcast: live official-nowcast, parsed 12 values.
- BLS calendar: official endpoint returns 403 in this environment; manual override fallback is active and labeled as `manual_override`, not official live.
- Consensus: intentionally missing; release-surprise calculation is disabled.
- FedWatch: CME unavailable path tested; ZQ futures + FRED EFFR proxy works and is labeled `market_implied_proxy`.

## Latest Live Snapshot

```text
schema_version: p45.event_window.v3
active_event: PCE / Personal Income and Outlays
active_source_tier: official
nowcast: 0.40
source_mode: partial_live
calendar_quality: partial
actual_quality: pending
nowcast_quality: ok
consensus_quality: missing
fedwatch_quality: missing for non-FOMC event
speech_quality: ok
disabled_capabilities: release_surprise_disabled, actual_pending
```

## Verification

```text
ruff event_window/API/db: PASS
pytest event_watchtower + db: PASS, 9 passed
npm run build: PASS
FastAPI health: PASS
/api/event-window/latest: PASS
/api/event-window/sources/status: PASS
/api/event-window/sources/fetches: PASS
```

## Remaining Boundary

- P1-C61 is not fully live-validated because the current active PCE event is pre-release, so actual polling remains `actual_pending`.
- P1-C62 is intentionally partial: BLS official calendar is blocked by 403, and the current fallback is explicit manual override. FRED release dates / CME economic calendar fallback can be added as the next hardening step.
- Consensus remains missing unless a configured commercial provider key is supplied. This is correct behavior; the system must not fake consensus.

