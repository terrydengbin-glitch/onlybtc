# P7-C09 / 优化后 Radar Modules 全链路业务契约审计

## 状态

DONE

## Phase

P7 回测、评估与策略校准

## 背景

近期已陆续优化多个 Radar module，使它们从“单指标方向评分”升级为“BTC trend confirmation / rejection / warning”结构。现在需要做一次跨阶段全链条审计，确认每个已优化模块从 P1 数据派生、P2 registry、P3 状态机、P4.5 报告解释、P8 SQLite 持久化/replay、P9 API 透传，到 Vue3 前端展示，都保持同一业务语义和同一输出契约。

本卡目标不是新增某个模块能力，而是检查已经优化的 radar modules 是否真正形成可审计、可回放、可展示、不会误导用户的生产链路。

## 审计范围

重点覆盖已优化模块：

```text
macro_radar v3
dollar_liquidity v2.1
treasury_credit v2.1
fund_flow v2.2
onchain_valuation v2.2
btc_adoption v2.3
asia_risk v2.3
kline_orderflow v2.2
trade_structure_flow v2.3
derivatives_crowding v2.5
crypto_breadth v3
options_volatility v2.1
event_policy v2.1
btc_total_state v2
```

全链条覆盖：

```text
P1: source / derived metrics / data quality / fallback / proxy flags
P2: RadarMetricRule / role / context-only / affects_signal / driver eligibility
P3: semantic_profile_version / state machine / scores / signal_stage / btc_implication
P4.5: final payload / module explanation / forbidden interpretation governance
P8: SQLite persistence / module_json_outputs / feature_values / history replay
P9: FastAPI dashboard / radar detail / history API / audit reports API
P5: Vue3 Radar Detail / dashboard node / article / run logs display
```

## 核心审计问题

```text
1. 原始 level 指标是否仍被错误用于方向判断？
2. 每个模块的 version / state / signal_stage / btc_implication 是否完整透传？
3. warning / fast_signal / confirmed_signal 是否在 P3、P4.5、前端展示中被清楚区分？
4. BTC response / residual / acceptance / rejection 是否真正成为方向确认依据？
5. risk_score / pressure_score 是否被误读成 bearish direction？
6. proxy / data quality / stale / insufficient history 是否能降权而不是让链路失败？
7. SQLite replay 是否能复现 latest run 的关键 payload？
8. Dashboard / Radar Detail 是否避免“单指标看多/看空”的误导文案？
9. API latest / history / detail 是否读取同一份契约，而不是各自拼接不同字段？
10. run once 后 P1/P2/P3/P4.5 audit HTML 是否与 SQLite、API、前端显示一致？
```

## 具体任务

### 1. P1/P2 覆盖审计

- 检查 `METRIC_DEFINITIONS` 中所有新增派生指标都被 radar registry 消费。
- 检查原始 level 指标是否按模块设计降级为 `context_only` / `composite_only` / `risk_context`。
- 检查 `affects_signal=false`、`driver_eligible=false` 是否用于禁止单因子方向的指标。
- 检查 proxy 指标是否有 `proxy_flags` 或 data quality 降权。

### 2. P3 状态机审计

- 汇总每个优化模块的：

```text
semantic_profile_version
module_direction
module_score / effective_score
signal_stage
module_state / radar-specific state
btc_implication
scores
states
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
```

- 确认 confirmed_signal 不会由单一 raw metric 触发。
- 确认 warning / conflict / neutral 不会被下游翻译成强方向。

### 3. P4.5 报告解释审计

- 检查 final payload 是否包含各模块 explanation。
- 检查 `forbidden_directional_interpretations` 是否覆盖模块单因子误读。
- 检查 research_article / publish_article 是否不泄漏 raw evidence id、run_id、schema_version、Python dict。
- 检查 P4.5 final view 与 aggregation_audit / decision_card 一致。

### 4. P8 SQLite / Replay 审计

- 从 latest run 查询 SQLite：

```text
module_json_outputs
feature_values
radar_outputs
evidence_packs
run_stages
raw_observations
normalized_metrics
```

- 抽查每个已优化 module 的结构化 payload 是否完整落库。
- 用 history replay API 检查 replay payload 与 latest payload 的关键字段一致。

### 5. P9 API 审计

- 检查接口：

```text
/api/p45/dashboard/latest
/api/p45/radar-modules/latest
/api/p45/radar-modules/{module_id}
/api/p45/history/{final_run_id}
/api/p45/audit-reports/latest
/api/p45/articles/latest
/api/p45/runs/latest
```

- 确认 latest/detail/history 对同一 module 输出一致契约。
- 确认 radar detail 可以显示每个 module 的 v2/v3/v2.5 nested contract。

### 6. Vue3 前端审计

- 检查每个已优化 module 在 Radar Detail 至少有专属结构块或通用结构块展示。
- 检查 dashboard node 主摘要优先使用复合语义，不优先显示原始分数。
- 检查禁语治理：

```text
不能写：某 raw 指标高/低，因此 BTC 看多/看空。
必须写：该指标是 context / pressure / warning / confirmation，需要 BTC response 或 residual 确认。
```

- 跑：

```powershell
cd frontend
npm run build
```

### 7. Run Once 验收

- 重启服务。
- 执行 `fast_deterministic` run once。
- 记录 run lineage：

```text
collect_run_id
p2_radar_run_id
p3_run_id
pack_id
article_run_id
final_run_id
```

- 审计 final payload、radar detail、history replay 和 audit reports。

## DoD

- [ ] 所有 `METRIC_DEFINITIONS` 都被 radar registry 消费，无 uncovered metric。
- [ ] P1/P2/P3/P4.5/P8/P9/P5 链条对每个优化模块字段一致。
- [ ] 每个优化模块都有明确 `semantic_profile_version`。
- [ ] 每个优化模块的 key contract 能在 SQLite、API、前端至少三处被抽查到。
- [ ] warning / fast_signal / confirmed_signal 在报告和前端中语义不混淆。
- [ ] raw level 指标不直接触发 confirmed bullish / bearish。
- [ ] risk_score / pressure_score 不被当成 module_direction。
- [ ] proxy / stale / insufficient history 能降权，不导致链路失败。
- [ ] P4.5 final payload 的 contract validation 通过。
- [ ] P5 dashboard contract validation 通过。
- [ ] `npm run build` 通过。
- [ ] Run once 完成，P1/P2/P3/P4.5 audit reports 刷新。
- [ ] 审计报告产出一份机器可读 JSON 和一份人类可读 Markdown/HTML 总结。

## 建议测试命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_radars.py backend/tests/test_sources.py backend/tests/test_p3_pipeline.py backend/tests/test_p45_dashboard_api.py backend/tests/test_p45_final_writer.py backend/tests/test_p4_radar_coverage.py -q
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py
cd frontend
npm run build
```

## 依赖

- P1-C47 至 P1-C56
- P2-C30 至 P2-C39
- P3-C45 至 P3-C54
- P4.5-C31 至 P4.5-C40
- P5-C48 至 P5-C57
- P8-C22 至 P8-C31
- P9-C27 至 P9-C36

## Audit Result

Status: PASS with execution-profile caveat.

Audited run lineage:

```text
collect_run_id: collect-20260527092422-91c85d
p2_radar_run_id: radar-20260527092727-670d81
p3_run_id: p3-20260527092730-456f38
pack_id: p45pack-20260527092744-e59e9f
article_run_id: p45articles-20260527092745-5b7271
final_run_id: p45final-20260527092745-2a60bb
execution_profile: fast_deterministic
```

Reports:

```text
reports/p7-c09-radar-modules-full-chain-contract-audit.md
reports/p7-c09-radar-modules-full-chain-contract-audit.json
```

Verification:

```text
backend core pytest: 139 passed
trade_structure targeted pytest: 4 passed
P5 dashboard contract: passed
frontend npm run build: passed
SQLite/API/history/detail audit: passed
```

Fixed during audit:

```text
trade_structure_flow: btc_funding_rate and btc_funding_band moved to leverage_context
with affects_signal=false and driver_eligible=false.
```

Caveat:

```text
validate_p5_page_dod reports missing llm_research appendix because this run used
fast_deterministic and intentionally skipped LLM stages. This is not a radar-chain failure.
```
