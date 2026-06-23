# P3-C40 / Taker Buy Sell Ratio 主动成交语义与方向分隔离

## 状态
DONE

## 背景

Run Once 审计发现 `taker_buy_sell_ratio=1.1486` 被 P3 通用 `semantic.radar_rule` 按 24h 下降打成 bearish pressure driver：

```text
semantic_rule_id = semantic.radar_rule
direction = bearish
metric_score < 0
```

但在 P2-C25 / P3-C37 语义中，taker ratio 代表主动成交压力，不是独立趋势确认信号。它应进入 `aggressive_flow_state`，再由 price response / liquidation / stablecoin context 组合确认。

## 目标

- 为 `trade_structure_flow.taker_buy_sell_ratio` 增加 P3 专属语义覆写。
- taker ratio 不再回落到通用 `semantic.radar_rule`。
- Evidence 明确输出 `aggressive_flow_state`。
- taker ratio 本身作为确认上下文，默认不直接贡献 bullish / bearish metric_score。

## DoD

- `taker_buy_sell_ratio` 的 `semantic_rule_id` 不再是 `semantic.radar_rule`。
- `taker_buy_sell_ratio=1.1486` 输出 `aggressive_flow_state=buying_pressure`。
- taker ratio 的 `direction=neutral`、`metric_score=0.0`，不因 24h 下降单独进入 bearish pressure driver。
- 单元测试覆盖主动买压但方向隔离的 Evidence 输出。

## Execution Notes

- 新增 `semantic.trade_structure.aggressive_flow_context` 专属语义覆写。
- `taker_buy_sell_ratio` 现在只输出主动成交压力上下文：
  - `aggressive_flow_state`
  - `signal_type=confirmation_context`
  - `direction=neutral`
  - `metric_score=0.0`
- 该指标不再因为 `change_24h` 下降而回落到通用 `semantic.radar_rule` 并成为 bearish pressure driver。
- `_semantic_result` 与 scored metric evidence 增加 `aggressive_flow_state` 透传字段。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_radars.py backend\tests\test_p3_pipeline.py backend\tests\test_p45_final_writer.py backend\tests\test_p45_evidence_pack.py backend\tests\test_p45_dashboard_api.py -q
```

结果：

```text
28 passed
101 passed
```
