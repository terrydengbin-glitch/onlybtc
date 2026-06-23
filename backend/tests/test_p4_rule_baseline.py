from pathlib import Path

from onlybtc.algorithms.p3 import detect_event_windows
from onlybtc.db.session import Database
from onlybtc.p4.constants import ANALYST_MODULES
from onlybtc.p4.evidence_pack import build_p4_evidence_pack
from onlybtc.p4.rule_baseline import build_rule_baseline
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_rule_baseline_consumes_pack_features_events_and_quality(tmp_path: Path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)
    p3_events = detect_event_windows(run_id="p3-baseline-test", run_mode="mock", db=db)
    pack = build_p4_evidence_pack(
        radar_run_id=radar["run_id"],
        p3_run_id=p3_events["run_id"],
        pack_id="p4-baseline-pack-test",
        db=db,
    )

    baseline = build_rule_baseline(pack_id=pack["pack_id"], db=db)

    assert baseline["status"] == "completed"
    assert baseline["schema_version"] == "p4.rule_baseline.v1"
    assert baseline["pack_id"] == pack["pack_id"]
    assert baseline["controller_run_id"] == p3_events["run_id"]
    assert baseline["baseline_signal"] in {"bullish", "bearish", "mixed", "neutral"}
    assert 0 <= baseline["baseline_confidence"] <= 1
    assert 0 <= baseline["confidence_discount"] <= 0.65
    assert len(baseline["module_baselines"]) == len(RADAR_MODULES)
    assert set(baseline["analyst_context"]) == set(ANALYST_MODULES)
    assert baseline["coverage"]["p2_radar_evidence_count"] == pack["radar_feature_evidence_count"]
    assert baseline["coverage"]["p3_event_evidence_count"] == pack["p3_event_evidence_count"]
    assert baseline["coverage"]["missing_evidence_count"] == 0
    assert baseline["coverage"]["ignored_provider_required_missing_count"] == 4
    assert baseline["risk_constraints"]
    event_constraints = [
        constraint
        for constraint in baseline["risk_constraints"]
        if constraint["constraint"] == "event_window_publish_constraint"
    ]
    assert event_constraints
    assert all(constraint["gate_level"] == "watch" for constraint in event_constraints)
    assert not any(
        constraint["constraint"] == "missing_primary_signal_evidence"
        for constraint in baseline["risk_constraints"]
    )
    assert not any(
        reason["reason"] == "missing_evidence"
        for reason in baseline["confidence_discount_reasons"]
    )
    assert any(
        constraint["constraint"] == "event_window_publish_constraint"
        for constraint in baseline["risk_constraints"]
    )
    for analyst_id, context in baseline["analyst_context"].items():
        assert context["evidence_count"] > 0, analyst_id
        assert context["evidence_ids"]
