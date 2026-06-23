# Glassnode Provider Entitlement Report

- schema_version: `p10.c08.glassnode_entitlement.v1`
- generated_at: `2026-06-23T09:19:25.307368+00:00`
- provider_id: `glassnode`
- mode: `dry_run`
- applied_to_production: `False`
- overall_status: `provider_locked`
- configured: `False`
- available_count: `0`
- locked_count: `7`

## Guardrails

- audit_only_no_metric_write
- do_not_fabricate_provider_locked_metrics
- do_not_persist_api_key_or_session_cookie
- unauthorized_rate_limited_schema_changed_are_non_fatal

## Entitlements

| metric | status | http | quality | locked_reason | endpoint |
|---|---|---:|---:|---|---|
| realized_price | missing_key |  |  | ONLYBTC_GLASSNODE_API_KEY is not configured. | `/v1/metrics/market/price_realized_usd` |
| sth_cost_basis | missing_key |  |  | ONLYBTC_GLASSNODE_API_KEY is not configured. | `/v1/metrics/indicators/realized_price_short_term_holders` |
| lth_cost_basis | missing_key |  |  | ONLYBTC_GLASSNODE_API_KEY is not configured. | `/v1/metrics/indicators/realized_price_long_term_holders` |
| whale_flow | missing_key |  |  | ONLYBTC_GLASSNODE_API_KEY is not configured. | `/v1/metrics/transactions/transfers_volume_to_exchanges_mean` |
| miner_flow | missing_key |  |  | ONLYBTC_GLASSNODE_API_KEY is not configured. | `/v1/metrics/mining/miners_outflow_volume_sum` |
| stablecoin_exchange_inflow | missing_key |  |  | ONLYBTC_GLASSNODE_API_KEY is not configured. | `/v1/metrics/transactions/stablecoin_transfers_volume_to_exchanges_sum` |
| exchange_netflow | missing_key |  |  | ONLYBTC_GLASSNODE_API_KEY is not configured. | `/v1/metrics/transactions/transfers_volume_exchanges_net` |

## Production Write Candidates

- none

## Notes

- This report is audit-only and does not write metrics.
- Available metrics still require source lineage, freshness, and quality review before production use.
