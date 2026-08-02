"""Runtime interfaces for deterministic controlled aggregation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from rolecheck.schemas import (
    AggregatorIdentity,
    ArtifactSnapshot,
    NodeExecutorIdentity,
    RoleContract,
    TaskSpec,
)


def isolated_json_copy(value: object) -> object:
    """Return a deterministic JSON copy that cannot mutate its source."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return json.loads(payload)


def isolated_task_copy(task: TaskSpec) -> TaskSpec:
    """Return a validated task copy isolated from aggregator mutation."""

    return TaskSpec.model_validate(isolated_json_copy(task.model_dump(mode="json")))


def isolated_role_copy(role: RoleContract) -> RoleContract:
    """Return a validated role copy isolated from executor mutation."""

    return RoleContract.model_validate(isolated_json_copy(role.model_dump(mode="json")))


@dataclass(frozen=True)
class FrozenRoleResponse:
    """One baseline response supplied to an aggregator."""

    role_id: str
    output: object
    output_hash: str


@dataclass(frozen=True)
class AggregationRequest:
    """An ordered, seed-controlled aggregation request."""

    task: TaskSpec
    responses: tuple[FrozenRoleResponse, ...]
    aggregation_seed: int


class Aggregator(Protocol):
    """Dependency-injected aggregator; it never executes role nodes."""

    @property
    def identity(self) -> AggregatorIdentity: ...

    @property
    def accepts_variable_responses(self) -> bool: ...

    def aggregate(self, request: AggregationRequest) -> object: ...


@dataclass(frozen=True)
class FrozenNodeInput:
    """One immutable-by-contract artifact supplied to a role node."""

    input_name: str
    artifact: ArtifactSnapshot


@dataclass(frozen=True)
class NodeExecutionRequest:
    """A seed-controlled request for exactly one DAG role node."""

    task: TaskSpec
    role: RoleContract
    inputs: tuple[FrozenNodeInput, ...]
    role_seed: int


class NodeExecutor(Protocol):
    """Dependency-injected node executor; implementations return named artifacts."""

    @property
    def identity(self) -> NodeExecutorIdentity: ...

    def execute(self, request: NodeExecutionRequest) -> dict[str, object]: ...
