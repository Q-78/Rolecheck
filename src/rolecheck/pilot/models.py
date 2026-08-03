"""Strict evidence models for the bounded server pilot."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from rolecheck.hashing import canonical_json_hash
from rolecheck.schemas.models import StrictModel


class AnswerParseStatus(StrEnum):
    """Deterministic terminal-answer parser outcome."""

    VALID = "valid"
    INVALID = "invalid"


class AnswerParseResult(StrictModel):
    """Answer evidence derived only from final visible model content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    final_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    option_count: int = Field(ge=2, le=10)
    status: AnswerParseStatus
    answer_letter: str | None = Field(default=None, pattern=r"^[A-J]$")
    invalid_reason: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> AnswerParseResult:
        if self.status is AnswerParseStatus.VALID:
            if self.answer_letter is None or self.invalid_reason is not None:
                raise ValueError("valid answer parse requires only an answer letter")
            if ord(self.answer_letter) - ord("A") >= self.option_count:
                raise ValueError("answer letter exceeds the available option range")
        elif self.answer_letter is not None or not self.invalid_reason:
            raise ValueError("invalid answer parse requires only an invalid reason")
        return self


class ParsedModelText(StrictModel):
    """Deterministic separation of optional thinking text and visible content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reasoning: str | None = None
    final_content: str
    structure_valid: bool
    invalid_reason: str | None = None

    @model_validator(mode="after")
    def validate_structure(self) -> ParsedModelText:
        if self.structure_valid == (self.invalid_reason is not None):
            raise ValueError("thinking-text validity and reason are inconsistent")
        return self


class RawGeneration(StrictModel):
    """Provider-neutral generation returned by an injected local engine."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_token_ids: list[int] = Field(default_factory=list)
    raw_decoded_output: str
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_token_count(self) -> RawGeneration:
        if self.output_token_count != len(self.raw_token_ids):
            raise ValueError("output token count must match raw generated token IDs")
        if any(token_id < 0 for token_id in self.raw_token_ids):
            raise ValueError("raw generated token IDs cannot be negative")
        return self


class RenderedRolePrompt(StrictModel):
    """Frozen two-message chat input before tokenizer templating."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    messages_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_messages_hash(self) -> RenderedRolePrompt:
        expected = canonical_json_hash(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_prompt},
            ]
        )
        if self.messages_hash != expected:
            raise ValueError("rendered Prompt hash does not match frozen messages")
        return self


class PilotRoleOutput(StrictModel):
    """Complete per-role execution evidence retained by Pilot v0.1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role_id: str = Field(min_length=1)
    role_seed: int = Field(ge=0)
    rendered_prompt_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    raw_token_ids: list[int] = Field(default_factory=list)
    raw_decoded_output: str
    raw_output_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parsed_reasoning: str | None = None
    parsed_final_content: str
    answer_parse: AnswerParseResult
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_evidence(self) -> PilotRoleOutput:
        if self.raw_output_hash != canonical_json_hash(self.raw_decoded_output):
            raise ValueError("raw output hash does not match decoded output")
        if self.answer_parse.final_content_hash != canonical_json_hash(self.parsed_final_content):
            raise ValueError("answer parse does not match parsed final content")
        if self.output_token_count != len(self.raw_token_ids):
            raise ValueError("output token count must match retained token IDs")
        return self


class MajorityVoteResult(StrictModel):
    """Deterministic, model-free aggregation output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: Literal["strict_majority_then_lexicographic_tie_v0.1"] = (
        "strict_majority_then_lexicographic_tie_v0.1"
    )
    ordered_role_ids: list[str] = Field(min_length=1)
    valid_votes: dict[str, str] = Field(default_factory=dict)
    invalid_role_ids: list[str] = Field(default_factory=list)
    vote_counts: dict[str, int] = Field(default_factory=dict)
    selected_answer: str | None = Field(default=None, pattern=r"^[A-J]$")
    strict_majority: bool
    tie_break_applied: bool

    @model_validator(mode="after")
    def validate_vote_evidence(self) -> MajorityVoteResult:
        ordered = self.ordered_role_ids
        if len(ordered) != len(set(ordered)):
            raise ValueError("aggregation role IDs must be unique")
        if set(ordered) != set(self.valid_votes) | set(self.invalid_role_ids):
            raise ValueError("valid and invalid votes must partition aggregation roles")
        if set(self.valid_votes) & set(self.invalid_role_ids):
            raise ValueError("a role cannot have both a valid and invalid vote")
        expected_counts: dict[str, int] = {}
        for letter in self.valid_votes.values():
            expected_counts[letter] = expected_counts.get(letter, 0) + 1
        if self.vote_counts != dict(sorted(expected_counts.items())):
            raise ValueError("vote counts must match valid role votes")
        if not expected_counts:
            if self.selected_answer is not None or self.strict_majority:
                raise ValueError("no-valid-vote result cannot select an answer")
            if self.tie_break_applied:
                raise ValueError("no-valid-vote result cannot apply a tie break")
            return self
        if self.selected_answer not in expected_counts:
            raise ValueError("selected answer must be present in valid votes")
        maximum = max(expected_counts.values())
        leaders = sorted(letter for letter, count in expected_counts.items() if count == maximum)
        expected_majority = maximum > len(self.valid_votes) / 2
        if self.strict_majority is not expected_majority:
            raise ValueError("strict-majority flag does not match vote counts")
        if self.selected_answer != leaders[0]:
            raise ValueError("selected answer does not follow the frozen tie policy")
        expected_tie_break = not expected_majority and len(leaders) > 1
        if self.tie_break_applied is not expected_tie_break:
            raise ValueError("tie-break flag does not match vote counts")
        return self
