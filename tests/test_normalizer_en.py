from __future__ import annotations

import pytest
from pydantic import ValidationError

from rolecheck.normalization import (
    DetectedLanguage,
    NormalizationResult,
    RoleContractNormalizer,
)
from rolecheck.schemas import SourceType


def test_english_sections_are_extracted_without_rewriting() -> None:
    prompt = """You are a Research Reviewer.
# Goal
Assess the draft.
# Responsibilities
- Check citations.
- Identify unsupported claims.
# Success Criteria
- Every concern cites evidence.
# Required Inputs
- draft text
# Outputs
- JSON report {findings, verdict}
# Prohibited Behaviors
- Do not invent evidence.
"""
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt=prompt,
    )

    assert result.detected_language is DetectedLanguage.ENGLISH
    assert result.draft.role_name == "Research Reviewer"
    assert result.draft.goal == "Assess the draft."
    assert result.draft.responsibilities == [
        "Check citations.",
        "Identify unsupported claims.",
    ]
    assert result.draft.prohibited_behaviors == ["Do not invent evidence."]
    assert result.draft.required_inputs is not None
    assert result.draft.required_inputs[0].description == "draft text"
    assert result.draft.outputs is not None
    assert result.draft.outputs[0].description == "JSON report {findings, verdict}"
    assert result.draft.outputs[0].format == "json"
    assert result.draft.outputs[0].required_fields is None
    assert result.contract is None
    assert result.contract_validation_errors
    assert result.contract_parse_risk == pytest.approx(0.2)
    assert result.unparsed_segments == []


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("JSON report", "json"),
        ("YAML report", "yaml"),
        ("XML report", "xml"),
        ("Markdown report", "markdown"),
        ("plain-text report", "plain_text"),
    ],
)
def test_only_explicit_format_names_are_recognized(
    description: str, expected: str
) -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt=f"Outputs: {description}",
    )
    assert result.draft.outputs is not None
    assert result.draft.outputs[0].format == expected


def test_duplicate_source_entries_are_preserved() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt="Responsibilities:\n- Check facts.\n- Check facts.",
    )
    assert result.draft.responsibilities == ["Check facts.", "Check facts."]

def test_normalization_is_deterministic() -> None:
    prompt = (
        "Goal: Review the answer.\r\nResponsibilities:\r\n"
        "- Check facts.\r\nOutputs: JSON report"
    )
    normalizer = RoleContractNormalizer()
    first = normalizer.normalize(
        role_id="reviewer", source_initializer="manual", raw_prompt=prompt
    )
    second = normalizer.normalize(
        role_id="reviewer", source_initializer="manual", raw_prompt=prompt
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_complete_structured_draft_is_promoted_to_strict_contract() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        role_name="Reviewer",
        source_initializer="config",
        raw_prompt="Goal: Review the draft.",
        explicit_fields={
            "goal": "Review the draft.",
            "responsibilities": ["Check every claim."],
            "success_criteria": [],
            "non_goals": [],
            "prohibited_behaviors": [],
            "priority_rules": [],
            "required_inputs": [],
            "optional_inputs": [],
            "input_visibility": "global",
            "context_assumptions": [],
            "output_visibility": "shared",
            "failure_output": None,
            "format_strictness": "preferred",
            "authority_level": "advisory",
            "can_override": [],
            "requires_approval_from": [],
            "decision_scope": [],
            "conflict_resolution_rule": None,
            "upstream_dependencies": [],
            "downstream_consumers": [],
            "interaction_mode": "independent",
            "max_interaction_rounds": None,
            "termination_signal": None,
            "handoff_conditions": [],
            "required_capabilities": [],
            "resource_limits": {},
            "parent_role_version": None,
            "outputs": [
                {
                    "name": "review",
                    "semantic_type": "review_report",
                    "consumers": [],
                    "format": "plain_text",
                    "required_fields": [],
                    "description": "A review report.",
                }
            ],
        },
    )
    assert result.contract is not None
    assert result.contract.goal == "Review the draft."
    assert result.contract.outputs[0].format == "plain_text"
    assert result.contract_validation_errors == []


def test_structured_fields_override_but_do_not_hide_prompt_conflict() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="config",
        raw_prompt="Goal: Prompt goal.",
        explicit_fields={"goal": "Structured goal."},
    )
    assert result.draft.goal == "Structured goal."
    assert result.conflicting_fields == ["goal"]
    metadata = next(item for item in result.field_metadata if item.field_path == "goal")
    assert metadata.status is SourceType.EXPLICIT


def test_equivalent_structured_model_data_is_not_a_false_conflict() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="combined",
        raw_prompt="Outputs: JSON report",
        explicit_fields={
            "outputs": [{"format": "json", "description": "JSON report"}]
        },
    )
    assert result.conflicting_fields == []


def test_missing_fields_stay_in_draft_and_prevent_promotion() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt="You are a reviewer.",
    )
    assert result.draft.goal is None
    assert result.draft.responsibilities is None
    assert result.draft.outputs is None
    assert result.contract is None
    assert {"goal", "responsibilities", "outputs"}.issubset(result.missing_fields)
    assert result.contract_parse_risk == 1.0


def test_backtick_and_tilde_code_fences_are_not_parsed() -> None:
    prompt = """~~~text
Goal: fake goal
~~~
# Responsibilities
- Review the draft.
"""
    result = RoleContractNormalizer().normalize(
        role_id="reviewer", source_initializer="manual", raw_prompt=prompt
    )
    assert result.draft.goal is None
    assert result.draft.responsibilities == ["Review the draft."]
    assert any(segment.text == "Goal: fake goal" for segment in result.unparsed_segments)


def test_unclosed_code_fence_is_reported() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt="```\nGoal: fake goal",
    )
    assert result.draft.goal is None
    assert "unclosed code fence: enclosed text was not parsed" in result.warnings


def test_blank_line_ends_section_to_prevent_section_bleed() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt="# Responsibilities\n- Check facts.\n\nThis paragraph is commentary.",
    )
    assert result.draft.responsibilities == ["Check facts."]
    assert any(
        segment.text == "This paragraph is commentary."
        for segment in result.unparsed_segments
    )


def test_conflicting_scalar_sections_remain_unknown() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt="Goal: First.\nGoal: Second.",
    )
    assert result.draft.goal is None
    assert "goal" in result.unknown_fields


def test_normalization_id_covers_parse_metadata() -> None:
    result = RoleContractNormalizer().normalize(
        role_id="reviewer",
        source_initializer="manual",
        raw_prompt="Goal: Review the draft.",
    )
    payload = result.model_dump(mode="json")
    payload["warnings"].append("tampered")
    with pytest.raises(ValidationError, match="normalization_id must match"):
        NormalizationResult.model_validate(payload)


def test_non_contract_runtime_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported explicit role fields"):
        RoleContractNormalizer().normalize(
            role_id="reviewer",
            source_initializer="config",
            raw_prompt="",
            explicit_fields={"model_id": "forbidden-model-change"},
        )
