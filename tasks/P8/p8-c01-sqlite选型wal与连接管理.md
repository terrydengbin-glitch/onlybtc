# P8-C01 SQLite 选型、WAL 与连接管理

## 状态

DONE

## 所属 Phase

P8 SQLite 数据库与持久化层

## 任务目标

建立 onlyBTC 的 SQLite 数据库基础运行方式，包括文件位置、连接管理、WAL、外键、busy timeout、异步访问和 CLI 初始化入口。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)

## 实施范围

- 选择 SQLAlchemy 2.x Async + aiosqlite。
- 配置 SQLite PRAGMA：WAL、foreign_keys、busy_timeout、synchronous。
- 定义数据库路径、测试库路径、备份路径。
- 提供 CLI：db init、db check、db pragmas。
- 规定所有写入必须通过 Repository / Unit of Work，不允许业务模块散写 SQL。

## 输入

- P0 工程配置系统。
- P0 CLI 入口。

## 输出

- 数据库连接模块。
- Async session 管理。
- CLI 初始化命令。
- SQLite PRAGMA 校验。

## 验收标准

- 本地可以创建数据库文件。
- WAL mode 生效。
- foreign_keys 生效。
- 异步读写冒烟测试通过。
- 不保存 API key、cookie、token 明文。

## 依赖任务

P0-C03、P0-C04、P0-C06

## 备注

该任务是 P8 后续所有 Schema 与 Repository 的基础。
