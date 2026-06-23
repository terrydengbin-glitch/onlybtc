# P5-C17 Radar Detail 雷达舱、指标节点与 Evidence 下钻

## 状态

DONE

## 当前架构对齐

Radar Detail 页以 P4.5 pack 内的 module 与 metrics 为主，同时回链 P2 radar output 和 P3 scored evidence。页面通过 `GET /api/p45/radar-modules/{module_id}` 获取模块详情，并复用前端已加载的 `GET /api/p45/evidence` 数据完成 metric / evidence / source 下钻。

旧式表格详情不再作为第一视觉。新版页面采用 `Radar Scope`：中心是当前 module，外圈是该 module 下的 metric / source / evidence 节点，节点颜色、大小、距离和线条表达方向、贡献、质量和 fallback/stale 状态。

## UI 原型

- [Radar Detail Scope Prototype](../../ui-references/p5-radar-detail-scope-prototype.html)

## 所属 Phase

P5 Dashboard 与可视化层

## 任务目标

实现单个 Radar module 的“雷达舱”详情页，让用户能直观看到该模块内部哪些指标支撑 BTC、哪些指标压制 BTC、哪些指标只是 mixed / fallback / stale，并能点击指标进入 Evidence 详情。

## FastAPI 依赖

- `GET /api/p45/radar-modules/latest`
- `GET /api/p45/radar-modules/{module_id}`
- `GET /api/p45/evidence`
- `GET /api/p45/evidence/{evidence_id}`
- `GET /api/sources/{source_id}`

## 数据字段

- module：`module_id`、`module_name`、`module_score`、`module_effective_score`、`module_direction`、`module_strength`、`module_quality_score`
- metric：`metric_id`、`metric_name`、`value/current_value`、`metric_score`、`metric_effective_score`、`direction`、`score_bucket`
- quality：`quality_score`、`freshness_status`、`freshness_minutes`、`stale_after_minutes`、`fallback_used`、`fallback_reason`
- weighting：`freshness_weight`、`horizon_weight`、`duplicate_adjustment`、`module_weight`
- source：`source_id`、`source_run_id`、`source_ts`、`collected_at`
- explanation：`p45_metric_brief`、`metric_explanation`、`score_reason`

## 实施范围

### 1. Module Header

- 展示 module 名称、方向、分数、质量、evidence 数量、fallback/stale 数量。
- 提供 module switch，可以在 14 个 Radar module 之间切换，不离开页面。
- 提供返回 Dashboard、Evidence、Data Quality 的快捷入口。

### 2. Radar Scope

- 中心卡片展示当前 module。
- 外圈节点展示该 module metrics。
- 颜色规则：
  - support / bullish / positive：青绿色
  - pressure / bearish / negative：红色
  - mixed / zero：黄色
  - fallback / stale / unavailable：紫色或虚线
- 布局规则：
  - 节点离中心越近，代表 `abs(metric_effective_score)` 或贡献越高。
  - 节点越大，代表 `quality_score` 越高。
  - 线条粗细代表贡献大小。
  - 虚线代表 fallback/stale/unavailable。

### 3. Metric Detail Panel

- hover 或 click metric 节点时，右侧显示：
  - value/current_value
  - metric_score
  - metric_effective_score
  - quality_score
  - source/freshness
  - 一句话解释
- 点击 `Open Evidence` 打开 Evidence detail 弹窗。
- 点击 `Open Source` 打开 Source Detail。

### 4. Audit Table

- 底部保留完整 metrics 表格，用于审计。
- 表格必须包含 score、effective score、quality、source、freshness、fallback、brief。
- 表格不是第一视觉，不能替代 Radar Scope。

### 5. 交互

- 从 Dashboard 点击 Radar node 进入对应 module detail。
- 从 Radar Detail 点击 metric node 能进入 Evidence detail。
- 从 Radar Detail 点击 source 能进入 Source Detail。
- 保持当前 run context，不切换到历史 run。

## 非目标

- 不做 Three.js。
- 不做真实 3D 物理引擎。
- 不在 P5 重新计算 module score，只消费 P2/P3/P4.5 已产出的评分和解释。
- 不把发文建议或交易动作放进 Radar Detail。

## 验收标准

- Radar Detail 页第一视觉是 Radar Scope，而不是普通表格。
- 中心 module 卡、外圈 metric 节点、右侧 metric detail panel、底部 audit table 同屏存在。
- 至少能展示一个 module 的全部 metrics。
- metric 节点颜色、线条、大小或距离能体现 direction / score / quality / fallback。
- metric 节点可点击打开 Evidence detail。
- source 可点击进入 Source Detail。
- fallback/stale/unavailable 有明确视觉区分。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录

- Radar Detail 页已从普通模块列表升级为 `Radar Detail Scope`。
- 已实现 module switch，可在 14 个 Radar module 间切换并加载 `/api/p45/radar-modules/{module_id}`。
- 已实现中心 module 卡、外圈 metric 节点、SVG 雷达圈层、贡献连线和右侧 metric detail panel。
- metric 节点颜色按 direction / fallback / stale / unavailable 区分；距离和线宽按 effective score 表达贡献，节点大小按 quality 表达质量。
- 点击 metric 节点可选中并查看 value、score、quality、source、freshness、horizon、duplicate。
- `Open Evidence` 可打开 Evidence detail；`Open Source` 可进入 Source Detail。
- 底部保留 Metric Audit Table 作为审计附录。
- 已追加修复 Radar Scope 节点溢出问题：metric 节点缩小，并在画布内按安全边距夹取位置，避免节点被容器裁切。
- 已追加修复 Radar Scope 连线穿透节点问题：连线从中心 module 卡边缘起始，终止在 metric 卡片边缘前，不再连接到卡片中心点。

## 验收结果

- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。
- 溢出修复后再次执行上述三项，均通过。
- 连线边缘修复后再次执行上述三项，均通过。
