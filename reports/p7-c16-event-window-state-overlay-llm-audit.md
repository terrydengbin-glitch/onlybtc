# P7-C16 / Event Window State Overlay LLM Audit

- Status: PASS
- Snapshot: evt-20260622210343-f82bc676
- State: pre_event_high_alert / watch
- Overlay: reduce_size / trust reduced
- direct_score_impact: False
- Failures: none

## Checks

- State priority passed: True
- Overlay boundary passed: True
- LLM boundary passed: True
- SQLite consistency passed: True

## Regression Cases

- daemon paused blocks: data_quality_blocked level=watch pass=True
- critical shock overrides calendar: unscheduled_shock_confirmed level=critical pass=True
- event lock stays critical: event_lock level=critical pass=True
- fallback high alert capped to watch: pre_event_high_alert level=watch pass=True

## SQLite Counts

- event_watchtower_snapshots: 7293
- event_official_text_items: 26
- event_llm_analyses: 36
- event_source_fetches: 111312