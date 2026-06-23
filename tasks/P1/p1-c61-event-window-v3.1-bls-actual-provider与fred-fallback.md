# P1-C61 / Event Window v3.1 BLS Actual Provider 涓?FRED Fallback

## 鐘舵€?
DONE

## Execution Record

### 2026-06-23 / Start

- 用户要求继续，按优先级启动 P1-C61。
- 当前卡片历史状态为 `PARTIAL PASS - provider implemented; live post-release actual pending`。
- 本次先核查 provider / fallback / pending / source lineage 的代码与测试状态，再决定是补实现还是补验收回填。
- 约束：不把 FRED fallback 伪装成 BLS official live；actual 未发布时必须保持 pending，不允许历史值冒充 actual。

### 2026-06-23 / Completion

- Implemented top-level actual snapshot contract fields: `provider`, `source_tier`, `metric_group`, `latest_observation`, `previous_observation`, `observation_date`, `release_ts`, `actual_status`, `fallback_used`, `source_lineage`.
- Added source lineage provider metadata: `provider`, `confidence`, and `blocked_provider` for BLS failed paths; FRED remains `source_tier=official_mirror`.
- Added observation-period guard so stale historical BLS/FRED values remain `actual_status=not_released` instead of being promoted to current actual.
- Tightened post-event reaction so `actual` and `surprise_raw` are computed only when `actual_status=available`.
- Added deterministic tests for BLS success, BLS blocked/FRED fallback, stale actual pending, and reaction status gating.
- Audit report: `reports/p1-c61-event-window-bls-actual-provider-audit.md`.

Verification:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower.py -k "actual_provider or reaction_requires" -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_event_watchtower_offline.py -q
.\.venv\Scripts\python.exe -m compileall backend\src\onlybtc\event_window\connectors\actuals.py backend\src\onlybtc\event_window\connectors\reactions.py backend\tests\test_event_watchtower.py
```

Result:

- P1-C61 focused tests: 4 passed.
- Event Watchtower offline regression: 4 passed.
- Compile check: passed.
- Full `backend\tests\test_event_watchtower.py` was not used as the P1-C61 gate because existing live connector paths can block on external providers; deterministic provider/reaction contract tests cover this card.

## Phase

P1 鏁版嵁婧愭帴鍏ヤ笌閲囬泦灞?
## 鑳屾櫙

BLS schedule / ICS 鍦ㄥ綋鍓嶇幆澧冭繑鍥?403锛屼絾 BLS Public Data API 鏄畼鏂?actual 鏁版嵁婧愶紝鍙敤浜?CPI銆丯FP銆丣OLTS銆丳PI 绛夋寚鏍囩殑 latest observation銆侳RED CSV 鍙綔涓哄畼鏂归暅鍍?浜岀骇 fallback銆?
## 鐩爣

涓?BLS 绫讳簨浠惰ˉ actual provider锛岀‘淇濅簨浠跺彂甯冨悗鑳藉尯鍒嗭細

```text
actual_not_released
provider_failed
actual_available
fallback_used
```

## 鏁版嵁婧愪紭鍏堢骇

```text
1. BLS Public Data API
2. FRED fredgraph.csv fallback
```

## 鎸囨爣鏄犲皠

```text
CPI headline: CPIAUCSL / BLS CPI series
Core CPI: CPILFESL
NFP payrolls: PAYEMS / BLS CES series
Unemployment: UNRATE
Average hourly earnings: CES0500000003
JOLTS openings: JTSJOL
PPI final demand: PPIFIS
```

## 杈撳嚭濂戠害

```json
{
  "provider": "bls_api|fred_fallback",
  "source_tier": "official|official_mirror",
  "event_id": "",
  "metric_group": "CPI|NFP|JOLTS|PPI",
  "latest_observation": null,
  "previous_observation": null,
  "observation_date": "",
  "release_ts": "",
  "actual_status": "available|not_released|provider_failed",
  "fallback_used": false,
  "source_lineage": []
}
```

## 瀹炵幇瑕佹眰

```text
1. BLS API timeout/403/empty 涓嶅緱闈欓粯鍚炴帀銆?2. FRED fallback 蹇呴』鏍囪 source_tier=official_mirror锛屼笉寰楁樉绀烘垚 BLS official live銆?3. actual 鏈彂甯冩椂淇濈暀 pending锛屼笉鍑嗗～鍘嗗彶鍊煎啋鍏?actual銆?4. post-event reaction 鍙兘鍦?actual_status=available 鍚庤绠?surprise銆?```

## DoD

- [x] CPI/NFP/JOLTS/PPI 浠讳竴浜嬩欢鑳借繑鍥?latest + previous observation銆?- [x] BLS API 澶辫触鏃?FRED fallback 鍙敤骞惰褰?blocked_provider銆?- [x] `actual_not_released` 涓?`provider_failed` 鍙尯鍒嗐€?- [x] source fetch lineage 鏄剧ず provider銆乻ource_tier銆乫allback_used銆乧onfidence銆?- [x] 鍗曞厓娴嬭瘯瑕嗙洊 BLS success銆丅LS fail/FRED success銆乤ctual pending銆?
## 渚濊禆

- P1-C59
- P8-C35
- P9-C43


