# P1-C68 / Event Window v3.2 Atlanta Fed Market Probability Tracker Connector

## 状�?
DONE

## Phase

P1 数据源接入与采集�?
## 背景

CME FedWatch 不可用时，系统当前会�?ZQ futures + EFFR 自算 proxy。Atlanta Fed Market Probability Tracker �?Fed 体系内的研究工具，可提供基于 SOFR options 的市场隐含分布，用于 hawkish/dovish repricing 的交叉验证�?
## 目标

接入 Atlanta Fed Market Probability Tracker，作�?FedWatch 替代路径中的 research-tool source�?
```text
CME FedWatch official_market_implied
-> Atlanta Fed MPT fed_research_tool
-> ZQ futures proxy market_implied_proxy
-> prediction market odds
```

## 输出契约

```json
{
  "provider": "atlanta_fed_market_probability_tracker",
  "source_tier": "fed_research_tool",
  "rate_range_probabilities": [],
  "nearest_contracts": [],
  "updated_at": "",
  "not_same_as_cme_fedwatch": true,
  "confidence": 0.86,
  "source_lineage": []
}
```

## 实现要求

```text
1. Atlanta Fed MPT 不能显示�?CME FedWatch�?2. 如果页面/API 结构不可稳定解析，必须降级为 unavailable，不强抓�?3. 输出应服�?hawkish_repricing_watch，不直接服务 official FOMC probability�?4. �?ZQ proxy / prediction market 方向一致时提高 confidence�?```

## DoD

- [ ] 可采集或明确检�?Atlanta Fed MPT �?latest/proxy 信息�?- [ ] 输出 `source_tier=fed_research_tool`�?- [ ] 输出 `not_same_as_cme_fedwatch=true`�?- [ ] 失败时不阻断 Event Window，只降低 Fed probability confidence�?- [ ] Source UI 能显�?Research Tool，而不�?Official FedWatch�?
## 依赖

- P1-C64
- P3-C58
- P5-C70

