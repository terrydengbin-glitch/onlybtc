# P5-C77 / Event Watchtower 鐙珛 Run Once 鎸夐挳涓?Bundle 鍏ュ彛

## 鐘舵€?
TODO

## 鑳屾櫙

Event Window 鏄嫭绔?daemon锛屼笉鏄?radar 涓婚摼鐨勪竴閮ㄥ垎銆傜敤鎴烽渶瑕佸湪 Event Watchtower 瀛愰〉闈㈤噷鎵嬪姩璺戜竴娆′簨浠剁獥鍙ｉ噰闆嗕笌瀹¤锛岃€屼笉鏄偣鍑?Dashboard 鐨勪富 `Run Full Chain`銆?
褰撳墠 UI 鏈?daemon pause/resume锛屼絾缂哄皯娓呮櫚鐨勶細

```text
Event Run Once
Generate Audit Bundle HTML 1/2/3
```

## 鐩爣

鍦?Event Watchtower 瀛愰〉闈㈠鍔犵嫭绔嬫帶鍒跺尯锛屼娇鐢ㄦ埛鍙互锛?
```text
1. 鏌ョ湅 daemon 鏄惁 running / paused銆?2. 鎵嬪姩鎵ц Event Window Run Once銆?3. 鎵嬪姩鐢熸垚 HTML 1/2/3 鍚屾簮瀹¤ bundle銆?4. 鏄庣‘鐪嬪埌杩欎簺鎿嶄綔涓嶈Е鍙戜富 radar pipeline銆?```

## UI 瑕佹眰

寤鸿鏀惧湪 Event Watchtower 椤堕儴鍙充晶鎴?Live 椤垫帶鍒跺尯锛?
```text
Daemon: running / paused
[Pause daemon] [Resume daemon]
[Run Event Once]
[Generate Audit Bundle]
```

鐐瑰嚮 `Run Event Once` 鍚庯細

```text
鐘舵€佹樉绀?running...
瀹屾垚鍚庢樉绀?snapshot_id / asof_ts / emergency_level
鍒锋柊 Event Window latest / timeline / calendar / alerts / source status
鏄庣‘鏍囪 manual full sweep
```

鐐瑰嚮 `Generate Audit Bundle` 鍚庯細

```text
鏄剧ず bundle status
鏄剧ず HTML 1 / HTML 2 / HTML 3 / summary 閾炬帴
鏄剧ず snapshot consistency PASS / FAIL
```

## 杈圭晫

```text
鎸夐挳鍚嶅繀椤婚伩鍏嶅拰涓婚摼 Run Full Chain 娣锋穯銆?涓嶅緱澶嶇敤涓?dashboard 鐨?run once loading 鏂囨銆?涓嶅緱鎶?Event Run Once 鍐欐垚浼氬奖鍝?BTC 鍒嗘暟銆?鐢熸垚 HTML 鏄璁″姩浣滐紝涓嶆槸涓氬姟杈撳叆銆?```

## DoD

- [x] Event Watchtower 椤甸潰鍑虹幇鐙珛 `Run Event Once` 鎸夐挳銆?- [x] 鐐瑰嚮鍚庤皟鐢?`/api/event-window/run-once`銆?- [x] 鎴愬姛鍚庡埛鏂?Event Window 鐩稿叧 store 鏁版嵁銆?- [x] 椤甸潰鏄庣‘鏄剧ず `standalone daemon` / `does not run radar pipeline`銆?- [x] 椤甸潰鏄庣‘鏄剧ず `manual full sweep`锛屽尯鍒簬鍚庡彴鍒嗛 scheduler tick銆?- [x] daemon/status 鍖哄煙灞曠ず鑷姩杞鐘舵€侊細scheduler on/off銆乴ast tick銆乶ext due sources銆?- [x] 椤甸潰鍑虹幇 `Generate Audit Bundle` 鍏ュ彛銆?- [x] bundle 瀹屾垚鍚庡睍绀?HTML 1/2/3 涓?summary 閾炬帴銆?- [x] 鎸夐挳 loading / error / success 鐘舵€佹竻妤氥€?- [x] 涓嶅奖鍝嶄富 `Run Full Chain` 鐘舵€併€?- [x] `npm run build` 閫氳繃銆?
## 渚濊禆

- P9-C44
- P9-C45
- P7-C21
- P5-C73
- P5-C75

