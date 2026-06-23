# P12-C02 / Business Chain Contract Audit

- status: `PASS`
- generated_at: `2026-06-23T12:06:45Z`
- schema_version: `p12.c02.business_chain_contract_audit.v1`

## Key Evidence

### latest_lineage

```json
{
  "collect_run_id": "collect-20260622100457-1049fd",
  "p2_radar_run_id": "radar-20260622101102-f56d18",
  "p3_run_id": "p3-20260622101113-db9013",
  "pack_id": "p45pack-20260622101158-0555d2",
  "article_run_id": "p45articles-20260622101158-4e94a6",
  "final_run_id": "p45final-p8-replay-verify-202606221611",
  "llm_research_run_id": null,
  "llm_analyst_run_id": "p45llmanalysts-20260622101315-8deade",
  "created_at": "2026-06-22T16:05:03.386525+00:00",
  "runtime_mode": "deterministic"
}
```

### endpoint_summary

```json
{
  "/api/health": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 45,
    "url": "http://127.0.0.1:8118/api/health"
  },
  "/api/db/health": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 320,
    "url": "http://127.0.0.1:8118/api/db/health"
  },
  "/api/p45/dashboard/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 1616,
    "url": "http://127.0.0.1:8118/api/p45/dashboard/latest"
  },
  "/api/p45/overview/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 1259,
    "url": "http://127.0.0.1:8118/api/p45/overview/latest"
  },
  "/api/p45/radar-modules/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 1538,
    "url": "http://127.0.0.1:8118/api/p45/radar-modules/latest"
  },
  "/api/p45/evidence?limit=40": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 741,
    "url": "http://127.0.0.1:8118/api/p45/evidence?limit=40"
  },
  "/api/p45/articles/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 762,
    "url": "http://127.0.0.1:8118/api/p45/articles/latest"
  },
  "/api/p45/llm/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 23,
    "url": "http://127.0.0.1:8118/api/p45/llm/latest"
  },
  "/api/p45/analysts/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 812,
    "url": "http://127.0.0.1:8118/api/p45/analysts/latest"
  },
  "/api/p45/invalidation/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 855,
    "url": "http://127.0.0.1:8118/api/p45/invalidation/latest"
  },
  "/api/data-quality/latest": {
    "ok": false,
    "status_code": null,
    "elapsed_ms": 8048,
    "url": "http://127.0.0.1:8118/api/data-quality/latest",
    "error": "timed out"
  },
  "/api/p45/runs/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 2924,
    "url": "http://127.0.0.1:8118/api/p45/runs/latest"
  },
  "/api/p45/audit-reports/latest": {
    "ok": true,
    "status_code": 200,
    "elapsed_ms": 29,
    "url": "http://127.0.0.1:8118/api/p45/audit-reports/latest"
  }
}
```

## Issues

- `info` / freshness: P4.5 final lineage and live radar runtime snapshot may be from different runtime moments. Recommendation: Surface final-run frozen lineage separately from live runtime freshness.

## Full JSON

See `p12-business-chain-contract-audit.json`.
