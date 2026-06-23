# P9-C45 / Event Watchtower 鍒嗛杞 Scheduler 涓?Manual Full Sweep

## 鐘舵€?
TODO

## 鑳屾櫙

Event Window / Policy Shock Watchtower 鏄嫭绔嬪父椹?daemon銆傚畠鍜屼富 radar pipeline 鍒嗙锛屽惎鍔ㄩ」鐩椂榛樿鑷姩杩愯銆?
褰撳墠浠ｇ爜涓細

```text
FastAPI startup -> event_watchtower_daemon.start(auto=True)
start() -> collect_once()
```

杩欒鏄庣郴缁熷惎鍔ㄦ椂浼氳窇涓€娆?Event Window collect锛屼絾杩樻病鏈夌湡姝ｇ殑鍚庡彴鍒嗛杞 scheduler銆傜敤鎴锋湡鏈涚殑鏄細

```text
鑷姩杩愯锛?  鎸変笉鍚?source / event phase 浣跨敤涓嶅悓棰戠巼鎸佺画閲囬泦

鎵嬪姩 Run Once锛?  鐢ㄦ埛鐐瑰嚮鎸夐挳鍚庯紝瀹屾暣鎶撳彇銆佸垎鏋愩€佸叆搴撱€佸睍绀轰竴娆?  涓嶅彈鑷姩鍒嗛鑺傛祦褰卞搷
```

## 鐩爣

涓?Event Watchtower daemon 澧炲姞鐙珛鍒嗛 scheduler锛屽苟鏄庣‘鍖哄垎锛?
```text
1. background polling loop
2. manual full sweep run once
```

## 鑷姩杩愯鍒嗛绛栫暐

寤鸿鍒濆 cadence锛?
```text
official calendar:
  normal: 6h
  T-7d: 1h
  T-24h: 15m
  event_lock: 1m

expectation / nowcast:
  normal: 6h
  T-7d: 1h
  T-24h: 10m-15m

Fed RSS / official text:
  normal: 5m
  market hours / high alert: 1m-2m

unscheduled shock lane:
  official RSS / trusted text: 1m-2m
  market dislocation check: 15s-60s if enabled

actual polling:
  before release: disabled or low frequency
  T-5m to T+30m: 5s-15s
  T+30m to T+2h: 1m

post-event reaction:
  T+5m / T+30m / T+2h checkpoints

LLM speech analyzer:
  only on new text_hash / material text change
  never every polling tick
```

## Manual Full Sweep 璇箟

`Event Window Run Once` 涓嶇瓑浜庤嚜鍔?scheduler 鐨勪竴娆?tick銆?
瀹冨繀椤伙細

```text
1. 蹇界暐褰撳墠 source 鐨?next_due_at 鑺傛祦銆?2. 鎵ц鍏ㄩ噺 connector sweep銆?3. 閲嶆柊璁＄畻 state / overlay / shock lane / source quality銆?4. 瀵规柊鏂囨湰瑙﹀彂 LLM 鍒嗘瀽锛涙棤鏂版枃鏈垯澶嶇敤缂撳瓨銆?5. 鍐欏叆 SQLite snapshot 鍜岀浉鍏冲瓙琛ㄣ€?6. 鍒锋柊 API/UI銆?7. 涓嶈Е鍙戜富 radar / P45 Run Full Chain銆?```

## 鐘舵€佸瓧娈?
daemon status 寤鸿鎵╁睍锛?
```json
{
  "status": "running|paused_by_user|degraded|stopped",
  "collection_mode": "standalone_daemon",
  "scheduler_enabled": true,
  "manual_run_active": false,
  "last_tick_at": "",
  "last_full_sweep_at": "",
  "last_snapshot_id": "",
  "source_cadence": {},
  "next_due_sources": [],
  "inflight_sources": []
}
```

## API 褰卞搷

P9-C44 鐨?`/api/event-window/run-once` 搴旇皟鐢?manual full sweep锛岃€屼笉鏄櫘閫?scheduler tick銆?
寤鸿锛?
```text
POST /api/event-window/run-once
  -> event_watchtower_daemon.run_once_full_sweep(force=True)

GET /api/event-window/daemon/status
  -> 杩斿洖 scheduler cadence / next_due / last_tick / last_full_sweep
```

## 杈圭晫

```text
鍚庡彴 scheduler 鍙互璺宠繃鏈埌鏈?source銆?manual full sweep 涓嶈兘璺宠繃鍏抽敭 source锛岄櫎闈?provider disabled / missing key / access blocked銆?pause daemon 鍚庡悗鍙?scheduler 鍋滄銆?manual run once 鏄惁鍏佽鍦?paused 鐘舵€佹墽琛岋紝闇€瑕?UI 鏄庣‘锛氬缓璁厑璁革紝骞舵爣璁?manual_override=true銆?LLM 鍙湪鏂版枃鏈垨 material change 鏃惰皟鐢ㄣ€?critical/high alert 鍙互瑙﹀彂 UI 寮圭獥锛屼絾涓嶆敼 BTC/radar score銆?```

## DoD

- [x] Event Watchtower daemon 鏈夊悗鍙板垎棰?polling loop銆?- [x] FastAPI startup 鍚?daemon 甯搁┗锛屼笉鍙槸鍚姩鏃?collect_once 涓€娆°€?- [x] source cadence 鍙厤缃紝鑷冲皯瑕嗙洊 calendar / expectation / RSS / shock / actual / reaction / LLM銆?- [x] daemon/status 杩斿洖 cadence銆乶ext_due_sources銆乴ast_tick_at銆乴ast_full_sweep_at銆?- [x] manual Run Once 鎵ц full sweep锛屽苟鏍囪 `manual_full_sweep=true`銆?- [x] manual Run Once 涓嶈Е鍙戜富 radar pipeline銆?- [x] paused_by_user 鍋滄鍚庡彴 scheduler銆?- [x] manual Run Once 鍦?paused 鐘舵€佷笅琛屼负鏄庣‘骞跺彲瀹¤銆?- [x] LLM 涓嶅湪姣忎釜 tick 閲嶅璋冪敤銆?- [x] 娴嬭瘯瑕嗙洊 startup auto-run銆乻cheduler tick銆乵anual full sweep銆乸ause/resume銆?
## 渚濊禆

- P9-C41
- P9-C44
- P5-C77

