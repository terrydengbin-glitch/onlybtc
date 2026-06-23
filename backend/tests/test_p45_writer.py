from sqlalchemy import select

from onlybtc.db import schema
from onlybtc.db.session import Database
from onlybtc.p45.evidence_pack import P45_EVIDENCE_PACK_MODULE_ID
from onlybtc.p45.writer import P45_ANALYST_ARTICLES_MODULE_ID, run_p45_analyst_writers


def test_p45_analyst_writers_emit_four_articles(tmp_path) -> None:
    db = Database(tmp_path / "onlybtc-test.sqlite3")
    db.init_schema()
    with db.session() as session:
        session.add(
            schema.ModuleJsonOutput(
                run_id="pack-test",
                module_id=P45_EVIDENCE_PACK_MODULE_ID,
                schema_version="p45.evidence_pack.v1",
                payload=_pack(),
            )
        )

    result = run_p45_analyst_writers(
        pack_id="pack-test",
        article_run_id="articles-test",
        db=db,
    )

    assert result["summary"]["analyst_count"] == 4
    assert result["summary"]["all_reference_evidence"] is True
    assert len(result["analyst_articles"]) == 4
    for article in result["analyst_articles"]:
        assert article["article"]
        assert article["evidence_reference_count"] > 0
        assert article["fallback_used"] is True

    with db.session() as session:
        row = session.scalar(
            select(schema.ModuleJsonOutput).where(
                schema.ModuleJsonOutput.run_id == "articles-test",
                schema.ModuleJsonOutput.module_id == P45_ANALYST_ARTICLES_MODULE_ID,
            )
        )

    assert row is not None
    assert row.payload["summary"]["analyst_count"] == 4


def _pack() -> dict:
    analysts = []
    for analyst_id, module_id in (
        ("macro_event_analyst", "macro_radar"),
        ("liquidity_flow_analyst", "fund_flow"),
        ("microstructure_analyst", "trade_structure_flow"),
        ("onchain_structure_analyst", "onchain_valuation"),
    ):
        analysts.append(
            {
                "analyst_id": analyst_id,
                "radar_modules": [module_id],
                "module_count": 1,
                "metric_count": 2,
                "positive": 1,
                "negative": 1,
                "zero": 0,
                "unavailable": 0,
                "modules": [
                    {
                        "radar_module": module_id,
                        "module_score": 0.0,
                        "module_direction": "mixed",
                        "data_boundary": [],
                        "metrics": [
                            _metric(module_id, "positive", 0.2),
                            _metric(module_id, "negative", -0.2),
                        ],
                    }
                ],
                "data_boundary": [],
            }
        )
    return {
        "schema_version": "p45.evidence_pack.v1",
        "pack_id": "pack-test",
        "p3_run_id": "p3-test",
        "p2_radar_run_id": "radar-test",
        "collect_run_id": "collect-test",
        "analysts": analysts,
        "summary": {},
    }


def _metric(module_id: str, bucket: str, score: float) -> dict:
    return {
        "evidence_id": f"ev-{module_id}-{bucket}",
        "metric_id": f"{module_id}_{bucket}",
        "metric_score": score,
        "score_bucket": bucket,
        "p45_metric_brief": f"{module_id} {bucket} brief",
    }
