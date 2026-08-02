"""Deterministic local node executor for controlled DAG protocol tests."""

from __future__ import annotations

from rolecheck.hashing import canonical_json_hash
from rolecheck.runtime.interfaces import NodeExecutionRequest
from rolecheck.schemas import NodeExecutorIdentity


class MockNodeExecutor:
    """Produce explicit mock artifacts without model or network calls."""

    _identity = NodeExecutorIdentity(
        executor_id="deterministic-mock-node-executor",
        executor_version="v1",
        config_hash=canonical_json_hash(
            {"kind": "named-artifact-hash-summary", "version": "v1"}
        ),
    )

    @property
    def identity(self) -> NodeExecutorIdentity:
        return self._identity

    def execute(self, request: NodeExecutionRequest) -> dict[str, object]:
        input_hashes = {
            item.input_name: item.artifact.payload_hash for item in request.inputs
        }
        artifacts: dict[str, object] = {}
        for output in request.role.outputs:
            payload: dict[str, object] = {
                field: f"mock:{request.role.role_id}:{output.name}:{field}"
                for field in output.required_fields
            }
            payload.setdefault(
                "_mock",
                {
                "mock": True,
                "role_id": request.role.role_id,
                "artifact_name": output.name,
                "input_hashes": input_hashes,
                "role_seed": request.role_seed,
                },
            )
            artifacts[output.name] = payload
        return artifacts
