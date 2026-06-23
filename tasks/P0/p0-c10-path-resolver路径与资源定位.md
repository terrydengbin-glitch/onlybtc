# P0-C10 Path Resolver 路径与资源定位

## 状态

DONE

## 所属 Phase

P0 项目骨架与工程底座

## 任务目标

建立全项目统一的 Path Resolver，解决开发、打包、迁移目录、跨系统运行时的路径定位问题，禁止业务代码硬编码 `E:\onlyBTC` 或依赖当前工作目录。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 定义 `project_root`、`app_root`、`config_dir`、`data_dir`、`sqlite_db_path`、`cache_dir`、`logs_dir`、`exports_dir`、`screenshots_dir`、`playwright_artifacts_dir`、`seed_data_dir`、`ui_references_dir`、`static_assets_dir`、`backup_dir`。
- 支持环境变量覆盖：`ONLYBTC_HOME`、`ONLYBTC_DATA_DIR`。
- 使用 `pathlib.Path`，保证 Windows / macOS / Linux 路径行为一致。
- 提供目录初始化能力，缺失目录可由 CLI 或启动流程创建。
- 为 SQLite、Playwright、日志、导出、前端静态资源、seed data 提供统一入口。
- 为测试提供临时目录模式，避免污染真实数据目录。

## 输入

- P0-C01 项目目录结构。
- P0-C04 CLI 命令入口。
- P0-C06 配置系统与环境变量规范。

## 输出

- Path Resolver 模块设计与实现任务说明。
- 路径优先级规则。
- 目录 bootstrap 规则。
- 测试目录与生产目录隔离规则。

## 验收标准

- 任意模块获取路径都通过 resolver，不直接拼接项目根目录。
- 更换项目目录后，系统无需修改代码即可启动。
- 设置 `ONLYBTC_DATA_DIR` 后，SQLite、日志、缓存、导出文件全部写入新数据目录。
- 测试环境可以创建临时 data root，并在测试结束后清理。
- P8、P1、P5、P6、P9 相关任务均能引用该 resolver。

## 依赖任务

P0-C01、P0-C04、P0-C06

## 下游依赖

P8-C01、P8-C11、P1-C06、P5-C20、P6-C02、P9-C07

## 备注

Path Resolver 属于 P0 工程底座，不单独拆成大 Phase。它是后续 SQLite、Playwright、导出、日志、打包部署的共同基础。
