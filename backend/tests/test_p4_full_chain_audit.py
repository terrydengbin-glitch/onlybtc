from pathlib import Path

from onlybtc.audit import p1_c22, p2_full_chain, p3_full_chain, p4_dod, p4_full_chain
from onlybtc.audit.p4_dod import run_p4_dod_check
from onlybtc.audit.p4_full_chain import run_p4_full_chain_audit
from onlybtc.core.paths import PathResolver
from onlybtc.db.session import Database
from onlybtc.sources.models import SourceMode
from onlybtc.sources.service import collect_sources


async def test_p4_full_chain_audit_writes_four_independent_html_reports(
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
    monkeypatch.setattr(p4_full_chain, "paths", resolver)
    monkeypatch.setattr(p4_dod, "paths", resolver)
    await collect_sources(mode=SourceMode.MOCK, db=db)

    result = await run_p4_full_chain_audit(
        collect_live=False,
        run_mode="mock",
        runtime_mode="mock",
        article_runtime_mode="mock",
        db=db,
    )

    p1_html = Path(result["p1_c22_html_path"])
    p2_html = Path(result["p2_html_path"])
    p3_html = Path(result["p3_html_path"])
    p4_html = Path(result["p4_html_path"])
    assert result["status"] == "completed"
    assert result["article_status"] == "completed"
    assert p1_html.exists()
    assert p2_html.exists()
    assert p3_html.exists()
    assert p4_html.exists()
    assert p4_html.name == "p4-controller-audit-report.html"
    assert result["evidence_pack_id"]
    assert result["debate_id"]
    assert result["judge_synthesis_id"]
    assert result["adversarial_review_id"]
    assert result["snapshot_id"]
    html = p4_html.read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in html
    assert 'id="research-report"' in html
    assert 'id="analyst-research-briefs"' in html
    assert 'id="decision-chain"' in html
    assert 'id="audit-appendix"' in html
    assert "数据源与证据附录" in html
    assert "article_runtime_mode" in html
    assert "article_status" in html
    assert 'id="llm-readable-articles"' in html
    assert "p4.analyst_readable_article.v1" in html
    assert "p4.final_observation_article.v1" in html
    assert "Article Agent Runtime Trace" in html
    assert 'id="article-evidence-coverage"' in html
    assert "Article Evidence Coverage Summary" in html
    assert 'id="all-agent-runtime-audit"' in html
    assert "llm_runtime_integrity" in html
    assert "fallback_used" in html
    assert "交叉质询 Revision" in html
    assert "Revision Gate / Publish Scope" in html
    assert "revision_integrity" in html
    assert "Evidence Pack" in html
    assert result["publish_allowed"] in {True, False}

    dod = run_p4_dod_check(db=db)
    assert dod["status"] == "passed"
    assert dod["failed_count"] == 0
