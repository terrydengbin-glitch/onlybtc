# onlyBTC Task Index

> Rebuilt from `tasks/` task-card files at `2026-05-22 12:31:10 UTC`.
> 乱码修复策略：以任务卡文件名和可读 Markdown 标题为准；旧 P4 Agent 主线保留为 Legacy 审计参考，P4.5 为当前研究报告主线。

## UI / Design References

| 文档 | 链接 |
|---|---|
| P5 Dashboard UI Prototype | [p5-dashboard-ui-prototype](tasks/ui/p5-dashboard-ui-prototype.md) |
| P5 Subpages UI Prototype | [p5-subpages-ui-prototype](tasks/ui/p5-subpages-ui-prototype.md) |
| Dashboard High-Fidelity Reference | [ui-references](ui-references/) |

## Phase / Architecture Docs

| 文档 | 链接 |
|---|---|
| p4.5-phase方案-radar-scored-analyst-writer | [p4.5-phase方案-radar-scored-analyst-writer](tasks/P4.5/p4.5-phase方案-radar-scored-analyst-writer.md) |

## P0 工程底座与项目初始化

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P0-C01 | 项目目录结构与基础工程初始化 | [P0-C01](tasks/P0/p0-c01-项目目录结构与基础工程初始化.md) |
| DONE | P0-C02 | Vue3 前端项目初始化 | [P0-C02](tasks/P0/p0-c02-vue3前端项目初始化.md) |
| DONE | P0-C03 | FastAPI 后端项目初始化 | [P0-C03](tasks/P0/p0-c03-fastapi后端项目初始化.md) |
| DONE | P0-C04 | Python CLI 命令入口 | [P0-C04](tasks/P0/p0-c04-python-cli命令入口.md) |
| DONE | P0-C05 | 异步任务框架与 Worker 骨架 | [P0-C05](tasks/P0/p0-c05-异步任务框架与worker骨架.md) |
| DONE | P0-C06 | 配置系统、日志系统与环境变量规范 | [P0-C06](tasks/P0/p0-c06-配置系统日志系统与环境变量规范.md) |
| DONE | P0-C07 | 数据源注册表与任务状态表设计 | [P0-C07](tasks/P0/p0-c07-数据源注册表与任务状态表设计.md) |
| DONE | P0-C08 | Dashboard 基础布局与系统在线状态 | [P0-C08](tasks/P0/p0-c08-dashboard基础布局与系统在线状态.md) |
| DONE | P0-C09 | Run Once 空流程与任务状态记录 | [P0-C09](tasks/P0/p0-c09-run-once空流程与任务状态记录.md) |
| DONE | P0-C10 | Path Resolver 路径与资源定位 | [P0-C10](tasks/P0/p0-c10-path-resolver路径与资源定位.md) |
| DONE | P0-C11 | 工程底座 Mock 与 DoD 验收 | [P0-C11](tasks/P0/p0-c11-工程底座mock与dod验收.md) |
| DONE | P0-C12 | Event Policy v2.1 业务契约与方向隔离基线 | [P0-C12](tasks/P0/p0-c12-event-policy-v2.1业务契约与方向隔离基线.md) |

## P1 数据源接入与采集层

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P1-C01 | 数据源配置 Schema 与验证状态枚举 | [P1-C01](tasks/P1/p1-c01-数据源配置schema与验证状态枚举.md) |
| DONE | P1-C02 | FRED API 接入与核心宏观指标验证 | [P1-C02](tasks/P1/p1-c02-fred-api接入与核心宏观指标验证.md) |
| DONE | P1-C03 | 交易所 API 接入：价格、K线、Funding、OI | [P1-C03](tasks/P1/p1-c03-交易所api接入价格k线funding-oi.md) |
| DONE | P1-C04 | Bitcoin 区块高度与减产倒计时数据源 | [P1-C04](tasks/P1/p1-c04-bitcoin区块高度与减产倒计时数据源.md) |
| DONE | P1-C05 | 官方数据源接入框架：Fed、Treasury、OFR | [P1-C05](tasks/P1/p1-c05-官方数据源接入框架fed-treasury-ofr.md) |
| DONE | P1-C06 | Playwright 页面抓取框架 | [P1-C06](tasks/P1/p1-c06-playwright页面抓取框架.md) |
| DONE | P1-C07 | 数据清洗、标准化与 fallback 机制 | [P1-C07](tasks/P1/p1-c07-数据清洗标准化与fallback机制.md) |
| DONE | P1-C08 | 历史数据存储与窗口计算基础字段 | [P1-C08](tasks/P1/p1-c08-历史数据存储与窗口计算基础字段.md) |
| DONE | P1-C09 | 数据质量评分与 source health 监控 | [P1-C09](tasks/P1/p1-c09-数据质量评分与source-health监控.md) |
| DONE | P1-C10 | 数据源 Mock 与 DoD 验收 | [P1-C10](tasks/P1/p1-c10-数据源mock与dod验收.md) |
| DONE | P1-C11 | P2 首批雷达真实数据源补齐 | [P1-C11](tasks/P1/p1-c11-p2首批雷达真实数据源补齐.md) |
| DONE | P1-C12 | P2 全量雷达公开真实数据源补齐 | [P1-C12](tasks/P1/p1-c12-p2全量雷达公开真实数据源补齐.md) |
| DONE | P1-C13 | P2 剩余付费与 Playwright 数据源补齐 | [P1-C13](tasks/P1/p1-c13-p2剩余付费与playwright数据源补齐.md) |
| DONE | P1-C14 | Glassnode 公开数据与登录态 Playwright 数据勘探（公开源落地，P10-C08 entitlement 审计完成） | [P1-C14](tasks/P1/p1-c14-glassnode登录态playwright数据勘探.md) |
| DONE | P1-C15 | 免费数据源与代理指标补齐 | [P1-C15](tasks/P1/p1-c15-免费数据源与代理指标补齐.md) |
| DONE | P1-C16 | 免费宏观 Surprise 数据源与评分引擎 | [P1-C16](tasks/P1/p1-c16-免费宏观surprise数据源与评分引擎.md) |
| DONE | P1-C17 | Bitbo STH/LTH 成本基础公开数据勘探 | [P1-C17](tasks/P1/p1-c17-bitbo-sth-lth成本基础公开数据勘探.md) |
| DONE | P1-C18 | Fed Speech Risk 公开源与评分引擎 | [P1-C18](tasks/P1/p1-c18-fed-speech-risk公开源与评分引擎.md) |
| DONE | P1-C19 | Clark Moody Lightning 与 BTC 基础面板数据源 | [P1-C19](tasks/P1/p1-c19-clarkmoody-lightning与btc基础面板数据源.md) |
| DONE | P1-C20 | 数据新鲜度与质量快照闭环 | [P1-C20](tasks/P1/p1-c20-数据新鲜度与质量快照闭环.md) |
| DONE | P1-C21 | 采集批次 run_id 贯穿与多源仲裁 | [P1-C21](tasks/P1/p1-c21-采集批次run-id贯穿与多源仲裁.md) |
| DONE | P1-C22 | 真实数据全链路验收与指标参数盘点 | [P1-C22](tasks/P1/p1-c22-真实数据全链路验收与指标参数盘点.md) |
| DONE | P1-C23 | Clark Moody partial 指标修复 | [P1-C23](tasks/P1/p1-c23-clarkmoody-partial指标修复.md) |
| DONE | P1-C24 | 多源质量优先仲裁与冲突证据输出 | [P1-C24](tasks/P1/p1-c24-多源质量优先仲裁与冲突证据输出.md) |
| DONE | P1-C25 | 双时间戳 Freshness 模型修复 | [P1-C25](tasks/P1/p1-c25-双时间戳freshness模型修复.md) |
| DONE | P1-C26 | 数据源真实更新频率与 Freshness Policy | [P1-C26](tasks/P1/p1-c26-数据源真实更新频率与freshness-policy.md) |
| DONE | P1-C27 | Radar Quality 按数据类型重算 | [P1-C27](tasks/P1/p1-c27-radar-quality按数据类型重算.md) |
| DONE | P1-C28 | Lightning 多源冲突口径治理 | [P1-C28](tasks/P1/p1-c28-lightning多源冲突口径治理.md) |
| DONE | P1-C29 | TradingView 实时宏观市场数据源 | [P1-C29](tasks/P1/p1-c29-tradingview实时宏观市场数据源.md) |
| DONE | P1-C30 | run_mode 采集追溯与审计可见性 | [P1-C30](tasks/P1/p1-c30-run-mode采集追溯与审计可见性.md) |
| DONE | P1-C31 | BLS Calendar 403 与官方日历 Fallback 增强 | [P1-C31](tasks/P1/p1-c31-bls-calendar-403与官方日历fallback增强.md) |
| DONE | P1-C32 | FXStreet 无 Actual 事件状态治理与 Fallback | [P1-C32](tasks/P1/p1-c32-fxstreet无actual事件状态治理与fallback.md) |
| DONE | P1-C33 | OFR 与 Glassnode 页面源 Freshness 策略修复 | [P1-C33](tasks/P1/p1-c33-ofr与glassnode页面源freshness策略修复.md) |
| DONE | P1-C34 | Business Recency 策略校准与 Provider 发布节奏治理 | [P1-C34](tasks/P1/p1-c34-business-recency策略校准与provider发布节奏治理.md) |
| DONE | P1-C35 | 主源、Fallback 仲裁与多源冲突治理 | [P1-C35](tasks/P1/p1-c35-主源fallback仲裁与多源冲突治理.md) |
| DONE | P1-C36 | source_ts / collected_at 与 Freshness 字段贯穿 P1/P8 | [P1-C36](tasks/P1/p1-c36-source-ts-collected-at与freshness字段贯穿p1-p8.md) |
| DONE | P1-C37 | BLS 可选源与 FXStreet、Embedded Fallback 接管 | [P1-C37](tasks/P1/p1-c37-bls可选源与fxstreet-embedded-fallback接管.md) |
| DONE | P1-C38 | P1 全量采集并发限流、重试门控与失败诊断增强 | [P1-C38](tasks/P1/p1-c38-p1全量采集并发限流重试门控与失败诊断增强.md) |
| DONE | P1-C39 | Binance BTC Long/Short Ratio 数据源接入与 P1 指标入链 | [P1-C39](tasks/P1/p1-c39-binance-btc-long-short-ratio数据源接入与p1指标入链.md) |
| DONE | P1-C40 | Business Recency 滞后指标策略校准与 P1 报告口径修复 | [P1-C40](tasks/P1/p1-c40-business-recency滞后指标策略校准与p1报告口径修复.md) |
| DONE | P1-C41 | provider_stale_suspect 汇总计数口径修复 | [P1-C41](tasks/P1/p1-c41-provider-stale-suspect汇总计数口径修复.md) |
| DONE | P1-C42 | Trade Structure 5m-15m Price Response 派生指标接入 | [P1-C42](tasks/P1/p1-c42-trade-structure-5m-15m-price-response派生指标接入.md) |
| DONE | P1-C43 | BTC Total State 派生价格与 OI 变化指标准备 | [P1-C43](tasks/P1/p1-c43-btc-total-state派生价格与oi变化指标准备.md) |
| DONE | P1-C44 | Options Volatility 派生指标与历史窗口准备 | [P1-C44](tasks/P1/p1-c44-options-volatility派生指标与历史窗口准备.md) |
| DONE | P1-C45 | Event Policy 事件窗口阶段与 trade_gate 输入准备 | [P1-C45](tasks/P1/p1-c45-event-policy事件窗口阶段与trade-gate输入准备.md) |
| DONE | P1-C46 | Crypto Breadth v3 派生指标与历史窗口准备 | [P1-C46](tasks/P1/p1-c46-crypto-breadth-v3派生指标与历史窗口准备.md) |
| DONE | P1-C47 | Macro Radar v3 宏观派生指标、利率变化与 BTC 相对宏观 residual | [P1-C47](tasks/P1/p1-c47-macro-radar-v3宏观派生指标利率变化与btc相对宏观residual.md) |
| DONE | P1-C48 | Dollar Liquidity v2.1 派生指标、IORB 与 BTC response 准备 | [P1-C48](tasks/P1/p1-c48-dollar-liquidity-v2.1派生指标iorb与btc-response准备.md) |
| DONE | P1-C49 | Treasury Credit v2.1 派生指标与历史窗口准备 | [P1-C49](tasks/P1/p1-c49-treasury-credit-v2.1派生指标与历史窗口准备.md) |
| DONE | P1-C50 | Fund Flow v2.2 派生指标、多源 ETF、稳定币与 BTC response 准备 | [P1-C50](tasks/P1/p1-c50-fund-flow-v2.2派生指标多源etf稳定币与btc-response准备.md) |
| DONE | P1-C51 | Onchain Valuation v2.2 派生指标、动态成本位与 Proxy 准备 | [P1-C51](tasks/P1/p1-c51-onchain-valuation-v2.2派生指标动态成本位与proxy准备.md) |
| DONE | P1-C52 | BTC Adoption v2.3 派生指标、真实结算需求与 BTC response 准备 | [P1-C52](tasks/P1/p1-c52-btc-adoption-v2.3派生指标真实结算需求与btc-response准备.md) |
| DONE | P1-C53 | Asia Risk v2.3 派生指标、亚洲时段 BTC response 与 regional risk 准备 | [P1-C53](tasks/P1/p1-c53-asia-risk-v2.3派生指标亚洲时段btc-response与regional-risk准备.md) |
| DONE | P1-C54 | Kline Orderflow v2.2 派生指标、fast sensing 与主动流接受度准备 | [P1-C54](tasks/P1/p1-c54-kline-orderflow-v2.2派生指标fast-sensing与主动流接受度准备.md) |
| DONE | P1-C55 | Trade Structure Flow v2.3 派生指标、盘口流动性与标准化 residual 准备 | [P1-C55](tasks/P1/p1-c55-trade-structure-flow-v2.3派生指标盘口流动性与标准化residual准备.md) |
| DONE | P1-C56 | Derivatives Crowding v2.5 派生指标、趋势先验、杠杆接受与 residual 准备 | [P1-C56](tasks/P1/p1-c56-derivatives-crowding-v2.5派生指标趋势先验杠杆接受与residual准备.md) |
| DONE | P1-C57 | Event Window v3 官方事件日历采集 | [P1-C57](tasks/P1/p1-c57-event-window-v3官方事件日历采集.md) |
| DONE | P1-C58 | Event Window v3 预期、Nowcast 与 FedWatch 快照 | [P1-C58](tasks/P1/p1-c58-event-window-v3预期nowcast-fedwatch快照.md) |
| DONE | P1-C59 | Event Window v3 Actual 发布轮询与 Post-Event Reaction | [P1-C59](tasks/P1/p1-c59-event-window-v3-actual发布轮询与post-event-reaction.md) |
| DONE | P1-C60 | Event Window v3.1 Cleveland Fed Nowcast Parser | [P1-C60](tasks/P1/p1-c60-event-window-v3.1-cleveland-nowcast-parser.md) |
| DONE | P1-C61 | Event Window v3.1 BLS Actual Provider 与 FRED Fallback | [P1-C61](tasks/P1/p1-c61-event-window-v3.1-bls-actual-provider与fred-fallback.md) |
| DONE | P1-C62 | Event Window v3.1 BLS Calendar Provider Fallback Mesh | [P1-C62](tasks/P1/p1-c62-event-window-v3.1-bls-calendar-provider-fallback-mesh.md) |
| DONE | P1-C63 | Event Window v3.1 Consensus Provider Config | [P1-C63](tasks/P1/p1-c63-event-window-v3.1-consensus-provider-config.md) |
| DONE | P1-C64 | Event Window v3.1 FedWatch Proxy Provider | [P1-C64](tasks/P1/p1-c64-event-window-v3.1-fedwatch-proxy-provider.md) |
| DONE | P1-C65 | Event Window v3.2 FRED Release Dates Calendar Fallback | [P1-C65](tasks/P1/p1-c65-event-window-v3.2-fred-release-dates-calendar-fallback.md) |
| DONE | P1-C66 | Event Window v3.2 Secondary Calendar Scraper Mesh | [P1-C66](tasks/P1/p1-c66-event-window-v3.2-secondary-calendar-scraper-mesh.md) |
| DONE | P1-C67 | Event Window v3.2 Prediction Market Odds Connector | [P1-C67](tasks/P1/p1-c67-event-window-v3.2-prediction-market-odds-connector.md) |
| DONE | P1-C68 | Event Window v3.2 Atlanta Fed Market Probability Tracker Connector | [P1-C68](tasks/P1/p1-c68-event-window-v3.2-atlanta-fed-mpt-connector.md) |
| DONE | P1-C69 | Event Window 独立 Binance Market Probe | [P1-C69](tasks/P1/p1-c69-event-window独立binance-market-probe.md) |
| DONE | P1-C70 | Event Window BLS Calendar Replacement: FRED official_mirror + NYFed time crosscheck + DOL post-release docs | [P1-C70](tasks/P1/p1-c70-event-window-bls-calendar-replacement-fred-nyfed-dol.md) |
| DONE | P1-C71 | Event Window Secondary Calendar Free Replacement Mesh | [P1-C71](tasks/P1/p1-c71-event-window-secondary-calendar-free-replacement-mesh.md) |
| DONE | P1-C72 | Radar Module Cadence Profile | [P1-C72](tasks/P1/p1-c72-radar-module-cadence-profile.md) |
| DONE | P1-C73 | Event Window Secondary Source Throttle / Cache Guard | [P1-C73](tasks/P1/p1-c73-event-window-secondary-source-throttle-cache-guard.md) |
| DONE | P1-C74 | FRED Provider Resilience | [P1-C74](tasks/P1/p1-c74-fred-provider-resilience.md) |
| DONE | P1-C75 | BTC 4H/1D Direct Evidence Features | [P1-C75](tasks/P1/p1-c75-btc-4h-1d-direct-evidence-features.md) |

## P2 Radar 指标与模块层

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P2-C01 | BTC 总状态雷达 | [P2-C01](tasks/P2/p2-c01-btc总状态雷达.md) |
| DONE | P2-C02 | 宏观雷达 | [P2-C02](tasks/P2/p2-c02-宏观雷达.md) |
| DONE | P2-C03 | 美元流动性雷达 | [P2-C03](tasks/P2/p2-c03-美元流动性雷达.md) |
| DONE | P2-C04 | 美债与信用压力雷达 | [P2-C04](tasks/P2/p2-c04-美债与信用压力雷达.md) |
| DONE | P2-C05 | 资金流雷达与 ETF Flow 历史分析 | [P2-C05](tasks/P2/p2-c05-资金流雷达与etf-flow历史分析.md) |
| DONE | P2-C06 | BTC 采用率雷达 | [P2-C06](tasks/P2/p2-c06-btc采用率雷达.md) |
| DONE | P2-C07 | 链上估值与筹码雷达 | [P2-C07](tasks/P2/p2-c07-链上估值与筹码雷达.md) |
| DONE | P2-C08 | K 线盘口与价格结构雷达 | [P2-C08](tasks/P2/p2-c08-k线盘口与价格结构雷达.md) |
| DONE | P2-C09 | 衍生品拥挤度雷达 | [P2-C09](tasks/P2/p2-c09-衍生品拥挤度雷达.md) |
| DONE | P2-C10 | 交易结构与链上/衍生品流量雷达 | [P2-C10](tasks/P2/p2-c10-交易结构与链上衍生品流量雷达.md) |
| DONE | P2-C11 | 期权波动率雷达 | [P2-C11](tasks/P2/p2-c11-期权波动率雷达.md) |
| DONE | P2-C12 | 加密市场广度雷达 | [P2-C12](tasks/P2/p2-c12-加密市场广度雷达.md) |
| DONE | P2-C13 | 亚洲风险雷达 | [P2-C13](tasks/P2/p2-c13-亚洲风险雷达.md) |
| DONE | P2-C14 | 事件政策、Fed 言论与宏观事件冲击雷达 | [P2-C14](tasks/P2/p2-c14-事件政策fed言论与宏观事件冲击雷达.md) |
| DONE | P2-C15 | 雷达模块 Mock 与 DoD 验收 | [P2-C15](tasks/P2/p2-c15-雷达模块mock与dod验收.md) |
| DONE | P2-C16 | Onchain Valuation 残留质量提升 | [P2-C16](tasks/P2/p2-c16-onchain-valuation残留质量提升.md) |
| DONE | P2-C17 | 宏观雷达实时市场指标扩展 | [P2-C17](tasks/P2/p2-c17-宏观雷达实时市场指标扩展.md) |
| DONE | P2-C18 | P2 与 P1/SQLite/审计链路对齐 | [P2-C18](tasks/P2/p2-c18-p2与p1-sqlite审计链路对齐.md) |
| DONE | P2-C19 | P2 全链条全量重跑与 Radar 质检报告 | [P2-C19](tasks/P2/p2-c19-p2全链条全量重跑与radar质检报告.md) |
| DONE | P2-C20 | Radar 指标覆盖补齐与全量采集指标纳入治理 | [P2-C20](tasks/P2/p2-c20-radar指标覆盖补齐与全量采集指标纳入治理.md) |
| DONE | P2-C21 | P1-P2 同 run 数据契约与历史 fallback 显式化 | [P2-C21](tasks/P2/p2-c21-p1-p2同run数据契约与历史fallback显式化.md) |
| DONE | P2-C22 | Radar metric 默认 horizon_tags、module_weight 与 duplicate_group_id | [P2-C22](tasks/P2/p2-c22-radar-metric默认horizon-tags-module-weight与duplicate-group-id.md) |
| DONE | P2-C23 | Fund Flow ETF 绝对方向与边际改善语义前移 | [P2-C23](tasks/P2/p2-c23-fund-flow-etf绝对方向与边际改善语义前移.md) |
| DONE | P2-C24 | Derivatives Long/Short Ratio 指标注册与语义契约 | [P2-C24](tasks/P2/p2-c24-derivatives-long-short-ratio指标注册与语义契约.md) |
| DONE | P2-C25 | Trade Structure Flow 指标角色、权重与语义边界治理 | [P2-C25](tasks/P2/p2-c25-trade-structure-flow指标角色权重与语义边界治理.md) |
| DONE | P2-C26 | BTC Total State 指标角色、权重与 composite-only 契约 | [P2-C26](tasks/P2/p2-c26-btc-total-state指标角色权重与composite-only契约.md) |
| DONE | P2-C27 | Options Volatility 指标角色与 directional isolation | [P2-C27](tasks/P2/p2-c27-options-volatility指标角色与directional-isolation.md) |
| DONE | P2-C28 | Event Policy 指标角色与 risk-only 隔离 | [P2-C28](tasks/P2/p2-c28-event-policy指标角色与risk-only隔离.md) |
| DONE | P2-C29 | Crypto Breadth v3 指标角色与 composite-only 契约 | [P2-C29](tasks/P2/p2-c29-crypto-breadth-v3指标角色与composite-only契约.md) |
| DONE | P2-C30 | Macro Radar v3 role、composite-only 与 risk-context registry | [P2-C30](tasks/P2/p2-c30-macro-radar-v3-role-composite-only与risk-context-registry.md) |
| DONE | P2-C31 | Dollar Liquidity v2.1 role、composite-only 与 risk-context registry | [P2-C31](tasks/P2/p2-c31-dollar-liquidity-v2.1-role-composite-only与risk-context-registry.md) |
| DONE | P2-C32 | Treasury Credit v2.1 registry role / composite-only / risk-context | [P2-C32](tasks/P2/p2-c32-treasury-credit-v2.1-registry-role-composite-only-risk-context.md) |
| DONE | P2-C33 | Fund Flow v2.2 registry role、composite-only 与 flow-context | [P2-C33](tasks/P2/p2-c33-fund-flow-v2.2-registry-role-composite-only与flow-context.md) |
| DONE | P2-C34 | Onchain Valuation v2.2 registry 慢快变量与 proxy governance | [P2-C34](tasks/P2/p2-c34-onchain-valuation-v2.2-registry慢快变量与proxy-governance.md) |
| DONE | P2-C35 | BTC Adoption v2.3 registry 真实采用度与 context-only 治理 | [P2-C35](tasks/P2/p2-c35-btc-adoption-v2.3-registry真实采用度与context-only治理.md) |
| DONE | P2-C36 | Asia Risk v2.3 registry context-only 与 BTC response 治理 | [P2-C36](tasks/P2/p2-c36-asia-risk-v2.3-registry-context-only与btc-response治理.md) |
| DONE | P2-C37 | Kline Orderflow v2.2 registry context-only 与主动流接受度治理 | [P2-C37](tasks/P2/p2-c37-kline-orderflow-v2.2-registry-context-only与主动流接受度治理.md) |
| DONE | P2-C38 | Trade Structure Flow v2.3 registry context-only 与 price acceptance 治理 | [P2-C38](tasks/P2/p2-c38-trade-structure-flow-v2.3-registry-context-only与price-acceptance治理.md) |
| DONE | P2-C39 | Derivatives Crowding v2.5 registry context-only 与趋势接受治理 | [P2-C39](tasks/P2/p2-c39-derivatives-crowding-v2.5-registry-context-only与趋势接受治理.md) |
| DONE | P2-C40 | Event Window v3 Unscheduled Shock Fast Lane | [P2-C40](tasks/P2/p2-c40-event-window-v3-unscheduled-shock-fast-lane.md) |
| DONE | P2-C41 | Event Window Shock Fast Lane 多窗口行情冲击判定 | [P2-C41](tasks/P2/p2-c41-event-window-shock-fast-lane多窗口行情冲击.md) |
| DONE | P2-C42 | Radar Runtime Incremental Module Runner | [P2-C42](tasks/P2/p2-c42-radar-runtime-incremental-module-runner.md) |
| DONE | P2-C43 | BTC 4H/1D Direct Evidence Registry | [P2-C43](tasks/P2/p2-c43-btc-4h-1d-direct-evidence-registry.md) |

## P3 算法、事件窗口与评分层

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P3-C01 | 历史窗口、移动均值与变化率计算 | [P3-C01](tasks/P3/p3-c01-历史窗口移动均值与变化率计算.md) |
| DONE | P3-C02 | Z-score、历史分位数与异常值检测 | [P3-C02](tasks/P3/p3-c02-zscore历史分位数与异常值检测.md) |
| DONE | P3-C03 | 背离检测：价格、资金流、杠杆、宏观 | [P3-C03](tasks/P3/p3-c03-背离检测价格资金流杠杆宏观.md) |
| DONE | P3-C04 | 模块级反证条件检查器 | [P3-C04](tasks/P3/p3-c04-模块级反证条件检查器.md) |
| DONE | P3-C05 | 总控级反证条件检查器 | [P3-C05](tasks/P3/p3-c05-总控级反证条件检查器.md) |
| DONE | P3-C06 | 预警等级 info/watch/warning/critical | [P3-C06](tasks/P3/p3-c06-预警等级info-watch-warning-critical.md) |
| DONE | P3-C07 | 去抖动、冷却期与自动升级降级 | [P3-C07](tasks/P3/p3-c07-去抖动冷却期与自动升级降级.md) |
| DONE | P3-C08 | 事件窗口 T-7/T-3/T-1/T-0/T+1/T+3 | [P3-C08](tasks/P3/p3-c08-事件窗口倒计时预警.md) |
| DONE | P3-C09 | 预警与反证 Mock 与 DoD 验收 | [P3-C09](tasks/P3/p3-c09-预警与反证mock与dod验收.md) |
| DONE | P3-C10 | live-only 算法输入隔离与污染防护 | [P3-C10](tasks/P3/p3-c10-live-only算法输入隔离与污染防护.md) |
| DONE | P3-C11 | P1/P2/P3 全链条全量重跑与 P3 审计报告 | [P3-C11](tasks/P3/p3-c11-p1p2p3全链条全量重跑与p3审计报告.md) |
| DONE | P3-C12 | P3 反证语义校准与业务链条治理 | [P3-C12](tasks/P3/p3-c12-p3反证语义校准与业务链条治理.md) |
| DONE | P3-C13 | P2 新增指标与 run-scope 证据链对齐 | [P3-C13](tasks/P3/p3-c13-p2新增指标与run-scope证据链对齐.md) |
| DONE | P3-C14 | 事件窗口分析器与 Post-event 风险总结治理 | [P3-C14](tasks/P3/p3-c14-事件窗口分析器与post-event风险总结治理.md) |
| DONE | P3-C15 | Run Mode Integrity 按同 run 作用域校准与历史 mock 隔离 | [P3-C15](tasks/P3/p3-c15-run-mode-integrity按同run作用域校准与历史mock隔离.md) |
| DONE | P3-C16 | 指标级正/零/负评分与 P4.5 输入契约 | [P3-C16](tasks/P3/p3-c16-指标级正零负评分与p4.5输入契约.md) |
| DONE | P3-C17 | P1/P2/P3 全链条审计报告接入 Scored Evidence | [P3-C17](tasks/P3/p3-c17-p1p2p3全链条审计报告接入scored-evidence.md) |
| DONE | P3-C18 | BTC 专业指标评分语义校准与阈值化治理 | [P3-C18](tasks/P3/p3-c18-btc专业指标评分语义校准与阈值化治理.md) |
| DONE | P3-C19 | P3 审计报告展示 Semantic 评分字段 | [P3-C19](tasks/P3/p3-c19-p3审计报告展示semantic评分字段.md) |
| DONE | P3-C20 | Freshness / Horizon / Duplicate 权重与 metric_effective_score | [P3-C20](tasks/P3/p3-c20-freshness-horizon-duplicate权重与metric-effective-score.md) |
| DONE | P3-C21 | Scoring Rulebook 文档化与零分指标治理 | [P3-C21](tasks/P3/p3-c21-scoring-rulebook文档化与零分指标治理.md) |
| DONE | P3-C22 | 高优先级零分指标评分规则优化与阈值补全 | [P3-C22](tasks/P3/p3-c22-高优先级零分指标评分规则优化与阈值补全.md) |
| DONE | P3-C23 | Radar Module 聚合器升级：Coverage / Conflict / Confidence | [P3-C23](tasks/P3/p3-c23-radar-module聚合器升级coverage-conflict-confidence.md) |
| DONE | P3-C24 | Radar 状态机与多维模块输出 | [P3-C24](tasks/P3/p3-c24-radar状态机与多维模块输出.md) |
| DONE | P3-C25 | Trend State 阈值校准与状态分布回测 | [P3-C25](tasks/P3/p3-c25-trend-state阈值校准与状态分布回测.md) |
| DONE | P3-C26 | Score Bucket v2 与 Zero 语义拆分治理 | [P3-C26](tasks/P3/p3-c26-score-bucket-v2与zero语义拆分治理.md) |
| DONE | P3-C27 | P0 Radar 核心模块组合规则优化 | [P3-C27](tasks/P3/p3-c27-p0-radar核心模块组合规则优化.md) |
| DONE | P3-C28 | P1 Radar 高零分模块语义补全 | [P3-C28](tasks/P3/p3-c28-p1-radar高零分模块语义补全.md) |
| DONE | P3-C29 | Kline Orderflow 量价结构组合评分与趋势敏感度优化 | [P3-C29](tasks/P3/p3-c29-kline-orderflow量价结构组合评分与趋势敏感度优化.md) |
| DONE | P3-C30 | P3-C29 kline 派生指标入链守门与 P1 指标数回归测试 | [P3-C30](tasks/P3/p3-c30-p3-c29-kline派生指标入链守门与p1指标数回归测试.md) |
| DONE | P3-C31 | Kline 派生指标单项方向与组合分解释一致性修复 | [P3-C31](tasks/P3/p3-c31-kline派生指标单项方向与组合分解释一致性修复.md) |
| DONE | P3-C32 | Derivatives Crowding Funding-OI 组合语义与拥挤状态治理 | [P3-C32](tasks/P3/p3-c32-derivatives-crowding-funding-oi组合语义与拥挤状态治理.md) |
| DONE | P3-C33 | Top Contributors 使用语义方向而非分数方向 | [P3-C33](tasks/P3/p3-c33-top-contributors使用语义方向而非分数方向.md) |
| DONE | P3-C34 | Derivatives Long/Short Ratio 组合评分与挤压风险语义 | [P3-C34](tasks/P3/p3-c34-derivatives-long-short-ratio组合评分与挤压风险语义.md) |
| DONE | P3-C35 | Kline 极小 effective 方向 Deadband 与展示口径修复 | [P3-C35](tasks/P3/p3-c35-kline极小effective方向deadband与展示口径修复.md) |
| DONE | P3-C36 | Kline trend_state 优先展示与 module_effective_bias 取分修复 | [P3-C36](tasks/P3/p3-c36-kline-trend-state优先展示与effective-bias取分修复.md) |
| DONE | P3-C37 | Trade Structure Flow 主动成交、价格响应、清算与执行摩擦复合语义治理 | [P3-C37](tasks/P3/p3-c37-trade-structure-flow主动成交价格响应清算与执行摩擦复合语义治理.md) |
| DONE | P3-C38 | Trade Structure Price Response 确认层评分接入 | [P3-C38](tasks/P3/p3-c38-trade-structure-price-response确认层评分接入.md) |
| DONE | P3-C39 | Trade Structure Price Response 口径一致性修复 | [P3-C39](tasks/P3/p3-c39-trade-structure-price-response口径一致性修复.md) |
| DONE | P3-C40 | Taker Buy Sell Ratio 主动成交语义与方向分隔离 | [P3-C40](tasks/P3/p3-c40-taker-buy-sell-ratio主动成交语义与方向分隔离.md) |
| DONE | P3-C41 | BTC Total State v2：价格、合约、周期、审计上下文分层治理 | [P3-C41](tasks/P3/p3-c41-btc-total-state-v2价格合约周期审计上下文分层治理.md) |
| DONE | P3-C42 | Options Volatility v2.1：波动风险、保护需求、尾部风险、到期与 pinning profile | [P3-C42](tasks/P3/p3-c42-options-volatility-v2.1波动风险保护需求尾部风险到期与pinning-profile.md) |
| DONE | P3-C43 | Event Policy v2.1：宏观事件 risk lock 与 trade_gate profile | [P3-C43](tasks/P3/p3-c43-event-policy-v2.1宏观事件risk-lock与trade-gate-profile.md) |
| DONE | P3-C44 | Crypto Breadth v3：BTC 趋势确认、市场扩散与宽度背离 | [P3-C44](tasks/P3/p3-c44-crypto-breadth-v3-btc趋势确认市场扩散与宽度背离.md) |
| DONE | P3-C45 | Macro Radar v3 状态机与二段式评分 | [P3-C45](tasks/P3/p3-c45-macro-radar-v3状态机与二段式评分.md) |
| DONE | P3-C46 | Dollar Liquidity v2.1 状态机与 BTC 吸收/拒绝评分 | [P3-C46](tasks/P3/p3-c46-dollar-liquidity-v2.1状态机与btc吸收拒绝评分.md) |
| DONE | P3-C47 | Treasury Credit v2.1 状态机、warning 前置与 BTC residual | [P3-C47](tasks/P3/p3-c47-treasury-credit-v2.1状态机warning前置与btc-residual.md) |
| DONE | P3-C48 | Fund Flow v2.2 状态机 fast warning、confirmation 与 rejection | [P3-C48](tasks/P3/p3-c48-fund-flow-v2.2状态机fast-warning-confirmation-rejection.md) |
| DONE | P3-C49 | Onchain Valuation v2.2 状态机、动态成本位、慢快分数与反证 | [P3-C49](tasks/P3/p3-c49-onchain-valuation-v2.2状态机动态成本位慢快分数与反证.md) |
| DONE | P3-C50 | BTC Adoption v2.3 状态机 Fast/Core/Regime 与采用度确认反证 | [P3-C50](tasks/P3/p3-c50-btc-adoption-v2.3状态机fast-core-regime与采用度确认反证.md) |
| DONE | P3-C51 | Asia Risk v2.3 状态机 BTC response first 与亚洲风险确认反证 | [P3-C51](tasks/P3/p3-c51-asia-risk-v2.3状态机btc-response-first与亚洲风险确认反证.md) |
| DONE | P3-C52 | Kline Orderflow v2.2 多时间尺度状态机、主动流接受与假突破反证 | [P3-C52](tasks/P3/p3-c52-kline-orderflow-v2.2多时间尺度状态机主动流接受与假突破反证.md) |
| DONE | P3-C53 | Trade Structure Flow v2.3 状态机、多周期价格接受与优先级治理 | [P3-C53](tasks/P3/p3-c53-trade-structure-flow-v2.3状态机多周期价格接受与优先级治理.md) |
| DONE | P3-C54 | Derivatives Crowding v2.5 状态机、趋势接受、拥挤脆弱与迟滞治理 | [P3-C54](tasks/P3/p3-c54-derivatives-crowding-v2.5状态机趋势接受拥挤脆弱与迟滞治理.md) |
| DONE | P3-C55 | Radar Modules to BTC Cockpit 输入归一化 | [P3-C55](tasks/P3/p3-c55-radar-modules-to-btc-cockpit输入归一化.md) |
| DONE | P3-C56 | Event Window v3 状态机与 Emergency Overlay | [P3-C56](tasks/P3/p3-c56-event-window-v3状态机与emergency-overlay.md) |
| DONE | P3-C57 | Event Window v3.1 Source Quality State Machine | [P3-C57](tasks/P3/p3-c57-event-window-v3.1-source-quality-state-machine.md) |
| DONE | P3-C58 | Event Window v3.2 Provider Confidence Resolver | [P3-C58](tasks/P3/p3-c58-event-window-v3.2-provider-confidence-resolver.md) |
| DONE | P3-C59 | Event Window Market Shock 状态机与 Overlay 升级 | [P3-C59](tasks/P3/p3-c59-event-window-market-shock状态机与overlay.md) |
| DONE | P3-C60 | Event Window partial_live functional live 语义治理 | [P3-C60](tasks/P3/p3-c60-event-window-partial-live-functional-live语义治理.md) |
| DONE | P3-C61 | Radar Runtime Module Freshness State Machine | [P3-C61](tasks/P3/p3-c61-radar-runtime-module-freshness-state-machine.md) |
| DONE | P3-C62 | BTC 4H/1D Direct Trend State Machine | [P3-C62](tasks/P3/p3-c62-btc-4h-1d-direct-trend-state-machine.md) |

## P4 Agent 推理与总控融合（Legacy）

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P4-C01 | Analyst Agent 输入输出 Schema | [P4-C01](tasks/P4/p4-c01-模块llm输入输出schema.md) |
| DONE | P4-C02 | 4 分析师 Agent Prompt 与证据约束 | [P4-C02](tasks/P4/p4-c02-模块llm-prompt模板与证据约束.md) |
| DONE | P4-C03 | 规则权重融合引擎 | [P4-C03](tasks/P4/p4-c03-规则权重融合引擎.md) |
| DONE | P4-C04 | BTC 状态机与状态切换规则 | [P4-C04](tasks/P4/p4-c04-btc状态机与状态切换规则.md) |
| DONE | P4-C05 | Evidence Pack 生成器 | [P4-C05](tasks/P4/p4-c05-evidence-pack生成器.md) |
| DONE | P4-C06 | 4 分析师 Agent 独立分析执行器 | [P4-C06](tasks/P4/p4-c06-多llm独立盲审.md) |
| DONE | P4-C07 | Analyst Agent 交叉质询与修正 | [P4-C07](tasks/P4/p4-c07-多llm交叉质询与修正.md) |
| DONE | P4-C08 | Judge Agent 主裁判合成与分歧处理 | [P4-C08](tasks/P4/p4-c08-主裁判合成与分歧处理.md) |
| DONE | P4-C09 | 反方审查机制 | [P4-C09](tasks/P4/p4-c09-反方审查机制.md) |
| DONE | P4-C10 | 最终总控 JSON 与观察建议输出 | [P4-C10](tasks/P4/p4-c10-最终总控json与观察建议输出.md) |
| DONE | P4-C11 | LLM 与总控 Mock 与 DoD 验收 | [P4-C11](tasks/P4/p4-c11-llm与总控mock与dod验收.md) |
| DONE | P4-C12 | P4 全链条复盘与真实数据契约对齐 | [P4-C12](tasks/P4/p4-c12-p4全链条复盘与真实数据契约对齐.md) |
| DONE | P4-C13 | P4 全量 Radar Evidence Pack 消费与新增事件指标契约 | [P4-C13](tasks/P4/p4-c13-p4全量radar-evidence-pack消费与新增事件指标契约.md) |
| DONE | P4-C14 | LLM 分析师历史记忆 SQLite 持久化与本轮调用契约 | [P4-C14](tasks/P4/p4-c14-llm分析师历史记忆sqlite持久化与本轮调用契约.md) |
| DONE | P4-C15 | OpenAI Agents SDK Runtime Adapter | [P4-C15](tasks/P4/p4-c15-openai-agents-sdk-runtime-adapter.md) |
| DONE | P4-C16 | P4 Agent 全链条重跑与审计 HTML | [P4-C16](tasks/P4/p4-c16-p4-agent全链条重跑与审计html.md) |
| DONE | P4-C17 | 提示词驱动中文文章生成与审计 HTML 可读化 | [P4-C17](tasks/P4/p4-c17-提示词驱动中文文章生成与审计html可读化.md) |
| DONE | P4-C18 | 全 Agent 真实 Runtime 切换与成本失败降级治理 | [P4-C18](tasks/P4/p4-c18-全agent真实runtime切换与成本失败降级治理.md) |
| DONE | P4-C19 | GPT 独立验证子线与 P4 结果对照 | [P4-C19](tasks/P4/p4-c19-gpt独立验证子线与p4结果对照.md) |
| DONE | P4-C20 | CrossExamRevision 修正回合与 Judge 输入契约 | [P4-C20](tasks/P4/p4-c20-crossexamrevision修正回合与judge输入契约.md) |
| DONE | P4-C21 | 反方审查 Revision 覆盖与发布门禁升级 | [P4-C21](tasks/P4/p4-c21-反方审查revision覆盖与发布门禁升级.md) |
| DONE | P4-C22 | Final Controller Revision Gate 与观察建议输出对齐 | [P4-C22](tasks/P4/p4-c22-final-controller-revision-gate与观察建议输出对齐.md) |
| DONE | P4-C23 | P4 审计 HTML Revision 链路可读化升级 | [P4-C23](tasks/P4/p4-c23-p4审计html-revision链路可读化升级.md) |
| DONE | P4-C24 | Final Controller 发布门控语义一致性与观察级输出治理 | [P4-C24](tasks/P4/p4-c24-final-controller发布门控语义一致性与观察级输出治理.md) |
| DONE | P4-C25 | Article Writer 深度中文研究报告生成与 Evidence 全量引用增强 | [P4-C25](tasks/P4/p4-c25-article-writer深度中文研究报告生成与evidence全量引用增强.md) |
| DONE | P4-C26 | Agent Runtime Provider、Schema Repair 与 No-Fallback 文章运行门控 | [P4-C26](tasks/P4/p4-c26-agent-runtime-provider-schema-repair与no-fallback文章运行门控.md) |
| DONE | P4-C27 | Research Article Writer 两阶段中文研究报告生成器 | [P4-C27](tasks/P4/p4-c27-research-article-writer两阶段中文研究报告生成器.md) |
| DONE | P4-C28 | P4 HTML Research View 与 Audit Appendix 分层可读化 | [P4-C28](tasks/P4/p4-c28-p4-html-research-view与audit-appendix分层可读化.md) |
| DONE | P4-C29 | Trend Sensitive Insight Writer 与约束分层治理 | [P4-C29](tasks/P4/p4-c29-trend-sensitive-insight-writer与约束分层治理.md) |
| DONE | P4-C30 | 发布门控约束分级与 Missing Signal 阈值治理 | [P4-C30](tasks/P4/p4-c30-发布门控约束分级与missing-signal阈值治理.md) |
| LEGACY | P4-C31 | 专业研究文章结构化长文生成与 Schema Repair 质量门控 | [P4-C31](tasks/P4/p4-c31-专业研究文章结构化长文生成与schema-repair质量门控.md) |

## P4.5 Research Report 与 P4 替代主线

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P4.5-C01 | Phase 架构与旧 P4 清理边界 | [P4.5-C01](tasks/P4.5/p4.5-c01-phase架构与旧p4清理边界.md) |
| DONE | P4.5-C02 | Scored Evidence Pack Builder | [P4.5-C02](tasks/P4.5/p4.5-c02-scored-evidence-pack-builder.md) |
| DONE | P4.5-C03 | 指标一句话解释词典与动态说明生成 | [P4.5-C03](tasks/P4.5/p4.5-c03-指标一句话解释词典与动态说明生成.md) |
| DONE | P4.5-C04 | 四分析员 Writer 提示词与输出 Schema | [P4.5-C04](tasks/P4.5/p4.5-c04-四分析员writer提示词与输出schema.md) |
| DONE | P4.5-C05 | Final Writer 综合研究文章生成 | [P4.5-C05](tasks/P4.5/p4.5-c05-final-writer综合研究文章生成.md) |
| DONE | P4.5-C06 | HTML 研究报告与证据附录 | [P4.5-C06](tasks/P4.5/p4.5-c06-html研究报告与证据附录.md) |
| DONE | P4.5-C07 | 旧 P4 Legacy 隔离与 CLI/API 切换 | [P4.5-C07](tasks/P4.5/p4.5-c07-旧p4-legacy隔离与cli-api切换.md) |
| DONE | P4.5-C08 | P1/P2/P3/P4.5 全链条真实重跑与验收 | [P4.5-C08](tasks/P4.5/p4.5-c08-p1p2p3p4.5全链条真实重跑与验收.md) |
| DONE | P4.5-C09 | LLM Research Writer 接入与全量 Evidence 深度中文研报生成 | [P4.5-C09](tasks/P4.5/p4.5-c09-llm-research-writer接入与全量evidence深度中文研报生成.md) |
| DONE | P4.5-C10 | 四分析师 LLM 板块深度分析追加到 P4.5 报告 | [P4.5-C10](tasks/P4.5/p4.5-c10-四分析师llm板块深度分析追加到p45报告.md) |
| DONE | P4.5-C11 | Research Report V2 契约、决策卡与聚合审计 | [P4.5-C11](tasks/P4.5/p4.5-c11-research-report-v2契约决策卡与聚合审计.md) |
| DONE | P4.5-C12 | HTML Report v2 决策视图、周期视图、反证条件与发文层渲染 | [P4.5-C12](tasks/P4.5/p4.5-c12-html-report-v2决策视图周期视图反证条件与发文层渲染.md) |
| DONE | P4.5-C13 | Final View 唯一主结论与方向一致性治理 | [P4.5-C13](tasks/P4.5/p4.5-c13-final-view唯一主结论与方向一致性治理.md) |
| DONE | P4.5-C14 | Horizon Driver 分类、聚合公式与反证规则结构化 | [P4.5-C14](tasks/P4.5/p4.5-c14-horizon-driver分类聚合公式与反证规则结构化.md) |
| DONE | P4.5-C15 | Research Article v2 与 Publish Article 发文层重写 | [P4.5-C15](tasks/P4.5/p4.5-c15-research-article-v2与publish-article发文层重写.md) |
| DONE | P4.5-C16 | v2 细节契约收口与 HTML 可读性治理 | [P4.5-C16](tasks/P4.5/p4.5-c16-v2细节契约收口与html可读性治理.md) |
| DONE | P4.5-C17 | P1/P2/P3/P4.5 含 LLM 一键全链条运行 | [P4.5-C17](tasks/P4.5/p4.5-c17-p1p2p3p45含llm一键全链条运行.md) |
| DONE | P4.5-C18 | Report v2 最后契约打磨与 LLM 附录治理 | [P4.5-C18](tasks/P4.5/p4.5-c18-report-v2最后契约打磨与llm附录治理.md) |
| DONE | P4.5-C19 | LLM Provider 统一 DeepSeek 与 Timeout 降级治理 | [P4.5-C19](tasks/P4.5/p4.5-c19-llm-provider统一deepseek与timeout降级治理.md) |
| DONE | P4.5-C20 | Decision Zero Ratio 与降级逻辑重构 | [P4.5-C20](tasks/P4.5/p4.5-c20-decision-zero-ratio与降级逻辑重构.md) |
| DONE | P4.5-C21 | Horizon Narrative Driver Side 一致性修复 | [P4.5-C21](tasks/P4.5/p4.5-c21-horizon-narrative-driver-side一致性修复.md) |
| DONE | P4.5-C22 | Fund Flow Pressure Note 边际语义精确化 | [P4.5-C22](tasks/P4.5/p4.5-c22-fund-flow-pressure-note边际语义精确化.md) |
| DONE | P4.5-C23 | Radar Module Detail API 透传 P3 复合语义字段 | [P4.5-C23](tasks/P4.5/p4.5-c23-radar-module-detail-api透传p3复合语义字段.md) |
| DONE | P4.5-C24 | Derivatives Long/Short Ratio 研报透传与解释契约 | [P4.5-C24](tasks/P4.5/p4.5-c24-derivatives-long-short-ratio研报透传与解释契约.md) |
| DONE | P4.5-C25 | Trade Structure Flow 复合状态研报透传与解释契约 | [P4.5-C25](tasks/P4.5/p4.5-c25-trade-structure-flow复合状态研报透传与解释契约.md) |
| DONE | P4.5-C26 | BTC Total State v2 研报方向、风险、上下文、审计分层解释 | [P4.5-C26](tasks/P4.5/p4.5-c26-btc-total-state-v2研报方向风险上下文审计分层解释.md) |
| DONE | P4.5-C27 | Options Volatility 报告层风险口径与方向禁语治理 | [P4.5-C27](tasks/P4.5/p4.5-c27-options-volatility报告层风险口径与方向禁语治理.md) |
| DONE | P4.5-C28 | Event Policy 报告层 risk lock 与方向禁语治理 | [P4.5-C28](tasks/P4.5/p4.5-c28-event-policy报告层risk-lock与方向禁语治理.md) |
| DONE | P4.5-C29 | Crypto Breadth v3 报告层趋势确认与宽度背离解释 | [P4.5-C29](tasks/P4.5/p4.5-c29-crypto-breadth-v3报告层趋势确认与宽度背离解释.md) |
| DONE | P4.5-C30 | Crypto Breadth v3 drivers 扁平化过滤修复 | [P4.5-C30](tasks/P4.5/p4.5-c30-crypto-breadth-v3-drivers扁平化过滤修复.md) |
| DONE | P4.5-C31 | Macro Radar v3 宏观解释层与单因子禁语治理 | [P4.5-C31](tasks/P4.5/p4.5-c31-macro-radar-v3宏观解释层与单因子禁语治理.md) |
| DONE | P4.5-C32 | Dollar Liquidity v2.1 报告层解释与单因子禁语治理 | [P4.5-C32](tasks/P4.5/p4.5-c32-dollar-liquidity-v2.1报告层解释与单因子禁语治理.md) |
| DONE | P4.5-C33 | Treasury Credit v2.1 报告解释与单因子禁语治理 | [P4.5-C33](tasks/P4.5/p4.5-c33-treasury-credit-v2.1报告解释与单因子禁语治理.md) |
| DONE | P4.5-C34 | Fund Flow v2.2 报告解释与资金流接受/拒绝禁语治理 | [P4.5-C34](tasks/P4.5/p4.5-c34-fund-flow-v2.2报告解释与资金流接受拒绝禁语治理.md) |
| DONE | P4.5-C35 | Onchain Valuation v2.2 报告解释与慢快变量禁语治理 | [P4.5-C35](tasks/P4.5/p4.5-c35-onchain-valuation-v2.2报告解释与慢快变量禁语治理.md) |
| DONE | P4.5-C36 | BTC Adoption v2.3 报告解释与采用度确认反证禁语治理 | [P4.5-C36](tasks/P4.5/p4.5-c36-btc-adoption-v2.3报告解释与采用度确认反证禁语治理.md) |
| DONE | P4.5-C37 | Asia Risk v2.3 报告解释与 BTC response first 禁语治理 | [P4.5-C37](tasks/P4.5/p4.5-c37-asia-risk-v2.3报告解释与btc-response-first禁语治理.md) |
| DONE | P4.5-C38 | Kline Orderflow v2.2 报告解释与主动流接受禁语治理 | [P4.5-C38](tasks/P4.5/p4.5-c38-kline-orderflow-v2.2报告解释与主动流接受禁语治理.md) |
| DONE | P4.5-C39 | Trade Structure Flow v2.3 报告解释与单因子禁语治理 | [P4.5-C39](tasks/P4.5/p4.5-c39-trade-structure-flow-v2.3报告解释与单因子禁语治理.md) |
| DONE | P4.5-C40 | Derivatives Crowding v2.5 报告解释与杠杆接受禁语治理 | [P4.5-C40](tasks/P4.5/p4.5-c40-derivatives-crowding-v2.5报告解释与杠杆接受禁语治理.md) |
| DONE | P4.5-C41 | BTC Trend Cockpit v2 聚合器与中心趋势状态机 | [P4.5-C41](tasks/P4.5/p4.5-c41-btc-trend-cockpit-v2聚合器与中心趋势状态机.md) |
| DONE | P4.5-C42 | Invalidation Workbench v2 规则生成器 | [P4.5-C42](tasks/P4.5/p4.5-c42-invalidation-workbench-v2规则生成器.md) |
| DONE | P4.5-C43 | BTC TimeScale Judge v2.1 聚合器 | [P4.5-C43](tasks/P4.5/p4.5-c43-btc-timescale-judge-v2.1聚合器.md) |
| DONE | P4.5-C44 | BTC Acceptance Gate 时间尺度接受度 | [P4.5-C44](tasks/P4.5/p4.5-c44-btc-acceptance-gate时间尺度接受度.md) |
| DONE | P4.5-C45 | Cross-Horizon Arbiter 多周期仲裁器 | [P4.5-C45](tasks/P4.5/p4.5-c45-cross-horizon-arbiter多周期仲裁器.md) |
| DONE | P4.5-C46 | Fed Speech Analyzer 与 Event Window Overlay 解释层 | [P4.5-C46](tasks/P4.5/p4.5-c46-fed-speech-analyzer与event-window-overlay.md) |
| DONE | P4.5-C47 | BTC Cockpit Fresh Snapshot Aggregator | [P4.5-C47](tasks/P4.5/p4.5-c47-cockpit-fresh-snapshot-aggregator.md) |
| DONE | P4.5-C48 | BTC 4H/1D Direct Trend Judge v2.2 | [P4.5-C48](tasks/P4.5/p4.5-c48-btc-4h-1d-direct-trend-judge-v2.2.md) |

## P5 Dashboard 与可视化层

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P5-C01 | 单页 Dashboard 拓扑布局 | [P5-C01](tasks/P5/p5-c01-单页dashboard拓扑布局.md) |
| DONE | P5-C02 | BTC 中心状态节点与闪耀机制 | [P5-C02](tasks/P5/p5-c02-btc中心状态节点与闪耀机制.md) |
| DONE | P5-C03 | Radar 拓扑节点动态连线、拖拽布局与数据源状态展示 | [P5-C03](tasks/P5/p5-c03-雷达分组节点与数据源状态展示.md) |
| DONE | P5-C04 | 预警面板与冷却期展示 | [P5-C04](tasks/P5/p5-c04-预警面板与冷却期展示.md) |
| DONE | P5-C05 | 事件倒计时与减产倒计时展示 | [P5-C05](tasks/P5/p5-c05-事件倒计时与减产倒计时展示.md) |
| DONE | P5-C05.5 | 时间尺度视图可读化与指标解释展示 | [P5-C05.5](tasks/P5/p5-c05.5-时间尺度视图可读化与指标解释展示.md) |
| LEGACY | P5-C06 | P4.5 LLM 附录摘要可视化（Legacy Debate 已隔离） | [P5-C06](tasks/P5/p5-c06-多llm讨论过程可视化.md) |
| DONE | P5-C07 | Run Once 按钮与全流程运行状态 | [P5-C07](tasks/P5/p5-c07-run-once按钮与全流程运行状态.md) |
| DONE | P5-C08 | 详细文章查看与历史文章列表 | [P5-C08](tasks/P5/p5-c08-详细文章查看与历史文章列表.md) |
| DONE | P5-C09 | BTC Detail Overview 子页面 | [P5-C09](tasks/P5/p5-c09-btc-detail-overview子页面.md) |
| DONE | P5-C10 | Evidence 证据页 | [P5-C10](tasks/P5/p5-c10-evidence证据页.md) |
| LEGACY | P5-C11 | P4.5 LLM 分析附录页（Legacy Debate 已隔离） | [P5-C11](tasks/P5/p5-c11-llm-debate多模型讨论页.md) |
| DONE | P5-C12 | Alerts 预警页 | [P5-C12](tasks/P5/p5-c12-alerts预警页.md) |
| DONE | P5-C13 | Invalidation 反证页 | [P5-C13](tasks/P5/p5-c13-invalidation反证页.md) |
| DONE | P5-C14 | Data Quality 数据质量页 | [P5-C14](tasks/P5/p5-c14-data-quality数据质量页.md) |
| DONE | P5-C15 | Run Logs 运行日志页 | [P5-C15](tasks/P5/p5-c15-run-logs运行日志页.md) |
| DONE | P5-C16 | Source Detail 数据源详情页 | [P5-C16](tasks/P5/p5-c16-source-detail数据源详情页.md) |
| DONE | P5-C17 | Radar Detail 雷达舱、指标节点与 Evidence 下钻 | [P5-C17](tasks/P5/p5-c17-radar-detail雷达详情页.md) |
| DONE | P5-C18 | History Replay 历史回放页 | [P5-C18](tasks/P5/p5-c18-history-replay历史回放页.md) |
| DONE | P5-C19 | 页面路由、右侧抽屉与全屏模式 | [P5-C19](tasks/P5/p5-c19-页面路由右侧抽屉与全屏模式.md) |
| DONE | P5-C20 | Vue3 API Client、状态管理与实时推送 | [P5-C20](tasks/P5/p5-c20-vue3-api-client状态管理与实时推送.md) |
| DONE | P5-C21 | Vue3 页面 Mock 与 DoD 验收 | [P5-C21](tasks/P5/p5-c21-vue3页面mock与dod验收.md) |
| DONE | P5-C22 | Settings 设置中心页面 | [P5-C22](tasks/P5/p5-c22-settings设置中心页面.md) |
| DONE | P5-C23 | 半自动数据源人工验证 UI | [P5-C23](tasks/P5/p5-c23-半自动数据源人工验证ui.md) |
| DONE | P5-C24 | 多源冲突证据展示与仲裁解释 | [P5-C24](tasks/P5/p5-c24-多源冲突证据展示与仲裁解释.md) |
| DONE | P5-C25 | P5 全链路契约对齐与 Dashboard 验收基线 | [P5-C25](tasks/P5/p5-c25-p5全链路契约对齐与dashboard验收基线.md) |
| DONE | P5-C26 | Dashboard 像素级还原、FastAPI 契约与页面验收矩阵 | [P5-C26](tasks/P5/p5-c26-dashboard像素级还原fastapi契约与页面验收矩阵.md) |
| DONE | P5-C27 | Web 页面乱码清理与 Mojibake 显示修复 | [P5-C27](tasks/P5/p5-c27-web页面乱码清理与mojibake显示修复.md) |
| DONE | P5-C28 | Evidence 页面排版压缩与评分可读化 | [P5-C28](tasks/P5/p5-c28-evidence页面排版压缩与评分可读化.md) |
| DONE | P5-C29 | Evidence 证据详情弹窗化与按钮样式修复 | [P5-C29](tasks/P5/p5-c29-evidence证据详情弹窗化与按钮样式修复.md) |
| DONE | P5-C30 | Evidence 滚动条暗色样式修复 | [P5-C30](tasks/P5/p5-c30-evidence滚动条暗色样式修复.md) |
| DONE | P5-C31 | 前端多接口加载容错与空态治理 | [P5-C31](tasks/P5/p5-c31-前端多接口加载容错与空态治理.md) |
| DONE | P5-C32 | Dashboard BTC Core 3D 金色动效与趋势光效治理 | [P5-C32](tasks/P5/p5-c32-dashboard-btc-core-3d金色动效与趋势光效治理.md) |
| DONE | P5-C33 | Dashboard Radar Node 轻量 3D Tilt 与拖拽深度协同 | [P5-C33](tasks/P5/p5-c33-dashboard-radar-node轻量3d-tilt与拖拽深度协同.md) |

| DONE | P5-C34 | Dashboard BTC Core 动态投影与 3D 悬浮感增强 | [P5-C34](tasks/P5/p5-c34-dashboard-btc-core动态投影与3d悬浮感增强.md) |

| DONE | P5-C35 | Run Logs Pipeline Progress 动态链路进度特效 | [P5-C35](tasks/P5/p5-c35-run-logs-pipeline-progress动态链路进度特效.md) |
| DONE | P5-C36 | Evidence 导航清空与弹窗状态隔离 | [P5-C36](tasks/P5/p5-c36-evidence导航清空与弹窗状态隔离.md) |
| DONE | P5-C37 | 前端 Run Pipeline 刷新恢复、运行中态持久化与 API 错误降噪 | [P5-C37](tasks/P5/p5-c37-前端run-pipeline刷新恢复运行中态持久化与api错误降噪.md) |
| DONE | P5-C38 | Dashboard deterministic 结论先行展示、LLM 异步补全与 Run 模式开关 | [P5-C38](tasks/P5/p5-c38-dashboard-deterministic结论先行展示llm异步补全与run模式开关.md) |
| DONE | P5-C39 | Radar Module 复合状态优先展示与 Fund Flow 语义防误导 | [P5-C39](tasks/P5/p5-c39-radar-module复合状态优先展示与fund-flow语义防误导.md) |
| DONE | P5-C40 | BTC 决策卡多周期语义完整展示与条件措辞校准 | [P5-C40](tasks/P5/p5-c40-btc决策卡多周期语义完整展示与条件措辞校准.md) |
| DONE | P5-C41 | Derivatives Long/Short Ratio 前端展示与语义防误导 | [P5-C41](tasks/P5/p5-c41-derivatives-long-short-ratio前端展示与语义防误导.md) |
| DONE | P5-C42 | Trade Structure Flow 复合状态前端展示与防误导 | [P5-C42](tasks/P5/p5-c42-trade-structure-flow复合状态前端展示与防误导.md) |
| DONE | P5-C43 | BTC Total State v2 四区块展示与方向防误导 | [P5-C43](tasks/P5/p5-c43-btc-total-state-v2四区块展示与方向防误导.md) |
| DONE | P5-C44 | Options Volatility 五区块 Radar Detail 展示 | [P5-C44](tasks/P5/p5-c44-options-volatility五区块radar-detail展示.md) |
| DONE | P5-C45 | Event Policy v2.1 trade_gate 与事件风险窗口前端展示对齐 | [P5-C45](tasks/P5/p5-c45-event-policy-v2.1-trade-gate与事件风险窗口前端展示对齐.md) |
| DONE | P5-C46 | 优化后 Radar Module 状态优先级、标签映射与指标展示口径收口 | [P5-C46](tasks/P5/p5-c46-优化后radar-module状态优先级标签映射与指标展示口径收口.md) |
| DONE | P5-C47 | Crypto Breadth v3 六区块 Radar Detail 展示 | [P5-C47](tasks/P5/p5-c47-crypto-breadth-v3六区块radar-detail展示.md) |
| DONE | P5-C48 | Macro Radar v3 八区块 Radar Detail 展示 | [P5-C48](tasks/P5/p5-c48-macro-radar-v3八区块radar-detail展示.md) |
| DONE | P5-C49 | Dollar Liquidity v2.1 八区块 Radar Detail 展示 | [P5-C49](tasks/P5/p5-c49-dollar-liquidity-v2.1八区块radar-detail展示.md) |
| DONE | P5-C50 | Treasury Credit v2.1 前端七区块展示 | [P5-C50](tasks/P5/p5-c50-treasury-credit-v2.1前端七区块展示.md) |
| DONE | P5-C51 | Fund Flow v2.2 四区块确认/拒绝状态展示 | [P5-C51](tasks/P5/p5-c51-fund-flow-v2.2四区块确认拒绝状态展示.md) |
| DONE | P5-C52 | Onchain Valuation v2.2 前端慢快分数、关键位与 Signal Stage 展示 | [P5-C52](tasks/P5/p5-c52-onchain-valuation-v2.2前端慢快分数关键位与signal-stage展示.md) |
| DONE | P5-C53 | BTC Adoption v2.3 前端 Fast/Core/Regime 与 Signal Stage 展示 | [P5-C53](tasks/P5/p5-c53-btc-adoption-v2.3前端fast-core-regime与signal-stage展示.md) |
| DONE | P5-C54 | Asia Risk v2.3 前端四区块与 BTC response 展示 | [P5-C54](tasks/P5/p5-c54-asia-risk-v2.3前端四区块与btc-response展示.md) |
| DONE | P5-C55 | Kline Orderflow v2.2 前端多时间尺度与主动流接受展示 | [P5-C55](tasks/P5/p5-c55-kline-orderflow-v2.2前端多时间尺度与主动流接受展示.md) |
| DONE | P5-C56 | Trade Structure Flow v2.3 前端多周期交易结构展示 | [P5-C56](tasks/P5/p5-c56-trade-structure-flow-v2.3前端多周期交易结构展示.md) |
| DONE | P5-C57 | Derivatives Crowding v2.5 前端趋势接受与拥挤脆弱展示 | [P5-C57](tasks/P5/p5-c57-derivatives-crowding-v2.5前端趋势接受与拥挤脆弱展示.md) |
| DONE | P5-C58 | 中央 BTC 卡片 v2 趋势驾驶舱展示 | [P5-C58](tasks/P5/p5-c58-中央btc卡片v2趋势驾驶舱展示.md) |
| DONE | P5-C59 | 雷达子页面 UI 整齐卡片与指标折叠优化 | [P5-C59](tasks/P5/p5-c59-雷达子页面ui整齐卡片与指标折叠优化.md) |
| DONE | P5-C60 | Invalidation / Confirmation Workbench v2 前端展示 | [P5-C60](tasks/P5/p5-c60-invalidation-confirmation-workbench-v2前端展示.md) |
| DONE | P5-C61 | 时间尺度视图 v2 前端展示 | [P5-C61](tasks/P5/p5-c61-时间尺度视图v2前端展示.md) |
| DONE | P5-C62 | Post Event Reaction Validator | [P5-C62](tasks/P5/p5-c62-post-event-reaction-validator.md) |
| DONE | P5-C63 | Event Window Policy Shock Watchtower v3 前端 | [P5-C63](tasks/P5/p5-c63-event-window-policy-shock-watchtower-v3前端.md) |
| DONE | P5-C64 | Event Watchtower 全局浮窗与弹窗层 | [P5-C64](tasks/P5/p5-c64-event-watchtower全局浮窗与弹窗层.md) |
| DONE | P5-C65 | Event Watchtower 独立子页面 | [P5-C65](tasks/P5/p5-c65-event-watchtower独立子页面.md) |
| DONE | P5-C66 | Dashboard 事件窗口 Summary Widget 改造 | [P5-C66](tasks/P5/p5-c66-dashboard事件窗口summary-widget改造.md) |
| DONE | P5-C67 | Event Watchtower Timeline / Calendar 子页视图 | [P5-C67](tasks/P5/p5-c67-event-watchtower-timeline-calendar子页视图.md) |
| DONE | P5-C68 | Event Window v3 Source Status UI | [P5-C68](tasks/P5/p5-c68-event-window-v3-source-status-ui.md) |
| DONE | P5-C69 | Event Window v3.1 Source Mesh UI | [P5-C69](tasks/P5/p5-c69-event-window-v3.1-source-mesh-ui.md) |
| DONE | P5-C70 | Event Window v3.2 Provider Mesh UI v2 | [P5-C70](tasks/P5/p5-c70-event-window-v3.2-provider-mesh-ui-v2.md) |
| DONE | P5-C71 | Event Watchtower 子页面按原型重排 | [P5-C71](tasks/P5/p5-c71-event-watchtower子页面按原型重排.md) |
| DONE | P5-C72 | Event Watchtower 浮窗与 Critical 警告层按原型优化 | [P5-C72](tasks/P5/p5-c72-event-watchtower浮窗与critical警告层按原型优化.md) |
| DONE | P5-C73 | Event Watchtower 按截图三栏布局精确对齐 | [P5-C73](tasks/P5/p5-c73-event-watchtower按截图三栏布局精确对齐.md) |
| DONE | P5-C74 | Event Watchtower Critical Overlay 行为与 Mock 态隔离 | [P5-C74](tasks/P5/p5-c74-event-watchtower-critical-overlay行为与mock态隔离.md) |
| DONE | P5-C75 | Event Watchtower 三份审计 HTML 内容入 UI | [P5-C75](tasks/P5/p5-c75-event-watchtower三份审计html内容入ui.md) |
| DONE | P5-C76 | Event Watchtower 事件 Ack、清除与可见性治理 | [P5-C76](tasks/P5/p5-c76-event-watchtower事件ack清除与可见性治理.md) |
| DONE | P5-C77 | Event Watchtower 独立 Run Once 按钮与 Bundle 入口 | [P5-C77](tasks/P5/p5-c77-event-watchtower独立run-once按钮与bundle入口.md) |
| DONE | P5-C78 | Event Watchtower Daemon Stale 与 Market Shock UI | [P5-C78](tasks/P5/p5-c78-event-watchtower-daemon-stale与market-shock-ui.md) |
| DONE | P5-C79 | Event Watch Floating Overlay 原型对齐 | [P5-C79](tasks/P5/p5-c79-event-watch-floating-overlay原型对齐.md) |
| DONE | P5-C80 | Event Watch Floating Overlay 静音小图标 | [P5-C80](tasks/P5/p5-c80-event-watch-floating-overlay静音小图标.md) |
| DONE | P5-C81 | Event Watchtower LLM 判断入 UI | [P5-C81](tasks/P5/p5-c81-event-watchtower-llm判断入ui.md) |
| DONE | P5-C82 | Event Watchtower Partial-live Source Quality 可见性加固 | [P5-C82](tasks/P5/p5-c82-event-watchtower-partial-live-source-quality-visibility-hardening.md) |
| DONE | P5-C83 | Event Watchtower Shock Fast Lane LLM 中文观察入 UI | [P5-C83](tasks/P5/p5-c83-event-watchtower-shock-fast-lane-llm中文观察入ui.md) |
| DONE | P5-C84 | Event Watchtower Shock LLM 同源入库与 UI 对齐修复 | [P5-C84](tasks/P5/p5-c84-event-watchtower-shock-llm同源入库与ui对齐修复.md) |
| DONE | P5-C85 | Radar Runtime Health UI | [P5-C85](tasks/P5/p5-c85-radar-runtime-health-ui.md) |
| DONE | P5-C86 | Radar Detail Center Card Composite Color | [P5-C86](tasks/P5/p5-c86-radar-detail-center-card-composite-color.md) |
| DONE | P5-C87 | BTC TimeScale Direct Trend UI Vue3 | [P5-C87](tasks/P5/p5-c87-btc-timescale-direct-trend-ui-vue3.md) |

## P6 发布、通知与策略表达

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P6-C01 | 自动文章生成流程 | [P6-C01](tasks/P6/p6-c01-自动文章生成流程.md) |
| DONE | P6-C02 | 手动文章生成与 Run Once 发文策略 | [P6-C02](tasks/P6/p6-c02-手动文章生成与run-once发文策略.md) |
| DONE | P6-C03 | 总控判断历史与 Evidence Pack 回放 | [P6-C03](tasks/P6/p6-c03-总控判断历史与evidence-pack回放.md) |
| DONE | P6-C04 | 预警历史与预警质量评分 | [P6-C04](tasks/P6/p6-c04-预警历史与预警质量评分.md) |
| DONE | P6-C05 | 24h/72h/7D 结果跟踪 | [P6-C05](tasks/P6/p6-c05-24h-72h-7d结果跟踪.md) |
| DONE | P6-C06 | 模块有效性与噪音评分 | [P6-C06](tasks/P6/p6-c06-模块有效性与噪音评分.md) |
| DONE | P6-C07 | 文章回放评分 Mock 与 DoD 验收 | [P6-C07](tasks/P6/p6-c07-文章回放评分mock与dod验收.md) |

## P7 回测、评估与策略校准

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P7-C01 | 模块权重动态调整 | [P7-C01](tasks/P7/p7-c01-模块权重动态调整.md) |
| DONE | P7-C02 | 状态机阈值与预警阈值校准 | [P7-C02](tasks/P7/p7-c02-状态机阈值与预警阈值校准.md) |
| DONE | P7-C03 | Prompt 版本管理 | [P7-C03](tasks/P7/p7-c03-prompt版本管理.md) |
| DONE | P7-C04 | 数据源健康监控与告警 | [P7-C04](tasks/P7/p7-c04-数据源健康监控与告警.md) |
| DONE | P7-C05 | Playwright 抓取稳定性增强 | [P7-C05](tasks/P7/p7-c05-playwright抓取稳定性增强.md) |
| DONE | P7-C06 | 成本控制、缓存、限流与重试 | [P7-C06](tasks/P7/p7-c06-成本控制缓存限流与重试.md) |
| DONE | P7-C07 | 权限、审计与配置化新增数据源 | [P7-C07](tasks/P7/p7-c07-权限审计与配置化新增数据源.md) |
| DONE | P7-C08 | 生产化校准 Mock 与 DoD 验收 | [P7-C08](tasks/P7/p7-c08-生产化校准mock与dod验收.md) |
| DONE | P7-C09 | 优化后 Radar Modules 全链路业务契约审计 | [P7-C09](tasks/P7/p7-c09-优化后radar-modules全链路业务契约审计.md) |
| DONE | P7-C10 | BTC Trend Cockpit 全链路审计与 DoD | [P7-C10](tasks/P7/p7-c10-btc-trend-cockpit全链路审计与dod.md) |
| DONE | P7-C11 | Invalidation Workbench 全链路审计 | [P7-C11](tasks/P7/p7-c11-invalidation-workbench全链路审计.md) |
| DONE | P7-C12 | Radar Module 反证语义收紧审计与修复 | [P7-C12](tasks/P7/p7-c12-radar-module反证语义收紧审计与修复.md) |
| DONE | P7-C13 | TimeScale Judge 全链路审计 | [P7-C13](tasks/P7/p7-c13-timescale-judge全链路审计.md) |
| DONE | P7-C14 | Event Window v3 全链路审计 | [P7-C14](tasks/P7/p7-c14-event-window-v3全链路审计.md) |
| DONE | P7-C15 | Event Window v3 Live Source 全链路审计 | [P7-C15](tasks/P7/p7-c15-event-window-v3-live-source全链路审计.md) |
| DONE | P7-C16 | Event Window 状态机、Overlay 与 LLM Analyzer 第二审计 HTML | [P7-C16](tasks/P7/p7-c16-event-window-state-overlay-llm-audit-html.md) |
| DONE | P7-C17 | Event Window Shock Fast Lane 第三审计 HTML 与 LLM 解释 | [P7-C17](tasks/P7/p7-c17-event-window-shock-fast-lane-llm-audit-html.md) |
| DONE | P7-C18 | Event Watchtower UI 全链路审计 | [P7-C18](tasks/P7/p7-c18-event-watchtower-ui全链路审计.md) |
| DONE | P7-C19 | Event Watchtower UI 截图对齐审计 | [P7-C19](tasks/P7/p7-c19-event-watchtower-ui截图对齐审计.md) |
| DONE | P7-C20 | Event Watchtower 审计 HTML 入 UI 与清除交互审计 | [P7-C20](tasks/P7/p7-c20-event-watchtower审计html入ui与清除交互审计.md) |
| DONE | P7-C21 | Event Window HTML 1/2/3 同源 Snapshot 审计 Runner | [P7-C21](tasks/P7/p7-c21-event-window-html123同源snapshot审计runner.md) |
| DONE | P7-C22 | Event Window 暴跌漏报回归审计 | [P7-C22](tasks/P7/p7-c22-event-window暴跌漏报回归审计.md) |
| DONE | P7-C23 | Event Windows 全面审计与断点排查 | [P7-C23](tasks/P7/p7-c23-event-windows全面审计与断点排查.md) |
| DONE | P7-C24 | P7-C16 Snapshot-specific SQLite 一致性修复 | [P7-C24](tasks/P7/p7-c24-fix-p7-c16-snapshot-specific-sqlite-consistency-check.md) |
| DONE | P7-C25 | Event Watchtower 离线确定性测试套件 | [P7-C25](tasks/P7/p7-c25-event-watchtower-deterministic-offline-test-suite.md) |
| DONE | P7-C26 | Event Window 审计 HTML 新鲜度门控与自动刷新修复 | [P7-C26](tasks/P7/p7-c26-event-window-audit-html-freshness-gate.md) |
| DONE | P7-C27 | Radar Runtime Daemon Full Chain Audit | [P7-C27](tasks/P7/p7-c27-radar-runtime-daemon-full-chain-audit.md) |
| DONE | P7-C28 | Radar Runtime Stale Feature Targeted Repair & Full-chain Audit | [P7-C28](tasks/P7/p7-c28-radar-runtime-stale-feature-targeted-repair-audit.md) |
| DONE | P7-C29 | Radar Metrics -> Module Score -> BTC Card -> Vue UI Freshness Chain Audit | [P7-C29](tasks/P7/p7-c29-radar-metrics-score-btc-ui-freshness-chain-audit.md) |
| DONE | P7-C30 | BTC 4H/1D Direct Trend Full Chain Audit | [P7-C30](tasks/P7/p7-c30-btc-4h-1d-direct-trend-full-chain-audit.md) |
| DONE | P7-C31 | BTC 4H-1D Direct Trend Replay Sample Builder & Walk-forward Evaluation | [P7-C31](tasks/P7/p7-c31-btc-4h-1d-direct-trend-replay-sample-builder-walk-forward-evaluation.md) |
| DONE | P7-C32 | Source Health Run Mode Production Gate Scope Repair | [P7-C32](tasks/P7/p7-c32-source-health-run-mode-production-gate-scope-repair.md) |
| DONE | P7-C33 | Sensitive Query Parameter Log Redaction | [P7-C33](tasks/P7/p7-c33-sensitive-query-parameter-log-redaction.md) |
| DONE | P7-C34 | Source Health Warning Severity Attribution Calibration | [P7-C34](tasks/P7/p7-c34-source-health-warning-severity-attribution-calibration.md) |
| DONE | P7-C35 | Radar Runtime Source Gate Async Collect Bridge | [P7-C35](tasks/P7/p7-c35-radar-runtime-source-gate-async-collect-bridge.md) |
| DONE | P7-C36 | Production Gate Remaining Warning Closure & Manual Acceptance | [P7-C36](tasks/P7/p7-c36-production-gate-remaining-warning-closure-manual-acceptance.md) |

## P8 SQLite、历史数据与持久化

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P8-C01 | SQLite 选型、WAL 与连接管理 | [P8-C01](tasks/P8/p8-c01-sqlite选型wal与连接管理.md) |
| DONE | P8-C02 | Alembic 迁移体系与基础 Schema 版本 | [P8-C02](tasks/P8/p8-c02-alembic迁移体系与基础schema版本.md) |
| DONE | P8-C03 | 数据源、原始观测与标准化指标表 | [P8-C03](tasks/P8/p8-c03-数据源原始观测与标准化指标表.md) |
| DONE | P8-C04 | 时序指标 metric_values 与历史窗口索引 | [P8-C04](tasks/P8/p8-c04-时序指标metric-values与历史窗口索引.md) |
| DONE | P8-C05 | Run Logs、Worker 与 Pipeline Stage 表 | [P8-C05](tasks/P8/p8-c05-run-logs-worker与pipeline-stage表.md) |
| DONE | P8-C06 | 雷达输出、特征值与模块 JSON 表 | [P8-C06](tasks/P8/p8-c06-雷达输出特征值与模块json表.md) |
| DONE | P8-C07 | 预警、反证、Evidence Pack 与 LLM Debate 表 | [P8-C07](tasks/P8/p8-c07-预警反证evidence-pack与llm-debate表.md) |
| DONE | P8-C08 | 文章、快照、History Replay 与评分表 | [P8-C08](tasks/P8/p8-c08-文章快照history-replay与评分表.md) |
| DONE | P8-C09 | Data Quality、Fallback、Rate Limit 与 Source Health 表 | [P8-C09](tasks/P8/p8-c09-data-quality-fallback-rate-limit与source-health表.md) |
| DONE | P8-C10 | Repository 层、查询服务与页面聚合 API | [P8-C10](tasks/P8/p8-c10-repository层查询服务与页面聚合api.md) |
| DONE | P8-C11 | 数据保留、归档、备份、VACUUM 与导出 | [P8-C11](tasks/P8/p8-c11-数据保留归档备份vacuum与导出.md) |
| DONE | P8-C12 | 数据库测试、种子数据与迁移验收 | [P8-C12](tasks/P8/p8-c12-数据库测试种子数据与迁移验收.md) |
| DONE | P8-C13 | SQLite 数据库 Mock 与 DoD 验收 | [P8-C13](tasks/P8/p8-c13-sqlite数据库mock与dod验收.md) |
| DONE | P8-C14 | Source Registry Reconciliation 与旧 source 归档 | [P8-C14](tasks/P8/p8-c14-source-registry-reconciliation与旧source归档.md) |
| DONE | P8-C15 | SQLite 双时间戳与 Freshness Policy 持久化 | [P8-C15](tasks/P8/p8-c15-sqlite双时间戳与freshness-policy持久化.md) |
| DONE | P8-C16 | run_mode 隔离与历史窗口过滤底座 | [P8-C16](tasks/P8/p8-c16-run-mode隔离与历史窗口过滤底座.md) |
| DONE | P8-C17 | run_mode 历史混用归档与生产窗口审计口径治理 | [P8-C17](tasks/P8/p8-c17-run-mode历史混用归档与生产窗口审计口径治理.md) |
| DONE | P8-C18 | BTC Total State v2 结构化 payload 持久化与回放兼容 | [P8-C18](tasks/P8/p8-c18-btc-total-state-v2结构化payload持久化与回放兼容.md) |
| DONE | P8-C19 | Options Volatility v2.1 payload 持久化与 replay | [P8-C19](tasks/P8/p8-c19-options-volatility-v2.1-payload持久化与replay.md) |
| DONE | P8-C20 | Event Policy v2.1 payload 持久化与 replay | [P8-C20](tasks/P8/p8-c20-event-policy-v2.1-payload持久化与replay.md) |
| DONE | P8-C21 | Crypto Breadth v3 payload 持久化与 replay | [P8-C21](tasks/P8/p8-c21-crypto-breadth-v3-payload持久化与replay.md) |
| DONE | P8-C22 | Macro Radar v3 payload 持久化与 replay | [P8-C22](tasks/P8/p8-c22-macro-radar-v3-payload持久化与replay.md) |
| DONE | P8-C23 | Dollar Liquidity v2.1 payload 持久化与 replay | [P8-C23](tasks/P8/p8-c23-dollar-liquidity-v2.1-payload持久化与replay.md) |
| DONE | P8-C24 | Treasury Credit v2.1 payload 持久化与 replay | [P8-C24](tasks/P8/p8-c24-treasury-credit-v2.1-payload持久化与replay.md) |
| DONE | P8-C25 | Fund Flow v2.2 payload 持久化与 replay | [P8-C25](tasks/P8/p8-c25-fund-flow-v2.2-payload持久化与replay.md) |
| DONE | P8-C26 | Onchain Valuation v2.2 payload 持久化与 replay | [P8-C26](tasks/P8/p8-c26-onchain-valuation-v2.2-payload持久化与replay.md) |
| DONE | P8-C27 | BTC Adoption v2.3 payload 持久化与 replay | [P8-C27](tasks/P8/p8-c27-btc-adoption-v2.3-payload持久化与replay.md) |
| DONE | P8-C28 | Asia Risk v2.3 payload 持久化与 replay | [P8-C28](tasks/P8/p8-c28-asia-risk-v2.3-payload持久化与replay.md) |
| DONE | P8-C29 | Kline Orderflow v2.2 payload 持久化与 replay | [P8-C29](tasks/P8/p8-c29-kline-orderflow-v2.2-payload持久化与replay.md) |
| DONE | P8-C30 | Trade Structure Flow v2.3 payload 持久化与 replay | [P8-C30](tasks/P8/p8-c30-trade-structure-flow-v2.3-payload持久化与replay.md) |
| DONE | P8-C31 | Derivatives Crowding v2.5 payload 持久化与 replay | [P8-C31](tasks/P8/p8-c31-derivatives-crowding-v2.5-payload持久化与replay.md) |
| DONE | P8-C32 | BTC Trend Cockpit payload 持久化与 replay | [P8-C32](tasks/P8/p8-c32-btc-trend-cockpit-payload持久化与replay.md) |
| DONE | P8-C33 | Invalidation Workbench payload 持久化与 replay | [P8-C33](tasks/P8/p8-c33-invalidation-workbench-payload持久化与replay.md) |
| DONE | P8-C34 | TimeScale Judge payload 持久化与 replay | [P8-C34](tasks/P8/p8-c34-timescale-judge-payload持久化与replay.md) |
| DONE | P8-C35 | Event Window v3 Payload、Source Fetch 与 Replay | [P8-C35](tasks/P8/p8-c35-event-window-v3-payload持久化与replay.md) |
| DONE | P8-C36 | Event Watchtower SQLite 独立事件时间线 Schema | [P8-C36](tasks/P8/p8-c36-event-watchtower-sqlite独立事件时间线schema.md) |
| DONE | P8-C37 | Event Window Market Probe 持久化与 Replay | [P8-C37](tasks/P8/p8-c37-event-window-market-probe持久化与replay.md) |
| DONE | P8-C38 | Radar Runtime SQLite Snapshots and Replay | [P8-C38](tasks/P8/p8-c38-radar-runtime-sqlite-snapshots.md) |
| DONE | P8-C39 | BTC TimeScale Direct Trend Judge SQLite Replay | [P8-C39](tasks/P8/p8-c39-btc-timescale-direct-trend-judge-sqlite-replay.md) |

## P9 FastAPI 聚合 API 与运维质控

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P9-C01 | API DTO、错误响应与前后端契约 | [P9-C01](tasks/P9/p9-c01-api-dto错误响应与前后端契约.md) |
| DONE | P9-C02 | Dashboard 与 BTC Overview 聚合 API | [P9-C02](tasks/P9/p9-c02-dashboard与btc-overview聚合api.md) |
| DONE | P9-C03 | Article 与 Evidence 聚合 API | [P9-C03](tasks/P9/p9-c03-article与evidence聚合api.md) |
| LEGACY | P9-C04 | P4.5 LLM 分析附录聚合 API（Legacy Debate 已隔离） | [P9-C04](tasks/P9/p9-c04-llm-debate聚合api.md) |
| DONE | P9-C05 | Alerts 与 Invalidation 聚合 API | [P9-C05](tasks/P9/p9-c05-alerts与invalidation聚合api.md) |
| DONE | P9-C06 | Data Quality 与 Source Detail 聚合 API | [P9-C06](tasks/P9/p9-c06-data-quality与source-detail聚合api.md) |
| DONE | P9-C07 | Run Logs 聚合 API 与 Run Once 触发接口 | [P9-C07](tasks/P9/p9-c07-run-logs聚合api与run-once触发接口.md) |
| DONE | P9-C08 | Radar Detail 聚合 API | [P9-C08](tasks/P9/p9-c08-radar-detail聚合api.md) |
| DONE | P9-C09 | History Replay 聚合 API 与历史模式 | [P9-C09](tasks/P9/p9-c09-history-replay聚合api与历史模式.md) |
| DONE | P9-C10 | SSE/WebSocket 实时推送与前端订阅 | [P9-C10](tasks/P9/p9-c10-sse-websocket实时推送与前端订阅.md) |
| DONE | P9-C11 | API 权限、审计、限流与脱敏 | [P9-C11](tasks/P9/p9-c11-api权限审计限流与脱敏.md) |
| DONE | P9-C12 | FastAPI 集成测试与页面契约验收 | [P9-C12](tasks/P9/p9-c12-fastapi集成测试与页面契约验收.md) |
| DONE | P9-C13 | FastAPI API Mock 与 DoD 验收 | [P9-C13](tasks/P9/p9-c13-fastapi-api-mock与dod验收.md) |
| DONE | P9-C14 | Settings 配置聚合 API（P10 + P9-C59 已覆盖） | [P9-C14](tasks/P9/p9-c14-settings配置聚合api.md) |
| DONE | P9-C15 | P4.5 Full Chain 后台 Job 化、运行状态持久化与刷新恢复 API | [P9-C15](tasks/P9/p9-c15-p45-full-chain后台job化运行状态持久化与刷新恢复api.md) |
| DONE | P9-C16 | Evidence Detail 按 final_run_id/pack_id 查询与 stale evidence fallback | [P9-C16](tasks/P9/p9-c16-evidence-detail按final-run-pack查询与stale-evidence-fallback.md) |
| DONE | P9-C17 | Run Full Chain execution_profile、skip_llm 契约与阶段状态治理 | [P9-C17](tasks/P9/p9-c17-run-full-chain-execution-profile-skip-llm契约与阶段状态治理.md) |
| DONE | P9-C18 | P45 Dashboard LLM lineage 按 final_run_id/pack_id 作用域隔离 | [P9-C18](tasks/P9/p9-c18-p45-dashboard-llm-lineage按final-pack作用域隔离.md) |
| DONE | P9-C19 | Dashboard Pressure Notes 映射与前端可消费契约 | [P9-C19](tasks/P9/p9-c19-dashboard-pressure-notes映射与前端可消费契约.md) |
| DONE | P9-C20 | Derivatives Long/Short Ratio API 契约与 Dashboard 透传 | [P9-C20](tasks/P9/p9-c20-derivatives-long-short-ratio-api契约与dashboard透传.md) |
| DONE | P9-C21 | Data Quality recent_failed 统计口径修复 | [P9-C21](tasks/P9/p9-c21-data-quality-recent-failed统计口径修复.md) |
| DONE | P9-C22 | Kline Display 语义字段透传与 Radar Detail API 修复 | [P9-C22](tasks/P9/p9-c22-kline-display语义字段透传与radar-detail-api修复.md) |
| DONE | P9-C23 | Trade Structure Flow 复合语义 API 透传 | [P9-C23](tasks/P9/p9-c23-trade-structure-flow复合语义api透传.md) |
| DONE | P9-C24 | BTC Total State v2 API 透传与契约 | [P9-C24](tasks/P9/p9-c24-btc-total-state-v2-api透传与契约.md) |
| DONE | P9-C25 | Options Volatility v2.1 API 透传与契约 | [P9-C25](tasks/P9/p9-c25-options-volatility-v2.1-api透传与契约.md) |
| DONE | P9-C26 | Crypto Breadth v3 API 透传与契约 | [P9-C26](tasks/P9/p9-c26-crypto-breadth-v3-api透传与契约.md) |
| DONE | P9-C27 | Macro Radar v3 API 透传与契约 | [P9-C27](tasks/P9/p9-c27-macro-radar-v3-api透传与契约.md) |
| DONE | P9-C28 | Dollar Liquidity v2.1 API 透传与契约 | [P9-C28](tasks/P9/p9-c28-dollar-liquidity-v2.1-api透传与契约.md) |
| DONE | P9-C29 | Treasury Credit v2.1 API 透传与契约 | [P9-C29](tasks/P9/p9-c29-treasury-credit-v2.1-api透传与契约.md) |
| DONE | P9-C30 | Fund Flow v2.2 API 透传与契约 | [P9-C30](tasks/P9/p9-c30-fund-flow-v2.2-api透传与契约.md) |
| DONE | P9-C31 | Onchain Valuation v2.2 API 透传与契约 | [P9-C31](tasks/P9/p9-c31-onchain-valuation-v2.2-api透传与契约.md) |
| DONE | P9-C32 | BTC Adoption v2.3 API 透传与契约 | [P9-C32](tasks/P9/p9-c32-btc-adoption-v2.3-api透传与契约.md) |
| DONE | P9-C33 | Asia Risk v2.3 API 透传与契约 | [P9-C33](tasks/P9/p9-c33-asia-risk-v2.3-api透传与契约.md) |
| DONE | P9-C34 | Kline Orderflow v2.2 API 透传与契约 | [P9-C34](tasks/P9/p9-c34-kline-orderflow-v2.2-api透传与契约.md) |
| DONE | P9-C35 | Trade Structure Flow v2.3 API 透传与契约 | [P9-C35](tasks/P9/p9-c35-trade-structure-flow-v2.3-api透传与契约.md) |
| DONE | P9-C36 | Derivatives Crowding v2.5 API 透传与契约 | [P9-C36](tasks/P9/p9-c36-derivatives-crowding-v2.5-api透传与契约.md) |
| DONE | P9-C37 | BTC Trend Cockpit API 透传 | [P9-C37](tasks/P9/p9-c37-btc-trend-cockpit-api透传.md) |
| DONE | P9-C38 | Invalidation Workbench v2 API 透传 | [P9-C38](tasks/P9/p9-c38-invalidation-workbench-v2-api透传.md) |
| DONE | P9-C39 | TimeScale Judge API 透传 | [P9-C39](tasks/P9/p9-c39-timescale-judge-api透传.md) |
| DONE | P9-C40 | Event Window v3 API 透传 | [P9-C40](tasks/P9/p9-c40-event-window-v3-api透传.md) |
| DONE | P9-C41 | Event Watchtower Daemon 常驻运行与推送 | [P9-C41](tasks/P9/p9-c41-event-watchtower-daemon常驻运行与推送.md) |
| DONE | P9-C42 | Event Watchtower Timeline / Calendar / Alert API | [P9-C42](tasks/P9/p9-c42-event-watchtower-timeline-calendar-alert-api.md) |
| DONE | P9-C43 | Event Window v3 Source Diagnostics API | [P9-C43](tasks/P9/p9-c43-event-window-v3-source-diagnostics-api.md) |
| DONE | P9-C44 | Event Watchtower 独立 Run Once 与审计 Bundle API | [P9-C44](tasks/P9/p9-c44-event-watchtower独立run-once与审计bundle-api.md) |
| DONE | P9-C45 | Event Watchtower 分频轮询 Scheduler 与 Manual Full Sweep | [P9-C45](tasks/P9/p9-c45-event-watchtower分频轮询scheduler与manual-full-sweep.md) |
| DONE | P9-C46 | Event Watchtower 运行时版本与 Heartbeat 守门 | [P9-C46](tasks/P9/p9-c46-event-watchtower运行时版本与heartbeat守门.md) |
| DONE | P9-C47 | Shock Lane Latest API 契约归一化 | [P9-C47](tasks/P9/p9-c47-normalize-shock-lane-latest-contract-shape.md) |
| DONE | P9-C48 | Event Watchtower Daemon Heartbeat / Watchdog / Health 加固 | [P9-C48](tasks/P9/p9-c48-event-watchtower-daemon-heartbeat-watchdog-health.md) |
| DONE | P9-C49 | Radar Runtime Daemon Scheduler Health API | [P9-C49](tasks/P9/p9-c49-radar-runtime-daemon-scheduler-health-api.md) |
| DONE | P9-C50 | Event Watchtower Scheduler Due Gate 修复与审计 | [P9-C50](tasks/P9/p9-c50-event-watchtower-scheduler-due-gate.md) |
| DONE | P9-C51 | Radar Runtime Audit HTML 常态刷新与异常即时落盘 | [P9-C51](tasks/P9/p9-c51-radar-runtime-audit-html常态刷新与异常即时落盘.md) |
| DONE | P9-C52 | Radar Runtime Cockpit Score Bridge | [P9-C52](tasks/P9/p9-c52-radar-runtime-cockpit-score-bridge.md) |
| DONE | P9-C53 | Radar Runtime SQLite Lock + Source Freshness Gate | [P9-C53](tasks/P9/p9-c53-radar-runtime-sqlite-lock-source-freshness-gate.md) |
| DONE | P9-C54 | Radar Runtime Source Refresh Gate | [P9-C54](tasks/P9/p9-c54-radar-runtime-source-refresh-gate.md) |
| DONE | P9-C55 | BTC TimeScale Direct Trend API Contract | [P9-C55](tasks/P9/p9-c55-btc-timescale-direct-trend-api-contract.md) |
| DONE | P9-C56 | Runtime Source Freshness Remaining Modules Repair | [P9-C56](tasks/P9/p9-c56-runtime-source-freshness-remaining-modules-repair.md) |
| DONE | P9-C57 | API Startup Nonblocking Daemon Bootstrap | [P9-C57](tasks/P9/p9-c57-api-startup-nonblocking-daemon-bootstrap.md) |
| DONE | P9-C58 | Settings API Supersession Reconciliation | [P9-C58](tasks/P9/p9-c58-settings-api-supersession-reconciliation.md) |
| DONE | P9-C59 | Settings Runtime/Data Source/Paths Read-only Contract | [P9-C59](tasks/P9/p9-c59-settings-runtime-data-source-paths-readonly-contract.md) |

## P10 扩展与配置治理

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P10-C01 | .env 配置规范与 Provider Registry | [P10-C01](tasks/P10/p10-c01-env配置规范与provider-registry.md) |
| DONE | P10-C02 | FastAPI Settings 与密钥脱敏状态读取 | [P10-C02](tasks/P10/p10-c02-fastapi-settings与密钥脱敏状态读取.md) |
| DONE | P10-C03 | UI 写入 .env 的配置更新服务 | [P10-C03](tasks/P10/p10-c03-ui写入env的配置更新服务.md) |
| DONE | P10-C04 | API Key 连通性测试与 Provider 健康检查 | [P10-C04](tasks/P10/p10-c04-api-key连通性测试与provider健康检查.md) |
| DONE | P10-C05 | LLM Provider 配置与模型路由准备 | [P10-C05](tasks/P10/p10-c05-llm-provider配置与模型路由准备.md) |
| DONE | P10-C06 | 密钥审计、脱敏、权限与操作日志 | [P10-C06](tasks/P10/p10-c06-密钥审计脱敏权限与操作日志.md) |
| DONE | P10-C07 | API Settings Mock 与 DoD 验收 | [P10-C07](tasks/P10/p10-c07-api-settings-mock与dod验收.md) |
| DONE | P10-C08 | Glassnode Provider 精确指标授权与 Entitlement 验证 | [P10-C08](tasks/P10/p10-c08-glassnode-provider精确指标授权与entitlement验证.md) |

## P11 非阻塞小问题集中修复池

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P11-C01 | Source Health recent_failed 当前 run 与历史窗口口径分离 | [P11-C01](tasks/P11/p11-c01-source-health-recent-failed当前run与历史窗口口径分离.md) |
| DONE | P11-C02 | P1 采集指标数与 P4.5 Evidence 指标数口径说明与 UI 统一 | [P11-C02](tasks/P11/p11-c02-p1采集指标数与p45-evidence指标数口径说明与ui统一.md) |
| DONE | P11-C03 | Radar Metric Node value 与 effective score 并列展示 | [P11-C03](tasks/P11/p11-c03-radar-metric-node-value与effective-score并列展示.md) |
| DONE | P11-C04 | derivatives_crowding 与 BTC Total State 合约口径 UI 解释对齐 | [P11-C04](tasks/P11/p11-c04-derivatives-crowding与btc-total-state合约口径ui解释对齐.md) |
| DONE | P11-C05 | Options RV 日 K 未来 source_ts 修复 | [P11-C05](tasks/P11/p11-c05-options-rv日k未来source-ts修复.md) |
| DONE | P11-C06 | Options RV daily closed candle freshness policy | [P11-C06](tasks/P11/p11-c06-options-rv-daily-closed-candle-freshness-policy.md) |
| DONE | P11-C07 | Options RV 历史 future source_ts replay 展示口径清理 | [P11-C07](tasks/P11/p11-c07-options-rv历史future-source-ts-replay展示口径清理.md) |
| DONE | P11-C08 | yield_curve_2s10s_change_bps 口径修复 | [P11-C08](tasks/P11/p11-c08-yield-curve-2s10s-change-bps口径修复.md) |
| DONE | P11-C09 | Crypto Breadth neutral state with bullish score 口径收口 | [P11-C09](tasks/P11/p11-c09-crypto-breadth-neutral-state-with-bullish-score口径收口.md) |
| DONE | P11-C10 | Macro Radar BTC relative confirmation missing 分类口径修复 | [P11-C10](tasks/P11/p11-c10-macro-radar-btc-relative-confirmation-missing分类口径修复.md) |
| DONE | P11-C11 | GitHub CI、Fresh Clone Smoke 与 Release Hygiene | [P11-C11](tasks/P11/p11-c11-github-ci-fresh-clone-smoke-release-hygiene.md) |
| DONE | P11-C12 | Frontend Dependency Security Audit 与 Lockfile Hygiene | [P11-C12](tasks/P11/p11-c12-frontend-dependency-security-audit-lockfile-hygiene.md) |
| DONE | P11-C13 | Backend Dependency 与 Python Toolchain Security Baseline | [P11-C13](tasks/P11/p11-c13-backend-dependency-python-toolchain-security-baseline.md) |
| DONE | P11-C14 | FastAPI Lifespan Migration 与 Startup Contract Cleanup | [P11-C14](tasks/P11/p11-c14-fastapi-lifespan-migration-startup-contract-cleanup.md) |
| DONE | P11-C15 | Release Commit Hygiene 与 GitHub Push | [P11-C15](tasks/P11/p11-c15-release-commit-hygiene-github-push.md) |
| DONE | P11-C16 | Runtime Report Working Tree Policy | [P11-C16](tasks/P11/p11-c16-runtime-report-working-tree-policy.md) |
| DONE | P11-C17 | pip-audit AV False Positive Hardening | [P11-C17](tasks/P11/p11-c17-pip-audit-av-false-positive-hardening.md) |
| DONE | P11-C18 | CI Status Check 与 GitHub Actions Follow-up | [P11-C18](tasks/P11/p11-c18-ci-status-check-github-actions-follow-up.md) |

## P12 系统级全链路审计与验收

| 状态 | 任务卡 | 标题 | 链接 |
|---|---|---|---|
| DONE | P12-C01 | System Full-chain Audit Master Plan 与 Evidence Inventory | [P12-C01](tasks/P12/p12-c01-system-full-chain-audit-master-plan-evidence-inventory.md) |
| DONE | P12-C02 | Business Chain Contract Audit | [P12-C02](tasks/P12/p12-c02-business-chain-contract-audit.md) |
| DONE | P12-C03 | Dashboard / P45 UI-API Contract Audit | [P12-C03](tasks/P12/p12-c03-dashboard-p45-ui-api-contract-audit.md) |
| DONE | P12-C04 | Radar Runtime / Module Score Full-chain Audit | [P12-C04](tasks/P12/p12-c04-radar-runtime-module-score-full-chain-audit.md) |
| DONE | P12-C05 | Event Window / Event Watchtower Full-chain Audit | [P12-C05](tasks/P12/p12-c05-event-window-watchtower-full-chain-audit.md) |
| DONE | P12-C06 | Data Source / Settings / Provider Governance Audit | [P12-C06](tasks/P12/p12-c06-data-source-settings-provider-governance-audit.md) |
| DONE | P12-C07 | SQLite / API / Report Lineage Release Acceptance Audit | [P12-C07](tasks/P12/p12-c07-sqlite-api-report-lineage-release-acceptance-audit.md) |
| DONE | P12-C08 | Frozen Final Lineage vs Live Runtime Freshness UI Label Hardening | [P12-C08](tasks/P12/p12-c08-frozen-final-lineage-live-runtime-freshness-ui-label-hardening.md) |
| DONE | P12-C09 | Source Action Endpoint Contract Completion | [P12-C09](tasks/P12/p12-c09-source-action-endpoint-contract-completion.md) |
| DONE | P12-C10 | P12 Audit Artifact Release Commit 与 CI Rerun | [P12-C10](tasks/P12/p12-c10-p12-audit-artifact-release-commit-ci-rerun.md) |
