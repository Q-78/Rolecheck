"""Manifest-gated synthetic and self-hosted Runtime Adapter boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from pydantic import ConfigDict, Field, model_validator

from rolecheck.benchmark import TaskSplitManifest
from rolecheck.config import MockRuntimeConfig
from rolecheck.hashing import canonical_json_hash, derive_seed, role_contract_hash
from rolecheck.manifest import ExperimentManifest
from rolecheck.runtime.interfaces import Aggregator, isolated_json_copy
from rolecheck.runtime.mock import MockRuntime
from rolecheck.schemas import (
    AggregatorIdentity,
    CanonicalTeamConfig,
    EvidenceBoundModel,
    EvidenceClass,
    ExecutionRecord,
    ExecutionStatus,
    RuntimeAdapterIdentity,
    RuntimeEnvironmentIdentity,
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


class RuntimeAdapterResult(EvidenceBoundModel):
    """Preflight rejection or existing execution evidence from an adapter."""

    adapter: RuntimeAdapterIdentity
    request_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    accepted: bool
    execution: ExecutionRecord | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
    @model_validator(mode="after")
    def validate_outcome(self) -> RuntimeAdapterResult:
        if self.accepted:
            if self.execution is None:
                raise ValueError("accepted runtime request requires execution evidence")
            if self.rejection_reasons:
                raise ValueError("accepted runtime request cannot contain rejection reasons")
            expected_mock = (
                self.evidence_class is EvidenceClass.SYNTHETIC_NON_EMPIRICAL
            )
            if self.execution.mock is not expected_mock:
                raise ValueError(
                    "execution mock flag must match its evidence classification"
                )
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


class SelfHostedExecutionBackend(Protocol):
    """Injected implementation that performs one real self-hosted execution."""

    @property
    def identity(self) -> RuntimeAdapterIdentity: ...

    def execute(self, request: RuntimeExecutionRequest) -> ExecutionRecord: ...


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
        manifest_hash = canonical_json_hash(_manifest_hash_payload(manifest))
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
            _validate_execution(
                execution,
                task,
                team,
                manifest,
                expected_mock=True,
            )
        except Exception as exc:
            execution = _failed_execution(
                task,
                team,
                manifest,
                exc,
                mock=True,
            )
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
        return _manifest_preflight(
            task=task,
            team=team,
            manifest=manifest,
            split=split,
            runtime_identity=self.identity,
            aggregator=self._runtime.aggregator_identity,
            expected_evidence_class=EvidenceClass.SYNTHETIC_NON_EMPIRICAL,
            expected_mock=True,
            runtime_environment=None,
        )


class SelfHostedRuntimeAdapter:
    """Manifest-gated empirical boundary around an injected model backend."""

    def __init__(
        self,
        *,
        backend: SelfHostedExecutionBackend,
        environment: RuntimeEnvironmentIdentity,
        aggregator: AggregatorIdentity,
        runtime_id: str = "rolecheck.self_hosted",
        runtime_version: str = "v0.1",
    ) -> None:
        self._backend = backend
        self._backend_identity = RuntimeAdapterIdentity.model_validate(
            backend.identity.model_dump(mode="json")
        )
        self._environment = environment
        self._aggregator = aggregator
        self._identity = RuntimeAdapterIdentity(
            runtime_id=runtime_id,
            runtime_version=runtime_version,
            config_hash=canonical_json_hash(
                {
                    "runtime_id": runtime_id,
                    "runtime_version": runtime_version,
                    "environment": environment.model_dump(mode="json"),
                    "aggregator": aggregator.model_dump(mode="json"),
                    "backend": self._backend_identity.model_dump(mode="json"),
                }
            ),
        )

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        return self._identity.model_copy(deep=True)

    @property
    def environment(self) -> RuntimeEnvironmentIdentity:
        return self._environment.model_copy(deep=True)

    @property
    def backend_identity(self) -> RuntimeAdapterIdentity:
        return self._backend_identity.model_copy(deep=True)

    def execute(self, request: RuntimeExecutionRequest) -> RuntimeAdapterResult:
        task, team, manifest, split = _isolate_request(request)
        request_hash = _request_hash(task, team, manifest, split)
        manifest_hash = canonical_json_hash(_manifest_hash_payload(manifest))
        rejection_reasons = _manifest_preflight(
            task=task,
            team=team,
            manifest=manifest,
            split=split,
            runtime_identity=self.identity,
            aggregator=self._aggregator,
            expected_evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
            expected_mock=False,
            runtime_environment=self.environment,
        )
        current_backend_identity = RuntimeAdapterIdentity.model_validate(
            self._backend.identity.model_dump(mode="json")
        )
        if current_backend_identity != self._backend_identity:
            rejection_reasons.append("backend_identity_mismatch")
        if rejection_reasons:
            return RuntimeAdapterResult(
                evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
                adapter=self.identity,
                request_hash=request_hash,
                manifest_hash=manifest_hash,
                accepted=False,
                rejection_reasons=rejection_reasons,
            )

        isolated_request = RuntimeExecutionRequest(
            task=task,
            team=team,
            experiment_manifest=manifest,
            task_split_manifest=split,
        )
        try:
            execution = self._backend.execute(isolated_request)
            _validate_execution(
                execution,
                task,
                team,
                manifest,
                expected_mock=False,
            )
        except Exception as exc:
            execution = _failed_execution(
                task,
                team,
                manifest,
                exc,
                mock=False,
            )
        return RuntimeAdapterResult(
            evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
            adapter=self.identity,
            request_hash=request_hash,
            manifest_hash=manifest_hash,
            accepted=True,
            execution=execution,
        )


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
            "experiment_manifest": _manifest_hash_payload(manifest),
            "task_split_manifest": _split_hash_payload(split),
        }
    )


def _manifest_hash_payload(manifest: ExperimentManifest) -> dict[str, object]:
    payload = manifest.model_dump(mode="json")
    if manifest.runtime_environment is None:
        payload.pop("runtime_environment")
    return payload


def _split_hash_payload(split: TaskSplitManifest) -> dict[str, object]:
    payload = split.model_dump(mode="json")
    if split.evidence_class is EvidenceClass.SYNTHETIC_NON_EMPIRICAL:
        payload.pop("evidence_class")
    return payload


def _manifest_preflight(
    *,
    task: TaskSpec,
    team: CanonicalTeamConfig,
    manifest: ExperimentManifest,
    split: TaskSplitManifest,
    runtime_identity: RuntimeAdapterIdentity,
    aggregator: AggregatorIdentity,
    expected_evidence_class: EvidenceClass,
    expected_mock: bool,
    runtime_environment: RuntimeEnvironmentIdentity | None,
) -> list[str]:
    expected_models = {agent.agent_id: agent.model_id for agent in team.agents}
    expected_tools = {tool_id for agent in team.agents for tool_id in agent.tool_ids}
    expected_prompts = {role.role_id: role.prompt_hash for role in team.roles}
    expected_contracts = {
        role.role_id: role_contract_hash(role.model_dump(mode="json"))
        for role in team.roles
    }
    expected_environment_model = (
        None
        if runtime_environment is None
        else runtime_environment.model_assignment_id
    )
    checks = (
        ("manifest_mock_mismatch", manifest.mock is expected_mock),
        ("evidence_class_mismatch", split.evidence_class is expected_evidence_class),
        (
            "runtime_environment_mismatch",
            manifest.runtime_environment == runtime_environment,
        ),
        (
            "environment_model_assignments_mismatch",
            expected_environment_model is None
            or set(expected_models.values()) == {expected_environment_model},
        ),
        ("runtime_id_mismatch", manifest.runtime_id == runtime_identity.runtime_id),
        (
            "runtime_version_mismatch",
            manifest.runtime_version == runtime_identity.runtime_version,
        ),
        (
            "runtime_config_hash_mismatch",
            manifest.runtime_config_hash == runtime_identity.config_hash,
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
        ("model_versions_mismatch", dict(manifest.model_versions) == expected_models),
        ("tool_id_set_mismatch", set(manifest.tool_hashes) == expected_tools),
        ("prompt_hashes_mismatch", dict(manifest.prompt_hashes) == expected_prompts),
        (
            "role_contract_hashes_mismatch",
            dict(manifest.role_contract_hashes) == expected_contracts,
        ),
        ("aggregator_id_mismatch", manifest.aggregator_id == aggregator.aggregator_id),
        (
            "aggregator_version_mismatch",
            manifest.aggregator_version == aggregator.aggregator_version,
        ),
        (
            "aggregator_config_hash_mismatch",
            manifest.aggregator_config_hash == aggregator.config_hash,
        ),
        ("dataset_revision_mismatch", manifest.dataset_revision == split.dataset_revision),
        ("task_split_hash_mismatch", manifest.task_split_hash == split.split_hash),
        (
            "task_not_in_split",
            any(task.task_id in partition.task_ids for partition in split.partitions),
        ),
    )
    return [name for name, passed in checks if not passed]


def _validate_execution(
    execution: ExecutionRecord,
    task: TaskSpec,
    team: CanonicalTeamConfig,
    manifest: ExperimentManifest,
    *,
    expected_mock: bool,
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
    if execution.mock is not expected_mock:
        raise ValueError("runtime execution mock flag does not match adapter mode")
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
    *,
    mock: bool,
) -> ExecutionRecord:
    timestamp = datetime.now(UTC)
    return ExecutionRecord(
        run_id=(
            ("mock-failed-" if mock else "self-hosted-failed-")
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
        mock=mock,
        errors=[
            (
                "fake_runtime_error:"
                if mock
                else "self_hosted_runtime_error:"
            )
            + type(error).__name__
        ],
    )
