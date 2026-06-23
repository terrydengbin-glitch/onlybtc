# P9-C41 / Event Watchtower Daemon 甯搁┗杩愯涓庢帹閫?
## 鐘舵€?
TODO

## Phase

P9 FastAPI 鑱氬悎 API 涓庤繍缁磋川鎺?
## 鑳屾櫙

`Event Window / Policy Shock Watchtower v3` 涓嶅簲缁戝畾褰撳墠 `run once / collect / P1-P2-P3-P4.5` 鎵瑰鐞嗛摼璺€備簨浠剁獥鍙ｉ渶瑕佸父椹昏繍琛岋紝鍥犱负瀹樻柟 RSS銆丗ed 鍙戣█銆佸競鍦洪鏈熸紓绉汇€丅TC 浜嬩欢鍚庡弽搴斿拰闈炴棩鍘嗙獊鍙戠殑閲囬泦棰戠巼涓?radar 鍏ㄩ摼鏉″畬鍏ㄤ笉鍚屻€俤aemon 蹇呴』闅忛」鐩惎鍔ㄨ嚜鍔ㄨ繍琛岋紝榛樿寮€鍚紝骞跺厑璁哥敤鎴峰湪浜嬩欢瀛愰〉闈㈡殏鍋?鎭㈠銆?
鏍稿績鍘熷垯锛?
```text
Radar chain:
  鎵瑰鐞?/ run once / 閲忓寲瓒嬪娍鍒ゆ柇

Event Watchtower daemon:
  甯搁┗ / 楂橀 / 浜嬪疄浜嬩欢 / 绐佸彂鍐插嚮 / emergency overlay

Full chain:
  鍙鍙?daemon latest snapshot锛屼笉璐熻矗楂橀浜嬩欢閲囬泦
```

## 鐩爣

鏂板鐙珛甯搁┗ daemon锛?
```text
event_watchtower_daemon
```

璐熻矗锛?
```text
official calendar sync
Fed RSS / official text polling
expectation / nowcast / FedWatch snapshot
unscheduled shock fast lane
BTC market reaction websocket/listener
LLM trigger queue
event_window_v3 snapshot generation
SSE/WebSocket push to frontend
alert popup event dispatch
heartbeat / health check
```

## 鐢熷懡鍛ㄦ湡涓庣敤鎴峰紑鍏?
```text
FastAPI / backend process starts
  -> event_watchtower_daemon auto-starts when enabled
  -> daemon writes heartbeat and latest snapshot
  -> frontend reads daemon/status

default:
  EVENT_WATCHTOWER_ENABLED=true
  EVENT_WATCHTOWER_AUTO_START=true
  EVENT_WATCHTOWER_DEFAULT_ON=true
  status=running

pause:
  status=paused_by_user
  stop high-frequency polling
  stop new popup alerts
  preserve latest snapshot and history

resume:
  status=running
  restore polling schedules
  restore alert push
```

daemon failed 鏃?radar chain 涓嶅簲鎸傦紱radar chain failed 鏃?daemon 浠嶅彲缁х画杩愯銆?
## 閰嶇疆椤?
```text
EVENT_WATCHTOWER_ENABLED=true
EVENT_WATCHTOWER_AUTO_START=true
EVENT_WATCHTOWER_DEFAULT_ON=true
EVENT_WATCHTOWER_ALLOW_USER_TOGGLE=true
EVENT_WATCHTOWER_DISABLE_POPUPS=false
EVENT_WATCHTOWER_MAX_RSS_POLL_SECONDS=60
EVENT_WATCHTOWER_EVENT_LOCK_POLL_SECONDS=10
```

## 棰戠巼绛栫暐

```text
Normal mode:
  Fed RSS: 60s
  BLS / BEA calendar: 1h-6h
  FOMC calendar: 6h-24h
  consensus / nowcast: 1h-6h
  FedWatch / 2Y / DXY: 1m-5m
  BTC market websocket: realtime

T-24h high alert:
  Fed RSS: 15s-30s
  consensus / nowcast: 10m-15m
  FedWatch / 2Y / DXY: 30s-60s
  BTC market websocket: realtime

T-1h to T+30m event lock:
  official actual polling: 5s-15s
  Fed RSS / official text: 5s-15s
  BTC reaction: realtime
  LLM: only on new text / material change

Unscheduled shock burst:
  official RSS: 5s-15s for bounded burst window
  trusted news/feed: fastest configured
  BTC / cross-asset: realtime or 5s bucket
```

## LLM 瑙﹀彂杈圭晫

LLM 浠呭湪浠ヤ笅鎯呭喌鍏ラ槦锛?
```text
new Fed speech / testimony / press release
FOMC statement / minutes / SEP text hash changed
trusted shock headline with sufficient source quality
official text conflicts with prior baseline
human-readable alert summary required
```

LLM 涓嶅仛锛?
```text
BTC bullish / bearish scoring
actual / consensus / nowcast numeric override
ambiguous Fed speech 寮鸿楣伴附
```

## 鎺ㄩ€佷笌寮圭獥绛夌骇

```text
none:
  no popup, persist only

watch:
  badge / panel highlight

high:
  toast + event panel highlight

critical:
  modal popup + optional sound/flash
  requires manual acknowledge
```

## API / 鎺ㄩ€佸绾?
```json
{
  "daemon": "event_watchtower_daemon",
  "status": "running|paused_by_user|degraded|stopped",
  "default_enabled": true,
  "auto_start": true,
  "heartbeat_ts": "",
  "mode": "normal|high_alert|event_lock|shock_burst",
  "latest_snapshot_id": "",
  "latest_event_window_v3": {},
  "active_alerts": [],
  "source_health": {},
  "llm_queue": {
    "pending": 0,
    "last_completed_ts": ""
  }
}
```

## DoD

- [ ] daemon 鍙嫭绔嬪惎鍔?鍋滄锛屼笉渚濊禆 run once銆?- [ ] backend/FastAPI 鍚姩鏃?daemon 榛樿鑷姩鍚姩銆?- [ ] 榛樿鐘舵€佷负 ON / running銆?- [ ] 鏀寔鐢ㄦ埛 pause/resume锛屼笖鏆傚仠涓嶅垹闄ゅ巻鍙叉暟鎹€?- [ ] daemon 鏈?heartbeat 涓?source health銆?- [ ] 鏀寔 source polling scheduler 涓庡姩鎬侀鐜囧垏鎹€?- [ ] 鏀寔 BTC market websocket/listener 鎴栧彲闄嶇骇楂橀 polling銆?- [ ] 鏀寔 LLM trigger queue锛屼笖鍙湪鏂版枃鏈?material change 鏃惰皟鐢ㄣ€?- [ ] 鏀寔 event_window_v3 snapshot 鍐欏叆 SQLite銆?- [ ] 鏀寔 SSE/WebSocket 鎴栫瓑浠峰疄鏃舵帹閫佺粰鍓嶇銆?- [ ] critical/high alert 鍙┍鍔ㄥ墠绔脊绐椼€?- [ ] paused_by_user 鐘舵€佷笉浜х敓鏂板脊绐椼€?- [ ] full chain 鍙鍙?latest snapshot锛屼絾涓嶅惎鍔ㄩ珮棰戦噰闆嗐€?- [ ] daemon crash 鍚庝笉浼氱牬鍧?radar chain锛汚PI 杩斿洖 degraded snapshot銆?
## 渚濊禆

- P1-C57
- P1-C58
- P2-C40
- P3-C56
- P4.5-C46
- P8-C35
- P9-C40
- P5-C63

