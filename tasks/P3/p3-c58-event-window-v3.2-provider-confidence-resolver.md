# P3-C58 / Event Window v3.2 Provider Confidence Resolver

## 状�?
DONE

## Phase

P3 规则、状态机与信号治�?
## 背景

v3.2 会引�?official mirror、secondary calendar、secondary consensus、prediction market、fed research tool 等多�?provider。必须统一信任分层，避免非官方源被误用�?official fact�?
## 目标

新增 provider confidence resolver，把所有事件数据统一归一化为�?
```text
official
official_mirror
official_nowcast
fed_research_tool
secondary_consensus
secondary_calendar
prediction_market
market_implied_proxy
manual_override
missing
failed
```

## 默认权重

```json
{
  "official_api": 0.95,
  "official_html": 0.90,
  "official_mirror": 0.86,
  "official_nowcast": 0.86,
  "fed_research_tool": 0.84,
  "secondary_consensus": 0.78,
  "secondary_calendar": 0.76,
  "prediction_market_liquid": 0.70,
  "prediction_market_illiquid": 0.45,
  "market_implied_proxy": 0.65,
  "manual_override": 0.45,
  "missing": 0.0
}
```

## 裁决规则

```text
1. official actual 才能触发 final release_surprise�?2. secondary consensus 两源一致才输出 secondary_confirmed�?3. prediction market 只能触发 repricing_watch / high_alert�?4. manual_override 只能维持 calendar awareness，不能触�?surprise�?5. 非官方源可触�?watch/high alert，但不能触发 official fact confirmation�?6. source_conflict 时优先官方，非官方降级为 conflict evidence�?```

## 输出契约

```json
{
  "provider_confidence": {
    "calendar_confidence": 0,
    "consensus_confidence": 0,
    "actual_confidence": 0,
    "rate_probability_confidence": 0,
    "prediction_market_confidence": 0,
    "source_conflicts": [],
    "disabled_capabilities": []
  }
}
```

## DoD

- [ ] Provider resolver 覆盖 official / mirror / secondary / proxy / prediction / manual�?- [ ] official actual 缺失时禁�?final surprise�?- [ ] secondary consensus 不足两源时禁�?confirmed consensus�?- [ ] prediction market 低流动性自动降权�?- [ ] UI 能解释为什么某个源只能 watch，不�?final�?
## 依赖

- P1-C65
- P1-C66
- P1-C67
- P1-C68

