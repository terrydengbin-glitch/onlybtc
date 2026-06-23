from onlybtc.domain.models import RunStageStatus
from onlybtc.pipeline.run_once import run_once_mock


async def test_run_once_mock_completes_all_stages() -> None:
    run = await run_once_mock(delay_seconds=0, persist=False)

    assert run.status == RunStageStatus.COMPLETED
    assert len(run.stages) == 12
    assert all(stage.status == RunStageStatus.COMPLETED for stage in run.stages)
    assert "trading advice" in run.stages[-1].detail
