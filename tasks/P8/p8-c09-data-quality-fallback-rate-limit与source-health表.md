# P8-C09 Data Quality、Fallback、Rate Limit 与 Source Health 表

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

保存数据质量评分、source health、fallback、rate limit、module discount 和 system constraints。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- data_quality_snapshots。
- source_health_events。
- fallback_events。
- rate_limit_events。
- module_discounts。
- system_constraints。
- 记录 confidence_cap、critical_block、publish_block。

## 输入

- P1-C09 数据质量评分。
- P7-C04 数据源健康监控。

## 输出

- Data Quality 页面所需表。
- Source Detail 所需质量和 fallback 查询。
- 数据质量影响总控的查询接口。

## 验收标准

- 数据质量差时能说明哪些模块被降权。
- fallback 生效必须可追溯。
- rate limit 不能静默失败。
- critical / publish 受限原因可查询。

## 依赖任务

P8-C03、P8-C04、P1-C09

## 备注

数据质量不是 UI 装饰，它直接限制 final_confidence 和 publish_allowed。
