# P8-C02 Alembic 迁移体系与基础 Schema 版本

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立数据库迁移体系，保证 Schema 可版本化、可升级、可回滚，并为所有 JSON 输出保留 schema_version。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 引入 Alembic。
- 建立初始 migration。
- 定义 created_at、updated_at、schema_version、run_id、snapshot_id 等通用字段规范。
- 建立枚举值迁移策略。
- 提供 CLI：db upgrade、db downgrade、db current。

## 输入

- P8-C01 数据库连接。

## 输出

- Alembic 配置。
- 初始迁移文件。
- Schema 版本规范文档。

## 验收标准

- 空库可迁移到最新版本。
- 迁移状态可查询。
- 后续表结构变化必须通过 migration。
- JSON 表必须有 schema_version。

## 依赖任务

P8-C01

## 备注

后续所有 P8 表结构任务都基于本任务追加迁移。
