# P3-C25 Trend State Calibration Audit

- generated_at: 2026-05-23T06:30:11+00:00
- db: `E:\onlyBTC\data\onlybtc.sqlite3`
- covered_runs: 10

## Summary

### Previous rule distribution

| state | count | ratio |
|---|---:|---:|
| neutral_wait_confirm | 136 | 97.14% |
| conflict_no_trade | 4 | 2.86% |

### Calibrated rule distribution

| state | count | ratio |
|---|---:|---:|
| neutral_wait_confirm | 127 | 90.71% |
| bearish_pressure | 5 | 3.57% |
| conflict_no_trade | 4 | 2.86% |
| bearish_but_improving | 2 | 1.43% |
| risk_on_confirmed | 2 | 1.43% |

### Module state distribution

| state | count | ratio |
|---|---:|---:|
| unknown | 112 | 80.00% |
| balanced | 10 | 7.14% |
| support_dominant | 7 | 5.00% |
| pressure_dominant | 5 | 3.57% |
| internal_conflict | 4 | 2.86% |
| bearish_but_improving | 2 | 1.43% |

## Per-module Latest Rows

| module | latest_run | old_state | calibrated_state | module_state | direction_score | risk_score | confidence_score | conflict_score |
|---|---|---|---|---|---:|---:|---:|---:|
| asia_risk | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | balanced | 0.03 | 7.86 | 41.79 | 0.0 |
| btc_adoption | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | support_dominant | 2.41 | 20.85 | 85.11 | 0.2978 |
| btc_total_state | p3-20260523062951-0beea2 | conflict_no_trade | conflict_no_trade | internal_conflict | -0.02 | 48.59 | 62.41 | 0.6941 |
| crypto_breadth | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | support_dominant | 2.7 | 5.58 | 93.4 | 0.0797 |
| derivatives_crowding | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | balanced | 2.96 | 17.5 | 98.6 | 0.0 |
| dollar_liquidity | p3-20260523062951-0beea2 | neutral_wait_confirm | bearish_pressure | pressure_dominant | -2.26 | 6.72 | 94.95 | 0.096 |
| event_policy | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | balanced | -0.55 | 16.47 | 81.08 | 0.0763 |
| fund_flow | p3-20260523062951-0beea2 | conflict_no_trade | bearish_but_improving | bearish_but_improving | -2.7 | 32.58 | 48.23 | 0.4654 |
| kline_orderflow | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | support_dominant | 3.58 | 10.5 | 69.74 | 0.15 |
| macro_radar | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | balanced | 0.77 | 5.54 | 91.22 | 0.0791 |
| onchain_valuation | p3-20260523062951-0beea2 | neutral_wait_confirm | conflict_no_trade | internal_conflict | 0.2 | 37.23 | 35.35 | 0.5319 |
| options_volatility | p3-20260523062951-0beea2 | neutral_wait_confirm | neutral_wait_confirm | balanced | -0.69 | 5.88 | 81.37 | 0.084 |
| trade_structure_flow | p3-20260523062951-0beea2 | neutral_wait_confirm | bearish_pressure | pressure_dominant | -2.42 | 23.37 | 78.92 | 0.3339 |
| treasury_credit | p3-20260523062951-0beea2 | neutral_wait_confirm | bearish_pressure | pressure_dominant | -6.22 | 1.04 | 97.74 | 0.0149 |
