# P7-C27 Radar Runtime 全链路审计

状态：TODO

## 背景

主链条升级为常驻分频 Radar Runtime 后，需要严格审计：不同频率是否真的生效、stale 是否被正确降级、BTC 主卡是否没有误用过期模块。

## 目标

输出 Radar Runtime 全链路审计报告，覆盖：

```text
P1 cadence profile
P3 freshness state machine
P8 runtime snapshots
P9 daemon / health / API
P4.5 cockpit aggregation
P5 UI visibility
```

## 审计重点

1. fast module 高频刷新是否实际发生。
2. confirmation/regime module 是否按低频刷新。
3. stale module 是否被排除 confirmed_signal。
4. manual full sweep 是否能强制所有模块刷新一轮。
5. daemon heartbeat / watchdog 是否能识别卡死。
6. BTC 主卡是否显示真实 freshness。
7. event_window 是否仍是独立 overlay。

## DoD

1. 生成 `reports/radar-runtime-audit-report.html`。
2. 审计 HTML 显示 module cadence matrix。
3. 审计 HTML 显示 latest cockpit consumed snapshots。
4. 审计 HTML 显示 stale/missing/blocked cases。
5. 若 stale module 被用于 confirmed_signal，审计 FAIL。
6. 若 daemon health stale 但 UI 未显示，审计 FAIL。
7. run once / daemon tick / replay 三条链路全部 PASS。
