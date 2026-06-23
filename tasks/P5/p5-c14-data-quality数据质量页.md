# P5-C14 Data Quality 数据质量页

## 状态

DONE

## 当前架构对齐

Data Quality 页合并展示 P1/P2/P3/P4.5 的质量边界。当前前端通过 `GET /api/data-quality/latest` 消费 P4.5 `data_quality`、`contract_validation`、`html_contract`、`source_health`，并结合 Evidence payload 展示 freshness、fallback、stale、unavailable 和 source 跳转。

## 所属 Phase

P5 Dashboard 与可视化层

## 任务目标

实现数据质量控制台，让用户能快速判断本轮数据是否可信、哪些字段只是 warning、哪些 source/fallback/stale 需要追溯，并能跳转 Source Detail、Evidence、Run Logs。

## FastAPI 依赖

- `GET /api/data-quality/latest`
- `GET /api/p45/evidence`
- `GET /api/sources/{source_id}`
- `GET /api/p45/runs/latest`

## 实施范围

- Overall Quality：metric count、module count、avg quality、unavailable、missing freshness/horizon。
- Contract Validation：status、warnings、freshness_check、关键 checks。
- Evidence Quality：positive/negative/zero/stale/fallback/unavailable。
- Source Health：source_count、status_counts、recent source runs、source detail 跳转。
- Data Boundary：unavailable metric 的 freshness warning 不阻塞 DoD，但必须显式展示。
- 操作入口：Evidence、Source Detail、Run Logs、Audit Reports。

## 验收标准

- 页面不只是接口成功/失败，必须展示质量边界与原因。
- `MISSING_FRESHNESS_FIELDS` 如果只来自 unavailable 指标，显示为 warning 而不是 failed。
- recent source rows 可点击进入 Source Detail。
- Evidence 统计与 P4.5 data_quality 同屏展示。
- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。

## 完成记录

- Data Quality 页已升级为 `Data Quality Console`。
- 已展示整体质量、指标数、模块数、unavailable、missing freshness、fallback、stale。
- 已展示 contract validation、view consistency、关键 checks 和 warnings。
- 已将 freshness warning 边界显式化：available 缺失阻塞，unavailable-only 缺失作为 warning。
- 已展示 Evidence Quality 统计与 Source Health 状态分布。
- recent source rows 可点击进入 Source Detail。
- 页面提供 Evidence、Source Detail、Run Logs、Overview 快捷入口。

## 验收结果

- `npm run build` 通过。
- `python scripts/validate_p5_dashboard_contract.py` 通过。
- `python scripts/validate_p5_page_dod.py` 通过。
