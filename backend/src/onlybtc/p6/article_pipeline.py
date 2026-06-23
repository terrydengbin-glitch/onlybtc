from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.final_writer import P45_FINAL_ARTICLE_MODULE_ID

P6_AUTO_ARTICLE_MODULE_ID = "p6_auto_article_snapshot"
P6_AUTO_ARTICLE_SCHEMA_VERSION = "p6.auto_article.v1"
P6_MANUAL_ARTICLE_SCHEMA_VERSION = "p6.manual_article.v1"
P6_ARTICLE_HISTORY_SCHEMA_VERSION = "p6.article_history.v1"
P6_ARTICLE_REPLAY_SCHEMA_VERSION = "p6.article_replay.v1"


def generate_auto_article_snapshot(
    *,
    final_run_id: str | None = None,
    db: Database = database,
) -> dict[str, Any]:
    final_payload = _load_final_payload(final_run_id=final_run_id, db=db)
    if final_payload is None:
        raise ValueError("P4.5 final payload not found")
    resolved_final_run_id = str(final_payload.get("final_run_id") or final_run_id or "")
    if not resolved_final_run_id:
        raise ValueError("P4.5 final payload missing final_run_id")

    existing = _load_existing_snapshot(resolved_final_run_id, db=db)
    if existing is not None:
        return existing

    snapshot = build_auto_article_snapshot(final_payload)
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id=str(snapshot["article_snapshot_id"]),
                module_id=P6_AUTO_ARTICLE_MODULE_ID,
                schema_version=P6_AUTO_ARTICLE_SCHEMA_VERSION,
                payload=snapshot,
            )
        )
    return snapshot


def build_auto_article_snapshot(final_payload: dict[str, Any]) -> dict[str, Any]:
    final_run_id = str(final_payload.get("final_run_id") or "")
    evidence = _valid_evidence(final_payload)
    citations = [_citation(item) for item in evidence[:12]]
    research = final_payload.get("research_article") or {}
    publish = final_payload.get("publish_article") or {}
    contract = final_payload.get("contract_validation") or {}
    data_quality = final_payload.get("data_quality") or {}
    title = (
        publish.get("title")
        or research.get("title")
        or f"BTC P4.5 research draft {final_run_id}".strip()
    )
    body = _article_body(final_payload, research, publish, citations)
    quality_gate = _quality_gate(
        final_payload=final_payload,
        body=body,
        citations=citations,
        contract=contract,
        data_quality=data_quality,
    )
    return {
        "schema_version": P6_AUTO_ARTICLE_SCHEMA_VERSION,
        "article_snapshot_id": f"p6article-{final_run_id}",
        "source_schema_version": final_payload.get("schema_version"),
        "created_at": datetime.now(UTC).isoformat(),
        "draft_status": "ready" if quality_gate["status"] == "passed" else "needs_review",
        "final_run_id": final_run_id,
        "pack_id": final_payload.get("pack_id"),
        "article_run_id": final_payload.get("article_run_id"),
        "title": str(title),
        "summary": _summary(final_payload, research, publish),
        "body": body,
        "evidence_citations": citations,
        "risk_disclosures": _risk_disclosures(final_payload),
        "quality_gate": quality_gate,
        "publish_boundary": {
            "auto_publish_allowed": False,
            "manual_review_required": True,
            "reason": "P6-C01 only creates deterministic draft snapshots; publication is P6-C02.",
            "forbidden_outputs": [
                "trade_advice",
                "position_size",
                "leverage",
                "stop_loss",
                "take_profit",
            ],
        },
        "run_lineage": _run_lineage(final_payload),
    }


def latest_auto_article_snapshot(db: Database = database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.module_id == P6_AUTO_ARTICLE_MODULE_ID)
            .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
            .limit(1)
        )
        return dict(row.payload or {}) if row else None


def manual_generate_article(
    *,
    final_run_id: str | None = None,
    requested_by: str = "local_api",
    db: Database = database,
) -> dict[str, Any]:
    snapshot = generate_auto_article_snapshot(final_run_id=final_run_id, db=db)
    return _manual_envelope(
        snapshot=snapshot,
        action="manual_generate",
        requested_by=requested_by,
    )


def latest_manual_article(db: Database = database) -> dict[str, Any] | None:
    snapshot = latest_auto_article_snapshot(db=db)
    if snapshot is None:
        return None
    return _manual_envelope(
        snapshot=snapshot,
        action="latest",
        requested_by="local_api",
    )


def get_manual_article(
    article_snapshot_id: str,
    *,
    db: Database = database,
) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(
                schema.ModuleJsonOutput.module_id == P6_AUTO_ARTICLE_MODULE_ID,
                schema.ModuleJsonOutput.run_id == article_snapshot_id,
            )
            .limit(1)
        )
    if row is None:
        return None
    return _manual_envelope(
        snapshot=dict(row.payload or {}),
        action="get",
        requested_by="local_api",
    )


def article_history(limit: int = 50, db: Database = database) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.ModuleJsonOutput)
            .where(schema.ModuleJsonOutput.module_id == P6_AUTO_ARTICLE_MODULE_ID)
            .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
            .limit(max(1, min(limit, 200)))
        ).all()

    items: list[dict[str, Any]] = []
    for row in rows:
        snapshot = dict(row.payload or {})
        quality_gate = snapshot.get("quality_gate") or {}
        items.append(
            {
                "article_snapshot_id": snapshot.get("article_snapshot_id") or row.run_id,
                "final_run_id": snapshot.get("final_run_id"),
                "pack_id": snapshot.get("pack_id"),
                "article_run_id": snapshot.get("article_run_id"),
                "created_at": snapshot.get("created_at") or row.created_at.isoformat(),
                "draft_status": snapshot.get("draft_status"),
                "title": snapshot.get("title"),
                "summary": snapshot.get("summary"),
                "quality_gate_status": quality_gate.get("status"),
                "citation_count": len(snapshot.get("evidence_citations") or []),
                "history_url": (
                    f"/api/p6/articles/replay/{snapshot.get('article_snapshot_id') or row.run_id}"
                ),
            }
        )

    return {
        "schema_version": P6_ARTICLE_HISTORY_SCHEMA_VERSION,
        "status": "ok",
        "items": items,
        "count": len(items),
        "history_mode": {
            "anchor": "article_snapshot_id",
            "read_only": True,
            "historical_payload_frozen": True,
            "uses_latest_runtime_state": False,
        },
    }


def replay_article_snapshot(
    article_snapshot_id: str,
    *,
    db: Database = database,
) -> dict[str, Any] | None:
    snapshot = _load_article_snapshot(article_snapshot_id, db=db)
    if snapshot is None:
        return None
    final_run_id = str(snapshot.get("final_run_id") or "")
    pack_id = str(snapshot.get("pack_id") or "")
    final_payload = _payload_by_run(P45_FINAL_ARTICLE_MODULE_ID, final_run_id, db=db) or {}
    pack_payload = _payload_by_run(P45_EVIDENCE_PACK_MODULE_ID, pack_id, db=db) or {}
    evidence_replay = _evidence_pack_replay(snapshot, final_payload, pack_payload)
    return {
        "schema_version": P6_ARTICLE_REPLAY_SCHEMA_VERSION,
        "status": "ok",
        "article_snapshot_id": snapshot.get("article_snapshot_id") or article_snapshot_id,
        "final_run_id": final_run_id or None,
        "pack_id": pack_id or None,
        "created_at": snapshot.get("created_at"),
        "draft_status": snapshot.get("draft_status"),
        "history_mode": {
            "anchor": "article_snapshot_id",
            "article_snapshot_id": snapshot.get("article_snapshot_id") or article_snapshot_id,
            "read_only": True,
            "historical_payload_frozen": True,
            "uses_latest_runtime_state": False,
        },
        "run_lineage": {
            **_run_lineage(final_payload),
            "article_snapshot_id": snapshot.get("article_snapshot_id") or article_snapshot_id,
            "final_run_id": final_run_id or final_payload.get("final_run_id"),
            "pack_id": pack_id or final_payload.get("pack_id"),
        },
        "article": snapshot,
        "final": final_payload,
        "pack": pack_payload,
        "evidence_pack_replay": evidence_replay,
        "replay_boundary": {
            "read_only": True,
            "source": "module_json_outputs",
            "frozen_by": ["article_snapshot_id", "final_run_id", "pack_id"],
            "auto_publish_allowed": False,
            "uses_latest_runtime_state": False,
        },
    }


def _load_final_payload(
    *,
    final_run_id: str | None,
    db: Database,
) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        query = select(schema.ModuleJsonOutput).where(
            schema.ModuleJsonOutput.module_id == P45_FINAL_ARTICLE_MODULE_ID
        )
        if final_run_id:
            query = query.where(schema.ModuleJsonOutput.run_id == final_run_id)
        row = session.scalar(
            query.order_by(
                schema.ModuleJsonOutput.created_at.desc(),
                schema.ModuleJsonOutput.id.desc(),
            ).limit(1)
        )
        return dict(row.payload or {}) if row else None


def _load_article_snapshot(article_snapshot_id: str, db: Database) -> dict[str, Any] | None:
    return _payload_by_run(P6_AUTO_ARTICLE_MODULE_ID, article_snapshot_id, db=db)


def _payload_by_run(module_id: str, run_id: str, db: Database) -> dict[str, Any] | None:
    if not run_id:
        return None
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(
                schema.ModuleJsonOutput.module_id == module_id,
                schema.ModuleJsonOutput.run_id == run_id,
            )
            .order_by(schema.ModuleJsonOutput.created_at.desc(), schema.ModuleJsonOutput.id.desc())
            .limit(1)
        )
        return dict(row.payload or {}) if row else None


def _manual_envelope(
    *,
    snapshot: dict[str, Any],
    action: str,
    requested_by: str,
) -> dict[str, Any]:
    return {
        "schema_version": P6_MANUAL_ARTICLE_SCHEMA_VERSION,
        "status": "ok",
        "action": action,
        "requested_by": requested_by,
        "article_snapshot_id": snapshot.get("article_snapshot_id"),
        "final_run_id": snapshot.get("final_run_id"),
        "draft_status": snapshot.get("draft_status"),
        "publication_status": "draft_only",
        "article": snapshot,
        "run_once_publication_strategy": {
            "run_once_auto_generates_draft": True,
            "auto_publish_allowed": False,
            "manual_review_required": True,
            "publication_status": "draft_only",
            "reason": "Run Once / Full Chain may prepare a P6 draft, but external publication is reserved for a later manual approval flow.",
        },
    }


def _load_existing_snapshot(final_run_id: str, db: Database) -> dict[str, Any] | None:
    db.init_schema()
    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput)
            .where(
                schema.ModuleJsonOutput.module_id == P6_AUTO_ARTICLE_MODULE_ID,
                schema.ModuleJsonOutput.run_id == f"p6article-{final_run_id}",
            )
            .limit(1)
        )
        return dict(row.payload or {}) if row else None


def _valid_evidence(final_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = final_payload.get("metric_evidence") or []
    return [
        item
        for item in rows
        if isinstance(item, dict) and item.get("evidence_id") and item.get("metric_id")
    ]


def _citation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "radar_module": item.get("radar_module"),
        "metric_id": item.get("metric_id"),
        "source_id": item.get("source_id"),
        "source_ts": item.get("source_ts"),
        "claim": item.get("p45_metric_brief") or item.get("score_reason") or item.get("metric_id"),
        "interpretation": {
            "direction": item.get("direction"),
            "metric_effective_score": item.get("metric_effective_score"),
            "is_stale": bool(item.get("is_stale", False)),
            "fallback_used": bool(item.get("fallback_used", False)),
        },
    }


def _article_body(
    final_payload: dict[str, Any],
    research: dict[str, Any],
    publish: dict[str, Any],
    citations: list[dict[str, Any]],
) -> str:
    body_parts = [
        str(research.get("body") or "").strip(),
        str(publish.get("body") or "").strip(),
    ]
    body = "\n\n".join(part for part in body_parts if part)
    if body:
        return body
    final_view_cn = final_payload.get("final_view_cn") or final_payload.get("final_view") or "unknown"
    citation_text = "、".join(
        str(item.get("metric_id")) for item in citations[:5] if item.get("metric_id")
    )
    return (
        f"本轮 BTC P4.5 自动文章草稿结论为 {final_view_cn}。"
        f"草稿基于 frozen final payload 生成，核心证据包括：{citation_text or '暂无可用证据'}。"
        "该文本仅用于解释系统状态和后续人工复核，不构成交易建议。"
    )


def _summary(
    final_payload: dict[str, Any],
    research: dict[str, Any],
    publish: dict[str, Any],
) -> str:
    return str(
        research.get("executive_summary")
        or research.get("summary")
        or publish.get("summary")
        or final_payload.get("final_view_cn")
        or final_payload.get("final_view")
        or "P6 automatic article draft"
    )


def _risk_disclosures(final_payload: dict[str, Any]) -> list[str]:
    disclosures = [
        "This article is an explanation layer, not trading advice.",
        "No position size, leverage, stop-loss, or take-profit instruction is produced.",
    ]
    contract = final_payload.get("contract_validation") or {}
    data_quality = final_payload.get("data_quality") or {}
    if contract.get("status") not in {"passed", "ok"}:
        disclosures.append("Contract validation is not fully passed; manual review is required.")
    quality_level = data_quality.get("data_quality_level") or data_quality.get("quality_level")
    if quality_level and str(quality_level).lower() not in {"high", "ok", "normal"}:
        disclosures.append("Data quality is degraded; confidence should be reviewed manually.")
    return disclosures


def _quality_gate(
    *,
    final_payload: dict[str, Any],
    body: str,
    citations: list[dict[str, Any]],
    contract: dict[str, Any],
    data_quality: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "source_schema_v2": final_payload.get("schema_version") == "p45.research_report.v2",
        "has_final_run_id": bool(final_payload.get("final_run_id")),
        "contract_passed": contract.get("status") in {"passed", "ok"},
        "body_present": len(body.strip()) >= 20,
        "evidence_citations_present": bool(citations),
        "citations_traceable": _citations_traceable(final_payload, citations),
        "auto_publish_blocked": True,
        "data_quality_observable": bool(data_quality),
    }
    return {
        "status": "passed" if all(checks.values()) else "warning",
        "checks": checks,
        "warning_count": sum(1 for value in checks.values() if not value),
    }


def _citations_traceable(
    final_payload: dict[str, Any],
    citations: list[dict[str, Any]],
) -> bool:
    allowed = {
        str(item.get("evidence_id"))
        for item in _valid_evidence(final_payload)
        if item.get("evidence_id")
    }
    return bool(citations) and all(str(item.get("evidence_id")) in allowed for item in citations)


def _run_lineage(final_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "collect_run_id": final_payload.get("collect_run_id"),
        "p2_radar_run_id": final_payload.get("p2_radar_run_id"),
        "p3_run_id": final_payload.get("p3_run_id"),
        "pack_id": final_payload.get("pack_id"),
        "article_run_id": final_payload.get("article_run_id"),
        "final_run_id": final_payload.get("final_run_id"),
    }


def _evidence_pack_replay(
    snapshot: dict[str, Any],
    final_payload: dict[str, Any],
    pack_payload: dict[str, Any],
) -> dict[str, Any]:
    pack_evidence = _pack_evidence_items(pack_payload, final_payload)
    pack_ids = {
        str(item.get("evidence_id"))
        for item in pack_evidence
        if item.get("evidence_id") is not None
    }
    citations = [
        item
        for item in snapshot.get("evidence_citations") or []
        if isinstance(item, dict)
    ]
    cited_ids = [
        str(item.get("evidence_id"))
        for item in citations
        if item.get("evidence_id") is not None
    ]
    unique_cited_ids = sorted(set(cited_ids))
    missing = sorted(evidence_id for evidence_id in unique_cited_ids if evidence_id not in pack_ids)
    uncited = sorted(evidence_id for evidence_id in pack_ids if evidence_id not in set(cited_ids))
    return {
        "pack_id": snapshot.get("pack_id") or pack_payload.get("pack_id"),
        "article_snapshot_id": snapshot.get("article_snapshot_id"),
        "pack_evidence_count": len(pack_evidence),
        "citation_count": len(citations),
        "unique_cited_evidence_count": len(unique_cited_ids),
        "missing_citation_count": len(missing),
        "uncited_evidence_count": len(uncited),
        "cited_evidence_ids": unique_cited_ids,
        "missing_citation_evidence_ids": missing,
        "uncited_evidence_ids": uncited,
        "traceability_status": "passed" if not missing else "warning",
        "frozen_pack_present": bool(pack_payload),
    }


def _pack_evidence_items(
    pack_payload: dict[str, Any],
    final_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    metrics = pack_payload.get("metric_evidence")
    if isinstance(metrics, list):
        return [dict(item) for item in metrics if isinstance(item, dict)]
    items: list[dict[str, Any]] = []
    for analyst in pack_payload.get("analysts") or []:
        if not isinstance(analyst, dict):
            continue
        for module in analyst.get("modules") or []:
            if not isinstance(module, dict):
                continue
            for item in module.get("metrics") or []:
                if isinstance(item, dict):
                    items.append(dict(item))
    if items:
        return items
    final_metrics = final_payload.get("metric_evidence")
    if isinstance(final_metrics, list):
        return [dict(item) for item in final_metrics if isinstance(item, dict)]
    return []
