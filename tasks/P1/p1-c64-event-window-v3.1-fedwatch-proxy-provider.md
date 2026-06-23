# P1-C64 / Event Window v3.1 FedWatch Proxy Provider

## 鐘舵€?
DONE

## Phase

P1 鏁版嵁婧愭帴鍏ヤ笌閲囬泦灞?
## 鑳屾櫙

CME FedWatch 椤甸潰褰撳墠 403锛屽畼鏂?FedWatch API 灞炰簬鍟嗕笟 API銆傛病鏈?CME API key 鏃讹紝搴斾娇鐢?Fed Funds futures / EFFR proxy 鍋氬競鍦洪殣鍚埄鐜囪矾寰勯璀︼紝骞舵槑纭爣璁颁负 proxy銆?
## 鐩爣

瀹炵幇涓ゆ。 FedWatch provider锛?
```text
A 妗ｏ細CME FedWatch API key 鍙敤
  source_tier = official_market_implied

B 妗ｏ細鏃?CME key
  source_tier = market_implied_proxy
  provider = zq_futures_proxy
```

## Proxy 杈撳叆

```text
ZQ futures quote:
  Yahoo Finance / TradingView / Stooq / broker feed

EFFR:
  NY Fed / FRED DFF/EFFR

FOMC calendar:
  Fed official page
```

## Proxy 杈撳嚭濂戠害

```json
{
  "provider": "cme_fedwatch_api|zq_futures_proxy",
  "source_tier": "official_market_implied|market_implied_proxy",
  "fedwatch_proxy_used": true,
  "implied_avg_rate": null,
  "current_effr": null,
  "expected_change_bps": null,
  "cut_25bp_probability_proxy": null,
  "warning": "not_cme_fedwatch_probability",
  "source_lineage": []
}
```

## 瑙勫垯

```text
CME API 鍙敤:
  杈撳嚭 official FedWatch probability

CME API 涓嶅彲鐢?
  杈撳嚭 proxy probability
  绂佹浣跨敤瀛楁鍚?`fedwatch_probability`
  UI 鏄剧ず 鈥淔ed Funds futures proxy鈥?```

## DoD

- [ ] 鏃?CME key 鏃朵笉鍐嶆妸 FedWatch 鏍囪 failed-only锛岃€屾槸杈撳嚭 proxy/missing 鍒嗗眰銆?- [ ] proxy 杈撳嚭 implied_avg_rate / expected_change_bps銆?- [ ] UI 鏄庣‘鏄剧ず proxy锛屼笉鏄剧ず CME official probability銆?- [ ] source lineage 璁板綍 zq_source / effr_source / confidence銆?- [ ] 鍗曞厓娴嬭瘯瑕嗙洊 CME success銆丆ME missing/proxy success銆乤ll failed銆?
## 渚濊禆

- P1-C58
- P1-C57
- P8-C35
- P9-C43


