from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from onlybtc.audit.p3_full_chain import run_p3_full_chain_audit
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.p4.adversarial_review import run_adversarial_review
from onlybtc.p4.analyst_executor import run_analyst_agents
from onlybtc.p4.article_writer import generate_readable_articles
from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.cross_exam import run_cross_examination
from onlybtc.p4.cross_exam_revision import run_cross_exam_revisions
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.p4.final_controller import build_final_controller_json
from onlybtc.p4.judge import run_judge_synthesis
from onlybtc.p4.rule_baseline import build_rule_baseline
from onlybtc.p4.state_machine import run_state_machine
from onlybtc.radars.registry import RADAR_MODULES

P4_HTML_FILENAME = "p4-controller-audit-report.html"


async def run_p4_full_chain_audit(
    collect_live: bool = True,
    run_mode: str = "live",
    runtime_mode: str = "mock",
    article_runtime_mode: str = "mock",
    db: Database = database,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    p3_result = await run_p3_full_chain_audit(
        collect_live=collect_live,
        run_mode=run_mode,
        db=db,
    )
    pack_result = build_p4_evidence_pack(
        radar_run_id=p3_result["p2_radar_run_id"],
        p3_run_id=p3_result["p3_run_id"],
        db=db,
    )
    analyst_result = run_analyst_agents(
        pack_id=pack_result["pack_id"],
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        db=db,
    )
    baseline = build_rule_baseline(pack_id=pack_result["pack_id"], db=db)
    state = run_state_machine(pack_id=pack_result["pack_id"], baseline=baseline, db=db)
    cross_result = run_cross_examination(
        debate_id=analyst_result["debate_id"],
        pack_id=pack_result["pack_id"],
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        db=db,
    )
    revision_result = run_cross_exam_revisions(
        debate_id=analyst_result["debate_id"],
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        db=db,
    )
    judge_result = run_judge_synthesis(
        debate_id=analyst_result["debate_id"],
        pack_id=pack_result["pack_id"],
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        db=db,
    )
    review_result = run_adversarial_review(
        debate_id=analyst_result["debate_id"],
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        db=db,
    )
    final_result = build_final_controller_json(
        debate_id=analyst_result["debate_id"],
        db=db,
    )
    context = _build_context(
        started_at=started_at,
        p3_result=p3_result,
        pack_result=pack_result,
        analyst_result=analyst_result,
        baseline=baseline,
        state=state,
        cross_result=cross_result,
        revision_result=revision_result,
        judge_result=judge_result,
        review_result=review_result,
        final_result=final_result,
        run_mode=run_mode,
        runtime_mode=runtime_mode,
        article_runtime_mode=article_runtime_mode,
        db=db,
    )
    report_dir = paths.project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = _write_report(report_dir / P4_HTML_FILENAME, _html_report(context))
    return {
        "status": "completed",
        "p1_c22_html_path": p3_result["p1_c22_html_path"],
        "p2_html_path": p3_result["p2_html_path"],
        "p3_html_path": p3_result["p3_html_path"],
        "p4_html_path": str(html_path),
        "collect_run_id": p3_result.get("collect_run_id"),
        "p2_radar_run_id": p3_result["p2_radar_run_id"],
        "p3_run_id": p3_result["p3_run_id"],
        "evidence_pack_id": pack_result["pack_id"],
        "debate_id": analyst_result["debate_id"],
        "judge_synthesis_id": judge_result["judge_synthesis"]["judge_synthesis_id"],
        "adversarial_review_id": review_result["adversarial_review"]["review_id"],
        "snapshot_id": final_result["snapshot_id"],
        "publish_allowed": final_result["final_controller_json"]["publish_allowed"],
        "blocked_by": final_result["final_controller_json"]["blocked_by"],
        "run_mode": run_mode,
        "runtime_mode": runtime_mode,
        "article_runtime_mode": article_runtime_mode,
        "article_status": context["article_result"]["status"],
    }


def run_p4_full_chain_audit_sync(
    collect_live: bool = True,
    run_mode: str = "live",
    runtime_mode: str = "mock",
    article_runtime_mode: str = "mock",
) -> dict[str, Any]:
    return asyncio.run(
        run_p4_full_chain_audit(
            collect_live=collect_live,
            run_mode=run_mode,
            runtime_mode=runtime_mode,
            article_runtime_mode=article_runtime_mode,
        )
    )


def _build_context(
    started_at: datetime,
    p3_result: dict[str, Any],
    pack_result: dict[str, Any],
    analyst_result: dict[str, Any],
    baseline: dict[str, Any],
    state: dict[str, Any],
    cross_result: dict[str, Any],
    revision_result: dict[str, Any],
    judge_result: dict[str, Any],
    review_result: dict[str, Any],
    final_result: dict[str, Any],
    run_mode: str,
    runtime_mode: str,
    article_runtime_mode: str,
    db: Database,
) -> dict[str, Any]:
    pack_id = str(pack_result["pack_id"])
    debate_id = str(analyst_result["debate_id"])
    with db.session() as session:
        evidence_counts = dict(
            session.execute(
                select(
                    schema.EvidenceItem.data["source_layer"].as_string(),
                    func.count(),
                )
                .where(schema.EvidenceItem.pack_id == pack_id)
                .group_by(schema.EvidenceItem.data["source_layer"].as_string())
            ).all()
        )
        votes = session.scalars(
            select(schema.LlmModelVote)
            .where(schema.LlmModelVote.debate_id == debate_id)
            .order_by(schema.LlmModelVote.model_name)
        ).all()
        challenges = session.scalars(
            select(schema.LlmChallenge)
            .where(schema.LlmChallenge.debate_id == debate_id)
            .order_by(schema.LlmChallenge.created_at)
        ).all()
        revisions = session.scalars(
            select(schema.LlmRevision)
            .where(schema.LlmRevision.debate_id == debate_id)
            .order_by(schema.LlmRevision.created_at)
        ).all()
        snapshot_modules = session.scalars(
            select(schema.SnapshotModule)
            .where(schema.SnapshotModule.snapshot_id == final_result["snapshot_id"])
            .order_by(schema.SnapshotModule.module_id)
        ).all()
        evidence_items = session.scalars(
            select(schema.EvidenceItem)
            .where(schema.EvidenceItem.pack_id == pack_id)
            .order_by(schema.EvidenceItem.evidence_id)
        ).all()

    final_json = final_result["final_controller_json"]
    evidence_rows = [_evidence_row(row) for row in evidence_items]
    vote_rows = [_vote_row(row) for row in votes]
    challenge_rows = [_challenge_row(row) for row in challenges]
    revision_rows = [_revision_row(row) for row in revisions]
    snapshot_module_rows = [_snapshot_module_row(row) for row in snapshot_modules]
    analyst_narratives = _analyst_narratives(
        evidence_rows=evidence_rows,
        vote_rows=vote_rows,
        final_json=final_json,
    )
    article_result = generate_readable_articles(
        analyst_narratives=analyst_narratives,
        final_json=final_json,
        judge=judge_result["judge_synthesis"],
        review=review_result["adversarial_review"],
        state=state,
        article_runtime_mode=article_runtime_mode,  # type: ignore[arg-type]
        full_evidence_rows=evidence_rows,
    )
    article_evidence_coverage = _article_evidence_coverage(
        article_result=article_result,
        analyst_narratives=analyst_narratives,
        evidence_rows=evidence_rows,
    )
    checks = _sqlite_checks(
        pack_result=pack_result,
        analyst_result=analyst_result,
        final_result=final_result,
        snapshot_modules=snapshot_modules,
    )
    return {
        "started_at": started_at,
        "generated_at": datetime.now(UTC),
        "run_mode": run_mode,
        "runtime_mode": runtime_mode,
        "article_runtime_mode": article_runtime_mode,
        "p3_result": p3_result,
        "pack_result": pack_result,
        "analyst_result": analyst_result,
        "baseline": baseline,
        "state": state,
        "cross_result": cross_result,
        "revision_result": revision_result,
        "judge_result": judge_result,
        "review_result": review_result,
        "final_result": final_result,
        "final_json": final_json,
        "all_agent_runtime_results": _all_agent_runtime_results(
            analyst_result=analyst_result,
            cross_result=cross_result,
            revision_result=revision_result,
            judge_result=judge_result,
            review_result=review_result,
            article_result=article_result,
        ),
        "evidence_counts": evidence_counts,
        "votes": vote_rows,
        "challenges": challenge_rows,
        "revisions": revision_rows,
        "snapshot_modules": snapshot_module_rows,
        "evidence_items": evidence_rows,
        "analyst_narratives": analyst_narratives,
        "article_result": article_result,
        "article_evidence_coverage": article_evidence_coverage,
        "final_observation_article": _article_to_text(article_result["final_article"]),
        "sqlite_checks": checks,
    }


def _all_agent_runtime_results(
    analyst_result: dict[str, Any],
    cross_result: dict[str, Any],
    revision_result: dict[str, Any],
    judge_result: dict[str, Any],
    review_result: dict[str, Any],
    article_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage, result in (
        ("analyst", analyst_result),
        ("cross_exam", cross_result),
        ("cross_exam_revision", revision_result),
        ("judge", judge_result),
        ("adversarial_review", review_result),
        ("article_writer", article_result),
    ):
        for item in result.get("runtime_results") or []:
            rows.append({"stage": stage, **item})
    return rows


def _sqlite_checks(
    pack_result: dict[str, Any],
    analyst_result: dict[str, Any],
    final_result: dict[str, Any],
    snapshot_modules: list[schema.SnapshotModule],
) -> list[dict[str, Any]]:
    return [
        {
            "check": "evidence_pack_radar_modules",
            "status": _status(
                pack_result["radar_modules_consumed_count"]
                == pack_result["radar_module_total"]
            ),
            "detail": (
                f'{pack_result["radar_modules_consumed_count"]}/'
                f'{pack_result["radar_module_total"]}'
            ),
        },
        {
            "check": "analyst_votes_written",
            "status": _status(analyst_result["votes_written_count"] == 4),
            "detail": analyst_result["votes_written_count"],
        },
        {
            "check": "snapshot_modules",
            "status": _status(len(snapshot_modules) == len(RADAR_MODULES)),
            "detail": f"{len(snapshot_modules)}/{len(RADAR_MODULES)}",
        },
        {
            "check": "final_json_evidence_ids",
            "status": _status(bool(final_result["final_controller_json"]["evidence_ids"])),
            "detail": len(final_result["final_controller_json"]["evidence_ids"]),
        },
    ]


def _vote_row(row: schema.LlmModelVote) -> dict[str, Any]:
    return {
        "raw_model_name": row.model_name,
        "model_name": _display_analyst_id(row.model_name),
        "vote": row.vote,
        "confidence": row.confidence,
        "evidence_count": len(row.evidence_ids or []),
        "changed": row.changed,
    }


def _evidence_row(row: schema.EvidenceItem) -> dict[str, Any]:
    data = row.data or {}
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    event_summary = data.get("event_summary") if isinstance(data.get("event_summary"), dict) else {}
    daily_watch = data.get("daily_watch") if isinstance(data.get("daily_watch"), dict) else {}
    history = data.get("history") if isinstance(data.get("history"), list) else []
    return {
        "evidence_id": row.evidence_id,
        "module_id": row.module_id,
        "claim": row.claim,
        "direction": row.direction,
        "strength": row.strength,
        "source_layer": data.get("source_layer"),
        "assigned_analyst": data.get("assigned_analyst"),
        "metric_id": data.get("metric_id"),
        "source_id": data.get("source_id"),
        "source_run_id": data.get("source_run_id"),
        "value": data.get("value"),
        "quality_score": data.get("quality_score"),
        "available": data.get("available"),
        "role": data.get("role"),
        "event_type": data.get("event_type"),
        "event_phase": data.get("event_phase"),
        "publish_impact": data.get("publish_impact"),
        "event_headline": event_summary.get("headline"),
        "daily_watch": daily_watch.get("change_summary"),
        "history_available": data.get("history_available"),
        "history": history,
        "score": payload.get("score"),
        "percentile": payload.get("percentile"),
    }


def _challenge_row(row: schema.LlmChallenge) -> dict[str, Any]:
    try:
        payload = json.loads(row.issue)
    except json.JSONDecodeError:
        payload = {}
    return {
        "challenger": row.challenger,
        "target": _display_analyst_id(row.target),
        "severity": row.severity,
        "challenge_id": payload.get("challenge_id", f"challenge-row-{row.id}"),
        "challenge_type": payload.get("challenge_type", ""),
        "claim": _sanitize_display_text(payload.get("claim_under_review", row.issue)),
        "required_response": payload.get("required_response", ""),
        "evidence_count": len(payload.get("evidence_ids") or []),
    }


def _revision_row(row: schema.LlmRevision) -> dict[str, Any]:
    payload = row.payload or {}
    return {
        "challenge_id": row.challenge_id,
        "responding_agent": _display_analyst_id(row.responding_agent),
        "changed": row.changed,
        "previous_vote": row.previous_vote,
        "revised_vote": row.revised_vote,
        "previous_confidence": row.previous_confidence,
        "revised_confidence": row.revised_confidence,
        "accepted_points": "; ".join(payload.get("accepted_points") or []),
        "rejected_points": "; ".join(payload.get("rejected_points") or []),
        "reason": payload.get("reason", ""),
        "evidence_count": len(payload.get("evidence_ids") or []),
    }


def _analyst_narratives(
    evidence_rows: list[dict[str, Any]],
    vote_rows: list[dict[str, Any]],
    final_json: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    votes = {row["raw_model_name"]: row for row in vote_rows}
    for analyst_id, modules in ANALYST_MODULES.items():
        analyst_evidence = [
            row
            for row in evidence_rows
            if row.get("assigned_analyst") == analyst_id
            and row.get("source_layer") != "analyst_history"
        ]
        history_rows = [
            row
            for row in evidence_rows
            if row.get("assigned_analyst") == analyst_id
            and row.get("source_layer") == "analyst_history"
        ]
        top_evidence = _top_evidence(analyst_evidence, limit=12)
        all_evidence = _top_evidence(analyst_evidence, limit=len(analyst_evidence))
        vote = votes.get(analyst_id, {})
        history_summary = _history_summary(history_rows)
        conclusion = _analyst_conclusion(
            analyst_id=analyst_id,
            modules=modules,
            vote=vote,
            top_evidence=top_evidence,
            history_summary=history_summary,
            final_json=final_json,
        )
        rows.append(
            {
                "analyst_id": _display_analyst_id(analyst_id),
                "raw_analyst_id": analyst_id,
                "modules": ", ".join(modules),
                "vote": vote.get("vote", "unknown"),
                "confidence": vote.get("confidence", "-"),
                "evidence_count": len(analyst_evidence),
                "history_available": bool(history_summary["history_available"]),
                "history_summary": history_summary["text"],
                "top_evidence": top_evidence,
                "all_evidence": all_evidence,
                "evidence_by_module": _evidence_by_module(all_evidence),
                "coverage_target_evidence_ids": [
                    str(row["evidence_id"]) for row in all_evidence if row.get("evidence_id")
                ],
                "conclusion": conclusion,
            }
        )
    return rows


def _evidence_by_module(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("module_id") or "unknown"), []).append(row)
    return [
        {
            "module_id": module_id,
            "evidence_count": len(module_rows),
            "evidence_ids": [
                str(row["evidence_id"]) for row in module_rows if row.get("evidence_id")
            ],
            "sample_claims": [str(row.get("claim") or "") for row in module_rows[:4]],
        }
        for module_id, module_rows in sorted(grouped.items())
    ]


def _top_evidence(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    available = [row for row in rows if row.get("available") is not False]
    sorted_rows = sorted(
        available or rows,
        key=lambda row: (_evidence_priority(row), float(row.get("quality_score") or 0)),
        reverse=True,
    )
    return sorted_rows[:limit]


def _evidence_priority(row: dict[str, Any]) -> float:
    try:
        strength = abs(float(row.get("strength") or 0))
    except (TypeError, ValueError):
        strength = 0.0
    try:
        quality = float(row.get("quality_score") or 0)
    except (TypeError, ValueError):
        quality = 0.0
    text = " ".join(
        str(row.get(key) or "")
        for key in ("metric_id", "source_id", "module_id", "claim", "role")
    ).lower()
    sensitive_keywords = (
        "1h",
        "funding",
        "open_interest",
        "oi",
        "taker",
        "etf",
        "stablecoin",
        "exchange_balance",
        "vix",
        "dxy",
        "days_until",
        "event",
        "macro_surprise",
        "basis",
        "options",
    )
    sensitivity = 0.08 * sum(1 for keyword in sensitive_keywords if keyword in text)
    directional = 0.04 if str(row.get("direction") or "neutral") not in {"neutral", "mixed"} else 0
    return strength + quality * 0.25 + sensitivity + directional


def _history_summary(history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not history_rows:
        return {
            "history_available": False,
            "text": "本轮 Evidence Pack 没有冻结该分析师的历史记录。",
        }
    row = history_rows[0]
    history = row.get("history") or []
    if not history:
        return {
            "history_available": False,
            "text": (
                f"{row['evidence_id']} 已冻结 analyst_history，但其中没有上一轮 vote "
                "历史。"
            ),
        }
    latest = history[0]
    return {
        "history_available": True,
        "text": (
            f"{row['evidence_id']} 最新历史：上一轮 debate={latest.get('debate_id')}，"
            f"vote={latest.get('vote')}，confidence={latest.get('confidence')}，"
            f"final_state={latest.get('final_state')}，changed={latest.get('changed')}。"
        ),
    }


def _analyst_conclusion(
    analyst_id: str,
    modules: tuple[str, ...],
    vote: dict[str, Any],
    top_evidence: list[dict[str, Any]],
    history_summary: dict[str, Any],
    final_json: dict[str, Any],
) -> str:
    evidence_text = " ".join(_evidence_sentence(row) for row in top_evidence[:3])
    if not evidence_text:
        evidence_text = "该分析师在冻结 Evidence Pack 中没有可用 evidence 行。"
    return (
        f"{_display_analyst_id(analyst_id)} 负责 {', '.join(modules)}。"
        f"本轮该分析师输出 vote={vote.get('vote', 'unknown')}，"
        f"confidence={vote.get('confidence', '-')}。"
        f"证据与数据：{evidence_text} "
        f"历史上下文：{history_summary['text']} "
        "总控状态、发布门控与 runtime 只用于置信度折扣和审计分层："
        f"trend_state={final_json.get('trend_state')}，"
        f"risk_state={final_json.get('risk_state')}，"
        f"blocked_by={', '.join(final_json.get('blocked_by') or []) or '无'}。"
    )


def _evidence_sentence(row: dict[str, Any]) -> str:
    parts = [
        f"{row.get('evidence_id')}",
        f"module={row.get('module_id')}",
    ]
    if row.get("metric_id"):
        parts.append(f"metric={row.get('metric_id')}")
    if row.get("source_id"):
        parts.append(f"source={row.get('source_id')}")
    if row.get("value") is not None:
        parts.append(f"value={row.get('value')}")
    if row.get("quality_score") is not None:
        parts.append(f"quality={row.get('quality_score')}")
    if row.get("event_headline"):
        parts.append(f"event={row.get('event_headline')}")
    if row.get("daily_watch"):
        parts.append(f"daily_watch={row.get('daily_watch')}")
    return (
        "[" + ", ".join(str(part) for part in parts) + "] "
        f"证据说明={_sanitize_display_text(str(row.get('claim')))}。"
    )


def _final_observation_article(
    final_json: dict[str, Any],
    analyst_narratives: list[dict[str, Any]],
    judge: dict[str, Any],
    review: dict[str, Any],
    state: dict[str, Any],
) -> str:
    analyst_lines = "\n\n".join(
        f"{item['analyst_id']}：{item['conclusion']}" for item in analyst_narratives
    )
    evidence_refs = []
    for analyst in analyst_narratives:
        evidence_refs.extend(row["evidence_id"] for row in analyst["top_evidence"][:2])
    evidence_ref_text = ", ".join(evidence_refs[:12])
    return (
        "最终观察建议文章\n\n"
        f"本轮总控状态为 trend_state={final_json.get('trend_state')}，"
        f"risk_state={final_json.get('risk_state')}。主导状态为 "
        f"{final_json.get('dominant_regime')}，总控 confidence="
        f"{final_json.get('confidence')}，confidence_discount="
        f"{final_json.get('confidence_discount')}。状态机保留的硬约束包括："
        f"{', '.join(final_json.get('blocked_by') or []) or '无'}。"
        f"状态机同时给出 critical_publish_allowed="
        f"{state.get('critical_publish_allowed')}，state_transition_allowed="
        f"{state.get('state_transition_allowed')}。\n\n"
        f"主裁判合成 {judge.get('judge_synthesis_id')} 给出 consensus_level="
        f"{judge.get('consensus_level')}，disagreement_level="
        f"{judge.get('disagreement_level')}，并保留 "
        f"{len(judge.get('minority_objections') or [])} 条 minority objection。"
        "这意味着最终结论不是简单投票，而是需要同时考虑证据质量、反证、"
        "状态机约束和历史一致性。"
        f"反方审查 {review.get('review_id')} 的结果为 passed={review.get('passed')}，"
        f"required_fixes={review.get('required_fixes')}。\n\n"
        "四个分析师证据链如下：\n\n"
        f"{analyst_lines}\n\n"
        f"本文引用的关键 evidence 包括：{evidence_ref_text}。"
        "总控 observation_points 为："
        f"{_sanitize_display_text('; '.join(final_json.get('observation_points') or []))}。"
        "数据质量说明为："
        f"{'; '.join(final_json.get('data_quality_notes') or [])}。"
        "以上内容仅用于观察、复盘和证据审计，不构成任何执行建议。"
    )


def _article_to_text(article: dict[str, Any]) -> str:
    sections = "\n\n".join(
        f"{section.get('heading')}\n{section.get('body')}"
        for section in article.get("sections", [])
    )
    evidence_ids = ", ".join(
        str(item.get("evidence_id")) for item in article.get("evidence_citations", [])
    )
    return (
        f"{article.get('title')}\n\n"
        f"{article.get('summary')}\n\n"
        f"{sections}\n\n"
        f"Evidence: {evidence_ids}"
    )


def _article_evidence_coverage(
    article_result: dict[str, Any],
    analyst_narratives: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    articles = list(article_result.get("analyst_articles") or [])
    if article_result.get("final_article"):
        articles.append(article_result["final_article"])
    article_ids = set(_article_evidence_ids_from_articles(articles))
    pack_ids = {
        str(row["evidence_id"])
        for row in evidence_rows
        if row.get("evidence_id") and row.get("source_layer") != "analyst_history"
    }
    analyst_rows: list[dict[str, Any]] = []
    for narrative in analyst_narratives:
        target_ids = {
            str(row["evidence_id"])
            for row in narrative.get("all_evidence") or []
            if row.get("evidence_id")
        }
        used_count = len(target_ids & article_ids)
        analyst_rows.append(
            {
                "analyst_id": narrative.get("analyst_id"),
                "target_evidence_count": len(target_ids),
                "article_evidence_count": used_count,
                "coverage_pct": round(used_count / len(target_ids), 3) if target_ids else 1.0,
                "missing_count": len(target_ids - article_ids),
            }
        )
    covered_count = len(pack_ids & article_ids)
    return {
        "pack_evidence_count": len(pack_ids),
        "article_unique_evidence_count": len(article_ids),
        "covered_pack_evidence_count": covered_count,
        "coverage_pct": round(covered_count / len(pack_ids), 3) if pack_ids else 1.0,
        "analyst_rows": analyst_rows,
        "missing_evidence_ids": sorted(pack_ids - article_ids)[:50],
    }


def _article_evidence_ids_from_articles(articles: list[dict[str, Any]]) -> list[str]:
    evidence_ids: list[str] = []
    for article in articles:
        evidence_ids.extend(
            str(item.get("evidence_id"))
            for item in article.get("evidence_citations") or []
            if item.get("evidence_id")
        )
        for section in article.get("sections") or []:
            evidence_ids.extend(str(item) for item in section.get("evidence_ids") or [])
    return sorted(set(evidence_ids))


def _snapshot_module_row(row: schema.SnapshotModule) -> dict[str, Any]:
    return {
        "module_id": row.module_id,
        "signal": row.signal,
        "strength": row.strength,
        "data_quality": (row.payload or {}).get("data_quality", ""),
    }


def _display_analyst_id(analyst_id: str) -> str:
    names = {
        "macro_event_analyst": "宏观与事件分析师",
        "liquidity_flow_analyst": "流动性与资金流分析师",
        "leverage_microstructure_analyst": "微观结构分析师",
        "onchain_market_structure_analyst": "链上与市场结构分析师",
    }
    return names.get(analyst_id, analyst_id.replace("leverage_microstructure", "microstructure"))


def _sanitize_display_text(text: str) -> str:
    return (
        text.replace("leverage_microstructure_analyst", "微观结构分析师")
        .replace("leverage_microstructure", "microstructure")
        .replace("Leverage & Microstructure", "Microstructure")
    )


def _html_report(context: dict[str, Any]) -> str:
    p3 = context["p3_result"]
    pack = context["pack_result"]
    analyst = context["analyst_result"]
    judge = context["judge_result"]["judge_synthesis"]
    review = context["review_result"]["adversarial_review"]
    final_json = context["final_json"]
    run_rows = [
        {"key": "collect_run_id", "value": p3.get("collect_run_id")},
        {"key": "p2_radar_run_id", "value": p3["p2_radar_run_id"]},
        {"key": "p3_run_id", "value": p3["p3_run_id"]},
        {"key": "evidence_pack_id", "value": pack["pack_id"]},
        {"key": "debate_id", "value": analyst["debate_id"]},
        {"key": "judge_synthesis_id", "value": judge["judge_synthesis_id"]},
        {"key": "adversarial_review_id", "value": review["review_id"]},
        {"key": "snapshot_id", "value": context["final_result"]["snapshot_id"]},
    ]
    html_paths = [
        {"report": "P1-C22", "path": p3["p1_c22_html_path"]},
        {"report": "P2 Radar", "path": p3["p2_html_path"]},
        {"report": "P3 Algorithm", "path": p3["p3_html_path"]},
    ]
    pack_rows = [
        {"metric": key, "value": value}
        for key, value in pack.items()
        if key.endswith("_count") or key in {"radar_module_total", "pack_id"}
    ]
    analyst_rows = context["analyst_result"]["analyst_inputs"]
    baseline_rows = [
        {"key": "baseline_signal", "value": context["baseline"]["baseline_signal"]},
        {"key": "aggregate_signal_score", "value": context["baseline"]["aggregate_signal_score"]},
        {"key": "baseline_confidence", "value": context["baseline"]["baseline_confidence"]},
        {"key": "confidence_discount", "value": context["baseline"]["confidence_discount"]},
    ]
    state_rows = [
        {"key": "trend_state", "value": context["state"]["trend_state"]},
        {"key": "risk_state", "value": context["state"]["risk_state"]},
        {"key": "critical_publish_allowed", "value": context["state"]["critical_publish_allowed"]},
        {"key": "blocked_by", "value": context["state"]["blocked_by"]},
    ]
    judge_rows = [
        {"key": "dominant_regime", "value": judge["dominant_regime"]},
        {"key": "consensus_level", "value": judge["consensus_level"]},
        {"key": "disagreement_level", "value": judge["disagreement_level"]},
        {"key": "confidence", "value": judge["confidence"]},
        {"key": "confidence_discount", "value": judge["confidence_discount"]},
        {"key": "publish_allowed", "value": judge["publish_allowed"]},
        {"key": "minority_objections", "value": len(judge["minority_objections"])},
        {
            "key": "revision_summary",
            "value": context["judge_result"]["judge_synthesis"].get("revision_summary")
            or context["judge_result"].get("revision_summary")
            or "see judge payload",
        },
    ]
    review_rows = [
        {"key": "passed", "value": review["passed"]},
        {"key": "publish_allowed", "value": review["publish_allowed"]},
        {"key": "required_fixes", "value": review["required_fixes"]},
    ]
    final_rows = [
        {"key": "trend_state", "value": final_json["trend_state"]},
        {"key": "risk_state", "value": final_json["risk_state"]},
        {"key": "confidence", "value": final_json["confidence"]},
        {"key": "confidence_discount", "value": final_json["confidence_discount"]},
        {"key": "publish_allowed", "value": final_json["publish_allowed"]},
        {"key": "publish_scope", "value": final_json.get("publish_scope")},
        {"key": "watch_only", "value": final_json.get("watch_only")},
        {"key": "dashboard_only", "value": final_json.get("dashboard_only")},
        {"key": "revision_integrity", "value": final_json.get("revision_integrity")},
        {
            "key": "unresolved_high_challenge_count",
            "value": final_json.get("unresolved_high_challenge_count"),
        },
        {
            "key": "adversarial_publish_gate_reason",
            "value": final_json.get("adversarial_publish_gate_reason"),
        },
        {"key": "blocked_by", "value": final_json["blocked_by"]},
        {"key": "evidence_ids", "value": len(final_json["evidence_ids"])},
    ]
    revision_gate_rows = [
        {"key": "revision_integrity", "value": final_json.get("revision_integrity")},
        {"key": "revision_round_count", "value": final_json.get("revision_round_count")},
        {
            "key": "unresolved_challenge_count",
            "value": final_json.get("unresolved_challenge_count"),
        },
        {
            "key": "unresolved_high_challenge_count",
            "value": final_json.get("unresolved_high_challenge_count"),
        },
        {"key": "revision_required_fixes", "value": final_json.get("revision_required_fixes")},
        {"key": "publish_scope", "value": final_json.get("publish_scope")},
        {"key": "publish_block_reason", "value": final_json.get("publish_block_reason")},
    ]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>P4 总控审计报告</title>
  <style>
    body {{ margin: 0; background: #08131c; color: #dbeafe; font-family: Arial, sans-serif; }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ color: #f8fafc; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #1e3a4f; background: #0d1f2d; border-radius: 8px; padding: 14px; }}
    .value {{ font-size: 20px; font-weight: 700; color: #67e8f9; overflow-wrap: anywhere; }}
    .ok {{ color: #86efac; }}
    .bad {{ color: #fb7185; }}
    .warn {{ color: #fbbf24; }}
    .table-wrap {{ width: 100%; overflow-x: auto; border: 1px solid #102c3e; border-radius: 6px; }}
    table {{ width: 100%; min-width: 980px; border-collapse: collapse; font-size: 13px; }}
    th, td {{
      border-bottom: 1px solid #1e3a4f;
      padding: 8px;
      text-align: left;
      vertical-align: top;
      max-width: 360px;
      overflow-wrap: anywhere;
    }}
    th {{ color: #bae6fd; background: #0b1a26; position: sticky; top: 0; z-index: 1; }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #0b1a26;
      padding: 12px;
      border-radius: 6px;
    }}
    .narrative {{
      border: 1px solid #1e3a4f;
      background: #0d1f2d;
      border-radius: 8px;
      padding: 16px;
      margin: 12px 0;
    }}
    .narrative h3 {{ margin-top: 0; color: #e0f2fe; }}
    .narrative p {{ line-height: 1.6; }}
    .evidence-list {{ margin: 0; padding-left: 18px; }}
    code {{ color: #fef3c7; }}
  </style>
</head>
<body>
<main>
  <h1>P4 总控审计报告</h1>
  <p>
    生成时间: {escape(context["generated_at"].isoformat())} |
    run_mode: <code>{escape(context["run_mode"])}</code> |
    runtime_mode: <code>{escape(context["runtime_mode"])}</code>
    | article_runtime_mode: <code>{escape(context["article_runtime_mode"])}</code>
    | article_status: <code>{escape(context["article_result"]["status"])}</code>
  </p>
  <div class="grid">
    {_card("Evidence Pack", pack["pack_id"])}
    {_card("Debate", analyst["debate_id"])}
    {_card("Judge Confidence", judge["confidence"])}
    {_card("Publish Scope", final_json.get("publish_scope", "unknown"))}
    {_card("Revision Gate", final_json.get("revision_integrity", "unknown"))}
    {
        _card(
            "Publish Allowed",
            final_json["publish_allowed"],
            _status(final_json["publish_allowed"]),
        )
    }
  </div>
  <h2 id="research-report">Research Report</h2>
  {_research_report_html(context["article_result"])}
  <h2 id="analyst-research-briefs">Analyst Research Briefs</h2>
  {_analyst_briefs_html(context["article_result"])}
  <h2 id="decision-chain">Decision Chain</h2>
  {_decision_chain_html(context)}
  <h2 id="audit-appendix">Audit Appendix</h2>
  <h2>Run 契约</h2>
  {_table(["key", "value"], run_rows)}
  <h2>上游 HTML 报告</h2>
  {_table(["report", "path"], html_paths)}
  <h2>SQLite 契约检查</h2>
  {_table(["check", "status", "detail"], context["sqlite_checks"])}
  <h2>Evidence Pack 覆盖</h2>
  {_table(["metric", "value"], pack_rows)}
  <h2>Evidence 来源层级</h2>
  {_table(["metric", "value"], _dict_rows(context["evidence_counts"]))}
  <h2>分析师覆盖矩阵</h2>
  {_table(["analyst_id", "assigned_modules", "evidence_count", "history_available"], analyst_rows)}
  <h2>分析师投票</h2>
  {_table(["model_name", "vote", "confidence", "evidence_count", "changed"], context["votes"])}
  <h2>分析师中文结论</h2>
  {_analyst_narrative_html(context["analyst_narratives"])}
  <h2 id="llm-readable-articles">LLM 中文文章输出</h2>
  {_article_result_html(context["article_result"])}
  <h2 id="article-evidence-coverage">Article Evidence Coverage</h2>
  {_article_evidence_coverage_html(context["article_evidence_coverage"])}
  <h2 id="all-agent-runtime-audit">全 Agent Runtime 审计</h2>
  {_agent_runtime_audit_html(context["all_agent_runtime_results"], final_json)}
  <h2>交叉质询 Challenge</h2>
  {
        _table(
            [
                "challenge_id",
                "target",
                "severity",
                "challenge_type",
                "claim",
                "required_response",
                "evidence_count",
            ],
            context["challenges"],
        )
    }
  <h2>交叉质询 Revision</h2>
  {
        _table(
            [
                "challenge_id",
                "responding_agent",
                "changed",
                "previous_vote",
                "revised_vote",
                "previous_confidence",
                "revised_confidence",
                "accepted_points",
                "rejected_points",
                "reason",
                "evidence_count",
            ],
            context["revisions"],
        )
    }
  <h2>Revision Gate / Publish Scope</h2>
  {_table(["key", "value"], revision_gate_rows)}
  <h2>规则基线</h2>
  {_table(["key", "value"], baseline_rows)}
  <h2>状态机约束</h2>
  {_table(["key", "value"], state_rows)}
  <h2>主裁判合成</h2>
  {_table(["key", "value"], judge_rows)}
  <h2>反方审查</h2>
  {_table(["key", "value"], review_rows)}
  <h2>最终总控摘要</h2>
  {_table(["key", "value"], final_rows)}
  <h2>最终观察建议文章</h2>
  <div class="narrative">
    <pre>{escape(context["final_observation_article"])}</pre>
  </div>
  <h2>Snapshot 模块</h2>
  {_table(["module_id", "signal", "strength", "data_quality"], context["snapshot_modules"])}
  <h2>最终总控 JSON</h2>
  <pre>{escape(json.dumps(final_json, ensure_ascii=False, indent=2))}</pre>
</main>
</body>
</html>
"""


def _card(label: str, value: Any, status: str = "ok") -> str:
    return (
        '<div class="card">'
        f"<div>{escape(str(label))}</div>"
        f'<div class="value {escape(status)}">{escape(str(value))}</div>'
        "</div>"
    )


def _dict_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"metric": key, "value": value} for key, value in payload.items()]


def _table(headers: list[str], rows: list[dict[str, Any]]) -> str:
    if not rows:
        rows = [{header: "-" for header in headers}]
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>"
        + "".join(f"<td>{_format_cell(row.get(header, ''))}</td>" for header in headers)
        + "</tr>"
        for row in rows
    )
    return (
        '<div class="table-wrap">'
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        "</div>"
    )


def _analyst_narrative_html(rows: list[dict[str, Any]]) -> str:
    return "\n".join(
        (
            '<section class="narrative">'
            f"<h3>{escape(str(row['analyst_id']))}</h3>"
            f"<p><strong>负责模块:</strong> {escape(str(row['modules']))}</p>"
            f"<p><strong>投票:</strong> {escape(str(row['vote']))} | "
            f"<strong>Confidence:</strong> {escape(str(row['confidence']))} | "
            f"<strong>证据数量:</strong> {escape(str(row['evidence_count']))} | "
            f"<strong>历史可用:</strong> {escape(str(row['history_available']))}</p>"
            f"<p>{escape(str(row['conclusion']))}</p>"
            "<h4>Evidence + Data 证据与数据</h4>"
            f"{_evidence_list_html(row['top_evidence'])}"
            f"<p><strong>历史记录:</strong> {escape(str(row['history_summary']))}</p>"
            "</section>"
        )
        for row in rows
    )


def _article_result_html(article_result: dict[str, Any]) -> str:
    runtime_rows = [
        {"key": "article_runtime_mode", "value": article_result.get("article_runtime_mode")},
        {"key": "status", "value": article_result.get("status")},
        {"key": "errors", "value": article_result.get("errors") or []},
    ]
    analyst_html = "\n".join(
        _article_html(article) for article in article_result.get("analyst_articles") or []
    )
    final_html = _article_html(article_result.get("final_article") or {})
    runtime_trace_rows = [
        {
            "agent_name": row.get("agent_name"),
            "provider": row.get("model_provider"),
            "model": row.get("model_name"),
            "schema": row.get("schema_version"),
            "error": row.get("error") or "",
            "latency_ms": row.get("latency_ms"),
        }
        for row in article_result.get("runtime_results") or []
    ]
    trace_table = _table(
        ["agent_name", "provider", "model", "schema", "error", "latency_ms"],
        runtime_trace_rows,
    )
    return (
        '<section class="narrative">'
        "<h3>Article Runtime</h3>"
        f'{_table(["key", "value"], runtime_rows)}'
        "</section>"
        f"{analyst_html}"
        '<section class="narrative">'
        "<h3>最终观察文章</h3>"
        f"{final_html}"
        "</section>"
        "<h3>Article Agent Runtime Trace</h3>"
        f"{trace_table}"
    )


def _research_report_html(article_result: dict[str, Any]) -> str:
    return _article_html(article_result.get("final_article") or {})


def _analyst_briefs_html(article_result: dict[str, Any]) -> str:
    articles = article_result.get("analyst_articles") or []
    if not articles:
        return (
            '<section class="narrative">'
            '<p class="bad">No analyst briefs available.</p>'
            "</section>"
        )
    return "\n".join(_article_html(article) for article in articles)


def _decision_chain_html(context: dict[str, Any]) -> str:
    final_json = context["final_json"]
    rows = [
        {"stage": "analyst_votes", "result": context["votes"]},
        {"stage": "cross_exam_challenges", "result": len(context["challenges"])},
        {"stage": "cross_exam_revisions", "result": len(context["revisions"])},
        {"stage": "judge_synthesis", "result": context["judge_result"]["judge_synthesis"]},
        {"stage": "adversarial_review", "result": context["review_result"]["adversarial_review"]},
        {
            "stage": "final_controller_gate",
            "result": {
                "publish_allowed": final_json.get("publish_allowed"),
                "publish_scope": final_json.get("publish_scope"),
                "blocked_by": final_json.get("blocked_by"),
                "confidence": final_json.get("confidence"),
                "confidence_discount": final_json.get("confidence_discount"),
            },
        },
    ]
    return '<section class="narrative">' + _table(["stage", "result"], rows) + "</section>"


def _article_evidence_coverage_html(coverage: dict[str, Any]) -> str:
    summary_rows = [
        {"key": "pack_evidence_count", "value": coverage.get("pack_evidence_count")},
        {
            "key": "article_unique_evidence_count",
            "value": coverage.get("article_unique_evidence_count"),
        },
        {
            "key": "covered_pack_evidence_count",
            "value": coverage.get("covered_pack_evidence_count"),
        },
        {"key": "coverage_pct", "value": coverage.get("coverage_pct")},
        {"key": "missing_evidence_ids", "value": coverage.get("missing_evidence_ids") or []},
    ]
    matrix_headers = [
        "analyst_id",
        "target_evidence_count",
        "article_evidence_count",
        "coverage_pct",
        "missing_count",
    ]
    return (
        '<section class="narrative">'
        "<h3>Article Evidence Coverage Summary</h3>"
        f'{_table(["key", "value"], summary_rows)}'
        "<h3>Analyst Coverage Matrix</h3>"
        f'{_table(matrix_headers, coverage.get("analyst_rows") or [])}'
        "</section>"
    )


def _agent_runtime_audit_html(
    runtime_results: list[dict[str, Any]],
    final_json: dict[str, Any],
) -> str:
    summary_rows = [
        {"key": "runtime_mode", "value": final_json.get("runtime_mode")},
        {"key": "llm_runtime_integrity", "value": final_json.get("llm_runtime_integrity")},
        {"key": "fallback_used", "value": final_json.get("fallback_used")},
        {"key": "agent_runtime_failures", "value": final_json.get("agent_runtime_failures") or []},
        {"key": "fallback_reasons", "value": final_json.get("fallback_reasons") or []},
        {"key": "llm_budget_summary", "value": final_json.get("llm_budget_summary") or {}},
    ]
    trace_rows = [
        {
            "stage": row.get("stage"),
            "agent": row.get("agent_name"),
            "role": row.get("agent_role"),
            "provider": row.get("model_provider"),
            "model": row.get("model_name"),
            "schema": row.get("schema_version"),
            "fallback": row.get("fallback_used"),
            "error": row.get("error") or "",
            "latency_ms": row.get("latency_ms"),
        }
        for row in runtime_results
    ]
    trace_table = _table(
        [
            "stage",
            "agent",
            "role",
            "provider",
            "model",
            "schema",
            "fallback",
            "error",
            "latency_ms",
        ],
        trace_rows,
    )
    return (
        '<section class="narrative">'
        "<h3>Runtime Integrity</h3>"
        f'{_table(["key", "value"], summary_rows)}'
        "<h3>Agent Runtime Matrix</h3>"
        f"{trace_table}"
        "</section>"
    )


def _article_html(article: dict[str, Any]) -> str:
    research_fields = [
        ("trend_insight", "趋势洞察"),
        ("marginal_change", "边际变化"),
        ("conflict_weighting", "冲突权重"),
        ("confidence_explanation", "置信度解释"),
        ("audit_constraints_summary", "审计约束摘要"),
        ("executive_summary", "执行摘要"),
        ("market_state", "市场状态"),
        ("driver_analysis", "关键驱动"),
        ("conflict_analysis", "冲突证据"),
        ("history_delta", "历史变化"),
        ("event_watch", "事件观察"),
        ("quality_and_runtime", "数据质量与运行状态"),
        ("final_observation", "最终观察"),
        ("headline", "要点标题"),
        ("core_view", "核心观点"),
        ("changed_from_history", "历史变化"),
        ("confidence_rationale", "置信度依据"),
    ]
    structured_sections = "".join(
        f"<section><h4>{escape(label)}</h4><p>{escape(str(article.get(key)))}</p></section>"
        for key, label in research_fields
        if article.get(key)
    )
    list_fields = [
        ("sensitive_signals", "敏感信号"),
        ("early_warning_signals", "领先预警信号"),
        ("scenario_map", "情景地图"),
        ("invalidation_conditions", "反证条件"),
        ("watch_horizon", "观察周期"),
        ("key_drivers", "关键驱动列表"),
        ("counter_evidence", "反向证据"),
        ("watch_items", "观察清单"),
    ]
    structured_lists = "".join(
        "<section>"
        f"<h4>{escape(label)}</h4>"
        + '<ul class="evidence-list">'
        + "".join(f"<li>{escape(str(item))}</li>" for item in article.get(key) or [])
        + "</ul></section>"
        for key, label in list_fields
        if article.get(key)
    )
    sections = "".join(
        "<section>"
        f"<h4>{escape(str(section.get('heading', '-')))}</h4>"
        f"<p>{escape(str(section.get('body', '-')))}</p>"
        f"<p><strong>evidence_ids:</strong> "
        f"{escape(', '.join(str(item) for item in section.get('evidence_ids', [])))}</p>"
        "</section>"
        for section in article.get("sections") or []
    )
    citations = "".join(
        "<li>"
        f"<code>{escape(str(item.get('evidence_id')))}</code> "
        f"metric={escape(str(item.get('metric_id')))} "
        f"source={escape(str(item.get('source_id')))} "
        f"value={escape(str(item.get('value')))} "
        f"quality={escape(str(item.get('quality_score')))} "
        f"note={escape(str(item.get('note')))}"
        "</li>"
        for item in article.get("evidence_citations") or []
    )
    data_source_appendix = _data_source_appendix_html(
        article.get("data_source_appendix") or article.get("evidence_citations") or []
    )
    return (
        '<section class="narrative">'
        f"<h3>{escape(str(article.get('title', '-')))}</h3>"
        f"<p><code>{escape(str(article.get('schema_version', '-')))}</code></p>"
        f"<p>{escape(str(article.get('summary', '-')))}</p>"
        f"{structured_sections}"
        f"{structured_lists}"
        f"{sections}"
        f'<ul class="evidence-list">{citations}</ul>'
        f"{data_source_appendix}"
        "</section>"
    )


def _data_source_appendix_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    items = "".join(
        "<li>"
        f"<code>{escape(str(item.get('evidence_id')))}</code> "
        f"metric={escape(str(item.get('metric_id')))} "
        f"source={escape(str(item.get('source_id')))} "
        f"value={escape(str(item.get('value')))} "
        f"quality={escape(str(item.get('quality_score')))} "
        f"note={escape(str(item.get('note')))}"
        "</li>"
        for item in rows
    )
    return (
        '<section class="data-source-appendix">'
        "<h4>数据源与证据附录</h4>"
        f'<ul class="evidence-list">{items}</ul>'
        "</section>"
    )


def _evidence_list_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="bad">No evidence rows available.</p>'
    items = "".join(f"<li>{escape(_evidence_sentence(row))}</li>" for row in rows)
    return f'<ul class="evidence-list">{items}</ul>'


def _format_cell(value: Any) -> str:
    if isinstance(value, bool):
        return f'<span class="{_status(value)}">{value}</span>'
    if isinstance(value, list):
        return escape(", ".join(str(item) for item in value) or "-")
    if isinstance(value, dict):
        return escape(json.dumps(value, ensure_ascii=False))
    return escape(str(value))


def _status(ok: bool) -> str:
    return "ok" if ok else "bad"


def _write_report(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path
