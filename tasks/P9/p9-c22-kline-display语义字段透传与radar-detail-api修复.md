# P9-C22 / Kline Display 语义字段透传与 Radar Detail API 修复

## 状态

DONE

## 背景

最新审计发现，P3 已经在 `kline_orderflow` 的复合语义里生成了：

- `module_effective_bias = mild_pressure`
- `display_state = neutral_wait_confirm`
- `display_summary = Short-term pressure exists, but kline structure still waits for confirmation.`
- `top_kline_reason`

但是 `/api/p45/radar-modules/kline_orderflow` 的模块顶层仍返回：

```json
{
  "module_effective_bias": "mild_pressure",
  "display_state": null,
  "display_summary": null,
  "top_kline_reason": null
}
```

这说明 P3 算法层已经正确，但 P4.5 / P9 API projection 没有把 `module_semantic_profile` 内的 Kline 展示语义提升到前端稳定字段，导致 Dashboard / Radar Detail 页面仍可能展示粗粒度方向或空字段。

## 目标

修复 Radar Module Detail API 的 Kline 复合语义透传：

1. `/api/p45/radar-modules/kline_orderflow` 顶层必须返回 `display_state`。
2. 顶层必须返回 `display_summary`。
3. 顶层必须返回 `top_kline_reason`。
4. 如果字段在 `module_semantic_profile` 内存在，API projection 必须提升到 module 顶层。
5. 如果字段已经在 module 顶层存在，则优先使用 module 顶层值。
6. Dashboard / Radar Detail 前端不重新推断 Kline 语义，只消费后端字段。

## 不改范围

- 不修改 P1 采集。
- 不修改 P2 registry。
- 不修改 P3 Kline 组合评分规则。
- 不修改 P4.5 final_view / decision_card 聚合逻辑。
- 不修改 Kline 权重。
- 不在前端重算 `display_state` 或 `display_summary`。

## API 契约

`/api/p45/radar-modules/kline_orderflow` 的 `module` 至少包含：

```json
{
  "radar_module": "kline_orderflow",
  "module_effective_bias": "mild_pressure",
  "trend_state": "neutral_wait_confirm",
  "display_state": "neutral_wait_confirm",
  "display_summary": "Short-term pressure exists, but kline structure still waits for confirmation.",
  "top_kline_reason": "..."
}
```

字段来源优先级：

```text
module.display_state
  -> module.module_semantic_profile.display_state
  -> module.trend_state

module.display_summary
  -> module.module_semantic_profile.display_summary
  -> derived fallback from trend_state + module_effective_bias

module.top_kline_reason
  -> module.module_semantic_profile.top_kline_reason
  -> primary contributor reason
  -> null
```

## DoD

- [x] `/api/p45/radar-modules/kline_orderflow` 返回非空 `display_state`。
- [x] `/api/p45/radar-modules/kline_orderflow` 返回非空 `display_summary`。
- [x] 当 `trend_state=neutral_wait_confirm` 且 `module_effective_bias=mild_pressure` 时，文案不能显示成 confirmed bearish 或 bullish。
- [x] P45 report final JSON 内已有的 `display_state/display_summary` 不丢失。
- [x] Dashboard / Radar Detail API 兼容旧 run：旧 payload 没有字段时不 500。
- [x] 增加或更新 `backend/tests/test_p45_dashboard_api.py` 覆盖 Kline display 字段透传。
- [x] 测试通过。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_final_writer.py -q
```

## 关联任务

- P3-C36 / Kline trend_state 优先展示与 module_effective_bias 取分修复
- P4.5-C23 / Radar Module Detail API 透传 P3 复合语义字段
- P5-C41 / Derivatives Long/Short Ratio 前端展示与语义防误导

## Completion Note

2026-05-24 已完成：

- `backend/src/onlybtc/api/p45_dashboard.py`
  - 新增 Radar module projection helper。
  - 将 `module_semantic_profile.display_state/display_summary/top_kline_reason` 提升到 module 顶层。
  - `latest_dashboard`、`latest_radar_modules`、`radar_module_detail` 统一使用投影后的 module。
  - 为旧 payload 增加兼容 fallback：`display_state -> trend_state`，`display_summary` 根据 Kline `trend_state + module_effective_bias` 生成。
- `backend/tests/test_p45_dashboard_api.py`
  - 增加 Kline display 字段透传回归测试。

验收：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_final_writer.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```

结果：

- `13 passed`
- `5 passed`
- `23 passed`

真实 API 验收：

- `/api/p45/radar-modules/kline_orderflow` 返回 `display_state=neutral_wait_confirm`。
- `/api/p45/radar-modules/kline_orderflow` 返回 `display_summary=Short-term pressure exists, but kline structure still waits for confirmation.`。
- `/api/p45/dashboard/latest` 与 `/api/p45/radar-modules/latest` 的 Kline 摘要同步返回上述字段。
