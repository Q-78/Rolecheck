"""Offline Benchmark Adapter protocol and synthetic implementation."""

from __future__ import annotations

from typing import Protocol

from rolecheck.benchmark.models import (
    BenchmarkAdapterIdentity,
    OfflineTaskRecord,
    TaskConversionResult,
)
from rolecheck.hashing import canonical_json_hash
from rolecheck.schemas import TaskSpec


class BenchmarkAdapter(Protocol):
    """Convert already-available records without I/O or evaluation."""

    @property
    def identity(self) -> BenchmarkAdapterIdentity: ...

    @property
    def dataset_id(self) -> str: ...

    @property
    def dataset_revision(self) -> str: ...

    def convert(self, record: OfflineTaskRecord) -> TaskConversionResult: ...


class SyntheticBenchmarkAdapter:
    """Deterministic adapter for small, hand-authored non-empirical fixtures."""

    def __init__(
        self,
        *,
        dataset_id: str,
        dataset_revision: str,
        adapter_id: str = "rolecheck.synthetic",
        adapter_version: str = "v0.1",
    ) -> None:
        if not dataset_id.strip() or not dataset_revision.strip():
            raise ValueError("dataset identity and revision cannot be blank")
        self._dataset_id = dataset_id
        self._dataset_revision = dataset_revision
        self._identity = BenchmarkAdapterIdentity(
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            config_hash=canonical_json_hash(
                {
                    "adapter_id": adapter_id,
                    "adapter_version": adapter_version,
                    "dataset_id": dataset_id,
                    "dataset_revision": dataset_revision,
                }
            ),
        )

    @property
    def identity(self) -> BenchmarkAdapterIdentity:
        return self._identity.model_copy(deep=True)

    @property
    def dataset_id(self) -> str:
        return self._dataset_id

    @property
    def dataset_revision(self) -> str:
        return self._dataset_revision

    def convert(self, record: OfflineTaskRecord) -> TaskConversionResult:
        isolated = OfflineTaskRecord.model_validate(record.model_dump(mode="python"))
        if not isolated.task_text.strip():
            return TaskConversionResult(
                adapter=self.identity,
                dataset_id=self.dataset_id,
                dataset_revision=self.dataset_revision,
                source_record_id=isolated.source_record_id,
                accepted=False,
                rejection_reasons=["task_text_blank"],
            )
        if set(isolated.sensitive_fields) & set(isolated.public_metadata):
            return TaskConversionResult(
                adapter=self.identity,
                dataset_id=self.dataset_id,
                dataset_revision=self.dataset_revision,
                source_record_id=isolated.source_record_id,
                accepted=False,
                rejection_reasons=["sensitive_fields_present_in_public_metadata"],
            )

        digest = canonical_json_hash(
            {
                "adapter": self.identity.model_dump(mode="json"),
                "dataset_id": self.dataset_id,
                "dataset_revision": self.dataset_revision,
                "source_record_id": isolated.source_record_id,
            }
        )
        task = TaskSpec(
            task_id=f"task-{digest.removeprefix('sha256:')[:24]}",
            task_text=isolated.task_text,
            task_type=isolated.task_type,
            public_metadata=isolated.public_metadata,
            sensitive_fields=isolated.sensitive_fields,
        )
        return TaskConversionResult(
            adapter=self.identity,
            dataset_id=self.dataset_id,
            dataset_revision=self.dataset_revision,
            source_record_id=isolated.source_record_id,
            accepted=True,
            task=task,
        )
