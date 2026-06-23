# P7-C17 Event Window Shock Fast Lane Audit

Status: PASS

## Current State

- state: `pre_event_high_alert`
- emergency_level: `watch`
- overlay: `reduce_size`
- direct_score_impact: `False`

## Latest Shock

```json
{
  "shock_id": "shock-btc-5m-202606222003",
  "detected_at": "2026-06-22T20:03:07.227585+00:00",
  "shock_type": "crypto_native",
  "emergency_level": "high",
  "confirmation_level": "market_dislocation",
  "source_count": 1,
  "official_confirmed": false,
  "market_dislocation": true,
  "btc_microstructure_confirmation": false,
  "cross_asset_confirmation": false,
  "rumor_risk": false,
  "raw_title": "BTC 5m market dislocation",
  "raw_url": "",
  "source_hash": "cee749bc992ad2997fb351c168fddac2e5ca2cbccb40396cdc63f6e4a0c915fb",
  "published_at": "2026-06-22T20:03:07.227585+00:00",
  "reason_codes": [
    "btc_5m_market_dislocation"
  ],
  "source_lineage": [
    {
      "source_id": "binance",
      "source_tier": "market_live",
      "market_probe_id": "mprobe-20260622200307-87daa6aa",
      "primary_window": "5m",
      "primary_return": 0.001706477230425607,
      "primary_return_z": 2.025037718838325
    }
  ],
  "evidence": {
    "primary_window": "5m",
    "primary_return": 0.001706477230425607,
    "primary_return_z": 2.025037718838325,
    "btc_return_5m": 0.001706477230425607,
    "btc_return_15m": 0.001706477230425607,
    "btc_return_1h": 0.001706477230425607,
    "btc_return_4h": -0.002128406822212159,
    "btc_return_24h": 0.011496366370129074,
    "btc_return_5m_z": 2.025037718838325,
    "btc_return_15m_z": 0.866225514920561,
    "btc_return_1h_z": 0.35437405746448014,
    "btc_return_4h_z": 0.22099684310885517,
    "btc_return_24h_z": 0.4872209327320961,
    "oi_change_15m_z": null,
    "liquidation_z": null,
    "dxy_move_z": null,
    "us2y_move_z": null,
    "ndx_move_z": null
  },
  "data_quality_flags": [
    "oi_liquidation_confirmation_missing"
  ],
  "direct_score_impact": false
}
```

## LLM 中文解释

- provider: `deepseek`
- status: `success`
- summary: 冲击为原生加密高紧急度市场错位事件，但缺乏官方与微观结构确认，未触发直接得分影响。Event Window 从正常转入高警戒（非锁定）状态，叠加层开启交易规模缩减、信心上限70%和波动警告，普通雷达信任降级。
- boundary: Event Window 保持高警戒，叠加层仅允许缩减规模操作，不限制退出，但禁止新增风险敞口。雷达信任在手动审核前维持降级。

## Synthetic Cases

[
  {
    "label": "critical overrides scheduled",
    "state": {
      "event_window_state": "unscheduled_shock_confirmed",
      "state_priority": 95,
      "emergency_level": "critical",
      "reason_codes": [
        "policy"
      ],
      "valid_until": "2026-05-28T10:00:00+00:00"
    },
    "overlay": {
      "trade_permission_modifier": "event_lock",
      "confidence_cap": 45,
      "volatility_warning": true,
      "ordinary_radar_trust": "blocked"
    },
    "passed": true
  },
  {
    "label": "high watch only",
    "state": {
      "event_window_state": "market_dislocation_high_alert",
      "state_priority": 75,
      "emergency_level": "high",
      "reason_codes": [
        "market_dislocation"
      ],
      "valid_until": "2026-05-28T09:00:00+00:00"
    },
    "overlay": {
      "trade_permission_modifier": "watch_only",
      "confidence_cap": 55,
      "volatility_warning": true,
      "ordinary_radar_trust": "low"
    },
    "passed": true
  },
  {
    "label": "rumor downgrade",
    "state": {
      "event_window_state": "unscheduled_shock_watch",
      "state_priority": 55,
      "emergency_level": "watch",
      "reason_codes": [
        "rumor"
      ],
      "valid_until": "2026-05-28T08:45:00+00:00"
    },
    "overlay": {
      "trade_permission_modifier": "reduce_size",
      "confidence_cap": 70,
      "volatility_warning": true,
      "ordinary_radar_trust": "reduced"
    },
    "passed": true
  },
  {
    "label": "official url hash lineage",
    "state": {},
    "overlay": {},
    "shock": {
      "shock_id": "shock-official-synthetic-fed-em",
      "detected_at": "2026-05-28T08:00:00+00:00",
      "shock_type": "policy",
      "emergency_level": "critical",
      "confirmation_level": "official",
      "source_count": 1,
      "official_confirmed": true,
      "market_dislocation": false,
      "btc_microstructure_confirmation": false,
      "cross_asset_confirmation": false,
      "rumor_risk": false,
      "raw_title": "Federal Reserve issues emergency policy statement",
      "raw_url": "https://www.federalreserve.gov/newsevents/pressreleases/test.htm",
      "source_hash": "synthetic-fed-emergency-hash",
      "published_at": "2026-05-28T08:00:00+00:00",
      "reason_codes": [
        "official_source_hit"
      ],
      "source_lineage": [
        {
          "source_id": "Federal Reserve RSS",
          "source_tier": "official",
          "url": "https://www.federalreserve.gov/newsevents/pressreleases/test.htm",
          "source_hash": "synthetic-fed-emergency-hash"
        }
      ],
      "evidence": {},
      "data_quality_flags": [],
      "direct_score_impact": false
    },
    "passed": true
  }
]

## API Checks

{
  "latest_status": 200,
  "history_status": 200,
  "alerts_status": 200,
  "latest_passed": true,
  "history_passed": true,
  "alerts_passed": true,
  "latest_payload_keys": [
    "api_schema_version",
    "created_at",
    "errors",
    "run_lineage",
    "schema_version",
    "shock_fast_lane",
    "status",
    "warnings"
  ]
}

## SQLite Counts

{
  "snapshots": 7295,
  "shocks": 726,
  "alerts": 4357,
  "source_fetches": 111348
}
