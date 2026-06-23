# P2-C24 / Derivatives Long/Short Ratio 指标注册与语义契约

## 状态

DONE

## 背景

P1-C39 会新增 Binance BTCUSDT long/short ratio 指标。P2 需要把这些指标纳入 `derivatives_crowding`，并明确它们和 `btc_open_interest`、`btc_funding_rate`、`taker_buy_sell_ratio` 的区别。

## 目标

1. 将新增 long/short ratio 指标注册到 Radar metric。
2. 默认归属 `derivatives_crowding`。
3. 设置 horizon、module weight、duplicate group。
4. 明确账户多空比、仓位多空比、主动买卖比、总 OI 的语义边界。
5. 不把 long/short ratio 单独解释成趋势确认。

## 指标角色

```text
btc_global_long_short_account_ratio:
  role = positioning_sentiment
  meaning = 全市场账户多空偏斜

btc_top_long_short_account_ratio:
  role = top_trader_account_bias
  meaning = 大户账户多空偏斜

btc_top_long_short_position_ratio:
  role = top_trader_position_bias
  meaning = 大户仓位多空偏斜，优先用于拥挤判断

btc_open_interest:
  role = leverage_size
  meaning = 总杠杆规模，不含多空方向

taker_buy_sell_ratio:
  role = aggressive_flow
  meaning = 主动买卖流，不等于持仓多空
```

## Horizon / Duplicate

建议：

```text
horizon_tags = h24, d3
duplicate_group_id = derivatives_long_short_ratio_btc
module_weight = derivatives_crowding 内中等权重
```

其中：

- global account ratio 权重最低。
- top account ratio 中等。
- top position ratio 最高。

## P2 输出建议

在 `derivatives_crowding` 模块补充：

```json
{
  "long_short_positioning_state": "long_skew|short_skew|balanced|extreme_long|extreme_short",
  "top_trader_bias_state": "top_long_skew|top_short_skew|balanced",
  "positioning_conflict_level": "none|low|medium|high"
}
```

## DoD

- [ ] 新增 long/short ratio 指标进入 `derivatives_crowding`。
- [ ] P2 Radar quality 不出现 uncovered metric。
- [ ] P2 输出能区分 total OI、account ratio、position ratio、taker flow。
- [ ] `btc_open_interest` 仍只表示总 OI。
- [ ] P2 HTML 能展示新增指标的 source / value / freshness。
- [ ] P2 测试通过。

## 关联

P1-C39, P2-C22, P3-C32, P3-C34, P4.5-C24

## Completion Note

- Done: derivatives_crowding registry, horizon tags, duplicate group, semantic roles.
- Verified: backend source/radar/P3/P4.5/API tests passed.
