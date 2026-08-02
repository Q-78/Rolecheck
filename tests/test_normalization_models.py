from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolecheck.hashing import sha256_text
from rolecheck.normalization import (
    FieldNormalization,
    InputSpecDraft,
    RoleContractDraft,
    SourceSpan,
    promote_draft,
)
from rolecheck.schemas import FieldProvenance, OutputSpec, RoleContract, SourceType


def test_missing_field_metadata_has_fixed_semantics() -> None:
    metadata = FieldNormalization(
        field_path="goal",
        status=SourceType.MISSING,
        confidence=0.0,
        parse_risk=1.0,
    )
    assert metadata.source_spans == []


def test_missing_field_metadata_rejects_false_confidence() -> None:
    with pytest.raises(ValidationError, match="missing fields require"):
        FieldNormalization(
            field_path="goal",
            status=SourceType.MISSING,
            confidence=0.5,
            parse_risk=0.5,
        )


def test_source_span_must_be_nonempty_and_length_consistent() -> None:
    with pytest.raises(ValidationError):
        SourceSpan(start=0, end=0, text="")
    with pytest.raises(ValidationError, match="length must match"):
        SourceSpan(start=0, end=2, text="x")


def test_partial_draft_does_not_weaken_role_contract() -> None:
    prompt = "Use the task."
    draft = RoleContractDraft(
        role_id="solver",
        source_initializer="test",
        raw_prompt=prompt,
        prompt_hash=sha256_text(prompt),
        required_inputs=[InputSpecDraft(required=True, description="the task")],
    )
    contract, errors = promote_draft(draft)
    assert draft.goal is None
    assert draft.required_inputs is not None
    assert draft.required_inputs[0].name is None
    assert contract is None
    assert any(error.startswith("role_name:") for error in errors)


def test_legacy_role_contract_defaults_and_provenance_remain_compatible() -> None:
    contract = RoleContract(
        role_id="solver",
        role_name="Solver",
        source_initializer="test",
        raw_prompt="Solve the task.",
        prompt_hash="sha256:" + "0" * 64,
        goal="Solve the task.",
        responsibilities=["Produce an answer."],
        outputs=[OutputSpec(name="answer", semantic_type="text")],
        provenance=[
            FieldProvenance(
                field_path="goal",
                source_type=SourceType.PARSED,
                confidence=1.0,
            )
        ],
    )
    assert contract.input_visibility.value == "global"
    assert contract.required_inputs == []


def test_draft_input_buckets_reject_wrong_required_flag() -> None:
    prompt = "Use the task."
    with pytest.raises(ValidationError, match="required_inputs"):
        RoleContractDraft(
            role_id="solver",
            source_initializer="test",
            raw_prompt=prompt,
            prompt_hash=sha256_text(prompt),
            required_inputs=[InputSpecDraft(required=False, description="context")],
        )
