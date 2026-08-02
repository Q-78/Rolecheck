"""Data contracts for deterministic role-contract normalization."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, Field, model_validator

from rolecheck.hashing import canonical_json_hash, sha256_text
from rolecheck.schemas.models import (
    AuthorityLevel,
    FormatStrictness,
    InteractionMode,
    NonEmptyStr,
    Probability,
    ResourceLimits,
    RoleContract,
    SourceType,
    StrictModel,
    Visibility,
)


class SourceKind(StrEnum):
    PROMPT = "prompt"
    CONFIG = "config"
    WORKFLOW = "workflow"
    COMBINED = "combined"


class DetectedLanguage(StrEnum):
    ENGLISH = "en"
    CHINESE = "zh"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SourceSpan(StrictModel):
    """A non-empty, half-open character span in preserved source text."""

    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: NonEmptyStr

    @model_validator(mode="after")
    def validate_order(self) -> SourceSpan:
        if self.end <= self.start:
            raise ValueError("source span end must follow start")
        if self.end - self.start != len(self.text):
            raise ValueError("source span length must match text length")
        return self


class NormalizationSource(StrictModel):
    source_initializer: NonEmptyStr
    source_node_id: str | None = None
    source_kind: SourceKind = SourceKind.PROMPT
    raw_text: str
    source_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def validate_source_hash(self) -> NormalizationSource:
        if self.source_hash != sha256_text(self.raw_text):
            raise ValueError("source_hash must match raw_text")
        return self


class InputSpecDraft(StrictModel):
    """Source-supported input facts that may be too incomplete for InputSpec."""

    name: NonEmptyStr | None = None
    semantic_type: NonEmptyStr | None = None
    producer_role_id: str | None = None
    required: bool
    format: NonEmptyStr | None = None
    schema_ref: str | None = None
    description: str | None = None


class OutputSpecDraft(StrictModel):
    """Source-supported output facts that may be too incomplete for OutputSpec."""

    name: NonEmptyStr | None = None
    semantic_type: NonEmptyStr | None = None
    consumers: list[str] | None = None
    format: NonEmptyStr | None = None
    schema_ref: str | None = None
    required_fields: list[str] | None = None
    description: str | None = None


class DependencySpecDraft(StrictModel):
    role_id: NonEmptyStr
    artifact: NonEmptyStr | None = None
    required: bool = True
    timing: NonEmptyStr | None = None
    fallback: str | None = None


class RoleContractDraft(StrictModel):
    """Lossless partial contract; ``None`` means unavailable or unresolved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_id: NonEmptyStr
    role_name: NonEmptyStr | None = None
    role_version: NonEmptyStr = "v1"
    source_initializer: NonEmptyStr
    source_node_id: str | None = None
    raw_prompt: str
    prompt_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

    goal: NonEmptyStr | None = None
    responsibilities: list[NonEmptyStr] | None = None
    success_criteria: list[NonEmptyStr] | None = None
    non_goals: list[NonEmptyStr] | None = None
    prohibited_behaviors: list[NonEmptyStr] | None = None
    priority_rules: list[NonEmptyStr] | None = None

    required_inputs: list[InputSpecDraft] | None = None
    optional_inputs: list[InputSpecDraft] | None = None
    input_visibility: Visibility | None = None
    context_assumptions: list[NonEmptyStr] | None = None

    outputs: list[OutputSpecDraft] | None = None
    output_visibility: Visibility | None = None
    failure_output: OutputSpecDraft | None = None
    format_strictness: FormatStrictness | None = None

    authority_level: AuthorityLevel | None = None
    can_override: list[str] | None = None
    requires_approval_from: list[str] | None = None
    decision_scope: list[str] | None = None
    conflict_resolution_rule: str | None = None

    upstream_dependencies: list[DependencySpecDraft] | None = None
    downstream_consumers: list[str] | None = None
    interaction_mode: InteractionMode | None = None
    max_interaction_rounds: int | None = Field(default=None, ge=1)
    termination_signal: str | None = None
    handoff_conditions: list[str] | None = None

    required_capabilities: list[str] | None = None
    resource_limits: ResourceLimits | None = None
    parent_role_version: str | None = None

    @model_validator(mode="after")
    def validate_source_and_input_buckets(self) -> RoleContractDraft:
        if self.prompt_hash != sha256_text(self.raw_prompt):
            raise ValueError("prompt_hash must match raw_prompt")
        if self.required_inputs is not None and any(
            not input_spec.required for input_spec in self.required_inputs
        ):
            raise ValueError("required_inputs entries must have required=true")
        if self.optional_inputs is not None and any(
            input_spec.required for input_spec in self.optional_inputs
        ):
            raise ValueError("optional_inputs entries must have required=false")
        return self


# This versioned boundary is intentionally independent of RoleContract.model_fields.
# Schema-only identity, source, and legacy parse-metadata fields do not belong here.
NORMALIZABLE_FIELDS: tuple[str, ...] = (
    "role_name",
    "goal",
    "responsibilities",
    "success_criteria",
    "non_goals",
    "prohibited_behaviors",
    "priority_rules",
    "required_inputs",
    "optional_inputs",
    "input_visibility",
    "context_assumptions",
    "outputs",
    "output_visibility",
    "failure_output",
    "format_strictness",
    "authority_level",
    "can_override",
    "requires_approval_from",
    "decision_scope",
    "conflict_resolution_rule",
    "upstream_dependencies",
    "downstream_consumers",
    "interaction_mode",
    "max_interaction_rounds",
    "termination_signal",
    "handoff_conditions",
    "required_capabilities",
    "resource_limits",
    "parent_role_version",
)

CORE_CONTRACT_FIELDS: tuple[str, ...] = (
    "role_name",
    "goal",
    "responsibilities",
    "outputs",
)


class FieldNormalization(StrictModel):
    """How one draft field was obtained, independent of contract semantics."""

    field_path: NonEmptyStr
    status: SourceType
    source_spans: list[SourceSpan] = Field(default_factory=list)
    confidence: Probability
    parse_risk: Probability
    rule_id: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_missing_semantics(self) -> FieldNormalization:
        if self.status is SourceType.MISSING:
            if self.source_spans:
                raise ValueError("missing fields cannot have source spans")
            if self.confidence != 0.0 or self.parse_risk != 1.0:
                raise ValueError("missing fields require confidence=0 and parse_risk=1")
        if self.status is SourceType.UNKNOWN and (
            self.confidence != 0.0 or self.parse_risk != 1.0
        ):
            raise ValueError("unknown fields require confidence=0 and parse_risk=1")
        return self


def normalization_content(
    *,
    normalizer_version: str,
    source: NormalizationSource,
    detected_language: DetectedLanguage,
    draft: RoleContractDraft,
    contract: RoleContract | None,
    field_metadata: list[FieldNormalization],
    missing_fields: list[str],
    unknown_fields: list[str],
    conflicting_fields: list[str],
    unparsed_segments: list[SourceSpan],
    warnings: list[str],
    contract_validation_errors: list[str],
    contract_parse_risk: float,
) -> dict[str, object]:
    """Return the complete JSON-compatible content covered by normalization_id."""

    return {
        "normalizer_version": normalizer_version,
        "source": source.model_dump(mode="json"),
        "detected_language": detected_language.value,
        "draft": draft.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json") if contract is not None else None,
        "field_metadata": [item.model_dump(mode="json") for item in field_metadata],
        "missing_fields": missing_fields,
        "unknown_fields": unknown_fields,
        "conflicting_fields": conflicting_fields,
        "unparsed_segments": [span.model_dump(mode="json") for span in unparsed_segments],
        "warnings": warnings,
        "contract_validation_errors": contract_validation_errors,
        "contract_parse_risk": contract_parse_risk,
    }


class NormalizationResult(StrictModel):
    """A partial draft, optional strict contract, and auditable parse metadata."""

    normalization_id: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    normalizer_version: NonEmptyStr
    source: NormalizationSource
    detected_language: DetectedLanguage
    draft: RoleContractDraft
    contract: RoleContract | None = None
    field_metadata: list[FieldNormalization]
    missing_fields: list[NonEmptyStr] = Field(default_factory=list)
    unknown_fields: list[NonEmptyStr] = Field(default_factory=list)
    conflicting_fields: list[NonEmptyStr] = Field(default_factory=list)
    unparsed_segments: list[SourceSpan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    contract_validation_errors: list[str] = Field(default_factory=list)
    contract_parse_risk: Probability

    @model_validator(mode="after")
    def validate_result_consistency(self) -> NormalizationResult:
        if self.draft.raw_prompt != self.source.raw_text:
            raise ValueError("draft raw_prompt must preserve source raw_text")
        if self.draft.prompt_hash != self.source.source_hash:
            raise ValueError("draft prompt_hash must match source_hash")
        promoted, promotion_errors = promote_draft(self.draft)
        if self.contract is not None:
            if promoted is None or promotion_errors:
                raise ValueError("contract exists but draft cannot be promoted")
            if self.contract.model_dump(mode="json") != promoted.model_dump(mode="json"):
                raise ValueError("contract must be the strict promotion of draft")
            if self.contract_validation_errors:
                raise ValueError("valid contract cannot have validation errors")
        else:
            if promoted is not None:
                raise ValueError("promotable draft must include the strict contract")
            if self.contract_validation_errors != promotion_errors:
                raise ValueError("contract_validation_errors must match draft validation")

        content = normalization_content(
            normalizer_version=self.normalizer_version,
            source=self.source,
            detected_language=self.detected_language,
            draft=self.draft,
            contract=self.contract,
            field_metadata=self.field_metadata,
            missing_fields=list(self.missing_fields),
            unknown_fields=list(self.unknown_fields),
            conflicting_fields=list(self.conflicting_fields),
            unparsed_segments=self.unparsed_segments,
            warnings=list(self.warnings),
            contract_validation_errors=list(self.contract_validation_errors),
            contract_parse_risk=self.contract_parse_risk,
        )
        if self.normalization_id != canonical_json_hash(content):
            raise ValueError("normalization_id must match complete normalization content")

        paths = [metadata.field_path for metadata in self.field_metadata]
        if len(paths) != len(set(paths)):
            raise ValueError("field_metadata paths must be unique")
        if set(paths) != set(NORMALIZABLE_FIELDS):
            raise ValueError("field_metadata must cover the versioned normalizable fields")

        for values in (
            self.missing_fields,
            self.unknown_fields,
            self.conflicting_fields,
        ):
            if len(values) != len(set(values)):
                raise ValueError("normalization field lists cannot contain duplicates")

        metadata_by_path = {metadata.field_path: metadata for metadata in self.field_metadata}
        expected_missing = {
            path for path, item in metadata_by_path.items() if item.status is SourceType.MISSING
        }
        expected_unknown = {
            path for path, item in metadata_by_path.items() if item.status is SourceType.UNKNOWN
        }
        if set(self.missing_fields) != expected_missing:
            raise ValueError("missing_fields must exactly match missing metadata")
        if set(self.unknown_fields) != expected_unknown:
            raise ValueError("unknown_fields must exactly match unknown metadata")
        for path in (*self.missing_fields, *self.unknown_fields, *self.conflicting_fields):
            if path not in metadata_by_path:
                raise ValueError(f"normalization metadata references unknown field: {path}")

        for span in [
            *(span for metadata in self.field_metadata for span in metadata.source_spans),
            *self.unparsed_segments,
        ]:
            if span.end > len(self.source.raw_text):
                raise ValueError("source span exceeds source text")
            if self.source.raw_text[span.start : span.end] != span.text:
                raise ValueError("source span text does not match source text")
        return self


def _promotable_payload(draft: RoleContractDraft) -> dict[str, object]:
    return draft.model_dump(mode="json")


def promote_draft(draft: RoleContractDraft) -> tuple[RoleContract | None, list[str]]:
    """Promote a complete draft without inventing canonical defaults or facts."""

    from pydantic import ValidationError

    payload = _promotable_payload(draft)
    try:
        contract = RoleContract.model_validate(payload)
    except ValidationError as error:
        messages = []
        for item in error.errors(include_url=False):
            location = ".".join(str(part) for part in item["loc"])
            messages.append(f"{location}: {item['msg']}")
        return None, sorted(messages)
    return contract, []
