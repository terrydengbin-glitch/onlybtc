# P5-C10 Evidence 证据页

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

P4.5 已经形成 `p45.research_report.v2` 契约，Evidence 页需要作为前端可审计入口，承接 P4.5 的 scored evidence，而不是只显示 metric 列表。

## 数据源与接口

- `GET /api/p45/evidence?limit=200`
- `GET /api/p45/evidence/{evidence_id}`
- `GET /api/sources/{source_id}`

## 实施内容

- Evidence 页升级为 `Evidence Workbench`。
- 增加 run lineage 展示：`collect_run_id -> p2_radar_run_id -> p3_run_id -> pack_id -> final_run_id`。
- 增加 Radar module 与 score bucket 筛选。
- 列表展示 metric title、Radar module、brief、raw/effective score、quality、freshness、fallback/stale/live/exact 标签。
- 详情展示：
  - value、metric_score、metric_effective_score、quality、bucket、available。
  - score_reason / metric_explanation。
  - freshness_weight、horizon_weight、duplicate_adjustment、weight。
  - source_id、source_run_id、source_ts、collected_at、freshness_minutes、stale_after_minutes。
  - horizon_tags、duplicate_group_id、semantic_rule_id、role、evidence_tier。
  - history_context。
  - fallback/stale boundary flags。
- Source Detail 按钮打通到 source 子页。
- Article / Overview / Radar 侧点击 evidence 仍进入同一个 Evidence detail。

## DoD

- Evidence 页不再只是三列列表，必须展示 data + interpretation + run context。
- 每条 evidence 可点击打开详情。
- stale / fallback / unavailable 必须有可见标签或 boundary flags。
- source detail 可从 evidence detail 跳转。
- 前端构建通过。
- P5 DoD 校验脚本通过。

## 验收记录

- `npm run build` 通过。
- `scripts/validate_p5_page_dod.py` 已增加 Evidence Workbench / Source & Freshness / Horizon & Duplicate / History Context / Open Source Detail 校验。
