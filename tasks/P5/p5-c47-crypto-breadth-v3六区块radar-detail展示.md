# P5-C47 / Crypto Breadth v3 六区块 Radar Detail 展示

## 状态

DONE

## 目标

前端 Radar Detail 为 `crypto_breadth` 增加 v3 六区块展示，清晰表达 BTC 趋势确认、市场宽度、资金扩散、领导权切换、板块热度与宽度质量。

## 页面区块

```text
1. BTC Trend Anchor
2. Breadth Participation
3. Market Cap Diffusion
4. BTC vs Alt Leadership
5. Sector Risk Appetite
6. Breadth Quality / Divergence
```

顶部显示：

```text
Crypto Breadth: {crypto_breadth_state}
BTC implication: {btc_implication}
```

## UI 约束

- 不显示成 `Crypto Breadth: Bullish/Bearish`。
- BTC.D / ETHBTC / sector heat 不单独展示为方向结论。
- `alt_beta_rotation` 文案必须说明：支持 crypto risk-on，但不等于 BTC 跑赢。
- `alt_chase_overheat` 显示为风险/追高提醒。

## DoD

- Radar Detail 能从 `crypto_breadth_v3`、顶层字段或 `module_semantic_profile` fallback 读取。
- Dashboard 节点优先展示 `crypto_breadth_state`。
- 指标面板继续显示 `value / metric_score / metric_effective_score / quality`。
- `npm run build` 通过。

## Tests

```powershell
npm run build
```

## Verification

```powershell
npm run build
```
