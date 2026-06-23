# P9-C52 / Radar Runtime Cockpit Score Bridge

## 状态

DONE

## 背景

Radar Runtime daemon 已经改成常驻分频运行，并且 14 个 radar modules 的 freshness / scheduler / heartbeat 链条已经通过审计。

但当前审计发现：

```text
runtime snapshot 中 14 个 modules 全部 fresh；
runtime module_payload 内有完整模块语义与指标证据；
但 runtime module_score 当前全部为 0.0；
前端 BTC 主卡主要读取 P4.5 btc_trend_cockpit，而不是 runtime cockpit 的实时分数；
因此中心 BTC 卡对 fast module 的实时变化感应偏弱。
```

这不是数据断链，而是 **runtime score bridge 不完整**：

```text
module_payload / module_semantic_profile / contract 字段
  -> runtime module_score / direction / stage / response / residual
  -> btc_runtime_cockpit
  -> dashboard BTC 主卡双层展示
```

当前这条链路没有完整打通。

## 目标

让 radar runtime daemon 每次分频刷新后，正确从 `module_payload`、`module_semantic_profile`、模块 contract 字段中提取：

```text
module_score
module_effective_score
module_direction
module_effective_direction
signal_stage
btc_implication
btc_response_score
residual
support_drivers
pressure_drivers
conflict_drivers
data_quality_flags
```

并把增量 runtime cockpit 透传给前端 BTC 主卡，使主卡可以同时展示：

```text
P4.5 acceptance / confirmed gate
Radar Runtime freshness / fast layer nowcast
```

核心原则：

```text
runtime cockpit 负责敏感 nowcast；
P4.5 btc_trend_cockpit 负责 acceptance/residual 后的确认裁决；
runtime 单点变化不能直接覆盖 confirmed_bullish / confirmed_bearish。
```

## 范围

涉及：

- `backend/src/onlybtc/radar_runtime/service.py`
- `backend/src/onlybtc/p45/cockpit.py` 中可复用的 normalize / contribution 逻辑
- `/api/radar-runtime/cockpit/latest`
- `/api/p45/dashboard/latest`
- Vue3 BTC 主卡展示
- Radar Runtime 审计 HTML
- 后端测试 / 前端构建

不涉及：

- 重写 14 个 radar module 业务算法
- 让 Event Window 改写 BTC score
- 取消 P4.5 confirmed gate
- 用 runtime cockpit 直接发布最终交易方向

## 业务规则

### 1. Runtime module score 提取规则

每个 runtime module snapshot 必须从 payload 中按优先级提取分数：

```text
module_semantic_profile.module_effective_score
module_semantic_profile.module_score
payload.module_effective_score
payload.module_score
payload.scores.module_score
payload.scores.trend_acceptance_score / derived score fallback
payload.strength
```

方向字段按优先级：

```text
module_effective_direction
module_direction
direction
signal
module_bias
```

阶段字段按优先级：

```text
signal_stage
stage
state_machine.signal_stage
contract.signal_stage
```

BTC response / residual 按模块 contract 的语义字段提取，至少覆盖：

```text
btc_response_score
btc_acceptance_score
price_acceptance_score
trend_acceptance_score
derivatives_residual_z
trade_structure_residual_z
fund_flow_residual_z_60d
onchain_residual_z_90d
adoption_residual_z_90d
btc_residual_24h
```

### 2. Runtime cockpit 贡献规则

runtime cockpit 不做简单 `module_score` 求和，而是沿用 P4.5 Cockpit 的贡献逻辑：

```text
direction_sign
* abs(module_score)
* stage_multiplier
* quality_multiplier
* accepted_multiplier
```

其中：

```text
fast modules: kline_orderflow / trade_structure_flow / derivatives_crowding / asia_risk
confirmation modules: fund_flow / treasury_credit / macro_radar / dollar_liquidity
regime modules: onchain_valuation / btc_adoption / crypto_breadth / options_volatility / event_policy
controller modules: btc_total_state / data_quality / contract_validation / aggregation_audit
```

### 3. BTC 主卡展示边界

前端 BTC 主卡必须区分两层：

```text
P4.5 Cockpit:
  final headline / confidence / acceptance / confirmation gate

Runtime Cockpit:
  freshness / fast nowcast / runtime net score / recently changed modules
```

显示建议：

```text
主圆环仍使用 P4.5 confidence_score；
Fast layer readout 优先显示 runtime fast_net_score 与 freshness；
P4.5 confirmation / acceptance 仍显示为确认门槛；
runtime shock / fast shift 只能标记 watch / nowcast，不允许直接 confirmed。
```

### 4. 安全边界

```text
P4.5 confirmed_bullish / confirmed_bearish 必须继续满足 acceptance/residual gate。
runtime 单一 fast module 变化最多把 UI 推成 nowcast / watch，不允许直接改 final confirmed。
如果 runtime module freshness stale，则 runtime nowcast 降权或隐藏。
```

## DoD

- [ ] 14 个 runtime modules 不再全部 `module_score=0.0`。
- [ ] runtime `module_score` 与模块详情页中间综合分一致，或有 `score_source / score_explanation` 可解释映射。
- [ ] runtime module snapshot 包含 `effective_direction`、`signal_stage`、`btc_implication`、`btc_response_score`、`residual`。
- [ ] `btc_runtime_cockpit` 输出 `fast_net_score`、`confirmation_net_score`、`regime_net_score`、`support_score`、`pressure_score`、`trend_acceptance_score`。
- [ ] `/api/radar-runtime/cockpit/latest` 返回 runtime cockpit 与 14 个 module contribution。
- [ ] `/api/p45/dashboard/latest` 透传最新 `btc_runtime_cockpit`，且与 `btc_trend_cockpit` 并列存在。
- [ ] BTC 主卡显示 runtime freshness + P4.5 acceptance 双层结果。
- [ ] fast 模块变化后，BTC 主卡 fast layer 在 1-2 个 runtime tick 内变化。
- [ ] P4.5 confirmed 信号仍由 `btc_trend_cockpit` 的 acceptance/residual gate 决定。
- [ ] Radar Runtime 审计 HTML 显示 runtime contribution 表，能看出每个模块 score 来源。
- [ ] 后端测试覆盖 score extraction、runtime contribution、dashboard passthrough。
- [ ] `npm run build` 通过。

## 验收命令

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radar_runtime.py backend\tests\test_radar_runtime_daemon.py -q
.\.venv\Scripts\python.exe scripts\generate_radar_runtime_audit_report.py
cd frontend
npm run build
```

## 审计点

完成后需要人工核对：

```text
/api/radar-runtime/modules/latest:
  14 modules module_score 不全为 0

/api/radar-runtime/cockpit/latest:
  fast_net_score 随 fast module tick 更新

/api/p45/dashboard/latest:
  btc_trend_cockpit 与 btc_runtime_cockpit 均存在

前端 BTC 主卡:
  圆环 = P4.5 confidence
  fast readout = runtime nowcast/freshness
  confirmation/invalidation = P4.5 gate
```
