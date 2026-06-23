# P7-C05 Playwright Stability Report

- schema_version: `p7.c05.playwright_stability.v1`
- generated_at: `2026-06-22T23:39:54.232740+00:00`
- applied_to_production: `False`
- overall_status: `warning`
- alert_count: `2`
- playwright_source_count: `16`
- provider_count: `1`

## Artifact Policy

- playwright_artifacts_ignored: `True`
- auth_dir: `E:\onlyBTC\playwright-artifacts\auth`
- storage_state_reported_as_path_only: `True`

## Guardrails

- audit_only
- does_not_open_browser
- does_not_collect_sources
- does_not_store_secrets_in_report
- does_not_modify_state_machine
- does_not_emit_trading_advice
- requires_p7_c08_before_production_apply

## Alerts

| level | scope | alert_id | reason | action |
|---|---|---|---|---|
| warning | provider_auth | provider_auth_not_verified | glassnode: status not found | degrade_provider_to_health_warning_until_verified |
| warning | source_health | playwright_recent_health_warnings | fxstreet-economic-calendar | inspect_artifacts_selectors_or_provider_auth |

## Provider Auth

| provider | configured | verified | sensitive_fields | message |
|---|---:|---:|---:|---|
| glassnode | False | False | False | status not found |

## Playwright Sources

| source | group | method | fallback | profile_required |
|---|---|---|---|---:|
| bitbo-sth-lth-realized-price | onchain_valuation | playwright_persistent_chart_export | - | True |
| fxstreet-economic-calendar | event_policy | playwright_calendar | - | False |
| playwright-glassnode-asset-overview | fund_flow | playwright_network | - | True |
| playwright-glassnode-sopr | onchain_valuation | playwright_network | - | True |
| playwright-tradingview-brent-oil | macro | playwright | fred-brent-oil | False |
| playwright-tradingview-dow-jones | macro | playwright | fred-dow-jones | False |
| playwright-tradingview-dxy | macro | playwright | fred-dxy | False |
| playwright-tradingview-gold | macro | playwright | - | False |
| playwright-tradingview-hang-seng-tech | asia_risk | playwright | - | False |
| playwright-tradingview-jgb-10y | asia_risk | playwright | fred-jgb-10y | False |
| playwright-tradingview-russell-2000 | macro | playwright | - | False |
| playwright-tradingview-sp500 | macro | playwright | fred-sp500 | False |
| playwright-tradingview-topix | asia_risk | playwright | - | False |
| playwright-tradingview-usdcnh | asia_risk | playwright | fred-usdcnh-proxy | False |
| playwright-tradingview-usdjpy | asia_risk | playwright | fred-usdjpy | False |
| playwright-tradingview-wti-oil | macro | playwright | fred-wti-oil | False |

## Recent Health Events

| source | status | category | quality | message |
|---|---|---|---:|---|
| playwright-tradingview-hang-seng-tech | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=2.654 |
| playwright-tradingview-topix | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=7.234 |
| playwright-tradingview-usdcnh | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=11.994 |
| playwright-tradingview-usdjpy | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=16.537 |
| playwright-tradingview-jgb-10y | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=21.131 |
| playwright-glassnode-sopr | healthy | unknown | 0.76 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=expected_lag business_age_seconds=171466.123 |
| playwright-glassnode-asset-overview | healthy | unknown | 0.7 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=expected_lag business_age_seconds=171465.612 |
| playwright-tradingview-hang-seng-tech | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=26.066 |
| playwright-tradingview-topix | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=30.616 |
| playwright-tradingview-usdcnh | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=35.184 |
| playwright-tradingview-usdjpy | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=39.372 |
| playwright-tradingview-jgb-10y | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=44.037 |
| playwright-tradingview-brent-oil | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=48.67 |
| playwright-tradingview-wti-oil | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=55.06 |
| playwright-tradingview-gold | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=59.956 |
| playwright-tradingview-russell-2000 | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=64.882 |
| playwright-tradingview-dow-jones | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=69.673 |
| playwright-tradingview-sp500 | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=75.0 |
| playwright-tradingview-dxy | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=80.532 |
| bitbo-sth-lth-realized-price | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=85064.779 |
| fxstreet-economic-calendar | warning | unknown | 0.6699999999999999 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=103.914 |
| playwright-tradingview-hang-seng-tech | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=3.564 |
| playwright-tradingview-topix | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=8.619 |
| playwright-tradingview-usdcnh | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=13.878 |
| playwright-tradingview-usdjpy | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=19.421 |
| playwright-tradingview-jgb-10y | healthy | unknown | 0.72 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=24.058 |
| playwright-tradingview-brent-oil | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=28.688 |
| playwright-tradingview-wti-oil | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=33.721 |
| playwright-tradingview-gold | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=38.707 |
| playwright-tradingview-russell-2000 | healthy | unknown | 0.78 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=43.747 |

## Notes

- This report is audit-only and does not open Playwright.
- Storage state content is never embedded in the report.
- Unverified provider auth degrades to warning rather than blocking global collection.
