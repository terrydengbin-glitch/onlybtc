# P8-C21 / Crypto Breadth v3 payload 持久化与 replay

## 状态

DONE

## 目标

确保 `crypto_breadth.v3` 的结构化 payload 能进入 SQLite、P4.5 final snapshot 和 History Replay。

## 范围

持久化字段：

```text
crypto_breadth_state
btc_implication
btc_trend_anchor
breadth_participation
market_cap_diffusion
btc_vs_alt_leadership
sector_risk_appetite
breadth_quality
confidence_adjustment
risk_score
support_drivers
pressure_drivers
risk_drivers
context_notes
```

## DoD

- 最新 run 与历史 replay 均能读取 v3 payload。
- 历史模式不被当前实时状态覆盖。
- 旧版 `p3.c28.crypto_breadth.v1` payload 仍可兼容显示。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py backend\tests\test_database.py -q
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
```
