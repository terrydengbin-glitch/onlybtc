from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Signal = Literal["bullish", "bearish", "mixed", "neutral"]
MetricRole = Literal[
    "primary_signal",
    "supporting_context",
    "risk_context",
    "audit_context",
    "quality_context",
    "event_context",
    "macro_data_event",
    "fomc_policy_event",
    "fed_speech_event",
    "blackout_context",
    "price_state",
    "perp_state",
    "cycle_context",
    "aggressive_flow",
    "price_response",
    "price_context",
    "confirmation_factor",
    "structure_context",
    "volume_efficiency_context",
    "liquidation_event",
    "liquidity_context",
    "execution_friction",
    "derivatives_pricing_context",
    "positioning_sentiment",
    "top_trader_account_bias",
    "top_trader_position_bias",
    "positioning_context",
    "volatility_regime",
    "protection_demand",
    "tail_risk",
    "expiry_pressure",
    "pinning_structure",
    "btc_trend_anchor",
    "breadth_participation",
    "market_cap_diffusion",
    "btc_vs_alt_leadership",
    "sector_risk_appetite",
    "breadth_quality",
    "equity_beta",
    "rates_pressure",
    "dollar_pressure",
    "volatility_stress",
    "financial_stress",
    "commodity_context",
    "macro_impulse",
    "btc_relative_confirmation",
    "liquidity_level",
    "liquidity_impulse",
    "reserve_buffer",
    "liquidity_drain_pressure",
    "repo_funding_pressure",
    "btc_response_confirmation",
    "policy_rate_pressure",
    "real_yield_pressure",
    "duration_term_pressure",
    "curve_regime",
    "inflation_mix",
    "credit_stress",
    "composite_only",
    "context_only",
    "fast_flow_signal",
    "demand_momentum",
    "demand_persistence",
    "persistence_bonus",
    "pressure_warning",
    "demand_acceleration",
    "flow_reversal_context",
    "flow_shock_context",
    "liquidity_regime",
    "liquidity_buying_power",
    "supply_pressure_context",
    "confirmed_supply_signal",
    "btc_response_veto",
    "flow_data_quality",
    "valuation_regime",
    "profit_realization_context",
    "cost_basis_reaction",
    "realized_cap_impulse",
    "onchain_response_veto",
    "proxy_context",
    "miner_pressure_context",
    "whale_pressure_context",
    "trend_prior",
    "trend_acceptance",
    "oi_participation",
    "funding_basis",
    "positioning_skew",
    "liquidation_response",
    "squeeze_risk",
    "residual_confirmation",
]


@dataclass(frozen=True)
class RadarMetricRule:
    metric_id: str
    weight: float
    higher_is: Literal["bullish", "bearish", "mixed", "neutral"]
    change_sensitive: bool = True
    role: MetricRole = "primary_signal"
    affects_signal: bool = True
    affects_confidence: bool = True
    affects_risk_flags: bool = False
    driver_eligible: bool = True


@dataclass(frozen=True)
class RadarModule:
    module_id: str
    name: str
    metrics: tuple[RadarMetricRule, ...]
