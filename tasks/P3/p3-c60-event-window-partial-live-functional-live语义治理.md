# P3-C60 Event Window partial_live functional live 语义治理

状态：DONE

## 背景

Event Window 的数据源体系已经从单一官方源升级为 provider fallback / mirror / proxy 架构。当前运行态可能长期处于：

```text
overall_source_mode = partial_live
```

这不是故障态。它表示部分商业源、受限源或 actual/consensus 字段缺失，但核心功能仍可运行：

- 独立 daemon 常驻
- 官方/镜像日历倒计时
- Cleveland nowcast / secondary calendar mesh
- Binance market probe
- Shock Fast Lane
- Emergency Overlay
- LLM 中文解释
- SQLite / API / UI / HTML audit

因此需要把 `partial_live` 固化为 **functional live** 语义，避免后续状态机、API、UI 或审计把它误判成不可用。

## 目标

建立 Event Window source mode 的业务分层：

```text
live:
  official / primary source complete，最高可信。

partial_live:
  functional live，可完整运行 Event Window 核心功能；
  只在 source lineage、confidence、disabled_capabilities 中标注缺口。

fallback:
  可监控，但 UI / audit 必须提示 fallback。

blocked:
  关键事件时间不可得、actual 应发布但无法确认、系统时间/时区异常、所有 fallback 失败。
```

## 核心要求

1. `partial_live` 不允许阻断 Event Window daemon。
2. `partial_live` 不允许阻断 Shock Fast Lane。
3. `partial_live` 不允许阻断浮窗和 emergency overlay。
4. `partial_live` 不允许被 UI 展示成失败态。
5. `partial_live` 仍必须保留 source lineage、source_tier、fallback_used、disabled_capabilities。
6. `release_surprise_disabled` / `actual_pending` 只能禁用对应能力，不能把整个 Event Window 置为 blocked。
7. 只有 blocking 条件才输出 `blocked`：
   - critical/high 事件时间完全不可得
   - actual 已发布但无法通过官方或可信 fallback 确认
   - 官方文本源冲突且无法仲裁
   - 系统时间/时区异常
   - 所有 calendar/provider fallback 都失败
8. API 必须明确输出：
   - `overall_source_mode`
   - `functional_live`
   - `blocked`
   - `disabled_capabilities`
   - `confidence_note`
9. UI 必须把 `partial_live` 显示为可运行态，例如：
   - `partial live · functional`
   - 不使用错误红色
   - 缺口显示在 source/audit 区域
10. 审计 HTML 必须区分：
    - functional pass
    - source completeness gap
    - true block

## 建议契约

```json
{
  "source_quality": {
    "overall_source_mode": "live|partial_live|fallback|blocked",
    "functional_live": true,
    "blocked": false,
    "disabled_capabilities": [
      "release_surprise_disabled",
      "actual_pending"
    ],
    "confidence_note": "partial_live is fully functional for monitoring; missing fields are capability-scoped, not system-blocking."
  }
}
```

## DoD

1. `/api/event-window/latest` 在 `partial_live` 时返回 `functional_live=true`。
2. `/api/event-window/latest` 在 `partial_live` 时 `blocked=false`。
3. `partial_live` 时 Event Window state machine 可继续输出 `calendar_monitor / pre_event_high_alert / sustained_drawdown_high_alert / unscheduled_shock_confirmed`。
4. `partial_live` 时 Shock Fast Lane 可继续触发 market shock。
5. `partial_live` 时 overlay 可继续输出 `watch_only / reduce_size / event_lock`。
6. `partial_live` 时 UI 不显示为 failed / blocked。
7. source audit HTML 显示 `partial_live = functional live`。
8. audit bundle 允许 `partial_live` 作为 PASS 条件。
9. 测试覆盖：
   - partial_live + actual_pending => functional pass
   - partial_live + consensus missing => release_surprise disabled only
   - blocked 条件出现 => true blocked
10. `npm run build` 通过。

## 后续关联

- P9：API 契约透传 `functional_live / blocked / confidence_note`
- P5：Event Watchtower UI source mode 样式与文案
- P7：审计 HTML 与 regression case
