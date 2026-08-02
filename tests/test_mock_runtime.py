from __future__ import annotations

from collections.abc import Callable

from rolecheck.config import MockRuntimeConfig
from rolecheck.runtime import MockRuntime
from rolecheck.schemas import CanonicalTeamConfig, TaskSpec


def test_mock_runtime_is_deterministic_for_outputs(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    runtime = MockRuntime(MockRuntimeConfig())
    task = TaskSpec(task_id="task-1", task_text="Return a test artifact.")
    team = team_factory()

    first = runtime.run(task=task, team=team, experiment_id="exp-1", experiment_seed=11)
    second = runtime.run(task=task, team=team, experiment_id="exp-1", experiment_seed=11)

    assert first.mock is True
    assert first.utility is None
    assert first.run_id == second.run_id
    assert first.role_output_hashes == second.role_output_hashes
    assert first.seeds == second.seeds
