# P5-C49 / Dollar Liquidity v2.1 八区块 Radar Detail 展示

## 状态

DONE

## Execution Record

- DONE: frontend state priority and labels include dollar_liquidity v2.1 states.
- DONE: Radar Detail renders Data Freshness, Liquidity Level, Liquidity Impulse, Reserve Buffer, TGA/RRP Drain, Repo Funding Pressure, BTC Response Confirmation and Regime State.
- Verified: `npm run build` passed.

## 背景

`dollar_liquidity.v2.1` 前端展示需要避免单因子误导，把美元流动性拆成净流动性、资金压力与 BTC response。

## 目标

Radar Detail 页面为 `dollar_liquidity` 增加八区块展示。

## 展示区块

```text
1. Module State
   dollar_liquidity_state / module_direction / score / risk

2. Data Freshness
   weekly_macro_asof / daily_funding_asof / btc_price_asof / stale reasons

3. Liquidity Level
   Fed assets / TGA / ON RRP / reserves / net liquidity / rrp_depleted

4. Liquidity Impulse
   net liquidity 1w/4w change / impulse z / acceleration

5. Reserve Buffer
   reserves level / reserve change / buffer state

6. Liquidity Drain Pressure
   TGA change / ON RRP change / drain state

7. Repo Funding Pressure
   SOFR / IORB / SOFR-IORB spread / funding stress z

8. BTC Response Confirmation
   BTC 1d/5d/20d return / liquidity residual / response state
```

## UI 文案约束

- 不显示 “SOFR bearish”。
- 不显示 “ON RRP bullish/bearish”。
- 顶部标签优先使用 `dollar_liquidity_state`。
- raw metric 只作为 basis 展示。

## DoD

- `dollar_liquidity` detail 页展示八区块。
- 状态标签优先级：

```text
dollar_liquidity_state > display_state > module_direction fallback
```

- 页面能展示 `value` 与 `effective score`，不误导用户。
- 缺失字段显示空态，不导致页面报错。
- `npm run build` 通过。

## 验证建议

```powershell
npm run build
```
