"""Data contracts for offline, dataset-agnostic task conversion."""

from __future__ import annotations

from pydantic import ConfigDict, Field, field_validator, model_validator

from rolecheck.schemas.models import EvidenceBoundModel, StrictModel, TaskSpec


class BenchmarkAdapterIdentity(StrictModel):
    """Immutable identity of an offline Benchmark Adapter implementation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    config_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("adapter_id", "adapter_version")
    @classmethod
    def reject_blank_identifiers(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("adapter identifiers cannot be blank")
        return value


class OfflineTaskRecord(EvidenceBoundModel):
    """Already-available source material accepted by local adapters.

    The local Stage 3 scaffold accepts only hand-authored synthetic records.
    It intentionally contains no download location, credentials, labels, gold
    answers, role outputs, traces, or counterfactual outcomes.
    """

    source_record_id: str = Field(min_length=1)
    task_text: str
    task_type: str | None = None
    public_metadata: dict[str, object] = Field(default_factory=dict)
    sensitive_fields: list[str] = Field(default_factory=list)

    @field_validator("source_record_id")
    @classmethod
    def reject_blank_source_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_record_id cannot be blank")
        return value

    @field_validator("sensitive_fields")
    @classmethod
    def validate_sensitive_fields(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("sensitive field names cannot be blank")
        if len(value) != len(set(value)):
            raise ValueError("sensitive field names must be unique")
        return value


class TaskConversionResult(EvidenceBoundModel):
    """Auditable result of one offline source-record conversion."""

    adapter: BenchmarkAdapterIdentity
    dataset_id: str = Field(min_length=1)
    dataset_revision: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    accepted: bool
    task: TaskSpec | None = None
    warnings: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)

    @field_validator("dataset_id", "dataset_revision", "source_record_id")
    @classmethod
    def reject_blank_identifiers(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("conversion identifiers cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> TaskConversionResult:
        if self.accepted:
            if self.task is None:
                raise ValueError("accepted conversion requires a task")
            if self.rejection_reasons:
                raise ValueError("accepted conversion cannot contain rejection reasons")
        else:
            if self.task is not None:
                raise ValueError("rejected conversion cannot contain a task")
            if not self.rejection_reasons:
                raise ValueError("rejected conversion requires at least one reason")
        return self
