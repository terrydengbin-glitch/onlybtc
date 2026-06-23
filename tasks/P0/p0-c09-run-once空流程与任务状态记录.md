# P0-C09 Run Once 空流程与任务状态记录

## 状态

DONE

## 所属 Phase

P0

## 任务目标

实现 Run Once 空流程，让用户可以手动触发一条完整但不执行真实业务的 pipeline，并记录阶段状态。

P0 阶段可以先使用临时内存状态；P8-C05 完成后必须切换为 SQLite runs / run_stages / run_logs。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- CLI 或 API 触发 Run Once 空流程。
- 生成 run_id。
- 依次模拟 queued、fetching、cleaning、feature_calculation、radar_analysis、module_llm、fusion、multi_llm_debate、review、alert_policy、publish、completed。
- 暴露当前 run 状态给 Dashboard。
- 预留 P8-C05 SQLite 写入接口。

## 输入

- 上游 Phase 或前置任务产物。
- 开发文档中对应模块、雷达、总控、预警或 Dashboard 规范。

## 输出

- Run Once 空流程。
- run_id 和 stage 状态模型。
- Dashboard 可读取的任务状态。
- 后续迁移到 P8-C05 的适配点。

## 验收标准

- 触发 Run Once 后能看到完整阶段进度。
- 空流程不会生成交易建议。
- P5-C07 可以读取状态展示。
- P8-C05 完成后可无痛切换到 SQLite 持久化。

## 依赖任务

P0-C04、P0-C05、P0-C07

## 备注

P9-C07 负责最终 FastAPI Run Once 接口，P8-C05 负责持久化。
