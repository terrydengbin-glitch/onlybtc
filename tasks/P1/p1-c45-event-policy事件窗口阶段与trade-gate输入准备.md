# P1-C45 / Event Policy 事件窗口阶段与 trade_gate 输入准备

## 状态
DONE

## 背景

`event_policy` v2.1 需要的不只是 `days_until`，还需要小时级事件窗口、发布后 digest 状态、blackout 上下文、Fed speech 风险与可选 surprise 上下文。

## 目标

为 P3 `p3.c43.event_policy.v2.1` 准备稳定输入：

```text
cpi_days_until
fomc_days_until
pce_days_until
nfp_days_until
next_fed_speech_hours_until
fed_speech_scheduled_risk
fomc_blackout_active
```

并尽量派生：

```text
cpi_hours_until
fomc_hours_until
pce_hours_until
nfp_hours_until
nearest_event_type
nearest_event_ts
nearest_event_hours
post_event_elapsed_minutes
event_release_landed
event_surprise_abs
event_surprise_direction
btc_5m_range_after_release
dxy_yield_reaction_after_release
```

## 范围

- 复用现有官方日历与 fallback 数据源，不在本卡引入付费源。
- 事件时间戳必须保留 `source_ts`、`collected_at`、provider 与 fallback 标记。
- 若只有 days_until 而没有精确发布时间，允许输出 `precision = day`，P3 不得生成过强 hard lock。
- surprise 与 post-release reaction 缺失时，必须显式标记 `missing`，不得伪造冲击强度。

## DoD

- P1 可为 CPI/FOMC/PCE/NFP/Fed speech 输出事件倒计时与精度。
- blackout active 可作为上下文输入，但不在 P1 直接生成交易禁令。
- 发布后 0-2h 的 digest 判断具备可用字段或明确 missing 标记。
- P1 不输出 bullish / bearish 结论。
- P1/P8 相关测试通过。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_p1_pipeline.py -q
```
