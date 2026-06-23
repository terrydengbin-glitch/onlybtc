from __future__ import annotations

from typing import Any

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
        "crypto_breadth",
    ),
    "microstructure_analyst": (
        "kline_orderflow",
        "derivatives_crowding",
        "trade_structure_flow",
        "options_volatility",
    ),
    "onchain_structure_analyst": (
        "btc_total_state",
        "btc_adoption",
        "onchain_valuation",
    ),
}

P45_UPSTREAM_CONTRACTS: dict[str, tuple[str, ...]] = {
    "p1": (
        "collect_run_id",
        "metric_values",
        "source_health",
        "freshness_status",
        "business_recency_status",
    ),
    "p2": (
        "p2_radar_run_id",
        "radar_module",
        "module_json_outputs",
        "radar_outputs",
    ),
    "p3": (
        "p3_run_id",
        "p3_scored_metric_evidence",
        "p3_scored_radar_module",
        "semantic_rule_id",
        "event_window_evidence",
        "invalidation_events",
    ),
    "p8": (
        "sqlite_lineage",
        "feature_values",
        "module_json_outputs",
        "html_audit_artifacts",
    ),
    "p0": (
        "path_resolver",
        "cli_entrypoint",
        "configuration",
        "logging",
    ),
}

P45_OUTPUTS: tuple[str, ...] = (
    "p45_analyst_evidence_pack",
    "p45_analyst_articles",
    "p45_final_research_article",
    "p45_html_report",
)

LEGACY_P4_COMPONENTS: tuple[str, ...] = (
    "agent_runtime",
    "cross_exam",
    "cross_exam_revision",
    "judge_synthesis",
    "adversarial_review",
    "final_controller_publish_gate",
)


def phase_boundary() -> dict[str, Any]:
    return {
        "phase": "P4.5",
        "name": "Radar Scored Analyst Writer",
        "status": "active_build",
        "upstream_contracts": P45_UPSTREAM_CONTRACTS,
        "analyst_modules": ANALYST_MODULES,
        "outputs": P45_OUTPUTS,
        "legacy_p4_components_not_used": LEGACY_P4_COMPONENTS,
        "rules": {
            "does_not_recompute_scores": True,
            "does_not_use_agent_debate": True,
            "does_not_use_judge_or_adversarial_review": True,
            "must_reference_evidence_id": True,
            "must_preserve_run_lineage": True,
        },
    }
