# P7-C17 Event Window v3.2 Provider Mesh Audit

## Verdict

PASS.

## Live Source Result

- FRED release dates fallback: PASS. BLS calendar returned 403, then `fred-release-dates` returned `official_mirror / fallback_used` with 26 parsed BLS release dates.
- Secondary calendar mesh: PARTIAL PASS. FXStreet is reachable but did not match the active PCE item in current payload; Myfxbook, ForexFactory and Investing returned 403 and are recorded as failed fetches. Consensus remains `missing`, so release surprise is disabled.
- Prediction market connector: PASS with liquidity downgrade. Kalshi returned 51 PCE markets; Polymarket returned no matching active PCE markets. Snapshot is `available_low_liquidity`, not treated as official.
- Atlanta Fed MPT: PASS. Page is reachable and recorded as `fed_research_tool`; no probability rows parsed in this run.
- Provider confidence resolver: PASS. Payload now includes separate calendar, consensus, nowcast, actual, rate odds and prediction confidence.
- Provider mesh UI: PASS. Event subpage now displays provider confidence and tier counts without changing the daemon or radar pages.

## Current Payload Snapshot

```text
schema_version: p45.event_window.v3
active_event: PCE / Personal Income and Outlays
event_state: pre_event_high_alert
emergency_level: high
calendar_confidence: 0.95
consensus_confidence: 0.0
nowcast_confidence: 0.9
prediction_market_confidence: 0.45
lineage_mode: official_mirror_partial_live
```

## Test Evidence

```text
ruff: PASS
pytest backend/tests/test_event_watchtower.py backend/tests/test_db.py: 9 passed
npm run build: PASS
live payload audit: PASS
```

## Residual Risk

- Consensus remains missing unless a secondary provider can be parsed or an API key is configured.
- Prediction market odds are currently useful for watch-level risk only because active PCE markets have weak/unknown liquidity fields.
- Atlanta Fed MPT is treated as a research-tool source, not as CME FedWatch replacement.
