from __future__ import annotations

from collections.abc import Callable

from rolecheck.config import MockRuntimeConfig
from rolecheck.hashing import canonical_json_hash, role_contract_hash
from rolecheck.manifest import ExperimentManifest, create_manifest
from rolecheck.runtime import (
    AggregationRequest,
    MockAggregator,
    MockRuntime,
    ParallelRemovalRunner,
)
from rolecheck.schemas import (
    AggregatorIdentity,
    AuthorityLevel,
    CanonicalTeamConfig,
    CommunicationEdge,
    InterventionAction,
    ProtocolKind,
    TaskSpec,
)


class RecordingAggregator(MockAggregator):
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], int]] = []

    def aggregate(self, request: AggregationRequest) -> object:
        self.calls.append(
            (
                [response.role_id for response in request.responses],
                request.aggregation_seed,
            )
        )
        return super().aggregate(request)


class NonReplayableAggregator(RecordingAggregator):
    def aggregate(self, request: AggregationRequest) -> object:
        output = super().aggregate(request)
        assert isinstance(output, dict)
        output["call_number"] = len(self.calls)
        return output


class FixedArityAggregator(MockAggregator):
    @property
    def accepts_variable_responses(self) -> bool:
        return False


class UnexpectedFailureAggregator(MockAggregator):
    def aggregate(self, request: AggregationRequest) -> object:
        raise OSError("unexpected aggregation failure")


class MutatingAggregator(MockAggregator):
    def aggregate(self, request: AggregationRequest) -> object:
        output = request.responses[0].output
        assert isinstance(output, dict)
        output["message"] = "mutated by aggregator"
        request.task.public_metadata["mutated"] = True
        return super().aggregate(request)


class WrongIdentityAggregator(MockAggregator):
    @property
    def identity(self) -> AggregatorIdentity:
        return AggregatorIdentity(
            aggregator_id="different-aggregation",
            aggregator_version="v1",
            config_hash="sha256:" + "b" * 64,
        )


def _manifest(
    aggregator: MockAggregator,
    team: CanonicalTeamConfig,
) -> ExperimentManifest:
    return create_manifest(
        experiment_id="exp-1",
        git_commit="test",
        dataset_revision="not-applicable",
        task_split_hash="not-applicable",
        initializer_id="manual-test",
        runtime_id="mock-runtime-v1",
        protocol_id="parallel-v1",
        removal_protocol_id="parallel-removal-v1",
        seed=11,
        config_hash="sha256:" + "0" * 64,
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
        aggregator_id=aggregator.identity.aggregator_id,
        aggregator_version=aggregator.identity.aggregator_version,
        aggregator_config_hash=aggregator.identity.config_hash,
        mock=True,
    )


def _run(
    team: CanonicalTeamConfig,
    aggregator: MockAggregator,
) -> tuple[object, object]:
    task = TaskSpec(task_id="task-1", task_text="Return a test artifact.")
    baseline = MockRuntime(MockRuntimeConfig(), aggregator=aggregator).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )
    outcome = ParallelRemovalRunner().run(
        baseline=baseline,
        task=task,
        team=team,
        target_role_id="critic",
        output_team_version="v2",
        manifest=_manifest(aggregator, team),
        aggregator=aggregator,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
    )
    return baseline, outcome


def test_parallel_removal_reuses_responses_and_only_reaggregates(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    aggregator = RecordingAggregator()
    baseline, outcome = _run(team, aggregator)

    assert outcome.intervention.action is InterventionAction.REMOVE
    assert outcome.record.safety.valid is True
    assert outcome.record.reused_role_ids == ["solver"]
    assert outcome.record.reexecuted_role_ids == []
    assert outcome.record.removal_aggregation is not None
    assert outcome.record.removal_aggregation.ordered_role_ids == ["solver"]
    assert outcome.record.removal_aggregation.role_output_hashes == {
        "solver": baseline.role_output_hashes["solver"]
    }
    assert aggregator.calls == [
        (["solver", "critic"], baseline.seeds.aggregation_seed),
        (["solver", "critic"], baseline.seeds.aggregation_seed),
        (["solver"], baseline.seeds.aggregation_seed),
    ]


def test_tampered_baseline_abstains(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    aggregator = RecordingAggregator()
    task = TaskSpec(task_id="task-1", task_text="Return a test artifact.")
    baseline = MockRuntime(MockRuntimeConfig(), aggregator=aggregator).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )
    solver_output = baseline.role_outputs["solver"]
    assert isinstance(solver_output, dict)
    solver_output["message"] = "tampered"

    outcome = ParallelRemovalRunner().run(
        baseline=baseline,
        task=task,
        team=team,
        target_role_id="critic",
        output_team_version="v2",
        manifest=_manifest(aggregator, team),
        aggregator=aggregator,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert outcome.intervention.abstained is True
    assert "baseline_record_valid" in outcome.intervention.reason
    assert "replayable_aggregation" not in outcome.intervention.reason
    assert set(outcome.record.safety.not_run_checks) == {
        "replayable_aggregation",
        "other_responses_frozen",
        "removal_aggregation_succeeded",
    }
    assert len(aggregator.calls) == 1


def test_non_replayable_aggregator_abstains(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    aggregator = NonReplayableAggregator()
    _, outcome = _run(team_factory(), aggregator)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "replayable_aggregation" in outcome.intervention.reason
    assert outcome.record.removal_aggregation is None
    assert len(aggregator.calls) == 2


def test_unexpected_aggregator_exception_abstains_with_record(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    task = TaskSpec(task_id="task-1", task_text="Return a test artifact.")
    baseline = MockRuntime(MockRuntimeConfig()).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )
    aggregator = UnexpectedFailureAggregator()
    outcome = ParallelRemovalRunner().run(
        baseline=baseline,
        task=task,
        team=team,
        target_role_id="critic",
        output_team_version="v2",
        manifest=_manifest(aggregator, team),
        aggregator=aggregator,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert outcome.intervention.abstained is True
    assert outcome.record.replay_aggregation is None
    assert outcome.record.safety.invalid_reasons == ["replayable_aggregation"]
    assert set(outcome.record.safety.not_run_checks) == {
        "other_responses_frozen",
        "removal_aggregation_succeeded",
    }


def test_mock_runtime_isolates_baseline_from_mutating_aggregator(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    task = TaskSpec(
        task_id="task-1",
        task_text="Return a test artifact.",
        public_metadata={"source": "test"},
    )
    baseline = MockRuntime(
        MockRuntimeConfig(),
        aggregator=MutatingAggregator(),
    ).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )

    solver_output = baseline.role_outputs["solver"]
    assert isinstance(solver_output, dict)
    assert solver_output["message"] == "placeholder output; no model was called"
    assert canonical_json_hash(solver_output) == baseline.role_output_hashes["solver"]
    assert task.public_metadata == {"source": "test"}


def test_parallel_removal_rejects_aggregator_that_mutates_response_copies(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    task = TaskSpec(
        task_id="task-1",
        task_text="Return a test artifact.",
        public_metadata={"source": "test"},
    )
    baseline = MockRuntime(MockRuntimeConfig()).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )
    original_hashes = dict(baseline.role_output_hashes)
    aggregator = MutatingAggregator()

    outcome = ParallelRemovalRunner().run(
        baseline=baseline,
        task=task,
        team=team,
        target_role_id="critic",
        output_team_version="v2",
        manifest=_manifest(aggregator, team),
        aggregator=aggregator,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert outcome.record.safety.invalid_reasons == ["replayable_aggregation"]
    assert outcome.record.replay_aggregation is None
    assert outcome.record.safety.other_responses_frozen is None
    assert baseline.role_output_hashes == original_hashes
    assert task.public_metadata == {"source": "test"}


def test_required_target_dependency_blocks_removal(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    team.edges.append(
        CommunicationEdge(
            source_role_id="critic",
            target_role_id="solver",
            artifact="critique",
            semantic_type="test_artifact",
            required=True,
        )
    )
    aggregator = RecordingAggregator()
    _, outcome = _run(team, aggregator)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "no_required_target_dependency" in outcome.intervention.reason
    assert len(aggregator.calls) == 1


def test_non_removable_role_is_rejected(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    team.removal_protocol.non_removable_role_ids = ["critic"]
    aggregator = RecordingAggregator()
    _, outcome = _run(team, aggregator)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "target_not_non_removable" in outcome.intervention.reason


def test_fixed_arity_aggregator_is_rejected(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    aggregator = FixedArityAggregator()
    _, outcome = _run(team_factory(), aggregator)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "variable_arity_aggregation" in outcome.intervention.reason


def test_coverage_gap_and_joint_intervention_force_keep(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    aggregator = RecordingAggregator()
    task = TaskSpec(task_id="task-1", task_text="Return a test artifact.")
    baseline = MockRuntime(MockRuntimeConfig(), aggregator=aggregator).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )
    outcome = ParallelRemovalRunner().run(
        baseline=baseline,
        task=task,
        team=team,
        target_role_id="critic",
        output_team_version="v2",
        manifest=_manifest(aggregator, team),
        aggregator=aggregator,
        coverage_gap_detected=True,
        joint_intervention_required=True,
        contract_topology_sufficient=True,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert outcome.intervention.coverage_gap_detected is True
    assert outcome.intervention.joint_intervention_required is True
    assert {"no_coverage_gap", "no_joint_intervention"}.issubset(
        outcome.intervention.reason
    )


def test_sequential_protocol_is_rejected(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    team.execution_protocol.kind = ProtocolKind.SEQUENTIAL_DAG
    aggregator = RecordingAggregator()
    _, outcome = _run(team, aggregator)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "parallel_protocol" in outcome.intervention.reason


def test_unique_veto_role_is_rejected(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    critic = next(role for role in team.roles if role.role_id == "critic")
    critic.authority_level = AuthorityLevel.VETO
    aggregator = RecordingAggregator()
    _, outcome = _run(team, aggregator)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "target_not_final_or_unique_veto" in outcome.intervention.reason


def test_unknown_target_and_unchanged_team_version_are_rejected(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    aggregator = RecordingAggregator()
    task = TaskSpec(task_id="task-1", task_text="Return a test artifact.")
    baseline = MockRuntime(MockRuntimeConfig(), aggregator=aggregator).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )
    outcome = ParallelRemovalRunner().run(
        baseline=baseline,
        task=task,
        team=team,
        target_role_id="unknown",
        output_team_version=team.team_version,
        manifest=_manifest(aggregator, team),
        aggregator=aggregator,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert {"target_exists", "new_team_version"}.issubset(outcome.intervention.reason)


def test_aggregator_identity_and_topology_evidence_are_required(
    team_factory: Callable[[], CanonicalTeamConfig],
) -> None:
    team = team_factory()
    task = TaskSpec(task_id="task-1", task_text="Return a test artifact.")
    baseline = MockRuntime(MockRuntimeConfig()).run(
        task=task,
        team=team,
        experiment_id="exp-1",
        experiment_seed=11,
    )
    outcome = ParallelRemovalRunner().run(
        baseline=baseline,
        task=task,
        team=team,
        target_role_id="critic",
        output_team_version="v2",
        manifest=_manifest(WrongIdentityAggregator(), team),
        aggregator=WrongIdentityAggregator(),
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=False,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert {"same_aggregation_protocol", "contract_topology_sufficient"}.issubset(
        outcome.intervention.reason
    )
