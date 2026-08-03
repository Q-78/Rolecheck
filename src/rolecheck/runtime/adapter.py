"""Offline Runtime Adapter protocol and non-empirical implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from pydantic import ConfigDict, Field, model_validator

from rolecheck.benchmark import TaskSplitManifest
from rolecheck.config import MockRuntimeConfig
from rolecheck.hashing import canonical_json_hash, derive_seed, role_contract_hash
from rolecheck.manifest import ExperimentManifest
from rolecheck.runtime.interfaces import Aggregator, isolated_json_copy
from rolecheck.runtime.mock import MockRuntime
from rolecheck.schemas import (
    CanonicalTeamConfig,
    ExecutionRecord,
    ExecutionStatus,
    RuntimeAdapterIdentity,
    SeedBundle,
    TaskSpec,
)
from rolecheck.schemas.models import StrictModel


@dataclass(frozen=True)
class RuntimeExecutionRequest:
    """Validated inputs and frozen manifests for one offline execution."""

    task: TaskSpec
    team: CanonicalTeamConfig
    experiment_manifest: ExperimentManifest
    task_split_manifest: TaskSplitManifest


class RuntimeAdapterResult(StrictModel):
    """Preflight rejection or existing execution evidence from an adapter."""

    adapter: RuntimeAdapterIdentity
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    accepted: bool
    execution: ExecutionRecord | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
    synthetic: Literal[True] = True
    non_empirical: Literal[True] = True

    @model_validator(mode="after")
    def validate_outcome(self) -> RuntimeAdapterResult:
        if self.accepted:
            if self.execution is None:
                raise ValueError("accepted runtime request requires execution evidence")
            if self.rejection_reasons:
                raise ValueError("accepted runtime request cannot contain rejection reasons")
            if not self.execution.mock:
                raise ValueError("offline runtime evidence must be marked mock")
        else:
            if self.execution is not None:
                raise ValueError("rejected runtime request cannot contain execution evidence")
            if not self.rejection_reasons:
                raise ValueError("rejected runtime request requires reasons")
        return self


class RuntimeAdapter(Protocol):
    """Dependency-injected runtime boundary without provider assumptions."""

    @property
    def identity(self) -> RuntimeAdapterIdentity: ...

    def execute(self, request: RuntimeExecutionRequest) -> RuntimeAdapterResult: ...


class RuntimeCallRecord(StrictModel):
    """In-memory audit record that stores hashes, not task or Prompt content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_index: int = Field(ge=0)
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    result: RuntimeAdapterResult


class FakeRuntimeAdapter:
    """Manifest-gated adapter over the deterministic, network-free Mock Runtime."""

    def __init__(
        self,
        config: MockRuntimeConfig,
        aggregator: Aggregator | None = None,
        *,
        runtime_version: str = "v0.1",
    ) -> None:
        self._runtime = MockRuntime(config, aggregator=aggregator)
        aggregator_identity = self._runtime.aggregator_identity
        self._identity = RuntimeAdapterIdentity(
            runtime_id=config.runtime_id,
            runtime_version=runtime_version,
            config_hash=canonical_json_hash(
                {
                    "runtime_config": config.model_dump(mode="json"),
                    "aggregator": aggregator_identity.model_dump(mode="json"),
                }
            ),
        )

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        return RuntimeAdapterIdentity.model_validate(
            self._identity.model_dump(mode="json")
        )

    def execute(self, request: RuntimeExecutionRequest) -> RuntimeAdapterResult:
        task, team, manifest, split = _isolate_request(request)
        request_hash = _request_hash(task, team, manifest, split)
        manifest_hash = canonical_json_hash(manifest.model_dump(mode="json"))
        rejection_reasons = self._preflight(task, team, manifest, split)
        if rejection_reasons:
            return RuntimeAdapterResult(
                adapter=self.identity,
                request_hash=request_hash,
                manifest_hash=manifest_hash,
                accepted=False,
                rejection_reasons=rejection_reasons,
            )

        try:
            execution = self._runtime.run(
                task=task,
                team=team,
                experiment_id=manifest.experiment_id,
                experiment_seed=manifest.seed,
            )
            _validate_execution(execution, task, team, manifest)
        except Exception as exc:
            execution = _failed_execution(task, team, manifest, exc)
        return RuntimeAdapterResult(
            adapter=self.identity,
            request_hash=request_hash,
            manifest_hash=manifest_hash,
            accepted=True,
            execution=execution,
        )

    def _preflight(
        self,
        task: TaskSpec,
        team: CanonicalTeamConfig,
        manifest: ExperimentManifest,
        split: TaskSplitManifest,
    ) -> list[str]:
        reasons: list[str] = []
        expected_models = {agent.agent_id: agent.model_id for agent in team.agents}
        expected_tools = {tool_id for agent in team.agents for tool_id in agent.tool_ids}
        expected_prompts = {role.role_id: role.prompt_hash for role in team.roles}
        expected_contracts = {
            role.role_id: role_contract_hash(role.model_dump(mode="json"))
            for role in team.roles
        }
        aggregator = self._runtime.aggregator_identity
        checks = (
            ("manifest_not_mock", manifest.mock),
            ("runtime_id_mismatch", manifest.runtime_id == self.identity.runtime_id),
            (
                "runtime_version_mismatch",
                manifest.runtime_version == self.identity.runtime_version,
            ),
            (
                "runtime_config_hash_mismatch",
                manifest.runtime_config_hash == self.identity.config_hash,
            ),
            (
                "protocol_id_mismatch",
                manifest.protocol_id == team.execution_protocol.protocol_id,
            ),
            (
                "removal_protocol_id_mismatch",
                manifest.removal_protocol_id
                == team.removal_protocol.removal_protocol_id,
            ),
            (
                "initializer_id_mismatch",
                manifest.initializer_id == team.source_initializer,
            ),
            (
                "team_config_hash_mismatch",
                manifest.team_config_hash
                == canonical_json_hash(team.model_dump(mode="json")),
            ),
            (
                "model_versions_mismatch",
                dict(manifest.model_versions) == expected_models,
            ),
            (
                "tool_id_set_mismatch",
                set(manifest.tool_hashes) == expected_tools,
            ),
            (
                "prompt_hashes_mismatch",
                dict(manifest.prompt_hashes) == expected_prompts,
            ),
            (
                "role_contract_hashes_mismatch",
                dict(manifest.role_contract_hashes) == expected_contracts,
            ),
            (
                "aggregator_id_mismatch",
                manifest.aggregator_id == aggregator.aggregator_id,
            ),
            (
                "aggregator_version_mismatch",
                manifest.aggregator_version == aggregator.aggregator_version,
            ),
            (
                "aggregator_config_hash_mismatch",
                manifest.aggregator_config_hash == aggregator.config_hash,
            ),
            (
                "dataset_revision_mismatch",
                manifest.dataset_revision == split.dataset_revision,
            ),
            (
                "task_split_hash_mismatch",
                manifest.task_split_hash == split.split_hash,
            ),
            (
                "task_not_in_split",
                any(task.task_id in partition.task_ids for partition in split.partitions),
            ),
        )
        reasons.extend(name for name, passed in checks if not passed)
        return reasons


class RecordingRuntimeAdapter:
    """In-memory recorder around an injected adapter implementation."""

    def __init__(self, delegate: RuntimeAdapter) -> None:
        self._delegate = delegate
        self._records: list[RuntimeCallRecord] = []

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        return RuntimeAdapterIdentity.model_validate(
            self._delegate.identity.model_dump(mode="json")
        )

    @property
    def records(self) -> tuple[RuntimeCallRecord, ...]:
        return tuple(
            RuntimeCallRecord.model_validate(record.model_dump(mode="json"))
            for record in self._records
        )

    def execute(self, request: RuntimeExecutionRequest) -> RuntimeAdapterResult:
        task, team, manifest, split = _isolate_request(request)
        isolated_request = RuntimeExecutionRequest(
            task=task,
            team=team,
            experiment_manifest=manifest,
            task_split_manifest=split,
        )
        result = RuntimeAdapterResult.model_validate(
            self._delegate.execute(isolated_request).model_dump(mode="json")
        )
        self._records.append(
            RuntimeCallRecord(
                call_index=len(self._records),
                request_hash=result.request_hash,
                result=result,
            )
        )
        return RuntimeAdapterResult.model_validate(result.model_dump(mode="json"))


def _isolate_request(
    request: RuntimeExecutionRequest,
) -> tuple[TaskSpec, CanonicalTeamConfig, ExperimentManifest, TaskSplitManifest]:
    task = TaskSpec.model_validate(
        isolated_json_copy(request.task.model_dump(mode="json"))
    )
    team = CanonicalTeamConfig.model_validate(
        isolated_json_copy(request.team.model_dump(mode="json"))
    )
    manifest = ExperimentManifest.model_validate(
        isolated_json_copy(request.experiment_manifest.model_dump(mode="json"))
    )
    split = TaskSplitManifest.model_validate(
        isolated_json_copy(request.task_split_manifest.model_dump(mode="json"))
    )
    return task, team, manifest, split


def _request_hash(
    task: TaskSpec,
    team: CanonicalTeamConfig,
    manifest: ExperimentManifest,
    split: TaskSplitManifest,
) -> str:
    return canonical_json_hash(
        {
            "task": task.model_dump(mode="json"),
            "team": team.model_dump(mode="json"),
            "experiment_manifest": manifest.model_dump(mode="json"),
            "task_split_manifest": split.model_dump(mode="json"),
        }
    )


def _validate_execution(
    execution: ExecutionRecord,
    task: TaskSpec,
    team: CanonicalTeamConfig,
    manifest: ExperimentManifest,
) -> None:
    expected = {
        "experiment_id": manifest.experiment_id,
        "task_id": task.task_id,
        "team_id": team.team_id,
        "team_version": team.team_version,
        "protocol_id": team.execution_protocol.protocol_id,
        "removal_protocol_id": team.removal_protocol.removal_protocol_id,
    }
    if any(getattr(execution, name) != value for name, value in expected.items()):
        raise ValueError("runtime execution identity does not match its request")
    expected_seeds = SeedBundle(
        experiment_seed=manifest.seed,
        task_seed=derive_seed(manifest.seed, "task", task.task_id),
        role_seeds={
            role.role_id: derive_seed(manifest.seed, "role", role.role_id)
            for role in team.roles
        },
        aggregation_seed=derive_seed(manifest.seed, "aggregation", team.team_id),
    )
    if execution.seeds != expected_seeds:
        raise ValueError("runtime execution seed hierarchy does not match its manifest")
    if not execution.mock:
        raise ValueError("offline runtime returned non-mock evidence")
    if set(execution.role_outputs) != set(execution.role_output_hashes):
        raise ValueError("runtime output identifiers and hashes do not match")
    if any(
        canonical_json_hash(output) != execution.role_output_hashes[role_id]
        for role_id, output in execution.role_outputs.items()
    ):
        raise ValueError("runtime output hash does not match recorded output")
    if execution.status is ExecutionStatus.SUCCEEDED:
        expected_role_ids = {
            role_id for role_id in team.execution_protocol.execution_order
        }
        if set(execution.role_outputs) != expected_role_ids:
            raise ValueError("successful runtime execution must contain every role output")
        if execution.final_output is None:
            raise ValueError("successful runtime execution requires a final output")


def _failed_execution(
    task: TaskSpec,
    team: CanonicalTeamConfig,
    manifest: ExperimentManifest,
    error: Exception,
) -> ExecutionRecord:
    timestamp = datetime.now(UTC)
    return ExecutionRecord(
        run_id=(
            "mock-failed-"
            + canonical_json_hash(
                {
                    "experiment_id": manifest.experiment_id,
                    "task_id": task.task_id,
                    "team_id": team.team_id,
                    "seed": manifest.seed,
                    "error_type": type(error).__name__,
                }
            ).removeprefix("sha256:")[:16]
        ),
        experiment_id=manifest.experiment_id,
        task_id=task.task_id,
        team_id=team.team_id,
        team_version=team.team_version,
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        started_at=timestamp,
        finished_at=timestamp,
        status=ExecutionStatus.FAILED,
        seeds=SeedBundle(
            experiment_seed=manifest.seed,
            task_seed=derive_seed(manifest.seed, "task", task.task_id),
            role_seeds={
                role.role_id: derive_seed(manifest.seed, "role", role.role_id)
                for role in team.roles
            },
            aggregation_seed=derive_seed(
                manifest.seed, "aggregation", team.team_id
            ),
        ),
        mock=True,
        errors=[f"fake_runtime_error:{type(error).__name__}"],
    )
