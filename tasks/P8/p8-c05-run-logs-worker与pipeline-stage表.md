# P8-C05 Run Logs、Worker 与 Pipeline Stage 表

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立 run_id 维度的全流程运行审计表，支撑 Run Once、定时任务、worker、失败重试、阶段耗时和 Run Logs 页面。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- runs：run_id、trigger_type、status、started_at、completed_at、current_step、progress。
- run_stages：queued、fetching、cleaning、feature_calculation、radar_analysis、module_llm、fusion、multi_llm_debate、review、alert_policy、publish、completed。
- worker_heartbeats：worker_id、status、current_job、heartbeat_delay、cpu、memory。
- run_logs：timestamp、level、message、source_id、module_id、stage_name、error_code。
- retry_records：failed_step、retry_count、fallback_used、resolved_status。

## 输入

- P0-C05 异步任务框架。
- P0-C09 Run Once 空流程。

## 输出

- Run Logs 相关表。
- Run stage 写入 API。
- Worker heartbeat 写入 API。

## 验收标准

- Run Once 空流程可以写入完整阶段链路。
- 失败阶段必须能定位 source_id / module_id / stage_name。
- Run Logs 页面聚合查询可返回当前 run 状态。

## 依赖任务

P8-C02、P0-C05、P0-C09

## 备注

Run Logs 是后续排障和审计的骨架，不允许只写纯文本日志。
