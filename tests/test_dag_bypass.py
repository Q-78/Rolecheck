from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rolecheck.hashing import canonical_json_hash, role_contract_hash, sha256_text
from rolecheck.manifest import create_manifest
from rolecheck.runtime import (
    AggregationRequest,
    DagBypassRunner,
    MockAggregator,
    MockNodeExecutor,
    NodeExecutionRequest,
)
from rolecheck.schemas import (
    AgentInstance,
    ArtifactSnapshot,
    BypassRule,
    CanonicalTeamConfig,
    CommunicationEdge,
    DagBypassRecord,
    DagExecutionTrace,
    DagNodeExecution,
    ExecutionProtocol,
    ExecutionRecord,
    ExecutionStatus,
    InputSpec,
    InterventionAction,
    NodeExecutorIdentity,
    OutputSpec,
    ProtocolKind,
    RemovalProtocol,
    RemovalStrategy,
    RoleContract,
    SeedBundle,
    TaskSpec,
    Visibility,
)


class RecordingNodeExecutor(MockNodeExecutor):
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.input_payloads: list[dict[str, object]] = []

    def execute(self, request: NodeExecutionRequest) -> dict[str, object]:
        self.calls.append((request.role.role_id, request.role_seed))
        self.input_payloads.append(
            {item.input_name: item.artifact.payload for item in request.inputs}
        )
        return super().execute(request)


class FailingNodeExecutor(MockNodeExecutor):
    def execute(self, request: NodeExecutionRequest) -> dict[str, object]:
        raise OSError("node execution failed")


class MutatingNodeExecutor(MockNodeExecutor):
    def execute(self, request: NodeExecutionRequest) -> dict[str, object]:
        payload = request.inputs[0].artifact.payload
        assert isinstance(payload, dict)
        payload["body"] = "mutated"
        return super().execute(request)


class FixedArityAggregator(MockAggregator):
    @property
    def accepts_variable_responses(self) -> bool:
        return False


class CounterfactualFailureAggregator(MockAggregator):
    def __init__(self) -> None:
        self.calls = 0

    def aggregate(self, request: AggregationRequest) -> object:
        self.calls += 1
        if self.calls == 2:
            raise OSError("counterfactual aggregation failed")
        return super().aggregate(request)


class BrokenIdentityExecutor(MockNodeExecutor):
    @property
    def identity(self) -> NodeExecutorIdentity:
        raise RuntimeError("identity unavailable")


def _role(
    role_id: str,
    *,
    required_inputs: list[InputSpec] | None = None,
    outputs: list[OutputSpec],
    output_visibility: Visibility = Visibility.SHARED,
) -> RoleContract:
    prompt = f"Act as the {role_id} node."
    return RoleContract(
        role_id=role_id,
        role_name=role_id.title(),
        source_initializer="manual-test",
        raw_prompt=prompt,
        prompt_hash=sha256_text(prompt),
        goal=f"Produce {role_id} artifacts.",
        responsibilities=[f"Execute the {role_id} node."],
        required_inputs=required_inputs or [],
        outputs=outputs,
        output_visibility=output_visibility,
        interaction_mode="sequential",
    )


def _team() -> CanonicalTeamConfig:
    upstream = _role(
        "upstream",
        outputs=[
            OutputSpec(
                name="source_artifact",
                semantic_type="review_artifact",
                format="json",
                schema_ref="urn:review:v1",
                required_fields=["content"],
                consumers=["target"],
            )
        ],
    )
    target = _role(
        "target",
        required_inputs=[
            InputSpec(
                name="source_input",
                semantic_type="review_artifact",
                producer_role_id="upstream",
                format="json",
                schema_ref="urn:review:v1",
                required_fields=["content"],
            )
        ],
        outputs=[
            OutputSpec(
                name="target_artifact",
                semantic_type="review_artifact",
                format="json",
                schema_ref="urn:review:v1",
                required_fields=["body"],
                consumers=["downstream"],
            )
        ],
    )
    side = _role(
        "side",
        outputs=[
            OutputSpec(
                name="side_artifact",
                semantic_type="side_artifact",
                format="json",
                required_fields=["note"],
            )
        ],
    )
    downstream = _role(
        "downstream",
        required_inputs=[
            InputSpec(
                name="review_input",
                semantic_type="review_artifact",
                producer_role_id="target",
                format="json",
                schema_ref="urn:review:v1",
                required_fields=["body"],
            )
        ],
        outputs=[
            OutputSpec(
                name="final_artifact",
                semantic_type="final_artifact",
                format="json",
                required_fields=["result"],
            )
        ],
    )
    roles = [upstream, target, side, downstream]
    return CanonicalTeamConfig(
        team_id="dag-team",
        roles=roles,
        agents=[
            AgentInstance(
                agent_id=f"agent-{role.role_id}",
                role_id=role.role_id,
                model_id="mock-model",
            )
            for role in roles
        ],
        edges=[
            CommunicationEdge(
                source_role_id="upstream",
                target_role_id="target",
                artifact="source_artifact",
                semantic_type="review_artifact",
            ),
            CommunicationEdge(
                source_role_id="target",
                target_role_id="downstream",
                artifact="target_artifact",
                semantic_type="review_artifact",
            ),
        ],
        execution_protocol=ExecutionProtocol(
            protocol_id="sequential-dag-v1",
            kind=ProtocolKind.SEQUENTIAL_DAG,
            communication_protocol="declared-dag",
            aggregation_protocol="fixed-mock-aggregation",
            termination_protocol="single-pass",
            execution_order=["upstream", "target", "side", "downstream"],
            fixed_rounds=1,
        ),
        removal_protocol=RemovalProtocol(
            removal_protocol_id="dag-bypass-v1",
            strategy=RemovalStrategy.SCHEMA_PRESERVING_BYPASS,
            bypass_rules=[
                BypassRule(
                    target_role_id="target",
                    upstream_role_id="upstream",
                    upstream_artifact="source_artifact",
                    downstream_role_id="downstream",
                    downstream_input="review_input",
                    semantic_type="review_artifact",
                    field_mapping={"content": "body"},
                )
            ],
        ),
        source_initializer="manual-test",
    )


def _team_with_descendant() -> CanonicalTeamConfig:
    team = _team()
    sink = _role(
        "sink",
        required_inputs=[
            InputSpec(
                name="final_input",
                semantic_type="final_artifact",
                producer_role_id="downstream",
                format="json",
                required_fields=["result"],
            )
        ],
        outputs=[
            OutputSpec(
                name="sink_artifact",
                semantic_type="sink_artifact",
                format="json",
                required_fields=["stored"],
            )
        ],
    )
    downstream = next(role for role in team.roles if role.role_id == "downstream")
    downstream.outputs[0].consumers = ["sink"]
    team.roles.append(sink)
    team.agents.append(
        AgentInstance(
            agent_id="agent-sink",
            role_id="sink",
            model_id="mock-model",
        )
    )
    team.edges.append(
        CommunicationEdge(
            source_role_id="downstream",
            target_role_id="sink",
            artifact="final_artifact",
            semantic_type="final_artifact",
        )
    )
    team.execution_protocol.execution_order.append("sink")
    return CanonicalTeamConfig.model_validate(team.model_dump(mode="json"))


def _artifact(
    producer: str,
    name: str,
    semantic_type: str,
    payload: object,
    *,
    schema_ref: str | None = None,
) -> ArtifactSnapshot:
    return ArtifactSnapshot(
        producer_role_id=producer,
        artifact_name=name,
        semantic_type=semantic_type,
        format="json",
        schema_ref=schema_ref,
        payload=payload,
        payload_hash=canonical_json_hash(payload),
    )


def _node(
    role_id: str,
    seed: int,
    inputs: dict[str, ArtifactSnapshot],
    outputs: dict[str, ArtifactSnapshot],
) -> DagNodeExecution:
    role_output = {name: artifact.payload for name, artifact in outputs.items()}
    return DagNodeExecution(
        role_id=role_id,
        role_seed=seed,
        inputs=inputs,
        outputs=outputs,
        role_output=role_output,
        role_output_hash=canonical_json_hash(role_output),
        reused=False,
        reexecution_reason="baseline_execution",
    )


def _baseline(
    team: CanonicalTeamConfig,
) -> tuple[TaskSpec, ExecutionRecord, DagExecutionTrace]:
    task = TaskSpec(task_id="dag-task", task_text="Process a review artifact.")
    role_seeds = {
        "upstream": 102,
        "target": 103,
        "side": 104,
        "downstream": 105,
    }
    if "sink" in team.execution_protocol.execution_order:
        role_seeds["sink"] = 107
    seeds = SeedBundle(
        experiment_seed=17,
        task_seed=101,
        role_seeds=role_seeds,
        aggregation_seed=106,
    )
    upstream_output = _artifact(
        "upstream",
        "source_artifact",
        "review_artifact",
        {"content": "draft"},
        schema_ref="urn:review:v1",
    )
    target_output = _artifact(
        "target",
        "target_artifact",
        "review_artifact",
        {"body": "checked"},
        schema_ref="urn:review:v1",
    )
    side_output = _artifact(
        "side",
        "side_artifact",
        "side_artifact",
        {"note": "unchanged"},
    )
    downstream_output = _artifact(
        "downstream",
        "final_artifact",
        "final_artifact",
        {"result": "baseline"},
    )
    nodes = [
        _node("upstream", 102, {}, {"source_artifact": upstream_output}),
        _node(
            "target",
            103,
            {"source_input": upstream_output},
            {"target_artifact": target_output},
        ),
        _node("side", 104, {}, {"side_artifact": side_output}),
        _node(
            "downstream",
            105,
            {"review_input": target_output},
            {"final_artifact": downstream_output},
        ),
    ]
    if "sink" in team.execution_protocol.execution_order:
        sink_output = _artifact(
            "sink",
            "sink_artifact",
            "sink_artifact",
            {"stored": "baseline"},
        )
        nodes.append(
            _node(
                "sink",
                107,
                {"final_input": downstream_output},
                {"sink_artifact": sink_output},
            )
        )
    role_outputs = {node.role_id: node.role_output for node in nodes}
    role_hashes = {node.role_id: node.role_output_hash for node in nodes}
    final_output = {
        "mock": True,
        "ordered_roles": team.execution_protocol.execution_order,
        "role_output_hashes": role_hashes,
    }
    now = datetime.now(UTC)
    baseline = ExecutionRecord(
        run_id="dag-baseline-run",
        experiment_id="dag-exp",
        task_id=task.task_id,
        team_id=team.team_id,
        team_version=team.team_version,
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        started_at=now,
        finished_at=now,
        status=ExecutionStatus.SUCCEEDED,
        seeds=seeds,
        role_outputs=role_outputs,
        role_output_hashes=role_hashes,
        final_output=final_output,
        mock=True,
    )
    return task, baseline, DagExecutionTrace(run_id=baseline.run_id, nodes=nodes)


def _manifest(
    team: CanonicalTeamConfig,
    executor: MockNodeExecutor,
    aggregator: MockAggregator | None = None,
) -> object:
    aggregator = aggregator or MockAggregator()
    return create_manifest(
        experiment_id="dag-exp",
        git_commit="test",
        dataset_revision="not-applicable",
        task_split_hash="not-applicable",
        initializer_id="manual-test",
        runtime_id="mock-runtime-v1",
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        seed=17,
        config_hash="sha256:" + "0" * 64,
        model_versions={agent.agent_id: agent.model_id for agent in team.agents},
        prompt_hashes={role.role_id: role.prompt_hash for role in team.roles},
        role_contract_hashes={
            role.role_id: role_contract_hash(role.model_dump(mode="json"))
            for role in team.roles
        },
        aggregator_id=aggregator.identity.aggregator_id,
        aggregator_version=aggregator.identity.aggregator_version,
        aggregator_config_hash=aggregator.identity.config_hash,
        node_executor_id=executor.identity.executor_id,
        node_executor_version=executor.identity.executor_version,
        node_executor_config_hash=executor.identity.config_hash,
        mock=True,
    )


def _run(
    team: CanonicalTeamConfig,
    executor: MockNodeExecutor,
    aggregator: MockAggregator | None = None,
    **overrides: bool,
) -> object:
    aggregator = aggregator or MockAggregator()
    task, baseline, trace = _baseline(team)
    arguments = {
        "coverage_gap_detected": False,
        "joint_intervention_required": False,
        "contract_topology_sufficient": True,
        "irreversible_transformation_detected": False,
        "security_gate_without_alternative": False,
    }
    arguments.update(overrides)
    return DagBypassRunner().run(
        baseline=baseline,
        baseline_trace=trace,
        task=task,
        team=team,
        target_role_id="target",
        output_team_version="v2",
        manifest=_manifest(team, executor, aggregator),
        aggregator=aggregator,
        executor=executor,
        **arguments,
    )


def test_dag_bypass_maps_fields_and_only_reruns_changed_input_nodes() -> None:
    team = _team()
    team_hash = canonical_json_hash(team.model_dump(mode="json"))
    executor = RecordingNodeExecutor()
    outcome = _run(team, executor)

    assert outcome.intervention.action is InterventionAction.REMOVE
    assert outcome.record.safety.valid is True
    assert outcome.record.removed_role_ids == ["target"]
    assert outcome.record.reused_role_ids == ["upstream", "side"]
    assert outcome.record.reexecuted_role_ids == ["downstream"]
    assert executor.calls == [("downstream", 105)]
    assert executor.input_payloads == [{"review_input": {"body": "draft"}}]
    assert outcome.record.bypassed_artifact is not None
    assert outcome.record.bypassed_artifact.payload == {"body": "draft"}
    assert outcome.record.counterfactual_trace is not None
    assert [node.role_id for node in outcome.record.counterfactual_trace.nodes] == [
        "upstream",
        "side",
        "downstream",
    ]
    assert canonical_json_hash(team.model_dump(mode="json")) == team_hash


def test_dag_bypass_reruns_the_full_changed_input_descendant_closure() -> None:
    executor = RecordingNodeExecutor()
    outcome = _run(_team_with_descendant(), executor)

    assert outcome.intervention.action is InterventionAction.REMOVE
    assert outcome.record.reused_role_ids == ["upstream", "side"]
    assert outcome.record.reexecuted_role_ids == ["downstream", "sink"]
    assert executor.calls == [("downstream", 105), ("sink", 107)]


@pytest.mark.parametrize(
    ("override", "value", "reason"),
    [
        ("coverage_gap_detected", True, "no_coverage_gap"),
        ("joint_intervention_required", True, "no_joint_intervention"),
        ("contract_topology_sufficient", False, "contract_topology_sufficient"),
        (
            "irreversible_transformation_detected",
            True,
            "target_not_irreversible",
        ),
        (
            "security_gate_without_alternative",
            True,
            "target_not_security_gate",
        ),
    ],
)
def test_dag_bypass_safety_flags_abstain(
    override: str,
    value: bool,
    reason: str,
) -> None:
    executor = RecordingNodeExecutor()
    outcome = _run(_team(), executor, **{override: value})

    assert outcome.intervention.action is InterventionAction.KEEP
    assert outcome.intervention.abstained is True
    assert reason in outcome.record.safety.invalid_reasons
    assert executor.calls == []
    assert "execution_succeeded" in outcome.record.safety.not_run_checks


def test_unsafe_field_mapping_abstains_before_execution() -> None:
    team = _team()
    team.removal_protocol.bypass_rules[0].field_mapping = {"missing": "body"}
    executor = RecordingNodeExecutor()
    outcome = _run(team, executor)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "field_mapping_safe" in outcome.record.safety.invalid_reasons
    assert executor.calls == []


def test_unknown_downstream_required_fields_abstain_without_guessing() -> None:
    team = _team()
    downstream = next(role for role in team.roles if role.role_id == "downstream")
    downstream.required_inputs[0].required_fields = None
    executor = RecordingNodeExecutor()
    outcome = _run(team, executor)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert {
        "required_fields_available",
        "field_mapping_safe",
    }.issubset(outcome.record.safety.invalid_reasons)
    assert executor.calls == []


def test_multiple_required_bypass_paths_are_rejected() -> None:
    team = _team()
    team.edges.append(
        CommunicationEdge(
            source_role_id="target",
            target_role_id="side",
            artifact="target_artifact",
            semantic_type="review_artifact",
        )
    )
    outcome = _run(team, RecordingNodeExecutor())

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "single_bypass_path" in outcome.record.safety.invalid_reasons


def test_non_topological_execution_order_is_rejected() -> None:
    team = _team()
    team.execution_protocol.execution_order = [
        "downstream",
        "upstream",
        "target",
        "side",
    ]
    task, baseline, trace = _baseline(_team())
    baseline.protocol_id = team.execution_protocol.protocol_id
    executor = RecordingNodeExecutor()
    outcome = DagBypassRunner().run(
        baseline=baseline,
        baseline_trace=trace,
        task=task,
        team=team,
        target_role_id="target",
        output_team_version="v2",
        manifest=_manifest(team, executor),
        aggregator=MockAggregator(),
        executor=executor,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
        irreversible_transformation_detected=False,
        security_gate_without_alternative=False,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "topological_order_valid" in outcome.record.safety.invalid_reasons


def test_fixed_arity_aggregation_is_rejected() -> None:
    outcome = _run(
        _team(),
        RecordingNodeExecutor(),
        aggregator=FixedArityAggregator(),
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "variable_arity_aggregation" in outcome.record.safety.invalid_reasons


def test_semantic_mismatch_abstains_before_execution() -> None:
    team = _team()
    downstream = next(role for role in team.roles if role.role_id == "downstream")
    downstream.required_inputs[0].semantic_type = "different_artifact"
    outcome = _run(team, RecordingNodeExecutor())

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "semantic_type_compatible" in outcome.record.safety.invalid_reasons


@pytest.mark.parametrize("executor", [FailingNodeExecutor(), MutatingNodeExecutor()])
def test_executor_failure_or_input_mutation_abstains(
    executor: MockNodeExecutor,
) -> None:
    outcome = _run(_team(), executor)

    assert outcome.intervention.action is InterventionAction.KEEP
    assert outcome.record.safety.invalid_reasons == ["execution_succeeded"]
    assert outcome.record.counterfactual_trace is None
    assert outcome.record.reused_role_ids == ["upstream", "side"]
    assert [node.role_id for node in outcome.record.attempted_node_executions] == [
        "upstream",
        "side",
    ]
    assert "counterfactual_aggregation_succeeded" in outcome.record.safety.not_run_checks


def test_counterfactual_aggregation_failure_preserves_execution_evidence() -> None:
    aggregator = CounterfactualFailureAggregator()
    outcome = _run(
        _team(),
        RecordingNodeExecutor(),
        aggregator=aggregator,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert outcome.record.safety.invalid_reasons == [
        "counterfactual_aggregation_succeeded"
    ]
    assert outcome.record.counterfactual_trace is not None
    assert outcome.record.reused_role_ids == ["upstream", "side"]
    assert outcome.record.reexecuted_role_ids == ["downstream"]
    assert outcome.record.removed_role_ids == ["target"]


def test_tampered_baseline_trace_abstains_without_execution() -> None:
    team = _team()
    task, baseline, trace = _baseline(team)
    output = trace.nodes[0].role_output
    assert isinstance(output, dict)
    output["source_artifact"] = {"content": "tampered"}
    executor = RecordingNodeExecutor()
    outcome = DagBypassRunner().run(
        baseline=baseline,
        baseline_trace=trace,
        task=task,
        team=team,
        target_role_id="target",
        output_team_version="v2",
        manifest=_manifest(team, executor),
        aggregator=MockAggregator(),
        executor=executor,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
        irreversible_transformation_detected=False,
        security_gate_without_alternative=False,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "baseline_trace_valid" in outcome.record.safety.invalid_reasons
    assert executor.calls == []


def test_succeeded_baseline_with_recorded_errors_is_rejected() -> None:
    team = _team()
    task, baseline, trace = _baseline(team)
    baseline.errors.append("inconsistent succeeded record")
    executor = RecordingNodeExecutor()
    outcome = DagBypassRunner().run(
        baseline=baseline,
        baseline_trace=trace,
        task=task,
        team=team,
        target_role_id="target",
        output_team_version="v2",
        manifest=_manifest(team, executor),
        aggregator=MockAggregator(),
        executor=executor,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
        irreversible_transformation_detected=False,
        security_gate_without_alternative=False,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "baseline_record_valid" in outcome.record.safety.invalid_reasons
    assert executor.calls == []


def test_baseline_artifact_metadata_must_match_role_contract() -> None:
    team = _team()
    task, baseline, trace = _baseline(team)
    trace.nodes[0].outputs["source_artifact"].semantic_type = "other"
    executor = RecordingNodeExecutor()
    outcome = DagBypassRunner().run(
        baseline=baseline,
        baseline_trace=trace,
        task=task,
        team=team,
        target_role_id="target",
        output_team_version="v2",
        manifest=_manifest(team, executor),
        aggregator=MockAggregator(),
        executor=executor,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
        irreversible_transformation_detected=False,
        security_gate_without_alternative=False,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "baseline_trace_valid" in outcome.record.safety.invalid_reasons


def test_broken_executor_identity_abstains_with_evidence() -> None:
    team = _team()
    task, baseline, trace = _baseline(team)
    manifest_executor = MockNodeExecutor()
    outcome = DagBypassRunner().run(
        baseline=baseline,
        baseline_trace=trace,
        task=task,
        team=team,
        target_role_id="target",
        output_team_version="v2",
        manifest=_manifest(team, manifest_executor),
        aggregator=MockAggregator(),
        executor=BrokenIdentityExecutor(),
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
        irreversible_transformation_detected=False,
        security_gate_without_alternative=False,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "executor_identity_valid" in outcome.record.safety.invalid_reasons


def test_unserializable_trace_tampering_abstains_instead_of_raising() -> None:
    team = _team()
    task, baseline, trace = _baseline(team)
    output = trace.nodes[0].role_output
    assert isinstance(output, dict)
    output["source_artifact"] = {"bad": {1, 2}}
    executor = RecordingNodeExecutor()
    outcome = DagBypassRunner().run(
        baseline=baseline,
        baseline_trace=trace,
        task=task,
        team=team,
        target_role_id="target",
        output_team_version="v2",
        manifest=_manifest(team, executor),
        aggregator=MockAggregator(),
        executor=executor,
        coverage_gap_detected=False,
        joint_intervention_required=False,
        contract_topology_sufficient=True,
        irreversible_transformation_detected=False,
        security_gate_without_alternative=False,
    )

    assert outcome.intervention.action is InterventionAction.KEEP
    assert "baseline_trace_valid" in outcome.record.safety.invalid_reasons


def test_input_required_fields_default_is_backward_compatible() -> None:
    input_spec = InputSpec(name="legacy", semantic_type="text")

    assert input_spec.required_fields is None


def test_empty_input_required_fields_preserve_legacy_contract_hash() -> None:
    role = _role(
        "legacy",
        required_inputs=[InputSpec(name="source", semantic_type="text")],
        outputs=[OutputSpec(name="answer", semantic_type="text")],
    )
    current_payload = role.model_dump(mode="json")
    legacy_payload = role.model_dump(mode="json")
    legacy_payload["required_inputs"][0].pop("required_fields")

    assert role_contract_hash(current_payload) == canonical_json_hash(legacy_payload)


def test_valid_dag_record_rejects_counterfactual_seed_forgery() -> None:
    outcome = _run(_team(), RecordingNodeExecutor())
    payload = outcome.record.model_dump(mode="json")
    payload["counterfactual_trace"]["nodes"][-1]["role_seed"] = 999
    payload["attempted_node_executions"][-1]["role_seed"] = 999

    with pytest.raises(ValidationError, match="preserve baseline role seeds"):
        DagBypassRecord.model_validate(payload)
