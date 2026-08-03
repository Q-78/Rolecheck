"""Pinned, I/O-free MMLU-Pro pre-execution task conversion boundary."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from rolecheck.benchmark.models import (
    BenchmarkAdapterIdentity,
    TaskConversionResult,
)
from rolecheck.hashing import canonical_json_hash
from rolecheck.schemas import EvidenceBoundModel, EvidenceClass, TaskSpec
from rolecheck.schemas.models import StrictModel

MMLU_PRO_DATASET_ID: Final = "TIGER-Lab/MMLU-Pro"
MMLU_PRO_REVISION: Final = "b189ec765aa7ed75c8acfea42df31fdae71f97be"


class MMLUProTaskRecord(EvidenceBoundModel):
    """Label-free source fields permitted to enter pre-execution processing."""

    evidence_class: Literal[EvidenceClass.EMPIRICAL_UNEVALUATED] = (
        EvidenceClass.EMPIRICAL_UNEVALUATED
    )
    synthetic: Literal[False] = False
    non_empirical: Literal[False] = False
    source_record_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    options: tuple[str, ...] = Field(min_length=2, max_length=10)
    category: str = Field(min_length=1)

    @field_validator("source_record_id", "question", "category")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("MMLU-Pro task fields cannot be blank")
        return value

    @field_validator("options")
    @classmethod
    def reject_blank_options(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not option.strip() for option in value):
            raise ValueError("MMLU-Pro options cannot be blank")
        return value


class MMLUProEvaluationRecord(StrictModel):
    """Post-execution labels that must never enter TaskSpec or role inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: Literal["TIGER-Lab/MMLU-Pro"] = MMLU_PRO_DATASET_ID
    dataset_revision: Literal[
        "b189ec765aa7ed75c8acfea42df31fdae71f97be"
    ] = MMLU_PRO_REVISION
    task_id: str = Field(min_length=1)
    answer_index: int = Field(ge=0, le=9)
    answer_letter: str = Field(pattern=r"^[A-J]$")
    gold_answer: str = Field(min_length=1)
    reference_chain_of_thought: str | None = None

    @model_validator(mode="after")
    def validate_answer_identity(self) -> MMLUProEvaluationRecord:
        if not self.task_id.strip():
            raise ValueError("task identity cannot be blank")
        if self.answer_letter != chr(ord("A") + self.answer_index):
            raise ValueError("answer letter does not match answer index")
        if not self.gold_answer.strip():
            raise ValueError("gold answer cannot be blank")
        return self


class MMLUProBenchmarkAdapter:
    """Deterministically convert only the approved pinned MMLU-Pro revision."""

    def __init__(
        self,
        *,
        dataset_revision: str,
        adapter_version: str = "v0.1",
    ) -> None:
        if dataset_revision != MMLU_PRO_REVISION:
            raise ValueError("MMLU-Pro adapter requires the approved pinned revision")
        self._dataset_revision = dataset_revision
        self._identity = BenchmarkAdapterIdentity(
            adapter_id="rolecheck.mmlu_pro",
            adapter_version=adapter_version,
            config_hash=canonical_json_hash(
                {
                    "adapter_id": "rolecheck.mmlu_pro",
                    "adapter_version": adapter_version,
                    "dataset_id": MMLU_PRO_DATASET_ID,
                    "dataset_revision": dataset_revision,
                    "input_contract": "label_free_v0.1",
                }
            ),
        )

    @property
    def identity(self) -> BenchmarkAdapterIdentity:
        return self._identity.model_copy(deep=True)

    @property
    def dataset_id(self) -> str:
        return MMLU_PRO_DATASET_ID

    @property
    def dataset_revision(self) -> str:
        return self._dataset_revision

    def convert(self, record: MMLUProTaskRecord) -> TaskConversionResult:
        isolated = MMLUProTaskRecord.model_validate(record.model_dump(mode="python"))
        source_hash = canonical_json_hash(isolated.model_dump(mode="json"))
        digest = canonical_json_hash(
            {
                "adapter": self.identity.model_dump(mode="json"),
                "dataset_id": self.dataset_id,
                "dataset_revision": self.dataset_revision,
                "source_record_id": isolated.source_record_id,
                "source_hash": source_hash,
            }
        )
        task = TaskSpec(
            task_id=f"mmlu-pro-{digest.removeprefix('sha256:')[:24]}",
            task_text=isolated.question,
            task_type="multiple_choice",
            public_metadata={
                "category": isolated.category,
                "dataset_id": self.dataset_id,
                "dataset_revision": self.dataset_revision,
                "options": list(isolated.options),
                "source_record_id": isolated.source_record_id,
                "source_record_hash": source_hash,
            },
        )
        return TaskConversionResult(
            evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
            adapter=self.identity,
            dataset_id=self.dataset_id,
            dataset_revision=self.dataset_revision,
            source_record_id=isolated.source_record_id,
            accepted=True,
            task=task,
        )
