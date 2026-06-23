# BTC 4H/1D Direct Trend Walk-forward Evaluation
- status: PASS
- generated_at: 2026-06-22T19:11:10.207387+00:00
- sample_count: 70
- target_schema: p45.btc_timescale_judge.v2.2
- split_policy: walk_forward_with_purged_embargo
- random_k_fold: forbidden

## Metrics
| metric | status | value | samples | reason |
|---|---|---:|---:|---|
| rank_ic | PASS | -0.305957 | 70 |  |
| auc_trend_accepted | PASS | 0.724044 | 70 |  |
| f1_trend_accepted | PASS | 0.190476 | 70 |  |
| precision_top_decile | PASS | 0.0 | 70 |  |
| whipsaw_rate | PASS | 0.416667 | 70 |  |
| false_breakout_reduction | PASS | -0.232759 | 70 |  |
| lead_time_hours | PASS | None | 0 | no_4h_lead_samples_in_current_history |
| confidence_calibration | PASS | 0.651429 | 70 |  |
| event_window_robustness | PASS | None | 0 | no_event_window_samples_in_current_history |

## Sample Builder
```json
{
  "production_latest_asof": "2026-06-22T15:51:35.576061+00:00",
  "max_sample_asof": "2026-06-21T15:51:35.576061+00:00",
  "close_points": 327,
  "skipped": {
    "not_enough_history": 24,
    "missing_future": 3,
    "stride": 218
  },
  "persisted": true,
  "requested_max_samples": 80,
  "stride_hours": 4,
  "sample_count": 70,
  "target_schema": "p45.btc_timescale_judge.v2.2"
}
```
