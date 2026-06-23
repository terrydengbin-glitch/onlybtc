# P5-C69 / Event Window v3.1 Source Mesh UI

## 鐘舵€?
DONE

## Phase

P5 Vue3 鍓嶇灞曠ず

## 鑳屾櫙

浜嬩欢瀛愰〉闈㈠凡缁忚兘鏄剧ず Source Status锛屼絾 v3.1 闇€瑕佽繘涓€姝ユ樉绀?provider fallback mesh銆乸roxy銆乵issing銆乨isabled capabilities锛岄伩鍏嶇敤鎴疯浠ヤ负 partial live 鏄郴缁熷け璐ユ垨 fake live銆?
## 鐩爣

鍦ㄤ簨浠跺瓙椤甸潰涓睍绀哄垎灞?source quality 鍜?provider fallback 璇︽儏銆?
## UI 鍖哄潡

```text
Source Quality Strip:
  calendar / actual / nowcast / consensus / fedwatch / speech

Provider Mesh:
  official live
  official mirror
  secondary
  proxy
  missing
  failed

Disabled Capabilities:
  release_surprise_disabled
  official_fedwatch_unavailable
  actual_pending
```

## DoD

- [ ] 浜嬩欢椤垫樉绀?`partial_live`锛岃€屼笉鏄畝鍗?failed銆?- [ ] BLS 403 鏃舵樉绀?blocked provider 涓?active fallback provider銆?- [ ] consensus missing 鏃舵樉绀?鈥渟urprise disabled, nowcast risk only鈥濄€?- [ ] FedWatch proxy 鏃舵樉绀?鈥淔ed Funds futures proxy, not CME FedWatch鈥濄€?- [ ] `npm run build` 閫氳繃銆?
## 渚濊禆

- P3-C57
- P9-C43
- P5-C68


