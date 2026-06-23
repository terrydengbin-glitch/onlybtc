# P1-C19 Clark Moody Lightning 与 BTC 基础面板数据源

## 状态

DONE

## 所属 Phase

P1 数据源与历史数据底座

## 任务定位

优化 `lightning_capacity_btc` 当前数据源稳定性。

P1-C15 已接入 `mempool-lightning-network-stats`，但当前环境访问 mempool API 出现 TLS EOF / warning 风险。本任务新增 Clark Moody Dashboard 作为 Lightning 与 BTC 基础面板的公开页面源，优先补强 BTC 采用率雷达，同时评估页面里的其他公开数据是否可以进入 P2 雷达。

目标页面：

```text
https://dashboard.clarkmoody.com/
```

## 优先级

### P0 必须补齐

```yaml
lightning_capacity_btc:
  primary_candidate:
    source: clarkmoody_dashboard
    section: Lightning Network (Public)
    label: Total Capacity
    method:
      - http_text_parse
      - playwright_text_fallback
    current_example: 4776.03 BTC
  fallback:
    source: mempool-lightning-network-stats
    method: rest
  radar:
    module: btc_adoption
```

同步采集：

```yaml
lightning_node_count:
  label: Total Nodes
  current_example: 10020

lightning_channel_count:
  label: Total Channels
  current_example: 39444

lightning_tor_capacity_btc:
  label: Tor Capacity
  use_as: adoption_decentralization_context

lightning_tor_capacity_pct:
  label: Percentage Tor Capacity
  use_as: adoption_decentralization_context
```

## Clark Moody 可用数据初筛

### 1. BTC 总状态 / 价格

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Price | `btc_price` / 交叉验证 | 只做 backup，不覆盖交易所价格 |
| 24H Change / 7D / 30D / 1Y Change | `btc_return_*` | 价格趋势辅助 |
| Market Cap | `btc_market_cap` | BTC 总状态 / 估值上下文 |
| Sats per Dollar | `sats_per_dollar` | 展示型指标 |

结论：交易所 API 仍是价格主源，Clark Moody 只做 backup / UI context。

### 2. 供应与减产

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Money Supply | `btc_supply_current` | 与 Coin Metrics / 区块源交叉验证 |
| Percentage Issued | `btc_supply_issued_pct` | 长期供应状态 |
| Issuance Remaining | `btc_issuance_remaining` | 减产/供应 context |
| Blocks to Halving | `btc_halving_blocks_remaining` | 与 P1-C04 交叉验证 |
| Halving Estimate | `btc_halving_estimated_date` | UI 展示 / fallback |

结论：P1-C04 仍是主源，Clark Moody 可做减产倒计时交叉验证。

### 3. Blockchain / 网络基础

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Block Height | `btc_block_height` | 与 Blockstream 交叉验证 |
| UTXO Set Size | `utxo_set_size` | 链上活动/状态长期趋势 |
| Total TXOs | `total_txos` | 链上使用强度 context |
| Chain Size | `chain_size_gb` | 节点运行成本 context |
| OP_RETURN Data | `op_return_data_gb` | 链上数据占用 context |

结论：适合 BTC 采用率与链上活动 context，但不作为趋势核心主判据。

### 4. Bitcoin Network

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Reachable Bitcoin Nodes | `bitcoin_reachable_nodes` | 去中心化/网络健康 |
| Bitcoin Tor Nodes | `bitcoin_tor_nodes` | 隐私/抗审查 context |
| Percentage Tor Nodes | `bitcoin_tor_nodes_pct` | 网络结构变化 |

结论：可进入 `btc_adoption`，但需要趋势窗口，单点值不单独触发预警。

### 5. Lightning Network (Public)

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Total Capacity | `lightning_capacity_btc` | BTC 采用率核心指标 |
| Capacity Value | `lightning_capacity_usd` | UI context |
| Total Nodes | `lightning_node_count` | Lightning 网络规模 |
| Total Channels | `lightning_channel_count` | Lightning 网络规模 |
| Tor Capacity | `lightning_tor_capacity_btc` | Lightning 隐私/路由结构 |
| Percentage Tor Capacity | `lightning_tor_capacity_pct` | Lightning 去中心化 context |
| Tor Nodes | `lightning_tor_node_count` | Lightning 隐私/路由结构 |

结论：本任务的核心采集范围。

### 6. Transactions / Mempool / Fees

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Transaction Rate, 30 days | `tx_rate_30d` | 链上活跃度 |
| Transaction Count, 30 days | `tx_count_30d` | 链上活跃度 |
| Mempool Transactions | `mempool_tx_count` | 交易拥堵 |
| vSize | `mempool_vsize_mb` | 拥堵程度 |
| Blocks to Clear | `mempool_blocks_to_clear` | 手续费压力 |
| Pending Fees | `mempool_pending_fees_btc` | 手续费需求 |
| Minimum Fee Rate | `mempool_min_fee_rate_sat_vb` | 链上拥堵 |
| Fee Estimates | `fee_estimate_*` | 交易成本 |

结论：可进入 `trade_structure_flow` 或 `btc_adoption`，用于链上活跃/拥堵代理。

### 7. Mining / Chain Security

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Hash Rate, 90 Days | `hashrate_90d_ehs` | 网络安全 / 矿工压力 context |
| Hash Rate, 2016 Blocks | `hashrate_2016_blocks_ehs` | 短期算力 |
| Difficulty | `mining_difficulty` | 挖矿状态 |
| Last Difficulty Change | `difficulty_change_pct` | 算力变化 |
| Estimated Difficulty Change | `estimated_difficulty_change_pct` | 下次难度预期 |
| Hash Price | `hash_price_usd` | 矿工收入压力 |
| Avg Fees per Block | `avg_fees_per_block_btc` | 矿工收入结构 |
| Avg Fees vs. Reward | `fees_vs_reward_pct` | 手续费周期 |

结论：适合补 `miner_flow` 之外的矿工压力代理，不替代 CryptoQuant/Glassnode 的矿工地址流。

### 8. Economics

| 页面字段 | 可映射指标 | 用途 |
|---|---|---|
| Realized Monetary Inflation | `btc_realized_monetary_inflation` | BTC 供应稀缺性 |
| Forward Monetary Inflation | `btc_forward_monetary_inflation` | 长期估值 context |
| Velocity of Money | `btc_velocity_of_money` | 链上经济活跃 |
| Daily Value Throughput | `btc_daily_value_throughput_usd` | 链上结算强度 |

结论：可作为 BTC 采用率与链上活跃的辅助 evidence。

## 采集策略

### 第一阶段：HTTP 文本解析

Clark Moody 页面已能返回可读文本，优先使用普通 HTTP 抓取并解析 `section -> label -> value`。

要求：

```yaml
parser:
  input: html_or_text
  output:
    section: Lightning Network (Public)
    label: Total Capacity
    raw_value: 4,776.03 BTC
    value: 4776.03
    unit: BTC
  normalization:
    - remove commas
    - parse percentage
    - parse BTC/USD/GB/EH/s/sat_vB
    - keep raw_value for audit
```

### 第二阶段：Playwright fallback

如果 HTTP 文本缺失或页面结构变化，降级使用 Playwright：

```yaml
fallback:
  method: playwright_text
  trigger:
    - missing_lightning_capacity
    - parse_error
    - suspicious_zero_value
  source_health:
    status: warning
    reason: http_parser_failed_playwright_used
```

### 第三阶段：历史趋势窗口

所有进入雷达的 Clark Moody 指标必须保留历史窗口：

```yaml
trend_windows:
  short: 24h
  medium: 7d
  long: 30d
```

单点值只用于展示，不直接触发状态变化。

## Source Registry 规划

```yaml
source_id: clarkmoody-dashboard
name: Clark Moody Bitcoin Dashboard
kind: OFFICIAL_OR_PLAYWRIGHT
group_name: btc_adoption
method: http_text_parse_with_playwright_fallback
url: https://dashboard.clarkmoody.com/
metrics:
  - lightning_capacity_btc
  - lightning_capacity_usd
  - lightning_node_count
  - lightning_channel_count
  - lightning_tor_capacity_btc
  - lightning_tor_capacity_pct
  - lightning_tor_node_count
  - bitcoin_reachable_nodes
  - bitcoin_tor_nodes
  - bitcoin_tor_nodes_pct
  - mempool_tx_count
  - mempool_vsize_mb
  - mempool_blocks_to_clear
  - mempool_min_fee_rate_sat_vb
  - hashrate_90d_ehs
  - hash_price_usd
  - avg_fees_per_block_btc
```

注意：

- `lightning_capacity_btc` 与现有 mempool 源同 metric，需要 source quality 与 fallback 优先级明确。
- 不要把 Clark Moody 的价格覆盖交易所主源。
- 矿工指标只能叫 `miner_pressure_proxy` 或相关 proxy，不能冒充 `miner_flow`。

## 与 P2 雷达对接

| P2 模块 | 可消费指标 | 用途 |
|---|---|---|
| P2-C06 BTC 采用率 | Lightning、节点、交易数、吞吐量 | 采用率与网络健康 |
| P2-C10 交易结构/链上衍生品流量 | mempool、fee、pending fees | 链上拥堵与手续费压力 |
| P2-C07 链上估值与筹码 | velocity、daily throughput | 辅助 evidence |
| P2-C04 美债/信用压力雷达 | 不直接消费 | 无 |
| P2-C09 衍生品拥挤度 | 不直接消费 | 无 |

## DoD

- [x] 能从 `https://dashboard.clarkmoody.com/` 真实采集 `lightning_capacity_btc`。
- [x] `lightning_capacity_btc`、`lightning_node_count`、`lightning_channel_count` 至少 3 个核心 Lightning 指标落库。
- [x] 可读 raw payload 保存 section、label、raw value、normalized value。
- [x] 与 mempool Lightning 源形成 fallback / cross-check，而不是互相覆盖。
- [x] `btc_adoption` 雷达可消费 Clark Moody Lightning 指标。
- [x] 新增 Clark Moody text parser fixture。
- [x] 覆盖带逗号、BTC、%、MB、EH/s、sat/vB、美元 M 后缀的单位解析。
- [x] live 采集通过。
- [ ] Playwright fallback 尚未实现。当前 HTTP 文本源稳定可用，fallback 留给 P7/P1 后续增强。

## 验收命令

```powershell
..\.venv\Scripts\python.exe -m onlybtc.cli collect-sources --mode live --source-id clarkmoody-dashboard
..\.venv\Scripts\python.exe -m onlybtc.cli analyze-radars --module-id btc_adoption
ruff check src tests
..\.venv\Scripts\python.exe -m pytest
```

## 风险

- Clark Moody 是个人维护的公开 dashboard，稳定性需要 source health 监控。
- 页面值可能是快照型，不适合高频 10 分钟强预警，建议 10-30 分钟采集。
- 某些字段可能是计算值，需保存 raw value 和采集时间，避免误当官方链上原始值。
- Lightning public network 本身不等于全部 Lightning 私有通道，指标名称必须保留 `public` 语义。

## 实施结果

### 代码变更

- 新增 `clarkmoody-dashboard` source。
- 新增 Clark Moody HTTP text parser。
- 新增 Lightning、Bitcoin nodes、mempool、mining proxy 指标。
- P2 `btc_adoption` 雷达新增消费：
  - `lightning_node_count`
  - `bitcoin_reachable_nodes`
- P2 `trade_structure_flow` 雷达新增消费：
  - `mempool_blocks_to_clear`
  - `mempool_min_fee_rate_sat_vb`
- 修正 metric enrichment：历史值用于计算 change，不再用旧样本质量压低当前样本质量。

### 当前 live 样本

```yaml
lightning_capacity_btc: 4775.55
lightning_node_count: 10020
lightning_channel_count: 39442
bitcoin_reachable_nodes: 23866
mempool_blocks_to_clear: 3
mempool_min_fee_rate_sat_vb: 1
hashrate_90d_ehs: 979.7
hash_price_usd: 35.78
quality_score: 0.84
```

### 验收结果

```text
collect-sources --mode live --source-id clarkmoody-dashboard
collected: 1
errors: []

ruff check src tests
All checks passed

pytest
31 passed
```
