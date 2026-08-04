"""Strict, Gold-free contracts for Gate 6.2 structured-score evidence."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, field_validator, model_validator

from rolecheck.hashing import canonical_json_hash
from rolecheck.schemas.models import StrictModel

SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
EVIDENCE_MAX_CHARS = 240


class FrozenModel(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def canonical_hash(self) -> str:
        return canonical_json_hash(self.model_dump(mode="json"))


class ExactScore(FrozenModel):
    numerator: int
    denominator: int = Field(gt=0)

    @model_validator(mode="after")
    def reduced(self) -> ExactScore:
        value = Fraction(self.numerator, self.denominator)
        if (value.numerator, value.denominator) != (self.numerator, self.denominator):
            raise ValueError("exact score must be stored in reduced form")
        return self

    def as_fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    @classmethod
    def from_fraction(cls, value: Fraction) -> ExactScore:
        return cls(numerator=value.numerator, denominator=value.denominator)


class OptionScoreVector(FrozenModel):
    scores: dict[str, StrictInt]

    @field_validator("scores")
    @classmethod
    def valid_scores(cls, value: dict[str, int]) -> dict[str, int]:
        if not 2 <= len(value) <= 10:
            raise ValueError("option score vector requires 2 to 10 options")
        expected = [chr(ord("A") + index) for index in range(len(value))]
        if sorted(value) != expected:
            raise ValueError("option keys must be the contiguous letters A onward")
        if any(score < 0 or score > 100 for score in value.values()):
            raise ValueError("option scores must be between 0 and 100")
        if sum(value.values()) != 100:
            raise ValueError("option scores must sum exactly to 100")
        return dict(sorted(value.items()))


class StructuredRoleOutput(FrozenModel):
    option_scores: OptionScoreVector
    key_evidence: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("key_evidence")
    @classmethod
    def brief_evidence(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > EVIDENCE_MAX_CHARS for item in value):
            raise ValueError("evidence must be nonblank and at most 240 characters")
        return value


class StructuredRoleOutputParseResult(FrozenModel):
    status: Literal["valid", "invalid"]
    raw_output_hash: str = Field(pattern=SHA256_PATTERN)
    output: StructuredRoleOutput | None = None
    output_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    invalid_reason: str | None = None

    @model_validator(mode="after")
    def consistent(self) -> StructuredRoleOutputParseResult:
        if self.status == "valid":
            if self.output is None or self.output_hash != self.output.canonical_hash:
                raise ValueError("valid parse requires matching structured output and hash")
            if self.invalid_reason is not None:
                raise ValueError("valid parse cannot have an invalid reason")
        elif self.output is not None or self.output_hash is not None or not self.invalid_reason:
            raise ValueError("invalid parse requires only an invalid reason")
        return self


class Gate62ProtocolIdentity(FrozenModel):
    protocol_id: Literal["rolecheck.gate62.structured_score"] = "rolecheck.gate62.structured_score"
    protocol_version: Literal["v0.1"] = "v0.1"
    role_output_schema: Literal["StructuredRoleOutput.v0.1"] = "StructuredRoleOutput.v0.1"
    aggregator_id: Literal["rolecheck.signal.deterministic_score"] = (
        "rolecheck.signal.deterministic_score"
    )
    aggregator_version: Literal["v0.1"] = "v0.1"
    tie_break_namespace: Literal["rolecheck.gate62.tie-break.v0.1"] = (
        "rolecheck.gate62.tie-break.v0.1"
    )


class RoleScoreEvidence(FrozenModel):
    role_id: str = Field(min_length=1)
    output: StructuredRoleOutput
    output_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def hash_matches(self) -> RoleScoreEvidence:
        if self.output_hash != self.output.canonical_hash:
            raise ValueError("role output hash mismatch")
        return self


class DeterministicScoreAggregationResult(FrozenModel):
    scorable: bool
    ordered_role_ids: list[str]
    valid_role_ids: list[str]
    invalid_role_ids: list[str]
    per_role_scores: dict[str, dict[str, int]]
    total_scores: dict[str, int]
    mean_scores: dict[str, ExactScore]
    selected_answer: str | None = None
    top_score: ExactScore | None = None
    second_score: ExactScore | None = None
    score_margin: ExactScore | None = None
    tied_options: list[str] = Field(default_factory=list)
    tie_break_applied: bool = False
    tie_break_order: list[str]
    tie_break_order_hash: str = Field(pattern=SHA256_PATTERN)
    aggregator_id: str
    aggregator_version: str
    config_hash: str = Field(pattern=SHA256_PATTERN)


class StructuredRemovalEvaluation(FrozenModel):
    task_id: str = Field(min_length=1)
    task_hash: str = Field(pattern=SHA256_PATTERN)
    removed_role_id: str = Field(min_length=1)
    baseline_input_hash: str = Field(pattern=SHA256_PATTERN)
    removal_input_hash: str = Field(pattern=SHA256_PATTERN)
    baseline_role_output_hashes: dict[str, str]
    removal_role_output_hashes: dict[str, str]
    baseline: DeterministicScoreAggregationResult
    removal: DeterministicScoreAggregationResult
    retained_role_ids: list[str]
    role_reexecutions: Literal[0] = 0

    @model_validator(mode="after")
    def exact_single_drop(self) -> StructuredRemovalEvaluation:
        if not self.baseline.scorable or not self.removal.scorable:
            raise ValueError("removal requires a complete, scorable baseline and retained set")
        if set(self.baseline.valid_role_ids) - {self.removed_role_id} != set(
            self.retained_role_ids
        ):
            raise ValueError("removal must drop exactly the named baseline role")
        if self.removal.valid_role_ids != self.retained_role_ids:
            raise ValueError("removal roles must be the ordered retained baseline roles")
        if list(self.baseline_role_output_hashes) != self.baseline.valid_role_ids:
            raise ValueError("baseline output hashes must follow baseline role order")
        if list(self.removal_role_output_hashes) != self.retained_role_ids:
            raise ValueError("removal output hashes must follow retained role order")
        if self.removal_role_output_hashes != {
            role: self.baseline_role_output_hashes[role] for role in self.retained_role_ids
        }:
            raise ValueError("removal must reuse retained baseline output hashes")
        if self.baseline_input_hash != canonical_json_hash(self.baseline_role_output_hashes):
            raise ValueError("baseline input hash mismatch")
        if self.removal_input_hash != canonical_json_hash(self.removal_role_output_hashes):
            raise ValueError("removal input hash mismatch")
        return self


class HardKeepValueEvaluation(FrozenModel):
    outcome_transition: Literal[
        "correct_to_wrong", "correct_to_correct", "wrong_to_correct", "wrong_to_wrong"
    ]
    hard_keep_value: Literal[-1, 0, 1]
    answer_changed: bool
    tie_dependent: bool


class SoftKeepValueEvaluation(FrozenModel):
    baseline_gold_score: ExactScore
    baseline_best_wrong_score: ExactScore
    baseline_gold_margin: ExactScore
    removed_gold_score: ExactScore
    removed_best_wrong_score: ExactScore
    removed_gold_margin: ExactScore
    soft_keep_value: ExactScore
    exactly_zero: bool
