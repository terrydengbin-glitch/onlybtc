# P3-C24 Radar 状态机与多维模块输出

## 状态

DONE

## 所属 Phase

P3 算法、事件窗口与评分层

## 背景

P3-C22 会优化高优先级指标语义，P3-C23 会升级模块聚合器。但最终给 P4.5 和前端的模块输出仍不应只有：

```text
bullish / bearish / neutral
```

BTC 趋势分析更需要表达：

```text
方向
风险
置信度
新鲜度
是否冲突
是否等待确认
```

因此需要把 Radar module 输出升级为多维状态机。

## 上下游对齐

| Phase | 契约关系 |
| --- | --- |
| P1/P8 | 提供数据质量、新鲜度、业务时间、run lineage。 |
| P2 | 提供 module/metric 基础契约、horizon、duplicate、权重。 |
| P3-C22 | 提供更准确的指标级方向、风险、组合规则。 |
| P3-C23 | 提供 coverage/conflict/confidence/top contributors。 |
| P3-C24 | 基于 C22/C23 输出模块状态机。 |
| P4.5 | 消费 `trend_state` 和四维 score，生成更专业研报。 |
| P5/P9 | 展示状态机结果，不在前端推理。 |

## 任务目标

每个 Radar module 输出四类分数：

| 字段 | 含义 | 范围 |
| --- | --- | --- |
| `direction_score` | 看多/看空方向 | -100 到 +100 |
| `risk_score` | 风险高低 | 0 到 100 |
| `confidence_score` | 置信度 | 0 到 100 |
| `freshness_score` | 数据新鲜度 | 0 到 100 |

并输出状态机：

```text
trend_state:
  risk_on_confirmed
  bullish_but_crowded
  bearish_pressure
  bearish_but_improving
  neutral_wait_confirm
  event_risk_locked
  conflict_no_trade
```

## 状态解释

| trend_state | 业务含义 | 文章语气 |
| --- | --- | --- |
| `risk_on_confirmed` | 风险偏好与资金/订单流确认 | 偏多，回踩能接 |
| `bullish_but_crowded` | 偏多但杠杆或情绪拥挤 | 多头还在，但别追 |
| `bearish_pressure` | 资金、宏观或链上压力明确 | 反弹容易被砸 |
| `bearish_but_improving` | 仍偏空但压力在缓和 | 空头压力缓和，等确认 |
| `neutral_wait_confirm` | 支撑与压力拉扯 | 方向还没打出来 |
| `event_risk_locked` | 重大事件窗口约束 | 数据前不重仓 |
| `conflict_no_trade` | 模块内部或跨模块信号打架 | 先看盘口确认 |

## DoD

- 每个 Radar module 都输出四维分数。
- 每个 Radar module 都输出 `trend_state`。
- `event_policy` 能输出 `event_risk_locked`。
- `fund_flow` 能输出 `bearish_but_improving` 或 conflict 类状态。
- `derivatives_crowding` 能区分 bullish_but_crowded 与 neutral。
- P4.5 research article 能引用 trend_state。
- P5 Dashboard / Radar Detail 能展示 trend_state。
- 不破坏旧字段 `module_direction`、`module_score`、`module_effective_score`。
- 全量 P1/P2/P3/P4.5 跑通。

## 关联任务

P3-C22, P3-C23, P4.5-C11, P4.5-C12, P5-C03, P5-C17


## 执行记录

- 已基于 P3-C22 指标语义和 P3-C23 模块聚合结果，为每个 Radar module 新增 `direction_score`、`risk_score`、`confidence_score`、`freshness_score` 四维输出。
- 已保留 `freshness_factor` 作为 0-1 内部因子，`freshness_score` 作为 0-100 前端 / 研报可读分数。
- 已实现 `trend_state` 状态机：`risk_on_confirmed`、`bullish_but_crowded`、`bearish_pressure`、`bearish_but_improving`、`neutral_wait_confirm`、`event_risk_locked`、`conflict_no_trade`。
- 已新增 `trend_state_reason`，用于 P4.5 研报和 P5 Radar Detail 解释状态机判断原因。
- 已将新字段透传到 P3 full-chain audit、P4.5 final module scores 和 P4.5 HTML module rows。
- 已扩展测试，验证 `event_policy -> event_risk_locked`、`fund_flow` 方向分和 derivatives 状态机输出。

## 验证结果

```text
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p3_pipeline.py -q
15 passed in 6.63s

.\.venv\Scripts\python.exe -m py_compile backend/src/onlybtc/algorithms/p3.py backend/src/onlybtc/audit/p3_full_chain.py backend/src/onlybtc/p45/html_report.py backend/src/onlybtc/p45/final_writer.py
passed
```
