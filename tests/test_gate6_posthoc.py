from __future__ import annotations

import json
from pathlib import Path

import pytest

from rolecheck.analysis.gate6_posthoc import _summarize, _transition
from rolecheck.analysis.models import EvaluatedRemovalRecord, ExhaustiveRemovalRecord
from rolecheck.analysis.statistics import bootstrap_mean_ci, exact_binomial_two_sided, exact_mcnemar
from rolecheck.analysis.verifier import verify_analysis


@pytest.mark.parametrize(
    ("baseline", "removal", "expected"),
    [
        (True, False, "correct_to_wrong"),
        (True, True, "correct_to_correct"),
        (False, True, "wrong_to_correct"),
        (False, False, "wrong_to_wrong"),
        (None, False, "unscorable"),
        (True, None, "unscorable"),
    ],
)
def test_transitions(baseline: bool | None, removal: bool | None, expected: str) -> None:
    assert _transition(baseline, removal) == expected


def test_exact_tests_known_values() -> None:
    assert exact_binomial_two_sided(0, 3) == 0.25
    assert exact_mcnemar(3, 0) == 0.25
    assert exact_mcnemar(0, 0) == 1.0


def test_bootstrap_is_deterministic_and_empty_safe() -> None:
    first = bootstrap_mean_ci([-1.0, 0.0, 1.0], seed=7, samples=100)
    assert first == bootstrap_mean_ci([-1.0, 0.0, 1.0], seed=7, samples=100)
    assert bootstrap_mean_ci([], seed=7)["mean"] is None


def test_summary_groups_and_preserves_unscorable() -> None:
    rows = [
        {
            "outcome_transition": "correct_to_wrong",
            "keep_value": 1,
            "role_id": "a",
            "category": "x",
        },
        {
            "outcome_transition": "wrong_to_correct",
            "keep_value": -1,
            "role_id": "b",
            "category": "x",
        },
        {"outcome_transition": "unscorable", "keep_value": None, "role_id": "a", "category": "y"},
    ]
    summary = _summarize(rows)
    assert summary["valid_labels"] == 2
    assert summary["keep_value_distribution"]["unscorable"] == 1
    assert summary["by_role"]["a"] == {"1": 1, "unscorable": 1}
    assert summary["by_domain"]["x"] == {"-1": 1, "1": 1}


def test_counterfactual_schema_has_no_gold_or_labels() -> None:
    record = ExhaustiveRemovalRecord(
        task_id="t",
        category="c",
        role_id="a",
        baseline_aggregation_hash="sha256:" + "0" * 64,
        exhaustive_removal_aggregation_hash="sha256:" + "1" * 64,
        retained_role_ids=["b", "c"],
        retained_role_output_hashes={"b": "h1", "c": "h2"},
        removed_role_output_hash="sha256:" + "2" * 64,
        baseline_selected_answer="A",
        removed_selected_answer="B",
        baseline_scorable=True,
        removed_scorable=True,
        baseline_tie_break_applied=False,
        removal_tie_break_applied=True,
        baseline_strict_majority=True,
        removal_strict_majority=False,
        baseline_invalid_role_ids=[],
        removal_invalid_role_ids=[],
        baseline_vote_pattern="2_to_1",
        protocol_id="p",
        aggregator_identity={"aggregator_id": "a", "aggregator_version": "v", "config_hash": "h"},
        source_gate6_root_hash="sha256:" + "3" * 64,
    )
    assert not ({"gold_answer", "keep_value", "baseline_correct"} & set(record.model_dump()))


def test_evaluated_schema_keeps_unscorable_null() -> None:
    row = EvaluatedRemovalRecord(
        counterfactual_record_hash="sha256:" + "0" * 64,
        task_id="t",
        category="c",
        role_id="a",
        baseline_correct=None,
        removed_correct=False,
        outcome_transition="unscorable",
        answer_changed=None,
        keep_value=None,
        tie_dependent=True,
        invalid_vote_related=True,
    )
    assert row.keep_value is None


def test_verifier_rejects_missing_or_tampered_root(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_analysis(tmp_path, expected_source_hash="sha256:" + "0" * 64)
    (tmp_path / "artifact-manifest.json").write_text(json.dumps({"files": [], "files_hash": "bad"}))
    with pytest.raises(RuntimeError, match="seal"):
        verify_analysis(tmp_path, expected_source_hash="sha256:" + "0" * 64)
