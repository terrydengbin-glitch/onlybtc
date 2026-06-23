# P2-C29 / Crypto Breadth v3 指标角色与 composite-only 契约

## 状态

DONE

## 目标

将 `crypto_breadth` 的指标角色升级为 v3 分层契约，避免 `btc_dominance`、`eth_btc`、`sector_heat` 单项直接生成 bullish/bearish 结论。

## 范围

为指标补充 role / scope：

```text
btc_trend_anchor
breadth_participation
market_cap_diffusion
btc_vs_alt_leadership
sector_risk_appetite
breadth_quality
```

建议：

```text
btc_dominance:
  direction = composite_only
  driver_eligible = false

eth_btc:
  direction = composite_only
  driver_eligible = false

sector_heat:
  direction = risk_context
  driver_eligible = false

top50_advance_pct / top50_strength:
  role = breadth_participation

total2_return:
  role = market_cap_diffusion
```

## DoD

- `crypto_breadth` registry 能区分 raw metric 与 derived state metric。
- BTC.D / ETHBTC / sector heat 不再单独作为 support/pressure driver。
- P2 输出中保留 role、affects_signal、driver_eligible、score_bucket 等字段。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radars.py -q
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```
