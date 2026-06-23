from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from onlybtc.audit.p4_full_chain import P4_HTML_FILENAME
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database


def run_p4_dod_check(db: Database = database) -> dict[str, Any]:
    db.init_schema()
    with db.session() as session:
        snapshot = session.scalar(
            select(schema.DashboardSnapshot)
            .order_by(
                schema.DashboardSnapshot.created_at.desc(),
                schema.DashboardSnapshot.id.desc(),
            )
            .limit(1)
        )
        final_json = snapshot.payload if snapshot else {}
        debate_id = final_json.get("debate_id")
        pack_id = final_json.get("evidence_pack_id")
        judge_synthesis_id = final_json.get("judge_synthesis_id")
        review_id = final_json.get("adversarial_review_id")

        evidence_count = _count(
            session.scalars(
                select(schema.EvidenceItem).where(schema.EvidenceItem.pack_id == pack_id)
            ).all()
        )
        vote_rows = session.scalars(
            select(schema.LlmModelVote).where(schema.LlmModelVote.debate_id == debate_id)
        ).all()
        challenge_rows = session.scalars(
            select(schema.LlmChallenge).where(schema.LlmChallenge.debate_id == debate_id)
        ).all()
        revision_rows = session.scalars(
            select(schema.LlmRevision).where(schema.LlmRevision.debate_id == debate_id)
        ).all()
        judge_rows = session.scalars(
            select(schema.JudgeSynthesis).where(schema.JudgeSynthesis.debate_id == debate_id)
        ).all()
        review_rows = session.scalars(
            select(schema.AdversarialReview).where(schema.AdversarialReview.debate_id == debate_id)
        ).all()
        snapshot_modules = []
        if snapshot is not None:
            snapshot_modules = session.scalars(
                select(schema.SnapshotModule).where(
                    schema.SnapshotModule.snapshot_id == snapshot.snapshot_id
                )
            ).all()

    html_path = paths.project_root / "reports" / P4_HTML_FILENAME
    checks = [
        _check("p4_html_exists", html_path.exists(), str(html_path)),
        _check(
            "final_controller_json_exists",
            bool(final_json),
            snapshot.snapshot_id if snapshot else "",
        ),
        _check("evidence_pack_exists", bool(pack_id and evidence_count), evidence_count),
        _check("four_analyst_votes", len(vote_rows) == 4, len(vote_rows)),
        _check("votes_have_evidence", all(row.evidence_ids for row in vote_rows), len(vote_rows)),
        _check("cross_exam_challenges_exist", bool(challenge_rows), len(challenge_rows)),
        _check("cross_exam_revisions_exist", bool(revision_rows), len(revision_rows)),
        _check(
            "judge_synthesis_exists",
            bool(judge_rows and judge_synthesis_id),
            judge_synthesis_id,
        ),
        _check(
            "adversarial_review_passed",
            any(
                row.review_passed
                and (row.issues or {}).get("review_id") == review_id
                for row in review_rows
            ),
            review_id,
        ),
        _check("snapshot_modules_exist", bool(snapshot_modules), len(snapshot_modules)),
        _check(
            "final_json_has_required_fields",
            _final_json_has_required_fields(final_json),
            sorted(final_json.keys()) if final_json else [],
        ),
        _check(
            "final_json_no_trading_terms",
            _final_json_no_trading_terms(final_json),
            "display payload sanitized",
        ),
        _check(
            "state_constraints_preserved",
            bool(final_json.get("blocked_by")) == bool(final_json.get("publish_constraints")),
            final_json.get("blocked_by"),
        ),
        _check(
            "blocked_by_nonempty_blocks_publish_candidate",
            not final_json.get("blocked_by")
            or (
                final_json.get("publish_allowed") is False
                and final_json.get("publish_scope") != "publish_candidate"
            ),
            {
                "blocked_by": final_json.get("blocked_by"),
                "publish_allowed": final_json.get("publish_allowed"),
                "publish_scope": final_json.get("publish_scope"),
            },
        ),
        _check(
            "publish_scope_matches_blocked_by",
            _publish_scope_matches_blocked_by(final_json),
            {
                "blocked_by": final_json.get("blocked_by"),
                "publish_scope": final_json.get("publish_scope"),
                "revision_integrity": final_json.get("revision_integrity"),
            },
        ),
        _check(
            "watch_only_matches_publish_scope",
            _watch_only_matches_publish_scope(final_json),
            {
                "watch_only": final_json.get("watch_only"),
                "dashboard_only": final_json.get("dashboard_only"),
                "publish_scope": final_json.get("publish_scope"),
            },
        ),
        _check(
            "article_publish_semantics_consistent",
            _article_publish_semantics_consistent(html_path, final_json),
            str(html_path),
        ),
        _check(
            "article_evidence_coverage_complete",
            _article_evidence_coverage_complete(html_path),
            str(html_path),
        ),
        _check(
            "article_runtime_completed_without_errors",
            _article_runtime_completed_without_errors(html_path),
            str(html_path),
        ),
    ]
    return {
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "checks": checks,
        "passed_count": sum(1 for item in checks if item["passed"]),
        "failed_count": sum(1 for item in checks if not item["passed"]),
        "p4_html_path": str(html_path),
        "snapshot_id": snapshot.snapshot_id if snapshot else None,
        "debate_id": debate_id,
        "evidence_pack_id": pack_id,
    }


def _final_json_has_required_fields(payload: dict[str, Any]) -> bool:
    required = {
        "run_id",
        "evidence_pack_id",
        "debate_id",
        "judge_synthesis_id",
        "adversarial_review_id",
        "analyst_vote_ids",
        "challenge_ids",
        "revision_ids",
        "revision_integrity",
        "publish_scope",
        "trend_state",
        "risk_state",
        "dominant_drivers",
        "invalidation_watch",
        "observation_points",
        "data_quality_notes",
        "confidence",
        "confidence_discount",
        "publish_allowed",
        "blocked_by",
        "evidence_ids",
    }
    return required.issubset(payload.keys()) and bool(payload.get("evidence_ids"))


def _final_json_no_trading_terms(payload: dict[str, Any]) -> bool:
    published_fields = {
        key: payload.get(key)
        for key in (
            "trend_state",
            "risk_state",
            "dominant_drivers",
            "invalidation_watch",
            "observation_points",
            "data_quality_notes",
            "minority_objections",
            "state_machine_constraints_applied",
            "publish_constraints",
            "publish_scope",
            "publish_block_reason",
        )
    }
    return "leverage" not in json.dumps(published_fields, ensure_ascii=False).lower()


def _check(name: str, passed: bool, detail: Any) -> dict[str, Any]:
    return {"check": name, "passed": bool(passed), "detail": detail}


def _publish_scope_matches_blocked_by(payload: dict[str, Any]) -> bool:
    scope = payload.get("publish_scope")
    blocked = bool(payload.get("blocked_by"))
    if blocked:
        return scope in {"watch_only", "dashboard_only", "blocked"}
    if payload.get("publish_allowed"):
        return scope == "publish_candidate"
    return scope in {"dashboard_only", "blocked"}


def _watch_only_matches_publish_scope(payload: dict[str, Any]) -> bool:
    scope = payload.get("publish_scope")
    return bool(payload.get("watch_only")) == (scope in {"watch_only", "dashboard_only"})


def _article_publish_semantics_consistent(html_path, payload: dict[str, Any]) -> bool:
    if not html_path.exists():
        return False
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    if payload.get("blocked_by") and "publish_scope</td><td>publish_candidate" in text:
        return False
    return True


def _article_evidence_coverage_complete(html_path) -> bool:
    if not html_path.exists():
        return False
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    return (
        'id="article-evidence-coverage"' in text
        and "coverage_pct</td><td>1.0" in text
        and "missing_count</th>" in text
    )


def _article_runtime_completed_without_errors(html_path) -> bool:
    if not html_path.exists():
        return False
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    return (
        "completed_with_errors" not in text
        and "<tr><td>errors</td><td>-</td></tr>" in text
    )


def _count(rows: list[Any]) -> int:
    return len(rows)
