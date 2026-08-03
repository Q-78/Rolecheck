from __future__ import annotations

import socket
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch

from rolecheck.benchmark import (
    SyntheticBenchmarkAdapter,
    create_task_split_manifest,
)
from rolecheck.config import MockRuntimeConfig
from rolecheck.hashing import canonical_json_hash, role_contract_hash
from rolecheck.manifest import ExperimentManifest, create_manifest
from rolecheck.runtime import (
    FakeRuntimeAdapter,
    RecordingRuntimeAdapter,
    RuntimeAdapter,
    RuntimeAdapterResult,
    RuntimeExecutionRequest,
)
from rolecheck.runtime.interfaces import AggregationRequest
from rolecheck.schemas import (
    AggregatorIdentity,
    CanonicalTeamConfig,
    ExecutionRecord,
    ExecutionStatus,
    RoleExecutionMetrics,
    RuntimeAdapterIdentity,
    SeedBundle,
    TaskSpec,
)


class FailingAggregator:
    @property
    def identity(self) -> AggregatorIdentity:
        return AggregatorIdentity(
            aggregator_id="fixed-mock-aggregation",
            aggregator_version="v1",
            config_hash=canonical_json_hash(
                {"implementation": "fixed-order-mock", "version": 1}
            ),
        )

    @property
    def accepts_variable_responses(self) -> bool:
        return True

    def aggregate(self, request: AggregationRequest) -> object:
        raise RuntimeError("synthetic aggregator failure")


def _split(task: TaskSpec) -> object:
    benchmark = SyntheticBenchmarkAdapter(
        dataset_id="synthetic-stage-3",
        dataset_revision="fixture-v1",
    )
    return create_task_split_manifest(
        [task.task_id, "task-2", "task-3"],
        dataset_id=benchmark.dataset_id,
        dataset_revision=benchmark.dataset_revision,
        adapter=benchmark.identity,
        seed=23,
    )


def _manifest(
    team: CanonicalTeamConfig,
    adapter: FakeRuntimeAdapter,
    split: object,
    *,
    protocol_id: str | None = None,
) -> ExperimentManifest:
    from rolecheck.benchmark import TaskSplitManifest

    validated_split = cast(TaskSplitManifest, split)
    aggregator = adapter._runtime.aggregator_identity
    return create_manifest(
        experiment_id="stage-3-offline",
        git_commit="deadbeef",
        dataset_revision=validated_split.dataset_revision,
        task_split_hash=validated_split.split_hash,
        initializer_id=team.source_initializer,
        team_config_hash=canonical_json_hash(team.model_dump(mode="json")),
        runtime_id=adapter.identity.runtime_id,
        runtime_version=adapter.identity.runtime_version,
        runtime_config_hash=adapter.identity.config_hash,
        protocol_id=protocol_id or team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        seed=31,
        config_hash=canonical_json_hash({"stage": 3, "offline": True}),
        model_versions={agent.agent_id: agent.model_id for agent in team.agents},
        tool_hashes={
            tool_id: canonical_json_hash({"tool_id": tool_id})
            for agent in team.agents
            for tool_id in agent.tool_ids
        },
        prompt_hashes={role.role_id: role.prompt_hash for role in team.roles},
        role_contract_hashes={
            role.role_id: role_contract_hash(role.model_dump(mode="json"))
            for role in team.roles
        },
        aggregator_id=aggregator.aggregator_id,
        aggregator_version=aggregator.aggregator_version,
        aggregator_config_hash=aggregator.config_hash,
        mock=True,
    )


def _request(
    team: CanonicalTeamConfig,
    adapter: FakeRuntimeAdapter,
    *,
    protocol_id: str | None = None,
) -> RuntimeExecutionRequest:
    from rolecheck.benchmark import TaskSplitManifest

    task = TaskSpec(task_id="task-1", task_text="Return a synthetic artifact.")
    split = cast(TaskSplitManifest, _split(task))
    return RuntimeExecutionRequest(
        task=task,
        team=team,
        experiment_manifest=_manifest(
            team, adapter, split, protocol_id=protocol_id
        ),
        task_split_manifest=split,
    )


def test_fake_runtime_adapter_executes_offline_and_preserves_inputs(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    adapter = FakeRuntimeAdapter(MockRuntimeConfig())
    request = _request(team, adapter)
    before = {
        "task": request.task.model_dump(mode="json"),
        "team": request.team.model_dump(mode="json"),
        "manifest": request.experiment_manifest.model_dump(mode="json"),
        "split": request.task_split_manifest.model_dump(mode="json"),
    }

    first = adapter.execute(request)
    second = adapter.execute(request)

    assert first.accepted is True
    assert first.execution is not None
    assert first.execution.status is ExecutionStatus.SUCCEEDED
    assert first.execution.mock is True
    assert first.synthetic is True
    assert first.non_empirical is True
    assert first.request_hash == second.request_hash
    assert first.execution.run_id == second.execution.run_id  # type: ignore[union-attr]
    assert request.task.model_dump(mode="json") == before["task"]
    assert request.team.model_dump(mode="json") == before["team"]
    assert request.experiment_manifest.model_dump(mode="json") == before["manifest"]
    assert request.task_split_manifest.model_dump(mode="json") == before["split"]


def test_manifest_mismatch_is_rejected_before_runtime_execution(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    adapter = FakeRuntimeAdapter(MockRuntimeConfig())
    request = _request(team_factory(), adapter, protocol_id="wrong-protocol")

    with patch.object(adapter._runtime, "run", side_effect=AssertionError("must not run")):
        result = adapter.execute(request)

    assert result.accepted is False
    assert result.execution is None
    assert result.rejection_reasons == ["protocol_id_mismatch"]


def test_task_must_belong_to_recorded_split(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    adapter = FakeRuntimeAdapter(MockRuntimeConfig())
    request = _request(team_factory(), adapter)
    changed = RuntimeExecutionRequest(
        task=request.task.model_copy(update={"task_id": "not-in-split"}),
        team=request.team,
        experiment_manifest=request.experiment_manifest,
        task_split_manifest=request.task_split_manifest,
    )

    result = adapter.execute(changed)

    assert result.accepted is False
    assert "task_not_in_split" in result.rejection_reasons


def test_fake_adapter_has_no_network_or_subprocess_execution_path(
    team_factory: Callable[[], CanonicalTeamConfig],
    monkeypatch: object,
) -> None:
    from pytest import MonkeyPatch

    typed_monkeypatch = cast(MonkeyPatch, monkeypatch)
    typed_monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("network access attempted")
        ),
    )
    typed_monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("subprocess access attempted")
        ),
    )
    adapter = FakeRuntimeAdapter(MockRuntimeConfig())

    result = adapter.execute(_request(team_factory(), adapter))

    assert result.accepted is True
    assert result.execution is not None
    assert result.execution.status is ExecutionStatus.SUCCEEDED


def test_runtime_failure_is_preserved_as_mock_failure_evidence(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    adapter = FakeRuntimeAdapter(
        MockRuntimeConfig(),
        aggregator=FailingAggregator(),
    )

    result = adapter.execute(_request(team_factory(), adapter))

    assert result.accepted is True
    assert result.execution is not None
    assert result.execution.status is ExecutionStatus.FAILED
    assert result.execution.mock is True
    assert result.execution.errors == ["mock_aggregation_error:RuntimeError"]
    assert set(result.execution.role_outputs) == {"solver", "critic"}
    assert set(result.execution.role_output_hashes) == {"solver", "critic"}


class PartialFailureAdapter:
    def __init__(self) -> None:
        self._identity = RuntimeAdapterIdentity(
            runtime_id="partial-fake",
            runtime_version="v0.1",
            config_hash=canonical_json_hash({"partial": True}),
        )

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        return self._identity

    def execute(self, request: RuntimeExecutionRequest) -> RuntimeAdapterResult:
        request.task.task_text = "mutated only inside the isolated delegate request"
        output = {"mock": True, "role_id": "solver", "partial": True}
        timestamp = datetime.now(UTC)
        execution = ExecutionRecord(
            run_id="partial-failure",
            experiment_id=request.experiment_manifest.experiment_id,
            task_id=request.task.task_id,
            team_id=request.team.team_id,
            team_version=request.team.team_version,
            protocol_id=request.team.execution_protocol.protocol_id,
            removal_protocol_id=request.team.removal_protocol.removal_protocol_id,
            started_at=timestamp,
            finished_at=timestamp,
            status=ExecutionStatus.FAILED,
            seeds=SeedBundle(
                experiment_seed=request.experiment_manifest.seed,
                task_seed=1,
                role_seeds={"solver": 2},
                aggregation_seed=3,
            ),
            role_outputs={"solver": output},
            role_output_hashes={"solver": canonical_json_hash(output)},
            role_metrics={"solver": RoleExecutionMetrics()},
            mock=True,
            errors=["synthetic_partial_failure"],
        )
        return RuntimeAdapterResult(
            adapter=self.identity,
            request_hash=canonical_json_hash({"partial_request": True}),
            manifest_hash=canonical_json_hash(
                request.experiment_manifest.model_dump(mode="json")
            ),
            accepted=True,
            execution=execution,
        )


def test_recording_adapter_preserves_partial_failure_evidence(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    fake = FakeRuntimeAdapter(MockRuntimeConfig())
    request = _request(team_factory(), fake)
    delegate: RuntimeAdapter = PartialFailureAdapter()
    recorder = RecordingRuntimeAdapter(delegate)

    result = recorder.execute(request)

    assert result.execution is not None
    assert result.execution.status is ExecutionStatus.FAILED
    assert set(result.execution.role_outputs) == {"solver"}
    assert recorder.records[0].result == result
    assert recorder.records[0].request_hash == result.request_hash
    assert request.task.task_text == "Return a synthetic artifact."


def test_runtime_identity_and_manifest_are_frozen_and_backward_compatible(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    adapter = FakeRuntimeAdapter(MockRuntimeConfig())
    request = _request(team, adapter)

    assert request.experiment_manifest.runtime_version == "v0.1"
    assert request.experiment_manifest.runtime_config_hash == adapter.identity.config_hash
    legacy = create_manifest(
        experiment_id="legacy",
        git_commit="abc",
        dataset_revision="none",
        task_split_hash="none",
        initializer_id="manual",
        runtime_id="mock-runtime-v1",
        protocol_id="parallel-v1",
        removal_protocol_id="parallel-removal-v1",
        seed=1,
        config_hash=canonical_json_hash({"legacy": True}),
        mock=True,
    )
    assert legacy.runtime_version is None
    assert legacy.runtime_config_hash is None
    assert legacy.team_config_hash is None
