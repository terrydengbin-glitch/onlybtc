# Radar Metrics Score BTC UI Chain Audit
- status: PARTIAL
- generated_at: 2026-05-29T14:34:28.048882+00:00
- runtime_snapshot_id: radar-runtime-20260529143200-146efc10
- runtime_asof_ts: 2026-05-29T14:32:00.470592+00:00
- modules: 14/14
- module_status_counts: {"PARTIAL": 6, "PASS": 8}

## Module Summary
- asia_risk: PARTIAL score=0.1787 direction=conflict source=fresh reasons=hibor: no metric_value row
- btc_adoption: PARTIAL score=0.1699 direction=bullish source=expected_lag reasons=lightning_capacity_btc: latest source_run status=warning; lightning_capacity_btc: latest source_run status=warning; lightning_node_count: latest source_run status=warning; lightning_node_count: latest source_run status=warning; lightning_channel_count: latest source_run status=warning; lightning_channel_count: latest source_run status=warning; lightning_capacity_btc: latest source_run status=warning; lightning_capacity_btc: latest source_run status=warning; lightning_node_count: latest source_run status=warning; lightning_node_count: latest source_run status=warning; lightning_channel_count: latest source_run status=warning; lightning_channel_count: latest source_run status=warning
- btc_total_state: PASS score=-0.25 direction=bearish source=fresh reasons=
- crypto_breadth: PASS score=0.407 direction=bullish source=expected_lag reasons=
- derivatives_crowding: PASS score=0.479 direction=bearish source=fresh reasons=
- dollar_liquidity: PASS score=0.006 direction=bullish source=expected_lag reasons=
- event_policy: PARTIAL score=0.0 direction=neutral source=fresh reasons=regulatory_event_score: no metric_value row
- fund_flow: PASS score=-0.45 direction=bearish source=expected_lag reasons=
- kline_orderflow: PASS score=0.305 direction=bearish source=fresh reasons=
- macro_radar: PARTIAL score=0.0808 direction=bullish source=expected_lag reasons=
- onchain_valuation: PARTIAL score=0.2155 direction=bullish source=expected_lag reasons=realized_price_derived: no metric_value row; whale_flow: no metric_value row; miner_flow: no metric_value row
- options_volatility: PASS score=0.0 direction=neutral source=fresh reasons=
- trade_structure_flow: PASS score=0.008 direction=conflict source=fresh reasons=
- treasury_credit: PARTIAL score=-0.15 direction=bearish source=expected_lag reasons=