# P7-C13 TimeScale Judge 全链路审计

## 结论

PASS

## 审计时间

2026-05-27 Asia/Shanghai

## 审计对象

- P4.5-C43 BTC TimeScale Judge v2.1 聚合器
- P4.5-C44 BTC Acceptance Gate
- P4.5-C45 Cross-Horizon Arbiter
- P8-C34 payload 持久化与 replay
- P9-C39 API 透传
- P5-C61 时间尺度视图 v2 前端展示

## 最新 run

- `collect_run_id`: `collect-20260527143118-087f32`
- `p2_radar_run_id`: `radar-20260527143403-b103b0`
- `p3_run_id`: `p3-20260527143406-ed25df`
- `pack_id`: `p45pack-20260527143416-1fb09b`
- `article_run_id`: `p45articles-20260527143417-6ab6e1`
- `final_run_id`: `p45final-20260527143417-2e0020`

## 契约检查

- `final_payload.btc_timescale_judge.schema_version = p45.btc_timescale_judge.v2.1`
- `dashboard/latest` 返回 `btc_timescale_judge`
- `overview/latest` 返回 `btc_timescale_judge`
- `history/{final_run_id}` 返回历史对应 `btc_timescale_judge`
- horizon 输出包含 `4h / 24h / 3d / 7d`
- cross_horizon 输出包含 `dominant_horizon / alignment / headline_direction / headline_stage / why_not_stronger / why_not_reversed`

## 业务规则检查

| 规则 | 结果 |
|---|---|
| 4h 只做 fast sensing，不单独触发 headline confirmed | PASS |
| 24h 必须经过 BTC acceptance gate | PASS |
| 3d 用资金/宏观/衍生品延续确认，不被 5m 噪音覆盖 | PASS |
| 7d 作为 regime/background，不覆盖短线 | PASS |
| context_only / regime_only 不允许触发 confirmed | PASS |
| BTC response/residual 缺失时 confirmed 自动降级 | PASS |
| 24h + 3d 同向且 accepted 才能 headline confirmed | PASS |
| latest/history replay 保持同一份 payload | PASS |

## 最新 payload 摘要

```json
{
  "schema_version": "p45.btc_timescale_judge.v2.1",
  "horizons": ["4h", "24h", "3d", "7d"],
  "cross_horizon": {
    "dominant_horizon": "3d",
    "alignment": "aligned",
    "headline_direction": "neutral",
    "headline_stage": "watch",
    "why_not_stronger": "Need 24h and 3d same-direction acceptance for confirmed headline.",
    "why_not_reversed": "No accepted opposite multi-horizon evidence yet."
  }
}
```

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_timescale_judge.py backend\tests\test_p45_btc_trend_cockpit.py backend\tests\test_p45_invalidation_workbench.py -q
```

结果：`14 passed`

```powershell
cd frontend
npm run build
```

结果：通过

```powershell
.\.venv\Scripts\python.exe scripts\validate_p5_dashboard_contract.py --base-url http://127.0.0.1:8118
```

结果：`P5 dashboard contract validation passed.`

## 残余风险

- 当前 `btc_response_score / residual_score` 仍依赖各 radar module 已输出字段，后续可继续用 replay/backtest 校准阈值。
- 4h 在前端仍作为 24h 内部 fast 子证据使用，UI 不单独展示第四张主卡，这是本轮设计选择。
