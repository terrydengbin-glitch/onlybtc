# P8-C04 时序指标 metric_values 与历史窗口索引

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立统一时序指标表 metric_values，支撑历史窗口、趋势判断、z-score、分位数、History Replay 和 Dashboard 图表。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- metric_values 字段：metric_id、source_id、observed_at、ingested_at、value_num、value_text、unit、timeframe、quality_score、is_fallback、raw_observation_id。
- 索引：(metric_id, observed_at)、(source_id, observed_at)、(metric_id, source_id, observed_at)。
- 支持 1m、5m、10m、1h、1d 等 timeframe。
- 支持窗口查询：24h、7d、30d、90d。
- 规定数值、文本、布尔、JSON 值的存储边界。

## 输入

- P8-C03 normalized_metrics。
- P1 数据采集结果。

## 输出

- metric_values 表与索引。
- 历史窗口查询 Repository。
- 示例窗口查询测试。

## 验收标准

- 趋势敏感指标可以按窗口读取。
- P3 算法可直接计算 z-score、分位数、变化率。
- 大量 metric_values 写入后查询性能可接受。

## 依赖任务

P8-C03

## 备注

P1-C08 调整为消费该表，不再单独设计存储。
