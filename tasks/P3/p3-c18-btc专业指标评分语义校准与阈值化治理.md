# P3-C18 BTC 专业指标评分语义校准与阈值化治理

## 状态

DONE

## 所属 Phase

P3 状态机、风险与事件窗口 / P4.5 Radar Scored Analyst Writer 前置语义契约

## 背景

P3-C16 已经完成指标级正/零/负评分、Radar 板块总分和一句话说明落库，P3-C17 已经把这些内容接入 P3 审计 HTML。当前问题不在覆盖率，而在专业语义：部分 BTC 指标不能只用 `higher_is=bullish/bearish` 和短期变化率线性判断。

P4.5 的目标是让 LLM 基于 scored evidence 写出专业趋势文章。如果 P3 给出的分数和说明没有对齐 BTC 专业分析语义，P4.5 会把“字段完整”误当成“趋势判断可靠”，导致文章仍然生硬或出现矛盾表达。

## 任务目标

建立 BTC 专业指标评分语义层，使 P3 输出的 `metric_score / direction / score_bucket / metric_explanation / score_reason` 不只是技术字段，而是能对齐专业市场解释：

- 指标正负分必须能解释为对 BTC 趋势的正向、负向、中性或观察贡献。
- 对非线性指标使用阈值区间、市场阶段和组合上下文，而不是简单线性变化。
- 对 `mixed` 指标给出语境化解释，必要时允许输出正/负/零，而不是全部归零。
- 对 ETF、funding、OI、MVRV、SOPR、宏观惊喜等关键指标补充专业规则。
- 为 P4.5 提供可直接引用的中文解释和评分原因。

## 重点校准范围

### 链上估值与持仓结构

- `mvrv_zscore`
  - 低位/中性/高位/极端高位分区。
  - 高位继续上行才偏空；低位回升不应机械偏空。
- `sopr`
  - `< 1`、接近 `1`、突破 `1`、持续高位分别解释。
  - 接近 1 应作为盈亏平衡/卖压测试，而不是简单 mixed。
- `nupl`
  - 按恐惧、乐观、信念、狂热区间解释。
- `sth_cost_basis / lth_cost_basis`
  - 结合 BTC 当前价格相对成本基础判断压力位、支撑位和利润状态。
- `realized_price / cap_real_usd`
  - 区分长期成本基础抬升与短线方向贡献。

### 衍生品与微观结构

- `btc_funding_rate`
  - 负 funding、温和正 funding、过热 funding 分区。
  - funding 降温可视为去拥挤，极端负 funding 可视为反向挤压风险。
- `btc_open_interest`
  - 必须结合 BTC 价格方向、funding、清算数据判断。
  - OI 上升不是天然偏空，可能代表趋势确认或杠杆拥挤。
- `futures_basis`
  - 区分正常 contango、过热 basis、backwardation。
- `liquidation_long_usd / liquidation_short_usd`
  - 区分去杠杆、挤压和趋势延续。
- `options_iv / options_rv / put_call_ratio / options_skew`
  - 区分波动风险下降、尾部风险上升和期权保护需求。

### 资金流与流动性

- `etf_net_flow / etf_flow_7d`
  - 区分绝对净流入/净流出与边际改善/恶化。
  - 净流出但边际改善时，说明必须明确“负值仍是压力，但压力边际缓和”。
- `stablecoin_supply / stablecoin_buying_power_proxy`
  - 解释为链上购买力和风险资产流动性，不直接等同买盘。
- `exchange_balance_delta_1d_proxy`
  - 区分交易所余额下降的供给收缩含义与数据代理局限。

### 宏观与事件

- `dxy_proxy / vix / ofr_fsi`
  - 同时考虑绝对风险水平和边际变化。
- `treasury_2y / treasury_10y / real_yield_10y`
  - 利率上行通常压制 BTC，但下降也需区分经济衰退风险。
- `macro_surprise_score / aggregate_macro_surprise`
  - `0` 应默认 neutral，不能机械给正分或负分。
  - 只有明确超预期方向和 BTC 影响映射时才给方向分。
- `fed_speech_hawkish_score / fed_speech_dovish_score`
  - hawkish 偏空、dovish 偏多，但需要与事件窗口和发言权重结合。

## 业务原则

- P3 负责专业语义评分，P4.5 负责表达和综合推理。
- 同一个指标允许在不同 Radar module 中有不同解释，但必须明确原因。
- `zero` 表示当前不形成方向贡献，不等于无意义。
- `unavailable` 不参与方向打分，但必须进入数据边界。
- 如果分数来自“边际改善”而不是“绝对偏多”，必须在 `score_reason` 写清楚。
- 不输出交易指令，只输出趋势、风险、观察路径。

## 输出要求

继续兼容 P3-C16 schema，但增强以下字段：

- `metric_explanation`
  - 包含指标含义、BTC 影响逻辑、当前值语境。
- `score_reason`
  - 包含正/负/零分的具体触发条件。
- `history_context`
  - 尽量保留 change、均值、分位数、zscore、相对成本基础等解释变量。
- `semantic_rule_id`
  - 可选，标记使用了哪条专业语义规则。
- `semantic_warning`
  - 可选，标记“绝对值偏空但边际改善”“数据代理有限”等情况。

## 验收标准

- P3 scored evidence 中关键 BTC 指标的正负分能与专业指标解释对齐。
- `macro_surprise_score=0`、`aggregate_macro_surprise=0` 不再机械贡献正/负分。
- ETF 净流出但边际改善时，`score_reason` 必须说明绝对压力和边际改善的区别。
- `mvrv_zscore / sopr / funding / open_interest` 不再只依赖简单线性变化。
- P3 HTML 中能看到专业化后的指标解释和评分原因。
- P4.5-C03 可以基于该语义层生成更强的一句话解释词典。
- 单元测试覆盖关键语义规则。
- 真实全链条运行后，P1/P2/P3 HTML 正常输出。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p3-full-audit --run-mode live
```

## 依赖

P2-C20, P2-C21, P3-C16, P3-C17, P4.5-C03

## 完成记录

已完成 P3 scored evidence 专业语义层：

- 在 P3 `ScoredMetricEvidence` 中新增并落库：
  - `base_metric_score`
  - `base_direction`
  - `semantic_rule_id`
  - `semantic_warning`
- P3 scored evidence 现在优先使用 BTC 专业语义规则，再回退到 P2 Radar 原始方向规则。
- Radar module `module_score` 改为聚合语义校准后的指标分数，使 P4.5 消费的板块方向与专业语义一致。
- 已覆盖并测试关键规则：
  - `macro_surprise_score=0` / `aggregate_macro_surprise=0` 为中性观察。
  - ETF 净流出按绝对资金压力偏空，同时保留“边际改善不能直接等同偏多”的 warning。
  - `mvrv_zscore` 使用低位/中性/高位/极端高位阈值，低位不再机械偏空。
  - `sopr` 接近 1 作为盈亏平衡测试区。
  - `btc_funding_rate` 使用过热、温和、负 funding 挤压区间。
  - `btc_open_interest` 使用变化幅度区分杠杆拥挤、去杠杆和观察项。
  - `futures_basis` 区分过热升水、正常升水、贴水压力和接近零。
  - `ofr_fsi`、`vix`、美债/真实利率/SOFR 使用绝对区间语义。
  - `put_call_ratio` 高保护需求时偏空。

验证：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend/src backend/tests
.\.venv\Scripts\python.exe -m onlybtc.cli p3-full-audit --run-mode live
```

结果：

- `110 passed`
- `ruff passed`
- 真实运行完成：
  - `collect_run_id=collect-20260522054908-7c80a8`
  - `p2_radar_run_id=radar-20260522055049-8b265e`
  - `p3_run_id=p3-20260522055050-7f0291`
  - `scored_metric_rows=118`
  - `scored_radar_module_rows=14`

输出 HTML：

- `reports/p1-c22-真实数据全链路验收报告.html`
- `reports/p2-radar-quality-report.html`
- `reports/p3-algorithm-audit-report.html`
