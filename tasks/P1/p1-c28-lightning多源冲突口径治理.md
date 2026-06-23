# P1-C28 Lightning 多源冲突口径治理

## 状态

DONE

## 来源

P1-C22 复跑后多源冲突从 5 项降为 3 项，剩余冲突集中在 Lightning：

```text
lightning_capacity_btc
lightning_channel_count
lightning_node_count
```

当前候选源主要为：

- `clarkmoody-dashboard`
- `mempool-lightning-network-stats`

## 所属 Phase

P1 数据源与多源仲裁 / P2 BTC 采用率雷达 / P5 Evidence 与 Radar Detail

## 当前问题

Lightning 指标的多源差异可能来自：

- 统计口径不同。
- 更新时间不同。
- 可见节点/通道定义不同。
- 页面展示四舍五入。
- API 与页面 snapshot 不同步。

这类差异不应简单视为采集错误，但必须被清晰展示和治理。

## 目标

建立 Lightning 指标的口径分层与仲裁规则：

```yaml
lightning_capacity_btc:
  primary_semantic: public_network_capacity
  selected_source_rule:
    prefer: api_source_if_quality_equal_or_higher
    fallback: page_snapshot
  conflict_type:
    - definition_conflict
    - update_lag
```

## 修复要求

### 1. 指标级质量与优先级

不要只使用 source 全局质量。Clark Moody 对部分面板指标质量高，但 Lightning 网络容量/节点/通道可能需要 mempool API 优先。

支持：

```yaml
metric_source_overrides:
  lightning_capacity_btc:
    mempool-lightning-network-stats:
      quality_score: 0.90
      priority: 20
    clarkmoody-dashboard:
      quality_score: 0.82
      priority: 40
      role_preference: cross_check
```

### 2. 冲突类型化

多源冲突输出增加：

```yaml
conflict:
  type: definition_conflict | update_lag | rounding | source_error
  severity: low | medium | high
  user_action_required: false
```

### 3. Evidence 展示准备

Radar / Evidence 输出需要能解释：

- 当前采用哪个源。
- 另一个源为什么不是主源。
- 差异百分比。
- 差异是否影响 BTC 采用率判断。

## DoD

- Lightning 3 个冲突指标具备指标级 source quality / priority override。
- `historical_window()` 对这些指标能按指标级规则选源。
- 冲突不再只显示数值差异，还显示 `conflict.type`。
- P1-C22 报告中 Lightning 冲突原因更具体，不再笼统标为问题。
- BTC 采用率雷达能消费 selected source，同时保留 fallback / cross-check 证据。
- 测试覆盖：
  - 指标级 override 优先于 source 全局配置。
  - definition conflict 不会被当作采集失败。
  - Lightning 冲突能进入 Evidence pack。

## 验收命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window lightning_capacity_btc
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window lightning_channel_count
..\.venv\Scripts\python.exe -m onlybtc.cli metric-window lightning_node_count
..\.venv\Scripts\python.exe -m onlybtc.cli analyze-radars --module-id btc_adoption
..\.venv\Scripts\python.exe -m pytest
```

## 本次执行结果

已完成：

- Lightning 三个网络指标增加指标级 source override：
  - `lightning_capacity_btc`
  - `lightning_channel_count`
  - `lightning_node_count`
- mempool API 对 Lightning 网络容量/节点/通道优先级与质量分高于 Clark Moody 页面。
- Clark Moody 对这些指标作为 fallback / cross-check。
- 多源冲突增加：
  - `type`
  - `user_action_required`
- Lightning 指标冲突标记为 `definition_conflict`，不再被视为采集失败。

验证：

```text
pytest: 42 passed
P1-C22: Lightning selected source 使用 mempool-lightning-network-stats
```
