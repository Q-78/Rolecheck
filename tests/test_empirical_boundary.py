from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from rolecheck.benchmark import (
    MMLU_PRO_REVISION,
    EvidenceClass,
    MMLUProBenchmarkAdapter,
    MMLUProEvaluationRecord,
    MMLUProTaskRecord,
    OfflineTaskRecord,
    create_task_split_manifest,
)
from rolecheck.config import MockRuntimeConfig
from rolecheck.hashing import canonical_json_hash, derive_seed, role_contract_hash
from rolecheck.manifest import create_manifest
from rolecheck.runtime import (
    FakeRuntimeAdapter,
    RuntimeAdapterResult,
    RuntimeExecutionRequest,
    SelfHostedExecutionBackend,
    SelfHostedRuntimeAdapter,
)
from rolecheck.runtime.mock_aggregator import MockAggregator
from rolecheck.schemas import (
    AgentInstance,
    CanonicalTeamConfig,
    ExecutionRecord,
    ExecutionStatus,
    RuntimeAdapterIdentity,
    RuntimeEnvironmentIdentity,
    SeedBundle,
    TaskSpec,
)

MODEL_ID = "Qwen/Qwen3-8B"
MODEL_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
MODEL_ASSIGNMENT = f"{MODEL_ID}@{MODEL_REVISION}"


def _digest(label: str) -> str:
    return canonical_json_hash({"fixture": label})


def _environment() -> RuntimeEnvironmentIdentity:
    return RuntimeEnvironmentIdentity(
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        model_assignment_id=MODEL_ASSIGNMENT,
        model_artifact_manifest_hash=_digest("model-artifacts"),
        tokenizer_hash=_digest("tokenizer"),
        generation_config_hash=_digest("generation"),
        dependency_lock_hash=_digest("dependencies"),
        hardware_inventory_hash=_digest("hardware"),
    )


def _record() -> MMLUProTaskRecord:
    return MMLUProTaskRecord(
        source_record_id="test-math-0001",
        question="Which option is equal to two plus two?",
        options=("1", "2", "3", "4"),
        category="math",
    )


def _empirical_team(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> CanonicalTeamConfig:
    team = team_factory()
    agents = [
        AgentInstance.model_validate(
            {
                **agent.model_dump(mode="python"),
                "model_id": MODEL_ASSIGNMENT,
            }
        )
        for agent in team.agents
    ]
    return CanonicalTeamConfig.model_validate(
        {
            **team.model_dump(mode="python"),
            "agents": agents,
        }
    )


class ContractTestBackend:
    """In-memory contract fixture; it does not call a model or persist evidence."""

    def __init__(self, *, return_mock: bool = False) -> None:
        self.call_count = 0
        self.return_mock = return_mock

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        return RuntimeAdapterIdentity(
            runtime_id="rolecheck.contract_test_backend",
            runtime_version="v0.1",
            config_hash=_digest(
                f"contract-test-backend-mock-{self.return_mock}"
            ),
        )

    def execute(self, request: RuntimeExecutionRequest) -> ExecutionRecord:
        self.call_count += 1
        request.task.task_text = "mutated inside isolated backend request"
        outputs = {
            role_id: {"fixture_only": True, "answer": "D"}
            for role_id in request.team.execution_protocol.execution_order
        }
        timestamp = datetime.now(UTC)
        return ExecutionRecord(
            run_id="contract-test-execution",
            experiment_id=request.experiment_manifest.experiment_id,
            task_id=request.task.task_id,
            team_id=request.team.team_id,
            team_version=request.team.team_version,
            protocol_id=request.team.execution_protocol.protocol_id,
            removal_protocol_id=(
                request.team.removal_protocol.removal_protocol_id
            ),
            started_at=timestamp,
            finished_at=timestamp,
            status=ExecutionStatus.SUCCEEDED,
            seeds=SeedBundle(
                experiment_seed=request.experiment_manifest.seed,
                task_seed=derive_seed(
                    request.experiment_manifest.seed,
                    "task",
                    request.task.task_id,
                ),
                role_seeds={
                    role.role_id: derive_seed(
                        request.experiment_manifest.seed,
                        "role",
                        role.role_id,
                    )
                    for role in request.team.roles
                },
                aggregation_seed=derive_seed(
                    request.experiment_manifest.seed,
                    "aggregation",
                    request.team.team_id,
                ),
            ),
            role_outputs=outputs,
            role_output_hashes={
                role_id: canonical_json_hash(output)
                for role_id, output in outputs.items()
            },
            final_output={"fixture_only": True, "answer": "D"},
            mock=self.return_mock,
        )


def _request(
    team_factory: Callable[[], CanonicalTeamConfig],
    backend: SelfHostedExecutionBackend,
) -> tuple[SelfHostedRuntimeAdapter, RuntimeExecutionRequest]:
    benchmark = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    conversion = benchmark.convert(_record())
    assert conversion.task is not None
    task = conversion.task
    split = create_task_split_manifest(
        [task.task_id, "mmlu-pro-fixture-2", "mmlu-pro-fixture-3"],
        dataset_id=benchmark.dataset_id,
        dataset_revision=benchmark.dataset_revision,
        adapter=benchmark.identity,
        seed=2026080301,
        evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
    )
    team = _empirical_team(team_factory)
    aggregator = MockAggregator().identity
    runtime = SelfHostedRuntimeAdapter(
        backend=backend,
        environment=_environment(),
        aggregator=aggregator,
    )
    manifest = create_manifest(
        experiment_id="gate-1-contract-test",
        git_commit="fixture-only",
        dataset_revision=split.dataset_revision,
        task_split_hash=split.split_hash,
        initializer_id=team.source_initializer,
        team_config_hash=canonical_json_hash(team.model_dump(mode="json")),
        runtime_id=runtime.identity.runtime_id,
        runtime_version=runtime.identity.runtime_version,
        runtime_config_hash=runtime.identity.config_hash,
        runtime_environment=runtime.environment,
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        seed=2026080302,
        config_hash=_digest("experiment"),
        model_versions={
            agent.agent_id: agent.model_id for agent in team.agents
        },
        tool_hashes={
            tool_id: _digest(tool_id)
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
        mock=False,
    )
    return runtime, RuntimeExecutionRequest(
        task=task,
        team=team,
        experiment_manifest=manifest,
        task_split_manifest=split,
    )


def test_legacy_synthetic_evidence_defaults_remain_compatible() -> None:
    record = OfflineTaskRecord(
        source_record_id="legacy-fixture",
        task_text="Synthetic task.",
    )

    assert record.evidence_class is EvidenceClass.SYNTHETIC_NON_EMPIRICAL
    assert record.synthetic is True
    assert record.non_empirical is True


def test_evidence_class_rejects_inconsistent_legacy_flags() -> None:
    with pytest.raises(ValidationError, match="must match evidence_class"):
        OfflineTaskRecord(
            source_record_id="bad-flags",
            task_text="Synthetic task.",
            evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
            synthetic=True,
            non_empirical=True,
        )
    with pytest.raises(ValidationError):
        OfflineTaskRecord(
            source_record_id="coerced-flags",
            task_text="Synthetic task.",
            synthetic="true",
        )


def test_task_spec_recursively_rejects_explicit_leakage_keys_only() -> None:
    with pytest.raises(ValidationError, match=r"public_metadata\.nested\[0\]\.Gold-Answer"):
        TaskSpec(
            task_id="leaking-task",
            task_text="Question without embedded evaluation data.",
            public_metadata={
                "nested": [{"Gold-Answer": "D"}],
            },
        )

    allowed = TaskSpec(
        task_id="allowed-task",
        task_text="The word answer may legitimately occur in a question.",
        public_metadata={"answer_format": "single uppercase letter"},
    )
    assert allowed.public_metadata["answer_format"] == "single uppercase letter"


def test_mmlu_adapter_requires_pin_and_excludes_evaluation_fields() -> None:
    with pytest.raises(ValueError, match="approved pinned revision"):
        MMLUProBenchmarkAdapter(dataset_revision="main")
    with pytest.raises(ValidationError):
        MMLUProTaskRecord(
            source_record_id="leaking",
            question="Question",
            options=("A", "B"),
            category="other",
            answer="A",
        )

    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    result = adapter.convert(_record())

    assert result.evidence_class is EvidenceClass.EMPIRICAL_UNEVALUATED
    assert result.synthetic is False
    assert result.non_empirical is False
    assert result.task is not None
    task_payload = result.task.model_dump(mode="json")
    assert task_payload["public_metadata"]["options"] == ["1", "2", "3", "4"]
    assert "answer" not in task_payload
    assert "gold" not in task_payload
    assert "chain_of_thought" not in task_payload


def test_evaluation_record_is_pinned_and_not_a_pre_execution_record() -> None:
    evaluation = MMLUProEvaluationRecord(
        task_id="mmlu-pro-task",
        answer_index=3,
        answer_letter="D",
        gold_answer="4",
        reference_chain_of_thought="Evaluation-only rationale.",
    )

    assert evaluation.dataset_revision == MMLU_PRO_REVISION
    with pytest.raises(ValidationError):
        MMLUProTaskRecord.model_validate(evaluation.model_dump(mode="python"))


def test_mmlu_conversion_is_deterministic_and_content_addressed() -> None:
    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    record = _record()
    before = record.model_dump(mode="json")

    first = adapter.convert(record)
    second = adapter.convert(record)
    changed = adapter.convert(
        record.model_copy(update={"question": "A changed question."})
    )

    assert first.model_dump_json() == second.model_dump_json()
    assert record.model_dump(mode="json") == before
    assert first.task is not None and changed.task is not None
    assert first.task.task_id != changed.task.task_id


def test_empirical_split_hash_covers_evidence_class() -> None:
    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    task_ids = ["task-a", "task-b", "task-c"]

    synthetic = create_task_split_manifest(
        task_ids,
        dataset_id=adapter.dataset_id,
        dataset_revision=adapter.dataset_revision,
        adapter=adapter.identity,
        seed=7,
    )
    empirical = create_task_split_manifest(
        task_ids,
        dataset_id=adapter.dataset_id,
        dataset_revision=adapter.dataset_revision,
        adapter=adapter.identity,
        seed=7,
        evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
    )

    assert empirical.synthetic is False
    assert empirical.non_empirical is False
    assert empirical.split_hash != synthetic.split_hash


def test_legacy_synthetic_split_payload_still_validates() -> None:
    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    split = create_task_split_manifest(
        ["task-a", "task-b", "task-c"],
        dataset_id=adapter.dataset_id,
        dataset_revision=adapter.dataset_revision,
        adapter=adapter.identity,
        seed=7,
    )
    legacy_payload = split.model_dump(mode="python")
    legacy_payload.pop("evidence_class")

    restored = type(split).model_validate(legacy_payload)

    assert restored.split_hash == split.split_hash
    assert restored.evidence_class is EvidenceClass.SYNTHETIC_NON_EMPIRICAL


def test_self_hosted_runtime_preserves_inputs_and_marks_unevaluated(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    backend = ContractTestBackend()
    runtime, request = _request(team_factory, backend)
    before = {
        "task": request.task.model_dump(mode="json"),
        "team": request.team.model_dump(mode="json"),
        "manifest": request.experiment_manifest.model_dump(mode="json"),
        "split": request.task_split_manifest.model_dump(mode="json"),
    }

    result = runtime.execute(request)

    assert result.accepted is True
    assert result.evidence_class is EvidenceClass.EMPIRICAL_UNEVALUATED
    assert result.synthetic is False
    assert result.non_empirical is False
    assert result.execution is not None
    assert result.execution.mock is False
    assert result.execution.status is ExecutionStatus.SUCCEEDED
    assert runtime.backend_identity == backend.identity
    assert backend.call_count == 1
    assert request.task.model_dump(mode="json") == before["task"]
    assert request.team.model_dump(mode="json") == before["team"]
    assert request.experiment_manifest.model_dump(mode="json") == before["manifest"]
    assert request.task_split_manifest.model_dump(mode="json") == before["split"]


def test_backend_identity_changes_runtime_config_hash() -> None:
    aggregator = MockAggregator().identity
    first = SelfHostedRuntimeAdapter(
        backend=ContractTestBackend(return_mock=False),
        environment=_environment(),
        aggregator=aggregator,
    )
    second = SelfHostedRuntimeAdapter(
        backend=ContractTestBackend(return_mock=True),
        environment=_environment(),
        aggregator=aggregator,
    )

    assert first.backend_identity != second.backend_identity
    assert first.identity.config_hash != second.identity.config_hash


def test_backend_identity_mutation_rejects_before_execution(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    backend = ContractTestBackend(return_mock=False)
    runtime, request = _request(team_factory, backend)
    backend.return_mock = True

    result = runtime.execute(request)

    assert result.accepted is False
    assert "backend_identity_mismatch" in result.rejection_reasons
    assert backend.call_count == 0


def test_self_hosted_identity_mismatch_rejects_before_backend(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    backend = ContractTestBackend()
    runtime, request = _request(team_factory, backend)
    wrong_environment = request.experiment_manifest.runtime_environment.model_copy(
        update={"hardware_inventory_hash": _digest("wrong-hardware")}
    )
    changed_manifest = request.experiment_manifest.model_copy(
        update={"runtime_environment": wrong_environment}
    )
    changed_request = RuntimeExecutionRequest(
        task=request.task,
        team=request.team,
        experiment_manifest=changed_manifest,
        task_split_manifest=request.task_split_manifest,
    )

    result = runtime.execute(changed_request)

    assert result.accepted is False
    assert result.execution is None
    assert result.rejection_reasons == ["runtime_environment_mismatch"]
    assert backend.call_count == 0


def test_fake_runtime_rejects_empirical_split_before_execution(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    backend = ContractTestBackend()
    _, empirical_request = _request(team_factory, backend)
    fake = FakeRuntimeAdapter(MockRuntimeConfig())

    with patch.object(
        fake._runtime,
        "run",
        side_effect=AssertionError("must not execute"),
    ):
        result = fake.execute(empirical_request)

    assert result.accepted is False
    assert "evidence_class_mismatch" in result.rejection_reasons
    assert result.execution is None


def test_legacy_fake_runtime_hash_payload_omits_new_default_fields(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    from rolecheck.benchmark import SyntheticBenchmarkAdapter

    team = team_factory()
    task = MMLUProBenchmarkAdapter(
        dataset_revision=MMLU_PRO_REVISION
    ).convert(_record()).task
    assert task is not None
    benchmark = SyntheticBenchmarkAdapter(
        dataset_id="synthetic-stage-3",
        dataset_revision="fixture-v1",
    )
    split = create_task_split_manifest(
        [task.task_id, "fixture-2", "fixture-3"],
        dataset_id=benchmark.dataset_id,
        dataset_revision=benchmark.dataset_revision,
        adapter=benchmark.identity,
        seed=17,
    )
    fake = FakeRuntimeAdapter(MockRuntimeConfig())
    aggregator = fake._runtime.aggregator_identity
    manifest = create_manifest(
        experiment_id="legacy-hash",
        git_commit="fixture",
        dataset_revision=split.dataset_revision,
        task_split_hash=split.split_hash,
        initializer_id=team.source_initializer,
        team_config_hash=canonical_json_hash(team.model_dump(mode="json")),
        runtime_id=fake.identity.runtime_id,
        runtime_version=fake.identity.runtime_version,
        runtime_config_hash=fake.identity.config_hash,
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        seed=11,
        config_hash=_digest("legacy-hash"),
        model_versions={
            agent.agent_id: agent.model_id for agent in team.agents
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
    request = RuntimeExecutionRequest(
        task=task,
        team=team,
        experiment_manifest=manifest,
        task_split_manifest=split,
    )
    legacy_manifest = manifest.model_dump(mode="json")
    legacy_manifest.pop("runtime_environment")
    legacy_split = split.model_dump(mode="json")
    legacy_split.pop("evidence_class")

    result = fake.execute(request)

    assert result.manifest_hash == canonical_json_hash(legacy_manifest)
    assert result.request_hash == canonical_json_hash(
        {
            "task": task.model_dump(mode="json"),
            "team": team.model_dump(mode="json"),
            "experiment_manifest": legacy_manifest,
            "task_split_manifest": legacy_split,
        }
    )


def test_self_hosted_adapter_converts_invalid_backend_mode_to_failure_evidence(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    backend = ContractTestBackend(return_mock=True)
    runtime, request = _request(team_factory, backend)

    result = runtime.execute(request)

    assert result.accepted is True
    assert result.execution is not None
    assert result.execution.status is ExecutionStatus.FAILED
    assert result.execution.mock is False
    assert result.execution.errors == ["self_hosted_runtime_error:ValueError"]


def test_runtime_result_cannot_relabel_mock_output_as_empirical(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    backend = ContractTestBackend(return_mock=True)
    runtime, request = _request(team_factory, backend)
    invalid_execution = backend.execute(request)

    with pytest.raises(ValidationError, match="mock flag must match"):
        RuntimeAdapterResult(
            evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
            adapter=runtime.identity,
            request_hash=_digest("request"),
            manifest_hash=_digest("manifest"),
            accepted=True,
            execution=invalid_execution,
        )
