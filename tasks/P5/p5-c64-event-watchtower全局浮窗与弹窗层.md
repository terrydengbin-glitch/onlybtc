# P5-C64 / Event Watchtower 鍏ㄥ眬娴獥涓庡脊绐楀眰

## 鐘舵€?
TODO

## Phase

P5 Dashboard 涓庡彲瑙嗗寲灞?
## 鑳屾櫙

Event Window / Policy Shock Watchtower v3 闇€瑕佷竴涓嫭绔嬩簬 dashboard銆乺adar銆乼opology銆佸彸渚ф娊灞夊拰鏅€?modal 鐨勫叏灞€鎻愰啋灞傘€傜揣鎬ヤ簨浠朵笉鏄櫘閫氬崱鐗囦俊鎭紝`high` 涓?`critical` 蹇呴』鑳藉嵆鏃惰鐩栨墍鏈夊眰锛屽苟娓呮琛ㄨ揪鏅€?radar trust 鏄惁闄嶄綆銆?
## 鐩爣

鏂板鍏ㄥ眬 fixed 娴獥缁勪欢锛?
```text
EventWatchtowerFloatingAlert
```

灞曠ず褰撳墠锛?
```text
emergency_level
event_window_state
active_event / shock_type
trade_permission_modifier
ordinary_radar_trust
valid_until
reason_summary
source_count / confirmation_level
```

## 灞曠ず绛夌骇

```text
none:
  涓嶆樉绀?
watch:
  鍙充笂瑙?鍙充笅瑙掑皬娴獥
  涓嶆墦鏂搷浣?
high:
  杈冨ぇ娴獥 + 闂儊杈规
  toast + panel highlight
  鍙?dismiss 15 鍒嗛挓

critical:
  灞呬腑 modal-like 娴獥
  鑳屾櫙杞婚伄缃?  鑴夊啿/闂€€杈规
  蹇呴』 acknowledge
```

## 灞傜骇瑙勫垯

```text
event-watchtower-floating-alert:
  z-index: 10000

normal modal:
  z-index: 9000

right drawer:
  z-index: 8000

dashboard / radar / topology:
  normal layer
```

critical 娴獥蹇呴』楂樹簬锛?
```text
dashboard main
radar detail
topology canvas
right drawer
settings
history replay
normal modal
```

## 浜や簰瑙勫垯

```text
watch:
  鍙嚜鍔ㄦ敹璧凤紝鍙繚鐣?badge

high:
  鍙?dismiss / mute 15 鍒嗛挓
  鐘舵€佷粛淇濈暀鍦?dashboard summary widget

critical:
  蹇呴』 acknowledge
  鍙?mute 5/15/30 鍒嗛挓
  鑻?mute 鍒版湡涓?state 浠?critical锛屽垯鍐嶆寮瑰嚭
```

## 鏂囨杈圭晫

- 涓嶅啓 `BTC bullish` / `BTC bearish`銆?- 鍙啓浜嬩欢椋庨櫓銆乷rdinary radar trust銆乼rade permission modifier銆?- 蹇呴』璇存槑 `direct_score_impact=false` 鎴栧悓绛夊惈涔夈€?
## Daemon 鏆傚仠鎬?
褰?daemon status 涓?`paused_by_user`锛?
```text
涓嶅脊鍑烘柊鐨?watch/high/critical 娴獥
涓嶆挱鏀惧０闊?闂儊
淇濈暀褰撳墠椤甸潰涓殑 paused badge
鑻ユ殏鍋滃墠宸叉湁 active critical alert锛屾樉绀轰竴娆¤交鎻愮ず锛?  Watchtower paused. Critical alerts are muted.
```

## DoD

- [ ] 鍏ㄥ眬娴獥鍙秷璐?`/api/event-window/alerts/stream` 鎴?fallback polling銆?- [ ] watch/high/critical 涓夌瑙嗚鐘舵€佸彲鍖哄垎銆?- [ ] critical 灞呬腑骞堕珮浜庢墍鏈夐〉闈㈠眰銆?- [ ] 鏀寔 acknowledge / mute銆?- [ ] daemon paused_by_user 鏃朵笉寮规柊 alert銆?- [ ] paused 鏃跺凡鏈?critical 鍙樉绀轰竴娆?muted 鎻愮ず銆?- [ ] 寮圭獥涓嶄細淇敼 radar score銆?- [ ] `npm run build` 閫氳繃銆?
## 渚濊禆

- P5-C63
- P9-C40
- P9-C41

