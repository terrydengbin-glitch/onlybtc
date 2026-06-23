# P3-C31 / Kline 派生指标单项方向与组合分解释一致性修复

## 状态
DONE

## 优先级
P0

## 所属 Phase
P3 算法、事件窗口与评分层

## 背景
P3-C29 已经把 `kline_orderflow` 从原始 OHLCV 加权升级为量价结构组合评分，P3-C30 已补上 Kline 派生指标入链守门。

最新审计发现：模块级组合输出基本符合预期，但 Evidence 层存在可读性问题。部分单项 return 指标自身为负，却因为继承模块级 `price_trend_score` 而显示为 `bullish`。

典型样本：

```text
btc_return_1h = -0.00023458478757365508
btc_return_4h = 0.00976079820307496
btc_return_24h = -0.01654616796146502
trend_state = neutral_wait_confirm
```

修复目标是：单项指标展示自身方向，模块组合状态继续由 `semantic.kline_orderflow.composite` 决定。

## 已完成实现

1. `backend/src/onlybtc/algorithms/p3.py`
   - Kline return 类指标改为使用自身 return 计算 `metric_score`：
     - `btc_return_1h` 使用 `ret_1h / 0.02`
     - `btc_return_4h` 使用 `ret_4h / 0.04`
     - `btc_return_24h` 使用 `ret_24h / 0.08`
   - 保留模块组合解释字段：
     - `module_composite_score`
     - `module_composite_direction`
     - `module_composite_state`
     - `kline_composite_contribution`
   - 新增单项解释字段：
     - `metric_self_direction`
     - `metric_self_score`
   - `score_reason` 明确写入 self direction 与 composite state 的区别。

2. `backend/src/onlybtc/p45/evidence_pack.py`
   - P4.5 Evidence Pack 保留 Kline 单项方向与组合解释字段，避免报告层丢失语义。

3. `frontend/src/App.vue`
   - Evidence 列表和弹窗优先展示 `metric_self_direction`。
   - Kline 指标额外显示 `module_composite_state`、`module_composite_direction` 与 `kline_composite_contribution`，避免把组合贡献误读为单项方向。

4. `backend/tests/test_p3_pipeline.py`
   - 新增回归测试：
     - `btc_return_1h < 0` 时单项方向必须为 `bearish`
     - `btc_return_24h < 0` 时单项方向必须为 `bearish`
     - `btc_return_4h > 0` 时单项方向必须为 `bullish`
     - 模块组合状态仍可保持 `neutral_wait_confirm`

## DoD

- [x] `btc_return_1h < 0` 时 Evidence 不再显示为单项 `bullish`。
- [x] `btc_return_24h < 0` 时 Evidence 不再显示为单项 `bullish`。
- [x] 模块级 `kline_orderflow.trend_state` 仍由组合规则决定，不被单项方向覆盖。
- [x] `semantic.kline_orderflow.composite` 保留 `price_trend_score`、`volume_confirmation_score`、`candle_structure_score`、`trend_state`。
- [x] P4.5 Evidence Pack 能区分单项方向和组合状态。
- [x] P5 Evidence/Radar Detail 页面不再把 Kline 单项负 return 误导展示为单项 bullish。
- [x] 增加回归测试覆盖负 return + 组合待确认样本。
- [x] P3 / P4.5 / Frontend build 相关测试通过。

## 测试

```text
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py -q
19 passed

.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_evidence_pack.py backend/tests/test_p45_html_report.py backend/tests/test_p45_dashboard_api.py -q
12 passed

npm run build
built successfully
```

## 关联任务

- P3-C29
- P3-C30
- P3-C25
- P4.5-C21
- P5-C17
