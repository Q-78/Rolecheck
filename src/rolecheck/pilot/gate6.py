"""Deterministic Gate 6 assignment and post-seal evaluation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rolecheck.hashing import canonical_json_hash


def assign_removal_target(
    *, task_id: str, role_ids: Sequence[str], experiment_seed: int
) -> str:
    """Assign exactly one frozen removal target without task labels or outputs."""
    if not task_id.strip():
        raise ValueError("task_id cannot be blank")
    if not role_ids or len(set(role_ids)) != len(role_ids):
        raise ValueError("role_ids must be non-empty and unique")
    digest = canonical_json_hash(
        {
            "assignment_policy": "task_hash_modulo_frozen_role_order_v0.1",
            "experiment_seed": experiment_seed,
            "task_id": task_id,
            "role_ids": list(role_ids),
        }
    )
    index = int(digest.removeprefix("sha256:")[:16], 16) % len(role_ids)
    return role_ids[index]


def score_sealed_outputs(
    *,
    baseline_answers: Mapping[str, str | None],
    removal_answers: Mapping[str, str | None],
    gold_answers: Mapping[str, str],
) -> dict[str, object]:
    """Score two sealed conditions against labels loaded only after execution."""
    task_ids = set(baseline_answers)
    if set(removal_answers) != task_ids or set(gold_answers) != task_ids:
        raise ValueError("baseline, removal, and gold task identities must match")
    rows = []
    for task_id in sorted(task_ids):
        baseline = baseline_answers[task_id]
        removal = removal_answers[task_id]
        gold = gold_answers[task_id]
        rows.append(
            {
                "task_id": task_id,
                "baseline_answer": baseline,
                "removal_answer": removal,
                "gold_answer": gold,
                "baseline_correct": baseline == gold,
                "removal_correct": removal == gold,
            }
        )
    total = len(rows)
    baseline_correct = sum(bool(row["baseline_correct"]) for row in rows)
    removal_correct = sum(bool(row["removal_correct"]) for row in rows)
    return {
        "rows": rows,
        "task_count": total,
        "baseline_correct": baseline_correct,
        "removal_correct": removal_correct,
        "baseline_accuracy": baseline_correct / total if total else 0.0,
        "removal_accuracy": removal_correct / total if total else 0.0,
        "accuracy_delta": (removal_correct - baseline_correct) / total if total else 0.0,
    }
