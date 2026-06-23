# P7-C13 / TimeScale Judge 全链路审计

## 状态

DONE

## 目标

对 TimeScale Judge v2.1 做严格全链路审计，确认 P4.5 聚合器、BTC acceptance gate、cross-horizon arbiter、SQLite/replay、FastAPI、Vue3 时间尺度视图都符合业务预期。

## 审计范围

- P4.5-C43 TimeScale Judge 聚合器
- P4.5-C44 BTC Acceptance Gate
- P4.5-C45 Cross-Horizon Arbiter
- P8-C34 payload 持久化与 replay
- P9-C39 API 透传
- P5-C61 前端展示

## 审计重点

1. 4h 是否只负责 fast sensing，不单独触发 headline confirmed。
2. 24h 是否能结合 4h fast + BTC acceptance 输出短线判断。
3. 3d 是否以资金/宏观/衍生品确认为主，不被 5m 噪音污染。
4. 7d 是否只作为 regime/background，不覆盖短线。
5. BTC response / residual 缺失时是否降级。
6. context_only / regime_only 是否不能触发 confirmed。
7. 24h + 3d 同向且 accepted 时是否可升级 headline confirmed。
8. conflict / why_not_stronger / why_not_reversed 是否可解释。
9. latest 与 history replay 是否读取同一份 payload。
10. 前端是否优先读新契约，旧契约 fallback 是否可用。

## 输出报告

- `reports/p7-c13-timescale-judge-audit.md`
- `reports/p7-c13-timescale-judge-audit.json`

## DoD

- 审计报告状态为 PASS 才能关闭。
- 发现 confirmed 误触发必须修复后重跑。
- `pytest` 通过。
- `npm run build` 通过。
- `validate_p5_dashboard_contract.py` 通过。
- run once 后 latest payload 包含 `btc_timescale_judge.v2.1`。

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_timescale_judge.py backend\tests\test_p45_btc_trend_cockpit.py backend\tests\test_p45_invalidation_workbench.py -q
cd frontend
npm run build
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py --base-url http://127.0.0.1:8118
```

## 关联任务

P4.5-C43, P4.5-C44, P4.5-C45, P8-C34, P9-C39, P5-C61

## 验收记录

- 审计报告：[p7-c13-timescale-judge-audit.md](../../reports/p7-c13-timescale-judge-audit.md)
- 审计 JSON：[p7-c13-timescale-judge-audit.json](../../reports/p7-c13-timescale-judge-audit.json)
- 结论：PASS。
