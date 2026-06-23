# P5-C44 / Options Volatility 五区块 Radar Detail 展示

## 状态

DONE

## 背景

前端不能把 `options_volatility` 显示成 Options Bullish / Bearish。它应该展示为期权风险结构模块，帮助用户理解波动、保护、尾部、到期与 pinning。

## 目标

Radar Detail 顶部显示：

```text
Options Structure: {options_short_term_state}
```

页面拆成五块：

```text
1. Volatility Pricing
   IV / RV / IV-RV Spread / IV Change

2. Protection Demand
   Put-Call Ratio / Skew Side / Skew Strength

3. Tail Risk
   Downside Tail / Upside Tail / Two-tail Fear

4. Expiry Pressure
   Expiry Days / Expiry Notional / Notional Z-score

5. Pinning Structure
   Max Pain Distance / Gamma Wall Distance / Wall Side
```

## UI 约束

- 不展示 `Options: Bullish / Bearish`。
- 不把 put-call、skew、max pain、gamma wall 放入方向驱动列表。
- 显示 `risk_score`、`confidence_adjustment`、`trade_permission_hint`。
- 数据缺失时展示 data quality degraded / missing，不展示强结论。

## DoD

- Radar Detail 对 `options_volatility` 使用五区块展示。
- Dashboard 节点显示结构状态，不显示方向判断。
- 移动端与桌面端文本不溢出、不重叠。
- 前端 build 通过。

## Tests

```powershell
npm run build
```
