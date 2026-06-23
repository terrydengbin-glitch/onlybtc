# P2-C31 / Dollar Liquidity v2.1 role、composite-only 与 risk-context registry

## 状态

DONE

## 背景

`dollar_liquidity` 旧 registry 容易把原始指标解释成单项方向：

```text
Fed balance sheet 高 -> bullish
SOFR 高 -> bearish
ON RRP 高 -> bearish
```

这会误导 BTC 趋势判断。v2.1 要求原始美元流动性指标只作为组合输入。

## 目标

调整 P2 registry，使 `dollar_liquidity` 指标进入角色型、组合型、风险型解释，不再单指标输出 BTC 多空。

## 指标角色

```text
fed_balance_sheet:
  role = liquidity_level
  direction = composite_only

bank_reserves:
  role = reserve_buffer
  direction = composite_only

on_rrp:
  role = liquidity_drain_pressure
  direction = composite_only

tga:
  role = liquidity_drain_pressure
  direction = composite_only

sofr:
  role = repo_funding_pressure
  direction = risk_context

iorb:
  role = repo_funding_pressure
  direction = context_only

net_liquidity_proxy_bil / net_liquidity_change_*:
  role = liquidity_impulse
  direction = composite_only

sofr_iorb_spread_bps / funding_stress_z:
  role = repo_funding_pressure
  direction = risk_context

btc_vs_liquidity_residual:
  role = btc_response_confirmation
  direction = composite_only
```

## DoD

- 原始指标 `fed_balance_sheet`、`bank_reserves`、`on_rrp`、`tga`、`sofr` 不再单独 `driver_eligible=true`。
- `SOFR` 只允许进入 funding pressure / risk context，不允许输出“SOFR 高所以 BTC bearish”。
- `ON_RRP` 在 depleted 低位时不允许继续给强 bullish 释放分。
- P2 输出包含 `dollar_liquidity.v2.1` 所需 roles。
- 测试覆盖 registry role、score bucket 与 driver eligibility。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radars.py -q
```

## Execution Record

- DONE: converted dollar_liquidity raw and derived metrics to role-based composite/risk context rules.
- DONE: disabled single-metric direction eligibility for Fed balance sheet, TGA, ON RRP, SOFR and IORB.
- Verified: target regression suite -> 124 passed.
