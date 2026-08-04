from __future__ import annotations

import json
from fractions import Fraction

import pytest
from pydantic import ValidationError

from rolecheck.hashing import canonical_json_hash
from rolecheck.signal.aggregation import DeterministicScoreAggregator
from rolecheck.signal.evaluation import evaluate_keep_value
from rolecheck.signal.models import (
    OptionScoreVector,
    RoleScoreEvidence,
    StructuredRemovalEvaluation,
    StructuredRoleOutput,
)
from rolecheck.signal.parsing import parse_structured_role_output
from rolecheck.signal.tie_break import deterministic_tie_order

OPTIONS = ["A", "B", "C", "D"]


def output(scores: dict[str, int], role_id: str) -> RoleScoreEvidence:
    value = StructuredRoleOutput(
        option_scores=OptionScoreVector(scores=scores), key_evidence=["Synthetic evidence."]
    )
    return RoleScoreEvidence(role_id=role_id, output=value, output_hash=value.canonical_hash)


def test_strict_parser_and_canonical_hash() -> None:
    raw = json.dumps({"option_scores": {"A": 5, "B": 15, "C": 70, "D": 10}, "key_evidence": []})
    first = parse_structured_role_output(raw, OPTIONS)
    second = parse_structured_role_output(raw, OPTIONS)
    assert first.status == "valid" and first.output_hash == second.output_hash
    assert parse_structured_role_output(f"text {raw}", OPTIONS).status == "invalid"
    assert parse_structured_role_output(f"```json\n{raw}\n```", OPTIONS).status == "invalid"
    assert parse_structured_role_output("{", OPTIONS).status == "invalid"


@pytest.mark.parametrize(
    "scores",
    [
        {"A": 50.0, "B": 20, "C": 20, "D": 10},
        {"A": -1, "B": 21, "C": 70, "D": 10},
        {"A": 101, "B": 0, "C": 0, "D": 0},
        {"A": 25, "B": 25, "C": 25, "D": 24},
    ],
)
def test_invalid_score_vectors(scores: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        OptionScoreVector(scores=scores)


def test_evidence_limits() -> None:
    vector = OptionScoreVector(scores={"A": 25, "B": 25, "C": 25, "D": 25})
    with pytest.raises(ValidationError):
        StructuredRoleOutput(option_scores=vector, key_evidence=["x"] * 4)
    with pytest.raises(ValidationError):
        StructuredRoleOutput(option_scores=vector, key_evidence=["x" * 241])


def test_parser_rejects_missing_and_extra_task_options() -> None:
    missing = json.dumps({"option_scores": {"A": 50, "B": 50, "C": 0}, "key_evidence": []})
    extra = json.dumps(
        {
            "option_scores": {"A": 50, "B": 50, "C": 0, "D": 0, "E": 0},
            "key_evidence": [],
        }
    )
    assert parse_structured_role_output(missing, OPTIONS).status == "invalid"
    assert parse_structured_role_output(extra, OPTIONS).status == "invalid"


def test_aggregation_removal_and_exact_mean() -> None:
    roles = ["domain", "elimination", "verification"]
    evidence = [
        output({"A": 90, "B": 0, "C": 0, "D": 10}, roles[0]),
        output({"A": 10, "B": 70, "C": 10, "D": 10}, roles[1]),
        output({"A": 10, "B": 20, "C": 60, "D": 10}, roles[2]),
    ]
    aggregator = DeterministicScoreAggregator()
    baseline = aggregator.aggregate(
        task_id="t",
        task_hash=canonical_json_hash("t"),
        option_letters=OPTIONS,
        required_role_ids=roles,
        role_outputs=evidence,
    )
    retained = roles[1:]
    removal = aggregator.aggregate(
        task_id="t",
        task_hash=canonical_json_hash("t"),
        option_letters=OPTIONS,
        required_role_ids=retained,
        role_outputs=evidence[1:],
    )
    assert baseline.mean_scores["A"].as_fraction() == Fraction(110, 3)
    assert removal.mean_scores["B"].as_fraction() == Fraction(90, 2)
    record = StructuredRemovalEvaluation(
        task_id="t",
        task_hash=canonical_json_hash("t"),
        removed_role_id=roles[0],
        baseline_input_hash=canonical_json_hash(
            {item.role_id: item.output_hash for item in evidence}
        ),
        removal_input_hash=canonical_json_hash(
            {item.role_id: item.output_hash for item in evidence[1:]}
        ),
        baseline_role_output_hashes={item.role_id: item.output_hash for item in evidence},
        removal_role_output_hashes={item.role_id: item.output_hash for item in evidence[1:]},
        baseline=baseline,
        removal=removal,
        retained_role_ids=retained,
    )
    hard, soft = evaluate_keep_value(record, gold_answer="A")
    assert hard.hard_keep_value == 1
    assert soft.soft_keep_value.as_fraction() != 0


def test_invalid_baseline_is_unscorable_not_excluded() -> None:
    aggregator = DeterministicScoreAggregator()
    result = aggregator.aggregate(
        task_id="t",
        task_hash=canonical_json_hash("t"),
        option_letters=OPTIONS,
        required_role_ids=["a", "b"],
        role_outputs=[output({"A": 25, "B": 25, "C": 25, "D": 25}, "a"), None],
    )
    assert not result.scorable and result.invalid_role_ids == ["b"]


def test_role_order_does_not_change_scores() -> None:
    aggregator = DeterministicScoreAggregator()
    one = output({"A": 60, "B": 20, "C": 10, "D": 10}, "one")
    two = output({"A": 20, "B": 60, "C": 10, "D": 10}, "two")
    common = dict(task_id="t", task_hash=canonical_json_hash("t"), option_letters=OPTIONS)
    first = aggregator.aggregate(
        required_role_ids=["one", "two"], role_outputs=[one, two], **common
    )
    second = aggregator.aggregate(
        required_role_ids=["two", "one"], role_outputs=[two, one], **common
    )
    assert first.total_scores == second.total_scores
    assert first.selected_answer == second.selected_answer


def test_tie_break_is_stable_gold_free_and_complete() -> None:
    args = dict(
        task_id="t",
        task_hash=canonical_json_hash("t"),
        aggregator_version="v0.1",
        namespace="rolecheck.gate62.tie-break.v0.1",
    )
    first = deterministic_tie_order(OPTIONS, **args)
    assert first == deterministic_tie_order(OPTIONS, **args)
    assert set(first[0]) == set(OPTIONS)


def test_duplicate_roles_and_hash_mismatch_are_rejected() -> None:
    aggregator = DeterministicScoreAggregator()
    item = output({"A": 25, "B": 25, "C": 25, "D": 25}, "a")
    with pytest.raises(ValueError, match="unique"):
        aggregator.aggregate(
            task_id="t",
            task_hash=canonical_json_hash("t"),
            option_letters=OPTIONS,
            required_role_ids=["a", "a"],
            role_outputs=[item, item],
        )
    with pytest.raises(ValidationError, match="hash"):
        RoleScoreEvidence(role_id="a", output=item.output, output_hash=canonical_json_hash("bad"))
