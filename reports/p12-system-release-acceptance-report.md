# P12-C07 / SQLite / API / Report Lineage Release Acceptance Audit

- status: `PASS`
- generated_at: `2026-06-23T12:06:45Z`
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
  "status_short": "## main...origin/main",
  "head": "9470f81",
  "branch": "main",
  "remote": "https://github.com/terrydengbin-glitch/onlybtc.git"
}
```

### github_actions_latest

```json
{
  "id": 28024843275,
  "status": "completed",
  "conclusion": "success",
  "html_url": "https://github.com/terrydengbin-glitch/onlybtc/actions/runs/28024843275",
  "head_sha": "9470f8147c1c35df53f32c89da75b50e0ea41130"
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

- No blocking or warning issues found.

## Full JSON

See `p12-system-release-acceptance-report.json`.
