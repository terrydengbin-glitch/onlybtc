# P3-C57 / Event Window v3.1 Source Quality State Machine

## 鐘舵€?
DONE

## Phase

P3 鐘舵€佹満涓?emergency overlay

## 鑳屾櫙

褰撳墠 Event Window 鍙湁涓€涓?`overall_source_mode`锛屽鏄撴妸 partial live 婧愯璇绘垚鏁翠綋澶辫触銆倂3.1 闇€瑕佹妸 calendar銆乤ctual銆乶owcast銆乧onsensus銆丗edWatch銆乻peech 鍒嗗紑璇勭骇銆?
## 鐩爣

鏂板 source quality state machine锛岃 Event Window 鍦?partial live 鐘舵€佷笅鍙户缁伐浣滐紝鍚屾椂鏄庣‘鍝簺鍔熻兘琚鐢ㄣ€?
## 杈撳嚭濂戠害

```json
{
  "source_quality": {
    "calendar_quality": "ok|partial|fallback|missing|blocked",
    "actual_quality": "ok|pending|fallback|missing|blocked",
    "nowcast_quality": "ok|partial|stale|missing",
    "consensus_quality": "ok|missing|stale|provider_failed",
    "fedwatch_quality": "ok|proxy|missing|provider_failed",
    "speech_quality": "ok|partial|missing",
    "overall_source_mode": "live|partial_live|fallback|blocked"
  },
  "disabled_capabilities": [],
  "blocked_reason": null
}
```

## Block 鏉′欢

```text
critical event 鏃堕棿涓嶅彲寰?actual 宸插彂甯冧絾鏃犳硶纭
瀹樻柟鏂囨湰婧愬啿绐?绯荤粺鏃堕棿/鏃跺尯閿欒
鎵€鏈?calendar provider 閮藉け璐?```

## 闈?Block 闄嶇骇

```text
consensus missing:
  绂佺敤 release_surprise
  淇濈暀 nowcast_risk / pre_event_high_alert

fedwatch proxy:
  淇濈暀 hawkish_repricing_proxy
  绂佺敤 official fedwatch_probability

BLS calendar fallback:
  淇濈暀 countdown
  闄嶄綆 calendar_confidence
```

## DoD

- [ ] `overall_source_mode=partial_live` 鏃朵簨浠剁獥鍙ｇ户缁緭鍑?high/watch overlay銆?- [ ] consensus missing 涓嶅鑷存暣涓澘鍧?blocked銆?- [ ] actual 宸插彂甯冧絾鏃犳硶纭鏃跺彲鍗囩骇 blocked/high risk銆?- [ ] UI 鍜?API 閮借兘鐪嬪埌 disabled_capabilities銆?- [ ] 鍗曞厓娴嬭瘯瑕嗙洊 ok銆乸artial_live銆乫allback銆乥locked銆?
## 渚濊禆

- P1-C60
- P1-C61
- P1-C62
- P1-C63
- P1-C64
- P9-C43


