# P1-C60 / Event Window v3.1 Cleveland Fed Nowcast Parser

## 鐘舵€?
DONE

## Phase

P1 鏁版嵁婧愭帴鍏ヤ笌閲囬泦灞?
## 鑳屾櫙

褰撳墠 Cleveland Fed Inflation Nowcasting 椤甸潰鍙互璁块棶锛屼絾瑙ｆ瀽鍣ㄥ彧杩斿洖 `partial`锛屾病鏈夋娊鍙?CPI / Core CPI / PCE / Core PCE 鐨?nowcast 鏁板€笺€傝繖涓棶棰樹笉鏄簮涓嶅彲鐢紝鑰屾槸瑙ｆ瀽鍣ㄦ柇銆?
## 鐩爣

鎶?Cleveland Fed nowcast 浠庨〉闈㈠彲璁块棶鍗囩骇涓虹粨鏋勫寲 nowcast provider锛岀敤浜庝簨浠剁獥鍙ｇ殑棰勬湡婕傜Щ鍜岄€氳儉涓婅/涓嬭椋庨櫓棰勮銆?
## 鏁版嵁婧?
```text
Cleveland Fed Inflation Nowcasting
source_tier = official_nowcast
access_method = html_table
fallback_access_method = playwright_text_content
```

## 杈撳嚭濂戠害

```json
{
  "provider": "cleveland_fed_inflation_nowcasting",
  "source_tier": "official_nowcast",
  "updated_date": "",
  "period": "",
  "monthly_mom": {
    "cpi": null,
    "core_cpi": null,
    "pce": null,
    "core_pce": null
  },
  "monthly_yoy": {},
  "quarterly_annualized": {},
  "data_quality": "ok|partial|stale|failed",
  "data_quality_flags": [],
  "source_lineage": []
}
```

## 瀹炵幇瑕佹眰

```text
1. 浼樺厛 requests + pandas.read_html / BeautifulSoup 瑙ｆ瀽琛ㄦ牸銆?2. 澶辫触鏃跺啀浣跨敤 Playwright text_content 鍏滃簳銆?3. 涓嶅厑璁歌嚜鐢辨枃鏈ぇ姝ｅ垯鎵叏椤靛悗璇厤鏁板€笺€?4. 鑷冲皯瑙ｆ瀽 monthly_mom 涓?CPI/Core CPI/PCE/Core PCE 浠绘剰涓€缁勯潪绌恒€?5. updated_date 瓒呰繃 2 涓伐浣滄棩鏃舵爣璁?stale銆?6. 瑙ｆ瀽澶辫触蹇呴』鍐?source_fetch lineage 鍜?data_quality_flags銆?```

## DoD

- [ ] `/api/event-window/latest` 涓?`expectation_monitor.nowcast` 涓嶅啀鍥犱负瑙ｆ瀽澶辫触鎭掍负 null銆?- [ ] `cleveland-fed-nowcast` fetch 鐘舵€佷粠 `partial parsed=0` 鍙樹负 `success parsed>0` 鎴栨槑纭?`failed/stale`銆?- [ ] 杈撳嚭 raw_html_hash / parsed_rows / updated_date銆?- [ ] 娌℃湁 consensus 鏃讹紝鍙緭鍑?`nowcast_risk`锛屼笉璁＄畻 actual-vs-consensus surprise銆?- [ ] 鍗曞厓娴嬭瘯瑕嗙洊 HTML 琛ㄦ牸銆丣S fallback銆乻tale銆佽В鏋愬け璐ャ€?
## 渚濊禆

- P1-C58
- P8-C35
- P9-C43


