"""Deterministic, leakage-resistant task split manifests."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from rolecheck.benchmark.models import BenchmarkAdapterIdentity
from rolecheck.hashing import canonical_json_hash
from rolecheck.schemas.models import StrictModel

PartitionName = Literal["train", "development", "test"]
_PARTITION_ORDER: tuple[PartitionName, ...] = ("train", "development", "test")


class SplitWeights(StrictModel):
    """Integer allocation weights, avoiding floating-point split ambiguity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    train: int = Field(default=8, ge=0)
    development: int = Field(default=1, ge=0)
    test: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def require_positive_total(self) -> SplitWeights:
        if self.train + self.development + self.test == 0:
            raise ValueError("at least one split weight must be positive")
        return self

    def as_ordered_tuple(self) -> tuple[int, int, int]:
        return (self.train, self.development, self.test)


class TaskPartition(StrictModel):
    """One named partition and its canonical evidence hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: PartitionName
    task_ids: tuple[str, ...]
    task_ids_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("task_ids")
    @classmethod
    def validate_task_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not task_id.strip() for task_id in value):
            raise ValueError("partition task identifiers cannot be blank")
        if len(value) != len(set(value)):
            raise ValueError("partition task identifiers must be unique")
        return value

    @model_validator(mode="after")
    def validate_hash(self) -> TaskPartition:
        expected = canonical_json_hash(
            {"name": self.name, "task_ids": list(self.task_ids)}
        )
        if self.task_ids_hash != expected:
            raise ValueError("partition task hash does not match its identifiers")
        return self


class TaskSplitManifest(StrictModel):
    """Canonical train/development/test assignment evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(min_length=1)
    dataset_revision: str = Field(min_length=1)
    adapter: BenchmarkAdapterIdentity
    seed: int = Field(ge=0)
    weights: SplitWeights
    source_task_ids_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    partitions: tuple[TaskPartition, TaskPartition, TaskPartition]
    split_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    synthetic: Literal[True] = True
    non_empirical: Literal[True] = True

    @field_validator("dataset_id", "dataset_revision")
    @classmethod
    def reject_blank_identifiers(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("dataset identity and revision cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_manifest(self) -> TaskSplitManifest:
        if tuple(partition.name for partition in self.partitions) != _PARTITION_ORDER:
            raise ValueError("partitions must be ordered train, development, test")
        all_ids = [
            task_id
            for partition in self.partitions
            for task_id in partition.task_ids
        ]
        if not all_ids:
            raise ValueError("split manifest cannot be empty")
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("split partitions must be disjoint")
        expected_source_hash = canonical_json_hash(sorted(all_ids))
        if self.source_task_ids_hash != expected_source_hash:
            raise ValueError("source task hash does not match exhaustive partitions")
        expected_order = _deterministic_task_order(all_ids, self.seed)
        expected_counts = _allocate_counts(
            len(all_ids), self.weights.as_ordered_tuple()
        )
        offset = 0
        for partition, count in zip(self.partitions, expected_counts, strict=True):
            expected_ids = tuple(expected_order[offset : offset + count])
            offset += count
            if partition.task_ids != expected_ids:
                raise ValueError(
                    "partition assignment does not match the recorded seed and weights"
                )
        if self.split_hash != _split_hash_payload(
            dataset_id=self.dataset_id,
            dataset_revision=self.dataset_revision,
            adapter=self.adapter,
            seed=self.seed,
            weights=self.weights,
            source_task_ids_hash=self.source_task_ids_hash,
            partitions=self.partitions,
        ):
            raise ValueError("split hash does not match canonical manifest content")
        return self


def create_task_split_manifest(
    task_ids: Sequence[str],
    *,
    dataset_id: str,
    dataset_revision: str,
    adapter: BenchmarkAdapterIdentity,
    seed: int,
    weights: SplitWeights | None = None,
) -> TaskSplitManifest:
    """Assign validated identifiers without consulting task outcomes or labels."""

    if seed < 0:
        raise ValueError("split seed must be non-negative")
    if not dataset_id.strip() or not dataset_revision.strip():
        raise ValueError("dataset identity and revision cannot be blank")
    isolated_ids = tuple(task_ids)
    if not isolated_ids:
        raise ValueError("task identifiers cannot be empty")
    if any(not isinstance(task_id, str) or not task_id.strip() for task_id in isolated_ids):
        raise ValueError("task identifiers must be non-blank strings")
    if len(isolated_ids) != len(set(isolated_ids)):
        raise ValueError("task identifiers must be unique")

    selected_weights = weights or SplitWeights()
    ordered_ids = _deterministic_task_order(isolated_ids, seed)
    counts = _allocate_counts(len(ordered_ids), selected_weights.as_ordered_tuple())
    offset = 0
    partitions: list[TaskPartition] = []
    for name, count in zip(_PARTITION_ORDER, counts, strict=True):
        assigned = tuple(ordered_ids[offset : offset + count])
        offset += count
        partitions.append(
            TaskPartition(
                name=name,
                task_ids=assigned,
                task_ids_hash=canonical_json_hash(
                    {"name": name, "task_ids": list(assigned)}
                ),
            )
        )
    partition_tuple = (partitions[0], partitions[1], partitions[2])
    source_hash = canonical_json_hash(sorted(isolated_ids))
    split_hash = _split_hash_payload(
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        adapter=adapter,
        seed=seed,
        weights=selected_weights,
        source_task_ids_hash=source_hash,
        partitions=partition_tuple,
    )
    return TaskSplitManifest(
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        adapter=adapter,
        seed=seed,
        weights=selected_weights,
        source_task_ids_hash=source_hash,
        partitions=partition_tuple,
        split_hash=split_hash,
    )


def _allocate_counts(task_count: int, weights: tuple[int, int, int]) -> tuple[int, int, int]:
    total_weight = sum(weights)
    counts = [task_count * weight // total_weight for weight in weights]
    remainder_count = task_count - sum(counts)
    remainder_order = sorted(
        range(len(weights)),
        key=lambda index: (-(task_count * weights[index] % total_weight), index),
    )
    for index in remainder_order[:remainder_count]:
        counts[index] += 1
    return (counts[0], counts[1], counts[2])


def _deterministic_task_order(task_ids: Sequence[str], seed: int) -> list[str]:
    return sorted(
        task_ids,
        key=lambda task_id: (
            canonical_json_hash({"seed": seed, "task_id": task_id}),
            task_id,
        ),
    )


def _split_hash_payload(
    *,
    dataset_id: str,
    dataset_revision: str,
    adapter: BenchmarkAdapterIdentity,
    seed: int,
    weights: SplitWeights,
    source_task_ids_hash: str,
    partitions: tuple[TaskPartition, TaskPartition, TaskPartition],
) -> str:
    return canonical_json_hash(
        {
            "dataset_id": dataset_id,
            "dataset_revision": dataset_revision,
            "adapter": adapter.model_dump(mode="json"),
            "seed": seed,
            "weights": weights.model_dump(mode="json"),
            "source_task_ids_hash": source_task_ids_hash,
            "partitions": [
                partition.model_dump(mode="json") for partition in partitions
            ],
            "synthetic": True,
            "non_empirical": True,
        }
    )
