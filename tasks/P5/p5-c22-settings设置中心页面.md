# P5-C22 Settings 设置中心页面

## 状态

DONE

## 当前架构对齐（2026-05-22）

Settings 页需要展示 P4.5 当前运行配置：`ONLYBTC_P45_RESEARCH_PROVIDER`、DeepSeek model、timeout seconds、max retries、run_mode 默认值、llm_runtime_mode 默认值。

页面只读为主。涉及 API key 的内容必须脱敏，不允许前端显示密钥。

## 所属 Phase

P5 Dashboard 全量可视化

## 任务目标

建立 Settings 设置中心子页面，用于集中管理 API Key、数据源、运行策略、预警阈值、LLM 模型、发布策略、路径与系统维护配置。Dashboard 主页面右上角齿轮作为入口。

## 背景依据

- [开发文档.md](../../开发文档.md)
- [task index.md](../../task%20index.md)
- P10 API Key 配置与密钥管理
- P9-C14 Settings 配置聚合 API

## 页面入口

- Dashboard 顶部右上角 Settings 齿轮进入 `/settings`。
- Data Quality、Run Logs、LLM Appendix、Alerts 页面可跳转到对应设置 Tab。
- 设置页需要有返回 Dashboard 的按钮。

## 设置分区

- API Keys：FRED、交易所、链上数据、ETF/期权、新闻源、LLM Provider。
- Data Sources：启用/禁用、刷新频率、fallback 优先级、Playwright 开关、超时时间。
- LLM Providers：DeepSeek、Qwen、火山、Kimi 的模型、base_url、temperature、max_tokens、启用状态。
- Radar & Alerts：雷达权重、预警阈值、冷却期、反证条件开关。
- Run Once & Scheduler：默认 run once 策略、定时采集间隔、是否自动触发发文。
- Publish Policy：publish_allowed 门槛、文章语言、人工确认开关。
- Storage & Paths：SQLite 路径、备份目录、导出目录、缓存目录、数据保留周期。
- System：端口、环境、日志级别、代理、Playwright 浏览器状态。

## 2026-05-21 对齐补充

- LLM Providers 必须覆盖 P4-C18 runtime governance：provider、model、base_url、timeout、retry、预算上限、fallback policy。
- Data Sources 必须能展示 P1 freshness policy、主源/fallback 优先级、semi-automated reauth 状态。
- Settings 只配置策略，不直接篡改历史 run、evidence、P4.5 final payload。

## 实施范围

- Settings 页面采用左侧分组导航 + 右侧配置面板。
- 每个配置项展示当前值、来源：`.env` / UI 写入 / 默认值。
- API Key 默认脱敏显示，明文只在编辑框本地临时可见。
- 保存、测试、清空、恢复默认都需要清晰状态。
- 高风险设置需要二次确认，例如清空 key、变更数据库路径、缩短保留周期。

## 输入

- P10 Provider Registry。
- P9-C14 Settings API。
- Dashboard 主页面全局路由。

## 输出

- Settings 页面。
- Settings 入口。
- 分组配置组件。
- 前端类型与 mock 数据。

## 验收标准

- 用户可以从 Dashboard 进入 Settings，并返回主面板。
- API Key 不泄露完整明文。
- 数据源、LLM、预警、路径等配置有清晰分组。
- 保存失败不会破坏 `.env` 或当前运行配置。
- Settings 页面不阻塞主 Dashboard 的实时监控。
- LLM / Data Source 配置变更必须有测试、脱敏、审计状态。

## 依赖任务

P5-C01、P5-C19、P5-C20、P9-C14、P10-C01、P10-C02、P10-C03、P10-C04、P10-C05

## 备注

早期可以只实现 API Keys 与 Data Sources 两个 Tab，但页面结构必须预留完整 Settings Center。

## 完成记录

- 已实现 Settings Center 页面，入口沿用 Dashboard 顶部 Settings 和侧边栏设置。
- 已接入 `/api/settings`，展示 `app`、`run_defaults`、`llm`、schema、API host/port、refresh 等配置。
- 已按分区提供只读 Tabs：
  - LLM Providers
  - API Keys
  - Data Sources
  - Radar & Alerts
  - Run Once
  - Publish
  - Storage
  - System
- API Key 仅展示 `configured / not configured` 与脱敏占位，不渲染明文密钥。
- 高风险动作如 Save / Rotate / Restore Default 当前保持 disabled，只做策略展示，不修改 `.env` 或历史 run。
- Run Once 分区保留 `Run Full Chain` 与 Run Logs 跳转。
- 验证通过：
  - `npm run build`
  - `python scripts/validate_p5_dashboard_contract.py`
  - `python scripts/validate_p5_page_dod.py`
