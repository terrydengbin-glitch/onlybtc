# P12-C07 / SQLite / API / Report Lineage Release Acceptance Audit

- status: `PARTIAL PASS`
- generated_at: `2026-06-23T12:01:59Z`
- schema_version: `p12.c07.system_release_acceptance.v1`

## Key Evidence

### child_status

```json
{
  "P12-C02": "PASS",
  "P12-C03": "PASS",
  "P12-C04": "PASS",
  "P12-C05": "PASS",
  "P12-C06": "PASS"
}
```

### git

```json
{
  "status_short": "## main...origin/main\n M backend/src/onlybtc/api/app.py\n M backend/tests/test_api_contracts.py\n M frontend/src/App.vue\n M frontend/src/App.vue.js\n M \"task index.md\"\n?? reports/p12-business-chain-contract-audit.json\n?? reports/p12-business-chain-contract-audit.md\n?? reports/p12-dashboard-ui-api-contract-audit.json\n?? reports/p12-dashboard-ui-api-contract-audit.md\n?? reports/p12-data-source-settings-provider-governance-audit.json\n?? reports/p12-data-source-settings-provider-governance-audit.md\n?? reports/p12-event-window-watchtower-audit.html\n?? reports/p12-event-window-watchtower-audit.json\n?? reports/p12-event-window-watchtower-audit.md\n?? reports/p12-radar-runtime-module-score-audit.html\n?? reports/p12-radar-runtime-module-score-audit.json\n?? reports/p12-radar-runtime-module-score-audit.md\n?? reports/p12-system-release-acceptance-report.html\n?? reports/p12-system-release-acceptance-report.json\n?? reports/p12-system-release-acceptance-report.md\n?? scripts/run_p12_system_audit.py\n?? tasks/P12/",
  "head": "ec4b407",
  "branch": "main",
  "remote": "https://github.com/terrydengbin-glitch/onlybtc.git"
}
```

### github_actions_latest

```json
{
  "id": 28020694175,
  "status": "completed",
  "conclusion": "success",
  "html_url": "https://github.com/terrydengbin-glitch/onlybtc/actions/runs/28020694175",
  "head_sha": "ec4b40798fa6aba8f046b79dd1f466019b538b1b"
}
```

### release_gate

```json
{
  "clean_git_required": true,
  "ci_green_required": true,
  "smoke_green_required": true,
  "blocking_child_audits_allowed": false
}
```

## Issues

- `warning` / git: Working tree is not clean because P12 audit artifacts are in progress. Recommendation: Commit P12 artifacts after review if this baseline should be released.

## Full JSON

See `p12-system-release-acceptance-report.json`.
