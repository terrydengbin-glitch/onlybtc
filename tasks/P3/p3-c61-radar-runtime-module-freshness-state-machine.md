# P3-C61 Radar Runtime Module Freshness State Machine

Status: DONE

## Background

After the radar chain becomes cadence-based, every module snapshot needs a freshness state. Stale modules must not keep participating as live confirmation evidence.

## Goal

Add a module freshness state machine:

```text
fresh
partial_live
stale
hard_stale
missing
blocked
failed
```

Each module must also output:

```text
can_trigger_early_warning
can_trigger_fast_signal
can_participate_confirmed_signal
can_only_context
confidence_cap
```

## Decision Rules

1. `fresh`: normal participation.
2. `partial_live`: may participate in watch/context, unless required confirmation fields are missing.
3. `stale`: cannot participate in confirmed_signal.
4. `hard_stale`: visible only, no directional participation.
5. `missing` or `failed`: data-quality only, no directional participation.
6. `blocked`: blocks the corresponding horizon from confirmed_signal.

## DoD

1. State machine consumes P1-C72 cadence profile and P8-C38 snapshot age.
2. Every module outputs freshness_state, age_sec, ttl_sec, hard_stale_sec.
3. Stale raw metrics cannot trigger bullish or bearish output.
4. Stale confirmation modules downgrade BTC confirmed_signal.
5. Stale fast modules reduce sensitivity_score.
6. Stale regime modules reduce confidence_score only.
7. Output is consumable by P4.5 cockpit aggregator and P5 UI.
