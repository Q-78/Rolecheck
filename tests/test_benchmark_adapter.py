from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolecheck.benchmark import (
    BenchmarkAdapter,
    OfflineTaskRecord,
    SyntheticBenchmarkAdapter,
    TaskConversionResult,
)


def _adapter() -> SyntheticBenchmarkAdapter:
    return SyntheticBenchmarkAdapter(
        dataset_id="synthetic-stage-3",
        dataset_revision="fixture-v1",
    )


def _record() -> OfflineTaskRecord:
    return OfflineTaskRecord(
        source_record_id="record-001",
        task_text="Classify the synthetic item.",
        task_type="synthetic_classification",
        public_metadata={"language": "en"},
        sensitive_fields=["private_note"],
    )


def test_synthetic_adapter_satisfies_protocol_and_preserves_source_fields() -> None:
    adapter: BenchmarkAdapter = _adapter()

    result = adapter.convert(_record())

    assert result.accepted is True
    assert result.synthetic is True
    assert result.non_empirical is True
    assert result.task is not None
    assert result.task.task_text == "Classify the synthetic item."
    assert result.task.task_type == "synthetic_classification"
    assert result.task.public_metadata == {"language": "en"}
    assert result.task.sensitive_fields == ["private_note"]
    assert result.source_record_id == "record-001"
    assert result.adapter.adapter_id == "rolecheck.synthetic"


def test_conversion_is_deterministic_and_does_not_mutate_source() -> None:
    adapter = _adapter()
    record = _record()
    before = record.model_dump(mode="json")

    first = adapter.convert(record)
    second = adapter.convert(record)

    assert first.model_dump_json() == second.model_dump_json()
    assert record.model_dump(mode="json") == before


def test_task_id_changes_with_source_or_adapter_revision() -> None:
    first = _adapter().convert(_record())
    changed_source = _record().model_copy(update={"source_record_id": "record-002"})
    second = _adapter().convert(changed_source)
    revised = SyntheticBenchmarkAdapter(
        dataset_id="synthetic-stage-3",
        dataset_revision="fixture-v2",
    ).convert(_record())

    assert first.task is not None and second.task is not None and revised.task is not None
    assert first.task.task_id != second.task.task_id
    assert first.task.task_id != revised.task.task_id


def test_blank_task_text_is_rejected_without_creating_a_task() -> None:
    result = _adapter().convert(
        OfflineTaskRecord(source_record_id="record-blank", task_text="  \n")
    )

    assert result.accepted is False
    assert result.task is None
    assert result.rejection_reasons == ["task_text_blank"]


def test_source_contract_rejects_extra_fields_and_invalid_sensitive_names() -> None:
    with pytest.raises(ValidationError):
        OfflineTaskRecord(
            source_record_id="record-001",
            task_text="synthetic",
            gold_answer="forbidden",
        )


def test_adapter_rejects_sensitive_values_in_public_metadata() -> None:
    result = _adapter().convert(
        OfflineTaskRecord(
            source_record_id="record-sensitive",
            task_text="synthetic",
            public_metadata={"private_note": "must not escape"},
            sensitive_fields=["private_note"],
        )
    )

    assert result.accepted is False
    assert result.task is None
    assert result.rejection_reasons == ["sensitive_fields_present_in_public_metadata"]


def test_adapter_identity_is_frozen() -> None:
    identity = _adapter().identity

    with pytest.raises(ValidationError):
        identity.adapter_version = "changed"
    with pytest.raises(ValidationError):
        OfflineTaskRecord(
            source_record_id="record-001",
            task_text="synthetic",
            sensitive_fields=["private_note", "private_note"],
        )


def test_conversion_result_enforces_acceptance_consistency() -> None:
    adapter = _adapter()
    with pytest.raises(ValidationError):
        TaskConversionResult(
            adapter=adapter.identity,
            dataset_id=adapter.dataset_id,
            dataset_revision=adapter.dataset_revision,
            source_record_id="record-001",
            accepted=True,
        )
