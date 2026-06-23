# P8-C11 数据保留、归档、备份、VACUUM 与导出

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立长期运行所需的数据库维护能力，包括保留策略、归档、备份、VACUUM、导出和 replay package。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- raw_observations 保留策略。
- run_logs 保留策略。
- metric_values 长期保留策略。
- snapshot / evidence / debate / article 长期保留策略。
- SQLite backup。
- VACUUM / incremental vacuum。
- archive old raw rows。
- export replay package。

## 输入

- P8 全部核心表。

## 输出

- DB maintenance CLI。
- 定时维护任务。
- 备份与恢复说明。
- 导出格式说明。

## 验收标准

- 可以备份当前数据库。
- 可以导出某个 snapshot 的 replay package。
- 可以清理旧 raw/log 数据，不影响 History Replay。
- VACUUM 后数据库可正常读取。

## 依赖任务

P8-C08、P8-C10

## 备注

Playwright screenshot 不直接保存进 SQLite，只保存文件路径和元数据。
