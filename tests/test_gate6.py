from __future__ import annotations

import pytest

from rolecheck.pilot.gate6 import assign_removal_target, score_sealed_outputs


def test_gate6_assignment_is_stable_and_bounded() -> None:
    roles = ["domain", "elimination", "verification"]
    first = assign_removal_target(task_id="task-1", role_ids=roles, experiment_seed=19)
    second = assign_removal_target(task_id="task-1", role_ids=roles, experiment_seed=19)
    assert first == second
    assert first in roles


def test_gate6_assignment_rejects_ambiguous_role_order() -> None:
    with pytest.raises(ValueError, match="unique"):
        assign_removal_target(task_id="task-1", role_ids=["a", "a"], experiment_seed=19)


def test_gate6_post_seal_scoring() -> None:
    scored = score_sealed_outputs(
        baseline_answers={"a": "A", "b": None},
        removal_answers={"a": "B", "b": "C"},
        gold_answers={"a": "A", "b": "C"},
    )
    assert scored["baseline_accuracy"] == 0.5
    assert scored["removal_accuracy"] == 0.5
    assert scored["accuracy_delta"] == 0.0


def test_gate6_scoring_requires_identical_task_sets() -> None:
    with pytest.raises(ValueError, match="identities"):
        score_sealed_outputs(
            baseline_answers={"a": "A"},
            removal_answers={"b": "A"},
            gold_answers={"a": "A"},
        )
