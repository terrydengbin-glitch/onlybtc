# P1-C62 / Event Window v3.1 BLS Calendar Provider Fallback Mesh

## 鐘舵€?
DONE

## Execution Record

### 2026-06-23 / Completion

- Standardized blocked BLS calendar diagnostics to `provider_failed_access_blocked`.
- Added provider/confidence/blocked_provider fields to calendar source fetch payloads.
- Added BLS official success event contract fields for ICS-derived events.
- Added FRED official_mirror source lineage showing blocked BLS plus active mirror fallback.
- Added versioned manual override metadata: `override_version`, `updated_at`, `source_note`.
- Added UI fallback notice for active Event Window calendar fallback states.
- Audit report: `reports/p1-c62-event-window-bls-calendar-fallback-mesh-audit.md`.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "bls_calendar" -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "actual_provider or reaction_requires or bls_calendar" -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower_offline.py -q
npm run build
```

Result:

- P1-C62 focused tests: 4 passed.
- P1-C61/P1-C62 combined focused tests: 8 passed.
- Event Watchtower offline regression: 4 passed.
- Frontend build: passed.

## Phase

P1 鏁版嵁婧愭帴鍏ヤ笌閲囬泦灞?
## 鑳屾櫙

BLS release HTML / ICS 鏄畼鏂规棩鍘嗘簮锛屼絾褰撳墠鐜璁块棶 403銆備簨浠剁獥鍙ｄ笉鑳藉洜姝ゅけ鍘?CPI/NFP/JOLTS/PPI 鐨勫€掕鏃惰兘鍔涳紝涔熶笉鑳芥妸 fallback 浼鎴?official live銆?
## 鐩爣

寤虹珛 BLS calendar provider fallback mesh锛岃 BLS 瀹樻柟婧愯璁块棶闄愬埗鏃讹紝鑷姩闄嶇骇鍒?official mirror / secondary calendar / manual override銆?
## Provider 浼樺厛绾?
```text
1. BLS official release HTML page
2. BLS ICS
3. FRED release dates API / CSV fallback
4. CME economic release calendar
5. secondary calendar provider
6. manual override yaml
```

## 杈撳嚭濂戠害

```json
{
  "event_id": "",
  "event_type": "CPI|NFP|JOLTS|PPI|ECI",
  "release_time": "",
  "source_tier": "official|official_mirror|secondary_calendar|manual_override",
  "provider": "",
  "original_authority": "BLS",
  "calendar_confidence": 0.0,
  "blocked_provider": "",
  "blocked_reason": "",
  "fallback_used": false,
  "source_lineage": []
}
```

## 瀹炵幇瑕佹眰

```text
1. 403 蹇呴』璁板綍涓?provider_failed_access_blocked銆?2. FRED release dates 鍙兘鏍囪 official_mirror銆?3. CME / secondary calendar 鍙兘鏍囪 secondary_calendar銆?4. manual yaml 蹇呴』鏈?version銆乽pdated_at銆乻ource_note銆?5. UI 蹇呴』鑳芥樉绀?鈥淏LS official blocked, using mirror/secondary source鈥濄€?```

## DoD

- [x] BLS 瀹樻柟琚?403 鏃朵粛鑳界敓鎴?CPI/NFP/JOLTS/PPI 鏈潵浜嬩欢銆?- [x] fallback 浜嬩欢涓嶆樉绀烘垚 `official_bls_live`銆?- [x] source diagnostics 鑳界湅鍒?blocked provider 鍜?active fallback provider銆?- [x] calendar_quality 鎷嗗垎涓?`ok|partial|fallback|missing|blocked`銆?- [x] 鍗曞厓娴嬭瘯瑕嗙洊 official success銆?03 fallback銆佹墍鏈?provider failed銆?
## 渚濊禆

- P1-C57
- P8-C35
- P9-C43
- P5-C68


