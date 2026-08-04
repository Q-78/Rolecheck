from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolecheck.benchmark.gate3 import audit_preexecution_payload, build_gate3_subset_manifests
from rolecheck.schemas import TaskSpec


def _tasks(*, domains: int = 14, per_domain: int = 5) -> list[TaskSpec]:
    return [
        TaskSpec(
            task_id=f"task-{d:02d}-{i:02d}",
            task_text=f"Question {d}-{i}",
            task_type="multiple_choice",
            public_metadata={
                "category": f"domain-{d:02d}",
                "options": ["one", "two", "three", "four"],
            },
        )
        for d in range(domains)
        for i in range(per_domain)
    ]


def test_gate3_subsets_are_deterministic_balanced_and_nested() -> None:
    small, large = build_gate3_subset_manifests(_tasks())
    small_again, large_again = build_gate3_subset_manifests(list(reversed(_tasks())))
    assert (small, large) == (small_again, large_again)
    assert len(small.task_ids) == 14
    assert len(large.task_ids) == 56
    assert set(small.task_ids) < set(large.task_ids)
    assert set(small.domain_counts.values()) == {1}
    assert set(large.domain_counts.values()) == {4}


def test_gate3_hard_aborts_on_domain_count_or_capacity() -> None:
    with pytest.raises(ValueError, match="exactly 14 domains"):
        build_gate3_subset_manifests(_tasks(domains=13))
    with pytest.raises(ValueError, match="fewer than four"):
        build_gate3_subset_manifests(_tasks(per_domain=3))


def test_gate3_manifest_rejects_domain_binding_tampering() -> None:
    small, _ = build_gate3_subset_manifests(_tasks())
    payload = small.model_dump(mode="python")
    payload["task_domains"] = tuple("wrong-domain" for _ in small.task_domains)
    with pytest.raises(ValidationError, match="exactly 14 domains"):
        type(small).model_validate(payload)


def test_gate3_leakage_audit_rejects_nested_evaluation_fields() -> None:
    with pytest.raises(ValueError, match=r"root.tasks\[0\].Gold-Answer"):
        audit_preexecution_payload({"tasks": [{"Gold-Answer": "D"}]})
    with pytest.raises(ValueError, match="reference_rationale"):
        audit_preexecution_payload({"nested": {"reference_rationale": "hidden"}})


def test_gate3_leakage_audit_allows_neutral_response_format() -> None:
    audit_preexecution_payload({"response_format": "one uppercase letter"})
