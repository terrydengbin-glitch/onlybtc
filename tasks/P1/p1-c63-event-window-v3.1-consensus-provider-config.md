# P1-C63 / Event Window v3.1 Consensus Provider Config

## 鐘舵€?
DONE

## Phase

P1 鏁版嵁婧愭帴鍏ヤ笌閲囬泦灞?
## 鑳屾櫙

Consensus / survey forecast 娌℃湁绋冲畾鍏嶈垂瀹樻柟婧愩€俆rading Economics銆丒conoday銆丅loomberg 绛夊睘浜庡晢涓?鑱氬悎婧愩€傛病鏈?key 鏃跺繀椤绘槑纭?`consensus_status=missing`锛屼笉鑳界敤 nowcast 浼 consensus銆?
## 鐩爣

鎶?consensus provider 閰嶇疆鍖栵紝骞惰浜嬩欢鐘舵€佹満鍦ㄧ己澶?consensus 鏃朵粛鍙仛棰勬湡椋庨櫓棰勮锛屼絾绂佹璁＄畻 actual-vs-consensus surprise銆?
## Provider

```text
primary:
  Trading Economics API
  Econoday / Bloomberg / other paid provider

fallback:
  none

proxy:
  Cleveland nowcast
  market-implied repricing
```

## 杈撳嚭濂戠害

```json
{
  "event_id": "",
  "consensus": null,
  "consensus_source": null,
  "consensus_status": "ok|missing|stale|provider_failed",
  "nowcast_proxy": null,
  "market_implied_proxy": null,
  "release_surprise_enabled": false,
  "source_lineage": [],
  "warnings": []
}
```

## 瑙勫垯

```text
鏈?consensus:
  actual - consensus => surprise_raw / surprise_z

鏃?consensus:
  绂佹 release_surprise
  鍏佽 nowcast_risk / market_repricing_risk / pre_event_high_alert
```

## DoD

- [ ] provider key 缂哄け鏃惰緭鍑?`consensus_status=missing`銆?- [ ] 娌℃湁 consensus 鏃朵笉璁＄畻 `actual_vs_consensus_surprise`銆?- [ ] nowcast_proxy 鍙敤浜?`inflation_upside_watch`锛屼笉鏇夸唬 consensus銆?- [ ] UI 鏄庣‘鏄剧ず consensus missing / proxy used銆?- [ ] 鍗曞厓娴嬭瘯瑕嗙洊 key missing銆乸rovider success銆乸rovider stale銆乸rovider failed銆?
## 渚濊禆

- P1-C58
- P1-C60
- P3-C56
- P5-C68


