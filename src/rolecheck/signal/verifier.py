"""Independent arithmetic verifier for Gate 6.2 synthetic artifacts."""

from __future__ import annotations

from fractions import Fraction

from rolecheck.hashing import canonical_json_hash
from rolecheck.signal.models import StructuredRemovalEvaluation
from rolecheck.signal.tie_break import deterministic_tie_order


def verify_removal(record: StructuredRemovalEvaluation) -> dict[str, object]:
    """Recompute hashes, exact score arithmetic, tie order, and one-role removal."""
    if record.role_reexecutions != 0:
        raise ValueError("role re-execution is forbidden")
    baseline_ids = record.baseline.valid_role_ids
    if [
        role for role in baseline_ids if role != record.removed_role_id
    ] != record.retained_role_ids:
        raise ValueError("not an ordered single-role deletion")
    if record.baseline_input_hash != canonical_json_hash(record.baseline_role_output_hashes):
        raise ValueError("baseline input hash mismatch")
    if record.removal_input_hash != canonical_json_hash(record.removal_role_output_hashes):
        raise ValueError("removal input hash mismatch")
    expected_retained = {
        role: record.baseline_role_output_hashes[role] for role in record.retained_role_ids
    }
    if record.removal_role_output_hashes != expected_retained:
        raise ValueError("retained outputs were not hash-identically reused")

    for aggregation, expected_ids in (
        (record.baseline, baseline_ids),
        (record.removal, record.retained_role_ids),
    ):
        totals = {
            letter: sum(aggregation.per_role_scores[role][letter] for role in expected_ids)
            for letter in aggregation.total_scores
        }
        if totals != aggregation.total_scores:
            raise ValueError("aggregation total mismatch")
        for letter, total in totals.items():
            if aggregation.mean_scores[letter].as_fraction() != Fraction(total, len(expected_ids)):
                raise ValueError("aggregation mean mismatch")
        order, digest = deterministic_tie_order(
            list(totals),
            task_id=record.task_id,
            task_hash=record.task_hash,
            aggregator_version=aggregation.aggregator_version,
            namespace="rolecheck.gate62.tie-break.v0.1",
        )
        if order != aggregation.tie_break_order or digest != aggregation.tie_break_order_hash:
            raise ValueError("tie-break identity mismatch")
        leaders = [letter for letter, value in totals.items() if value == max(totals.values())]
        expected = next(letter for letter in order if letter in leaders)
        if aggregation.selected_answer != expected:
            raise ValueError("selected answer mismatch")
    return {
        "status": "PASSED",
        "single_role_drop": True,
        "role_reexecutions": 0,
        "gold_in_removal_artifact": False,
        "offline_only": True,
    }
