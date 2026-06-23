# P11-C08 / yield_curve_2s10s_change_bps 口径修复

## 状态

DONE

## 背景

Macro Radar v3 最新 run once 审计发现：

```text
yield_curve_2s10s_change_bps = -408.0
```

该量级不符合 2Y/10Y 曲线 24h 变化的常见 bps 口径，更像是把当前 `10Y-2Y` 利差与历史 `10Y` 利率直接相减。

## 目标

修复 `yield_curve_2s10s_change_bps` 的含义，使其严格表示：

```text
(current 10Y - current 2Y) - (previous 10Y - previous 2Y)
```

并以 bps 输出。

## 已完成

- 新增曲线变化计算 helper。
- 历史对照不再使用 `treasury_10y` 单腿历史值。
- 缺少历史 2Y 或 10Y 任一腿时，不输出强错误值。
- `rates_pressure.basis.yield_curve_2s10s_change_bps` 字段名保持兼容。

## DoD

- `yield_curve_2s10s_change_bps` 不再出现类似 `-408.0` 的利差水平误差。
- 单元测试覆盖：
  - 10Y 与 2Y 均有历史样本时，输出正确的曲线变化 bps。
  - 缺少历史 2Y 或 10Y 时，不输出强错误值。
- `macro_radar` API 仍返回 200。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_p3_pipeline.py backend\tests\test_p45_dashboard_api.py -q
```
