# P9-C40 / Event Window v3 API 閫忎紶

## 鐘舵€?
TODO

## Phase

P9 FastAPI 鑱氬悎 API 涓庤繍缁磋川鎺?
## 鑳屾櫙

Event Window v3 鏄?dashboard 鐨勭嫭绔嬩簨浠?绐佸彂瑕嗙洊灞傦紝闇€瑕佺嫭绔?API锛屽悓鏃跺湪 dashboard/latest銆乷verview/latest銆乭istory replay 涓€忎紶 overlay锛屼娇鍓嶇鑳藉睍绀轰簨浠剁姸鎬併€佺獊鍙戠姸鎬佸拰鏅€?radar trust銆?
## 鐩爣

鏂板鎴栨墿灞?API锛?
```text
/api/event-window/latest
/api/event-window/active
/api/event-window/shock-lane/latest
/api/event-window/history
/api/event-window/post-event-reaction
```

骞跺湪锛?
```text
/api/p45/dashboard/latest
/api/p45/overview/latest
/api/p45/history
```

閫忎紶锛?
```text
event_window_v3
```

## API 濂戠害

```json
{
  "event_window_v3": {
    "schema_version": "p45.event_window.v3",
    "direct_score_impact": false,
    "state": {},
    "overlay": {},
    "active_event": {},
    "expectation_monitor": {},
    "fed_speech_monitor": {},
    "shock_fast_lane": {},
    "post_event_reaction": {},
    "data_quality": {},
    "source_lineage": []
  }
}
```

## DoD

- [ ] latest 杩斿洖 schema_version=p45.event_window.v3銆?- [ ] active 杩斿洖褰撳墠 critical/high/watch 浜嬩欢銆?- [ ] shock-lane/latest 杩斿洖 unscheduled shock state銆?- [ ] history 鍙寜 run_id/event_id 鏌ヨ銆?- [ ] dashboard/latest 閫忎紶 overlay銆?- [ ] API 缂烘暟鎹椂杩斿洖 structured empty payload锛屼笉 500銆?- [ ] FastAPI contract tests 瑕嗙洊銆?
## 渚濊禆

- P3-C56
- P8-C35
- P5-C63
- P9-C41

## Daemon API 琛ュ厖

鏂板 daemon 杩愮淮涓庡憡璀︽帹閫?API锛?
```text
/api/event-window/daemon/status
/api/event-window/alerts/stream
/api/event-window/alerts/ack
/api/event-window/daemon/start
/api/event-window/daemon/stop
/api/event-window/daemon/pause
/api/event-window/daemon/resume
```

琛ュ厖 DoD锛?
- [ ] daemon/status 杩斿洖 heartbeat銆乵ode銆乻ource health銆?- [ ] daemon/status 杩斿洖 `running|paused_by_user|degraded|stopped`銆?- [ ] daemon/status 杩斿洖 `default_enabled=true` 涓?`auto_start=true`銆?- [ ] daemon/pause 鍙 daemon 杩涘叆 paused_by_user銆?- [ ] daemon/resume 鍙仮澶?running銆?- [ ] alerts/stream 鍙帹閫?high/critical alert銆?- [ ] alerts/ack 鏀寔 critical 寮圭獥浜哄伐纭銆?- [ ] full chain API 鍙鍙?latest snapshot锛屼笉鍚姩 daemon 閲囬泦銆?
