from pathlib import Path

from onlybtc.audit import p1_c22, p2_full_chain
from onlybtc.audit.p2_full_chain import run_p2_full_chain_audit
from onlybtc.core.paths import PathResolver
from onlybtc.db.session import Database
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_p2_full_chain_audit_writes_independent_html_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    resolver = PathResolver(project_root=project_root, data_root=data_root)
    db = Database(data_root / "onlybtc-test.sqlite3")
    monkeypatch.setattr(p1_c22, "paths", resolver)
    monkeypatch.setattr(p2_full_chain, "paths", resolver)
    await collect_sources(mode=SourceMode.MOCK, db=db)

    result = await run_p2_full_chain_audit(collect_live=False, run_mode="mock", db=db)

    p1_html = Path(result["p1_c22_html_path"])
    p2_html = Path(result["p2_html_path"])
    assert result["status"] == "completed"
    assert p1_html.exists()
    assert p2_html.exists()
    assert p2_html.name == "p2-radar-quality-report.html"
    assert result["sqlite_checks"]["radar_outputs_ok"] is True
    assert result["sqlite_checks"]["module_json_outputs_ok"] is True
    assert result["sqlite_checks"]["feature_values_ok"] is True
    assert result["uncovered_metric_count"] == 0
    assert "same_run_coverage_score" in result["run_scope"]
    html = p2_html.read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in html
    assert "P2 Radar Quality Report" in html
    assert "Metric Coverage" in html
    assert "Run Contract" in html
    assert "Uncovered Metric Definitions" in html
    assert "Module Quality" in html
    assert "Feature Quality" in html
