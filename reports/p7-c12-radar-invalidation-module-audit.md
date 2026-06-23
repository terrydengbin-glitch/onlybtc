# P7-C12 Radar Module Invalidation Audit

- Status: **PASS**
- Final run: `p45final-20260527120852-bf4b06`
- Cockpit: `p45.btc_trend_cockpit.v2` / `neutral` / `neutral`
- Workbench: `p45.invalidation_workbench.v2` / `watching`
- Rules: triggered `0`, armed `3`, blocked `0`

## Verdict

- PASS. Context accepted and quality-discounted radar evidence is now separated from triggerable directional evidence.

## Passed Checks
- Workbench schema_version is p45.invalidation_workbench.v2.
- Evidence matrix contains 14 radar modules.
- All expected radar modules are represented.
- asia_risk context accepted evidence is non-triggerable.
- btc_adoption context accepted evidence is non-triggerable.
- onchain_valuation context accepted evidence is non-triggerable.
- fund_flow data-quality flagged evidence is discounted and non-triggerable.
- No triggered rules fired in neutral/watch-only thesis.
- Neutral thesis correctly has no refute_current_view rules.
- Neutral thesis keeps break-neutral scenarios.

## Module Matrix

| module | layer | direction | stage | evidence | weight | trigger | implication | dq flags |
|---|---|---|---|---|---|---|---|---|
| macro_radar | regime | bullish | none | missing | missing | False | wait_for_confirmation |  |
| treasury_credit | flow_capital | bearish | none | missing | missing | False | neutral | insufficient_hy_oas_history |
| asia_risk | fast_confirmation | bullish | none | accepted_context | context | False | neutral |  |
| event_policy | quality_controller | neutral | none | missing | missing | False |  |  |
| dollar_liquidity | flow_capital | bearish | none | missing | missing | False |  |  |
| fund_flow | flow_capital | bearish | confirmed_signal | quality_discounted | discounted | False | institutional_demand_drag | etf_single_source |
| crypto_breadth | fast_confirmation | bearish | none | missing | missing | False | risk_off_pressure |  |
| kline_orderflow | btc_response | neutral | none | missing | missing | False | neutral |  |
| derivatives_crowding | btc_response | neutral | early_warning | missing | missing | False | trend_fragile |  |
| trade_structure_flow | btc_response | bearish | early_warning | accepted | full | True | structure_pressure_emerging |  |
| options_volatility | fast_confirmation | neutral | none | missing | missing | False |  |  |
| btc_total_state | quality_controller | bearish | none | missing | missing | False |  |  |
| btc_adoption | regime | bearish | none | accepted_context | context | False | neutral |  |
| onchain_valuation | regime | bearish | none | accepted_context | context | False | neutral |  |
