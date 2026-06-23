# P9-C44 / Event Watchtower 鐙珛 Run Once 涓庡璁?Bundle API

## 鐘舵€?
TODO

## 鑳屾櫙

Event Window / Policy Shock Watchtower 鏄嫭绔嬩簬 radar 涓讳笟鍔￠摼鏉＄殑甯搁┗ daemon銆傚畠涓嶅簲缁戝畾 `Run Full Chain`銆丳1/P2/P3/P4.5 涓婚摼杩愯锛屼篃涓嶅簲渚濊禆涓昏繘绋?run once 鎵嶆洿鏂般€?
褰撳墠绯荤粺宸叉湁 Event Window daemon銆乣/api/event-window/latest`銆乨aemon pause/resume銆乼imeline/calendar/alerts/source diagnostics 绛?API銆備絾杩橀渶瑕佷竴涓槑纭殑 **Event Window 鑷繁鐨?run once**锛?
```text
Event Watchtower Run Once
  鍙Е鍙?event_watchtower_daemon.collect_once()
  鍙埛鏂?Event Window SQLite / API payload
  涓嶈Е鍙戜富 radar collect / p2 / p3 / p45
  涓嶄慨鏀?BTC radar score
```

鍚屾椂锛孒TML 1/2/3 瀹¤闇€瑕佸悓婧?snapshot锛屽洜姝ら渶瑕?API 鎴栬剼鏈叆鍙ｈ兘瑙﹀彂涓€娆″畬鏁?audit bundle銆?
## 鐩爣

鏂板 Event Watchtower 鐙珛 Run Once API 涓庡璁?bundle API锛屼娇鐢ㄦ埛鍙互浠?Event 瀛愰〉闈㈡墜鍔ㄥ畬鏁磋窇涓€娆?Event Window锛岃€屼笉褰卞搷涓讳笟鍔￠摼鏉°€?
## 鑼冨洿

### 鏂板 / 瀵归綈 API

寤鸿鏂板锛?
```text
POST /api/event-window/run-once
POST /api/event-window/audit-bundle/run
GET  /api/event-window/audit-bundle/latest
```

### `/run-once` 琛屼负

```text
1. 璋冪敤 Event Window manual full sweep銆?2. 涓嶄娇鐢ㄥ悗鍙?scheduler 鐨?next_due_at 鑺傛祦銆?3. 灏藉彲鑳藉畬鏁存墽琛?calendar / expectation / official text / shock / actual / reaction / source quality銆?4. 瀵规柊 Fed 鏂囨湰鎴?material change 瑙﹀彂 LLM锛涙棤鏂版枃鏈垯澶嶇敤缂撳瓨銆?5. 鍐欏叆 event_watchtower_snapshots 鍜岀浉鍏充簨浠惰〃銆?6. 杩斿洖 snapshot_id銆乤sof_ts銆乻tate銆乷verlay銆乤ctive_event銆乻ource_summary銆?7. 涓嶈Е鍙戜富 Run Full Chain銆?8. 涓嶈Е鍙?radar score 閲嶇畻銆?```

### `/audit-bundle/run` 琛屼负

```text
1. 鍙噰闆嗕竴娆?Event Window payload
2. 鍥哄畾 snapshot_id / asof_ts
3. 鍩轰簬鍚屼竴涓?payload 鐢熸垚 HTML 1/2/3
4. 杈撳嚭 bundle summary
5. 杩斿洖 html_paths銆乻napshot_id銆佷竴鑷存€у璁＄粨鏋?```

## 杈圭晫

```text
Event Window daemon 鏄嫭绔嬪父椹昏繘绋嬭涔夈€?Event Window Run Once 鏄墜鍔ㄥ埛鏂颁簨浠剁獥鍙ｏ紝涓嶆槸涓婚摼 run once銆?涓婚摼 Run Full Chain 鍙互璇诲彇 latest Event Window snapshot锛屼絾涓嶈兘鍙嶅悜鎺у埗 Event daemon銆?Event Window Run Once 涓嶄慨鏀?BTC module_score / radar score / p45 final score銆?```

## DoD

- [x] 鏂板 `/api/event-window/run-once`銆?- [x] Run Once 杩斿洖 `snapshot_id`銆乣asof_ts`銆乣state`銆乣overlay`銆?- [x] Run Once 璋冪敤 Event Window manual full sweep锛屼笉璋冪敤涓婚摼 run full chain銆?- [x] Run Once 涓嶅彈鍚庡彴 source cadence 鑺傛祦褰卞搷銆?- [x] Run Once 杩斿洖 `manual_full_sweep=true` 鎴栫瓑浠峰瓧娈点€?- [x] Run Once 鍚?SQLite `event_watchtower_snapshots` 澧炲姞鎴栨洿鏂板搴?snapshot銆?- [x] 鏂板 `/api/event-window/audit-bundle/run` 鎴栫瓑浠?API銆?- [x] audit bundle 鍙噰闆嗕竴娆★紝骞跺浐瀹氬悓涓€涓?`snapshot_id`銆?- [x] API 杩斿洖 HTML 1/2/3 璺緞鍜?bundle summary 璺緞銆?- [x] 鑻?HTML 1/2/3 snapshot_id 涓嶄竴鑷达紝API 杩斿洖 FAIL銆?- [x] 鍚庣娴嬭瘯瑕嗙洊 Event Run Once 涓庝富 Run Once 闅旂銆?
## 楠屾敹鍛戒护

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py -q
```

## 渚濊禆

- P9-C40
- P9-C41
- P9-C42
- P9-C43
- P7-C21
- P9-C45

