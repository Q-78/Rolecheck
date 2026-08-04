"""Gold-free task-specific deterministic tie breaking."""

from __future__ import annotations

from rolecheck.hashing import canonical_json_hash


def deterministic_tie_order(
    option_letters: list[str],
    *,
    task_id: str,
    task_hash: str,
    aggregator_version: str,
    namespace: str,
) -> tuple[list[str], str]:
    if len(set(option_letters)) != len(option_letters):
        raise ValueError("option letters must be unique")
    identity = {
        "task_id": task_id,
        "task_hash": task_hash,
        "aggregator_version": aggregator_version,
        "namespace": namespace,
    }
    order = sorted(
        option_letters,
        key=lambda letter: canonical_json_hash({**identity, "option": letter}),
    )
    return order, canonical_json_hash({**identity, "permutation": order})
