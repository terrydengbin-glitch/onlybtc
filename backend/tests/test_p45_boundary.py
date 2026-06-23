from onlybtc.p45.boundary import ANALYST_MODULES, LEGACY_P4_COMPONENTS, phase_boundary
from onlybtc.radars.registry import RADAR_MODULES


def test_p45_boundary_covers_all_radar_modules_once() -> None:
    expected = {module.module_id for module in RADAR_MODULES}
    covered = [module_id for modules in ANALYST_MODULES.values() for module_id in modules]

    assert set(covered) == expected
    assert len(covered) == len(set(covered))


def test_p45_boundary_excludes_legacy_p4_runtime() -> None:
    boundary = phase_boundary()

    assert boundary["phase"] == "P4.5"
    assert boundary["rules"]["does_not_use_agent_debate"] is True
    assert boundary["rules"]["does_not_use_judge_or_adversarial_review"] is True
    assert "judge_synthesis" in LEGACY_P4_COMPONENTS
    assert "p3_scored_metric_evidence" in boundary["upstream_contracts"]["p3"]
