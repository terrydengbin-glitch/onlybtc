# P7-C09 Radar Modules Full-Chain Contract Audit

Status: **PASS with execution-profile caveat**

Audited run:

- `collect_run_id`: `collect-20260527092422-91c85d`
- `p2_radar_run_id`: `radar-20260527092727-670d81`
- `p3_run_id`: `p3-20260527092730-456f38`
- `pack_id`: `p45pack-20260527092744-e59e9f`
- `article_run_id`: `p45articles-20260527092745-5b7271`
- `final_run_id`: `p45final-20260527092745-2a60bb`
- `execution_profile`: `fast_deterministic`

## Scope

Audited optimized radar modules across P1/P2/P3/P4.5/P8/P9/P5:

- `macro_radar v3`
- `dollar_liquidity v2.1`
- `treasury_credit v2.1`
- `fund_flow v2.2`
- `onchain_valuation v2.2`
- `btc_adoption v2.3`
- `asia_risk v2.3`
- `kline_orderflow v2.2`
- `trade_structure_flow v2.3`
- `derivatives_crowding v2.5`
- `crypto_breadth v3`
- `options_volatility v2.1`
- `event_policy v2.1`
- `btc_total_state v2`

## Findings

Fixed one contract issue during audit:

- `trade_structure_flow`: `btc_funding_rate` and `btc_funding_band` were still registered under `leverage_structure` signal rules.
- Fix: moved both to `leverage_context` with `affects_signal=false` and `driver_eligible=false`.
- File: `backend/src/onlybtc/radars/registry.py`

After the fix, the raw-metric guard found no optimized module where raw level fields directly participate in directional signal.

## Verification

Passed:

- Backend core tests: `139 passed`
- Trade structure targeted tests: `4 passed`
- P5 dashboard contract validation: passed
- Frontend build: passed
- SQLite/API/history/detail audit: passed
- Registry raw guard: passed

Expected caveat:

- `scripts/validate_p5_page_dod.py` reports `articles missing llm_research appendix`.
- This run used `fast_deterministic` with LLM skipped, so LLM research/analyst appendices are intentionally absent. Deterministic radar chain, SQLite persistence, API, reports and frontend contract still passed.

## SQLite / API Evidence

Latest run persisted:

- `module_json_outputs`: 14 rows for the audited P3 run
- `feature_values`: 6187 rows for the audited P3 run
- `radar_outputs`: 14 rows for the audited P3 run
- `raw_observations`: 70 rows for the audited P1 run

Global database counts at audit time:

- `module_json_outputs`: 5986
- `feature_values`: 321689
- `radar_outputs`: 5592
- `raw_observations`: 27910
- `normalized_metrics`: 515
- `run_stages`: 2476
- `articles`: 1

API checks covered:

- `/api/p45/dashboard/latest`
- `/api/p45/radar-modules/latest`
- `/api/p45/radar-modules/{module_id}`
- `/api/p45/history/{final_run_id}`
- `/api/p45/audit-reports/latest`
- `/api/p45/runs/latest`

## Module Summary

| Module | Version | State | Direction | Effective | Stage / implication |
|---|---|---|---|---|---|
| macro_radar | p3.c45.macro_radar.v3 | macro_tailwind_but_btc_lagging | neutral | bullish | macro_tailwind_not_absorbed |
| dollar_liquidity | p3.c46.dollar_liquidity.v2.1 | liquidity_neutral | neutral | neutral | - |
| treasury_credit | p3.c47.treasury_credit.v2.1 | treasury_credit_neutral | neutral | neutral | neutral |
| fund_flow | p3.c50.fund_flow.v2.2 | etf_outflow_confirmed | bearish | bearish | institutional_demand_drag |
| onchain_valuation | p3.c52.onchain_valuation.v2.2 | onchain_neutral | neutral | neutral | none / neutral |
| btc_adoption | p3.c54.btc_adoption.v2.3 | btc_adoption_neutral | neutral | neutral | none / neutral |
| asia_risk | p3.c56.asia_risk.v2.3 | asia_risk_neutral | neutral | neutral | early_warning / neutral |
| kline_orderflow | p3.c57.kline_orderflow.v2.2 | none | neutral | neutral | none / neutral |
| trade_structure_flow | p3.c58.trade_structure_flow.v2.3 | none | neutral | neutral | none / neutral |
| derivatives_crowding | p3.c60.derivatives_crowding.v2.5 | early_warning | neutral | neutral | early_warning / trend_fragile |
| crypto_breadth | p3.c44.crypto_breadth.v3 | risk_off_but_breadth_improving | neutral | bullish | early_repair |
| options_volatility | p3.c42.options_volatility.v2.1 | downside_protection_bid | neutral | neutral | - |
| event_policy | p3.c43.event_policy.v2.1 | event_neutral | neutral | neutral | - |
| btc_total_state | p3.c41.btc_total_state.v2 | price_down_confirmed | bearish | bearish | - |

## Conclusion

The optimized radar modules are aligned across registry semantics, P3 semantic profiles, SQLite scored-module persistence, P9 latest/detail/history APIs, refreshed audit reports, and Vue3 build contract. No blocking issue remains for deterministic production use.
