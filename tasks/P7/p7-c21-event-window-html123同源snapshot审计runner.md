# P7-C21 / Event Window HTML 1/2/3 鍚屾簮 Snapshot 瀹¤ Runner

## 鐘舵€?
TODO

## 鑳屾櫙

褰撳墠 Event Window 涓変唤 HTML 瀹¤鎶ュ憡閮藉彲浠ョ敓鎴愶細

```text
HTML 1: reports/event-window-source-audit-report.html
HTML 2: reports/event-window-state-overlay-llm-audit-report.html
HTML 3: reports/event-window-shock-fast-lane-audit-report.html
```

浣嗙幇鐘舵槸涓変釜鑴氭湰鍚勮嚜璋冪敤涓€娆★細

```python
event_watchtower_daemon.collect_once()
```

杩欎細瀵艰嚧 HTML 1/2/3 鍙兘瀵瑰簲涓嶅悓鐨?`snapshot_id` / `asof_ts`銆備綔涓哄璁￠棴鐜紝瀹冧滑蹇呴』鍩轰簬鍚屼竴涓?Event Window payload锛屽惁鍒欐棤娉曡瘉鏄庘€滃悓涓€杞?pipeline鈥濅竴鑷淬€?
## 鐩爣

鏂板缁熶竴瀹¤ runner锛?
```text
scripts/run_event_window_audit_bundle.py
```

涓€娆℃€у畬鎴愶細

```text
collect_once
鍥哄畾 snapshot_id / asof_ts
鐢熸垚 HTML 1
鐢熸垚 HTML 2
鐢熸垚 HTML 3
鐢熸垚 bundle summary
涓€鑷存€у璁?```

## 鏍稿績璁捐

### 杈撳叆

```text
鏃犲弬鏁帮細榛樿閲囬泦涓€娆℃渶鏂?Event Window payload銆?鍙€?--snapshot-id锛氬熀浜?SQLite 宸插瓨鍦?snapshot replay 鐢熸垚銆?鍙€?--no-collect锛氫笉閲囬泦锛屽彧璇诲彇 latest snapshot銆?```

### 杈撳嚭

```text
reports/event-window-source-audit-report.html
reports/event-window-state-overlay-llm-audit-report.html
reports/event-window-shock-fast-lane-audit-report.html
reports/event-window-audit-bundle-summary.html
reports/event-window-audit-bundle-summary.json
```

### 涓€鑷存€ч棬鎺?
HTML 1/2/3 鍜?summary 蹇呴』灞曠ず锛?
```text
snapshot_id
asof_ts
payload_hash
schema_version
```

濡傛灉浠绘剰鎶ュ憡涓嶄竴鑷达細

```text
overall_status = FAIL
failures += ["html_snapshot_mismatch"]
```

## 杈圭晫

```text
HTML 鏂囦欢涓嶅弬涓庝笟鍔℃祦銆?HTML 鐢熸垚鍙互瑙﹀彂瀹¤閲囬泦锛屼絾蹇呴』鏄庣‘鍐欏叆 SQLite銆?UI 鍙互灞曠ず HTML 閾炬帴鍜屽璁℃憳瑕侊紝浣嗕笉鑳戒粠 HTML 鍙嶅悜璇诲彇涓氬姟鏁版嵁銆?```

## DoD

- [x] 鏂板 `scripts/run_event_window_audit_bundle.py`銆?- [x] runner 鍙皟鐢ㄤ竴娆?`collect_once()`銆?- [x] HTML 1/2/3 閮芥樉绀哄悓涓€涓?`snapshot_id`銆?- [x] HTML 1/2/3 閮芥樉绀哄悓涓€涓?`asof_ts`銆?- [x] 杈撳嚭 `reports/event-window-audit-bundle-summary.html`銆?- [x] 杈撳嚭 machine-readable `reports/event-window-audit-bundle-summary.json`銆?- [x] summary 鏄剧ず涓讳笟鍔￠摼鏉°€丼QLite銆丄PI銆丠TML 1/2/3 鐨?PASS/FAIL銆?- [x] 鑻?snapshot 涓嶄竴鑷达紝summary FAIL銆?- [x] 鏀寔 `--snapshot-id` replay 妯″紡銆?- [x] 娴嬭瘯鎴?smoke 鍛戒护瑕嗙洊 runner銆?
## 楠屾敹鍛戒护

```powershell
.\.venv\Scripts\python.exe scripts/run_event_window_audit_bundle.py
```

## 渚濊禆

- P7-C16
- P7-C17
- P9-C44

