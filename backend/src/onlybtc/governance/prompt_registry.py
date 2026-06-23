from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.prompts import (
    PROMPT_VERSION as P4_PROMPT_VERSION,
    build_adversarial_reviewer_system_prompt,
    build_analyst_article_prompt,
    build_analyst_prompt,
    build_cross_examiner_system_prompt,
    build_final_article_prompt,
    build_judge_system_prompt,
)
from onlybtc.p4.schemas import AgentEvidenceItem, AnalystHistory, AnalystInput
from onlybtc.p45 import llm_analyst_writer, llm_research_writer

SCHEMA_VERSION = "p7.c03.prompt_version_registry.v1"

REQUIRED_GUARDRAILS = (
    "evidence_only",
    "no_external_facts",
    "no_trading_advice",
    "json_output",
)


@dataclass(frozen=True)
class PromptRegistryEntry:
    prompt_id: str
    prompt_version: str
    content_hash: str
    surface: str
    owner_phase: str
    runtime_scope: str
    status: str
    system_prompt_preview: str
    user_prompt_preview: str
    output_schema: str
    guardrails: tuple[str, ...]
    source_module: str
    notes: tuple[str, ...] = ()


def build_prompt_registry_report() -> dict[str, Any]:
    entries = prompt_registry_entries()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "applied_to_production": False,
        "entry_count": len(entries),
        "entries": [asdict(entry) for entry in entries],
        "coverage": _coverage(entries),
        "guardrails": [
            "registry_only",
            "does_not_modify_prompt_text",
            "does_not_modify_llm_runtime",
            "does_not_modify_state_machine",
            "does_not_emit_trading_advice",
            "requires_p7_c08_before_production_apply",
        ],
    }


def prompt_registry_entries() -> list[PromptRegistryEntry]:
    p4_entries = _p4_legacy_entries()
    p45_entries = _p45_mainline_entries()
    return sorted([*p45_entries, *p4_entries], key=lambda item: item.prompt_id)


def prompt_content_hash(
    *,
    prompt_id: str,
    prompt_version: str,
    system_prompt: str,
    user_prompt: str,
    output_schema: str,
) -> str:
    payload = {
        "prompt_id": prompt_id,
        "prompt_version": prompt_version,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "output_schema": output_schema,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_prompt_registry(entries: list[PromptRegistryEntry] | None = None) -> dict[str, Any]:
    rows = entries or prompt_registry_entries()
    failures: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in rows:
        if entry.prompt_id in seen:
            failures.append({"prompt_id": entry.prompt_id, "reason": "duplicate_prompt_id"})
        seen.add(entry.prompt_id)
        if len(entry.content_hash) != 64:
            failures.append({"prompt_id": entry.prompt_id, "reason": "invalid_content_hash"})
        missing = sorted(set(REQUIRED_GUARDRAILS) - set(entry.guardrails))
        if missing:
            failures.append(
                {
                    "prompt_id": entry.prompt_id,
                    "reason": "missing_required_guardrails:" + ",".join(missing),
                }
            )
    mainline = {entry.prompt_id for entry in rows if entry.runtime_scope == "p45_mainline"}
    for prompt_id in {
        "p45.llm_research_writer.article",
        "p45.llm_analyst_writer.article",
    }:
        if prompt_id not in mainline:
            failures.append({"prompt_id": prompt_id, "reason": "missing_p45_mainline_entry"})
    return {
        "passed": not failures,
        "entry_count": len(rows),
        "failures": failures,
    }


def _p45_mainline_entries() -> list[PromptRegistryEntry]:
    research_system = llm_research_writer._system_prompt()
    research_user = llm_research_writer._user_prompt(_sample_p45_research_context())
    analyst_system = llm_analyst_writer._system_prompt()
    analyst_user = llm_analyst_writer._user_prompt(_sample_p45_analyst_context())
    return [
        _entry(
            prompt_id="p45.llm_research_writer.article",
            prompt_version="p45.llm_research_article.prompt.v1",
            surface="system+user",
            owner_phase="P4.5",
            runtime_scope="p45_mainline",
            status="active",
            system_prompt=research_system,
            user_prompt=research_user,
            output_schema="P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION:p45.llm_research_article.v1",
            guardrails=(
                *REQUIRED_GUARDRAILS,
                "covers_all_radar_modules",
                "unavailable_is_data_boundary",
                "internal_reference_only",
            ),
            source_module="onlybtc.p45.llm_research_writer",
            notes=("current_p45_mainline", "representative_context_hash"),
        ),
        _entry(
            prompt_id="p45.llm_analyst_writer.article",
            prompt_version="p45.llm_analyst_articles.prompt.v1",
            surface="system+user",
            owner_phase="P4.5",
            runtime_scope="p45_mainline",
            status="active",
            system_prompt=analyst_system,
            user_prompt=analyst_user,
            output_schema="P45_LLM_ANALYST_ARTICLES_SCHEMA_VERSION:p45.llm_analyst_articles.v1",
            guardrails=(
                *REQUIRED_GUARDRAILS,
                "slice_only",
                "covers_assigned_modules",
                "unavailable_is_data_boundary",
                "internal_reference_only",
            ),
            source_module="onlybtc.p45.llm_analyst_writer",
            notes=("current_p45_mainline", "representative_context_hash"),
        ),
    ]


def _p4_legacy_entries() -> list[PromptRegistryEntry]:
    analyst = build_analyst_prompt(_sample_p4_analyst_input())
    cross_exam = build_cross_examiner_system_prompt()
    judge = build_judge_system_prompt()
    adversarial = build_adversarial_reviewer_system_prompt()
    analyst_article = build_analyst_article_prompt(
        "macro_event_analyst",
        _sample_p4_article_context(),
        ["ev-sample-1"],
    )
    final_article = build_final_article_prompt(_sample_p4_article_context(), ["ev-sample-1"])
    bundles = [
        ("p4.analyst_agent.independent_review", analyst, "AnalystOutput"),
        ("p4.cross_examiner.challenge", cross_exam, "CrossExamChallenge"),
        ("p4.judge.synthesis", judge, "JudgeSynthesis"),
        ("p4.adversarial_reviewer.review", adversarial, "AdversarialReview"),
        ("p4.article_writer.analyst_article", analyst_article, "AnalystReadableArticle"),
        ("p4.article_writer.final_observation", final_article, "FinalObservationArticle"),
    ]
    return [
        _entry(
            prompt_id=prompt_id,
            prompt_version=P4_PROMPT_VERSION,
            surface="system+user",
            owner_phase="P4",
            runtime_scope="legacy_compat",
            status="legacy_compat",
            system_prompt=bundle.system_prompt,
            user_prompt=bundle.user_prompt,
            output_schema=schema_name,
            guardrails=(
                *REQUIRED_GUARDRAILS,
                "hard_constraints_override_llm",
                "state_machine_boundary",
                "legacy_compat",
            ),
            source_module="onlybtc.p4.prompts",
            notes=("legacy_reference", "not_new_production_mainline"),
        )
        for prompt_id, bundle, schema_name in bundles
    ]


def _entry(
    *,
    prompt_id: str,
    prompt_version: str,
    surface: str,
    owner_phase: str,
    runtime_scope: str,
    status: str,
    system_prompt: str,
    user_prompt: str,
    output_schema: str,
    guardrails: tuple[str, ...],
    source_module: str,
    notes: tuple[str, ...] = (),
) -> PromptRegistryEntry:
    return PromptRegistryEntry(
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        content_hash=prompt_content_hash(
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
        ),
        surface=surface,
        owner_phase=owner_phase,
        runtime_scope=runtime_scope,
        status=status,
        system_prompt_preview=_preview(system_prompt),
        user_prompt_preview=_preview(user_prompt),
        output_schema=output_schema,
        guardrails=tuple(dict.fromkeys(guardrails)),
        source_module=source_module,
        notes=notes,
    )


def _coverage(entries: list[PromptRegistryEntry]) -> dict[str, Any]:
    validation = validate_prompt_registry(entries)
    return {
        "validation_passed": validation["passed"],
        "failures": validation["failures"],
        "by_runtime_scope": _count_by(entries, "runtime_scope"),
        "by_owner_phase": _count_by(entries, "owner_phase"),
        "p45_mainline_prompt_ids": sorted(
            entry.prompt_id for entry in entries if entry.runtime_scope == "p45_mainline"
        ),
        "legacy_compat_prompt_ids": sorted(
            entry.prompt_id for entry in entries if entry.runtime_scope == "legacy_compat"
        ),
    }


def _count_by(entries: list[PromptRegistryEntry], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(getattr(entry, key))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _preview(value: str, limit: int = 420) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _sample_p4_analyst_input() -> AnalystInput:
    return AnalystInput(
        pack_id="prompt-registry-pack",
        controller_run_id="prompt-registry-controller",
        p2_radar_run_id="prompt-registry-radar",
        p3_run_id="prompt-registry-p3",
        analyst_id="macro_event_analyst",
        assigned_modules=list(ANALYST_MODULES["macro_event_analyst"]),
        analyst_history=AnalystHistory(history_available=False, history=[]),
        evidence_items=[
            AgentEvidenceItem(
                evidence_id="ev-sample-1",
                source_layer="p2_radar",
                module_id="macro_radar",
                metric_id="sample_metric",
                role="primary_signal",
                quality_score=0.9,
                affects_signal=True,
                affects_confidence=True,
                affects_risk_flags=False,
            )
        ],
    )


def _sample_p4_article_context() -> dict[str, Any]:
    return {
        "run_mode": "mock",
        "final_controller": {
            "publish_allowed": False,
            "blocked_by": ["prompt_registry_sample"],
        },
        "all_evidence": [
            {
                "evidence_id": "ev-sample-1",
                "metric_id": "sample_metric",
                "source_id": "sample_source",
                "value": 1,
                "quality_score": 0.9,
            }
        ],
        "full_evidence_index": ["ev-sample-1"],
    }


def _sample_p45_research_context() -> dict[str, Any]:
    return {
        "lineage": {
            "collect_run_id": "collect-sample",
            "p2_radar_run_id": "radar-sample",
            "p3_run_id": "p3-sample",
            "pack_id": "pack-sample",
            "final_run_id": "final-sample",
        },
        "final_baseline": {"core_view": "neutral", "direction_counts": {}},
        "analyst_articles": [],
        "radar_modules": [
            {
                "radar_module": "macro_radar",
                "module_score": 0,
                "module_direction": "neutral",
                "module_explanation": "sample",
            }
        ],
        "metric_evidence": [
            {
                "evidence_id": "ev-sample-1",
                "metric_id": "sample_metric",
                "metric_score": 0,
                "score_bucket": "zero",
                "value": 1,
            }
        ],
        "summary": {
            "analyst_count": 0,
            "radar_module_count": 1,
            "metric_evidence_count": 1,
            "positive": 0,
            "negative": 0,
            "zero": 1,
            "unavailable": 0,
        },
    }


def _sample_p45_analyst_context() -> dict[str, Any]:
    return {
        "analyst_id": "macro_event_analyst",
        "analyst_name": "宏观与事件分析师",
        "pack_id": "pack-sample",
        "p3_run_id": "p3-sample",
        "radar_modules": [
            {
                "radar_module": "macro_radar",
                "module_score": 0,
                "module_direction": "neutral",
                "module_explanation": "sample",
            }
        ],
        "metric_evidence": [
            {
                "evidence_id": "ev-sample-1",
                "metric_id": "sample_metric",
                "metric_score": 0,
                "score_bucket": "zero",
                "value": 1,
            }
        ],
        "summary": {
            "module_count": 1,
            "metric_evidence_count": 1,
            "positive": 0,
            "negative": 0,
            "zero": 1,
            "unavailable": 0,
        },
    }
