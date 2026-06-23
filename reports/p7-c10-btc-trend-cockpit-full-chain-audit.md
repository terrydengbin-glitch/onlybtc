# P7-C10 BTC Trend Cockpit 全链路审计报告

结论：PASS

审计时间：2026-05-27 18:10 Asia/Shanghai

## 范围

- P3-C55：Radar module -> `module_signal[]` 输入归一化
- P4.5-C41：`btc_trend_cockpit.v2` 聚合器与中心状态机
- P8-C32：final payload 持久化与 history replay
- P9-C37：dashboard / overview / history API 透传
- P5-C58：Vue3 中央 BTC 卡片 cockpit-first 展示

## run once

```text
collect_run_id: collect-20260527100229-0f7763
p2_radar_run_id: radar-20260527100526-aea1dd
p3_run_id: p3-20260527100530-a911b2
pack_id: p45pack-20260527100544-e304b1
article_run_id: p45articles-20260527100544-0e39fe
final_run_id: p45final-20260527100544-19568a
contract_validation: passed
radar_module_count: 14
metric_evidence_count: 627
```

## cockpit latest / overview / history

```text
dashboard: p45.btc_trend_cockpit.v2 / neutral / neutral / unconfirmed
overview:  p45.btc_trend_cockpit.v2 / neutral / neutral / unconfirmed
history:   p45.btc_trend_cockpit.v2 / neutral / neutral / unconfirmed
```

当前 cockpit 分数：

```json
{
  "fast_net_score": 0.0204,
  "confirmation_net_score": -0.1101,
  "regime_net_score": 0.0021,
  "controller_score": 1.0,
  "support_score": 0.136,
  "pressure_score": 0.5026,
  "conflict_score": 0.136,
  "rejection_score": 0.2,
  "trend_acceptance_score": 51.82,
  "data_quality_penalty": 6.0
}
```

审计解释：

- `pressure_score` 高于 support，但 fast layer 未形成同向 bearish，`trend_acceptance_score` 只有 unconfirmed，因此中心卡没有机械升级为 `confirmed_bearish`。
- latest、overview、history replay 返回同一份 `btc_trend_cockpit` schema。
- `contract_validation.status = passed`，controller 未阻断。

## 测试

```text
backend/tests/test_p45_btc_trend_cockpit.py
backend/tests/test_p45_final_writer.py
backend/tests/test_p45_dashboard_api.py

结果：38 passed
```

```text
npm run build

结果：passed
```

```text
scripts/validate_p5_dashboard_contract.py --base-url http://127.0.0.1:8118

结果：P5 dashboard contract validation passed.
```

## DoD 核对

1. run once 产出 `btc_trend_cockpit.schema_version = p45.btc_trend_cockpit.v2`：PASS
2. dashboard latest / overview latest / history replay 均可读取 cockpit：PASS
3. 前端中心卡 cockpit-first，旧 payload fallback：PASS
4. 单模块 confirmed 禁止规则测试通过：PASS
5. pressure 高但 acceptance 低时不会 confirmed bearish：PASS
6. data quality / contract blocking 规则测试通过：PASS
7. targeted tests 与 frontend build 通过：PASS
8. P5 dashboard contract 通过：PASS

## 残余风险

- 本次 run 使用 `skip_llm=true`，LLM appendix 按执行 profile 被跳过；这不影响 cockpit deterministic 链路。
- data quality 仍有 `MISSING_FRESHNESS_FIELDS` warning，cockpit 已作为 `data_quality_penalty=6.0` 降权处理。
