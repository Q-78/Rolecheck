"""Exact deterministic score aggregation for the isolated Gate 6.2 condition."""

from __future__ import annotations

from fractions import Fraction

from rolecheck.hashing import canonical_json_hash
from rolecheck.signal.models import (
    DeterministicScoreAggregationResult,
    ExactScore,
    Gate62ProtocolIdentity,
    RoleScoreEvidence,
)
from rolecheck.signal.tie_break import deterministic_tie_order


class DeterministicScoreAggregator:
    def __init__(self, identity: Gate62ProtocolIdentity | None = None) -> None:
        self.identity = identity or Gate62ProtocolIdentity()
        self.config_hash = canonical_json_hash(self.identity.model_dump(mode="json"))

    def aggregate(
        self,
        *,
        task_id: str,
        task_hash: str,
        option_letters: list[str],
        required_role_ids: list[str],
        role_outputs: list[RoleScoreEvidence | None],
    ) -> DeterministicScoreAggregationResult:
        if len(required_role_ids) != len(set(required_role_ids)):
            raise ValueError("required role IDs must be unique")
        if len(role_outputs) != len(required_role_ids):
            raise ValueError("one response slot is required for every role")
        tie_order, tie_hash = deterministic_tie_order(
            option_letters,
            task_id=task_id,
            task_hash=task_hash,
            aggregator_version=self.identity.aggregator_version,
            namespace=self.identity.tie_break_namespace,
        )
        valid: list[RoleScoreEvidence] = []
        invalid: list[str] = []
        for expected, evidence in zip(required_role_ids, role_outputs, strict=True):
            if evidence is None:
                invalid.append(expected)
                continue
            if evidence.role_id != expected:
                raise ValueError("role identity/order mismatch")
            if set(evidence.output.option_scores.scores) != set(option_letters):
                raise ValueError("role output option-set mismatch")
            valid.append(evidence)
        if invalid:
            return DeterministicScoreAggregationResult(
                scorable=False,
                ordered_role_ids=required_role_ids,
                valid_role_ids=[item.role_id for item in valid],
                invalid_role_ids=invalid,
                per_role_scores={item.role_id: item.output.option_scores.scores for item in valid},
                total_scores={},
                mean_scores={},
                tie_break_order=tie_order,
                tie_break_order_hash=tie_hash,
                aggregator_id=self.identity.aggregator_id,
                aggregator_version=self.identity.aggregator_version,
                config_hash=self.config_hash,
            )
        totals = {
            letter: sum(item.output.option_scores.scores[letter] for item in valid)
            for letter in option_letters
        }
        means = {
            letter: ExactScore.from_fraction(Fraction(total, len(valid)))
            for letter, total in totals.items()
        }
        maximum = max(totals.values())
        tied = [letter for letter in option_letters if totals[letter] == maximum]
        selected = next(letter for letter in tie_order if letter in tied)
        distinct = sorted(set(totals.values()), reverse=True)
        second_total = distinct[1] if len(distinct) > 1 else distinct[0]
        return DeterministicScoreAggregationResult(
            scorable=True,
            ordered_role_ids=required_role_ids,
            valid_role_ids=required_role_ids,
            invalid_role_ids=[],
            per_role_scores={item.role_id: item.output.option_scores.scores for item in valid},
            total_scores=totals,
            mean_scores=means,
            selected_answer=selected,
            top_score=ExactScore.from_fraction(Fraction(maximum, len(valid))),
            second_score=ExactScore.from_fraction(Fraction(second_total, len(valid))),
            score_margin=ExactScore.from_fraction(Fraction(maximum - second_total, len(valid))),
            tied_options=tied,
            tie_break_applied=len(tied) > 1,
            tie_break_order=tie_order,
            tie_break_order_hash=tie_hash,
            aggregator_id=self.identity.aggregator_id,
            aggregator_version=self.identity.aggregator_version,
            config_hash=self.config_hash,
        )
