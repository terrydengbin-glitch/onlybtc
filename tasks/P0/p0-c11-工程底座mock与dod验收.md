# P0-C11 工程底座 Mock 与 DoD 验收

## 状态

DONE

## 所属 Phase

P0 项目骨架与工程底座

## 任务目标

用 Mock 流程和基础测试验证工程底座可被后续 Phase 可靠使用。P0-C11 未通过，不进入 P8 / P1。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 验证 Vue3、FastAPI、Python CLI、异步 Worker 骨架可启动。
- 验证配置系统、日志系统、环境变量读取正常。
- 验证 Path Resolver 在默认目录、环境变量覆盖、临时测试目录下行为一致。
- 验证 Run Once 空流程可以生成 run_id 和阶段状态。
- 准备 P0 级别 smoke test 与 mock fixtures。

## 输入

P0-C01 至 P0-C10。

## 输出

- P0 smoke test。
- Run Once mock result。
- Path Resolver 测试报告。
- P0 DoD 验收清单。

## 验收标准

- CLI 可以执行 health check 与 run-once mock。
- FastAPI health endpoint 可返回系统状态。
- Vue3 AppShell 能启动并显示 mock 在线状态。
- Worker mock 队列可以执行一个空任务。
- Resolver 测试通过，不依赖硬编码目录。
- P0 DoD 全部通过后，才允许进入 P8。

## 依赖任务

P0-C01、P0-C02、P0-C03、P0-C04、P0-C05、P0-C06、P0-C07、P0-C08、P0-C09、P0-C10

## 备注

该任务是 Phase 门禁任务，不产生业务判断，只保证工程骨架稳定。
