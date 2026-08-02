"""Deterministic local aggregator used by the Mock Runtime."""

from __future__ import annotations

from rolecheck.hashing import canonical_json_hash
from rolecheck.runtime.interfaces import AggregationRequest
from rolecheck.schemas import AggregatorIdentity


class MockAggregator:
    """Aggregate response hashes without model or network calls."""

    _identity = AggregatorIdentity(
        aggregator_id="fixed-mock-aggregation",
        aggregator_version="v1",
        config_hash=canonical_json_hash(
            {"kind": "ordered-response-hash-summary", "version": "v1"}
        ),
    )

    @property
    def identity(self) -> AggregatorIdentity:
        return self._identity

    @property
    def accepts_variable_responses(self) -> bool:
        return True

    def aggregate(self, request: AggregationRequest) -> object:
        return {
            "mock": True,
            "ordered_roles": [response.role_id for response in request.responses],
            "role_output_hashes": {
                response.role_id: response.output_hash for response in request.responses
            },
        }
