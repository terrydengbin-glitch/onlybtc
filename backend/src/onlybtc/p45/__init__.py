"""P4.5 Radar Scored Analyst Writer package.

P4.5 is the lightweight research-writing layer that consumes P3 scored
evidence. It intentionally does not use the legacy P4 Agent/CrossExam/Judge
runtime.
"""

from onlybtc.p45.boundary import (
    ANALYST_MODULES,
    LEGACY_P4_COMPONENTS,
    P45_OUTPUTS,
    P45_UPSTREAM_CONTRACTS,
    phase_boundary,
)
from onlybtc.p45.evidence_pack import (
    P45_EVIDENCE_PACK_MODULE_ID,
    P45_EVIDENCE_PACK_SCHEMA_VERSION,
    build_p45_scored_evidence_pack,
)
from onlybtc.p45.explanations import (
    build_metric_brief,
    catalog_coverage,
    metric_explanation_catalog,
)
from onlybtc.p45.final_writer import (
    P45_FINAL_ARTICLE_MODULE_ID,
    P45_FINAL_ARTICLE_SCHEMA_VERSION,
    run_p45_final_writer,
)
from onlybtc.p45.html_report import P45_HTML_REPORT_FILENAME, run_p45_html_report
from onlybtc.p45.llm_analyst_writer import (
    P45_LLM_ANALYST_ARTICLES_MODULE_ID,
    P45_LLM_ANALYST_ARTICLES_SCHEMA_VERSION,
    run_p45_llm_analyst_writers,
)
from onlybtc.p45.llm_research_writer import (
    P45_LLM_RESEARCH_ARTICLE_MODULE_ID,
    P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION,
    run_p45_llm_research_writer,
)
from onlybtc.p45.writer import (
    P45_ANALYST_ARTICLES_MODULE_ID,
    P45_ANALYST_ARTICLES_SCHEMA_VERSION,
    run_p45_analyst_writers,
)

__all__ = [
    "ANALYST_MODULES",
    "LEGACY_P4_COMPONENTS",
    "P45_OUTPUTS",
    "P45_UPSTREAM_CONTRACTS",
    "phase_boundary",
    "P45_EVIDENCE_PACK_MODULE_ID",
    "P45_EVIDENCE_PACK_SCHEMA_VERSION",
    "build_p45_scored_evidence_pack",
    "build_metric_brief",
    "catalog_coverage",
    "metric_explanation_catalog",
    "P45_FINAL_ARTICLE_MODULE_ID",
    "P45_FINAL_ARTICLE_SCHEMA_VERSION",
    "run_p45_final_writer",
    "P45_HTML_REPORT_FILENAME",
    "run_p45_html_report",
    "P45_LLM_RESEARCH_ARTICLE_MODULE_ID",
    "P45_LLM_RESEARCH_ARTICLE_SCHEMA_VERSION",
    "run_p45_llm_research_writer",
    "P45_LLM_ANALYST_ARTICLES_MODULE_ID",
    "P45_LLM_ANALYST_ARTICLES_SCHEMA_VERSION",
    "run_p45_llm_analyst_writers",
    "P45_ANALYST_ARTICLES_MODULE_ID",
    "P45_ANALYST_ARTICLES_SCHEMA_VERSION",
    "run_p45_analyst_writers",
]
