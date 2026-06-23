# P6 DoD Report

- schema_version: `p6.dod_report.v1`
- status: `warning`
- article_snapshot_id: `p6article-p45final-p8-replay-verify-202606221611`
- final_run_id: `p45final-p8-replay-verify-202606221611`

## Checks

- `passed` article_snapshot_available: P6 article snapshot is available.
- `passed` article_citations_traceable: Article citations are traceable to evidence ids.
- `passed` article_history_available: P6 article history returns snapshots.
- `passed` history_replay_frozen: History replay is frozen and does not use latest runtime state.
- `passed` alert_quality_available: Alert quality layer is queryable.
- `passed` outcome_tracking_available: Outcome tracking layer is queryable.
- `warning` module_effectiveness_available: Module effectiveness layer is queryable.
- `passed` no_trading_advice_boundary: P6 DoD artifacts do not provide trading advice.
- `passed` no_production_weight_mutation: P6 scoring does not mutate module weights.

## Boundary

- trading_advice: `false`
- production_weight_mutation: `false`
- mutates_final_view: `false`
