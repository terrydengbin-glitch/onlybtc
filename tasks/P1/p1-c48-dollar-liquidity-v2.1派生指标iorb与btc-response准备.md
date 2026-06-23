# P1-C48 / Dollar Liquidity v2.1 派生指标、IORB 与 BTC response 准备

## 状态

DONE

## 背景

`dollar_liquidity` 需要从单项指标加权升级为美元净流动性、repo funding pressure 与 BTC 吸收/拒绝反应模块。

当前已有输入：

```text
fed_balance_sheet
bank_reserves
on_rrp
sofr
tga
```

但缺少 `IORB`、净流动性派生、周频/日频分层、SOFR spread 与 BTC response。

## 目标

为 `dollar_liquidity.v2.1` 准备 P1 数据与派生指标，使下游可以判断：

```text
美元净流动性的边际变化，是否正在被 BTC 价格确认、拒绝或反向吸收。
```

## 范围

- 新增或接入 `IORB` 数据源。
- 标准化以下频率层：
  - `weekly_macro_clock`: WALCL / TGA / reserves
  - `daily_funding_clock`: SOFR / IORB / ON RRP
  - `btc_response_clock`: BTC 1d / 5d / 20d return
- 新增派生指标：

```text
net_liquidity_proxy_bil
net_liquidity_change_1w_bil
net_liquidity_change_4w_bil
liquidity_impulse_z
liquidity_acceleration
reserve_change_1w_bil
tga_change_1w_bil
rrp_depleted
sofr_iorb_spread_bps
funding_stress_z
sofr_jump_1d_bps
btc_1d_return
btc_5d_return
btc_20d_return
btc_vs_liquidity_residual
```

## DoD

- P1 能采集或 fallback 生成 `iorb`。
- `net_liquidity_proxy_bil = WALCL - TGA - ON_RRP`，单位统一为 billion USD。
- 周频指标不与 5m/1h BTC 数据直接相减打分，只输出分层 asof。
- `rrp_depleted = true` 当 `on_rrp_bil < 50`。
- `sofr_iorb_spread_bps = (SOFR - IORB) * 100`。
- 缺少必要历史窗口时，派生指标不输出强错误值，并带质量/缺失说明。
- 单元测试覆盖：
  - net liquidity 1w/4w 变化。
  - RRP depleted。
  - SOFR-IORB spread。
  - BTC response return 派生。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py -q
```

## Execution Record

- DONE: added IORB source/metric and dollar-liquidity derived source registration.
- DONE: added net liquidity, impulse, reserve/TGA, SOFR-IORB, funding stress and BTC response derived metrics.
- Verified: `.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_radars.py backend\tests\test_p3_pipeline.py backend\tests\test_p45_dashboard_api.py backend\tests\test_p45_final_writer.py -q` -> 124 passed.
