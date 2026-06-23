# P9-C26 / Crypto Breadth v3 API 透传与契约

## 状态

DONE

## 目标

FastAPI Radar Module Detail / Dashboard / History API 透传 `crypto_breadth.v3` 结构化字段。

## 范围

接口：

```text
GET /api/p45/radar-modules/crypto_breadth
GET /api/p45/radar-modules/latest
GET /api/p45/dashboard/latest
GET /api/p45/history/{final_run_id}
```

必须透传：

```text
crypto_breadth_v3
crypto_breadth_state
btc_implication
btc_trend_anchor
breadth_participation
market_cap_diffusion
btc_vs_alt_leadership
sector_risk_appetite
breadth_quality
crypto_breadth_explanation
```

## DoD

- API 返回字段与 P3/P4.5 payload 一致。
- 缺少 v3 时 fallback 到旧 `crypto_breadth_regime`。
- 前端不需要从 raw metrics 反推 v3 状态。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
```
