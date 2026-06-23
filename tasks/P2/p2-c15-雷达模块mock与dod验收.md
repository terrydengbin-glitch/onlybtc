# P2-C15 雷达模块 Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P2 全量雷达模块

## 任务目标

用统一 mock 指标和历史窗口验证所有雷达模块能输出结构化信号、证据、冲突信息和可解释评分。P2-C15 未通过，不进入 P3。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 覆盖 BTC 总状态、宏观、美元流动性、美债信用、资金流、采用率、链上、K 线盘口、衍生品、交易结构、期权、市场广度、亚洲风险、事件政策雷达。
- 为每个雷达输出 signal、strength、confidence、evidence_summary、conflicting_evidence、data_quality、risk_flags、invalidation_signals。
- 真实源未接入的指标必须进入 missing_metrics，不允许伪造高质量信号。
- 验证 Radar Detail、Evidence、Dashboard 后续页面所需字段。

## 输入

P2-C01 至 P2-C14，P1-C10 mock fixtures，P8-C06。

## 输出

- 雷达模块测试 fixture。
- 雷达输出快照。
- 雷达字段完整性报告。
- P2 DoD 验收清单。

## 验收结果

- P2 全量 14 个雷达已可运行。
- `analyze-radars` 实测写入 14 个 `radar_outputs`。
- `feature_values` 与 `module_json_outputs` 已同步写入。
- 后端测试：20 passed。
- Ruff：passed。
- 前端 build：passed。
- 真实源未接入的模块以 `data_quality=low` 与 `missing_metrics` 显示，不输出伪高置信信号。

## 依赖任务

P2-C01、P2-C02、P2-C03、P2-C04、P2-C05、P2-C06、P2-C07、P2-C08、P2-C09、P2-C10、P2-C11、P2-C12、P2-C13、P2-C14

## 备注

P2 当前完成的是全量雷达分析框架和指标位覆盖。后续新增真实数据源时，应回到 P1/P10 补 provider、registry、client、normalization，再由 P2 自动消费历史窗口。

## P1/P8/P1-C22 对齐补充

P1 已升级以下底座能力，P2 验收必须同步遵守：

- 采集数据必须带 `run_id`、`source_id`、`metric_id`、`ts`、`quality_score`。
- P2 只通过 `historical_window(metric_id)` 消费 SQLite，不直接读取 provider。
- Radar feature 必须透传 `source_id`、freshness、business recency、selected reason、candidates、conflict。
- P2 的 data quality 需要同时考虑覆盖率、有效质量分、采集新鲜度、业务时间状态。
- P1-C22 每次输出中文 Markdown + 中文 HTML，P2 DoD 以 HTML 中的“SQLite 状态”和“Radar 是否消费”为验收依据。
- 若 P1 新增指标但 P2 未消费，P1-C22 会显示 `Radar 是否消费=否`，需要回到对应 P2 任务卡修复。
