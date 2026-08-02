"""Controlled schema-preserving bypass for one role in a sequential DAG."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from rolecheck.hashing import canonical_json_hash, role_contract_hash
from rolecheck.manifest import ExperimentManifest
from rolecheck.runtime.interfaces import (
    AggregationRequest,
    Aggregator,
    FrozenNodeInput,
    FrozenRoleResponse,
    NodeExecutionRequest,
    NodeExecutor,
    isolated_json_copy,
    isolated_role_copy,
    isolated_task_copy,
)
from rolecheck.schemas import (
    AggregationRunKind,
    AggregationSnapshot,
    AggregatorIdentity,
    ArtifactSnapshot,
    AuthorityLevel,
    BypassRule,
    CanonicalTeamConfig,
    DagBypassRecord,
    DagBypassSafetyReport,
    DagExecutionTrace,
    DagNodeExecution,
    ExecutionRecord,
    ExecutionStatus,
    InputSpec,
    InterventionAction,
    InterventionRecord,
    NodeExecutorIdentity,
    OutputSpec,
    ProtocolKind,
    RemovalStrategy,
    RoleContract,
    TaskSpec,
    Visibility,
)


@dataclass(frozen=True)
class DagBypassOutcome:
    """The DAG evidence record and externally visible intervention decision."""

    record: DagBypassRecord
    intervention: InterventionRecord


@dataclass(frozen=True)
class _ExecutionAttempt:
    nodes: list[DagNodeExecution]
    reused_role_ids: list[str]
    reexecuted_role_ids: list[str]
    trace: DagExecutionTrace | None
    succeeded: bool


_INVALID_IDENTITY_HASH = "sha256:" + "0" * 64


def _aggregator_identity(aggregator: Aggregator) -> tuple[AggregatorIdentity, bool]:
    try:
        return (
            AggregatorIdentity.model_validate(
                aggregator.identity.model_dump(mode="json")
            ),
            True,
        )
    except Exception:
        return (
            AggregatorIdentity(
                aggregator_id="invalid-aggregator-identity",
                aggregator_version="invalid",
                config_hash=_INVALID_IDENTITY_HASH,
            ),
            False,
        )


def _executor_identity(executor: NodeExecutor) -> tuple[NodeExecutorIdentity, bool]:
    try:
        return (
            NodeExecutorIdentity.model_validate(
                executor.identity.model_dump(mode="json")
            ),
            True,
        )
    except Exception:
        return (
            NodeExecutorIdentity(
                executor_id="invalid-node-executor-identity",
                executor_version="invalid",
                config_hash=_INVALID_IDENTITY_HASH,
            ),
            False,
        )


def _stable_id(prefix: str, payload: object) -> str:
    digest = canonical_json_hash(payload).removeprefix("sha256:")[:16]
    return f"{prefix}-{digest}"


def _input_hash(role_ids: list[str], hashes: dict[str, str]) -> str:
    return canonical_json_hash(
        [{"role_id": role_id, "response_hash": hashes[role_id]} for role_id in role_ids]
    )


def _snapshot(
    *,
    run_id: str,
    kind: AggregationRunKind,
    role_ids: list[str],
    hashes: dict[str, str],
    aggregation_seed: int,
    final_output: object,
) -> AggregationSnapshot:
    copied_output = isolated_json_copy(final_output)
    selected_hashes = {role_id: hashes[role_id] for role_id in role_ids}
    return AggregationSnapshot(
        run_id=run_id,
        kind=kind,
        ordered_role_ids=role_ids,
        role_output_hashes=selected_hashes,
        aggregation_input_hash=_input_hash(role_ids, selected_hashes),
        aggregation_seed=aggregation_seed,
        final_output=copied_output,
        final_output_hash=canonical_json_hash(copied_output),
    )


def _baseline_valid(
    baseline: ExecutionRecord,
    task: TaskSpec,
    team: CanonicalTeamConfig,
) -> bool:
    role_ids = team.execution_protocol.execution_order
    if (
        baseline.status is not ExecutionStatus.SUCCEEDED
        or baseline.final_output is None
        or baseline.errors
    ):
        return False
    if (
        baseline.task_id != task.task_id
        or baseline.team_id != team.team_id
        or baseline.team_version != team.team_version
        or baseline.protocol_id != team.execution_protocol.protocol_id
        or baseline.removal_protocol_id != team.removal_protocol.removal_protocol_id
    ):
        return False
    if set(baseline.role_outputs) != set(role_ids):
        return False
    if set(baseline.role_output_hashes) != set(role_ids):
        return False
    if set(baseline.seeds.role_seeds) != set(role_ids):
        return False
    try:
        return all(
            canonical_json_hash(baseline.role_outputs[role_id])
            == baseline.role_output_hashes[role_id]
            for role_id in role_ids
        )
    except (TypeError, ValueError):
        return False


def _trace_valid(
    trace: DagExecutionTrace,
    baseline: ExecutionRecord,
    team: CanonicalTeamConfig,
) -> bool:
    role_ids = team.execution_protocol.execution_order
    if trace.run_id != baseline.run_id:
        return False
    if [node.role_id for node in trace.nodes] != role_ids:
        return False
    nodes = {node.role_id: node for node in trace.nodes}
    roles = {role.role_id: role for role in team.roles}
    for role_id in role_ids:
        node = nodes[role_id]
        role = roles[role_id]
        if (
            node.role_seed != baseline.seeds.role_seeds[role_id]
            or node.role_output_hash != baseline.role_output_hashes[role_id]
            or canonical_json_hash(node.role_output)
            != baseline.role_output_hashes[role_id]
            or node.role_output
            != {name: artifact.payload for name, artifact in node.outputs.items()}
        ):
            return False
        output_specs = {output.name: output for output in role.outputs}
        if set(node.outputs) != set(output_specs):
            return False
        for name, artifact in node.outputs.items():
            output_spec = output_specs[name]
            if (
                artifact.producer_role_id != role_id
                or artifact.semantic_type != output_spec.semantic_type
                or artifact.format != output_spec.format
                or artifact.schema_ref != output_spec.schema_ref
                or (
                    output_spec.required_fields
                    and (
                        not isinstance(artifact.payload, dict)
                        or not set(output_spec.required_fields).issubset(artifact.payload)
                    )
                )
            ):
                return False
        input_specs = {
            input_spec.name: input_spec
            for input_spec in role.required_inputs + role.optional_inputs
        }
        if not {item.name for item in role.required_inputs}.issubset(node.inputs):
            return False
        if not set(node.inputs).issubset(input_specs):
            return False
        for name, artifact in node.inputs.items():
            input_spec = input_specs[name]
            if (
                artifact.semantic_type != input_spec.semantic_type
                or artifact.format != input_spec.format
                or artifact.schema_ref != input_spec.schema_ref
                or (
                    input_spec.producer_role_id is not None
                    and artifact.producer_role_id != input_spec.producer_role_id
                )
                or (
                    input_spec.required_fields
                    and (
                        not isinstance(artifact.payload, dict)
                        or not set(input_spec.required_fields).issubset(artifact.payload)
                    )
                )
            ):
                return False
    return True


def _manifest_matches(
    manifest: ExperimentManifest,
    baseline: ExecutionRecord,
    team: CanonicalTeamConfig,
    aggregator_identity: AggregatorIdentity,
    executor_identity: NodeExecutorIdentity,
) -> bool:
    expected_models = {agent.agent_id: agent.model_id for agent in team.agents}
    expected_prompts = {role.role_id: role.prompt_hash for role in team.roles}
    expected_contracts = {
        role.role_id: role_contract_hash(role.model_dump(mode="json"))
        for role in team.roles
    }
    expected_tool_ids = {tool_id for agent in team.agents for tool_id in agent.tool_ids}
    return (
        manifest.experiment_id == baseline.experiment_id
        and manifest.protocol_id == team.execution_protocol.protocol_id
        and manifest.removal_protocol_id == team.removal_protocol.removal_protocol_id
        and manifest.seed == baseline.seeds.experiment_seed
        and manifest.model_versions == expected_models
        and manifest.prompt_hashes == expected_prompts
        and manifest.role_contract_hashes == expected_contracts
        and set(manifest.tool_hashes) == expected_tool_ids
        and manifest.aggregator_id == aggregator_identity.aggregator_id
        and manifest.aggregator_version == aggregator_identity.aggregator_version
        and manifest.aggregator_config_hash == aggregator_identity.config_hash
        and manifest.node_executor_id == executor_identity.executor_id
        and manifest.node_executor_version == executor_identity.executor_version
        and manifest.node_executor_config_hash == executor_identity.config_hash
        and manifest.mock == baseline.mock
    )


def _find_output(role: RoleContract, name: str) -> OutputSpec | None:
    return next((output for output in role.outputs if output.name == name), None)


def _find_required_input(role: RoleContract, name: str) -> InputSpec | None:
    return next(
        (input_spec for input_spec in role.required_inputs if input_spec.name == name),
        None,
    )


def _map_payload(payload: object, field_mapping: dict[str, str]) -> object | None:
    copied = isolated_json_copy(payload)
    if not field_mapping:
        return copied
    if not isinstance(copied, dict):
        return None
    if len(set(field_mapping.values())) != len(field_mapping):
        return None
    if not set(field_mapping).issubset(copied):
        return None
    untouched = set(copied) - set(field_mapping)
    if untouched & set(field_mapping.values()):
        return None
    return {field_mapping.get(key, key): value for key, value in copied.items()}


def _artifact_copy(artifact: ArtifactSnapshot) -> ArtifactSnapshot:
    return ArtifactSnapshot.model_validate(
        isolated_json_copy(artifact.model_dump(mode="json"))
    )


class DagBypassRunner:
    """Remove one sequential node and replay only the changed-input closure."""

    def run(
        self,
        *,
        baseline: ExecutionRecord,
        baseline_trace: DagExecutionTrace,
        task: TaskSpec,
        team: CanonicalTeamConfig,
        target_role_id: str,
        output_team_version: str,
        manifest: ExperimentManifest,
        aggregator: Aggregator,
        executor: NodeExecutor,
        coverage_gap_detected: bool,
        joint_intervention_required: bool,
        contract_topology_sufficient: bool,
        irreversible_transformation_detected: bool,
        security_gate_without_alternative: bool,
    ) -> DagBypassOutcome:
        role_ids = team.execution_protocol.execution_order
        retained_ids = [role_id for role_id in role_ids if role_id != target_role_id]
        roles = {role.role_id: role for role in team.roles}
        target = roles.get(target_role_id)
        rules = [
            rule
            for rule in team.removal_protocol.bypass_rules
            if rule.target_role_id == target_role_id
        ]
        rule = rules[0] if len(rules) == 1 else None
        aggregator_identity, aggregator_identity_valid = _aggregator_identity(aggregator)
        executor_identity, executor_identity_valid = _executor_identity(executor)
        manifest_hash = canonical_json_hash(manifest.model_dump(mode="json"))
        try:
            baseline_trace_valid = _trace_valid(baseline_trace, baseline, team)
        except Exception:
            baseline_trace_valid = False
        try:
            variable_arity_aggregation = aggregator.accepts_variable_responses is True
        except Exception:
            variable_arity_aggregation = False

        upstream_role = roles.get(rule.upstream_role_id) if rule else None
        downstream_role = roles.get(rule.downstream_role_id) if rule else None
        upstream_output = (
            _find_output(upstream_role, rule.upstream_artifact)
            if upstream_role is not None and rule is not None
            else None
        )
        downstream_input = (
            _find_required_input(downstream_role, rule.downstream_input)
            if downstream_role is not None and rule is not None
            else None
        )
        upstream_edge = bool(
            rule
            and any(
                edge.required
                and edge.source_role_id == rule.upstream_role_id
                and edge.target_role_id == target_role_id
                and edge.artifact == rule.upstream_artifact
                for edge in team.edges
            )
        )
        downstream_edge = bool(
            rule
            and downstream_input
            and downstream_input.producer_role_id == target_role_id
            and any(
                edge.required
                and edge.source_role_id == target_role_id
                and edge.target_role_id == rule.downstream_role_id
                for edge in team.edges
            )
        )
        incoming_edges = [
            edge
            for edge in team.edges
            if edge.target_role_id == target_role_id
        ]
        outgoing_edges = [
            edge
            for edge in team.edges
            if edge.source_role_id == target_role_id
        ]
        target_required_inputs = target.required_inputs if target is not None else []
        downstream_target_inputs = (
            [
                item
                for item in downstream_role.required_inputs
                if item.producer_role_id == target_role_id
            ]
            if downstream_role is not None
            else []
        )
        single_bypass_path = bool(
            rule
            and target is not None
            and upstream_edge
            and downstream_edge
            and len(incoming_edges) == 1
            and len(outgoing_edges) == 1
            and len(target_required_inputs) == 1
            and not target.optional_inputs
            and target_required_inputs[0].producer_role_id == rule.upstream_role_id
            and len(target.outputs) == 1
            and len(downstream_target_inputs) == 1
            and downstream_target_inputs[0].name == rule.downstream_input
        )
        order_index = {role_id: index for index, role_id in enumerate(role_ids)}
        topological_order_valid = all(
            order_index[edge.source_role_id] < order_index[edge.target_role_id]
            for edge in team.edges
            if edge.required
        )
        target_is_unique_final_or_veto = False
        if target is not None and target.authority_level in {
            AuthorityLevel.FINAL,
            AuthorityLevel.VETO,
        }:
            target_is_unique_final_or_veto = sum(
                role.authority_level is target.authority_level for role in team.roles
            ) == 1

        semantic_compatible = bool(
            rule
            and upstream_output
            and downstream_input
            and upstream_output.semantic_type
            == downstream_input.semantic_type
            == rule.semantic_type
        )
        format_compatible = bool(
            upstream_output
            and downstream_input
            and upstream_output.format == downstream_input.format
        )
        schema_compatible = bool(
            upstream_output
            and downstream_input
            and upstream_output.schema_ref == downstream_input.schema_ref
        )
        declared_mapping_safe = bool(
            rule
            and upstream_output
            and downstream_input
            and downstream_input.required_fields is not None
            and len(set(rule.field_mapping.values())) == len(rule.field_mapping)
            and set(rule.field_mapping).issubset(upstream_output.required_fields)
            and set(rule.field_mapping.values()).issubset(
                downstream_input.required_fields
            )
        ) if rule and rule.field_mapping else True
        mapped_declared_fields = (
            {
                rule.field_mapping.get(field, field)
                for field in upstream_output.required_fields
            }
            if rule and upstream_output
            else set()
        )
        required_fields_available = bool(
            downstream_input
            and downstream_input.required_fields is not None
            and set(downstream_input.required_fields).issubset(mapped_declared_fields)
        )
        visibility_allows_read = bool(
            upstream_role
            and upstream_role.output_visibility
            in {Visibility.SHARED, Visibility.DOWNSTREAM_ONLY, Visibility.GLOBAL}
        )

        checks: dict[str, bool | None] = {
            "baseline_record_valid": _baseline_valid(baseline, task, team),
            "baseline_trace_valid": baseline_trace_valid,
            "aggregator_identity_valid": aggregator_identity_valid,
            "executor_identity_valid": executor_identity_valid,
            "manifest_matches": _manifest_matches(
                manifest,
                baseline,
                team,
                aggregator_identity,
                executor_identity,
            ),
            "sequential_dag": team.execution_protocol.kind is ProtocolKind.SEQUENTIAL_DAG,
            "topological_order_valid": topological_order_valid,
            "strategy_predeclared": (
                team.removal_protocol.strategy is RemovalStrategy.SCHEMA_PRESERVING_BYPASS
            ),
            "single_registered_rule": rule is not None,
            "single_bypass_path": single_bypass_path,
            "same_aggregation_protocol": (
                aggregator_identity.aggregator_id
                == team.execution_protocol.aggregation_protocol
            ),
            "variable_arity_aggregation": variable_arity_aggregation,
            "new_team_version": output_team_version != team.team_version,
            "target_exists": target is not None,
            "target_not_non_removable": (
                target_role_id not in team.removal_protocol.non_removable_role_ids
            ),
            "target_not_final_or_unique_veto": not target_is_unique_final_or_veto,
            "target_not_irreversible": not irreversible_transformation_detected,
            "target_not_security_gate": not security_gate_without_alternative,
            "upstream_edge_exists": upstream_edge,
            "downstream_edge_exists": downstream_edge,
            "semantic_type_compatible": semantic_compatible,
            "format_compatible": format_compatible,
            "schema_compatible": schema_compatible,
            "required_fields_available": required_fields_available,
            "visibility_allows_read": visibility_allows_read,
            "field_mapping_safe": declared_mapping_safe,
            "no_coverage_gap": not coverage_gap_detected,
            "no_joint_intervention": not joint_intervention_required,
            "contract_topology_sufficient": contract_topology_sufficient,
            "no_compensation": not team.removal_protocol.compensation_message_allowed,
            "replayable_aggregation": None,
            "execution_succeeded": None,
            "same_role_seeds": None,
            "target_not_executed": None,
            "unchanged_inputs_reused": None,
            "counterfactual_aggregation_succeeded": None,
        }

        baseline_snapshot: AggregationSnapshot | None = None
        replay_snapshot: AggregationSnapshot | None = None
        counterfactual_snapshot: AggregationSnapshot | None = None
        counterfactual_trace: DagExecutionTrace | None = None
        bypassed_artifact: ArtifactSnapshot | None = None
        attempted_nodes: list[DagNodeExecution] = []
        reused_ids: list[str] = []
        reexecuted_ids: list[str] = []
        post_names = {
            "replayable_aggregation",
            "execution_succeeded",
            "same_role_seeds",
            "target_not_executed",
            "unchanged_inputs_reused",
            "counterfactual_aggregation_succeeded",
        }
        if all(checks[name] is True for name in checks if name not in post_names):
            baseline_snapshot = _snapshot(
                run_id=baseline.run_id,
                kind=AggregationRunKind.BASELINE,
                role_ids=role_ids,
                hashes=baseline.role_output_hashes,
                aggregation_seed=baseline.seeds.aggregation_seed,
                final_output=baseline.final_output,
            )
            replay_snapshot = self._aggregate_snapshot(
                kind=AggregationRunKind.REPLAY,
                baseline_run_id=baseline.run_id,
                task=task,
                role_ids=role_ids,
                role_outputs=baseline.role_outputs,
                role_hashes=baseline.role_output_hashes,
                aggregation_seed=baseline.seeds.aggregation_seed,
                aggregator=aggregator,
            )
            checks["replayable_aggregation"] = bool(
                replay_snapshot
                and replay_snapshot.final_output_hash == baseline_snapshot.final_output_hash
            )
            if checks["replayable_aggregation"]:
                assert rule is not None
                nodes = {node.role_id: node for node in baseline_trace.nodes}
                upstream_node = nodes[rule.upstream_role_id]
                upstream_artifact = upstream_node.outputs.get(rule.upstream_artifact)
                mapped_payload = (
                    _map_payload(upstream_artifact.payload, rule.field_mapping)
                    if upstream_artifact is not None
                    else None
                )
                runtime_mapping_safe = mapped_payload is not None
                if runtime_mapping_safe and isinstance(mapped_payload, dict):
                    assert downstream_input is not None
                    assert downstream_input.required_fields is not None
                    runtime_mapping_safe = set(
                        downstream_input.required_fields
                    ).issubset(mapped_payload)
                checks["field_mapping_safe"] = runtime_mapping_safe
                if runtime_mapping_safe:
                    assert upstream_artifact is not None
                    assert mapped_payload is not None
                    bypassed_artifact = ArtifactSnapshot(
                        producer_role_id=upstream_artifact.producer_role_id,
                        artifact_name=upstream_artifact.artifact_name,
                        semantic_type=upstream_artifact.semantic_type,
                        format=upstream_artifact.format,
                        schema_ref=upstream_artifact.schema_ref,
                        payload=mapped_payload,
                        payload_hash=canonical_json_hash(mapped_payload),
                    )
                    execution = self._execute_counterfactual(
                        baseline=baseline,
                        baseline_trace=baseline_trace,
                        task=task,
                        team=team,
                        target_role_id=target_role_id,
                        rule=rule,
                        bypassed_artifact=bypassed_artifact,
                        executor=executor,
                    )
                    attempted_nodes = execution.nodes
                    reused_ids = execution.reused_role_ids
                    reexecuted_ids = execution.reexecuted_role_ids
                    checks["execution_succeeded"] = execution.succeeded
                    checks["same_role_seeds"] = True
                    checks["target_not_executed"] = True
                    checks["unchanged_inputs_reused"] = True
                    if execution.succeeded:
                        assert execution.trace is not None
                        counterfactual_trace = execution.trace
                        counter_outputs = {
                            node.role_id: node.role_output
                            for node in counterfactual_trace.nodes
                        }
                        counter_hashes = {
                            node.role_id: node.role_output_hash
                            for node in counterfactual_trace.nodes
                        }
                        counterfactual_snapshot = self._aggregate_snapshot(
                            kind=AggregationRunKind.DAG_BYPASS,
                            baseline_run_id=baseline.run_id,
                            task=task,
                            role_ids=retained_ids,
                            role_outputs=counter_outputs,
                            role_hashes=counter_hashes,
                            aggregation_seed=baseline.seeds.aggregation_seed,
                            aggregator=aggregator,
                        )
                        checks["counterfactual_aggregation_succeeded"] = (
                            counterfactual_snapshot is not None
                        )

        failed_checks = [name for name, passed in checks.items() if passed is False]
        not_run_checks = [name for name, passed in checks.items() if passed is None]
        valid = all(passed is True for passed in checks.values())
        safety = DagBypassSafetyReport.model_validate(
            {
                **checks,
                "valid": valid,
                "invalid_reasons": failed_checks,
                "not_run_checks": not_run_checks,
            }
        )
        identity_payload = {
            "baseline_run_id": baseline.run_id,
            "target_role_id": target_role_id,
            "manifest_hash": manifest_hash,
            "executor": executor_identity.model_dump(mode="json"),
            "aggregator": aggregator_identity.model_dump(mode="json"),
        }
        intervention_id = _stable_id("intervention", identity_payload)
        effective_version = output_team_version if valid else team.team_version
        created_at = datetime.now(UTC)
        record = DagBypassRecord(
            record_id=_stable_id("dag-bypass", identity_payload),
            intervention_id=intervention_id,
            experiment_id=baseline.experiment_id,
            baseline_run_id=baseline.run_id,
            task_id=task.task_id,
            team_id=team.team_id,
            input_team_version=team.team_version,
            output_team_version=effective_version,
            protocol_id=team.execution_protocol.protocol_id,
            removal_protocol_id=team.removal_protocol.removal_protocol_id,
            target_role_id=target_role_id,
            seeds=baseline.seeds,
            manifest_hash=manifest_hash,
            executor=executor_identity,
            aggregator=aggregator_identity,
            bypass_rule=rule,
            bypassed_artifact=bypassed_artifact,
            bypass_input_name=rule.downstream_input if rule else None,
            baseline_trace=baseline_trace if checks["baseline_trace_valid"] else None,
            counterfactual_trace=counterfactual_trace,
            attempted_node_executions=attempted_nodes,
            baseline_aggregation=baseline_snapshot,
            replay_aggregation=replay_snapshot,
            counterfactual_aggregation=counterfactual_snapshot,
            reused_role_ids=reused_ids,
            reexecuted_role_ids=reexecuted_ids,
            removed_role_ids=[target_role_id] if attempted_nodes else [],
            safety=safety,
            mock=baseline.mock,
            created_at=created_at,
        )
        intervention = InterventionRecord(
            intervention_id=intervention_id,
            experiment_id=baseline.experiment_id,
            baseline_run_id=baseline.run_id,
            target_role_id=target_role_id,
            action=InterventionAction.REMOVE if valid else InterventionAction.KEEP,
            input_team_version=team.team_version,
            output_team_version=effective_version,
            removal_safe=valid,
            coverage_gap_detected=coverage_gap_detected,
            joint_intervention_required=joint_intervention_required,
            abstained=not valid,
            reason=failed_checks,
            created_at=created_at,
        )
        return DagBypassOutcome(record=record, intervention=intervention)

    @staticmethod
    def _execute_counterfactual(
        *,
        baseline: ExecutionRecord,
        baseline_trace: DagExecutionTrace,
        task: TaskSpec,
        team: CanonicalTeamConfig,
        target_role_id: str,
        rule: BypassRule,
        bypassed_artifact: ArtifactSnapshot,
        executor: NodeExecutor,
    ) -> _ExecutionAttempt:
        roles = {role.role_id: role for role in team.roles}
        baseline_nodes = {node.role_id: node for node in baseline_trace.nodes}
        current_outputs: dict[str, dict[str, ArtifactSnapshot]] = {}
        counter_nodes: list[DagNodeExecution] = []
        reused: list[str] = []
        reexecuted: list[str] = []

        def failed_attempt() -> _ExecutionAttempt:
            return _ExecutionAttempt(
                nodes=counter_nodes,
                reused_role_ids=reused,
                reexecuted_role_ids=reexecuted,
                trace=None,
                succeeded=False,
            )

        for role_id in team.execution_protocol.execution_order:
            if role_id == target_role_id:
                continue
            baseline_node = baseline_nodes[role_id]
            inputs = {
                name: _artifact_copy(artifact)
                for name, artifact in baseline_node.inputs.items()
            }
            for input_name, artifact in tuple(inputs.items()):
                replacement = current_outputs.get(artifact.producer_role_id, {}).get(
                    artifact.artifact_name
                )
                if replacement is not None:
                    inputs[input_name] = _artifact_copy(replacement)
            if role_id == rule.downstream_role_id:
                inputs[rule.downstream_input] = _artifact_copy(bypassed_artifact)
            input_hashes = {
                name: artifact.payload_hash for name, artifact in inputs.items()
            }
            baseline_hashes = {
                name: artifact.payload_hash
                for name, artifact in baseline_node.inputs.items()
            }
            if input_hashes == baseline_hashes:
                reused_node = DagNodeExecution.model_validate(
                    {
                        **baseline_node.model_dump(mode="json"),
                        "reused": True,
                        "reexecution_reason": None,
                    }
                )
                counter_nodes.append(reused_node)
                current_outputs[role_id] = reused_node.outputs
                reused.append(role_id)
                continue
            role = roles[role_id]
            request_inputs = tuple(
                FrozenNodeInput(input_name=name, artifact=_artifact_copy(artifact))
                for name, artifact in inputs.items()
            )
            try:
                output_payloads = executor.execute(
                    NodeExecutionRequest(
                        task=isolated_task_copy(task),
                        role=isolated_role_copy(role),
                        inputs=request_inputs,
                        role_seed=baseline.seeds.role_seeds[role_id],
                    )
                )
                if any(
                    canonical_json_hash(item.artifact.payload)
                    != item.artifact.payload_hash
                    for item in request_inputs
                ):
                    return failed_attempt()
                copied_payloads = isolated_json_copy(output_payloads)
                if not isinstance(copied_payloads, dict):
                    return failed_attempt()
                output_specs = {output.name: output for output in role.outputs}
                if set(copied_payloads) != set(output_specs):
                    return failed_attempt()
                if any(
                    output_specs[name].required_fields
                    and (
                        not isinstance(payload, dict)
                        or not set(output_specs[name].required_fields).issubset(payload)
                    )
                    for name, payload in copied_payloads.items()
                ):
                    return failed_attempt()
                outputs = {
                    name: ArtifactSnapshot(
                        producer_role_id=role_id,
                        artifact_name=name,
                        semantic_type=output_specs[name].semantic_type,
                        format=output_specs[name].format,
                        schema_ref=output_specs[name].schema_ref,
                        payload=payload,
                        payload_hash=canonical_json_hash(payload),
                    )
                    for name, payload in copied_payloads.items()
                }
            except Exception:
                return failed_attempt()
            role_output = {name: artifact.payload for name, artifact in outputs.items()}
            executed_node = DagNodeExecution(
                role_id=role_id,
                role_seed=baseline.seeds.role_seeds[role_id],
                inputs=inputs,
                outputs=outputs,
                role_output=role_output,
                role_output_hash=canonical_json_hash(role_output),
                reused=False,
                reexecution_reason="input_artifact_hash_changed",
            )
            counter_nodes.append(executed_node)
            current_outputs[role_id] = outputs
            reexecuted.append(role_id)
        run_id = _stable_id(
            "dag-counterfactual",
            {
                "baseline_run_id": baseline.run_id,
                "target_role_id": target_role_id,
                "node_hashes": {
                    node.role_id: node.role_output_hash for node in counter_nodes
                },
            },
        )
        trace = DagExecutionTrace(run_id=run_id, nodes=counter_nodes)
        return _ExecutionAttempt(
            nodes=counter_nodes,
            reused_role_ids=reused,
            reexecuted_role_ids=reexecuted,
            trace=trace,
            succeeded=True,
        )

    @staticmethod
    def _aggregate_snapshot(
        *,
        kind: AggregationRunKind,
        baseline_run_id: str,
        task: TaskSpec,
        role_ids: list[str],
        role_outputs: dict[str, object],
        role_hashes: dict[str, str],
        aggregation_seed: int,
        aggregator: Aggregator,
    ) -> AggregationSnapshot | None:
        try:
            responses = tuple(
                FrozenRoleResponse(
                    role_id=role_id,
                    output=isolated_json_copy(role_outputs[role_id]),
                    output_hash=role_hashes[role_id],
                )
                for role_id in role_ids
            )
            final_output = aggregator.aggregate(
                AggregationRequest(
                    task=isolated_task_copy(task),
                    responses=responses,
                    aggregation_seed=aggregation_seed,
                )
            )
            if any(
                canonical_json_hash(response.output) != response.output_hash
                for response in responses
            ):
                return None
            final_output = isolated_json_copy(final_output)
        except Exception:
            return None
        run_id = _stable_id(
            kind.value,
            {
                "baseline_run_id": baseline_run_id,
                "role_ids": role_ids,
                "hashes": {role_id: role_hashes[role_id] for role_id in role_ids},
                "aggregation_seed": aggregation_seed,
                "final_output": final_output,
            },
        )
        return _snapshot(
            run_id=run_id,
            kind=kind,
            role_ids=role_ids,
            hashes=role_hashes,
            aggregation_seed=aggregation_seed,
            final_output=final_output,
        )
