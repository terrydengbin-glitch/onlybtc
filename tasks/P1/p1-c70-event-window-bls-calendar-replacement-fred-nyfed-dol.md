# P1-C70 Event Window BLS Calendar Replacement: FRED official_mirror + NYFed time crosscheck + DOL post-release docs

## 背景

当前运行环境中 `bls.gov` 域名整体可能被 deny，继续更换 BLS URL 意义不大。Event Window 需要把 BLS calendar 从“主源 + fallback”改为“disabled blocked source + FRED official_mirror 主镜像”。

当前已验证：

```text
bls-release-calendar -> 403 Access Denied
fred-release-dates -> success, official_mirror, 可输出 CPI/NFP/PPI/JOLTS/ECI
```

## 目标

将 BLS 日历链路升级为：

```text
primary calendar mirror:
  fred-bls-release-calendar

time crosscheck:
  nyfed-economic-indicators-calendar

post-release document mirror:
  dol-bls-economicdata

disabled / recorded:
  bls-release-calendar
  bls-release-calendar-html
  bls-rss-release-feeds
```

核心原则：

```text
Event Window 可以 partial live，但不能 fake live。
FRED 可以替代 BLS schedule 主链路，但必须标记 official_mirror，不伪装成 BLS official live。
```

## 数据源契约

### 1. FRED BLS Release Calendar

```yaml
source_id: fred-bls-release-calendar
source_tier: official_mirror
status: primary_when_bls_denied
provider: Federal Reserve Bank of St. Louis FRED
replaces:
  - bls-release-calendar
```

使用：

```text
fred/source/releases?source_id=22
fred/release/dates?release_id={release_id}&include_release_dates_with_no_data=true
```

核心 release_id：

```text
CPI: 10
NFP / Employment Situation: 50
PPI: 46
JOLTS: 192
ECI: 11
Productivity and Costs: 47
Import / Export Price Indexes: 188
```

### 2. NY Fed Economic Indicators Calendar

```yaml
source_id: nyfed-economic-indicators-calendar
source_tier: official_fed_crosscheck
use_for:
  - release_time_crosscheck
  - 08:30 / 10:00 ET validation
```

### 3. DOL Economic Data

```yaml
source_id: dol-bls-economicdata
source_tier: official_parent_mirror
use_for:
  - post_release_pdf
  - release_document_link
  - arrival_confirmation
not_use_for:
  - full_future_schedule
```

## 实现要求

1. 不再把 `bls-release-calendar` 作为活跃 primary 反复尝试；当环境记录 BLS deny 后，应标记为 `disabled_access_denied` 或低频健康探测。
2. 将当前 `fred-release-dates` 重命名/升级为 `fred-bls-release-calendar`。
3. FRED 输出必须包含：
   - `release_id`
   - `release_name`
   - `release_date`
   - `release_time_et`
   - `release_time_utc`
   - `source_tier=official_mirror`
   - `original_authority=BLS`
   - `mirror_provider=FRED`
   - `calendar_confidence`
4. `include_release_dates_with_no_data=true` 必须保留。
5. 时间处理必须 timezone-aware，不允许硬写 `+1 hour`。
6. 对 FRED 无精确时间的情况，可以使用 event_type 默认时间，但必须标记 `time_inferred=true`。
7. 接入 NY Fed calendar 做时间交叉校验：
   - 若时间一致，增加 `time_crosscheck_status=passed`。
   - 若缺失，标记 `time_crosscheck_status=missing`，不阻断。
   - 若冲突，标记 `time_crosscheck_status=conflict` 并降低 confidence。
8. 接入 DOL post-release docs，只用于发布后文档链接和 arrival confirmation。
9. Source diagnostics / UI 不能显示成 `official_bls_live`。

## DoD

1. `bls-release-calendar` 403 时不再导致 calendar 主链路降级为 failed。
2. `fred-bls-release-calendar` 成为 BLS calendar replacement 的 primary mirror。
3. CPI/NFP/PPI/JOLTS/ECI 至少 5 类事件稳定输出。
4. Productivity and Costs / Import Export Price Indexes release_id 已纳入映射。
5. Source lineage 明确显示：
   - `source_tier=official_mirror`
   - `original_authority=BLS`
   - `mirror_provider=FRED`
   - `blocked_provider=bls-release-calendar`
6. NY Fed crosscheck 字段进入事件 payload。
7. DOL post-release docs 字段进入 post-release 文档 payload 或 source diagnostics。
8. Event Window source audit HTML 显示 FRED mirror 替代 BLS 的原因。
9. `scripts/run_event_window_audit_bundle.py` 通过。
10. FastAPI `/api/event-window/latest` 和 `/api/event-window/sources/status` 透传 replacement 状态。
