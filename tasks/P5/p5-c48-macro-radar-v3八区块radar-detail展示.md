# P5-C48 / Macro Radar v3 八区块 Radar Detail 展示

## 状态

DONE

## 目标

前端 Radar Detail 为 `macro_radar.v3` 增加八区块展示，表达宏观环境如何确认、削弱或反证 BTC 4h-3d 趋势。

## 页面区块

```text
1. Equity Beta
2. Rates Pressure
3. Dollar Pressure
4. Volatility Stress
5. Financial Stress
6. Commodity Context
7. Macro Impulse
8. BTC Relative Confirmation
```

顶部显示：

```text
Macro Radar: {macro_trend_state}
BTC implication: {btc_implication}
Risk: {risk_score}
Confidence adjustment: {confidence_adjustment}
```

## UI 约束

- 不显示成 `Macro: Bullish/Bearish` 作为唯一主标签。
- DXY / VIX / Nasdaq / Gold / Oil 不单独展示为方向结论。
- `macro_tailwind_but_btc_lagging` 必须说明宏观顺风尚未被 BTC 吸收。
- `btc_resisting_macro_headwind` 必须说明 BTC 内生强度，不等于宏观转多。
- `macro_shock_risk` 展示为风险/交易许可提醒，而不是纯 bearish。

## DoD

- Radar Detail 可从 v3 payload、顶层字段或 `module_semantic_profile` fallback 读取。
- Dashboard 节点优先展示 `macro_trend_state`。
- 指标列表继续展示 `value / metric_score / metric_effective_score / quality`。
- 标签映射覆盖全部 `macro_trend_state`。
- `npm run build` 通过。

## Tests

```powershell
npm run build
```
