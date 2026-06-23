# P2-C16 Onchain Valuation 残留质量提升

## 状态

DONE

## 来源

P1-C22 真实数据全链路验收已通过 P1 Phase Gate，但仍有一个非阻断残留项：

```text
radar_quality: onchain_valuation = medium
```

当前数据采集、SQLite 写入、Radar 消费均已打通，问题不是采集失败，而是链上估值与筹码雷达中仍有部分高级指标属于代理指标或后续 provider 增强项。

## 所属 Phase

P2 全量雷达模块 / P1 数据源 / P5 Radar Detail / Evidence

## 当前状态

已可用指标：

- `mvrv_zscore`
- `nupl`
- `realized_price`
- `sopr`
- `sth_cost_basis`
- `lth_cost_basis`

仍需治理或增强：

- `whale_flow`
- `miner_flow`
- 部分链上流量 exact / proxy 分层解释

## 目标

将 `onchain_valuation` 从 medium 提升为 high，或在无法免费精确获取时明确输出：

```yaml
quality_explanation:
  final_quality: medium
  reason:
    - whale_flow uses proxy or provider_required
    - miner_flow uses proxy or provider_required
  publish_allowed: true
  user_visible_note: 链上估值主指标完整，高级流量项仍为代理指标
```

## 修复要求

### 1. 指标分层

链上估值雷达需要区分：

- exact 指标：可直接用于强判断
- proxy 指标：只用于辅助判断
- provider_required 指标：缺口记录，不参与强扣分

### 2. Radar quality 调整

`onchain_valuation` 不应因为 provider_required 指标未接入而直接长期 medium。

建议规则：

```text
核心估值指标覆盖完整时，质量可为 high；
高级流量指标缺口作为 quality_explanation，而不是阻断项。
```

### 3. Evidence 输出

Radar output 必须说明：

- 当前哪些链上指标为 exact
- 哪些为 proxy
- 哪些需要 provider
- 这些缺口是否影响最终 BTC 判断

## DoD

- `onchain_valuation` 的质量扣分原因可解释。
- `whale_flow / miner_flow` 不再作为隐性质量黑洞。
- 若仍为 medium，必须在 `quality_explanation.main_discount_reasons` 中明确原因。
- P1-C22 复跑后，问题清单不再只写 `onchain_valuation`，而能指出具体指标缺口。
- 测试覆盖 exact / proxy / provider_required 三种指标质量分层。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli analyze-radars --module-id onchain_valuation
..\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
..\.venv\Scripts\python.exe -m pytest
```
