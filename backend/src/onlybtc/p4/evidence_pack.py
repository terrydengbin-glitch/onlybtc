from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from onlybtc.algorithms.p3 import EVENT_MODULE_ID
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.constants import ANALYST_MODULES, SIGNED_EVENT_METRICS
from onlybtc.radars.registry import RADAR_MODULES


def build_p4_evidence_pack(
    radar_run_id: str | None = None,
    p3_run_id: str | None = None,
    pack_id: str | None = None,
    history_limit: int = 3,
    db: Database = database,
) -> dict[str, Any]:
    db.init_schema()
    radar_run_id = radar_run_id or _latest_complete_radar_run_id(db)
    if radar_run_id is None:
        raise RuntimeError("No complete P2 Radar run found")
    p3_run_id = p3_run_id or _latest_p3_event_run_id(db) or radar_run_id
    pack_id = pack_id or _generate_pack_id()
    module_to_analyst = _module_to_analyst()

    with db.session() as session:
        if _pack_exists(session, pack_id):
            raise RuntimeError(f"Evidence pack already exists: {pack_id}")
        module_rows = _module_outputs(session, radar_run_id)
        p3_event_rows = _p3_event_rows(session, p3_run_id)
        data_quality = _latest_data_quality(session)
        items = _radar_evidence_items(
            pack_id=pack_id,
            radar_run_id=radar_run_id,
            p3_run_id=p3_run_id,
            module_rows=module_rows,
            module_to_analyst=module_to_analyst,
        )
        items.extend(
            _p3_event_evidence_items(
                pack_id=pack_id,
                p3_run_id=p3_run_id,
                rows=p3_event_rows,
            )
        )
        items.extend(
            _analyst_history_items(
                session=session,
                pack_id=pack_id,
                radar_run_id=radar_run_id,
                p3_run_id=p3_run_id,
                history_limit=history_limit,
            )
        )
        session.add(
            schema.EvidencePack(
                pack_id=pack_id,
                run_id=p3_run_id,
                summary=_pack_summary(radar_run_id, p3_run_id, items),
                data_quality_score=float(data_quality.get("score", 1.0)),
            )
        )
        session.add_all(items)
        session.flush()
        _link_metric_values(session, items)
    return {
        "status": "completed",
        "pack_id": pack_id,
        "radar_run_id": radar_run_id,
        "p3_run_id": p3_run_id,
        "evidence_item_count": len(items),
        "radar_feature_evidence_count": sum(
            1 for item in items if item.data.get("source_layer") == "p2_radar"
        ),
        "p3_event_evidence_count": sum(
            1 for item in items if item.data.get("source_layer") == "p3_event"
        ),
        "analyst_history_evidence_count": sum(
            1 for item in items if item.data.get("source_layer") == "analyst_history"
        ),
        "radar_modules_consumed_count": len(module_rows),
        "radar_module_total": len(RADAR_MODULES),
        "signed_event_metrics_consumed_count": _signed_event_count(items),
    }


def _radar_evidence_items(
    pack_id: str,
    radar_run_id: str,
    p3_run_id: str,
    module_rows: dict[str, dict[str, Any]],
    module_to_analyst: dict[str, str],
) -> list[schema.EvidenceItem]:
    items: list[schema.EvidenceItem] = []
    sequence = 1
    for module in RADAR_MODULES:
        module_payload = module_rows.get(module.module_id, {})
        module_signal = str(module_payload.get("signal") or "neutral")
        module_strength = float(module_payload.get("strength") or 0.0)
        features = {
            str(feature.get("metric_id")): feature
            for feature in module_payload.get("features", [])
            if isinstance(feature, dict) and feature.get("metric_id")
        }
        for rule in module.metrics:
            feature = features.get(rule.metric_id) or _missing_feature(rule.metric_id)
            evidence_id = _evidence_id(pack_id, sequence)
            sequence += 1
            direction = str(feature.get("direction") or "neutral")
            strength = abs(float(feature.get("score") or 0.0))
            items.append(
                schema.EvidenceItem(
                    evidence_id=evidence_id,
                    pack_id=pack_id,
                    module_id=module.module_id,
                    claim=_radar_claim(module.module_id, rule.metric_id, feature),
                    direction=direction if direction else module_signal,
                    strength=strength if strength else module_strength,
                    data={
                        "source_layer": "p2_radar",
                        "assigned_analyst": module_to_analyst.get(module.module_id),
                        "controller_run_id": p3_run_id,
                        "p2_radar_run_id": radar_run_id,
                        "p3_run_id": p3_run_id,
                        "module_id": module.module_id,
                        "module_signal": module_signal,
                        "metric_id": rule.metric_id,
                        "source_id": feature.get("source_id"),
                        "source_run_id": feature.get("source_run_id"),
                        "feature_run_scope": feature.get("feature_run_scope"),
                        "role": feature.get("role"),
                        "evidence_tier": feature.get("evidence_tier"),
                        "affects_signal": feature.get("affects_signal"),
                        "affects_confidence": feature.get("affects_confidence"),
                        "affects_risk_flags": feature.get("affects_risk_flags"),
                        "value": feature.get("current"),
                        "quality_score": feature.get("quality_score"),
                        "available": feature.get("available"),
                        "fallback_reason": feature.get("fallback_reason"),
                        "payload": feature,
                    },
                )
            )
    return items


def _p3_event_evidence_items(
    pack_id: str,
    p3_run_id: str,
    rows: list[schema.FeatureValue],
) -> list[schema.EvidenceItem]:
    items: list[schema.EvidenceItem] = []
    for index, row in enumerate(rows, start=10_000):
        metadata = row.metadata_json or {}
        summary = metadata.get("event_summary", {})
        interpretation = summary.get("interpretation", {})
        items.append(
            schema.EvidenceItem(
                evidence_id=_evidence_id(pack_id, index),
                pack_id=pack_id,
                module_id=EVENT_MODULE_ID,
                claim=summary.get("headline")
                or f"{metadata.get('event_type')} event window evidence",
                direction=interpretation.get("risk_direction", "neutral_watch"),
                strength=0.7 if metadata.get("risk_lock") else 0.35,
                data={
                    "source_layer": "p3_event",
                    "assigned_analyst": "macro_event_analyst",
                    "controller_run_id": p3_run_id,
                    "p3_run_id": p3_run_id,
                    "module_id": EVENT_MODULE_ID,
                    "metric_id": metadata.get("metric_id"),
                    "source_id": metadata.get("source_id"),
                    "source_run_id": metadata.get("source_run_id"),
                    "event_type": metadata.get("event_type"),
                    "signed_days": metadata.get("signed_days"),
                    "event_phase": metadata.get("event_phase"),
                    "window": metadata.get("window"),
                    "window_action": metadata.get("window_action"),
                    "event_summary": summary,
                    "daily_watch": metadata.get("daily_watch"),
                    "publish_impact": interpretation.get("publish_impact"),
                    "source_trace": metadata.get("source_trace"),
                    "payload": metadata,
                },
            )
        )
    return items


def _analyst_history_items(
    session: Session,
    pack_id: str,
    radar_run_id: str,
    p3_run_id: str,
    history_limit: int,
) -> list[schema.EvidenceItem]:
    items: list[schema.EvidenceItem] = []
    for index, analyst in enumerate(ANALYST_MODULES, start=20_000):
        history = _analyst_vote_history(session, analyst, history_limit)
        latest = history[0] if history else {}
        items.append(
            schema.EvidenceItem(
                evidence_id=_evidence_id(pack_id, index),
                pack_id=pack_id,
                module_id="analyst_history",
                claim=_analyst_history_claim(analyst, history),
                direction=str(latest.get("vote") or "neutral"),
                strength=float(latest.get("confidence") or 0.0),
                data={
                    "source_layer": "analyst_history",
                    "assigned_analyst": analyst,
                    "controller_run_id": p3_run_id,
                    "p2_radar_run_id": radar_run_id,
                    "p3_run_id": p3_run_id,
                    "history_available": bool(history),
                    "history_limit": history_limit,
                    "history": history,
                },
            )
        )
    return items


def _analyst_vote_history(
    session: Session,
    analyst: str,
    history_limit: int,
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(schema.LlmModelVote, schema.LlmDebate)
        .join(schema.LlmDebate, schema.LlmDebate.debate_id == schema.LlmModelVote.debate_id)
        .where(schema.LlmModelVote.model_name == analyst)
        .order_by(schema.LlmModelVote.created_at.desc())
        .limit(history_limit)
    ).all()
    return [
        {
            "debate_id": vote.debate_id,
            "run_id": debate.run_id,
            "vote": vote.vote,
            "confidence": vote.confidence,
            "evidence_ids": vote.evidence_ids,
            "changed": vote.changed,
            "final_state": debate.final_state,
            "consensus_score": debate.consensus_score,
            "disagreement_level": debate.disagreement_level,
            "created_at": vote.created_at.isoformat(),
        }
        for vote, debate in rows
    ]


def _link_metric_values(session: Session, items: list[schema.EvidenceItem]) -> None:
    for item in items:
        metric_id = item.data.get("metric_id")
        source_run_id = item.data.get("source_run_id")
        source_id = item.data.get("source_id")
        if not metric_id:
            continue
        query = select(schema.MetricValue.id).where(schema.MetricValue.metric_id == metric_id)
        if source_run_id:
            query = query.where(schema.MetricValue.run_id == source_run_id)
        if source_id:
            query = query.where(schema.MetricValue.source_id == source_id)
        metric_value_id = session.scalar(query.order_by(schema.MetricValue.ts.desc()))
        if metric_value_id is not None:
            session.add(
                schema.EvidenceMetricLink(
                    evidence_id=item.evidence_id,
                    metric_value_id=int(metric_value_id),
                )
            )


def _latest_complete_radar_run_id(db: Database) -> str | None:
    with db.session() as session:
        rows = session.execute(
            select(
                schema.ModuleJsonOutput.run_id,
                func.count(func.distinct(schema.ModuleJsonOutput.module_id)).label("module_count"),
                func.max(schema.ModuleJsonOutput.created_at).label("latest_at"),
            )
            .group_by(schema.ModuleJsonOutput.run_id)
            .order_by(func.max(schema.ModuleJsonOutput.created_at).desc())
        ).all()
    for run_id, module_count, _latest_at in rows:
        if int(module_count) == len(RADAR_MODULES):
            return str(run_id)
    return str(rows[0][0]) if rows else None


def _latest_p3_event_run_id(db: Database) -> str | None:
    with db.session() as session:
        row = session.scalar(
            select(schema.FeatureValue.run_id)
            .where(schema.FeatureValue.module_id == EVENT_MODULE_ID)
            .order_by(schema.FeatureValue.created_at.desc())
        )
    return str(row) if row else None


def _module_outputs(session: Session, radar_run_id: str) -> dict[str, dict[str, Any]]:
    rows = session.scalars(
        select(schema.ModuleJsonOutput).where(schema.ModuleJsonOutput.run_id == radar_run_id)
    ).all()
    return {row.module_id: row.payload for row in rows}


def _p3_event_rows(session: Session, p3_run_id: str) -> list[schema.FeatureValue]:
    return session.scalars(
        select(schema.FeatureValue)
        .where(
            schema.FeatureValue.run_id == p3_run_id,
            schema.FeatureValue.module_id == EVENT_MODULE_ID,
        )
        .order_by(schema.FeatureValue.feature_id)
    ).all()


def _latest_data_quality(session: Session) -> dict[str, Any]:
    row = session.scalar(
        select(schema.DataQualitySnapshot).order_by(schema.DataQualitySnapshot.created_at.desc())
    )
    if row is None:
        return {"status": "unknown", "score": 1.0}
    return {"status": row.status, "score": row.score, "payload": row.payload}


def _pack_exists(session: Session, pack_id: str) -> bool:
    return (
        session.scalar(select(schema.EvidencePack.id).where(schema.EvidencePack.pack_id == pack_id))
        is not None
    )


def _module_to_analyst() -> dict[str, str]:
    return {
        module_id: analyst
        for analyst, module_ids in ANALYST_MODULES.items()
        for module_id in module_ids
    }


def _missing_feature(metric_id: str) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "available": False,
        "direction": "neutral",
        "score": 0.0,
        "feature_run_scope": "missing",
        "role": "primary_signal",
        "evidence_tier": "missing",
        "affects_signal": True,
        "affects_confidence": True,
        "affects_risk_flags": False,
    }


def _radar_claim(module_id: str, metric_id: str, feature: dict[str, Any]) -> str:
    if feature.get("available"):
        return (
            f"{module_id}.{metric_id} contributes as {feature.get('role')} "
            f"with direction={feature.get('direction')}."
        )
    return (
        f"{module_id}.{metric_id} is unavailable or provider-required; "
        "keep as coverage/quality evidence."
    )


def _analyst_history_claim(analyst: str, history: list[dict[str, Any]]) -> str:
    if not history:
        return f"{analyst} has no prior persisted vote; start with explicit cold-start context."
    latest = history[0]
    return (
        f"{analyst} previous vote was {latest.get('vote')} "
        f"with confidence={latest.get('confidence')}."
    )


def _pack_summary(
    radar_run_id: str,
    p3_run_id: str,
    items: list[schema.EvidenceItem],
) -> str:
    radar_count = sum(1 for item in items if item.data.get("source_layer") == "p2_radar")
    event_count = sum(1 for item in items if item.data.get("source_layer") == "p3_event")
    history_count = sum(
        1 for item in items if item.data.get("source_layer") == "analyst_history"
    )
    return (
        f"P4 evidence pack frozen from radar_run_id={radar_run_id}, "
        f"p3_run_id={p3_run_id}; radar_features={radar_count}, "
        f"p3_events={event_count}, analyst_history={history_count}."
    )


def _signed_event_count(items: list[schema.EvidenceItem]) -> int:
    return len(
        {
            str(item.data.get("metric_id"))
            for item in items
            if item.data.get("metric_id") in SIGNED_EVENT_METRICS
        }
    )


def _evidence_id(pack_id: str, sequence: int) -> str:
    return f"ev-{pack_id[-10:]}-{sequence:05d}"


def _generate_pack_id() -> str:
    return f"p4-pack-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
