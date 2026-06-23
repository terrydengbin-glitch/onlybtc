# P7-C14 / Event Window v3 鍏ㄩ摼璺璁?
## 鐘舵€?
TODO

## Phase

P7 浼樺寲銆佸洖娴嬩笌鐢熶骇娌荤悊

## 鑳屾櫙

Event Window v3 鏄嫭绔嬭鐩栧眰锛屽繀椤诲璁″畠鏄惁鐪熸闄嶄綆鏅€?radar 鍦ㄤ簨浠剁獥鍙ｄ腑鐨勮鍒わ紝鑰屼笉鏄埗閫犲櫔闊炽€傚璁￠噸鐐规槸 source lineage銆佺姸鎬佷紭鍏堢骇銆乨irect_score_impact=false銆乪mergency overlay銆乭istory replay銆乁I 灞曠ず杈圭晫銆?
## 鐩爣

瀵逛互涓嬮摼璺仛涓ユ牸瀹¤锛?
```text
P1 official calendar / expectations
P2 shock fast lane
P3 state machine / emergency overlay
P4.5 Fed speech analyzer
P5 post-event reaction + UI
P8 SQLite replay
P9 API
Dashboard event window panel
```

## 瀹¤椤?
- 瀹樻柟浜嬩欢鏄惁鏉ヨ嚜 official source銆?- consensus / nowcast / FedWatch 鏄惁鏈?source lineage銆?- unscheduled shock 鏄惁闇€瑕佸婧愭垨瀹樻柟纭銆?- Event Window 鏄惁娌℃湁杩涘叆 radar score銆?- emergency overlay 鏄惁姝ｇ‘褰卞搷 trade_permission_modifier / ordinary_radar_trust銆?- event_lock 鏄惁鑳藉湪 post-event reaction 鍚庤В闄ゆ垨闄嶇骇銆?- history replay 鏄惁鑳藉鐜板綋鏃剁姸鎬併€?
## DoD

- [ ] 杈撳嚭 `reports/p7-c14-event-window-v3-audit.md`銆?- [ ] 杈撳嚭 machine-readable JSON 瀹¤鎶ュ憡銆?- [ ] 楠岃瘉 `direct_score_impact=false`銆?- [ ] 楠岃瘉 `event_window_v3` 鍦?latest/overview/history 涓彲鐢ㄣ€?- [ ] 楠岃瘉 data_quality_blocked 浼樺厛绾ф渶楂樸€?- [ ] 楠岃瘉 unscheduled_shock_confirmed 楂樹簬 scheduled calendar 鐘舵€併€?- [ ] 楠岃瘉 Fed speech ambiguous 涓嶈Е鍙?fed_tone_shift銆?- [ ] 楠岃瘉鍓嶇涓嶆妸 Event Window 鍐欐垚 BTC 鏂瑰悜銆?
## 渚濊禆

- P1-C57
- P1-C58
- P2-C40
- P3-C56
- P4.5-C46
- P5-C62
- P5-C63
- P8-C35
- P9-C40
- P9-C41

## Daemon 瀹¤琛ュ厖

鏂板瀹¤椤癸細

- daemon 鏄惁鐙珛浜?run once 甯搁┗銆?- daemon 鏄惁闅忛」鐩惎鍔ㄩ粯璁よ嚜鍔ㄨ繍琛屻€?- 鐢ㄦ埛鏄惁鍙湪浜嬩欢瀛愰〉闈?pause/resume銆?- paused_by_user 鏄惁鍋滄鏂板脊绐椾絾淇濈暀鍘嗗彶鏁版嵁銆?- source polling 棰戠巼鏄惁鎸?normal/high_alert/event_lock/shock_burst 鍒囨崲銆?- LLM 鏄惁鍙湪 material change 鏃惰Е鍙戙€?- high/critical 鏄惁鑳芥帹閫佸脊绐椾笖涓嶈緭鍑?BTC 鏂瑰悜銆?- full chain 鏄惁鍙鍙?latest snapshot銆?
琛ュ厖 DoD锛?
- [ ] 楠岃瘉 daemon heartbeat銆乻ource health銆乻napshot lineage銆?- [ ] 楠岃瘉 backend 鍚姩鍚?daemon 榛樿 running銆?- [ ] 楠岃瘉浜嬩欢瀛愰〉闈?ON/OFF 鎺у埗鐪熷疄璋冪敤 API銆?- [ ] 楠岃瘉 paused_by_user 涓嶄骇鐢熸柊 high/critical 寮圭獥銆?- [ ] 楠岃瘉 full chain 鍙鍙?latest snapshot銆?- [ ] 楠岃瘉 high/critical alert 寮圭獥閾捐矾銆?
## SQLite / Timeline / API 瀹¤琛ュ厖

鏂板瀹¤椤癸細

- Event Watchtower 鏄惁鍏峰鐙珛 SQLite 琛ㄧ粍锛岃€屼笉鏄彧渚濊禆 final_payload銆?- Calendar / Timeline / Speech / Shock / Reaction / Alert 鏄惁鍙寜鏃ユ湡銆佸皬鏃躲€佸垎閽熸煡璇€?- 瀛愰〉闈?Timeline 鏄惁灞曠ず鐪熷疄 daemon 璁板綍锛屼笉鏄?mock銆?- Alert ack/mute 鏄惁鍐欏叆 SQLite 骞惰兘 replay銆?- full chain final_payload 鏄惁鍙祵鍏?latest snapshot锛屼笉鍙嶅悜姹℃煋 daemon timeline銆?
琛ュ厖 DoD锛?
- [ ] 楠岃瘉 `event_watchtower_snapshots` 鍙煡璇?latest 涓庡巻鍙层€?- [ ] 楠岃瘉 timeline API 鍙繑鍥?calendar/expectation/official_text/llm/shock/reaction/alert 娣峰悎鏃堕棿绾裤€?- [ ] 楠岃瘉 event detail 鍙拷韪崟涓?event 鐢熷懡鍛ㄦ湡銆?- [ ] 楠岃瘉瀛愰〉闈?Calendar / Timeline / Speeches / Shock Lane / History 鍧囨秷璐圭湡瀹?API銆?
鏂板渚濊禆锛?
- P8-C36
- P9-C42
- P5-C67

