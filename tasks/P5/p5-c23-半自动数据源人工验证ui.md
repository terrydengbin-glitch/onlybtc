# P5-C23 半自动数据源人工验证 UI

## 状态

DONE

## 当前架构对齐（2026-05-22）

人工验证 UI 主要服务 P1 source health 和 P2/P3/P4.5 下游影响追踪。

页面需展示 source 验证结果对链路的影响：影响哪些 `metric_id`、影响哪些 Radar module、是否进入 P3 scored evidence、是否进入 P4.5 evidence pack、是否造成 contract warning 或 data boundary。

## 所属 Phase

P5 Vue3 Dashboard 与可视化页面

## 任务定位

为 Bitbo 这类“可采集但依赖 human-verified browser profile”的半自动数据源提供 UI 闭环。系统不能静默失败，也不能要求用户去命令行找脚本；当验证态过期时，UI 必须明确提示并提供“打开验证窗口”的动作。

首个适配源：

```text
bitbo-sth-lth-realized-price
```

## 背景

P1-C17 已验证：

- Bitbo STH/LTH 页面普通 HTTP 会返回 428。
- headless Playwright 会进入 Human Challenge。
- 用户通过一次可见 Playwright 验证后，可以复用 `cache/playwright-bitbo-profile`。
- 后续采集可从页面 `window.chartExportData` 读取结构化数据。

因此该源不是完全无人值守源，而是：

```yaml
automation_mode: semi_automated
requires_human_verified_profile: true
manual_action: reauth_required_when_profile_expired
```

## UI 入口

### Data Quality

在 Source Health 表格新增字段/标识：

| 字段 | 说明 |
|---|---|
| Automation | `auto` / `semi_auto` / `manual` |
| Reauth | `valid` / `required` / `unknown` |
| Last Verified | 最近人工验证时间 |
| Action | `Open Verify Window` |

当 source health 中出现以下情况时，行状态显示为 `reauth_required`：

```text
Human Challenge
Precondition Required
requires_human_verified_profile
manual_reauth_required
```

视觉要求：

- 默认使用 amber/warning 状态。
- 不把 reauth required 误显示成系统崩溃。
- Tooltip 说明：该源需要人工验证一次，验证通过后会继续自动采集。

### Source Detail

新增 “Manual Verification” 区块：

```yaml
source_id: bitbo-sth-lth-realized-price
automation_mode: semi_automated
profile_dir: cache/playwright-bitbo-profile
last_verified_at: 2026-05-20 16:39
expires_estimate: unknown
status: valid / required
```

按钮：

- `Open Verify Window`
- `Retry Collect`
- `View Last Capture`
- `Open Run Logs`

### Settings

Data Sources Tab 增加 “Semi-Automated Sources” 分组：

- Bitbo STH/LTH Realized Price
- 未来类似 Cloudflare / 登录态页面源

配置项：

```yaml
profile_dir:
  readonly_or_editable: editable
refresh_policy:
  default: 1h
on_challenge:
  options:
    - mark_warning
    - notify_user
    - open_verify_window
```

### Run Logs

当采集失败原因是 human challenge 时，运行日志阶段显示：

```text
stage: fetching
status: blocked
reason: manual_reauth_required
action: Open Verify Window
```

## FastAPI 对接需求

需要 P9 / P10 增加或复用以下接口：

```text
GET  /api/sources/{source_id}/auth-state
POST /api/sources/{source_id}/open-verify-window
POST /api/sources/{source_id}/retry-collect
GET  /api/sources/{source_id}/last-capture
```

返回示例：

```yaml
source_id: bitbo-sth-lth-realized-price
automation_mode: semi_automated
requires_human_verified_profile: true
auth_state: valid
last_verified_at: 2026-05-20T16:39:40+08:00
profile_dir: cache/playwright-bitbo-profile
last_error: null
```

## DoD

- Data Quality 能显示半自动源和重新验证状态。
- Source Detail 能展示 profile、验证状态、最近采集值和最近错误。
- Settings 有 Semi-Automated Sources 分组。
- 用户可以从 UI 触发打开验证窗口。
- 验证完成后可以点击 Retry Collect。
- Mock 数据覆盖 `auth_state=valid`、`required`、`unknown`。
- 半自动源状态必须进入 P5-C25 的数据质量/fallback fixture，不可只在单页特殊处理。
- History Replay 中必须保留当时的 reauth 状态，不用当前 auth_state 覆盖历史。

## 关联任务

P1-C17、P5-C14、P5-C16、P5-C22、P9-C06、P9-C14、P10-C04。

## Completion Log

- Completed at: 2026-05-23
- Frontend store connected source auth-state, verify-window, retry-collect and last-capture endpoints.
- Data Quality surfaces semi-automated source rows with automation, reauth and last verified state.
- Source Detail includes Manual Verification actions and downstream impact context.
- Settings / Data Sources includes a Semi-Automated Sources group.
- Run Logs surfaces manual reauth actions when stage payload reports human challenge / captcha / reauth signals.
- Verification:
  - `npm run build`
  - `scripts/validate_p5_dashboard_contract.py`
  - `scripts/validate_p5_page_dod.py`
