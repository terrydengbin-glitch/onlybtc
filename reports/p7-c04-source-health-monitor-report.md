# P7-C04 Source Health Monitor Report

- schema_version: `p7.c04.source_health_monitor.v1`
- generated_at: `2026-06-22T23:39:44.195779+00:00`
- applied_to_production: `False`
- overall_status: `watch`
- alert_count: `4`
- data_quality_run_id: `radar-runtime-source-20260622233822-b259b3`
- data_quality_score: `0.9037`
- data_quality_status: `healthy`

## Downstream Policy

- dashboard_badge: `data_quality_watch`
- participation_policy: `context_only_for_affected_sources`
- publish_gate_recommendation: `surface_warning_without_auto_block`

## Guardrails

- monitoring_only
- does_not_collect_sources
- does_not_modify_source_registry
- does_not_modify_state_machine
- does_not_emit_trading_advice
- requires_p7_c08_before_production_apply

## Alerts

| level | scope | alert_id | reason | action |
|---|---|---|---|---|
| watch | freshness | source_freshness_stale | stale=1 | lower_sensitivity_for_affected_modules |
| watch | fallback | fallback_sources_active | fallback_event_count=105 | surface_fallback_reason_in_dashboard_and_audit |
| watch | registry | source_registry_drift | archived_source_count=1 | review_removed_sources_before_new_provider_rollout |
| watch | source_health_events | recent_source_health_events | sources=binance-btcusdt-open-interest,binance-usdm-force-order-btcusdt,bybit-v5-all-liquidation-btcusdt,deribit-btc-options,fxstreet-economic-calendar,mempool-lightning-network-stats | inspect_recent_source_health_events |

## Data Quality Summary

- source_count: `72`
- freshness_counts: `{"fresh": 71, "stale": 1, "expired": 0, "missing": 0}`
- business_recency_counts: `{"current": 72, "expected_lag": 0, "lagging": 0, "outdated": 0, "provider_stale_suspect": 0, "unknown": 0}`
- stale_sources: `["binance-btcusdt-kline-1h"]`
- business_lagging_sources: `[]`
- missing_sources: `[]`
- fallback_summary: `{"fallback_event_count": 105, "warning_source_count": 6, "http_403_sources": [], "warning_sources": ["binance-btcusdt-open-interest", "binance-usdm-force-order-btcusdt", "bybit-v5-all-liquidation-btcusdt", "deribit-btc-options", "fxstreet-economic-calendar", "mempool-lightning-network-stats"]}`
- run_mode_summary: `{"live_metric_values": 652745, "mock_metric_values": 32719, "test_metric_values": 0, "unknown_metric_values": 0, "mixed_metric_count": 596, "mixed_metric_examples": ["active_addresses", "active_entities_or_addresses_change_7d_pct", "active_entities_or_addresses_z_30d", "active_entities_or_addresses_z_60d", "activity_spike_flag", "adoption_btc_return_24h", "adoption_btc_return_3d", "adoption_btc_return_4h", "adoption_btc_return_7d", "adoption_expected_return_24h"], "production_blocker": false}`

## Recent Source Events

| source | status | quality | latency_ms | message |
|---|---|---:|---:|---|
| playwright-tradingview-hang-seng-tech | healthy | 0.72 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=2.654 |
| playwright-tradingview-topix | healthy | 0.72 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=7.234 |
| playwright-tradingview-usdcnh | healthy | 0.78 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=11.994 |
| playwright-tradingview-usdjpy | healthy | 0.78 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=16.537 |
| playwright-tradingview-jgb-10y | healthy | 0.72 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=21.131 |
| bybit-v5-all-liquidation-btcusdt | warning | 0.56 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=19.797 |
| binance-usdm-force-order-btcusdt | warning | 0.56 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=11.448 |
| binance-btcusdt-taker-buy-sell-ratio | healthy | 0.96 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=544.326 |
| binance-btcusdt-top-long-short-position-ratio | healthy | 0.72 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=244.322 |
| binance-btcusdt-top-long-short-account-ratio | healthy | 0.88 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=244.319 |
| binance-btcusdt-global-long-short-account-ratio | healthy | 0.82 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=244.315 |
| binance-btcusdt-open-interest | warning | 0.6 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=36.079 |
| binance-btcusdt-funding | healthy | 0.7 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=29.057 |
| binance-btcusdt-kline-15m | healthy | 0.96 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=900.0 business_recency=current business_age_seconds=544.266 |
| binance-btcusdt-kline-5m | healthy | 0.96 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=300.0 business_recency=current business_age_seconds=244.233 |
| binance-btcusdt-kline-1h | healthy | 0.96 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=2343.05 |
| binance-btcusdt | healthy | 0.96 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=28.622 |
| fred-jgb-10y | healthy | 0.95 | 10726 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=2592000.0 business_recency=expected_lag business_age_seconds=4577942.497 |
| fred-nikkei | healthy | 0.95 | 3119 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=86400.0 business_recency=current business_age_seconds=85142.396 |
| fred-usdcnh-proxy | healthy | 0.95 | 2646 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=86400.0 business_recency=expected_lag business_age_seconds=430742.305 |
| fred-usdjpy | healthy | 0.95 | 11865 | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=86400.0 business_recency=expected_lag business_age_seconds=430742.199 |
| playwright-glassnode-sopr | healthy | 0.76 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=expected_lag business_age_seconds=171466.123 |
| playwright-glassnode-asset-overview | healthy | 0.7 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=expected_lag business_age_seconds=171465.612 |
| playwright-tradingview-hang-seng-tech | healthy | 0.72 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=26.066 |
| playwright-tradingview-topix | healthy | 0.72 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=3600.0 business_recency=current business_age_seconds=30.616 |
| playwright-tradingview-usdcnh | healthy | 0.78 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=35.184 |
| playwright-tradingview-usdjpy | healthy | 0.78 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=39.372 |
| playwright-tradingview-jgb-10y | healthy | 0.72 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=44.037 |
| playwright-tradingview-brent-oil | healthy | 0.78 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=48.67 |
| playwright-tradingview-wti-oil | healthy | 0.78 | None | collection_freshness=fresh collection_age_seconds=0.0 expected_seconds=600.0 business_recency=current business_age_seconds=55.06 |

## Notes

- This report is monitoring-only.
- It does not collect sources or modify source registry state.
- It does not emit trading advice or bypass state machine gates.
