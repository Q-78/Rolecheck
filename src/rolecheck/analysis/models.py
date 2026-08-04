"""Strict records for Gate 6.1A counterfactuals and post-seal labels."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from rolecheck.schemas.models import StrictModel


class ExhaustiveRemovalRecord(StrictModel):
    """Gold-free deterministic record sealed before evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str
    category: str
    role_id: str
    baseline_aggregation_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    exhaustive_removal_aggregation_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    retained_role_ids: list[str]
    retained_role_output_hashes: dict[str, str]
    removed_role_output_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_selected_answer: str | None
    removed_selected_answer: str | None
    baseline_scorable: bool
    removed_scorable: bool
    baseline_tie_break_applied: bool
    removal_tie_break_applied: bool
    baseline_strict_majority: bool
    removal_strict_majority: bool
    baseline_invalid_role_ids: list[str]
    removal_invalid_role_ids: list[str]
    baseline_vote_pattern: str
    valid_execution: bool = True
    invalid_reason: str | None = None
    protocol_id: str
    aggregator_identity: dict[str, str]
    source_gate6_root_hash: str
    analysis_version: Literal["v0.1"] = "v0.1"
    role_reexecutions: int = 0


class EvaluatedRemovalRecord(StrictModel):
    """Independent post-seal label record referencing a counterfactual hash."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    counterfactual_record_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    task_id: str
    category: str
    role_id: str
    baseline_correct: bool | None
    removed_correct: bool | None
    outcome_transition: Literal[
        "correct_to_wrong", "correct_to_correct", "wrong_to_correct", "wrong_to_wrong", "unscorable"
    ]
    answer_changed: bool | None
    keep_value: Literal[-1, 0, 1] | None
    tie_dependent: bool
    invalid_vote_related: bool
