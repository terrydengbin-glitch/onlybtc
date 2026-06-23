# P11-C05 / Options RV 日 K 未来 source_ts 修复

## 状态

DONE

## 背景

最新 run once 审计发现：

```text
options_rv
rv_change_1d
```

存在未来 `source_ts`：

```text
source_ts = 2026-05-25T23:59:59.999Z
审计时间约为 2026-05-25T11:06Z
```

原因大概率是 Binance 1D K 线使用了当前未收盘日 K 的 close time。该问题目前不污染方向分，但会误导 freshness / business recency 审计。

## 目标

修复 `options_rv` 派生逻辑，避免使用未来时间戳。

优先策略：

```text
1. 若使用当前未收盘日 K：
   source_ts 使用 open time 或 collected_at，不使用未来 close time。

2. 若计算 30D RV 需要闭合日 K：
   排除当前未收盘日 K，只使用已收盘 K。
```

建议优先采用第 2 种：`options_rv` 作为 30D realized volatility，应基于已收盘日 K 更稳。

## 范围

- 修复 `binance-btcusdt-kline-1d-rv` 的 `options_rv` 时间戳口径。
- 同步保证派生的 `rv_change_1d` 不继承未来 `source_ts`。
- 不改变 `options_volatility` v2.1 的方向隔离契约。
- 不改变 `module_score = 0` / `module_direction = neutral` 规则。

## DoD

- 最新 run 中不存在 `options_rv.ts > now`。
- 最新 run 中不存在 `rv_change_1d.ts > now`。
- `options_volatility` 仍输出：

```text
module_direction = neutral
module_score = 0
module_effective_score = 0
```

- P1/P3/API 相关测试通过。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_sources.py backend\tests\test_p3_pipeline.py backend\tests\test_p45_dashboard_api.py -q
```
