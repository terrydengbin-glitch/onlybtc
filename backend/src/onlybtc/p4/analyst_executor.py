from __future__ import annotations

from statistics import mean
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.agent_runtime import AgentRuntimeAdapter, RuntimeResult
from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.prompts import build_analyst_prompt
from onlybtc.p4.schemas import (
    AgentEvidenceItem,
    AnalystHistory,
    AnalystHistoryEntry,
    AnalystInput,
    AnalystOutput,
    GlobalContext,
)

RuntimeMode = Literal["mock", "llm"]


def run_analyst_agents(
    pack_id: str | None = None,
    debate_id: str | None = None,
    runtime_mode: RuntimeMode = "mock",
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    adapter = AgentRuntimeAdapter()
    with db.session() as session:
        pack = _load_pack(session, pack_id)
        evidence_items = _pack_evidence_items(session, pack.pack_id)
        debate_id = debate_id or _generate_debate_id()
        if _debate_exists(session, debate_id):
            raise RuntimeError(f"LLM debate already exists: {debate_id}")
        analyst_results: list[RuntimeResult] = []
        analyst_inputs: list[AnalystInput] = []
        for analyst_id in ANALYST_MODULES:
            analyst_input = _build_analyst_input(pack, evidence_items, analyst_id)
            prompt = build_analyst_prompt(analyst_input)
            if runtime_mode == "mock":
                runtime_result = adapter.run_mock(prompt, AnalystOutput)
            elif runtime_mode == "llm":
                runtime_result = adapter.run_llm_or_mock(
                    prompt,
                    AnalystOutput,
                    fallback_output=adapter.run_mock(prompt, AnalystOutput).structured_output or {},
                )
            else:
                raise ValueError(f"Unsupported runtime_mode: {runtime_mode}")
            analyst_inputs.append(analyst_input)
            analyst_results.append(runtime_result)

        _persist_debate(session, debate_id, pack, analyst_results)
        _persist_round(session, debate_id, pack, analyst_results)
        _persist_votes(session, debate_id, analyst_results)

    succeeded = sum(1 for result in analyst_results if result.succeeded)
    return {
        "status": "completed" if succeeded == len(ANALYST_MODULES) else "completed_with_errors",
        "pack_id": pack.pack_id,
        "debate_id": debate_id,
        "run_id": pack.run_id,
        "runtime_mode": runtime_mode,
        "analyst_count": len(ANALYST_MODULES),
        "succeeded_count": succeeded,
        "failed_count": len(ANALYST_MODULES) - succeeded,
        "votes_written_count": succeeded,
        "analyst_inputs": [
            {
                "analyst_id": analyst_input.analyst_id,
                "assigned_modules": analyst_input.assigned_modules,
                "evidence_count": len(analyst_input.evidence_items),
                "history_available": analyst_input.analyst_history.history_available,
            }
            for analyst_input in analyst_inputs
        ],
        "runtime_results": [result.model_dump(mode="json") for result in analyst_results],
    }


def _load_pack(session, pack_id: str | None) -> schema.EvidencePack:
    if pack_id:
        pack = session.scalar(
            select(schema.EvidencePack).where(schema.EvidencePack.pack_id == pack_id)
        )
    else:
        pack = session.scalar(
            select(schema.EvidencePack).order_by(schema.EvidencePack.created_at.desc())
        )
    if pack is None:
        raise RuntimeError("No P4 evidence pack found")
    return pack


def _pack_evidence_items(session, pack_id: str) -> list[schema.EvidenceItem]:
    return session.scalars(
        select(schema.EvidenceItem)
        .where(schema.EvidenceItem.pack_id == pack_id)
        .order_by(schema.EvidenceItem.evidence_id)
    ).all()


def _build_analyst_input(
    pack: schema.EvidencePack,
    items: list[schema.EvidenceItem],
    analyst_id: str,
) -> AnalystInput:
    assigned = ANALYST_MODULES[analyst_id]
    selected_items = [
        item
        for item in items
        if item.data.get("source_layer") != "analyst_history"
        and item.data.get("assigned_analyst") == analyst_id
    ]
    history_item = next(
        (
            item
            for item in items
            if item.data.get("source_layer") == "analyst_history"
            and item.data.get("assigned_analyst") == analyst_id
        ),
        None,
    )
    return AnalystInput(
        pack_id=pack.pack_id,
        controller_run_id=str(pack.run_id),
        p2_radar_run_id=_first_data_value(items, "p2_radar_run_id") or str(pack.run_id),
        p3_run_id=_first_data_value(items, "p3_run_id") or str(pack.run_id),
        analyst_id=analyst_id,  # type: ignore[arg-type]
        assigned_modules=list(assigned),
        global_context=GlobalContext(
            data_quality_summary={
                "pack_data_quality_score": pack.data_quality_score,
                "pack_summary": pack.summary,
            }
        ),
        evidence_items=[_to_agent_evidence_item(item) for item in selected_items],
        analyst_history=_to_analyst_history(history_item),
    )


def _to_agent_evidence_item(item: schema.EvidenceItem) -> AgentEvidenceItem:
    data = item.data or {}
    return AgentEvidenceItem(
        evidence_id=item.evidence_id,
        source_layer=str(data.get("source_layer") or "unknown"),
        module_id=str(data.get("module_id") or item.module_id),
        metric_id=data.get("metric_id"),
        source_id=data.get("source_id"),
        source_run_id=data.get("source_run_id"),
        role=data.get("role"),
        value=data.get("value"),
        quality_score=data.get("quality_score"),
        affects_signal=data.get("affects_signal"),
        affects_confidence=data.get("affects_confidence"),
        affects_risk_flags=data.get("affects_risk_flags"),
        payload=data.get("payload") or {},
    )


def _to_analyst_history(item: schema.EvidenceItem | None) -> AnalystHistory:
    if item is None:
        return AnalystHistory(history_available=False, history=[])
    data = item.data or {}
    history = [
        AnalystHistoryEntry(
            debate_id=str(entry["debate_id"]),
            run_id=str(entry["run_id"]),
            vote=str(entry["vote"]),
            confidence=float(entry["confidence"]),
            evidence_ids=list(entry.get("evidence_ids") or []),
            changed=bool(entry.get("changed")),
            final_state=entry.get("final_state"),
            consensus_score=entry.get("consensus_score"),
            disagreement_level=entry.get("disagreement_level"),
            created_at=entry.get("created_at"),
        )
        for entry in data.get("history", [])
    ]
    return AnalystHistory(
        history_available=bool(data.get("history_available")),
        history_limit=int(data.get("history_limit") or 3),
        history=history,
    )


def _first_data_value(items: list[schema.EvidenceItem], key: str) -> str | None:
    for item in items:
        value = (item.data or {}).get(key)
        if value:
            return str(value)
    return None


def _persist_debate(
    session,
    debate_id: str,
    pack: schema.EvidencePack,
    results: list[RuntimeResult],
) -> None:
    confidence_values = [
        float(result.structured_output["confidence"])
        for result in results
        if result.succeeded and result.structured_output
    ]
    consensus_score = mean(confidence_values) if confidence_values else 0.0
    votes = {
        str(result.structured_output["vote"])
        for result in results
        if result.succeeded and result.structured_output
    }
    session.add(
        schema.LlmDebate(
            debate_id=debate_id,
            run_id=str(pack.run_id),
            consensus_score=consensus_score,
            disagreement_level=_disagreement_level(votes, confidence_values),
            final_state="analyst_independent_review",
            publish_allowed=False,
        )
    )


def _persist_round(
    session,
    debate_id: str,
    pack: schema.EvidencePack,
    results: list[RuntimeResult],
) -> None:
    summary = {
        "pack_id": pack.pack_id,
        "round_type": "analyst_independent_review",
        "results": [
            {
                "agent_name": result.agent_name,
                "succeeded": result.succeeded,
                "model_provider": result.model_provider,
                "model_name": result.model_name,
                "agent_run_id": result.agent_run_id,
                "trace_id": result.trace_id,
                "prompt_version": result.prompt_version,
                "schema_version": result.schema_version,
                "guardrails": [item.model_dump(mode="json") for item in result.guardrail_results],
                "error": result.error,
                "token_usage": result.token_usage,
                "fallback_used": result.fallback_used,
                "fallback_reason": result.fallback_reason,
            }
            for result in results
        ],
    }
    session.add(
        schema.LlmRound(
            debate_id=debate_id,
            round_number=1,
            round_type="analyst_independent_review",
            summary=str(summary),
        )
    )


def _persist_votes(session, debate_id: str, results: list[RuntimeResult]) -> None:
    for result in results:
        if not result.succeeded or result.structured_output is None:
            continue
        output = AnalystOutput.model_validate(result.structured_output)
        evidence_ids = sorted(
            {
                evidence_id
                for claim in [*output.key_claims, *output.conflicting_evidence]
                for evidence_id in claim.evidence_ids
            }
        )
        session.add(
            schema.LlmModelVote(
                debate_id=debate_id,
                model_name=output.analyst_id,
                vote=output.vote,
                confidence=output.confidence,
                evidence_ids=evidence_ids,
                changed=output.history_delta.changed,
            )
        )


def _debate_exists(session, debate_id: str) -> bool:
    return (
        session.scalar(select(schema.LlmDebate.id).where(schema.LlmDebate.debate_id == debate_id))
        is not None
    )


def _disagreement_level(votes: set[str], confidence_values: list[float]) -> str:
    if len(votes) >= 3:
        return "high"
    if len(votes) == 2:
        return "medium"
    if confidence_values and mean(confidence_values) < 0.55:
        return "medium"
    return "low"


def _generate_debate_id() -> str:
    return f"debate-{uuid4().hex[:12]}"
