# P5-C41 / Derivatives Long/Short Ratio 前端展示与语义防误导

## 状态

DONE

## 背景

新增 long/short ratio 后，前端不能只展示为“多头比例高 = bullish”。Dashboard 与 Radar Detail 需要显示它是“仓位偏斜 / 拥挤风险 / 挤压风险”的证据。

## 目标

1. Dashboard derivatives card 显示 positioning state。
2. Radar Detail derivatives 页面展示 global/top account/top position 三组比例。
3. 指标节点颜色按语义展示：balanced、long crowded、short crowded、squeeze risk。
4. Evidence 弹窗显示 source/freshness/ratio 解释。
5. 文案避免把 long/short ratio 当成 long OI / short OI。

## 展示建议

Derivatives 卡片：

```text
拥挤状态：not_crowded / long_crowded / short_crowded
仓位偏斜：top_long_skew / top_short_skew / balanced
挤压风险：none / short_squeeze_risk / long_squeeze_risk
```

Radar Detail 指标：

```text
Global account L/S
Top account L/S
Top position L/S
Total OI
Funding
```

## DoD

- [ ] Dashboard derivatives card 不再只用 `module_effective_direction`。
- [ ] Radar Detail 能看到 long/short ratio 三组指标。
- [ ] Evidence 弹窗能解释 ratio 和 OI 的区别。
- [ ] 旧 run 缺字段时页面有空态，不出现 `[object Object]` 或 API error 噪音。
- [ ] `npm run build` 通过。

## 关联

P5-C17, P5-C39, P9-C20, P4.5-C24

## Completion Note

- Done: Dashboard and Radar Detail prioritize crowding/positioning/squeeze semantics over raw effective direction.
- Verified: `npm run build` passed.
