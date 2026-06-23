from pathlib import Path

from onlybtc.audit import p1_c22, p2_full_chain, p3_full_chain
from onlybtc.audit.p3_full_chain import run_p3_full_chain_audit
from onlybtc.core.paths import PathResolver
from onlybtc.db.session import Database
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_p3_full_chain_audit_writes_three_independent_html_reports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    data_root = tmp_path / "data"
    resolver = PathResolver(project_root=project_root, data_root=data_root)
    db = Database(data_root / "onlybtc-test.sqlite3")
    monkeypatch.setattr(p1_c22, "paths", resolver)
    monkeypatch.setattr(p2_full_chain, "paths", resolver)
    monkeypatch.setattr(p3_full_chain, "paths", resolver)
    await collect_sources(mode=SourceMode.MOCK, db=db)

    result = await run_p3_full_chain_audit(collect_live=False, run_mode="mock", db=db)

    p1_html = Path(result["p1_c22_html_path"])
    p2_html = Path(result["p2_html_path"])
    p3_html = Path(result["p3_html_path"])
    assert result["status"] == "completed"
    assert p1_html.exists()
    assert p2_html.exists()
    assert p3_html.exists()
    assert p3_html.name == "p3-algorithm-audit-report.html"
    assert result["sqlite_checks"]["features_ok"] is True
    assert result["sqlite_checks"]["scored_evidence_ok"] is True
    assert result["sqlite_checks"]["invalidations_ok"] is True
    html = p3_html.read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in html
    assert "P3 Algorithm Audit Report" in html
    assert "Pipeline Summary" in html
    assert "SQLite Contract" in html
    assert "Scored Radar Modules" in html
    assert "Scored Metric Evidence" in html
    assert "P4.5 Analyst Input Precheck" in html
    assert "module_direction" in html
    assert "metric_explanation" in html
    assert "base_metric_score" in html
    assert "base_direction" in html
    assert "semantic_rule_id" in html
    assert "semantic_warning" in html
    assert "Anomaly Details" in html
    assert "Divergence Details" in html
    assert "Event Window Details" in html
    assert "Invalidation Events" in html
