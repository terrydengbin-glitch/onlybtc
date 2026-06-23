# P8-C10 Repository 层、查询服务与页面聚合 API

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立统一 Repository 和面向页面的聚合查询 API，避免前端直接拼表，避免业务模块散写 SQL。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- source_repository。
- metric_repository。
- data_quality_repository。
- run_log_repository。
- radar_repository。
- alert_repository。
- evidence_repository。
- debate_repository。
- article_repository。
- replay_repository。
- 页面聚合 API：Dashboard、Overview、Evidence、LLM Debate、Alerts、Invalidation、Data Quality、Run Logs、Source Detail、Radar Detail、History Replay。

## 输入

- P8-C03 到 P8-C09 表结构。
- FastAPI 后端。

## 输出

- Repository 层。
- Service 层。
- 页面聚合 API DTO。

## 验收标准

- 前端所有 P5 页面都能通过聚合 API 获取数据。
- 业务代码不直接依赖 SQLite 方言。
- 后续迁移 PostgreSQL 时 API 层不需要大改。

## 依赖任务

P8-C03、P8-C04、P8-C05、P8-C06、P8-C07、P8-C08、P8-C09、P0-C03

## 备注

聚合 API 优先服务 UI 与调试效率。
