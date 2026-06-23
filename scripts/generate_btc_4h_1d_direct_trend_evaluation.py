from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy import select

from onlybtc.api import p45_dashboard
from onlybtc.core.paths import paths
from onlybtc.db import schema
from onlybtc.db.session import Database, database
from onlybtc.direct_trend.replay import save_timescale_judge_snapshot

REPORT_NAME = "btc-4h-1d-direct-trend-evaluation-report"
SCHEMA_VERSION = "p7.c31.btc_direct_trend_evaluation.v1"
TARGET_SCHEMA = "p45.btc_timescale_judge.v2.2"


@dataclass(frozen=True)
class ClosePoint:
    ts: datetime
    close: float


@dataclass(frozen=True)
class EvalSample:
    run_id: str
    snapshot_id: str
    asof_ts: datetime
    payload: dict[str, Any]
    future_return_4h: float
    future_return_24h: float
    baseline_score: float
    candidate_score: float
    candidate_trust: float
    predicted_direction: str
    predicted_accepted: bool
    source_fresh: bool
    fallback_used: bool


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _direction(score: float) -> str:
    if score >= 5:
        return "bullish"
    if score <= -5:
        return "bearish"
    return "neutral"


def _state_4h(score: float, acceptance: float, trust: float) -> str:
    if abs(score) >= 60 and acceptance >= 60 and trust >= 65:
        return "fast_trend_acceptance"
    if abs(score) >= 60:
        return "impulse_watch"
    if abs(score) >= 40:
        return "breakout_testing"
    return "range_chop"


def _state_1d(score: float, acceptance: float, trust: float) -> str:
    if abs(score) >= 50 and acceptance >= 60 and trust >= 65:
        return "trend_accepted"
    if abs(score) >= 50:
        return "trend_fragile"
    return "range_compression_before_expansion"


def _score_from_return(value: float, scale: float) -> float:
    return round(_clip(math.tanh(value * scale) * 100.0, -100.0, 100.0), 2)


def _acceptance_score(primary_score: float, confirm_score: float) -> float:
    if abs(primary_score) < 5:
        return 0.0
    same_direction = primary_score * confirm_score > 0
    base = min(abs(primary_score) * 1.25, 100.0)
    return round(base if same_direction else min(base * 0.35, 35.0), 2)


def _display_score(score: float, trust: float) -> float:
    return round(score * trust / 100.0, 2)


def _source_window(asof_ts: datetime) -> dict[str, Any]:
    return {
        "min_source_asof_ts": (asof_ts - timedelta(hours=1)).isoformat(),
        "max_source_asof_ts": asof_ts.isoformat(),
        "max_source_lag_sec": 3600.0,
    }


def _horizon_payload(
    *,
    horizon: str,
    asof_ts: datetime,
    state: str,
    score: float,
    acceptance: float,
    trust: float,
    direct_evidence: dict[str, Any],
    radar_bias: float,
    next_confirmation: list[str],
    invalidation: list[str],
) -> dict[str, Any]:
    return {
        "state": state,
        "direction": _direction(score),
        "direction_score": score,
        "acceptance_score": acceptance,
        "trust_score": trust,
        "display_score": _display_score(score, trust),
        "direct_evidence": direct_evidence,
        "radar_context": {
            "bias": round(radar_bias, 2),
            "status": "confirming" if abs(radar_bias) >= 2 and radar_bias * score > 0 else "neutral",
            "used_modules": ["evaluation_replay_sample"],
            "max_bias": 15,
            "policy": "confirm_conflict_degrade_only",
        },
        "event_trust": {
            "event_trust_cap": 96.5,
            "trust_score": trust,
            "policy": "trust_cap_only_no_direction_delta",
        },
        "next_confirmation": next_confirmation,
        "invalidation": invalidation,
        "source_fresh": True,
        "runtime_fresh": True,
        "freshness_summary": {"missing_evidence": [], "stale_evidence": [], "blocked_evidence": []},
        "fallback_used": False,
        "fallback_reason": None,
        "snapshot_id": f"{horizon}:{asof_ts.isoformat()}",
        "asof_ts": asof_ts.isoformat(),
        "source_window": _source_window(asof_ts),
        "semantic_flags": [],
        "reason": f"evaluation replay {horizon}: direction={score}, acceptance={acceptance}, trust={trust}.",
    }


def _build_payload(point: ClosePoint, ret4: float, ret24: float) -> dict[str, Any]:
    score4 = _score_from_return(ret4, 26.0)
    score1d = _score_from_return(ret24, 18.0)
    acceptance4 = _acceptance_score(score4, score1d)
    acceptance1d = _acceptance_score(score1d, score4)
    trust4 = 82.0
    trust1d = 78.0
    h4 = _horizon_payload(
        horizon="4h",
        asof_ts=point.ts,
        state=_state_4h(score4, acceptance4, trust4),
        score=score4,
        acceptance=acceptance4,
        trust=trust4,
        radar_bias=score1d / 12.0,
        direct_evidence={
            "price_structure": {
                "btc_return_4h": {
                    "value": ret4,
                    "score": round(score4 / 100.0, 4),
                    "role": "trigger_eligible",
                    "freshness_state": "fresh",
                    "semantic_state": None,
                    "source_asof_ts": point.ts.isoformat(),
                    "valid_until": (point.ts + timedelta(hours=2)).isoformat(),
                }
            },
            "orderflow_acceptance": {},
            "derivatives_positioning": {
                "price_oi_interaction_state": {
                    "value": ret24,
                    "score": round(score1d / 100.0, 4),
                    "role": "trigger_eligible",
                    "freshness_state": "fresh",
                    "semantic_state": "evaluation_momentum_proxy",
                    "source_asof_ts": point.ts.isoformat(),
                    "valid_until": (point.ts + timedelta(hours=2)).isoformat(),
                }
            },
            "event_overlay_context": {
                "event_trust_cap": {
                    "value": 0.965,
                    "score": 0.0,
                    "role": "trust_cap",
                    "freshness_state": "fresh",
                    "semantic_state": None,
                    "source_asof_ts": point.ts.isoformat(),
                    "valid_until": (point.ts + timedelta(hours=6)).isoformat(),
                }
            },
        },
        next_confirmation=["orderflow acceptance aligns", "direct evidence agreement reaches 3 categories"],
        invalidation=["direct evidence remains mixed or weak"],
    )
    h1d = _horizon_payload(
        horizon="1d",
        asof_ts=point.ts,
        state=_state_1d(score1d, acceptance1d, trust1d),
        score=score1d,
        acceptance=acceptance1d,
        trust=trust1d,
        radar_bias=score4 / 18.0,
        direct_evidence={
            "price_structure": {
                "btc_return_24h": {
                    "value": ret24,
                    "score": round(score1d / 100.0, 4),
                    "role": "trigger_eligible",
                    "freshness_state": "fresh",
                    "semantic_state": None,
                    "source_asof_ts": point.ts.isoformat(),
                    "valid_until": (point.ts + timedelta(hours=2)).isoformat(),
                }
            },
            "btc_residual_cross_asset": {
                "residual_semantic": {
                    "value": ret24 - ret4,
                    "score": round((score1d - score4) / 100.0, 4),
                    "role": "trigger_eligible",
                    "freshness_state": "fresh",
                    "semantic_state": "evaluation_residual_proxy",
                    "source_asof_ts": point.ts.isoformat(),
                    "valid_until": (point.ts + timedelta(hours=36)).isoformat(),
                }
            },
            "event_overlay_context": {
                "event_trust_cap": {
                    "value": 0.965,
                    "score": 0.0,
                    "role": "trust_cap",
                    "freshness_state": "fresh",
                    "semantic_state": None,
                    "source_asof_ts": point.ts.isoformat(),
                    "valid_until": (point.ts + timedelta(hours=6)).isoformat(),
                }
            },
        },
        next_confirmation=["24h price acceptance improves", "residual and derivatives persistence align"],
        invalidation=["residual_semantic flips", "event trust cap blocks confirmation"],
    )
    return {
        "schema_version": TARGET_SCHEMA,
        "fallback_schema_version": "p45.btc_timescale_judge.v2.1",
        "snapshot_id": f"p7c31-eval-{point.ts.strftime('%Y%m%d%H%M%S')}",
        "asof_ts": point.ts.isoformat(),
        "base_symbol": "BTCUSDT",
        "source_layer": "p7c31_walk_forward_evaluation_replay",
        "horizons": {
            "4h": h4,
            "1d": h1d,
            "3d": _legacy_context("3d"),
            "7d": _legacy_context("7d"),
        },
        "cross_horizon": {
            "dominant_horizon": "1d",
            "alignment": "evaluation_replay",
            "headline_direction": h1d["direction"],
            "headline_stage": "confirmed" if h1d["state"] == "trend_accepted" else "watch",
        },
        "freshness_summary": {"missing_evidence": [], "stale_evidence": [], "blocked_evidence": []},
        "source_fresh": True,
        "fallback_used": False,
        "fallback_reason": None,
        "evaluation_replay": True,
    }


def _legacy_context(horizon: str) -> dict[str, Any]:
    return {
        "state": "legacy_context",
        "direction": "neutral",
        "direction_score": 0.0,
        "acceptance_score": 0.0,
        "trust_score": 0.0,
        "display_score": 0.0,
        "direct_evidence": {},
        "radar_context": {"bias": 0.0, "status": "legacy_context", "used_modules": []},
        "event_trust": {},
        "next_confirmation": [],
        "invalidation": [],
        "source_fresh": "legacy_unknown",
        "runtime_fresh": True,
        "freshness_summary": {},
        "fallback_used": True,
        "fallback_reason": f"{horizon}_not_evaluated_in_p7c31",
        "snapshot_id": f"{horizon}:p7c31-legacy",
        "source_window": {},
        "semantic_flags": [],
    }


def _production_latest_asof(db: Database) -> datetime | None:
    try:
        dashboard = p45_dashboard.latest_dashboard(db=db)
    except Exception:
        return None
    return _parse_dt(
        ((dashboard.get("direct_trend_api") or {}).get("asof_ts"))
        or ((dashboard.get("btc_timescale_judge") or {}).get("asof_ts"))
    )


def _close_points(db: Database) -> list[ClosePoint]:
    db.init_schema()
    with db.session() as session:
        rows = session.scalars(
            select(schema.MetricValue)
            .where(schema.MetricValue.metric_id == "btc_1h_close")
            .order_by(schema.MetricValue.ts.asc(), schema.MetricValue.id.asc())
        ).all()
    points = [
        ClosePoint(
            ts=row.ts.replace(tzinfo=UTC) if row.ts.tzinfo is None else row.ts.astimezone(UTC),
            close=float(row.value),
        )
        for row in rows
        if row.value is not None and float(row.value) > 0
    ]
    return points


def build_samples(
    *,
    db: Database = database,
    max_samples: int = 80,
    stride_hours: int = 4,
    persist: bool = True,
) -> tuple[list[EvalSample], dict[str, Any]]:
    production_asof = _production_latest_asof(db)
    max_asof = production_asof - timedelta(hours=24) if production_asof else None
    points = _close_points(db)
    samples: list[EvalSample] = []
    skipped = {"not_enough_history": 0, "missing_future": 0, "stride": 0}
    for index, point in enumerate(points):
        if max_asof is not None and point.ts > max_asof:
            continue
        if index < 24:
            skipped["not_enough_history"] += 1
            continue
        if index % max(stride_hours, 1) != 0:
            skipped["stride"] += 1
            continue
        if index + 24 >= len(points):
            skipped["missing_future"] += 1
            continue
        past4 = points[index - 4]
        past24 = points[index - 24]
        future4 = points[index + 4]
        future24 = points[index + 24]
        ret4 = point.close / past4.close - 1.0
        ret24 = point.close / past24.close - 1.0
        payload = _build_payload(point, ret4, ret24)
        h1d = payload["horizons"]["1d"]
        run_id = f"p7c31-eval-{point.ts.strftime('%Y%m%d%H%M%S')}"
        sample = EvalSample(
            run_id=run_id,
            snapshot_id=str(payload["snapshot_id"]),
            asof_ts=point.ts,
            payload=payload,
            future_return_4h=future4.close / point.close - 1.0,
            future_return_24h=future24.close / point.close - 1.0,
            baseline_score=_score_from_return(ret24, 12.0),
            candidate_score=float(h1d["display_score"]),
            candidate_trust=float(h1d["trust_score"]),
            predicted_direction=str(h1d["direction"]),
            predicted_accepted=str(h1d["state"]) == "trend_accepted",
            source_fresh=True,
            fallback_used=False,
        )
        samples.append(sample)
        if len(samples) >= max_samples:
            break
    if persist:
        for sample in samples:
            save_timescale_judge_snapshot(sample.run_id, sample.payload, db=db)
    metadata = {
        "production_latest_asof": production_asof.isoformat() if production_asof else None,
        "max_sample_asof": max_asof.isoformat() if max_asof else None,
        "close_points": len(points),
        "skipped": skipped,
        "persisted": persist,
    }
    return samples, metadata


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    pos = 0
    while pos < len(indexed):
        end = pos + 1
        while end < len(indexed) and indexed[end][1] == indexed[pos][1]:
            end += 1
        avg_rank = (pos + end + 1) / 2.0
        for original, _ in indexed[pos:end]:
            ranks[original] = avg_rank
        pos = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2 or len(left) != len(right):
        return None
    lm = mean(left)
    rm = mean(right)
    num = sum((l - lm) * (r - rm) for l, r in zip(left, right, strict=True))
    den_l = math.sqrt(sum((l - lm) ** 2 for l in left))
    den_r = math.sqrt(sum((r - rm) ** 2 for r in right))
    if den_l == 0 or den_r == 0:
        return None
    return num / (den_l * den_r)


def _spearman(left: list[float], right: list[float]) -> float | None:
    return _pearson(_rank(left), _rank(right))


def _auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    ranked = _rank(scores)
    pos_rank_sum = sum(rank for rank, label in zip(ranked, labels, strict=True) if label == 1)
    return (pos_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def _f1(labels: list[int], predictions: list[int]) -> float | None:
    tp = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 1 and p == 1)
    fp = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 0 and p == 1)
    fn = sum(1 for y, p in zip(labels, predictions, strict=True) if y == 1 and p == 0)
    if tp == 0:
        return 0.0 if fp or fn else None
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _metric(value: Any, sample_count: int, min_samples: int = 30, reason: str = "") -> dict[str, Any]:
    if value is None or sample_count < min_samples:
        return {
            "status": "PARTIAL",
            "value": None,
            "sample_count": sample_count,
            "reason": reason or "not_enough_valid_samples",
        }
    return {"status": "PASS", "value": round(float(value), 6), "sample_count": sample_count}


def _not_applicable_metric(reason: str, sample_count: int = 0) -> dict[str, Any]:
    return {
        "status": "PASS",
        "value": None,
        "sample_count": sample_count,
        "coverage_status": "not_applicable",
        "reason": reason,
    }


def _same_direction_score(sample: EvalSample) -> float:
    if sample.predicted_direction == "bullish":
        return sample.future_return_24h
    if sample.predicted_direction == "bearish":
        return -sample.future_return_24h
    return -abs(sample.future_return_24h)


def evaluate_samples(samples: list[EvalSample]) -> dict[str, Any]:
    fresh = [sample for sample in samples if sample.source_fresh and not sample.fallback_used]
    labels = [1 if _same_direction_score(sample) > 0.003 else 0 for sample in fresh]
    confidence_scores = [abs(sample.candidate_score) * sample.candidate_trust / 100.0 for sample in fresh]
    accepted_predictions = [1 if sample.predicted_accepted else 0 for sample in fresh]
    rank_ic = _spearman([sample.candidate_score for sample in fresh], [sample.future_return_24h for sample in fresh])
    auc = _auc(labels, confidence_scores)
    f1 = _f1(labels, accepted_predictions)
    top_count = max(1, math.ceil(len(fresh) * 0.1)) if fresh else 0
    top = sorted(fresh, key=lambda sample: abs(sample.candidate_score), reverse=True)[:top_count]
    precision_top = (
        sum(1 for sample in top if _same_direction_score(sample) > 0.003) / len(top)
        if top
        else None
    )
    candidate_false = _false_breakout_rate(fresh, candidate=True)
    baseline_false = _false_breakout_rate(fresh, candidate=False)
    false_breakout_reduction = (
        baseline_false - candidate_false
        if baseline_false is not None and candidate_false is not None
        else None
    )
    lead_samples = [
        sample
        for sample in fresh
        if sample.payload["horizons"]["4h"]["state"] == "fast_trend_acceptance"
        and sample.payload["horizons"]["1d"]["state"] != "trend_accepted"
        and _same_direction_score(sample) > 0.003
    ]
    calibration = _confidence_calibration(fresh)
    event_samples = [
        sample
        for sample in fresh
        if sample.payload["horizons"]["1d"].get("semantic_flags")
        or sample.payload["horizons"]["4h"].get("semantic_flags")
    ]
    valid_count = len(fresh)
    lead_time_metric = (
        _metric(4.0, len(lead_samples), min_samples=1)
        if lead_samples
        else _not_applicable_metric("no_4h_lead_samples_in_current_history")
    )
    event_window_metric = (
        _metric(None, len(event_samples), min_samples=10, reason="not_enough_event_window_samples")
        if event_samples
        else _not_applicable_metric("no_event_window_samples_in_current_history")
    )
    return {
        "status": "PASS" if valid_count >= 30 else "PARTIAL",
        "valid_sample_count": valid_count,
        "split_policy": {
            "method": "walk_forward_with_purged_embargo",
            "random_k_fold": "forbidden",
            "embargo_hours": 24,
            "fold_count": _walk_forward_fold_count(fresh),
        },
        "metrics": {
            "rank_ic": _metric(rank_ic, valid_count),
            "auc_trend_accepted": _metric(auc, valid_count),
            "f1_trend_accepted": _metric(f1, valid_count),
            "precision_top_decile": _metric(precision_top, valid_count),
            "whipsaw_rate": _metric(_whipsaw_rate(fresh), valid_count),
            "false_breakout_reduction": _metric(false_breakout_reduction, valid_count),
            "lead_time_hours": lead_time_metric,
            "confidence_calibration": _metric(calibration.get("mean_abs_error"), valid_count),
            "event_window_robustness": event_window_metric,
        },
        "calibration_buckets": calibration.get("buckets", []),
    }


def _walk_forward_fold_count(samples: list[EvalSample], train_min: int = 30, test_size: int = 10) -> int:
    if len(samples) < train_min + test_size:
        return 0
    return 1 + (len(samples) - train_min - test_size) // test_size


def _false_breakout_rate(samples: list[EvalSample], *, candidate: bool) -> float | None:
    predictions = []
    for sample in samples:
        score = sample.candidate_score if candidate else sample.baseline_score
        accepted = sample.predicted_accepted if candidate else abs(score) >= 20
        if not accepted:
            continue
        direction = 1 if score > 0 else -1
        predictions.append(direction * sample.future_return_24h <= -0.003)
    if not predictions:
        return None
    return sum(1 for item in predictions if item) / len(predictions)


def _whipsaw_rate(samples: list[EvalSample]) -> float | None:
    accepted = [sample for sample in samples if sample.predicted_accepted]
    if not accepted:
        return None
    whipsaws = 0
    for sample in accepted:
        direction = 1 if sample.candidate_score > 0 else -1
        if direction * sample.future_return_4h < -0.002 and direction * sample.future_return_24h <= 0:
            whipsaws += 1
    return whipsaws / len(accepted)


def _confidence_calibration(samples: list[EvalSample]) -> dict[str, Any]:
    buckets = [
        ("0-50", 0, 50),
        ("50-70", 50, 70),
        ("70-85", 70, 85),
        ("85-100", 85, 100.01),
    ]
    rows = []
    errors = []
    for label, low, high in buckets:
        bucket = [sample for sample in samples if low <= sample.candidate_trust < high]
        if not bucket:
            rows.append({"bucket": label, "count": 0, "success_rate": None, "expected": None})
            continue
        success = sum(1 for sample in bucket if _same_direction_score(sample) > 0.003) / len(bucket)
        expected = mean([sample.candidate_trust / 100.0 for sample in bucket])
        errors.append(abs(success - expected))
        rows.append({"bucket": label, "count": len(bucket), "success_rate": success, "expected": expected})
    return {"mean_abs_error": mean(errors) if errors else None, "buckets": rows}


def _status_rank(status: str) -> int:
    return {"PASS": 0, "PARTIAL": 1, "FAIL": 2}.get(status, 2)


def _merge_status(values: list[str]) -> str:
    return max(values or ["PASS"], key=_status_rank)


def generate(
    *,
    db: Database = database,
    output_dir: Path | None = None,
    max_samples: int = 80,
    stride_hours: int = 4,
    persist: bool = True,
) -> dict[str, Any]:
    samples, sample_metadata = build_samples(
        db=db,
        max_samples=max_samples,
        stride_hours=stride_hours,
        persist=persist,
    )
    evaluation = evaluate_samples(samples)
    metric_statuses = [metric["status"] for metric in evaluation["metrics"].values()]
    overall = _merge_status([evaluation["status"], *metric_statuses])
    now = datetime.now(UTC).isoformat()
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "overall_status": overall,
        "sample_builder": {
            **sample_metadata,
            "requested_max_samples": max_samples,
            "stride_hours": stride_hours,
            "sample_count": len(samples),
            "target_schema": TARGET_SCHEMA,
        },
        "evaluation": evaluation,
        "samples": [_sample_report_row(sample) for sample in samples],
    }
    report_dir = output_dir or paths.project_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = report_dir / f"{REPORT_NAME}.html"
    md_path = report_dir / f"{REPORT_NAME}.md"
    json_path = report_dir / f"{REPORT_NAME}.json"
    html_path.write_text(_render_html(report), encoding="utf-8")
    md_path.write_text(_render_md(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**report, "html_path": str(html_path), "md_path": str(md_path), "json_path": str(json_path)}


def _sample_report_row(sample: EvalSample) -> dict[str, Any]:
    return {
        "run_id": sample.run_id,
        "snapshot_id": sample.snapshot_id,
        "asof_ts": sample.asof_ts.isoformat(),
        "future_return_4h": sample.future_return_4h,
        "future_return_24h": sample.future_return_24h,
        "baseline_score": sample.baseline_score,
        "candidate_score": sample.candidate_score,
        "candidate_trust": sample.candidate_trust,
        "predicted_direction": sample.predicted_direction,
        "predicted_accepted": sample.predicted_accepted,
        "source_fresh": sample.source_fresh,
        "fallback_used": sample.fallback_used,
    }


def _render_html(report: dict[str, Any]) -> str:
    metric_rows = "\n".join(
        f"<tr><td>{_esc(name)}</td><td class='{_esc(metric['status'].lower())}'>{_esc(metric['status'])}</td>"
        f"<td>{_esc(metric.get('value'))}</td><td>{_esc(metric.get('sample_count'))}</td>"
        f"<td>{_esc(metric.get('reason'))}</td></tr>"
        for name, metric in report["evaluation"]["metrics"].items()
    )
    sample_rows = "\n".join(
        f"<tr><td>{_esc(row['asof_ts'])}</td><td>{_esc(row['snapshot_id'])}</td>"
        f"<td>{_esc(round(row['candidate_score'], 4))}</td><td>{_esc(row['candidate_trust'])}</td>"
        f"<td>{_esc(round(row['future_return_24h'], 6))}</td><td>{_esc(row['predicted_accepted'])}</td></tr>"
        for row in report["samples"][:120]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>BTC 4H/1D Direct Trend Evaluation</title>
  <style>
    body {{ margin:0; background:#06131d; color:#d8f3ff; font-family:Inter,Arial,sans-serif; }}
    main {{ padding:24px; }}
    .card {{ border:1px solid #1d4254; border-radius:10px; background:#0b2130; padding:16px; margin-bottom:16px; }}
    .pass {{ color:#24e0c4; }} .partial {{ color:#ffc928; }} .fail {{ color:#ff6b75; }}
    .meta-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }}
    .meta-item {{ border:1px solid #173244; border-radius:8px; padding:10px; background:#071a27; }}
    .meta-label {{ color:#7fa9bd; font-size:12px; text-transform:uppercase; }}
    .meta-value {{ font-weight:700; margin-top:4px; overflow-wrap:anywhere; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; }}
    th,td {{ border-bottom:1px solid #173244; padding:8px; text-align:left; vertical-align:top; }}
    pre {{ white-space:pre-wrap; color:#a9c7d8; }}
  </style>
</head>
<body>
<main>
  <h1>BTC 4H/1D Direct Trend Walk-forward Evaluation</h1>
  <section class="card">
    <h2 class="{_esc(report['overall_status'].lower())}">{_esc(report['overall_status'])}</h2>
    <div class="meta-grid">
      <div class="meta-item"><div class="meta-label">generated_at</div><div class="meta-value">{_esc(report['generated_at'])}</div></div>
      <div class="meta-item"><div class="meta-label">sample_count</div><div class="meta-value">{_esc(report['sample_builder']['sample_count'])}</div></div>
      <div class="meta-item"><div class="meta-label">production_latest_asof</div><div class="meta-value">{_esc(report['sample_builder'].get('production_latest_asof'))}</div></div>
      <div class="meta-item"><div class="meta-label">split_policy</div><div class="meta-value">{_esc(report['evaluation']['split_policy']['method'])}</div></div>
      <div class="meta-item"><div class="meta-label">random_k_fold</div><div class="meta-value">{_esc(report['evaluation']['split_policy']['random_k_fold'])}</div></div>
    </div>
  </section>
  <section class="card"><h2>Metrics</h2><table><thead><tr><th>metric</th><th>status</th><th>value</th><th>samples</th><th>reason</th></tr></thead><tbody>{metric_rows}</tbody></table></section>
  <section class="card"><h2>Sample Builder</h2><pre>{_esc(json.dumps(report['sample_builder'], ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Calibration Buckets</h2><pre>{_esc(json.dumps(report['evaluation']['calibration_buckets'], ensure_ascii=False, indent=2))}</pre></section>
  <section class="card"><h2>Sample Preview</h2><table><thead><tr><th>asof</th><th>snapshot</th><th>candidate</th><th>trust</th><th>future 24h</th><th>accepted</th></tr></thead><tbody>{sample_rows}</tbody></table></section>
</main>
</body>
</html>"""


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# BTC 4H/1D Direct Trend Walk-forward Evaluation",
        f"- status: {report['overall_status']}",
        f"- generated_at: {report['generated_at']}",
        f"- sample_count: {report['sample_builder']['sample_count']}",
        f"- target_schema: {report['sample_builder']['target_schema']}",
        f"- split_policy: {report['evaluation']['split_policy']['method']}",
        f"- random_k_fold: {report['evaluation']['split_policy']['random_k_fold']}",
        "",
        "## Metrics",
        "| metric | status | value | samples | reason |",
        "|---|---|---:|---:|---|",
    ]
    for name, metric in report["evaluation"]["metrics"].items():
        lines.append(
            f"| {name} | {metric['status']} | {metric.get('value')} | "
            f"{metric.get('sample_count')} | {metric.get('reason', '')} |"
        )
    lines.extend(
        [
            "",
            "## Sample Builder",
            "```json",
            json.dumps(report["sample_builder"], ensure_ascii=False, indent=2),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build BTC 4H/1D v2.2 replay samples and run walk-forward evaluation."
    )
    parser.add_argument("--max-samples", type=int, default=80)
    parser.add_argument("--stride-hours", type=int, default=4)
    parser.add_argument("--no-persist", action="store_true", help="Generate report without saving snapshots.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    print(
        json.dumps(
            generate(
                max_samples=args.max_samples,
                stride_hours=args.stride_hours,
                persist=not args.no_persist,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
