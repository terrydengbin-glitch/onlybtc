# P7-C10 BTC Trend Cockpit 全链路审计与 DoD

状态：DONE

## 目标

对 `btc_trend_cockpit.v2` 进行严格全链路审计，确认它没有破坏已优化 radar modules，也没有把单因子风险误写成 BTC 最终方向。

## 审计范围

```text
P3:
  module_signal normalization

P4.5:
  btc_trend_cockpit builder
  multi-horizon state machine
  trend acceptance

P8:
  SQLite final payload persistence
  history replay

P9:
  dashboard / overview / history API passthrough

P5:
  Vue3 center BTC card rendering
  fallback behavior

Existing radar modules:
  ensure payloads are still passed through unchanged
```

## 审计重点

1. 中心卡不直接读 raw metric。
2. 单一 module 不触发 confirmed。
3. risk/pressure 不等于 bearish。
4. BTC response/residual 缺失时不允许 confirmed。
5. data quality blocking 时输出 blocked。
6. support 与 pressure 同高时输出 conflict。
7. latest 与 history replay cockpit 一致。
8. 前端 fallback 不影响旧 run。

## 必跑验证

```text
backend targeted pytest
P4.5 cockpit contract tests
P8 persistence/replay tests
P9 API tests
P5 dashboard contract tests
npm run build
run once
```

## 交付物

```text
reports/p7-c10-btc-trend-cockpit-full-chain-audit.md
reports/p7-c10-btc-trend-cockpit-full-chain-audit.json
```

## DoD

1. run once 产出 `btc_trend_cockpit.schema_version = p45.btc_trend_cockpit.v2`。
2. dashboard latest / overview latest / history replay 均可读取 cockpit。
3. 前端中心卡显示 cockpit 正常。
4. 单模块 confirmed 禁止规则测试通过。
5. pressure 高但 acceptance 低时最多 watch 的测试通过。
6. data quality blocking -> blocked 的测试通过。
7. 所有 targeted tests 和 build 通过。
8. 审计报告结论明确给出 PASS / FAIL 和残余风险。
