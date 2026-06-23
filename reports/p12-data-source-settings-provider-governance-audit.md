# P12-C06 / Data Source / Settings / Provider Governance Audit

- status: `PASS`
- generated_at: `2026-06-23T12:06:45Z`
- schema_version: `p12.c06.data_source_settings_provider_governance_audit.v1`

## Key Evidence

### source_governance_summary

```json
{
  "source_count": 78,
  "enabled_count": 72,
  "fallback_configured_count": 9,
  "freshness_policy_count": 23
}
```

### endpoint_summary

```json
{
  "/api/settings": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 31,
    "url": "http://127.0.0.1:8118/api/settings"
  },
  "/api/settings/runtime": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 15,
    "url": "http://127.0.0.1:8118/api/settings/runtime"
  },
  "/api/settings/data-sources": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 19,
    "url": "http://127.0.0.1:8118/api/settings/data-sources"
  },
  "/api/settings/paths": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 25,
    "url": "http://127.0.0.1:8118/api/settings/paths"
  },
  "/api/settings/providers/health": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 14,
    "url": "http://127.0.0.1:8118/api/settings/providers/health"
  },
  "/api/settings/providers/glassnode/entitlement/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 15,
    "url": "http://127.0.0.1:8118/api/settings/providers/glassnode/entitlement/latest"
  },
  "/api/settings/audit?limit=20": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 16,
    "url": "http://127.0.0.1:8118/api/settings/audit?limit=20"
  }
}
```

## Issues

- No blocking or warning issues found.

## Full JSON

See `p12-data-source-settings-provider-governance-audit.json`.
