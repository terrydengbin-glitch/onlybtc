# P3-C39 / Trade Structure Price Response 口径一致性修复

## 状态
DONE

## 背景

Run Once 审计发现 `trade_structure_flow` 的模块级 `price_response_state` 与指标级 Evidence `price_response_state` 存在分叉：

```text
module.price_response_state = upside_response
metric.btc_return_5m.price_response_state = neutral
```

同一组 `taker_buy_sell_ratio`、5m/15m return、close_position 输入不应在模块层和指标层输出不同确认结论。

## 目标

- 模块级 `_price_response_state` 与指标级 `_trade_structure_price_response_detail` 使用一致的阈值与状态语义。
- `1.12 <= taker_buy_sell_ratio <= 1.30` 的中等主动买压不得直接升级为 `upside_response`。
- 中等主动成交可输出 `weak_upside_response` / `weak_downside_response`，但不能触发 `bullish_confirmation` / `bearish_confirmation`。
- P3 Evidence 与 Radar Module Detail API 透传字段保持同口径。

## DoD

- 当前审计样本不再出现模块 `upside_response`、指标 `neutral` 的分叉。
- `taker_buy_sell_ratio=1.1486` 且 5m/15m 正收益时，模块和指标应输出同一个弱确认状态。
- 强买压 `taker_buy_sell_ratio > 1.30` 仍可在 5m/15m price response 完整确认后输出 `upside_response`。
- 单元测试覆盖强确认、弱确认和 fallback 场景。

## Execution Notes

- `_price_response_state` 改为复用 `_trade_structure_price_response_detail`，模块层和指标层共享同一套状态判断。
- `1.12 <= taker_buy_sell_ratio <= 1.30` 的中等主动成交压力在价格同向时输出 `weak_upside_response` / `weak_downside_response`，不再直接升级为强确认。
- 审计样本形态现在输出：
  - `aggressive_flow_state=buying_pressure`
  - `price_response_state=weak_upside_response`
  - `trade_structure_state=buy_pressure_unconfirmed`
  - `confirmation_state=unconfirmed`

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
