# P1-C74 FRED Provider Resilience

状态：DONE

完成时间：2026-05-29

## 背景

P1 审计中出现一批 FRED 源同时失败或滞后：

```text
fred-dxy
fred-real-yield
fred-treasury-2y / 10y / 30y
fred-vix
fred-fed-balance-sheet
fred-bank-reserves
fred-on-rrp
fred-sofr / fred-iorb / fred-tga
fred-dow-jones
fred-wti-oil / fred-brent-oil
fred-usdjpy
```

实测这些源在稍后可恢复，说明问题主要是 FRED API 瞬时 `504 Gateway Time-out`、`ReadTimeout` 或同一批 FRED 源并发过高导致的短时失败。另一个独立问题是 `fred-usdjpy` / `fred-usdcnh` 这类 FX proxy 天然可能比实时市场滞后，继续只依赖 FRED 会反复出现 `provider_stale_suspect`。

核心原则：

```text
FRED 是官方/官方镜像源，但不是高频行情源。
API 504/timeout 不能直接让整批宏观模块掉线。
API 失败要自动降级 fredgraph.csv。
同一批 FRED 源必须限流/分批。
FX proxy 必须接入实时替代源，否则 stale 是设计缺陷，不是偶发故障。
```

## 目标

增强 FRED Provider 的韧性，使 P1 在 FRED API 短时异常时仍能产出可追溯、可解释、非 mock 的数据，并让实时 FX proxy 不再被 FRED 日频更新节奏拖住。

## 范围

涉及：

- `FredClient` / FRED provider 调用层
- FRED source registry / source fetch lineage
- P1 collector 并发限流和分批策略
- TradingView 或其他实时 FX 替代源配置
- P1 审计 HTML / 失败清单展示

不涉及：

- 修改 radar module 评分逻辑
- 修改 BTC 主卡聚合规则
- 把 TradingView 替代源伪装成 FRED 官方源
- 暴露或记录 FRED API key

## 设计要求

### 1. FRED API 自动重试

对 FRED API 请求增加有限重试：

```yaml
fred_retry_policy:
  retry_on:
    - http_429
    - http_500
    - http_502
    - http_503
    - http_504
    - connect_timeout
    - read_timeout
  max_attempts: 3
  backoff:
    base_sec: 0.8
    multiplier: 2.0
    jitter_sec: 0.2
  do_not_retry:
    - http_400
    - http_401
    - http_403
    - invalid_series
    - parse_error
```

每次尝试必须写入 lineage：

```json
{
  "provider": "fred_api",
  "attempt": 2,
  "endpoint": "series/observations",
  "http_status": 504,
  "elapsed_ms": 15000,
  "error_type": "http_504"
}
```

### 2. `fredgraph.csv` fallback

当 FRED API 失败时，自动切换：

```text
https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}
```

要求：

- 不需要 API key。
- 解析最后一个非空、非 `.` 的 observation。
- 保留 `source_ts` 为 CSV 中最后 observation date。
- 标记 `fallback_used=fredgraph_csv`。
- 保留 primary API 错误，不得吞掉。
- CSV fallback 成功时，该源不应进入 `source_unavailable`，应进入 `partial_live` 或 `fallback_live`。

输出 lineage 示例：

```json
{
  "provider": "fredgraph_csv",
  "source_tier": "official_public_fallback",
  "is_fallback": true,
  "fallback_for": "fred_api",
  "primary_error": "http_504",
  "confidence": 0.90
}
```

### 3. FRED 批量限流 / 分批

同一轮 P1 collect 中，FRED 源不得瞬时全并发打到 FRED API。

建议策略：

```yaml
fred_batch_policy:
  max_concurrency: 3
  batch_size: 5
  inter_batch_delay_ms: 500
  per_request_jitter_ms: [100, 400]
  per_host_timeout_sec: 15
```

DoD 要求：

- 同一批 10+ FRED 源不会在同一毫秒级时间窗同时发起。
- `source_fetches` 或运行日志能看到 batch / queue / throttle 记录。
- FRED 限流只影响 FRED provider，不拖慢 Binance / Event Window / TradingView 等其他 provider。

### 4. FX proxy 实时替代源

`fred-usdjpy` / `fred-usdcnh` 不再作为实时判断主源。

建议优先级：

```yaml
fx_proxy_sources:
  usdjpy:
    primary_current:
      - tradingview-usdjpy
      - yahoo-finance-usdjpy
      - stooq-usdjpy
    fallback_context:
      - fred-usdjpy

  usdcnh:
    primary_current:
      - tradingview-usdcnh
      - yahoo-finance-usdcnh
      - stooq-usdcnh
    fallback_context:
      - fred-usdcnh-proxy
      - fred-usdcny-proxy
```

规则：

- 实时 FX 页面源成功时，P2/P3 使用实时源作为 current value。
- FRED FX 继续用于历史/context/fallback，不参与高频实时 freshness 判定。
- FRED FX stale 不应单独导致 `asia_risk` 或 `macro_radar` 数据质量降级为 failed。
- UI / 审计必须显示 `primary_current=tradingview/yahoo/stooq`、`fallback_context=fred`。

### 5. P1 审计展示

P1 审计 HTML 和失败清单必须展示：

- `retry_count`
- `api_attempts`
- `fallback_used`
- `fallback_provider`
- `primary_error`
- `batch_group`
- `throttle_status`
- `provider_stale_suspect` 是否由 FRED FX proxy 引起
- FX proxy 当前主源

失败清单口径：

```text
FRED API fail + fredgraph.csv success => 不列为失败，只列为 fallback warning。
FRED API fail + CSV fail => source_unavailable。
FRED FX stale + 实时替代源 success => 不列为失败，只列为 context fallback stale。
FRED FX stale + 无实时替代源 => provider_stale_suspect。
```

## 影响链条

```text
P1 Source Fetch
  -> source_fetch lineage
  -> raw observation / derived metric
  -> P2 radar module input
  -> P3/P4.5 semantic profile
  -> P5 UI / P1 audit HTML
```

该任务只提升数据源韧性和新鲜度，不改变下游多空解释逻辑。

## 测试计划

### Unit / Mock

1. Mock FRED API 第一次 `504`、第二次成功：
   - 返回成功
   - `retry_count >= 1`
2. Mock FRED API 连续 timeout，`fredgraph.csv` 成功：
   - status 为 fallback live
   - `fallback_used=fredgraph_csv`
3. Mock API 和 CSV 都失败：
   - status 为 `source_unavailable`
   - primary 和 fallback error 都可见
4. Mock `fred-usdjpy` stale + TradingView success：
   - metric 使用 TradingView current value
   - FRED 被标记为 context fallback

### Live Smoke

运行一批 FRED 核心源：

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'
.\.venv\Scripts\python.exe -m onlybtc.cli p1-c22-audit --source-id fred-dxy --source-id fred-real-yield --source-id fred-treasury-2y --source-id fred-treasury-10y --source-id fred-treasury-30y --source-id fred-vix --source-id fred-fed-balance-sheet --source-id fred-bank-reserves --source-id fred-on-rrp --source-id fred-sofr --source-id fred-iorb --source-id fred-tga --source-id fred-usdjpy
```

验收：

- 不出现整批 FRED 同时 `source_unavailable`。
- 若 API 失败，CSV fallback 能接管。
- P1 HTML 中 fallback / retry / batch 信息可见。

## DoD

1. [x] FRED API `504` / timeout 时自动重试，且 retry lineage 可见。
2. [x] FRED API 失败时自动走 `fredgraph.csv` fallback。
3. [x] API fail + CSV fallback success 不再被列入失败源，只作为 fallback warning。
4. [x] 同一批 FRED 源被限流/分批，避免瞬时并发打爆。
5. [x] FRED batch policy 有参数化配置，不是散落硬编码。
6. [x] `fred-usdjpy` / `fred-usdcnh` 具备 TradingView、Yahoo、Stooq 或等价实时替代源。
7. [x] FX 实时替代源成功时，FRED FX stale 不再阻断 `asia_risk` / `macro_radar`。
8. [x] P1 审计 HTML 显示 retry、fallback、batch、FX primary/fallback lineage。
9. [x] 单元测试覆盖 API retry、CSV fallback、FX stale 替代。
10. [x] P1 全链路审计通过，失败清单不再出现 FRED transient 造成的大面积滞后。

## 验收记录

```text
python -m pytest backend/tests/test_sources.py -q
=> 56 passed

python -m onlybtc.cli p1-c22-audit --source-id fred-dxy ... --source-id fred-usdjpy
=> 失败数量 0
=> reports/p1-c22-真实数据全链路验收报告.html 已生成
=> fred_batch_group_count=3
=> fredgraph_csv_fallback_count=0，本轮 FRED API 正常，fallback 逻辑由单测覆盖
```
