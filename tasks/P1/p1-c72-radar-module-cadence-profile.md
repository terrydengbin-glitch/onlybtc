# P1-C72 Radar Module Cadence Profile

Status: DONE

## Background

The BTC center card and the 14 radar modules should not be refreshed as one synchronized full-chain batch. Fast market modules need high-frequency updates, while macro, on-chain, adoption, and policy modules should refresh more slowly.

This task defines the cadence profile used by the future resident Radar Runtime Daemon.

## Goal

Create a `radar_module_cadence_profile` contract with:

```text
module_name
cadence_group
interval_sec
ttl_sec
hard_stale_sec
source_group
horizon
participation_policy
max_signal_stage_when_stale
```

## Default Groups

```text
fast_sensing, 30s-2m:
  kline_orderflow
  trade_structure_flow
  derivatives_crowding
  btc_total_state

confirmation, 5m-30m:
  fund_flow
  crypto_breadth
  options_volatility
  asia_risk

regime_context, 1h-6h:
  macro_radar
  treasury_credit
  dollar_liquidity
  onchain_valuation
  btc_adoption
  event_policy
```

## Rules

1. Fast modules control sensitivity, early warning, and fast signal.
2. Confirmation modules control whether confirmed_signal is allowed.
3. Regime modules control background bias and confidence caps.
4. Stale raw metrics must not directly trigger bullish or bearish output.
5. Event Window remains an independent overlay and is not merged into radar score.
6. Manual Radar Runtime run once must bypass cadence and perform one full sweep.

## DoD

1. A central profile exists for all 14 radar modules.
2. The profile contains interval, ttl, hard stale, horizon, and participation policy.
3. The profile supports normal, high_vol, shock, and degraded source modes.
4. P9 daemon scheduler can read the profile.
5. P3 freshness state machine can consume the profile.
6. P4.5 cockpit aggregator can consume the profile.
