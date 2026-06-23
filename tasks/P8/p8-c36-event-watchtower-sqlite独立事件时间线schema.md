# P8-C36 / Event Watchtower SQLite 鐙珛浜嬩欢鏃堕棿绾?Schema

## 鐘舵€?
TODO

## Phase

P8 SQLite銆佸巻鍙叉暟鎹笌鎸佷箙鍖?
## 鑳屾櫙

Event Watchtower 鏄嫭绔嬪父椹?daemon锛屼笉搴斿彧鎶?latest snapshot 濉炶繘 final_payload銆傜嫭绔嬪瓙椤甸潰闇€瑕佹寜鏃ユ湡銆佸皬鏃躲€佸垎閽熸煡鐪嬪畼鏂逛簨浠躲€侀鏈熸紓绉汇€丗ed 鏂囨湰銆丩LM 鍒嗘瀽銆佺獊鍙戦€氶亾銆丅TC 浜嬩欢鍚庡弽搴斿拰寮圭獥璁板綍锛屽洜姝ら渶瑕佺嫭绔?SQLite 浜嬩欢鏃堕棿绾?schema銆?
## 鐩爣

鏂板 Event Watchtower 鐙珛琛ㄧ粍锛屾敮鎸侊細

```text
鎸夋棩鏈熸煡璇?鎸夊皬鏃?鍒嗛挓鏌ヨ
鎸?event_id 鏌ヨ
鎸?alert 鏌ヨ
鎸?Fed speech 鏌ヨ
鎸?shock 鏌ヨ
鍘嗗彶 replay
```

## 寤鸿琛?
```text
event_watchtower_snapshots
event_calendar_items
event_expectation_snapshots
event_official_text_items
event_llm_analyses
event_shock_lane_items
event_post_reaction_snapshots
event_alerts
```

## 瀛楁瑕佹眰

### event_watchtower_snapshots

```text
snapshot_id
asof_ts
daemon_mode
event_window_state
emergency_level
trade_permission_modifier
ordinary_radar_trust
payload_json
payload_hash
created_at
```

### event_calendar_items

```text
event_id
event_type
title
importance
release_time_utc
release_time_et
release_time_local
source_name
source_url
source_tier
actual_available
official_text_available
payload_json
updated_at
```

### event_expectation_snapshots

```text
id
event_id
snapshot_ts
consensus
previous
forecast
nowcast
market_implied
expectation_gap
expectation_drift_1d
expectation_drift_3d
rate_cut_prob_drift_1d
risk_direction
source_lineage_json
payload_json
```

### event_official_text_items

```text
text_id
source_ts
source_name
source_url
speaker
title
text_hash
raw_text_excerpt
payload_json
created_at
```

### event_llm_analyses

```text
analysis_id
text_id
event_id
model
tone
tone_confidence
policy_relevance
speaker_weight
requires_human_review
reason_codes_json
summary
payload_json
created_at
```

### event_shock_lane_items

```text
shock_id
detected_ts
shock_type
confirmation_level
source_count
official_confirmed
market_dislocation
btc_microstructure_confirmation
rumor_risk
reason_codes_json
source_lineage_json
payload_json
```

### event_post_reaction_snapshots

```text
reaction_id
event_id
snapshot_ts
window
btc_return_5m
btc_return_30m
btc_return_2h
oi_change
funding_change
realized_vol
reaction_state
absorbed
followthrough
payload_json
```

### event_alerts

```text
alert_id
snapshot_id
level
title
message
trade_permission_modifier
valid_until
ack_required
ack_status
ack_at
mute_until
payload_json
```

## 鍐欏叆绛栫暐

daemon 涓嶆瘡绉掑啓搴擄紝鍙湪 material state change 鍐欏叆锛?
```text
calendar update
expectation snapshot drift beyond threshold
Fed RSS new item
LLM analysis completed
shock lane state changed
emergency level changed
alert triggered / acked / muted
post-event reaction window updated
```

## DoD

- [ ] 鏂板鎴栬縼绉荤嫭绔?event watchtower 琛ㄧ粍銆?- [ ] 鏀寔 latest snapshot 鏌ヨ銆?- [ ] 鏀寔鎸?date / from_ts / to_ts 鏌ヨ timeline銆?- [ ] 鏀寔鎸?event_id 鏌ヨ浜嬩欢瀹屾暣鐢熷懡鍛ㄦ湡銆?- [ ] 鏀寔 alert ack/mute 鐘舵€佹寔涔呭寲銆?- [ ] 鏀寔 Fed speech text_hash 鍘婚噸銆?- [ ] SQLite 鍐欏叆涓嶄細闃诲 radar chain銆?- [ ] 娴嬭瘯瑕嗙洊 material change 鍐欏叆涓?replay 鏌ヨ銆?
## 渚濊禆

- P8-C35
- P9-C41
- P9-C42


