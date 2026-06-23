# P5-C63 / Event Window Policy Shock Watchtower v3 鍓嶇

## 鐘舵€?
TODO

## Phase

P5 Dashboard 涓庡彲瑙嗗寲灞?
## 鑳屾櫙

褰撳墠鈥滈璀?/ 浜嬩欢绐楀彛鈥濇洿鍍忎簨浠跺垪琛ㄣ€倂3 闇€瑕佸崌绾ф垚鎴樻椂鐘舵€侀潰鏉匡細灞曠ず褰撳墠 emergency level銆乤ctive event銆侀鏈熸紓绉汇€佺獊鍙?fast lane銆丅TC reaction check锛屽苟鏄庣‘瀹冧笉鐩存帴鏀?radar score锛屽彧闄嶄綆鏅€?radar trust 鎴栫粰鍑?event lock銆?
## 鐩爣

鏂板 Event Window v3 UI 浜斿尯锛?
```text
1. Current Alert
2. Active Event
3. Expectation Drift
4. Shock Fast Lane
5. BTC Reaction Check
```

## 灞曠ず瑙勫垯

```text
none:
  鏅€?radar normal

watch:
  reduce_size / expectation drift

high:
  watch_only / pre-event high alert / material surprise

critical:
  event_lock / avoid_new_position / official shock / unscheduled shock confirmed
```

## 鏂囨杈圭晫

- 涓嶅啓鈥淓vent Window 鐪嬪 BTC / 鐪嬬┖ BTC鈥濄€?- 蹇呴』鍐欌€渙rdinary radar trust: normal/reduced/low/blocked鈥濄€?- 蹇呴』鏄剧ず `direct_score_impact=false` 鎴栫瓑浠峰惈涔夈€?- Fed speech tone 涓嶇‘瀹氭椂鏄剧ず ambiguous / data_dependent锛屼笉寮鸿楣伴附銆?
## DoD

- [ ] 鍓嶇浼樺厛娑堣垂 `/api/event-window/latest` 鎴?dashboard payload 涓殑 `event_window_v3`銆?- [ ] 灞曠ず emergency_level銆乻tate銆乿alid_until銆乼rade_permission_modifier銆?- [ ] 灞曠ず active event countdown 涓?phase銆?- [ ] 灞曠ず expectation_gap / drift / FedWatch drift銆?- [ ] 灞曠ず shock fast lane confirmation_level 涓?source_count銆?- [ ] 灞曠ず post-event reaction absorbed/followthrough銆?- [ ] `npm run build` 閫氳繃銆?
## 渚濊禆

- P9-C40
- P5-C62
- P9-C41

## Daemon 鎺ㄩ€佷笌寮圭獥琛ュ厖

鍓嶇闇€瑕佹秷璐?daemon 鎺ㄩ€佹垨杞 fallback锛?
```text
primary:
  SSE/WebSocket event alert stream

fallback:
  /api/event-window/latest polling
```

寮圭獥瑙勫垯锛?
```text
watch:
  badge / panel highlight only

high:
  toast + panel highlight

critical:
  modal popup
  requires manual acknowledge
```

寮圭獥鍙睍绀?emergency overlay锛屼笉鍐?BTC 澶氱┖缁撹銆?
琛ュ厖 DoD锛?
- [ ] high alert 鍙Е鍙?toast銆?- [ ] critical alert 鍙Е鍙?modal锛屽苟鏀寔浜哄伐纭鍏抽棴銆?- [ ] SSE/WebSocket 涓嶅彲鐢ㄦ椂 fallback polling 姝ｅ父銆?
