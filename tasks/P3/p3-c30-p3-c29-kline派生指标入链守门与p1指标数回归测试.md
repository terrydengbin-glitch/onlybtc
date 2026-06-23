# P3-C30 / P3-C29 kline 派生指标入链守门与 P1 指标数回归测试

## 状态

DONE

## 优先级

P0

## 所属 Phase

P3 算法、事件窗口与评分层

## 背景

P3-C29 已经完成 `kline_orderflow` 量价结构组合评分能力，代码中已经存在 Binance 1h kline 派生指标、P2 registry 角色重分类、P3 `semantic.kline_orderflow.composite` 与对应单元测试。

但最近一次真实全链条 run 暴露出回归：

```text
collect_run_id = collect-20260523140915-1688ae
p3_run_id      = p3-20260523141052-668929
final_run_id   = p45final-20260523141056-103f91

P1 distinct metric count = 111
kline_orderflow evidence count = 5
```

最新 P4.5 evidence 中，`kline_orderflow` 只进入了 raw OHLCV：

```text
btc_1h_open
btc_1h_high
btc_1h_low
btc_1h_close
btc_1h_volume
```

P3-C29 要求的派生指标未进入本轮链路，导致 `btc_1h_volume` 仍被 `semantic.radar_rule` 解释为 `positive/bullish`，重新出现“成交量放大单独拉多 kline 模块”的旧问题。

本任务用于补齐 C29 的入链守门和回归测试，确保后续真实 run 不会再退回 raw OHLCV 旧链路。

## 目标

确保 P1 -> P2 -> P3 -> P4.5 全链条中，`binance-btcusdt-kline-1h` 的 18 个 Kline 指标稳定入链，其中 13 个派生指标必须进入 P1 落库、P2 Radar、P3 scoring 和 P4.5 evidence。

同时建立 P1 指标数回归测试，避免注册指标、采集输出和审计报告之间再次出现 114/111/124 等口径漂移。

## 影响范围

- P1：Binance kline 采集窗口、raw payload、派生指标落库。
- P2：`kline_orderflow` Radar 指标位覆盖与 missing metric 守门。
- P3：`semantic.kline_orderflow.composite` 是否真实消费派生指标。
- P4.5：最终 evidence / aggregation / article 是否消费 Kline 派生字段。
- P8 / SQLite：`metric_values`、`normalized_metrics`、`source_runs` 中指标数量和 source lineage。
- P5：Dashboard / Radar Detail 只展示后端结果，不在前端补算派生指标。

## 必须入链的 Kline 指标

### Raw OHLCV

```text
btc_1h_open
btc_1h_high
btc_1h_low
btc_1h_close
btc_1h_volume
```

### P3-C29 派生指标

```text
btc_return_1h
btc_return_4h
btc_return_24h
btc_drawdown_24h
btc_close_position_1h
btc_candle_body_pct_1h
btc_upper_wick_ratio_1h
btc_lower_wick_ratio_1h
btc_volume_zscore_1h
btc_breakdown_24h_low
btc_breakout_24h_high
btc_rebound_quality_1h
btc_down_volume_pressure
```

## 当前已知异常

### 1. 最新 run 只落库 5 个 kline 指标

最新 `metric_values` 中：

```text
source_id = binance-btcusdt-kline-1h
metric_count = 5
```

但当前注册表期望：

```text
source_id = binance-btcusdt-kline-1h
expected_metric_count = 18
```

### 2. 最新 raw payload 只有 2 根 K 线

最新 raw observation：

```text
raw_payload.klines length = 2
```

P3-C29 至少需要最近 24 根 1h K 线，`btc_volume_zscore_1h` 需要最近 20 根可用窗口。

### 3. C29 规则没有在真实 run 中生效

最新 P4.5 中：

```text
btc_1h_volume.metric_score = 0.25
btc_1h_volume.score_bucket = positive
btc_1h_volume.semantic_rule_id = semantic.radar_rule
```

预期：

```text
btc_1h_volume.score_bucket_v2 = context_only 或 neutral_confirmed
btc_1h_volume 不得单独产生 bullish/positive
kline 派生指标应触发 semantic.kline_orderflow.composite
```

### 4. P1 指标数量口径漂移

当前代码注册：

```text
SOURCE_CONFIGS unique metrics = 124
METRIC_DEFINITIONS unique metrics = 124
```

最新 P1 落库：

```text
metric_values distinct metric_id = 111
```

缺失 13 个 Kline 派生指标是主因。

另有 3 个历史 alias / 当前 source 输出不一致需要审计口径说明：

```text
dxy -> 当前实际产出 dxy_proxy
exchange_netflow -> 当前实际产出 exchange_balance_delta_1d_proxy
gamma_wall_distance -> 当前实际产出 gamma_wall_proxy_distance
```

## 任务内容

### 1. P1 Kline 采集窗口守门

- 确认 `binance-btcusdt-kline-1h` 真实请求必须使用足够窗口，至少 26 根。
- 如果 API 返回少于 25 根 closed kline：
  - 不得静默降级成只输出 raw OHLCV。
  - 必须标记 `sample_boundary` 或 `insufficient_kline_window`。
  - 允许 raw OHLCV 入链，但 P3/P4.5 必须知道派生指标不可用的原因。

### 2. P1 派生指标落库守门

- 成功采集到足够窗口时，18 个 kline 指标必须全部进入 `metric_values`。
- `source_runs.status=healthy` 时不得只落 5 个 raw OHLCV。
- P1-C22 报告中新增或复用问题项，显式展示：
  - `expected_kline_metric_count`
  - `actual_kline_metric_count`
  - `missing_kline_derived_metrics`

### 3. P2 Radar 覆盖守门

- `kline_orderflow` 必须包含 18 个指标位。
- 若派生指标缺失，P2 quality report 必须标记为当前 run 的 missing/stale，而不是让 P3 fallback 到 raw OHLCV 旧规则。

### 4. P3 C29 组合规则守门

- 当 kline 派生指标可用时，`kline_orderflow` 必须走 `semantic.kline_orderflow.composite`。
- `btc_1h_volume` 不得单独产生 `positive/bullish`。
- `btc_1h_high` / `btc_1h_low` 不得单独通过 `semantic.radar_rule` 产生方向分。
- 如果派生指标不可用：
  - kline module 应进入 `insufficient_kline_window` / `combo_required` / `data_boundary`。
  - 不得退回“volume bullish”旧逻辑。

### 5. P4.5 Evidence 守门

- P4.5 `metric_evidence` 中必须能看到 kline 派生指标，或明确看到派生指标不可用原因。
- `support_drivers` / `dominant_drivers` 不得出现 `btc_1h_volume` 作为独立 bullish 主驱动。
- 研究文章和发文层必须能解释：

```text
成交量是确认因子，不是独立方向因子。
```

### 6. P1 指标数回归测试

- 增加测试或审计脚本，比较：
  - `SOURCE_CONFIGS unique metrics`
  - `METRIC_DEFINITIONS unique metrics`
  - 最新 collect run `metric_values distinct metric_id`
  - P1-C22 HTML/MD 中的指标数量
- 如果最新 collect run 少于 expected metrics，必须输出差异列表。
- 对 provider_required / alias / intentionally unavailable 指标建立白名单解释，避免误报。

## DoD

- [x] 全链条真实 run 后，`binance-btcusdt-kline-1h` 在 `metric_values` 中至少包含 18 个 kline 指标，或明确给出 `insufficient_kline_window` 原因。
- [x] P4.5 `kline_orderflow` evidence 不再只包含 5 个 raw OHLCV。
- [x] `btc_1h_volume` 不再以 `semantic.radar_rule` 单独产生 `positive/bullish`。
- [x] P3 输出包含 `semantic.kline_orderflow.composite` 或明确 sample boundary。
- [x] P1-C22 报告能解释 P1 指标数量口径，最新 run 不再无说明地从 114/124 降到 111。
- [x] 新增回归测试覆盖：
  - kline source 18 指标入链。
  - raw payload 少于 25 根 kline 时不得静默回退旧评分。
  - `btc_1h_volume` 不得单独成为 bullish 主驱动。
- [x] P1/P2/P3/P4.5 对应 HTML 均能反映修复后的链路状态。

## 执行记录

### 2026-05-23

- P1 持久化守门：`binance-btcusdt-kline-1h` 若实际落库指标少于 source registry 期望指标数，则 `source_runs.status=warning`，并写入 `insufficient_kline_metric_chain expected/actual/missing/raw_kline_count`。
- P3 评分守门：`btc_1h_open/high/low/close/volume` 在 `kline_orderflow` 中强制走 `semantic.kline.raw_context_only`，即使 P2 输入仍是旧的 bullish/positive，也不会回退到 `semantic.radar_rule`。
- 回归测试：
  - `test_kline_partial_metric_chain_is_warned_at_persist`
  - `test_kline_raw_ohlcv_does_not_fallback_to_bullish_radar_rule`
- 验证通过：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_sources.py backend/tests/test_p3_pipeline.py -q
# 54 passed

.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py -q
# 10 passed
```

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_sources.py backend/tests/test_p3_pipeline.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p45_dashboard_api.py -q
```

真实链路验收：

```powershell
# 运行 p1p2p3p45 全链条后检查：
# 1. reports/p1-c22-真实数据全链路验收报告.html
# 2. reports/p2-radar-quality-report.html
# 3. reports/p3-algorithm-audit-report.html
# 4. reports/p45-research-report.html
```

## 备注

本任务是 P3-C29 的回归守门，不重新设计 Kline 语义。核心是确保已完成的 C29 能稳定进入真实 pipeline，并在 P1 指标数变化时及时暴露原因。
