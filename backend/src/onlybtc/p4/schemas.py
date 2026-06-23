from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from onlybtc.p4.constants import ANALYST_MODULES

AnalystId = Literal[
    "macro_event_analyst",
    "liquidity_flow_analyst",
    "leverage_microstructure_analyst",
    "onchain_market_structure_analyst",
]
Vote = Literal["bullish", "bearish", "neutral", "mixed", "risk_off", "insufficient_evidence"]
Direction = Literal["bullish", "bearish", "neutral", "mixed", "risk_off", "unknown"]
ChallengeType = Literal[
    "missing_evidence",
    "evidence_conflict",
    "data_quality",
    "overreach",
    "ignored_invalidation",
    "history_drift",
]
Severity = Literal["low", "medium", "high", "critical"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GlobalContext(StrictModel):
    run_mode_integrity: dict[str, Any] = Field(default_factory=dict)
    data_quality_summary: dict[str, Any] = Field(default_factory=dict)
    p3_alert_summary: dict[str, Any] = Field(default_factory=dict)
    state_machine_constraints: dict[str, Any] = Field(default_factory=dict)


class AgentEvidenceItem(StrictModel):
    evidence_id: str = Field(min_length=1)
    source_layer: str = Field(min_length=1)
    module_id: str = Field(min_length=1)
    metric_id: str | None = None
    source_id: str | None = None
    source_run_id: str | None = None
    role: str | None = None
    value: Any = None
    quality_score: float | None = Field(default=None, ge=0, le=1)
    affects_signal: bool | None = None
    affects_confidence: bool | None = None
    affects_risk_flags: bool | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AnalystHistoryEntry(StrictModel):
    debate_id: str
    run_id: str
    vote: str
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    changed: bool
    final_state: str | None = None
    consensus_score: float | None = Field(default=None, ge=0, le=1)
    disagreement_level: str | None = None
    created_at: datetime | str


class AnalystHistory(StrictModel):
    history_available: bool
    history_limit: int = Field(default=3, ge=0)
    history: list[AnalystHistoryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def availability_matches_history(self) -> AnalystHistory:
        if self.history_available and not self.history:
            raise ValueError("history_available=true requires at least one history entry")
        return self


class AnalystInput(StrictModel):
    schema_version: str = "p4.agent_input.v1"
    pack_id: str = Field(min_length=1)
    controller_run_id: str = Field(min_length=1)
    p2_radar_run_id: str = Field(min_length=1)
    p3_run_id: str = Field(min_length=1)
    analyst_id: AnalystId
    assigned_modules: list[str] = Field(min_length=1)
    global_context: GlobalContext = Field(default_factory=GlobalContext)
    evidence_items: list[AgentEvidenceItem] = Field(min_length=1)
    analyst_history: AnalystHistory

    @model_validator(mode="after")
    def assigned_modules_match_analyst(self) -> AnalystInput:
        expected = set(ANALYST_MODULES[self.analyst_id])
        actual = set(self.assigned_modules)
        if actual != expected:
            raise ValueError(
                f"assigned_modules for {self.analyst_id} must be {sorted(expected)}"
            )
        invalid_evidence = [
            item.evidence_id
            for item in self.evidence_items
            if item.source_layer == "p2_radar" and item.module_id not in expected
        ]
        if invalid_evidence:
            raise ValueError(
                "analyst input contains evidence outside assigned modules: "
                + ", ".join(invalid_evidence)
            )
        return self


class KeyClaim(StrictModel):
    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    direction: Direction = "unknown"
    strength: float = Field(ge=0, le=1)
    uncertainty: str | None = None


class HistoryDelta(StrictModel):
    changed: bool
    previous_vote: str | None = None
    reason: str | None = None


class AnalystOutput(StrictModel):
    schema_version: str = "p4.analyst_output.v1"
    agent_role: Literal["analyst"] = "analyst"
    analyst_id: AnalystId
    vote: Vote
    confidence: float = Field(ge=0, le=1)
    confidence_discount: float = Field(default=0, ge=0, le=1)
    time_horizon: str = "1-5d"
    key_claims: list[KeyClaim] = Field(default_factory=list)
    conflicting_evidence: list[KeyClaim] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    publish_constraints: list[str] = Field(default_factory=list)
    history_delta: HistoryDelta = Field(default_factory=lambda: HistoryDelta(changed=False))


class CrossExamChallenge(StrictModel):
    schema_version: str = "p4.cross_exam_challenge.v1"
    challenge_id: str = Field(min_length=1)
    from_agent: str = Field(min_length=1)
    to_agent: AnalystId
    challenge_type: ChallengeType
    claim_under_review: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    severity: Severity
    required_response: str = Field(min_length=1)


class CrossExamRevision(StrictModel):
    schema_version: str = "p4.cross_exam_revision.v1"
    challenge_id: str = Field(min_length=1)
    responding_agent: AnalystId
    changed: bool
    previous_vote: Vote
    revised_vote: Vote
    previous_confidence: float = Field(ge=0, le=1)
    revised_confidence: float = Field(ge=0, le=1)
    accepted_points: list[str] = Field(default_factory=list)
    rejected_points: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class JudgeSynthesis(StrictModel):
    schema_version: str = "p4.judge_synthesis.v1"
    judge_synthesis_id: str = Field(min_length=1)
    debate_id: str = Field(min_length=1)
    pack_id: str = Field(min_length=1)
    controller_run_id: str = Field(min_length=1)
    dominant_regime: str
    trend_state: str
    risk_state: str
    consensus_level: str
    disagreement_level: str
    accepted_claims: list[KeyClaim] = Field(default_factory=list)
    rejected_claims: list[KeyClaim] = Field(default_factory=list)
    minority_objections: list[KeyClaim] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    confidence_discount: float = Field(default=0, ge=0, le=1)
    blocked_by: list[str] = Field(default_factory=list)
    publish_allowed: bool
    evidence_ids: list[str] = Field(min_length=1)
    state_machine_constraints_applied: list[str] = Field(default_factory=list)


class AdversarialReview(StrictModel):
    schema_version: str = "p4.adversarial_review.v1"
    review_id: str = Field(min_length=1)
    judge_synthesis_id: str = Field(min_length=1)
    passed: bool
    publish_allowed: bool
    findings: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceCitation(StrictModel):
    evidence_id: str = Field(min_length=1)
    metric_id: str | None = None
    source_id: str | None = None
    value: Any = None
    quality_score: float | None = Field(default=None, ge=0, le=1)
    note: str = Field(min_length=1)


class ReadableArticleSection(StrictModel):
    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class AnalystReadableArticle(StrictModel):
    schema_version: str = "p4.analyst_readable_article.v1"
    analyst_id: AnalystId
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    trend_insight: str | None = None
    marginal_change: str | None = None
    sensitive_signals: list[str] = Field(default_factory=list)
    early_warning_signals: list[str] = Field(default_factory=list)
    conflict_weighting: str | None = None
    scenario_map: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    watch_horizon: list[str] = Field(default_factory=list)
    confidence_explanation: str | None = None
    audit_constraints_summary: str | None = None
    headline: str | None = None
    core_view: str | None = None
    key_drivers: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    changed_from_history: str | None = None
    watch_items: list[str] = Field(default_factory=list)
    confidence_rationale: str | None = None
    sections: list[ReadableArticleSection] = Field(min_length=1)
    evidence_citations: list[EvidenceCitation] = Field(min_length=1)
    data_source_appendix: list[EvidenceCitation] = Field(default_factory=list)
    history_references: list[str] = Field(default_factory=list)
    state_constraints: list[str] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)


class FinalObservationArticle(StrictModel):
    schema_version: str = "p4.final_observation_article.v1"
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    trend_insight: str | None = None
    marginal_change: str | None = None
    sensitive_signals: list[str] = Field(default_factory=list)
    early_warning_signals: list[str] = Field(default_factory=list)
    conflict_weighting: str | None = None
    scenario_map: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    watch_horizon: list[str] = Field(default_factory=list)
    confidence_explanation: str | None = None
    audit_constraints_summary: str | None = None
    executive_summary: str | None = None
    market_state: str | None = None
    driver_analysis: str | None = None
    conflict_analysis: str | None = None
    history_delta: str | None = None
    event_watch: str | None = None
    quality_and_runtime: str | None = None
    final_observation: str | None = None
    sections: list[ReadableArticleSection] = Field(min_length=1)
    evidence_citations: list[EvidenceCitation] = Field(min_length=1)
    data_source_appendix: list[EvidenceCitation] = Field(default_factory=list)
    analyst_article_titles: list[str] = Field(default_factory=list)
    history_references: list[str] = Field(default_factory=list)
    state_constraints: list[str] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    publish_constraints: list[str] = Field(default_factory=list)


class FinalControllerJson(StrictModel):
    schema_version: str = "p4.final_controller.v1"
    run_id: str = Field(min_length=1)
    evidence_pack_id: str = Field(min_length=1)
    debate_id: str = Field(min_length=1)
    judge_synthesis_id: str = Field(min_length=1)
    adversarial_review_id: str | None = None
    analyst_vote_ids: list[str] = Field(default_factory=list)
    challenge_ids: list[str] = Field(default_factory=list)
    revision_ids: list[str] = Field(default_factory=list)
    agent_runtime_trace_ids: list[str] = Field(default_factory=list)
    runtime_mode: str = "mock"
    llm_runtime_integrity: str = "not_evaluated"
    agent_runtime_failures: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reasons: list[str] = Field(default_factory=list)
    llm_budget_summary: dict[str, Any] = Field(default_factory=dict)
    revision_integrity: str = "not_evaluated"
    revision_round_count: int = 0
    unresolved_challenge_count: int = 0
    unresolved_high_challenge_count: int = 0
    revision_required_fixes: list[str] = Field(default_factory=list)
    adversarial_publish_gate_reason: str | None = None
    watch_only: bool = False
    dashboard_only: bool = False
    publish_scope: str = "blocked"
    publish_block_reason: str | None = None
    revised_vote_matrix_summary: dict[str, Any] = Field(default_factory=dict)
    dominant_regime: str | None = None
    consensus_level: str | None = None
    disagreement_level: str | None = None
    minority_objections: list[KeyClaim] = Field(default_factory=list)
    state_machine_constraints_applied: list[str] = Field(default_factory=list)
    publish_constraints: list[str] = Field(default_factory=list)
    trend_state: str
    risk_state: str
    dominant_drivers: list[str] = Field(default_factory=list)
    invalidation_watch: list[str] = Field(default_factory=list)
    observation_points: list[str] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    confidence_discount: float = Field(default=0, ge=0, le=1)
    publish_allowed: bool
    blocked_by: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
