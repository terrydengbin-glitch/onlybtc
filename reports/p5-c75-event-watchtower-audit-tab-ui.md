# P5-C75 Event Watchtower Audit Tab UI

## Status

DONE

## Scope

- Added an `Audit` tab to the Event Watchtower page.
- Updated only `frontend/src/App.vue` Event Watchtower UI/computed helpers and dedicated `event-*` styles.
- Did not modify audit HTML generators, backend state machine, BTC score, radar score, or other pages.

## Implementation

- Added audit data helpers:
  - `eventWindowAuditBundleReports`
  - `eventWindowAuditFileMeta`
  - `eventWindowAuditRegression`
  - `eventWindowOverlayForbiddenKeys`
  - `eventWindowLlmViolations`
  - `eventWindowAuditReportLinks`
- Added `Audit` tab with three cards:
  - `Source Chain Audit`
  - `State / Overlay / LLM Audit`
  - `Shock Fast Lane Audit`
- Added report buttons for:
  - `reports/event-window-source-audit-report.html`
  - `reports/event-window-state-overlay-llm-audit-report.html`
  - `reports/event-window-shock-fast-lane-audit-report.html`
- Source Chain card maps:
  - source mode counts
  - source quality
  - provider confidence
  - provider tiers
  - recent fetch lineage from `eventWindowSourceFetches`
  - secondary/proxy/FedWatch boundary note
- State / Overlay / LLM card maps:
  - state priority, emergency level, reason codes, valid until
  - trade permission modifier, confidence cap, volatility warning, radar trust
  - `direct_score_impact=false`
  - forbidden keys pass/fail
  - Fed speech LLM provider/status/tone/confidence/relevance/speaker/boundary/violations
- Shock Fast Lane card maps:
  - shock detected/type/confirmation/source count
  - market dislocation, BTC microstructure, rumor risk
  - event window overlay and `direct_score_impact=false`
  - regression status from audit bundle
  - boundary checks and LLM Chinese shock explanation

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

## Notes

- The UI does not scrape or statically copy the HTML files.
- Metrics are rendered from Event Window store/API/audit bundle data.
- The HTML files are exposed through report entry buttons for drilldown.
