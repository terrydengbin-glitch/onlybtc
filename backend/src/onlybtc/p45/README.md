# P4.5 Radar Scored Analyst Writer

P4.5 is the lightweight research-writing layer between P3 and P5.

It consumes P3 scored evidence and writes:

- 4 analyst comments.
- 1 final Chinese research article.
- A human-readable HTML report with an evidence appendix.

P4.5 does not use the legacy P4 Agent/CrossExam/Judge/Adversarial Review chain.
Legacy P4 remains available only for historical review, debugging, and manual
comparison until P4.5 is fully accepted.

## Upstream Contracts

- P0: path resolver, configuration, logging, CLI conventions.
- P8: SQLite tables and run lineage persistence.
- P1: source health, freshness, business recency, collect run id.
- P2: Radar module outputs and module JSON.
- P3: scored metric evidence, scored radar module, semantic rules, events,
  invalidations.

## Analyst Split

- `macro_event_analyst`: macro, treasury/credit, Asia risk, event policy.
- `liquidity_flow_analyst`: dollar liquidity, ETF/fund flow, crypto breadth.
- `microstructure_analyst`: K-line/orderflow, derivatives, trade structure,
  options volatility.
- `onchain_structure_analyst`: BTC total state, adoption, on-chain valuation.
