# P9-C20 / Derivatives Long/Short Ratio API 契约与 Dashboard 透传

## 状态

DONE

## 背景

P4.5-C24 会把 derivatives long/short ratio 的复合语义写入 pack/final。P9 需要保证 Dashboard、Radar Detail、Evidence Detail API 都能按当前 `final_run_id / pack_id` 读取这些字段。

## 目标

1. Dashboard API 返回 derivatives module 的 long/short 复合状态。
2. Radar Detail API 返回指标级 long/short 字段。
3. Evidence Detail API 能打开新增 ratio 指标详情。
4. API DTO 文档明确字段含义。
5. 旧 run 缺字段时前端得到稳定 fallback，不报错。

## API 字段

Dashboard module card:

```text
positioning_state
top_positioning_state
positioning_conflict_level
long_short_squeeze_risk
module_effective_bias
crowding_state
```

Radar detail metric node:

```text
positioning_signal
crowding_contribution
trend_confirmation
source_id
freshness
```

## DoD

- [ ] `/api/p45/dashboard` 返回 derivatives long/short module fields。
- [ ] `/api/p45/radar-module/derivatives_crowding` 返回新增 metric fields。
- [ ] `/api/p45/evidence/{evidence_id}` 对新增指标可用。
- [ ] History Replay 旧 run 缺字段时显示 `unknown/not_available`，不污染当前 run。
- [ ] API tests 覆盖有字段和缺字段两个场景。

## 关联

P4.5-C24, P9-C08, P9-C16, P5-C41

## Completion Note

- Done: Dashboard/Radar Detail/Evidence payloads pass through positioning and squeeze fields.
- Verified: P9 dashboard API regression tests passed.
