# P7-C01 Module Weight Calibration Report

- schema_version: `p7.c01.module_weight_calibration.v1`
- generated_at: `2026-06-22T23:39:44.177375+00:00`
- applied_to_production: `False`
- selected_profile: `base`
- profile_reason: `no_profile_signal_above_threshold`
- confidence_discount: `0.0`
- latest_module_count: `14`

## Guardrails

- recommendation_only
- does_not_modify_registry
- does_not_modify_state_machine
- does_not_emit_trading_advice
- requires_p7_c08_before_production_apply

## Recommended Weights

| module | base | profile | recommended | delta_vs_base |
|---|---:|---:|---:|---:|
| asia_risk | 0.036364 | 0.036364 | 0.036364 | +0.000000 |
| btc_adoption | 0.054545 | 0.054545 | 0.054545 | +0.000000 |
| btc_total_state | 0.081818 | 0.081818 | 0.081818 | +0.000000 |
| crypto_breadth | 0.054545 | 0.054545 | 0.054545 | +0.000000 |
| derivatives_crowding | 0.072727 | 0.072727 | 0.072727 | +0.000000 |
| dollar_liquidity | 0.072727 | 0.072727 | 0.072727 | +0.000000 |
| event_policy | 0.100003 | 0.100003 | 0.100003 | +0.000000 |
| fund_flow | 0.090909 | 0.090909 | 0.090909 | +0.000000 |
| kline_orderflow | 0.072727 | 0.072727 | 0.072727 | +0.000000 |
| macro_radar | 0.081818 | 0.081818 | 0.081818 | +0.000000 |
| onchain_valuation | 0.081818 | 0.081818 | 0.081818 | +0.000000 |
| options_volatility | 0.054545 | 0.054545 | 0.054545 | +0.000000 |
| trade_structure_flow | 0.072727 | 0.072727 | 0.072727 | +0.000000 |
| treasury_credit | 0.072727 | 0.072727 | 0.072727 | +0.000000 |

## Quality Discounts

- none

## Rollback

- type: `restore_base_registry_weights`
- source: `onlybtc.radars.registry.MODULE_WEIGHTS`

## Notes

- This report is recommendation-only.
- It does not modify production registry weights.
- It does not bypass state machine, invalidation, warning level, or data quality gates.
