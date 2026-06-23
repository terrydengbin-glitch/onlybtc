from __future__ import annotations

ANALYST_MODULES: dict[str, tuple[str, ...]] = {
    "macro_event_analyst": (
        "macro_radar",
        "treasury_credit",
        "asia_risk",
        "event_policy",
    ),
    "liquidity_flow_analyst": (
        "dollar_liquidity",
        "fund_flow",
        "btc_adoption",
    ),
    "leverage_microstructure_analyst": (
        "derivatives_crowding",
        "trade_structure_flow",
        "options_volatility",
    ),
    "onchain_market_structure_analyst": (
        "onchain_valuation",
        "crypto_breadth",
        "btc_total_state",
        "kline_orderflow",
    ),
}

ANALYST_IDS = tuple(ANALYST_MODULES)

SIGNED_EVENT_METRICS = {
    "cpi_signed_days",
    "fomc_signed_days",
    "pce_signed_days",
    "nfp_signed_days",
}
