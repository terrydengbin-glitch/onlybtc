# P5-C65 / Event Watchtower 鐙珛瀛愰〉闈?
## 鐘舵€?
TODO

## Phase

P5 Dashboard 涓庡彲瑙嗗寲灞?
## 鑳屾櫙

Event Watchtower 闇€瑕佺嫭绔嬪瓙椤甸潰鎵胯浇瀹屾暣浜嬪疄銆佹潵婧愩€丗ed 鏂囨湰銆侀鏈熸紓绉汇€佺獊鍙戝揩璁€丅TC 浜嬩欢鍚庡弽搴斿拰鍘嗗彶 replay銆傚畠涓嶅簲濉炶繘 dashboard 涓昏鍥撅紝涔熶笉搴旀贩鍏?radar/topology 璇︽儏椤点€?
## 鐩爣

鏂板宸︿晶瀵艰埅鍏ュ彛锛?
```text
鎷撴墤
浜嬩欢
闆疯揪
璇佹嵁
...
```

璺敱寤鸿锛?
```text
/event-watchtower
```

涓枃瀵艰埅鍚嶏細

```text
浜嬩欢
```

## 椤甸潰缁撴瀯

```text
1. Current Alert
   emergency_level
   state
   trade_permission_modifier
   ordinary_radar_trust
   valid_until

2. Active Event Timeline
   event type
   release time
   countdown
   phase
   importance

3. Expectation Drift
   consensus
   nowcast
   FedWatch / rate path drift
   2Y / DXY / NDX drift

4. Fed Speech / Policy Text
   speaker
   speaker_weight
   tone
   tone_confidence
   policy_relevance
   source link
   LLM summary

5. Shock Fast Lane
   shock_type
   confirmation_level
   source_count
   official_confirmed
   market_dislocation

6. BTC Reaction Validator
   return_5m
   return_30m
   return_2h
   absorbed / followthrough / fakeout
```

## 鏁版嵁婧?
浼樺厛娑堣垂锛?
```text
/api/event-window/latest
/api/event-window/active
/api/event-window/shock-lane/latest
/api/event-window/post-event-reaction
/api/event-window/history
```

## Daemon 鎺у埗鍖?
椤甸潰椤堕儴蹇呴』灞曠ず骞舵帶鍒?daemon锛?
```text
Watchtower Status:
  running|paused_by_user|degraded|stopped

Toggle:
  ON / OFF

Heartbeat:
  last heartbeat age

Mode:
  normal|high_alert|event_lock|shock_burst
```

鎿嶄綔锛?
```text
Pause
Resume
Settings
```

榛樿鐘舵€侊細

```text
ON / running
```

褰撶敤鎴峰叧闂細

```text
status = paused_by_user
鍋滄鏂板脊绐?淇濈暀 latest snapshot 涓庡巻鍙?timeline
鏄剧ず Watchtower paused
```

## 鏂囨杈圭晫

- 椤甸潰鏍囬涓?`Event Watchtower` 鎴?`浜嬩欢鍝ㄥ叺`銆?- 涓嶇О涓?radar module銆?- 涓嶅睍绀?BTC 澶氱┖璇勫垎銆?- 鏄剧ず `ordinary radar trust` 涓?`direct_score_impact=false`銆?
## DoD

- [ ] 宸︿晶瀵艰埅鏂板 `浜嬩欢`锛屼綅缃湪 `鎷撴墤` 涓?`闆疯揪` 涔嬮棿銆?- [ ] 椤甸潰椤堕儴灞曠ず daemon status銆乼oggle銆乭eartbeat銆乵ode銆?- [ ] 鏀寔 pause/resume 鎿嶄綔銆?- [ ] 榛樿灞曠ず涓?ON / running銆?- [ ] paused_by_user 鏃舵樉绀烘槑纭殏鍋滄€併€?- [ ] 鐙珛椤甸潰鍙睍绀哄叚鍖轰俊鎭€?- [ ] source lineage 鍙偣鍑绘垨灞曞紑銆?- [ ] Fed speech ambiguous / data_dependent 鍙纭樉绀恒€?- [ ] shock fast lane 涓?scheduled event 鍒嗗尯灞曠ず銆?- [ ] history/replay 鍏ュ彛鍙銆?- [ ] `npm run build` 閫氳繃銆?
## 渚濊禆

- P5-C63
- P9-C40
- P9-C41

