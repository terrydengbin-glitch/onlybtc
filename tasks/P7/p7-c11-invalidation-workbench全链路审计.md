# P7-C11 Invalidation Workbench 全链路审计

状态：DONE

## 目标

对 `Invalidation Workbench v2` 进行严格全链路审计，确认它真正作为 BTC Cockpit 的证伪引擎工作，而不是把旧规则列表换皮。

## 审计范围

```text
P4.5:
  invalidation_workbench generator
  btc_trend_cockpit 输入消费
  module evidence matrix
  BTC response / residual gates

P8:
  SQLite final payload persistence
  history replay consistency

P9:
  /api/p45/invalidation/latest
  history / latest passthrough

P5:
  Workbench v2 前端展示
  fallback behavior

业务链条:
  14 radar modules -> BTC cockpit -> Workbench validation
```

## 审计重点

1. 缺 BTC response / residual 时不允许 `triggered`。
2. 单一 module 不允许触发 confirmed / refuted。
3. pressure 高但 BTC 不跌时不能直接 refuted bullish 或 confirmed bearish。
4. support 高但 BTC 不涨时不能直接 confirmed bullish。
5. neutral / watch_only 只输出 break-neutral scenarios，不输出错误的多空反证。
6. liquidation / funding / ETF / macro 不能单因子裁决。
7. data quality blocking 时 Workbench 必须 blocked。
8. latest 和 history replay 返回同一份持久化 payload。

## 验证命令

```text
backend targeted pytest
P4.5 workbench contract tests
P8 persistence / replay tests
P9 API tests
P5 dashboard contract tests
npm run build
run once
```

## 交付物

```text
reports/p7-c11-invalidation-workbench-full-chain-audit.md
reports/p7-c11-invalidation-workbench-full-chain-audit.json
```

## DoD

1. 审计报告给出 PASS / FAIL。
2. 抽样 latest final payload，确认 `invalidation_workbench.schema_version = p45.invalidation_workbench.v2`。
3. 确认 `validation_state` 与 `btc_trend_cockpit` 当前 thesis 一致。
4. 确认 `triggered_rules` 均有 BTC response gate 与 residual gate。
5. 确认 `module_evidence_matrix` 覆盖 14 个 radar modules。
6. 确认 replay 不被当前规则重算污染。
7. 所有 targeted tests / build / contract validation 通过。
