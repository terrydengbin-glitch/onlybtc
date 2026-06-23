from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.schemas import (
    AdversarialReview,
    AnalystId,
    AnalystInput,
    AnalystOutput,
    AnalystReadableArticle,
    CrossExamChallenge,
    CrossExamRevision,
    FinalObservationArticle,
    JudgeSynthesis,
)

PROMPT_VERSION = "p4.agent_prompt.v1"

PROHIBITED_TRADING_TERMS = (
    "建议开仓",
    "建议平仓",
    "建议买入",
    "建议卖出",
    "止损设在",
    "止盈设在",
    "加仓到",
    "减仓到",
    "仓位比例",
    "open long",
    "open short",
    "close position",
    "stop loss",
    "take profit",
    "position sizing",
)

ALLOWED_SOURCE_LAYERS = (
    "p2_radar",
    "p3_event",
    "p3_anomaly",
    "p3_divergence",
    "p3_invalidation",
    "p1_quality",
    "analyst_history",
)

ROLE_PROFILES: dict[str, dict[str, str]] = {
    "macro_event_analyst": {
        "title": "Macro & Event Analyst",
        "focus": (
            "Macro releases, rates and credit pressure, Asia risk, policy event "
            "windows, P3 event windows, and publish constraints."
        ),
        "primary_questions": (
            "Do macro or event signals change the 1-5 day risk state? Are there "
            "pre-event, post-event, or data-quality limits that should reduce "
            "confidence?"
        ),
    },
    "liquidity_flow_analyst": {
        "title": "Liquidity & Flow Analyst",
        "focus": (
            "Dollar liquidity, ETF/fund flows, stablecoins, BTC adoption, flow "
            "persistence, and divergence."
        ),
        "primary_questions": (
            "Are liquidity and flows aligned? Is improvement or deterioration "
            "persistent? Is there a divergence between BTC price and flow evidence?"
        ),
    },
    "leverage_microstructure_analyst": {
        "title": "Leverage & Microstructure Analyst",
        "focus": (
            "Funding, open interest, basis, options volatility, liquidation, trade "
            "structure, and crowding."
        ),
        "primary_questions": (
            "Are derivatives and microstructure entering crowded or fragile states? "
            "Does risk come from directional crowding, volatility repricing, or flow "
            "breaks?"
        ),
    },
    "onchain_market_structure_analyst": {
        "title": "On-chain & Market Structure Analyst",
        "focus": (
            "On-chain valuation, market breadth, BTC total state, K-line/order-book "
            "and price structure."
        ),
        "primary_questions": (
            "Do on-chain valuation and market structure support the current BTC "
            "state? Are breadth, price structure, and total state aligned or in "
            "conflict?"
        ),
    },
}


class PromptBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_version: str = PROMPT_VERSION
    agent_id: str = Field(min_length=1)
    agent_role: Literal[
        "analyst",
        "cross_examiner",
        "cross_exam_revision",
        "judge",
        "adversarial_reviewer",
        "article_writer",
    ]
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)


def build_analyst_prompt(analyst_input: AnalystInput) -> PromptBundle:
    profile = ROLE_PROFILES[analyst_input.analyst_id]
    evidence_ids = [item.evidence_id for item in analyst_input.evidence_items]
    evidence_catalog = _evidence_catalog(analyst_input)
    input_payload = analyst_input.model_dump(mode="json")
    system_prompt = _analyst_system_prompt(analyst_input.analyst_id, profile)
    user_prompt = (
        "You must analyze the frozen onlyBTC Evidence Pack slice below.\n"
        "Return JSON only, matching the provided AnalystOutput schema.\n\n"
        f"pack_id: {analyst_input.pack_id}\n"
        f"controller_run_id: {analyst_input.controller_run_id}\n"
        f"p2_radar_run_id: {analyst_input.p2_radar_run_id}\n"
        f"p3_run_id: {analyst_input.p3_run_id}\n"
        f"analyst_id: {analyst_input.analyst_id}\n"
        f"assigned_modules: {', '.join(analyst_input.assigned_modules)}\n"
        f"allowed_source_layers: {', '.join(ALLOWED_SOURCE_LAYERS)}\n"
        f"evidence_ids: {', '.join(evidence_ids)}\n\n"
        "Evidence catalog:\n"
        f"{json.dumps(evidence_catalog, ensure_ascii=False, indent=2)}\n\n"
        "Full validated analyst input JSON:\n"
        f"{json.dumps(input_payload, ensure_ascii=False, indent=2)}\n\n"
        "Output JSON Schema:\n"
        f"{json.dumps(AnalystOutput.model_json_schema(), ensure_ascii=False, indent=2)}"
    )
    return PromptBundle(
        agent_id=analyst_input.analyst_id,
        agent_role="analyst",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        evidence_ids=evidence_ids,
        output_schema=AnalystOutput.model_json_schema(),
    )


def build_cross_examiner_system_prompt() -> PromptBundle:
    system_prompt = (
        "You are the onlyBTC Cross-examination Agent. Challenge analyst outputs only "
        "against frozen Evidence Pack evidence_ids, P3 invalidations, source conflicts, "
        "data quality, run_mode integrity, and history drift. Do not introduce external "
        "facts. Do not give trading advice. Produce JSON only."
    )
    return PromptBundle(
        agent_id="cross_examiner_agent",
        agent_role="cross_examiner",
        system_prompt=system_prompt,
        user_prompt=(
            "Given analyst outputs and evidence references, produce CrossExamChallenge "
            "JSON objects. Every challenge must cite evidence_ids."
        ),
        output_schema=CrossExamChallenge.model_json_schema(),
    )


def build_cross_exam_revision_prompt(agent_id: str, evidence_ids: list[str]) -> PromptBundle:
    system_prompt = (
        "You are an onlyBTC Analyst Agent responding to cross-examination. Answer only "
        "with CrossExamRevision JSON. Use frozen Evidence Pack evidence_ids only. "
        "State changed=true only when vote or confidence changes. If rejecting a "
        "challenge, provide evidence-backed rejected_points. Do not introduce external "
        "facts. Do not give trading advice."
    )
    return PromptBundle(
        agent_id=agent_id,
        agent_role="cross_exam_revision",
        system_prompt=system_prompt,
        user_prompt=(
            "Given a challenge targeting this analyst and the original vote, produce "
            "one CrossExamRevision JSON object."
        ),
        evidence_ids=evidence_ids,
        output_schema=CrossExamRevision.model_json_schema(),
    )


def build_judge_system_prompt() -> PromptBundle:
    system_prompt = (
        "You are the onlyBTC Judge Agent. Synthesize rule baseline, state machine "
        "constraints, four analyst outputs, and cross-examination revisions. Never "
        "simple-vote. Hard constraints override model opinions. Preserve minority "
        "objections and confidence discounts. Produce JSON only."
    )
    return PromptBundle(
        agent_id="judge_agent",
        agent_role="judge",
        system_prompt=system_prompt,
        user_prompt=(
            "Given baseline constraints, analyst outputs, challenges, and revisions, "
            "produce one JudgeSynthesis JSON object with evidence_ids."
        ),
        output_schema=JudgeSynthesis.model_json_schema(),
    )


def build_adversarial_reviewer_system_prompt() -> PromptBundle:
    system_prompt = (
        "You are the onlyBTC Adversarial Review Agent. Check whether the judge ignored "
        "P3 invalidations, run_mode integrity, data quality blocks, source conflicts, "
        "missing evidence, or trading-advice prohibitions. Produce JSON only."
    )
    return PromptBundle(
        agent_id="adversarial_reviewer_agent",
        agent_role="adversarial_reviewer",
        system_prompt=system_prompt,
        user_prompt=(
            "Given JudgeSynthesis and final controller draft, produce one "
            "AdversarialReview JSON object."
        ),
        output_schema=AdversarialReview.model_json_schema(),
    )


def build_analyst_article_prompt(
    analyst_id: AnalystId,
    article_context: dict[str, Any],
    evidence_ids: list[str],
) -> PromptBundle:
    system_prompt = _article_system_prompt(
        "You are the onlyBTC Chinese article writer for one analyst. Transform "
        "structured evidence, analyst conclusions, and history into a human-readable "
        "Chinese audit article."
    )
    user_prompt = (
        "Write a detailed Simplified Chinese research-style article for this analyst. "
        "Use only the JSON facts below. Cover every assigned Radar module and use "
        "article_context.all_evidence plus article_context.evidence_by_module, not only "
        "top_evidence. Cite allowed evidence_id values broadly, include metric values, "
        "source_id, quality_score, event/window fields, and history when present. "
        "Write like a market research analyst: lead with trend impulse, marginal "
        "change, sensitive signals, conflict weighting, scenario map, and invalidation "
        "conditions. Treat runtime, fallback, publish gates, and state constraints as "
        "confidence/audit context near the end; they must not dominate the opening "
        "paragraph. Professional market structure terms such as 仓位, 杠杆仓位, "
        "风险暴露, 拥挤度, funding, gamma, and delta are allowed when descriptive; "
        "direct trade instructions are not allowed. Fill trend_insight, "
        "marginal_change, sensitive_signals, early_warning_signals, conflict_weighting, "
        "scenario_map, invalidation_conditions, watch_horizon, confidence_explanation, "
        "audit_constraints_summary, headline, core_view, key_drivers, counter_evidence, "
        "changed_from_history, watch_items, confidence_rationale, sections, "
        "evidence_citations, and "
        "data_source_appendix. data_source_appendix must preserve the evidence list "
        "with evidence_id, metric_id, source_id, value, quality_score, and note. "
        "If evidence is repetitive, group it by module but still preserve its evidence_id "
        "in sections or citations. Return strict JSON matching "
        "AnalystReadableArticle. Do not output markdown.\n\n"
        f"analyst_id: {analyst_id}\n"
        f"allowed_evidence_ids: {', '.join(evidence_ids)}\n\n"
        "article_context:\n"
        f"{json.dumps(article_context, ensure_ascii=False, indent=2)}\n\n"
        "Output JSON Schema:\n"
        f"{json.dumps(AnalystReadableArticle.model_json_schema(), ensure_ascii=False, indent=2)}"
    )
    return PromptBundle(
        agent_id="article_writer_agent",
        agent_role="article_writer",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        evidence_ids=evidence_ids,
        output_schema=AnalystReadableArticle.model_json_schema(),
    )


def build_final_article_prompt(
    article_context: dict[str, Any],
    evidence_ids: list[str],
) -> PromptBundle:
    system_prompt = _article_system_prompt(
        "You are the onlyBTC Chinese final observation writer. Synthesize the final "
        "controller JSON, judge synthesis, adversarial review, state constraints, "
        "analyst articles, and history into a human-readable Chinese long-form audit."
    )
    user_prompt = (
        "Write the final detailed Simplified Chinese observation article. Use only the JSON "
        "facts below. Synthesize all analyst articles and full_evidence_index, cite "
        "allowed evidence_id values broadly, preserve state-machine and "
        "adversarial-review constraints, and return strict JSON matching "
        "FinalObservationArticle. Do not output markdown.\n"
        "Publish semantics are deterministic: if final_controller.blocked_by is "
        "non-empty, publish_scope must be described as observation-only/watch-only "
        "or dashboard-only, not as publish_candidate. Do not say publish is allowed "
        "when final_controller.publish_allowed is false.\n"
        "Separate data quality from production readiness: a high data_quality_score "
        "means the evidence rows are clean, but run_mode_integrity_invalidation, "
        "fallback, or live/mock mixing means the run is not production publishable.\n\n"
        "The article should be human-readable and research-like: explain the main "
        "drivers, opposing evidence, history continuity, challenge/revision effects, "
        "judge synthesis, adversarial review, and final gate. The first part must read "
        "as trend-sensitive research: explain what is changing, which signals are "
        "leading, which conflicts matter most, what would confirm or falsify the view, "
        "and what to watch over 24h/3d/7d. Keep publish gates, fallback, runtime, and "
        "DoD details in confidence/audit sections rather than the opening thesis. "
        "Professional market structure terms such as 仓位, 杠杆仓位, 风险暴露, 拥挤度, "
        "funding, gamma, and delta are allowed when descriptive; direct trade "
        "instructions are not allowed. Do not hide evidence "
        "coverage; if many ids exist, group them by module in sections. Fill "
        "trend_insight, marginal_change, sensitive_signals, early_warning_signals, "
        "conflict_weighting, scenario_map, invalidation_conditions, watch_horizon, "
        "confidence_explanation, audit_constraints_summary, executive_summary, "
        "market_state, driver_analysis, conflict_analysis, "
        "history_delta, event_watch, quality_and_runtime, final_observation, sections, "
        "evidence_citations, and data_source_appendix. data_source_appendix must retain "
        "the source list after the article with evidence_id, metric_id, source_id, "
        "value, quality_score, and note.\n\n"
        f"allowed_evidence_ids: {', '.join(evidence_ids)}\n\n"
        "article_context:\n"
        f"{json.dumps(article_context, ensure_ascii=False, indent=2)}\n\n"
        "Output JSON Schema:\n"
        f"{json.dumps(FinalObservationArticle.model_json_schema(), ensure_ascii=False, indent=2)}"
    )
    return PromptBundle(
        agent_id="article_writer_agent",
        agent_role="article_writer",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        evidence_ids=evidence_ids,
        output_schema=FinalObservationArticle.model_json_schema(),
    )


def _analyst_system_prompt(analyst_id: AnalystId, profile: dict[str, str]) -> str:
    assigned_modules = ", ".join(ANALYST_MODULES[analyst_id])
    prohibited = ", ".join(PROHIBITED_TRADING_TERMS)
    return (
        f"You are the onlyBTC {profile['title']} ({analyst_id}).\n"
        f"Professional focus: {profile['focus']}\n"
        f"Primary questions: {profile['primary_questions']}\n"
        f"Allowed Radar modules: {assigned_modules}.\n"
        "You may use only evidence provided in the current frozen Evidence Pack slice. "
        "Every key_claim and conflicting_evidence item must cite evidence_ids from the "
        "provided list. analyst_history is continuity context only; it cannot override "
        "current P2/P3 evidence. Treat data quality, source conflicts, business recency, "
        "fallback, run_mode integrity, P3 alerts, event windows, and invalidations as "
        "confidence and publish constraints.\n"
        "Do not invent external facts, do not use live market knowledge, and do not make "
        "the final BTC controller decision. If evidence is insufficient, output "
        "vote=insufficient_evidence or mixed and lower confidence.\n"
        f"Forbidden trading advice terms and concepts: {prohibited}.\n"
        "Return only valid JSON conforming to AnalystOutput. Do not include markdown."
    )


def _article_system_prompt(role_description: str) -> str:
    prohibited = ", ".join(PROHIBITED_TRADING_TERMS)
    return (
        f"{role_description}\n"
        "The article language must be Simplified Chinese. Output must be strict JSON "
        "only. Do not output markdown, code fences, or extra explanation.\n"
        "Use only facts supplied in the user JSON. Do not add external market facts.\n"
        "Every conclusion must cite at least one allowed evidence_id.\n"
        "When evidence data is available, mention metric_id, source_id, value, "
        "quality_score, or history references in the JSON fields.\n"
        "Preserve run_mode, state-machine, adversarial-review, data-quality, and "
        "publish-constraint limits.\n"
        "Do not produce trading advice or operational instructions. Forbidden terms "
        f"and concepts include: {prohibited}.\n"
        "The goal is to help a human reader understand the conclusion first, then "
        "trace it back to evidence_id values."
    )


def _evidence_catalog(analyst_input: AnalystInput) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": item.evidence_id,
            "source_layer": item.source_layer,
            "module_id": item.module_id,
            "metric_id": item.metric_id,
            "role": item.role,
            "quality_score": item.quality_score,
            "affects_signal": item.affects_signal,
            "affects_confidence": item.affects_confidence,
            "affects_risk_flags": item.affects_risk_flags,
        }
        for item in analyst_input.evidence_items
    ]
