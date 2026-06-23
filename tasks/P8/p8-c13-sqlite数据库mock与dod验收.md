# P8-C13 SQLite 数据库 Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

对 SQLite 事实库进行 Phase 级验收，确认 schema、migration、seed data、repository、备份归档和路径 resolver 全部可用。P8-C13 未通过，不进入 P1。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 验证空库 migration 到最新版本。
- 验证 seed demo database 能覆盖所有 P5 页面。
- 验证 repository 查询可支撑 P9 聚合 API。
- 验证 WAL、连接管理、索引、约束、事务回滚。
- 验证数据保留、备份、VACUUM、导出。
- 验证数据库路径全部由 P0-C10 Path Resolver 提供。

## 输入

P8-C01 至 P8-C12，P0-C10 Path Resolver。

## 输出

- SQLite DoD test suite。
- seed database。
- migration report。
- repository coverage report。
- P8 DoD 验收清单。

## 验收标准

- 新环境一条命令可生成可演示数据库。
- 所有表具备必要主键、外键、索引和时间字段。
- P9 所有页面聚合 API 所需数据都能从 repository 查询。
- 数据库迁移、备份、恢复、清理流程通过。
- 迁移项目目录或修改 `ONLYBTC_DATA_DIR` 后数据库路径正确。
- P8 DoD 全部通过后，才允许进入 P1。

## 依赖任务

P8-C01、P8-C02、P8-C03、P8-C04、P8-C05、P8-C06、P8-C07、P8-C08、P8-C09、P8-C10、P8-C11、P8-C12、P0-C10

## 备注

P8-C12 偏测试与种子数据建设，P8-C13 是 Phase 门禁，判断整个 SQLite 层是否能支撑后续业务。
