# P1-C13 P2 剩余付费与 Playwright 数据源补齐

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座

## 本轮已完成

已按“低风险公开源优先、Playwright 只补公开页面缺口”的顺序补齐一批可真实运行的数据：

## 与 P1-C14 的进度边界（2026-05-20）

P1-C13 保持 DONE，定位为“P2 剩余指标路线审计 + 通用公开源补齐”。Glassnode 相关工作不再继续塞进 C13，而由 P1-C14 单独承接。

| 范围 | 当前状态 | 归属 |
|---|---|---|
| FRED / 交易所 / Deribit / CoinGecko / TradingView 公开补齐 | 已完成并通过 live 采集 | P1-C13 |
| `etf_net_flow`、`etf_flow_7d` | 已由 Glassnode 公开 dashboard 快速采集补齐 | P1-C14 |
| `exchange_netflow` | 已由 Glassnode 交易所余额日变化做代理补齐，质量降权 | P1-C14 |
| `active_addresses`、`transfer_volume_adjusted_usd` | 已由 Glassnode 公开 dashboard 补充 BTC 采用率 | P1-C14 |
| `nupl`、`mvrv_zscore`、`sopr` | 已由 Glassnode 公开 dashboard/chart 补齐 | P1-C14 |
| `realized_price`、STH/LTH 成本基础、鲸鱼/矿工流、稳定币交易所流入 | 仍需登录态/订阅权限或 provider API | P1-C14 / P10 |

### 已接入公开 API / 本地计算

| 指标 | 实现方式 | 给到的 P2 雷达 | 质量口径 |
|---|---|---|---|
| `tga` | FRED `WDTGAL` | 美元流动性雷达 | 官方源，周频 |
| `jgb_10y` | FRED `IRLTLT01JPM156N` + TradingView fallback | 亚洲风险雷达 | FRED 慢变量，TV 高频补充 |
| `taker_buy_sell_ratio` | Binance futures `takerlongshortRatio` | 交易结构/链上衍生品流量 | 公开 API，5m |
| `options_rv` | Binance BTCUSDT 日线收盘价计算 30D 年化 RV | 期权波动率雷达 | 本地计算 |
| `top50_strength` | CoinGecko Top50 24h 上涨比例 | 加密市场广度雷达 | 公开 API，等权广度 |
| `max_pain_distance` | Deribit option chain 本地计算 | 期权波动率雷达 | 公开 API，近似计算 |
| `gamma_wall_distance` | Deribit open interest 最大集中 strike 近似 | 期权波动率雷达 | 低置信代理，不等于专业 Greeks |

### 已接入 TradingView Playwright

| 指标 | TradingView URL | 给到的 P2 雷达 | 说明 |
|---|---|---|---|
| `dxy_proxy` | `https://www.tradingview.com/symbols/TVC-DXY/` | 宏观雷达 | 作为 FRED broad dollar index 的精确 DXY fallback |
| `jgb_10y` | `https://www.tradingview.com/symbols/TVC-JP10Y/` | 亚洲风险雷达 | 弥补 FRED JGB 月频滞后 |
| `topix` | `https://www.tradingview.com/symbols/TSE-TOPIX/` | 亚洲风险雷达 | P2 亚洲风险缺口 |
| `hang_seng_tech` | `https://www.tradingview.com/symbols/HSI-HSTECH/` | 亚洲风险雷达 | P2 亚洲风险缺口 |

### 真实采集验收

- `collect-sources --mode live`：40 个 source 注册，39 个成功产出指标，errors = 0。
- 最新每个 source 的 `SourceRun` 状态：无 error。
- `analyze-radars`：14 个 P2 雷达全部完成分析。
- 已达到 high 数据质量的雷达：BTC 总状态、宏观、美元流动性、美债信用、K 线、衍生品拥挤、期权波动率、加密市场广度、亚洲风险。
- 仍为 medium / low 的雷达，原因不是计算链路断开，而是缺少 provider 或需要事件日历/NLP：资金流、BTC 采用率、链上估值、交易结构流量、事件政策。

## 任务目标

补齐 P2 全量雷达中尚未完全真实覆盖的指标，并明确每个指标的最佳路线：

- 本地计算：由已采集的历史价格、期权链、ETF 日流量等计算得到。
- 公开 API：不需要登录或付费 key，适合长期稳定运行。
- Playwright：页面公开可见但没有稳定 API，用作 fallback 或低频抓取。
- 登录/授权/付费：口径复杂、页面受限或 provider 数据，必须通过 Settings 配置 key。

核心原则：Playwright 是 fallback，不是所有缺口的主方案。

## 当前结论

P2 不是所有缺口都能靠 Playwright 稳定补齐。

可用 Playwright 的主要是公开页面型数据，例如 Glassnode 公开 dashboard、Coinglass liquidation、TradingView 亚洲风险、HKAB HIBOR、Fed 日历和 Fed speeches。

更适合本地计算或 API 的包括 Top50 强弱、RV、Max Pain、taker buy/sell ratio。

必须依赖 provider 或登录授权的主要是链上成本基础、地址标签流量、精确交易所净流入、稳定币交易所流入、精确 Gamma Wall、宏观 surprise 和监管事件评分。

本轮已优先补齐无需登录、无需付费、可稳定运行的数据。Glassnode 公开 dashboard 已拆到 P1-C14 并完成首批真实采集；下一步不建议继续硬抓所有网页，而是进入 P3/P4/P5 前把剩余缺口归入 Provider Settings 与事件日历/NLP 专项。

## FRED API 覆盖审计

已使用 FRED API key 验证。FRED 很适合补宏观、流动性、信用、亚洲风险 proxy 和宏观公布值序列；不适合补 ETF Flow、链上估值、交易所净流、清算、Gamma Wall、Max Pain、监管新闻评分，也不直接提供未来公布日倒计时。

### FRED 可直接覆盖或已覆盖

| 雷达/用途 | 指标 | FRED series_id | 状态 | 备注 |
|---|---|---|---|---|
| 宏观雷达 | DXY proxy | `DTWEXBGS` | 已接入 | Broad Dollar Index，非 TVC:DXY 精确值 |
| 宏观雷达 | VIX | `VIXCLS` | 已接入 | 日频 |
| 宏观雷达 | Nasdaq | `NASDAQCOM` | 已接入 | 日频 |
| 宏观雷达 | WTI Oil | `DCOILWTICO` | 可接入 | 可补油价冲击 |
| 美元流动性 | Fed Balance Sheet | `WALCL` | 已接入 | 周频 |
| 美元流动性 | Bank Reserves | `WRESBAL` | 已接入 | 周频 |
| 美元流动性 | ON RRP | `RRPONTSYD` | 已接入 | 日频 |
| 美元流动性 | SOFR | `SOFR` | 已接入 | 日频 |
| 美元流动性 | TGA | `WDTGAL` | 可接入 | Treasury General Account |
| 美债/信用 | 2Y Treasury | `DGS2` | 已接入 | 日频 |
| 美债/信用 | 10Y Treasury | `DGS10` | 已接入 | 日频 |
| 美债/信用 | 30Y Treasury | `DGS30` | 已接入 | 日频 |
| 美债/信用 | 10Y Real Yield | `DFII10` | 已接入 | 日频 |
| 美债/信用 | 10Y Breakeven | `T10YIE` | 已接入 | 日频 |
| 美债/信用 | HY Spread | `BAMLH0A0HYM2` | 已接入 | 日频 |
| 美债/信用 | HY Effective Yield | `BAMLH0A0HYM2EY` | 可接入 | 可增强信用雷达 |
| 亚洲风险 | USDJPY | `DEXJPUS` | 已接入 | 日频 |
| 亚洲风险 | USDCNH proxy | `DEXCHUS` | 已接入 | 实际是 USDCNY proxy |
| 亚洲风险 | Nikkei 225 | `NIKKEI225` | 已接入 | 日频 |
| 亚洲风险 | JGB 10Y | `IRLTLT01JPM156N` | 可接入 | 月频，适合慢变量 |
| 事件/宏观冲击 | CPI 公布值 | `CPIAUCSL` | 可接入 | 不是未来发布日期 |
| 事件/宏观冲击 | PCE Price Index | `PCEPI` | 可接入 | 月频 |
| 事件/宏观冲击 | Nonfarm Payrolls | `PAYEMS` | 可接入 | 月频 |
| 事件/宏观冲击 | Unemployment Rate | `UNRATE` | 可接入 | 月频 |
| 事件/宏观冲击 | Initial Claims | `ICSA` | 可接入 | 周频 |
| 事件/宏观冲击 | Industrial Production | `INDPRO` | 可接入 | 月频 |
| 事件/宏观冲击 | Retail Sales | `RSAFS` | 可接入 | 月频 |

## 四类路线总表

### A. 可以本地计算

| 指标 | 计算方式 | 依赖输入 | 优先级 |
|---|---|---|---|
| `etf_flow_7d` | ETF 日流量滚动 7 日求和 | `etf_net_flow` 历史值 | 高 |
| `options_rv` | BTC 收益率滚动年化波动率 | BTC 价格/K线历史 | 高 |
| `max_pain_distance` | Deribit option chain 按 strike 计算最大痛点，再与现价比较 | Deribit options chain + BTC price | 高 |
| `gamma_wall_distance` | 用期权链、IV、到期日、OI 做 Black-Scholes gamma exposure 近似 | Deribit options chain | 中 |
| `top50_strength` | CoinGecko Top50 中 24h/7d 上涨比例、等权强弱分数 | CoinGecko markets API | 高 |
| `macro_surprise_score` | 公布值 - 预期值，标准化后打分 | 实际值 + 预期值 | 低，缺预期值来源 |
| `regulatory_event_score` | 新闻/RSS 文本分类和严重度评分 | 新闻/RSS | 中，需要 NLP |
| `fed_speech_risk` | Fed speech 文本分类和鹰鸽风险评分 | Fed speeches 页面/RSS | 已拆到 P1-C18 |

### B. 可以走公开 API

| 指标 | 推荐源 | 探测状态 | 说明 |
|---|---|---|---|
| `taker_buy_sell_ratio` | Binance futures `takerlongshortRatio` | 已验证 200 | 不需要 Playwright |
| `top50_strength` | CoinGecko markets API | 已验证 200 | 可直接批量计算 |
| `options_rv` | 本地计算 | 已有 BTC price/kline | 不需要外部新源 |
| `max_pain_distance` | Deribit public options chain | Deribit 已验证 200 | 可本地计算 |
| `gamma_wall_distance` | Deribit public options chain 近似计算 | 可尝试 | 精确 Gamma Wall 仍建议专业 provider |
| `tga` | FRED `WDTGAL` | 已验证可用 | 可补美元流动性 |
| `jgb_10y` | FRED `IRLTLT01JPM156N` | 已验证可用 | 月频慢变量 |
| `cpi_actual` | FRED `CPIAUCSL` | 已验证可用 | 公布值，不是倒计时 |
| `pce_actual` | FRED `PCEPI` | 已验证可用 | 公布值 |
| `nfp_actual` | FRED `PAYEMS` | 已验证可用 | 公布值 |
| `retail_sales_actual` | FRED `RSAFS` | 已验证可用 | 公布值 |
| `initial_claims_actual` | FRED `ICSA` | 已验证可用 | 公布值 |

### C. 可以走 Playwright fallback

| 指标 | 页面 | 探测状态 | 风险 |
|---|---|---|---|
| `etf_net_flow` | Glassnode Asset Overview | P1-C14 已打通 | 页面匿名 token 机制变化 |
| `etf_net_flow` | Farside / SoSoValue BTC ETF | 可作为后续交叉验证 | 选择器变化、表格结构变化、页面重 |
| `liquidation_long` | Coinglass Liquidation | HTTP/Playwright 可打开 | 可能登录/反爬，字段需验证 |
| `liquidation_short` | Coinglass Liquidation | HTTP/Playwright 可打开 | 同上 |
| `exchange_netflow` | Glassnode Asset Overview | P1-C14 已用交易所余额日变化代理补齐 | 口径不等于严格链上净流入 |
| `mvrv_zscore` | Glassnode Asset Overview | P1-C14 已打通 | 后续需要历史窗口和交叉验证 |
| `jgb_10y` | TradingView JP10Y | Playwright 可打开 | TV 页面结构变化 |
| `topix` | TradingView TOPIX | Playwright 可打开 | TV 页面结构变化 |
| `hang_seng_tech` | TradingView/HKEX | Playwright 可打开代表页面 | 需确认 symbol |
| `hibor` | HKAB HIBOR | HTTP/Playwright 可打开 | 官方页面结构变化 |
| `fomc_days_until` | Fed FOMC calendar | HTTP/Playwright 可打开 | 需解析日期 |
| `fed_speech_risk` | Fed speeches | HTTP/RSS/Calendar 可用 | 已拆到 P1-C18：Fed RSS + Calendar + blackout + NLP/规则评分 |

## TradingView Playwright 可覆盖清单

TradingView 适合抓公开市场行情、指数、汇率、债券收益率和加密市场总量指标。它不适合抓 ETF Flow、链上估值、交易所净流入、清算明细、Gamma Wall、宏观 surprise 这类专用口径数据。

### 已验证可打开的 TradingView 页面

| 指标/用途 | TradingView symbol URL | 可行性 | 建议角色 |
|---|---|---|---|
| Exact DXY | `https://www.tradingview.com/symbols/TVC-DXY/` | 可抓 | FRED `DTWEXBGS` 的精确 DXY fallback/补充 |
| Gold | `https://www.tradingview.com/symbols/TVC-GOLD/` | 可抓 | 宏观雷达补充 |
| WTI Oil | `https://www.tradingview.com/symbols/TVC-USOIL/` | 可抓 | 宏观事件/油价冲击补充 |
| USDJPY | `https://www.tradingview.com/symbols/USDJPY/` | 可抓 | FRED `DEXJPUS` fallback |
| USDCNH | `https://www.tradingview.com/symbols/USDCNH/` | 可抓 | 优于 FRED USDCNY proxy，可作为亚洲风险主 fallback |
| JGB 10Y | `https://www.tradingview.com/symbols/TVC-JP10Y/` | 可抓 | 比 FRED 月频 JGB 更适合高频观察 |
| Nikkei | `https://www.tradingview.com/symbols/TVC-NI225/` | 可抓 | FRED `NIKKEI225` fallback |
| TOPIX | `https://www.tradingview.com/symbols/TSE-TOPIX/` | 可抓 | 亚洲风险缺口 |
| Hang Seng Tech | `https://www.tradingview.com/symbols/HSI-HSTECH/` | 可抓 | 亚洲风险缺口 |
| Hang Seng Tech ETF proxy | `https://www.tradingview.com/symbols/HKEX-3033/` | 可抓 | 若指数页异常，可用 ETF proxy |
| BTC Dominance | `https://www.tradingview.com/symbols/CRYPTOCAP-BTC.D/` | 可抓 | CoinGecko fallback |
| TOTAL2 | `https://www.tradingview.com/symbols/CRYPTOCAP-TOTAL2/` | 可抓 | CoinGecko fallback |
| Total Crypto Market Cap | `https://www.tradingview.com/symbols/CRYPTOCAP-TOTAL/` | 可抓 | 市场广度补充 |
| ETH/BTC | `https://www.tradingview.com/symbols/ETHBTC/` | 可抓 | CoinGecko fallback |
| BTCUSDT | `https://www.tradingview.com/symbols/BTCUSDT/` | 可抓 | 交易所 API fallback，不建议主用 |
| Nasdaq Composite | `https://www.tradingview.com/symbols/NASDAQ-IXIC/` | 可抓 | FRED `NASDAQCOM` fallback |
| S&P 500 | `https://www.tradingview.com/symbols/SPX/` | 可抓 | 宏观风险补充 |
| VIX | `https://www.tradingview.com/symbols/TVC-VIX/` | 可抓 | FRED `VIXCLS` fallback |

### TradingView 不适合覆盖的 P1-C13 缺口

| 缺口 | 原因 | 推荐路线 |
|---|---|---|
| `etf_net_flow` / `etf_flow_7d` | TradingView 不提供 ETF 每日净流入口径 | 已由 P1-C14 走 Glassnode 公开 dashboard；Farside/SoSoValue 可做交叉验证 |
| `exchange_netflow` | 需要链上标签和交易所地址库 | P1-C14 已有交易所余额日变化代理；精确值走 Glassnode / CryptoQuant / Coinglass |
| `realized_price` / `sth_cost_basis` / `lth_cost_basis` | 链上成本基础指标，不是普通行情 | Glassnode / CryptoQuant / CoinMetrics provider |
| `liquidation_long` / `liquidation_short` | 清算明细不是普通 symbol 行情 | Coinglass |
| `gamma_wall_distance` / `max_pain_distance` | 需要期权链和 Greeks 计算 | Deribit 本地计算 / Greeks provider |
| `macro_surprise_score` | 需要预期值和实际值 | 经济日历 provider |
| `regulatory_event_score` | 需要新闻文本和分类 | 新闻/RSS/provider + NLP |

### TradingView 抓取实现要求

- 每个 symbol 需要独立 source_id，例如 `playwright-tradingview-usdcnh`。
- 抓取结果必须保存 HTML artifact 与 text_sample。
- 解析优先使用页面主体中的 symbol 名称后第一个报价数字，不使用全局随意正则。
- TradingView 只做 fallback 或缺口补充；已有稳定 API/FRED 的指标不以 TradingView 为主源。
- 质量分默认低于 API 源，例如 `quality_score=0.70`，若选择器稳定后可提高。

### D. 需要登录、授权或付费 provider

| 指标 | 推荐 provider | 原因 |
|---|---|---|
| 精确 `exchange_netflow` | Glassnode / CryptoQuant / CoinMetrics / Coinglass API | 当前只有交易所余额日变化代理，严格净流入口径仍需 provider |
| `stablecoin_exchange_inflow` | Glassnode / CryptoQuant | 需要链上标签和交易所地址库 |
| `realized_price` | Glassnode / CoinMetrics / CryptoQuant | 链上成本基础指标，推荐 provider |
| `aSOPR` / SOPR 变体 | Glassnode / CryptoQuant | 基础 `sopr` 已由 P1-C14 公开 chart 打通，变体仍需确认权限 |
| `sth_cost_basis` | Glassnode / CryptoQuant | 通常付费 |
| `lth_cost_basis` | Glassnode / CryptoQuant | 通常付费 |
| `whale_flow` | CryptoQuant / Glassnode | 地址标签依赖 provider |
| `miner_flow` | CryptoQuant / Glassnode | 地址标签依赖 provider |
| `gamma_wall_distance` 精确版 | Greeks.live / Laevitas / Amberdata / Coinglass | 需要专业 Greeks 和 OI 聚合 |
| `macro_surprise_score` | TradingEconomics / Econoday / Investing calendar provider | 需要市场预期值 |
| `regulatory_event_score` | News API / RSS + LLM / 专业新闻源 | 需要新闻覆盖和 NLP |

## 暂时不可直接依赖 Playwright

| 指标/页面 | 结果 | 处理 |
|---|---|---|
| BLS CPI schedule | HTTP 和 Playwright 均 403 | 不走页面，找 BLS API/日历替代 |
| BLS NFP schedule | 预计同类限制 | 不走页面，找官方 API/日历替代 |
| CoinMetrics community API | 当前 403 | 需要 key 或换 provider |
| mempool Lightning API | 当前环境 TLS 失败 | 后续重试，或页面/API fallback |

## 本轮后仍暂时无法解决的数据

这些指标在当前“免费公开 API + TradingView Playwright”范围内仍不能稳定、准确解决：

| P2 雷达 | 暂缺指标 | 原因 | 后续路线 |
|---|---|---|---|
| 资金流雷达 | `etf_net_flow`, `etf_flow_7d` | 已由 P1-C14 通过 Glassnode 公开 dashboard 快速网络截获补齐 | 后续可加 Farside/SoSoValue 作为交叉验证 |
| 资金流雷达 | `exchange_netflow` | 已由 P1-C14 用 Glassnode 交易所余额日变化做代理补齐；不是严格 netflow | 后续用 Glassnode/CryptoQuant/CoinMetrics provider 精确化 |
| BTC 采用率 | `lightning_capacity` | 免费 API 稳定性需另验；当前未并入生产源 | mempool/1ML/API fallback 专项 |
| 链上估值与筹码 | `realized_price`, `sth_cost_basis`, `lth_cost_basis`, `whale_flow`, `miner_flow` | 属于链上估值/地址标签/持有人成本基础，多数需专业 provider；`mvrv_zscore`、`nupl`、`sopr` 已由 P1-C14 公开 chart/dashboard 补齐 | Glassnode/CryptoQuant/CoinMetrics key |
| 交易结构/链上衍生品流量 | `liquidation_long`, `liquidation_short` | Coinglass 页面可访问但清算字段稳定性、反爬和登录限制未完成验证 | Coinglass Playwright/API 专项 |
| 交易结构/链上衍生品流量 | `stablecoin_exchange_inflow` | 需要稳定币链上流入交易所地址标签 | CryptoQuant/Glassnode provider |
| 亚洲风险 | `hibor` | 需要 HKAB 页面结构解析或替代源 | HKAB Playwright extractor |
| 事件政策 | `cpi_days_until`, `fomc_days_until`, `pce_days_until`, `nfp_days_until` | FRED 提供已公布值，不直接提供未来发布时间倒计时 | 官方日历解析/静态日历维护 |
| 事件政策 | `fed_speech_risk`, `regulatory_event_score` | 需要新闻/讲话文本采集 + NLP/LLM 分类 | `fed_speech_risk` 已由 P1-C18 承接；监管风险后续另拆 |
| 事件政策 | `macro_surprise_score` | 需要“市场预期值”与实际公布值，FRED 只有实际值 | TradingEconomics/Econoday/Investing 等日历 provider |

## 建议实施顺序

1. 先补无需 Playwright 的低风险项：
   - `top50_strength`：已完成。
   - `options_rv`：已完成。
   - `max_pain_distance`：已完成。
   - `taker_buy_sell_ratio`：已完成。
   - `tga`：已完成。
   - JGB 10Y 慢变量：已完成。

2. 再补 Playwright fallback：
   - TradingView 亚洲风险：已完成 `jgb_10y`、`topix`、`hang_seng_tech`。
   - Glassnode 公开 dashboard：已由 P1-C14 完成首批接入，补齐 ETF Flow、NUPL、MVRV Z-Score、SOPR、链上活跃等关键项。
   - ETF Flow 交叉验证：后续可单独做 Farside/SoSoValue extractor。
   - Coinglass liquidation：暂缓，单独做 selector/登录/反爬验证。
   - HKAB HIBOR：暂缓，单独做官方页面解析。
   - Fed FOMC calendar / Fed speeches：Fed speech risk 已拆到 P1-C18；监管事件 NLP 后续另拆。

3. 最后等 Settings 配置 provider key：
   - 链上估值与筹码全组
   - exchange/stablecoin netflow
   - 精确 Gamma Wall
   - macro surprise
   - regulatory event score

## 验收标准

- 每个剩余指标都有明确路线：本地计算、公开 API、Playwright fallback 或 provider。
- Playwright 抓取必须保存 artifact、selector 版本、抓取时间和质量评分。
- Playwright 抓取失败时不阻塞主采集链路，必须降权并进入 source health。
- 所有付费 key 通过 Settings 设置中心配置。
- 真实 live 采集 errors = 0。
- `analyze-radars` 全量 14 个雷达完成分析；仍低于 medium 的模块必须明确缺口原因和后续路线。

## 依赖任务

P10-C01 至 P10-C07、P5-C22、P9-C14、P1-C12、P1-C14。

## 备注

P1-C13 不应该一次性硬抓所有网页。优先把可计算和公开 API 项补掉，再把公开页面作为 Playwright fallback，最后把付费/授权数据交给 Settings Provider 体系。

Glassnode 这类登录态 provider 不追加在 P1-C13 内继续扩张，已拆到 P1-C14 单独做登录态、权限与可用指标勘探。
