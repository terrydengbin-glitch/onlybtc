# P3-C26 Score Bucket v2 与 Zero 语义拆分治理

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

当前 P3 已能输出 `positive / negative / zero / unavailable`，但 `zero` 语义过粗。很多并非规则缺失的指标也被统计为 zero：

- 上下文指标：如 block height、halving days、事件倒计时。
- 审计指标：source/status/fallback 相关字段。
- 正常中性区间：如 VIX normal、macro_surprise=0。
- 需要组合解读的指标：如 OI flat、cost basis、realized price。
- 真正规则缺口。

P4.5 继续使用 raw zero ratio 会导致全局 confidence 被无害 zero 压低。

## 目标

新增 `score_bucket_v2`，把 zero 拆成可审计语义：

```text
positive
negative
neutral_confirmed
context_only
combo_required
rule_gap_zero
unavailable
```

## 上下游契约

| Phase | 契约 |
| --- | --- |
| P1/P8 | 提供真实值、source_ts、freshness、fallback、run lineage。 |
| P2 | 提供 module/metric、horizon_tags、duplicate_group_id、module_weight。 |
| P3 | 生成 `score_bucket` 兼容旧字段，同时新增 `score_bucket_v2` 与 zero breakdown。 |
| P4.5 | 消费 `score_bucket_v2`，不再把全部 raw zero 用作降级理由。 |
| P5 | Evidence / Radar Detail 展示 zero 细分类。 |

## 规则口径

### neutral_confirmed

指标处于正常中性区间，说明没有异常信号，不应处罚。

示例：

```text
macro_surprise_score = 0
VIX normal
options_iv normal
basis flat
```

### context_only

只解释背景或审计上下文，不参与方向分和 decision zero。

示例：

```text
btc_block_height
btc_halving_estimated_days
cpi_days_until / fomc_days_until / pce_days_until / nfp_days_until
source status / fallback context
```

### combo_required

单指标不能直接判断方向，需要和其他指标组合。

示例：

```text
btc_open_interest flat
realized_price
sth_cost_basis
lth_cost_basis
cap_real_usd
```

### rule_gap_zero

指标有方向含义，但当前规则未覆盖或阈值不足，这是唯一应进入 decision zero penalty 的 zero 类型。

## 输出字段

指标级新增：

```json
{
  "score_bucket_v2": "neutral_confirmed",
  "zero_reason_type": "neutral_confirmed",
  "zero_reason": "macro surprise is exactly zero; this confirms no surprise instead of a rule gap",
  "decision_zero": false
}
```

模块级新增：

```json
{
  "zero_breakdown": {
    "raw_zero_count": 0,
    "context_only": 0,
    "neutral_confirmed": 0,
    "combo_required": 0,
    "rule_gap_zero": 0
  },
  "decision_zero_metric_count": 0,
  "decision_zero_metric_ratio": 0.0
}
```

## DoD

- 所有 P3 scored evidence 保留旧 `score_bucket`，同时新增 `score_bucket_v2`。
- `macro_surprise_score=0` 不再算 `rule_gap_zero`。
- 事件倒计时和减半/区块高度进入 `context_only` 或 risk component。
- OI flat、cost basis 类指标进入 `combo_required`。
- provider_required 仍进入 `unavailable/data_boundary`，不计 decision zero。
- P3 HTML 展示 zero breakdown。
- P4.5 Evidence Pack 透传 `score_bucket_v2`。
- 单元测试覆盖上述分类。
- P1/P2/P3/P4.5 全链条重跑通过。

## 关联任务

P3-C21, P3-C22, P3-C23, P3-C24, P3-C25, P4.5-C20, P5-C10, P5-C17

## Execution Notes

- Added metric-level `score_bucket_v2`, `zero_reason_type`, `zero_reason`, and `decision_zero`.
- Added module-level `zero_breakdown`, `decision_zero_metric_count`, and ratio fields.
- Preserved legacy `score_bucket` for P4.5/P5 compatibility.
- Added P3 audit HTML columns for v2 bucket and zero breakdown.
- Validation: `python -m pytest backend/tests/test_p3_pipeline.py -q` passed, 15 tests.
