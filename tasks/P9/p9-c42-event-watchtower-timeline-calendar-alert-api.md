# P9-C42 / Event Watchtower Timeline / Calendar / Alert API

## 鐘舵€?
TODO

## Phase

P9 FastAPI 鑱氬悎 API 涓庤繍缁磋川鎺?
## 鑳屾櫙

Event Watchtower 鐙珛瀛愰〉闈笉鑳藉彧渚濊禆 `/latest`銆傚畠闇€瑕佹寜鏃ユ湡銆佸皬鏃躲€佸垎閽熸煡鐪嬪畼鏂逛簨浠躲€侀鏈熸紓绉汇€丗ed 鍙戣█銆丩LM 鍒嗘瀽銆佺獊鍙戜簨浠躲€佷簨浠跺悗 BTC 鍙嶅簲涓?alert 璁板綍锛屽洜姝ら渶瑕佷笓鐢?Timeline / Calendar / Alert API銆?
## 鐩爣

鏂板 API锛?
```text
GET  /api/event-window/calendar
GET  /api/event-window/timeline
GET  /api/event-window/events/{event_id}
GET  /api/event-window/events/{event_id}/expectations
GET  /api/event-window/events/{event_id}/reaction
GET  /api/event-window/speeches
GET  /api/event-window/speeches/{text_id}
GET  /api/event-window/shock-lane/history
GET  /api/event-window/alerts
POST /api/event-window/alerts/{alert_id}/ack
POST /api/event-window/alerts/{alert_id}/mute
```

## Query 鍙傛暟

### calendar

```text
from_ts
to_ts
importance
event_type
source_tier
```

### timeline

```text
date
from_ts
to_ts
event_type
level
include_types=calendar,expectation,official_text,llm,shock,reaction,alert
```

### speeches

```text
from_ts
to_ts
speaker
tone
policy_relevance
requires_human_review
```

### alerts

```text
from_ts
to_ts
level
ack_status
active_only
```

## Timeline 杩斿洖缁撴瀯

```json
{
  "items": [
    {
      "ts": "",
      "item_type": "calendar|expectation|official_text|llm_analysis|shock|reaction|alert",
      "event_id": "",
      "title": "",
      "level": "none|watch|high|critical",
      "summary": "",
      "payload": {},
      "source_lineage": []
    }
  ],
  "range": {
    "from_ts": "",
    "to_ts": ""
  }
}
```

## DoD

- [ ] calendar API 鍙寜鏃ユ湡鑼冨洿鏌ヨ瀹樻柟浜嬩欢銆?- [ ] timeline API 鍙寜 hh/mm 鑱氬悎澶氱被鍨?event watchtower 淇℃伅銆?- [ ] event detail API 杩斿洖浜嬩欢鐢熷懡鍛ㄦ湡銆侀鏈熸紓绉汇€乺eaction銆乤lerts銆?- [ ] speeches API 杩斿洖 Fed 鏂囨湰涓?LLM 鍒嗘瀽銆?- [ ] shock-lane history 杩斿洖绐佸彂浜嬩欢璁板綍銆?- [ ] alerts ack/mute 鍙啓鍏?SQLite銆?- [ ] 鎵€鏈?API 缂烘暟鎹椂杩斿洖缁撴瀯鍖栫┖鎬侊紝涓?500銆?- [ ] FastAPI contract tests 瑕嗙洊銆?
## 渚濊禆

- P8-C36
- P9-C40
- P9-C41
- P5-C67


