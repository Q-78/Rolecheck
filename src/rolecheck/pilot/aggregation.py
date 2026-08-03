"""Frozen model-free aggregation for Pilot v0.1."""

from __future__ import annotations

from rolecheck.hashing import canonical_json_hash
from rolecheck.pilot.models import AnswerParseStatus, MajorityVoteResult, PilotRoleOutput
from rolecheck.runtime.interfaces import AggregationRequest
from rolecheck.schemas import AggregatorIdentity


class DeterministicMajorityAggregator:
    """Parse retained role evidence and vote without executing any model."""

    _ID = "rolecheck.pilot.deterministic_majority"
    _VERSION = "v0.1"
    _POLICY = "strict_majority_then_lexicographic_tie_v0.1"

    def __init__(self) -> None:
        self._identity = AggregatorIdentity(
            aggregator_id=self._ID,
            aggregator_version=self._VERSION,
            config_hash=canonical_json_hash(
                {
                    "aggregator_id": self._ID,
                    "aggregator_version": self._VERSION,
                    "policy": self._POLICY,
                    "invalid_vote_policy": "exclude_without_compensation",
                    "option_count_source": "TaskSpec.public_metadata.options",
                    "role_output_schema": "PilotRoleOutput.v0.1",
                    "model_calls": False,
                    "variable_arity": True,
                }
            ),
        )

    @property
    def identity(self) -> AggregatorIdentity:
        return self._identity.model_copy(deep=True)

    @property
    def accepts_variable_responses(self) -> bool:
        return True

    def aggregate(self, request: AggregationRequest) -> object:
        _ = request.aggregation_seed
        options = request.task.public_metadata.get("options")
        if not isinstance(options, list) or not 2 <= len(options) <= 10:
            raise ValueError("aggregator task requires between 2 and 10 ordered options")
        option_count = len(options)
        ordered_role_ids: list[str] = []
        valid_votes: dict[str, str] = {}
        invalid_role_ids: list[str] = []
        for response in request.responses:
            if canonical_json_hash(response.output) != response.output_hash:
                raise ValueError("aggregator received a role-output hash mismatch")
            output = PilotRoleOutput.model_validate(response.output)
            if output.role_id != response.role_id:
                raise ValueError("aggregator response role identity mismatch")
            if output.answer_parse.option_count != option_count:
                raise ValueError("aggregator response option-count mismatch")
            ordered_role_ids.append(response.role_id)
            if output.answer_parse.status is AnswerParseStatus.VALID:
                assert output.answer_parse.answer_letter is not None
                valid_votes[response.role_id] = output.answer_parse.answer_letter
            else:
                invalid_role_ids.append(response.role_id)

        vote_counts: dict[str, int] = {}
        for letter in valid_votes.values():
            vote_counts[letter] = vote_counts.get(letter, 0) + 1
        vote_counts = dict(sorted(vote_counts.items()))
        if not vote_counts:
            return MajorityVoteResult(
                ordered_role_ids=ordered_role_ids,
                valid_votes=valid_votes,
                invalid_role_ids=invalid_role_ids,
                vote_counts=vote_counts,
                strict_majority=False,
                tie_break_applied=False,
            ).model_dump(mode="json")
        maximum = max(vote_counts.values())
        leaders = sorted(letter for letter, count in vote_counts.items() if count == maximum)
        strict_majority = maximum > len(valid_votes) / 2
        return MajorityVoteResult(
            ordered_role_ids=ordered_role_ids,
            valid_votes=valid_votes,
            invalid_role_ids=invalid_role_ids,
            vote_counts=vote_counts,
            selected_answer=leaders[0],
            strict_majority=strict_majority,
            tie_break_applied=not strict_majority and len(leaders) > 1,
        ).model_dump(mode="json")
