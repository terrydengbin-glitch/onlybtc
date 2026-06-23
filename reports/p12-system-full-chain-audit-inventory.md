# P12-C01 / System Full-chain Audit Inventory

- status: `PASS`
- generated_at: `2026-06-23T12:17:11Z`
- schema_version: `p12.c01.system_full_chain_audit_inventory.v1`

## Scope

P12 covers the full onlyBTC chain:

`source collect -> source health/freshness -> radar modules -> P3/P4.5 decision -> evidence/report -> API -> Dashboard UI`

Evidence is separated by scope:

- Frozen final lineage: `final_run_id`, `pack_id`, `collect_run_id`, `p2_radar_run_id`, `p3_run_id`.
- Live runtime freshness: `radar-runtime-* snapshot_id`, runtime/source freshness, daemon heartbeat.
- Static acceptance reports: `reports/p12-*.json/md/html`.
- Mutable latest artifacts: runtime latest reports and active daemon state.

## Task Matrix

| Task | Status | Output |
|---|---|---|
| P12-C02 Business Chain Contract Audit | PASS | `reports/p12-business-chain-contract-audit.json` |
| P12-C03 Dashboard / P45 UI-API Contract Audit | PASS | `reports/p12-dashboard-ui-api-contract-audit.json` |
| P12-C04 Radar Runtime / Module Score Full-chain Audit | PASS | `reports/p12-radar-runtime-module-score-audit.json/html` |
| P12-C05 Event Window / Event Watchtower Full-chain Audit | PASS | `reports/p12-event-window-watchtower-audit.json/html` |
| P12-C06 Data Source / Settings / Provider Governance Audit | PASS | `reports/p12-data-source-settings-provider-governance-audit.json` |
| P12-C07 SQLite / API / Report Lineage Release Acceptance Audit | PASS | `reports/p12-system-release-acceptance-report.json/html` |
| P12-C08 Frozen Final vs Live Runtime UI Label Hardening | DONE | `frontend/src/App.vue` |
| P12-C09 Source Action Endpoint Contract Completion | DONE | `backend/src/onlybtc/api/app.py` |
| P12-C10 Audit Artifact Release Commit and CI Rerun | DONE | GitHub Actions `28025025354` |

## Key Evidence

- Dashboard/UI-API: `55` frontend endpoints, `124` backend routes, source action gaps empty.
- Radar: 14 modules, daemon healthy, runtime/source freshness true, SQLite lock ok.
- Event Window: daemon healthy; calendar 30, timeline 100, alerts 30, sources 43, fetches 40.
- Data sources: 78 sources, 72 enabled, 9 fallbacks, 23 freshness policies, secret hygiene pass.
- Release: P12-C02 through P12-C06 all pass; C07 release acceptance pass.

## Release Evidence

- latest release record commit: `c506afc`
- GitHub Actions run: `28025025354`
- GitHub Actions conclusion: `success`
- URL: `https://github.com/terrydengbin-glitch/onlybtc/actions/runs/28025025354`

## Open Items

No P12 blocking or warning issue remains after P12-C10.
