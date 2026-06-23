# P1-C17 Bitbo STH/LTH 成本基础公开数据勘探

## 状态

DONE

## Closure（2026-06-23）

P1-C17 主线目标已完成：Bitbo STH/LTH 页面结构化数据已经通过 human-verified Playwright profile 读取并进入 source registry、metric definition、live collection 与 P2 消费链路。

- 已落地 source：`bitbo-sth-lth-realized-price`。
- 已落地指标：`sth_cost_basis`、`lth_cost_basis`。
- 半自动验证态仍保留为运行边界：profile 过期、Human Challenge、迁移后 profile 丢失时进入 source health warning，并由 Data Quality / Settings 人工验证流程处理。
- 该 semi-automated caveat 不阻塞本卡 DONE；若后续要求无人工验证态稳定 API，应另开 provider/API 精确化任务。

## 当前进度（2026-05-20）

已通过一次可见 Playwright + 持久化 profile 的人工验证，并确认 Bitbo 页面存在结构化导出数据：

| 项目 | 状态 | 说明 |
|---|---|---|
| 可见 Playwright 验证 | DONE | 已使用 `cache/playwright-bitbo-profile` 完成 Human Challenge |
| 网络与页面勘探 | DONE | 页面无独立公开 JSON 请求，但 HTML/DOM 内存在 `window.chartExportData` |
| STH 数据读取 | DONE | `window.chartExportData` 可读取 `STH Realized Price`，共 5619 行 |
| LTH 数据读取 | DONE | `window.chartExportData` 可读取 `Long Term Holder Realized Price`，共 5619 行 |
| Source Registry | DONE | 已新增 `bitbo-sth-lth-realized-price` |
| Metric Definition | DONE | 已新增 `sth_cost_basis`、`lth_cost_basis` |
| Live 采集 | DONE | 已成功落库 STH/LTH 最新值，source health = healthy |
| 无人值守稳定性 | WATCH | 依赖持久化 human-verified profile，验证态过期后需重新运行可见脚本 |

### 最新实测值

| 指标 | 日期 | 值 |
|---|---|---:|
| `sth_cost_basis` | 2026-05-20 | 78343.98 |
| `lth_cost_basis` | 2026-05-20 | 48646.66 |

### 本轮验证结果

- `ruff check src tests`：通过。
- `..\.venv\Scripts\python.exe -m pytest`：26 passed。
- `collect-sources --mode live --source-id bitbo-sth-lth-realized-price`：通过，errors = 0。
- `analyze-radars`：14 个雷达完成，P2-C07 可消费 STH/LTH。

### 人工干预与 UI 同步

Bitbo 当前应被记录为半自动源，而不是完全自动源：

```yaml
source_id: bitbo-sth-lth-realized-price
automation_mode: semi_automated
requires_human_verified_profile: true
profile_dir: cache/playwright-bitbo-profile
manual_reauth_required_when:
  - Human Challenge
  - Precondition Required
  - profile expired
  - profile missing after migration
on_failure:
  source_health: warning
  block_pipeline: false
  ui_action: Open Verify Window
```

已新增 P5-C23 负责 UI 同步：Data Quality / Source Detail / Settings 需要显示 `manual_reauth_required`，并提供打开验证窗口、重试采集、查看最近捕获结果的入口。

## 所属 Phase

P1 数据源与历史数据底座

## 任务定位

继续补齐 `sth_cost_basis` / `lth_cost_basis`。本任务专门验证 Bitbo 图表页是否能作为免费公开数据源，目标是尽量拿到结构化数据，而不是从截图硬读数。

目标页面：

```text
https://charts.bitbo.io/sth-realized-price/
https://charts.bitbo.io/lth-realized-price/
```

## 当前实测结论（2026-05-20）

| 测试项 | 结果 | 结论 |
|---|---|---|
| 普通 HTTP 请求 `charts.bitbo.io/sth-realized-price/` | 428 Precondition Required | 不能用简单 HTTP 抓取 |
| 普通 HTTP 请求 `charts.bitbo.io/lth-realized-price/` | 428 Precondition Required | 不能用简单 HTTP 抓取 |
| Playwright headless 打开 STH 页面 | 页面标题 `Human Challenge`，触发 Cloudflare Turnstile | headless 默认不可直接抓 |
| 页面可视化人工浏览 | 用户截图显示图表可见 | 浏览器人工验证态下可能可访问 |
| API/CSV/JSON 稳定入口 | 未发现独立公开 endpoint | 页面下载功能读取 `window.chartExportData` |
| 持久化 profile 后 headless 读取 | 成功 | 复用验证态后可直接读取 `window.chartExportData` |

初步判断：Bitbo 页面“看得到”不等于“无状态生产可采集”。但通过一次人工验证后，可以复用持久化 profile，从页面内结构化对象 `window.chartExportData` 读取 STH/LTH 数据。该方案可用，但需要在 source health 中标记“依赖验证态”。

## 指标定义

```yaml
sth_cost_basis:
  meaning: 短期持有者 realized price / cost basis
  preferred_source: bitbo_or_provider
  target_quality: high

lth_cost_basis:
  meaning: 长期持有者 realized price / cost basis
  preferred_source: bitbo_or_provider
  target_quality: high
```

## 数据源分层方案

### 第一层：Bitbo 结构化数据

优先寻找：

```text
JSON API
CSV / XLSX 下载地址
Next.js / 静态数据 payload
图表 series endpoint
```

如果找到结构化接口：

```yaml
bitbo_sth_lth_realized_price:
  method: http_or_playwright_network
  metrics:
    - sth_cost_basis
    - lth_cost_basis
  quality: high_or_medium
  requirement:
    - stable_endpoint
    - latest_timestamp
    - numeric_series
```

### 第二层：Playwright 持久化浏览器验证态

如果接口需要 Cloudflare 人工验证态：

```yaml
bitbo_verified_browser_session:
  method: playwright_persistent_context
  flow:
    - 用户手动打开可见浏览器
    - 完成 Turnstile / 登录 / 订阅验证
    - 保存 storage_state 或 user_data_dir
    - 后续定时任务复用该验证态
  limitation:
    - 验证态可能过期
    - 打包迁移时需要重新验证
    - 不能作为无人值守强依赖
```

### 第三层：图表 OCR / Canvas 读数

仅作为最后兜底：

```yaml
bitbo_chart_ocr:
  method: screenshot_or_canvas_pixel
  quality: low
  usage: UI reference only
  not_allowed_for:
    - strong_signal
    - high_confidence_llm_evidence
```

## 需要实现的采集策略

### 1. 网络捕获脚本

新增或复用 P1-C06 Playwright 框架，支持：

- 可见浏览器模式。
- 持久化 `user_data_dir`。
- 捕获所有 XHR/fetch/script 请求。
- 自动保存：
  - request URL。
  - response status。
  - content-type。
  - JSON/CSV payload sample。
  - 页面截图。

### 2. Bitbo Source Registry

如果结构化数据确认可用，新增：

```yaml
source_id: bitbo-sth-lth-realized-price
group_name: onchain_valuation
method: playwright_network_or_http
metrics:
  - sth_cost_basis
  - lth_cost_basis
url:
  - https://charts.bitbo.io/sth-realized-price/
  - https://charts.bitbo.io/lth-realized-price/
```

### 3. 数据质量与 fallback

```yaml
quality_policy:
  structured_json: 0.82
  structured_csv: 0.80
  verified_browser_network: 0.72
  chart_ocr: 0.45
  human_challenge_unresolved: warning
```

如果 Bitbo 不稳定：

```yaml
fallback:
  provider_required:
    - glassnode
    - cryptoquant
  proxy:
    - realized_price
    - mvrv_zscore
    - nupl
  note: proxy 不能命名为 STH/LTH cost basis
```

## 对 P2 的影响

P2-C07 链上估值与筹码雷达目前仍缺：

- `sth_cost_basis`
- `lth_cost_basis`

如果 P1-C17 成功，P2-C07 的 data quality 可以从 medium 提升到 high。  
如果失败，P2-C07 保持 medium，并明确这两个指标进入 provider-required。

## DoD

- 完成 Bitbo STH/LTH 页面 HTTP、headless Playwright、可见 Playwright 三种方式验证。
- 明确是否存在可复用 JSON/CSV/API endpoint。
- 若存在稳定结构化数据，接入 source registry 并落库 `sth_cost_basis` / `lth_cost_basis`。
- 若只在人工验证态可用，建立 persistent browser session 方案与过期处理。
- 若只能截图/OCR，禁止标记为 DONE，必须保留为 `low_quality_reference`。
- 更新 P1-C15 / P1-C13 中关于 STH/LTH provider-required 的结论。

## 验收命令

```powershell
python -m onlybtc.cli collect-sources --mode live --source-id bitbo-sth-lth-realized-price
python -m onlybtc.cli analyze-radars
python -m pytest
```

## 风险

- Bitbo 有 Cloudflare Turnstile，普通 headless 抓取会触发 `Human Challenge`。
- 免费图表不一定授权高频抓取，采集频率应低于 1h，优先日更。
- 如果需要 Bitbo API key，应进入 P10 Provider Settings，而不是硬编码到 P1。
