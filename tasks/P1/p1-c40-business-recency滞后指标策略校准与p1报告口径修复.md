# P1-C40 / Business Recency 滞后指标策略校准与 P1 报告口径修复

## 状态

DONE

## 背景

P1-C22 报告曾把 expected lag、provider 低频发布、真实滞后混在“业务时间滞后或过旧”里，容易误伤低频指标。重点样例：

| metric_id | source_id | 处理口径 |
|---|---|---|
| `usdjpy` | `fred-usdjpy` | 若业务时间超过 7 天，标记 `provider_stale_suspect` |
| `usdcnh` | `fred-usdcnh-proxy` | 若业务时间超过 7 天，标记 `provider_stale_suspect` |
| `etf_net_flow` | `playwright-glassnode-asset-overview` | 按 daily / page snapshot 节奏判断，正常延迟为 `expected_lag` |
| `etf_flow_7d` | `playwright-glassnode-asset-overview` | 按 daily / page snapshot 节奏判断，正常延迟为 `expected_lag` |

## 修改内容

1. `compute_business_recency` 增加 `provider_stale_suspect` 状态。
2. `fred-usdjpy` / `fred-usdcnh-proxy` 超过 7 天未更新时，不再当作普通 expected lag，而是 provider 旧快照疑似。
3. Data Quality `business_recency_counts` 纳入 `provider_stale_suspect`。
4. P1-C22 当前问题清单只展示 `lagging` / `outdated` / `provider_stale_suspect`，不再把 `expected_lag` 放进问题清单。
5. P1-C22 business recency 问题文案改为“超过 provider 预期节奏，需核对源更新或 fallback”，避免把 expected lag 写成采集失败。
6. Radar/P3 freshness 权重识别 `provider_stale_suspect`，作为轻度降权，不作为未知状态处理。

## DoD

- [x] `expected_lag` 不再进入 P1 当前问题清单。
- [x] `usdjpy/usdcnh` 有 provider-aware 判断。
- [x] ETF flow 保留 daily/page snapshot 节奏口径。
- [x] P1-C22 文案不再混淆 expected lag 与真实滞后。
- [x] P1-C22 问题清单能列出具体指标、source_id、source_ts。
- [x] 相关测试通过。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_sources.py::test_fx_proxy_business_recency_marks_provider_stale_suspect backend/tests/test_sources.py::test_ofr_and_glassnode_use_daily_business_recency_policy backend/tests/test_p1_c22_audit.py -q
```

