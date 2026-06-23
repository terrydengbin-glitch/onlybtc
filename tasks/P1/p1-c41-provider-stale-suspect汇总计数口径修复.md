# P1-C41 / provider_stale_suspect 汇总计数口径修复

## 状态

DONE

## 背景

最新 `run once` 后，P1-C22 报告出现口径不一致：

- 顶部汇总显示：`provider suspect=0`
- 当前问题清单显示：`usdjpy`、`usdcnh` 为 `provider_stale_suspect`

这说明 `provider_stale_suspect` 已进入指标明细和问题清单，但没有正确进入 P1 顶部 Business Recency 汇总计数。

## 目标

修复 P1-C22 报告内 Business Recency 汇总口径，使顶部统计、指标明细、问题清单三处一致。

## 修改范围

1. 检查 P1-C22 报告生成逻辑中的 business recency 汇总来源。
2. 确保 `provider_stale_suspect` 被计入顶部 `provider suspect` 数量。
3. 保持 `expected_lag` 不进入当前问题清单。
4. 保持 `provider_stale_suspect` 进入当前问题清单。
5. 保持 current run 与 history run_mode 风险分离，不回退 P8-C17 口径。

## 不改范围

- 不修改 P1 数据采集源。
- 不修改 `compute_business_recency` 判定阈值。
- 不修改 Radar/P3/P4.5 分数逻辑。
- 不修改 `expected_lag` 的业务含义。
- 不清理历史 mock/live 混用数据。

## 实施结果

- P1-C22 顶部 Business Recency 汇总改为基于指标明细行重新聚合，而不是读取 source-level payload 汇总。
- 新增 `_business_recency_counts_from_metric_rows`，统一 `current / expected_lag / lagging / outdated / provider_stale_suspect / unknown` 的计数口径。
- Markdown 与 HTML 报告共用同一套 metric-level 汇总。
- 补充单测覆盖 `provider_stale_suspect` 与未知状态归入 `unknown` 的场景。

## DoD

- [x] P1-C22 顶部汇总中的 `provider suspect` 数量与指标明细一致。
- [x] 若 `usdjpy/usdcnh` 明细为 `provider_stale_suspect`，顶部 `provider suspect` 不得为 0。
- [x] 当前问题清单继续列出 `provider_stale_suspect` 样例。
- [x] `expected_lag` 只在明细中展示，不进入当前问题清单。
- [x] `run_mode_mixed_history` 仍显示为历史风险，不污染当前 run。
- [x] 相关单元测试通过。
- [x] 重新生成 P1-C22 报告后人工审计通过。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_p1_c22_audit.py backend/tests/test_sources.py::test_fx_proxy_business_recency_marks_provider_stale_suspect -q
```

结果：

```text
5 passed
```

重新生成报告：

```powershell
.\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --no-collect-live
```

生成结果：

```text
reports/p1-c22-真实数据全链路验收报告.md
reports/p1-c22-真实数据全链路验收报告.html
```

审计样例：

```text
业务时间状态：正常=49，expected lag=25，滞后=2，过旧=55，provider suspect=2，未知=0
```

当前问题清单仍保留：

```text
usdjpy(... provider_stale_suspect ...)
usdcnh(... provider_stale_suspect ...)
```
