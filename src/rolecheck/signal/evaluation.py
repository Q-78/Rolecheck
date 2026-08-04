"""Post-seal hard and soft Keep Value evaluation."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from rolecheck.signal.models import (
    DeterministicScoreAggregationResult,
    ExactScore,
    HardKeepValueEvaluation,
    SoftKeepValueEvaluation,
    StructuredRemovalEvaluation,
)


def evaluate_keep_value(
    removal: StructuredRemovalEvaluation, *, gold_answer: str
) -> tuple[HardKeepValueEvaluation, SoftKeepValueEvaluation]:
    baseline_answer = removal.baseline.selected_answer
    removed_answer = removal.removal.selected_answer
    assert baseline_answer is not None and removed_answer is not None
    baseline_correct = baseline_answer == gold_answer
    removed_correct = removed_answer == gold_answer
    transition: Literal[
        "correct_to_wrong", "correct_to_correct", "wrong_to_correct", "wrong_to_wrong"
    ]
    hard: Literal[-1, 0, 1]
    if baseline_correct and not removed_correct:
        transition, hard = "correct_to_wrong", 1
    elif baseline_correct and removed_correct:
        transition, hard = "correct_to_correct", 0
    elif not baseline_correct and removed_correct:
        transition, hard = "wrong_to_correct", -1
    else:
        transition, hard = "wrong_to_wrong", 0
    hard_result = HardKeepValueEvaluation(
        outcome_transition=transition,
        hard_keep_value=hard,
        answer_changed=baseline_answer != removed_answer,
        tie_dependent=removal.baseline.tie_break_applied or removal.removal.tie_break_applied,
    )

    def margin(
        aggregation: DeterministicScoreAggregationResult,
    ) -> tuple[Fraction, Fraction, Fraction]:
        means = aggregation.mean_scores
        gold = means[gold_answer].as_fraction()
        wrong = max(score.as_fraction() for letter, score in means.items() if letter != gold_answer)
        return gold, wrong, gold - wrong

    bg, bw, bm = margin(removal.baseline)
    rg, rw, rm = margin(removal.removal)
    delta = bm - rm
    soft_result = SoftKeepValueEvaluation(
        baseline_gold_score=ExactScore.from_fraction(bg),
        baseline_best_wrong_score=ExactScore.from_fraction(bw),
        baseline_gold_margin=ExactScore.from_fraction(bm),
        removed_gold_score=ExactScore.from_fraction(rg),
        removed_best_wrong_score=ExactScore.from_fraction(rw),
        removed_gold_margin=ExactScore.from_fraction(rm),
        soft_keep_value=ExactScore.from_fraction(delta),
        exactly_zero=delta == 0,
    )
    return hard_result, soft_result
