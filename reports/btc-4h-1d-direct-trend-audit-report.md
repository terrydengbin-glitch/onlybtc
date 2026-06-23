# BTC 4H/1D Direct Trend Full Chain Audit
- status: PASS
- generated_at: 2026-06-22T19:11:17.104383+00:00
- final_run_id: p45final-p8-replay-verify-202606221611
- dashboard_snapshot_id: p3c62-state-20260622155135-9d8cba
- sqlite_snapshot_id: p3c62-state-20260622155135-9d8cba
- cockpit_snapshot_id: p3c62-state-20260622155135-9d8cba

## Core Checks
- PASS `p45-schema-v22`: "p45.btc_timescale_judge.v2.2"
- PASS `p3-state-machine-present`: "p3c62-state-20260622155135-9d8cba"
- PASS `4h-1d-direct-evidence-present`: {"4h": true, "1d": true}
- PASS `scores-exposed`: "direction / acceptance / trust / display"
- PASS `event-overlay-trust-only`: "event_overlay_context roles are trust/quality gates; event_trust policy is trust cap"
- PASS `radar-context-not-direct-score`: "radar_context policy confirm_conflict_degrade_only / legacy_context"
- PASS `sqlite-api-snapshot-consistency`: {"dashboard": "p3c62-state-20260622155135-9d8cba", "sqlite_replay": "p3c62-state-20260622155135-9d8cba", "p8_payload": "p3c62-state-20260622155135-9d8cba", "cockpit": "p3c62-state-20260622155135-9d8cba"}
- PASS `api-freshness-explicit`: {"source_fresh": true, "runtime_fresh": true, "fallback_used": false}
- PASS `ui-static-contract`: {"vue-reads-v22-timescale-judge": "PASS", "vue-renders-direct-chain": "PASS", "vue-renders-event-phase": "PASS", "vue-shows-freshness-fallback": "PASS"}
- PASS `lineage-matrix-no-fail-gaps`: {"pass": 27}

## Evaluation
- status: PASS
- sample_count: 72
- reason: sufficient snapshots available for evaluation runner

## v2.1 vs v2.2
- baseline: btc_timescale_judge.v2.1 module average / horizon_views
- candidate: btc_timescale_judge.v2.2 direct evidence + radar context
- conclusion: v2.2 separates direct direction evidence, BTC acceptance, trust caps, and radar context; module average is retained only as context/fallback.

## Lineage Matrix
| metric_id | source_id | horizon | role | freshness | gap_status |
|---|---|---|---|---|---|
| btc_direct_trend.price_structure.btc_return_4h | binance-btcusdt-kline-1h | 4h | trigger_eligible | fresh | pass |
| btc_direct_trend.price_structure.btc_return_24h | binance-btcusdt-kline-1h | 1d | trigger_eligible | fresh | pass |
| btc_direct_trend.orderflow_acceptance.taker_buy_sell_ratio | binance-btcusdt-taker-buy-sell-ratio | 4h | acceptance_gate | fresh | pass |
| btc_direct_trend.orderflow_acceptance.taker_delta_quote | binance-btcusdt,binance-btcusdt-taker-buy-sell-ratio | 4h | acceptance_gate | fresh | pass |
| btc_direct_trend.orderflow_acceptance.cvd_slope_z | binance-btcusdt,binance-btcusdt-taker-buy-sell-ratio | 4h | acceptance_gate | fresh | pass |
| btc_direct_trend.derivatives_positioning.oi_impulse_z_15m | binance-btcusdt-open-interest | 4h | radar_context | fresh | pass |
| btc_direct_trend.derivatives_positioning.oi_impulse_z_1h | binance-btcusdt-open-interest | 4h | radar_context | fresh | pass |
| btc_direct_trend.derivatives_positioning.oi_impulse_z_4h | binance-btcusdt-open-interest | 4h | radar_context | fresh | pass |
| btc_direct_trend.derivatives_positioning.funding_rate_8h_equiv_z | binance-btcusdt-funding | 4h | radar_context | fresh | pass |
| btc_direct_trend.derivatives_positioning.funding_acceleration_z_24h | binance-btcusdt-funding | 4h | radar_context | fresh | pass |
| btc_direct_trend.derivatives_positioning.liquidation_followthrough_score | binance-usdm-force-order-btcusdt | 4h | acceptance_gate | fresh | pass |
| btc_direct_trend.derivatives_positioning.liquidation_absorption_score | binance-usdm-force-order-btcusdt | 4h | acceptance_gate | fresh | pass |
| btc_direct_trend.derivatives_positioning.price_oi_interaction_state | binance-btcusdt-kline-1h,binance-btcusdt-open-interest,binance-btcusdt-taker-buy-sell-ratio | 4h | trigger_eligible | fresh | pass |
| btc_direct_trend.btc_residual_cross_asset.expected_return_24h | treasury-credit-derived | 1d | radar_context | fresh | pass |
| btc_direct_trend.btc_residual_cross_asset.residual_24h | treasury-credit-derived | 1d | radar_context | fresh | pass |
| btc_direct_trend.btc_residual_cross_asset.residual_z | treasury-credit-derived | 1d | radar_context | fresh | pass |
| btc_direct_trend.btc_residual_cross_asset.residual_semantic | treasury-credit-derived | 1d | trigger_eligible | fresh | pass |
| btc_direct_trend.event_overlay_context.emergency_level | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 4h | quality_gate | fresh | pass |
| btc_direct_trend.event_overlay_context.emergency_level | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 1d | quality_gate | fresh | pass |
| btc_direct_trend.event_overlay_context.ordinary_radar_trust | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 4h | trust_cap | fresh | pass |
| btc_direct_trend.event_overlay_context.ordinary_radar_trust | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 1d | trust_cap | fresh | pass |
| btc_direct_trend.event_overlay_context.trade_permission_modifier | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 4h | trust_cap | fresh | pass |
| btc_direct_trend.event_overlay_context.trade_permission_modifier | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 1d | trust_cap | fresh | pass |
| btc_direct_trend.event_overlay_context.event_trust_cap | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 4h | trust_cap | fresh | pass |
| btc_direct_trend.event_overlay_context.event_trust_cap | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 1d | trust_cap | fresh | pass |
| btc_direct_trend.event_overlay_context.post_event_reaction_state | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 4h | trust_cap | fresh | pass |
| btc_direct_trend.event_overlay_context.post_event_reaction_state | binance-btcusdt-kline-1h,fed-fomc-blackout-calendar,fxstreet-economic-calendar,official-macro-event-calendar | 1d | trust_cap | fresh | pass |
