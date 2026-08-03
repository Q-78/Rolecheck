from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolecheck.benchmark import (
    SplitWeights,
    SyntheticBenchmarkAdapter,
    TaskSplitManifest,
    create_task_split_manifest,
)
from rolecheck.hashing import canonical_json_hash
from rolecheck.manifest import create_manifest


def _adapter() -> SyntheticBenchmarkAdapter:
    return SyntheticBenchmarkAdapter(
        dataset_id="synthetic-stage-3",
        dataset_revision="fixture-v1",
    )


def _task_ids() -> list[str]:
    return [f"task-{index:02d}" for index in range(20)]


def _manifest(task_ids: list[str] | None = None, *, seed: int = 17) -> TaskSplitManifest:
    adapter = _adapter()
    return create_task_split_manifest(
        _task_ids() if task_ids is None else task_ids,
        dataset_id=adapter.dataset_id,
        dataset_revision=adapter.dataset_revision,
        adapter=adapter.identity,
        seed=seed,
    )


def test_split_is_order_independent_and_byte_equivalent() -> None:
    forward = _manifest(_task_ids())
    reverse = _manifest(list(reversed(_task_ids())))

    assert forward.model_dump_json() == reverse.model_dump_json()
    assert forward.split_hash == reverse.split_hash


def test_partitions_are_disjoint_exhaustive_and_hashed() -> None:
    manifest = _manifest()
    partition_ids = [set(partition.task_ids) for partition in manifest.partitions]

    assert [partition.name for partition in manifest.partitions] == [
        "train",
        "development",
        "test",
    ]
    assert not (partition_ids[0] & partition_ids[1])
    assert not (partition_ids[0] & partition_ids[2])
    assert not (partition_ids[1] & partition_ids[2])
    assert set().union(*partition_ids) == set(_task_ids())
    assert manifest.source_task_ids_hash == canonical_json_hash(sorted(_task_ids()))
    assert manifest.synthetic is True
    assert manifest.non_empirical is True


def test_seed_changes_assignment_and_canonical_hash() -> None:
    first = _manifest(seed=17)
    second = _manifest(seed=18)

    assert first.partitions != second.partitions
    assert first.split_hash != second.split_hash


@pytest.mark.parametrize(
    "task_ids",
    [
        [],
        ["task-1", "task-1"],
        ["task-1", "  "],
    ],
)
def test_invalid_task_identifier_sets_are_rejected(task_ids: list[str]) -> None:
    with pytest.raises(ValueError):
        _manifest(task_ids)


def test_negative_seed_and_zero_total_weights_are_rejected() -> None:
    adapter = _adapter()
    with pytest.raises(ValueError):
        create_task_split_manifest(
            _task_ids(),
            dataset_id=adapter.dataset_id,
            dataset_revision=adapter.dataset_revision,
            adapter=adapter.identity,
            seed=-1,
        )
    with pytest.raises(ValidationError):
        SplitWeights(train=0, development=0, test=0)


def test_manifest_rejects_partition_or_hash_tampering() -> None:
    manifest = _manifest()
    payload = manifest.model_dump(mode="python")
    payload["split_hash"] = canonical_json_hash("tampered")

    with pytest.raises(ValidationError):
        TaskSplitManifest.model_validate(payload)


def test_manifest_rejects_assignment_not_generated_by_recorded_seed() -> None:
    manifest = _manifest()
    payload = manifest.model_dump(mode="python")
    first = payload["partitions"][0]
    second = payload["partitions"][1]
    first_ids = list(first["task_ids"])
    second_ids = list(second["task_ids"])
    first_ids[0], second_ids[0] = second_ids[0], first_ids[0]
    first["task_ids"] = tuple(first_ids)
    second["task_ids"] = tuple(second_ids)
    for partition in (first, second):
        partition["task_ids_hash"] = canonical_json_hash(
            {"name": partition["name"], "task_ids": partition["task_ids"]}
        )

    with pytest.raises(
        ValidationError,
        match="partition assignment does not match the recorded seed and weights",
    ):
        TaskSplitManifest.model_validate(payload)


def test_split_hash_is_compatible_with_experiment_manifest() -> None:
    split = _manifest()
    experiment = create_manifest(
        experiment_id="synthetic-experiment",
        git_commit="deadbeef",
        dataset_revision=split.dataset_revision,
        task_split_hash=split.split_hash,
        initializer_id="synthetic-initializer",
        runtime_id="mock-runtime",
        protocol_id="parallel-v1",
        removal_protocol_id="parallel-removal-v1",
        seed=split.seed,
        config_hash=canonical_json_hash({"fixture": True}),
        mock=True,
    )

    assert experiment.task_split_hash == split.split_hash
