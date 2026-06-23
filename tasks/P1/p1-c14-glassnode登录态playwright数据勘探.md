# P1-C14 Glassnode 公开数据与登录态 Playwright 数据勘探

## 状态

DONE

## Final Closure（2026-06-23）

P1-C14 已完成主线收口：

- Glassnode 匿名公开 dashboard/source 采集已落地并进入 P2/P4.5 主线。
- 登录态/订阅权限与精确 provider 指标已转入并完成 P10-C08 entitlement audit。
- 当前本机未配置 `ONLYBTC_GLASSNODE_API_KEY` 时，P10-C08 dry-run 正确输出 `provider_locked`，这是运行配置边界，不再阻塞 P1/P2/P4.5/P6 主线。
- 后续若用户提供 Glassnode key，只需重新运行 P10-C08 audit 并 review production write candidates。

## 所属 Phase

P1 数据源与历史数据底座

## 为什么单独成卡

Glassnode 与 P1-C13 不同。P1-C13 处理的是无需登录、无需授权、能稳定公开采集的数据；Glassnode 同时存在“公开 dashboard 匿名数据”和“登录/订阅权限数据”，必须单独验证：

- 用户需要在本地浏览器里手动登录，系统不能保存或读取密码。
- 登录态需要复用，但必须放在被 `.gitignore` 忽略的本地目录。
- 页面与接口可能随套餐权限变化，不能默认所有数据都可抓。
- 抓到的数据必须先做口径审计，再决定是否进入生产源。

## 任务目标

建立可复用的 Glassnode 登录态 Playwright 勘探流程，让用户本地登录后，系统可以在同一登录态下检查哪些 P2 缺口数据可获得、可稳定解析、可历史回溯。

同时，对无需登录即可访问的公开 dashboard，采用“快速刷新 + 网络响应截获”的方式采集，而不是依赖页面最终可见文本。

## 当前进度对齐（2026-05-20）

公开匿名 dashboard 采集已经进入生产源；登录态/订阅权限数据仍在勘探中。

## Status Alignment（2026-06-23）

P1-C14 曾改为 `SPLIT`：匿名公开 Glassnode 生产采集部分已完成并被后续 source freshness / radar runtime 任务验证；未完成部分仅限登录态、订阅权限和付费/高级指标可用性勘探，已转入并完成 P10-C08。

- 已完成公开主线：`playwright-glassnode-asset-overview`、`playwright-glassnode-sopr` 及相关 P2 指标消费。
- 已由后续任务覆盖 freshness 语义：P1-C33、P1-C34、P1-C35。
- 仍开放：需要用户登录态、订阅权限或官方 API key 的 realized price 变体、STH/LTH、鲸鱼/矿工流、稳定币交易所流入等。
- 这些开放项不阻塞 P1-C15/P1-C16/P1-C17 或 P2/P4.5/P6 主线，后续由 P10-C08 走 Provider Settings / entitlement 验证。

### 最新进度摘要

- 已完成 Glassnode 左侧 BTC 分类的第一轮全量巡检：Featured、Market、On-Chain、Indicators、Signals、Stablecoins、Guides 等入口均已展开检查。
- 已确认匿名公开可稳定采集的一批 endpoint，覆盖 ETF、BTC dominance、Fear & Greed、活跃地址、链上转账量、HODL waves、hash rate、difficulty、公司/政府持仓、NUPL、MVRV Z-Score、SOPR。
- 已确认多数高级指标在匿名状态下返回 403/429，不能直接作为免费公开生产源，包括 Realized Price、STH/LTH 成本基础、矿工流、Lightning 容量、Futures 清算、Options IV、精确 exchange netflow、稳定币交易所流入。
- 当前建议：P1-C14 保持 SPLIT；公开匿名源已经进入主线，登录态/订阅权限勘探转入 P10-C08。

| 范围 | 状态 | 说明 |
|---|---|---|
| Glassnode Asset Overview 匿名采集 | DONE | 已通过 Playwright 捕获页面匿名 `x-proxy-token`，再主动请求目标 `metrics-proxy` endpoint |
| SOPR 公开 chart 采集 | DONE | 已通过公开 chart 网络响应获得 `sopr` 最新值 |
| 5 分钟快速刷新策略 | DONE | 调度层按 300 秒刷新；采集器本身快速抓取，不等待 5 分钟 |
| P2 资金流补齐 | DONE | `etf_net_flow`、`etf_flow_7d` 已落库；`exchange_netflow` 使用交易所余额日变化做代理 |
| P2 采用率补齐 | DONE | `transfer_volume_adjusted_usd` 已进入 BTC 采用率雷达；`active_addresses` 与既有源交叉验证 |
| P2 链上估值部分补齐 | DONE | `nupl`、`mvrv_zscore`、`sopr` 已可真实采集 |
| 左侧分类全量巡检 | DONE | 已列出所有可见 dashboard，并标注匿名 200、403、429 的边界 |
| 可新增公开指标接入 | TODO | `fear_greed_index`、`btc_dominance`、`hodl_waves`、`btc_drawdown_from_ath`、公司/政府持仓等可作为下一批公开源 |
| 登录态/订阅权限勘探 | IN_PROGRESS | `realized_price`、STH/LTH 成本基础、鲸鱼/矿工流、稳定币交易所流入仍需继续验证 |

## 已验证的公开采集策略

用户观察到 `https://studio.glassnode.com/dashboards/asset-overview?a=BTC` 在刷新后短时间内可以看到数据。实测结果：

- 页面无登录可以打开。
- 直接用 `httpx` 请求指标接口会返回 `No token` 或 401，因为需要页面生成的匿名访客 token。
- 用 Playwright 打开页面后，关键 `metrics-proxy` 网络响应会较快返回。
- 即使页面存在 `Log in / Upgrade / Pricing` 文案，网络响应仍可被截获。
- 采集器不应等待 5 分钟；正确做法是刷新页面后快速等待目标响应，拿到后立即关闭页面。
- 调度层可以每 5 分钟刷新采集一次，符合“数据在刷新后 5 分钟内有效”的观察。

### 已接入公开数据

| 指标 | Glassnode 公开页面/接口 | 用法 | 质量口径 |
|---|---|---|---|
| `etf_net_flow` | Asset Overview / `institutions/us_spot_etf_flows_net` | 最新非空值 | 页面匿名 token，质量分 0.78 |
| `etf_flow_7d` | 同上 | 最近 7 个非空日值求和 | 本地计算，质量分 0.78 |
| `exchange_netflow` | Asset Overview / `distribution/balance_exchanges` | 交易所余额日变化代理 | 不是严格 netflow，质量分 0.70 |
| `active_addresses` | Asset Overview / `addresses/active_count` | 最新非空值 | 与 Blockchain.com 形成交叉验证，质量分 0.82 |
| `transfer_volume_adjusted_usd` | Asset Overview / `transactions/transfers_volume_adjusted_sum` | 最新非空值 | BTC 采用率/链上活跃补充，质量分 0.78 |
| `nupl` | Asset Overview / `indicators/net_unrealized_profit_loss` | 最新非空值 | 链上估值补充，质量分 0.78 |
| `mvrv_zscore` | Asset Overview / `market/mvrv_z_score` | 最新非空值 | 链上估值核心指标，质量分 0.78 |
| `sopr` | SOPR Chart / `indicators/sopr` | 最新非空值 | 公开 chart 数据，质量分 0.76 |

## 左侧分类 Dashboard 勘探结果（2026-05-20）

已按左侧分类逐项展开并巡检 BTC dashboard。结论：Glassnode Studio 的 BTC 左侧目录非常有价值，但匿名公开可稳定采集的数据集中在 Overview、ETF、网络基础、部分储备/持仓、少数市场指标；多数高级链上、衍生品、交易所风险、成本基础和稳定币交易所流量返回 403/429，需要登录态、订阅权限或官方 API key。

### 左侧分类与 Dashboard 入口

| 分类 | Dashboard |
|---|---|
| Featured | Overview, Multi-Asset Explorer, Options Pulse |
| Spot | Market, Volume |
| Futures | Open Interest & Volume, Funding Rates, Liquidations, Term Structure & Rolling Basis, Hyperliquid, CME |
| Options | Open Interest & Volume, Implied Volatility, Options Pulse, Premiums |
| ETFs | Balances & Flows |
| DATs | Public Companies, Strategic Reserves |
| Fundamentals | Network Statistics, Miners, Mempool, Lightning Network |
| Supply Dynamics | Unspent Supply Dynamics, Spent Supply Dynamics, Government & Company Holdings, Supply Investor Behaviour |
| Profit & Loss | Unrealized Profit/Loss, Realized Profit/Loss, Cost Basis Distribution, Profitability Map |
| Exchanges | Exchange Balances & Flows, Exchange Risk, Proof of Reserves |
| Indicators | Cycle top/bottom, seller exhaustion, trading models, momentum, bear/bull frameworks, altcoin season |
| Signals | Bitcoin Sharpe Signal, SBT Signals |
| Stablecoins | Stablecoin Supplies, Stablecoin Activity, Stablecoins and Exchanges, Next-Gen Stablecoins |
| Other / Guides | Engine Room, Deep Dives, On-chain tutorials, HODLers essentials, Workbench examples |

### 当前匿名公开可采集的 BTC 数据

这些 endpoint 已在无登录状态下返回 200，或已经通过 Overview/SOPR 页面完成真实采集验证。可进入生产源，但仍需记录 `source=glassnode_public`、`permission=anonymous`、`quality_score` 与 token 机制风险。

| 业务域 | Glassnode endpoint / chart | 可形成的系统指标 | 价值 |
|---|---|---|---|
| 市场价格 | `market/price_usd_close` | `btc_price`, 历史价格补源 | 与交易所价格交叉验证 |
| 市值 | `market/marketcap_usd` | `btc_marketcap_usd` | BTC 总状态、估值背景 |
| 回撤 | `market/price_drawdown_relative` | `btc_drawdown_from_ath` | 周期风险、顶部/底部框架 |
| 恐惧贪婪 | `indicators/fear_greed` | `fear_greed_index` | 情绪/风险偏好 |
| BTC Dominance | `market/btc_dominance` | `btc_dominance` | 加密市场广度 |
| ETF 净流入 | `institutions/us_spot_etf_flows_net` | `etf_net_flow`, `etf_flow_7d` | 资金流核心指标 |
| ETF 全量流量 | `institutions/us_spot_etf_flows_all` | `etf_flow_by_issuer` | ETF 发行商拆分、交叉验证 |
| ETF 持仓余额 | `institutions/us_spot_etf_balances_all` | `etf_balance_by_issuer` | 机构持仓趋势 |
| 交易所余额 | `distribution/balance_exchanges` | `exchange_balance`, `exchange_netflow_proxy` | 用余额日变化代理净流 |
| 活跃地址 | `addresses/active_count` | `active_addresses` | BTC 采用率 |
| 新非零地址 | `addresses/new_non_zero_count` | `new_non_zero_addresses` | 新用户/采用率补充 |
| 交易笔数 | `transactions/count` | `tx_count` | 链上活跃度 |
| 转账总量 | `transactions/transfers_volume_sum` | `transfer_volume_sum` | 链上流量 |
| 调整后转账量 | `transactions/transfers_volume_adjusted_sum` | `transfer_volume_adjusted_usd` | 采用率/真实经济活动 |
| 当前供应量 | `supply/current` | `btc_supply_current` | 市值、供应背景 |
| 1 年以上未动供应 | `supply/active_more_1y_percent` | `supply_active_more_1y_pct` | HODL 行为 |
| HODL Waves | `supply/hodl_waves` | `hodl_waves` | 筹码年龄结构 |
| 哈希率 | `mining/hash_rate_mean` | `hash_rate_mean` | 网络安全、矿工背景 |
| 难度 | `mining/difficulty_latest` | `mining_difficulty` | 网络基础指标 |
| 平均区块大小 | `blockchain/block_size_mean` | `block_size_mean` | 链上使用强度 |
| 平均出块间隔 | `blockchain/block_interval_mean` | `block_interval_mean` | 网络运行状态 |
| 公司 BTC 持仓 | `treasuries/balance_companies` | `company_treasury_balance` | DAT/企业采用 |
| 政府 BTC 持仓 | `treasuries/balance_governments` | `government_treasury_balance` | 主权/战略储备 |
| 萨尔瓦多持仓 | `distribution/balance_el_salvador` | `el_salvador_balance` | 主权采用补充 |
| NUPL | `indicators/net_unrealized_profit_loss` | `nupl` | 链上估值 |
| MVRV Z-Score | `market/mvrv_z_score` | `mvrv_zscore` | 链上估值核心 |
| SOPR | `indicators/sopr` | `sopr` | 盈亏兑现/筹码行为 |

### 匿名可见但当前不可直接生产采集的数据

这些 dashboard/chart 在页面中可见或可发起请求，但巡检时返回 403/429。它们仍然有很高业务价值，应作为登录态/订阅权限勘探候选，而不是匿名公开源。

| 分类 | 高价值候选 endpoint | 对应系统指标 | 当前状态 |
|---|---|---|---|
| Spot | `market/price_usd_ohlc`, `market/realized_volatility_all`, `market/spot_vd_sum`, `market/spot_volume_daily_sum_all` | OHLC/RV/现货量/成交 delta | 403 |
| Futures | `derivatives/futures_open_interest_sum_all`, `derivatives/futures_volume_daily_sum_all`, `derivatives/futures_funding_rate_perpetual`, `derivatives/futures_liquidated_volume_long_sum`, `derivatives/futures_liquidated_volume_short_sum` | OI、成交量、Funding、清算多空 | 403 |
| Futures | `derivatives/futures_cme_open_interest_sum`, `derivatives/futures_cme_volume_daily_sum`, `derivatives/futures_term_structure`, `derivatives/futures_annualized_basis_3m` | CME OI/成交量、期限结构、滚动基差 | 403 |
| Options | `derivatives/options_open_interest_sum`, `derivatives/options_volume_put_call_ratio`, `derivatives/options_open_interest_put_call_ratio`, `derivatives/options_atm_implied_volatility_*`, `options/options_premiums` | 期权 OI、Put/Call、IV、Premium | 403 |
| Miners | `mining/revenue_from_fees`, `mining/revenue_sum`, `distribution/balance_miners_change`, `transactions/transfers_volume_miners_to_exchanges` | 矿工收入、矿工余额变化、矿工到交易所流量 | 403 |
| Mempool | `mempool/fees_sum`, `mempool/txs_count_sum`, `mempool/fees_average_relative`, `mempool/txs_size_distribution` | 手续费压力、mempool 拥堵 | 403 |
| Lightning | `lightning/network_capacity_sum`, `lightning/nodes_count`, `lightning/channels_count`, `lightning/channel_size_mean` | Lightning 采用率 | 403 |
| Supply | `supply/lth_sum`, `supply/sth_sum`, `supply/hodl_waves`, `addresses/accumulation_balance`, `indicators/hodler_net_position_change`, `indicators/liveliness` | STH/LTH 供应、囤币行为、活跃性 | 部分 403；`hodl_waves` 已在 Overview 公开可取 |
| Profit/Loss | `market/price_realized_usd`, `market/marketcap_realized_usd`, `supply/sth_profit_loss_ratio`, `indicators/sopr_adjusted`, `indicators/net_realized_profit_loss`, `breakdowns/sopr_by_age` | Realized Price、Realized Cap、aSOPR、年龄段 SOPR、净实现盈亏 | 403/429 |
| Cost Basis | CBD / profitability map 相关页面 | 成本基础分布、筹码盈利地图 | 页面需进一步登录态确认 |
| Exchanges | `distribution/exchange_net_position_change`, `transactions/transfers_volume_exchanges_net_by_size`, `transactions/transfers_to_exchanges_count`, `addresses/sending_to_exchanges_count` | 精确交易所净流、交易所转入、地址数 | 403 |
| Exchanges | `distribution/exchange_whales_outflow`, `distribution/exchange_reliance_ratio`, `distribution/proof_of_reserves_all` | 交易所鲸鱼流出、交易所风险、PoR | 403 |
| Indicators | `indicators/puell_multiple`, `indicators/reserve_risk`, `indicators/rhodl_ratio`, `indicators/dormancy_flow`, `market/mvrv`, `market/mvrv_less_155`, `market/mvrv_more_155` | 周期顶部/底部、STH/LTH MVRV | 403 |
| Signals | `signals/btc_sharpe_signal` | Sharpe Signal | 403 |
| Stablecoins | `indicators/ssr`, `indicators/ssr_oscillator`, `distribution/exchange_net_position_change` | SSR、稳定币交易所流入/流出代理 | 403/429 |

### 对 onlyBTC 的接入优先级

| 优先级 | 建议接入 | 原因 |
|---|---|---|
| P0 | 已接入项继续稳定化：ETF Flow、MVRV Z-Score、NUPL、SOPR、活跃地址、调整后转账量、交易所余额代理 | 直接提升 P2 资金流、采用率、链上估值 |
| P1 | 补充公开可取：`fear_greed_index`、`btc_dominance`、`hodl_waves`、`btc_drawdown_from_ath`、公司/政府持仓 | 对宏观情绪、市场广度、筹码结构有价值，且匿名可取 |
| P2 | 登录态勘探：Realized Price、STH/LTH MVRV、LTH/STH Supply、矿工流、精确 exchange net position change | 直接补 P2 链上估值与筹码、交易结构缺口 |
| P3 | 订阅/provider 决策：期权 IV、CME OI、清算、稳定币交易所流入、Sharpe Signal | Glassnode 匿名多为 403，若要生产可靠，优先走 provider/API key |

### 快速采集 DoD

- 每次采集打开新页面。
- 监听目标 network response。
- 目标响应全部到齐后立即保存 artifact 并关闭页面。
- 默认最多等待 10 秒；超时后记录 source health warning/error。
- 不依赖 DOM 最终文本，不等待遮罩消失。
- 调度层刷新间隔建议 5 分钟，后续可按数据源健康状态调整到 10 分钟。

### 当前实测结果

- 单独采集 `playwright-glassnode-asset-overview` 与 `playwright-glassnode-sopr` 已验证 errors = 0；耗时受浏览器启动、页面网络和 endpoint 数量影响，通常按十几到二十几秒预算。
- 资金流雷达 `fund_flow` 已从 low 提升为 high。
- BTC 采用率雷达 `btc_adoption` 已提升为 high，仍缺 `lightning_capacity`。
- 链上估值雷达已获得 `nupl`、`mvrv_zscore`、`sopr`，但因缺少成本基础与地址标签类指标，整体仍可能为 low。
- 最新落库样本：
  - `etf_net_flow`
  - `etf_flow_7d`
  - `exchange_netflow`
  - `active_addresses`
  - `transfer_volume_adjusted_usd`
  - `nupl`
  - `mvrv_zscore`
  - `sopr`
- `exchange_netflow` 当前是 exchange balance 日变化代理，不是严格链上净流入，必须在 UI/Data Quality 中显示降权说明。
- 当前采集策略适合加入调度器，建议 interval = 300 秒。

## 登录态与安全原则

- 不要求用户提供账号、密码或 2FA 码。
- 由用户在本机弹出的 headed Chromium 中自行登录 Glassnode。
- 登录态只保存为本地 Playwright profile / storage state。
- 推荐路径：
  - 浏览器 profile：`playwright-artifacts/auth/glassnode-profile/`
  - storage state：`playwright-artifacts/auth/glassnode-storage-state.json`
- `playwright-artifacts/*` 已在 `.gitignore` 中忽略，不进入仓库。
- 日志与 artifact 不允许保存 cookie、token、authorization header、完整 localStorage。
- Source Detail / Data Quality 只展示脱敏后的登录态状态：`configured=true/false`、`last_verified_at`、`permission_level`。

## 可优先验证的 P2 缺口

| P2 雷达 | 指标 | Glassnode 可能路径 | 验证重点 |
|---|---|---|---|
| 链上估值与筹码 | `mvrv_zscore` | Asset Overview / metrics-proxy | 已公开打通；后续只需做历史窗口和交叉验证 |
| 链上估值与筹码 | `realized_price` | Studio chart / API endpoint | 是否有 BTC 全历史，单位口径 |
| 链上估值与筹码 | `sopr` | SOPR chart / API endpoint | 已公开打通 SOPR；aSOPR 等变体仍需确认权限 |
| 链上估值与筹码 | `sth_cost_basis` | Studio chart / API endpoint | STH realized price 口径 |
| 链上估值与筹码 | `lth_cost_basis` | Studio chart / API endpoint | LTH realized price 口径 |
| 链上估值与筹码 | `whale_flow` | Entity / exchange / whale metric | 是否可用，是否为派生口径 |
| 链上估值与筹码 | `miner_flow` | Miner outflow / miner balance | 是否可用，周期与单位 |
| 资金流雷达 | `exchange_netflow` | Exchange net position change / exchange netflow | 是否覆盖 BTC，是否日频/小时频 |
| 交易结构/链上衍生品流量 | `stablecoin_exchange_inflow` | Stablecoin exchange inflow | 是否支持多链与交易所标签 |

## 当前仍未公开打通的数据

| 指标 | 当前观察 | 结论 |
|---|---|---|
| `realized_price` | 常见 code 探测 404/未确认 | 需继续目录勘探 |
| `sth_cost_basis` | 常见 code 探测未命中 | 需登录后确认指标 code |
| `lth_cost_basis` | 常见 code 探测未命中 | 需登录后确认指标 code |
| `whale_flow` | asset overview 未覆盖 | 需登录/订阅或 provider API |
| `miner_flow` | dashboard 只有 hash rate，未见 miner flow | 需登录/订阅或 provider API |
| `stablecoin_exchange_inflow` | asset overview 未覆盖 | 需登录/订阅或 provider API |
| 精确 `exchange_netflow` | 当前仅有交易所余额日变化代理 | 需登录/订阅或 provider API 精确化 |

## 实施步骤

1. Auth bootstrap
   - 新增可复用 Playwright 登录态工具。
   - 支持 `provider=glassnode`。
   - 启动 headed browser，打开 Glassnode 登录页。
   - 用户手动登录完成后，保存 storage state。

2. Auth verification
   - 使用 storage state 启动 headless browser。
   - 打开 Glassnode Studio 或目标 chart。
   - 判断是否处于已登录状态。
   - 记录脱敏后的 provider health。

3. Data discovery
   - 对候选指标逐个打开页面或网络请求。
   - 保存 HTML artifact、截图、可用字段、样本值、时间范围。
   - 记录是否需要更高套餐、是否被登录墙/权限墙拦截。

4. Metric mapping
   - 将可用指标映射到 P2 metric_id。
   - 明确单位、时间粒度、刷新频率、历史窗口、质量分。
   - 区分“可直接采集”“只能人工观察”“需要 API key”“需要付费升级”。

5. Production decision
   - 能稳定采集的进入后续 source registry。
   - 不稳定页面抓取只作为人工勘探或低频 fallback。
   - 如果 Glassnode 提供 API key，优先转 P10 provider key 方式，不长期依赖页面抓取。

## 产出

- 可复用登录态 Playwright 方案说明。
- Glassnode 可用指标审计表。
- 每个候选指标的 artifact 路径和数据质量判断。
- P2 缺口映射清单：已解决、可解决但待 API key、权限不足、不可用。
- 后续生产接入任务建议。

## DoD

- 用户可以不透露密码完成本地 Glassnode 登录态保存。
- 复用登录态后可以 headless 验证 Glassnode 已登录。
- 至少验证链上估值与筹码雷达的 5 个核心指标可见性。
- 每个指标都必须给出：是否可抓、是否有历史、单位、频率、权限要求、推荐接入方式。
- 不把 cookie/token/storage state 提交到仓库。
- 失败时进入 source health / provider health，而不是阻塞 P1/P2 主链路。

## 依赖任务

P1-C06、P1-C07、P1-C13、P7-C05、P7-C07、P10-C01、P10-C04。

## 备注

Glassnode 页面抓取只能作为勘探或 fallback。长期生产最好走官方 API key/provider registry；如果页面能看到但 API 不可用，需要在 Data Quality 中明确降权。
