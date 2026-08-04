"""Gate 6.2 structured role-value signal design."""

from rolecheck.signal.aggregation import DeterministicScoreAggregator
from rolecheck.signal.evaluation import evaluate_keep_value
from rolecheck.signal.models import *  # noqa: F403
from rolecheck.signal.parsing import parse_structured_role_output

__all__ = ["DeterministicScoreAggregator", "evaluate_keep_value", "parse_structured_role_output"]
