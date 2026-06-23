# P2-C22 Radar metric 默认 horizon_tags、module_weight 与 duplicate_group_id

## 状态

DONE

## 所属 Phase

P2 Radar 特征工程与模块评分

## 任务目标

为 P4.5 Research Report V2 的周期拆分、聚合审计和重复指标降权补齐 P2 Radar metric 侧的默认契约字段：

- `horizon_tags`
- `module_weight`
- `duplicate_group_id`

这些字段应随 Radar metric / feature metadata 进入 P3 scored evidence，并最终被 P4.5-C11/C12 消费。

## 背景

P4.5-C11 需要解释每个指标如何影响最终结论，而不是只把 evidence dump 给 LLM。当前 P3 已有指标正零负评分，但 P4.5 v2 还需要知道：

- 指标主要影响 24h、3d 还是 7d。
- 所在 Radar module 在最终聚合里的权重。
- 跨 module 重复出现的指标是否属于同一个 duplicate group。

如果这些字段只在 P4.5 临时推断，长期会造成口径漂移。因此需要在 P2 Radar 定义层建立默认字段。

## 实施范围

1. Radar metric 默认周期标签
   - 为每个 Radar metric 定义 `horizon_tags`。
   - 默认枚举：
     - `h24`
     - `d3`
     - `d7`
     - `structural`
   - 示例：
     - `btc_1h_volume` -> `["h24"]`
     - `etf_flow_7d` -> `["d3", "d7"]`
     - `mvrv_zscore` -> `["d7", "structural"]`

2. Radar module 权重
   - 为 14 个 Radar module 定义 `module_weight`。
   - 权重用于 P3/P4.5 的聚合审计，不直接替代原 P2 module score。
   - 权重总和应可归一化，避免某个 module 隐性过重。

3. 重复指标分组
   - 为跨 module 重复出现或高度相关的指标定义 `duplicate_group_id`。
   - 示例：
     - `btc_funding_rate` 在 `derivatives_crowding` 与 `btc_total_state` 中应归入同一组。
     - `btc_1h_close` 与价格结构相关指标应明确是否同组。
   - 可扩展字段：
     - `duplicate_policy`
     - `duplicate_group_max_weight`

4. P2 Radar 质检报告
   - 显示每个 Radar metric 是否具备：
     - `horizon_tags`
     - `module_weight`
     - `duplicate_group_id`
   - 对缺失字段输出 warning。

5. 下游传递
   - P3 可从 P2 feature metadata 读取这些字段。
   - 若旧数据缺失字段，P3/P4.5 可 fallback，但必须显式 warning。

## 输出契约

每个 Radar metric metadata 建议至少包含：

```json
{
  "metric_id": "btc_funding_rate",
  "radar_module": "derivatives_crowding",
  "horizon_tags": ["h24", "d3"],
  "module_weight": 0.08,
  "duplicate_group_id": "derivatives_funding_btc",
  "duplicate_policy": "cap_group_total_weight",
  "duplicate_group_max_weight": 0.08
}
```

## 验收标准

- 14 个 Radar module 均有 `module_weight`。
- 已进入 Radar 的 metric 均有默认 `horizon_tags`。
- 已知重复指标有 `duplicate_group_id`。
- P2 Radar 质检 HTML 展示字段覆盖情况。
- P3 scored evidence 能继承 P2 的周期、权重、重复分组字段。
- 缺字段时输出 warning，不静默吞掉。

## 依赖任务

- P2-C20
- P2-C21
- P3-C16
- P4.5-C11
