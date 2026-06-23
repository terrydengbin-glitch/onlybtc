from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.direct_trend.evidence import BTC_DIRECT_TREND_EVIDENCE_MODULE_ID
from onlybtc.direct_trend.registry import (
    BTC_DIRECT_EVIDENCE_REGISTRY_MODULE_ID,
    build_direct_evidence_registry,
    direct_evidence_registry,
    registry_entry_for_feature,
)


def test_direct_evidence_registry_roles_enforce_boundaries() -> None:
    registry = direct_evidence_registry()

    assert len(registry) == 22
    assert (
        registry_entry_for_feature(
            "btc_direct_trend.price_structure.btc_return_4h"
        ).role
        == "trigger_eligible"
    )
    for feature_id, entry in registry.items():
        if ".oi_impulse_z_" in feature_id or ".funding_" in feature_id:
            assert entry.role != "trigger_eligible"
            assert entry.affects_direction is False
        if ".event_overlay_context." in feature_id:
            assert entry.role in {"trust_cap", "quality_gate"}
            assert entry.affects_direction is False
            assert entry.event_phase_roles["pre_event"] == "trust_cap"


def test_build_direct_evidence_registry_audits_latest_p1_rows(tmp_path) -> None:
    db = Database(tmp_path / "btc-direct-evidence-registry.sqlite3")
    db.init_schema()
    now = datetime.now(UTC)
    registry = direct_evidence_registry()
    with db.session() as session:
        for feature_id in registry:
            session.add(
                schema.FeatureValue(
                    run_id="p1c75-registry-test",
                    module_id=BTC_DIRECT_TREND_EVIDENCE_MODULE_ID,
                    feature_id=feature_id,
                    value=0.1,
                    metadata_json={
                        "freshness_state": "fresh",
                        "source_asof_ts": now.isoformat(),
                        "valid_until": (now + timedelta(minutes=30)).isoformat(),
                    },
                )
            )

    payload = build_direct_evidence_registry(
        evidence_run_id="p1c75-registry-test",
        registry_run_id="p2c43-test",
        db=db,
    )

    assert payload["summary"]["registry_count"] == 22
    assert payload["summary"]["latest_evidence_count"] == 22
    assert payload["summary"]["missing_in_latest"] == []
    assert payload["summary"]["unregistered_latest"] == []
    audit = {item["feature_id"]: item for item in payload["latest_evidence_audit"]}
    assert audit["btc_direct_trend.price_structure.btc_return_4h"]["used_by_default"] is True
    assert (
        audit["btc_direct_trend.orderflow_acceptance.cvd_slope_z"]["ignore_reason"]
        == "acceptance_or_confidence_only"
    )
    assert (
        audit["btc_direct_trend.event_overlay_context.event_trust_cap"]["ignore_reason"]
        == "role_trust_cap_not_direction_trigger"
    )

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "p2c43-test",
                schema.ModuleJsonOutput.module_id == BTC_DIRECT_EVIDENCE_REGISTRY_MODULE_ID,
            )
        )
    assert row is not None
    assert row.payload["summary"]["trigger_eligible_count"] == 4
