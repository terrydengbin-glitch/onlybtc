from pathlib import Path

from onlybtc.audit import p4_radar_coverage
from onlybtc.audit.p4_radar_coverage import run_p4_radar_coverage_audit
from onlybtc.core.paths import PathResolver
from onlybtc.db.session import Database
from onlybtc.radars.registry import RADAR_MODULES
from onlybtc.radars.service import analyze_radars
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_p4_radar_coverage_matrix_reads_all_radar_modules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    resolver = PathResolver(project_root=project_root, data_root=data_root)
    db = Database(data_root / "onlybtc-test.sqlite3")
    monkeypatch.setattr(p4_radar_coverage, "paths", resolver)

    await collect_sources(mode=SourceMode.MOCK, db=db)
    radar = analyze_radars(run_mode="mock", db=db)

    result = run_p4_radar_coverage_audit(
        radar_run_id=radar["run_id"],
        db=db,
    )

    assert result["status"] == "completed"
    assert result["radar_modules_consumed_count"] == len(RADAR_MODULES)
    assert result["radar_module_total"] == len(RADAR_MODULES)
    assert result["signed_event_metrics_consumed_count"] == 4
    assert result["uncovered_metric_count"] == 0
    assert result["evidence_pack_status"] == "not_generated"
    assert result["evidence_pack_missing_feature_count"] > 0
    html = Path(result["html_path"])
    assert html.exists()
    content = html.read_text(encoding="utf-8")
    assert "P4 Radar Coverage Matrix" in content
    assert "macro_event_analyst" in content
    assert "onchain_market_structure_analyst" in content
