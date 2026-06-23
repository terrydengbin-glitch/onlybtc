# P7-C02 State & Alert Threshold Calibration Report

- schema_version: `p7.c02.state_alert_threshold_calibration.v1`
- generated_at: `2026-06-22T23:39:44.178939+00:00`
- applied_to_production: `False`
- input_path: `E:\onlyBTC\reports\btc-4h-1d-direct-trend-evaluation-report.json`
- evaluation_status: `PASS`
- sample_count: `70`

## Guardrails

- recommendation_only
- does_not_modify_state_machine
- does_not_modify_alert_controller
- does_not_modify_direct_trend_thresholds
- does_not_emit_trading_advice
- does_not_relax_warning_sensitivity_without_p7_c08
- requires_p7_c08_before_production_apply

## Adjustments

| scope | key | base | recommended | delta | reason |
|---|---|---:|---:|---:|---|
| direct_trend | acceptance | 60 | 70 | 10 | confidence_bucket_70-85_success_rate_0.1286_below_expected_0.7800 |
| direct_trend | trust | 65 | 75 | 10 | confidence_bucket_70-85_success_rate_0.1286_below_expected_0.7800 |
| direct_trend | strong_direction | 60 | 65 | 5 | confidence_bucket_70-85_success_rate_0.1286_below_expected_0.7800 |
| p4_state_machine | critical_publish_confidence | 0.62 | 0.67 | 0.05 | confidence_bucket_70-85_success_rate_0.1286_below_expected_0.7800 |
| direct_trend_confidence_caps | 70-85 | - | 65 | - | confidence_bucket_70-85_success_rate_0.1286_below_expected_0.7800 |

## Calibration Buckets

| bucket | count | success_rate | expected |
|---|---:|---:|---:|
| 0-50 | 0 | - | - |
| 50-70 | 0 | - | - |
| 70-85 | 70 | 0.128571 | 0.78 |
| 85-100 | 0 | - | - |

## Evidence Gaps

- lead_time_hours: no_4h_lead_samples_in_current_history
- event_window_robustness: no_event_window_samples_in_current_history

## Thresholds

### p4_state_machine

| key | base | recommended |
|---|---:|---:|
| critical_publish_confidence | 0.62 | 0.67 |
| low_baseline_confidence | 0.5 | 0.5 |
| trend_candidate_confidence | 0.5 | 0.5 |
| warning_aggregate_abs_score | 0.35 | 0.35 |

### p4_alerts

| key | base | recommended |
|---|---:|---:|
| blocked_alert_level | 0.25 | 0.25 |
| data_quality_confidence_cap | 0.45 | 0.45 |
| run_mode_integrity_alert_level | 1 | 1 |
| watch_confidence | 0.45 | 0.45 |

### direct_trend

| key | base | recommended |
|---|---:|---:|
| acceptance | 60 | 70 |
| agreement_categories | 3 | 3 |
| event_cap | 65 | 65 |
| strong_direction | 60 | 65 |
| trend_direction | 50 | 50 |
| trust | 65 | 75 |
| volatility_shock | 70 | 70 |
| weak_acceptance | 45 | 45 |

## Confidence Caps

| bucket | cap |
|---|---:|
| 70-85 | 65 |

## Rollback

- type: `restore_base_thresholds`
- source: production constants remain unchanged by this report.

## Notes

- This report is recommendation-only.
- It keeps warning sensitivity unless P7-C08 validates a production change.
- It does not emit trading advice or bypass state machine gates.
