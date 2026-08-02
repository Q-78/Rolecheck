"""Canonical RoleCheck schemas.

This module intentionally contains data contracts only. It does not implement
role auditing, value prediction, repair generation, or real model execution.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rolecheck.hashing import canonical_json_hash

NonEmptyStr = Annotated[str, Field(min_length=1)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
Sha256Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class StrictModel(BaseModel):
    """Base model with strict unknown-field rejection."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class InformationSetting(StrEnum):
    STRICT = "strict_task_level_pre_execution"
    PROBE_ASSISTED = "probe_assisted_pre_deployment"


class SourceType(StrEnum):
    EXPLICIT = "explicit"
    PARSED = "parsed"
    INFERRED = "inferred"
    DEFAULTED = "defaulted"
    UNKNOWN = "unknown"
    MISSING = "missing"


class Visibility(StrEnum):
    PRIVATE = "private"
    SHARED = "shared"
    UPSTREAM_ONLY = "upstream-only"
    DOWNSTREAM_ONLY = "downstream-only"
    GLOBAL = "global"


class FormatStrictness(StrEnum):
    STRICT = "strict"
    PREFERRED = "preferred"
    FREEFORM = "freeform"


class AuthorityLevel(StrEnum):
    ADVISORY = "advisory"
    VOTING = "voting"
    VETO = "veto"
    FINAL = "final"
    EXECUTION = "execution"


class InteractionMode(StrEnum):
    INDEPENDENT = "independent"
    SEQUENTIAL = "sequential"
    DEBATE = "debate"
    REVIEW = "review"
    TOOL_MEDIATED = "tool-mediated"


class ProtocolKind(StrEnum):
    PARALLEL_INDEPENDENT = "parallel_independent"
    SEQUENTIAL_DAG = "sequential_dag"


class RemovalStrategy(StrEnum):
    PARALLEL_AGGREGATION_REMOVAL = "parallel_aggregation_removal"
    SCHEMA_PRESERVING_BYPASS = "schema_preserving_bypass"
    NONE = "none"


class InterventionAction(StrEnum):
    KEEP = "KEEP"
    REWRITE = "REWRITE"
    REMOVE = "REMOVE"


class ExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class AggregationRunKind(StrEnum):
    BASELINE = "baseline"
    REPLAY = "replay"
    PARALLEL_REMOVAL = "parallel_removal"
    DAG_BYPASS = "dag_bypass"


class FieldProvenance(StrictModel):
    field_path: NonEmptyStr
    source_type: SourceType
    source_span: str | None = None
    confidence: Probability
    extractor: str | None = None


class InputSpec(StrictModel):
    name: NonEmptyStr
    semantic_type: NonEmptyStr
    producer_role_id: str | None = None
    required: bool = True
    format: NonEmptyStr = "plain_text"
    schema_ref: str | None = None
    required_fields: list[NonEmptyStr] | None = None
    description: str = ""


class OutputSpec(StrictModel):
    name: NonEmptyStr
    semantic_type: NonEmptyStr
    consumers: list[str] = Field(default_factory=list)
    format: NonEmptyStr = "plain_text"
    schema_ref: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    description: str = ""


class DependencySpec(StrictModel):
    role_id: NonEmptyStr
    artifact: NonEmptyStr
    required: bool = True
    timing: NonEmptyStr = "before_execution"
    fallback: str | None = None


class ResourceLimits(StrictModel):
    max_tokens: int | None = Field(default=None, ge=1)
    max_latency_ms: int | None = Field(default=None, ge=1)
    max_tool_calls: int | None = Field(default=None, ge=0)


class TaskSpec(StrictModel):
    task_id: NonEmptyStr
    task_text: NonEmptyStr
    task_type: str | None = None
    public_metadata: dict[str, object] = Field(default_factory=dict)
    sensitive_fields: list[str] = Field(default_factory=list)


class RoleContract(StrictModel):
    role_id: NonEmptyStr
    role_name: NonEmptyStr
    role_version: NonEmptyStr = "v1"
    source_initializer: NonEmptyStr
    source_node_id: str | None = None
    raw_prompt: NonEmptyStr
    prompt_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

    goal: NonEmptyStr
    responsibilities: Annotated[list[NonEmptyStr], Field(min_length=1)]
    success_criteria: list[NonEmptyStr] = Field(default_factory=list)
    non_goals: list[NonEmptyStr] = Field(default_factory=list)
    prohibited_behaviors: list[NonEmptyStr] = Field(default_factory=list)
    priority_rules: list[NonEmptyStr] = Field(default_factory=list)

    required_inputs: list[InputSpec] = Field(default_factory=list)
    optional_inputs: list[InputSpec] = Field(default_factory=list)
    input_visibility: Visibility = Visibility.GLOBAL
    context_assumptions: list[NonEmptyStr] = Field(default_factory=list)

    outputs: Annotated[list[OutputSpec], Field(min_length=1)]
    output_visibility: Visibility = Visibility.SHARED
    failure_output: OutputSpec | None = None
    format_strictness: FormatStrictness = FormatStrictness.PREFERRED

    authority_level: AuthorityLevel = AuthorityLevel.ADVISORY
    can_override: list[str] = Field(default_factory=list)
    requires_approval_from: list[str] = Field(default_factory=list)
    decision_scope: list[str] = Field(default_factory=list)
    conflict_resolution_rule: str | None = None

    upstream_dependencies: list[DependencySpec] = Field(default_factory=list)
    downstream_consumers: list[str] = Field(default_factory=list)
    interaction_mode: InteractionMode = InteractionMode.INDEPENDENT
    max_interaction_rounds: int | None = Field(default=None, ge=1)
    termination_signal: str | None = None
    handoff_conditions: list[str] = Field(default_factory=list)

    required_capabilities: list[str] = Field(default_factory=list)
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    provenance: list[FieldProvenance] = Field(default_factory=list)
    parse_confidence: Probability = 1.0
    missing_fields: list[str] = Field(default_factory=list)
    parent_role_version: str | None = None


class AgentInstance(StrictModel):
    agent_id: NonEmptyStr
    role_id: NonEmptyStr
    model_id: NonEmptyStr
    tool_ids: list[str] = Field(default_factory=list)
    sampling_config: dict[str, object] = Field(default_factory=dict)
    resource_limits: ResourceLimits = Field(default_factory=ResourceLimits)
    runtime_metadata: dict[str, object] = Field(default_factory=dict)


class CommunicationEdge(StrictModel):
    source_role_id: NonEmptyStr
    target_role_id: NonEmptyStr
    artifact: NonEmptyStr
    semantic_type: NonEmptyStr
    required: bool = True


class ExecutionProtocol(StrictModel):
    protocol_id: NonEmptyStr
    kind: ProtocolKind
    communication_protocol: NonEmptyStr
    aggregation_protocol: NonEmptyStr
    termination_protocol: NonEmptyStr
    execution_order: list[NonEmptyStr]
    fixed_rounds: int | None = Field(default=None, ge=1)
    protocol_version: NonEmptyStr = "v1"
    immutable_during_intervention: Literal[True] = True


class BypassRule(StrictModel):
    target_role_id: NonEmptyStr
    upstream_role_id: NonEmptyStr
    upstream_artifact: NonEmptyStr
    downstream_role_id: NonEmptyStr
    downstream_input: NonEmptyStr
    semantic_type: NonEmptyStr
    field_mapping: dict[str, str] = Field(default_factory=dict)
    semantic_transformation_allowed: Literal[False] = False


class RemovalProtocol(StrictModel):
    removal_protocol_id: NonEmptyStr
    strategy: RemovalStrategy
    protocol_version: NonEmptyStr = "v1"
    freeze_other_responses: bool = False
    reaggregate_with_same_protocol: bool = False
    bypass_rules: list[BypassRule] = Field(default_factory=list)
    non_removable_role_ids: list[str] = Field(default_factory=list)
    coverage_gap_check_required: Literal[True] = True
    compensation_message_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_strategy_fields(self) -> RemovalProtocol:
        if self.strategy is RemovalStrategy.PARALLEL_AGGREGATION_REMOVAL:
            if not self.freeze_other_responses or not self.reaggregate_with_same_protocol:
                raise ValueError(
                    "parallel removal requires frozen other responses and "
                    "same-protocol reaggregation"
                )
            if self.bypass_rules:
                raise ValueError("parallel removal cannot define DAG bypass rules")
        if self.strategy is RemovalStrategy.SCHEMA_PRESERVING_BYPASS and not self.bypass_rules:
            raise ValueError(
                "schema-preserving bypass requires at least one registered bypass rule"
            )
        return self


class CanonicalTeamConfig(StrictModel):
    team_id: NonEmptyStr
    team_version: NonEmptyStr = "v1"
    roles: Annotated[list[RoleContract], Field(min_length=1)]
    agents: Annotated[list[AgentInstance], Field(min_length=1)]
    edges: list[CommunicationEdge] = Field(default_factory=list)
    execution_protocol: ExecutionProtocol
    removal_protocol: RemovalProtocol
    resource_constraints: ResourceLimits = Field(default_factory=ResourceLimits)
    source_initializer: NonEmptyStr
    adapter_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> CanonicalTeamConfig:
        role_ids = [role.role_id for role in self.roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("role_id values must be unique within a team")

        agent_ids = [agent.agent_id for agent in self.agents]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("agent_id values must be unique within a team")

        role_id_set = set(role_ids)
        for agent in self.agents:
            if agent.role_id not in role_id_set:
                raise ValueError(f"agent {agent.agent_id} references unknown role {agent.role_id}")
        for edge in self.edges:
            if edge.source_role_id not in role_id_set or edge.target_role_id not in role_id_set:
                raise ValueError("all communication edges must reference known roles")
        if set(self.execution_protocol.execution_order) != role_id_set:
            raise ValueError("execution_order must contain each role exactly once")
        if len(self.execution_protocol.execution_order) != len(role_ids):
            raise ValueError("execution_order cannot contain duplicate roles")
        unknown_non_removable = set(self.removal_protocol.non_removable_role_ids) - role_id_set
        if unknown_non_removable:
            raise ValueError(f"non-removable roles are unknown: {sorted(unknown_non_removable)}")
        for rule in self.removal_protocol.bypass_rules:
            referenced = {
                rule.target_role_id,
                rule.upstream_role_id,
                rule.downstream_role_id,
            }
            if not referenced.issubset(role_id_set):
                raise ValueError("bypass rules must reference known roles")
        return self


class SeedBundle(StrictModel):
    experiment_seed: int = Field(ge=0)
    task_seed: int = Field(ge=0)
    role_seeds: dict[str, int] = Field(default_factory=dict)
    aggregation_seed: int = Field(ge=0)
    repair_generation_seed: int | None = Field(default=None, ge=0)
    predictor_seed: int | None = Field(default=None, ge=0)


class AggregatorIdentity(StrictModel):
    aggregator_id: NonEmptyStr
    aggregator_version: NonEmptyStr
    config_hash: Sha256Digest


class RoleExecutionMetrics(StrictModel):
    token_cost: NonNegativeFloat = 0.0
    latency_ms: NonNegativeFloat = 0.0


class NodeExecutorIdentity(StrictModel):
    executor_id: NonEmptyStr
    executor_version: NonEmptyStr
    config_hash: Sha256Digest


class RuntimeAdapterIdentity(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_id: NonEmptyStr
    runtime_version: NonEmptyStr
    config_hash: Sha256Digest


class ArtifactSnapshot(StrictModel):
    producer_role_id: NonEmptyStr
    artifact_name: NonEmptyStr
    semantic_type: NonEmptyStr
    format: NonEmptyStr
    schema_ref: str | None = None
    payload: object
    payload_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_payload_hash(self) -> ArtifactSnapshot:
        if self.payload_hash != canonical_json_hash(self.payload):
            raise ValueError("artifact payload hash does not match payload")
        return self


class DagNodeExecution(StrictModel):
    role_id: NonEmptyStr
    role_seed: int = Field(ge=0)
    inputs: dict[str, ArtifactSnapshot] = Field(default_factory=dict)
    outputs: dict[str, ArtifactSnapshot]
    role_output: object
    role_output_hash: Sha256Digest
    reused: bool
    reexecution_reason: str | None = None

    @model_validator(mode="after")
    def validate_node_evidence(self) -> DagNodeExecution:
        if not self.outputs:
            raise ValueError("a DAG node execution requires output artifacts")
        if any(name != artifact.artifact_name for name, artifact in self.outputs.items()):
            raise ValueError("output artifact keys must match artifact names")
        if any(
            artifact.producer_role_id != self.role_id
            for artifact in self.outputs.values()
        ):
            raise ValueError("node output artifacts must identify their producer role")
        if self.role_output_hash != canonical_json_hash(self.role_output):
            raise ValueError("node role output hash does not match role output")
        if self.reused and self.reexecution_reason is not None:
            raise ValueError("reused nodes cannot have a re-execution reason")
        if not self.reused and not self.reexecution_reason:
            raise ValueError("re-executed nodes require a reason")
        return self


class DagExecutionTrace(StrictModel):
    run_id: NonEmptyStr
    nodes: Annotated[list[DagNodeExecution], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_unique_nodes(self) -> DagExecutionTrace:
        role_ids = [node.role_id for node in self.nodes]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("DAG execution trace roles must be unique")
        return self


class DagBypassSafetyReport(StrictModel):
    baseline_record_valid: bool
    baseline_trace_valid: bool
    aggregator_identity_valid: bool
    executor_identity_valid: bool
    manifest_matches: bool
    sequential_dag: bool
    topological_order_valid: bool
    strategy_predeclared: bool
    single_registered_rule: bool
    single_bypass_path: bool
    same_aggregation_protocol: bool
    variable_arity_aggregation: bool
    new_team_version: bool
    target_exists: bool
    target_not_non_removable: bool
    target_not_final_or_unique_veto: bool
    target_not_irreversible: bool
    target_not_security_gate: bool
    upstream_edge_exists: bool
    downstream_edge_exists: bool
    semantic_type_compatible: bool
    format_compatible: bool
    schema_compatible: bool
    required_fields_available: bool
    visibility_allows_read: bool
    field_mapping_safe: bool
    no_coverage_gap: bool
    no_joint_intervention: bool
    contract_topology_sufficient: bool
    no_compensation: bool
    replayable_aggregation: bool | None
    execution_succeeded: bool | None
    same_role_seeds: bool | None
    target_not_executed: bool | None
    unchanged_inputs_reused: bool | None
    counterfactual_aggregation_succeeded: bool | None
    valid: bool
    invalid_reasons: list[NonEmptyStr] = Field(default_factory=list)
    not_run_checks: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_summary(self) -> DagBypassSafetyReport:
        check_names = [
            name
            for name in type(self).model_fields
            if name not in {"valid", "invalid_reasons", "not_run_checks"}
        ]
        failed = [name for name in check_names if getattr(self, name) is False]
        not_run = [name for name in check_names if getattr(self, name) is None]
        if self.valid != all(getattr(self, name) is True for name in check_names):
            raise ValueError("valid must equal the conjunction of all safety checks")
        if self.valid and self.invalid_reasons:
            raise ValueError("a valid safety report cannot contain invalid reasons")
        if not self.valid and not self.invalid_reasons:
            raise ValueError("an invalid safety report requires reasons")
        if set(self.invalid_reasons) != set(failed):
            raise ValueError("invalid reasons must identify exactly the failed checks")
        if set(self.not_run_checks) != set(not_run):
            raise ValueError("not-run checks must identify exactly the unexecuted checks")
        return self


class DagBypassRecord(StrictModel):
    record_id: NonEmptyStr
    intervention_id: NonEmptyStr
    experiment_id: NonEmptyStr
    baseline_run_id: NonEmptyStr
    task_id: NonEmptyStr
    team_id: NonEmptyStr
    input_team_version: NonEmptyStr
    output_team_version: NonEmptyStr
    protocol_id: NonEmptyStr
    removal_protocol_id: NonEmptyStr
    target_role_id: NonEmptyStr
    seeds: SeedBundle
    manifest_hash: Sha256Digest
    executor: NodeExecutorIdentity
    aggregator: AggregatorIdentity
    bypass_rule: BypassRule | None = None
    bypassed_artifact: ArtifactSnapshot | None = None
    bypass_input_name: str | None = None
    baseline_trace: DagExecutionTrace | None = None
    counterfactual_trace: DagExecutionTrace | None = None
    attempted_node_executions: list[DagNodeExecution] = Field(default_factory=list)
    baseline_aggregation: AggregationSnapshot | None = None
    replay_aggregation: AggregationSnapshot | None = None
    counterfactual_aggregation: AggregationSnapshot | None = None
    reused_role_ids: list[NonEmptyStr] = Field(default_factory=list)
    reexecuted_role_ids: list[NonEmptyStr] = Field(default_factory=list)
    removed_role_ids: list[NonEmptyStr] = Field(default_factory=list)
    safety: DagBypassSafetyReport
    mock: bool
    created_at: datetime

    @model_validator(mode="after")
    def validate_dag_bypass_evidence(self) -> DagBypassRecord:
        attempted_ids = [node.role_id for node in self.attempted_node_executions]
        if self.target_role_id in self.reexecuted_role_ids or self.target_role_id in attempted_ids:
            raise ValueError("a bypassed target cannot be re-executed")
        if len(attempted_ids) != len(set(attempted_ids)):
            raise ValueError("attempted DAG node evidence must contain unique roles")
        if len(self.reused_role_ids) != len(set(self.reused_role_ids)) or len(
            self.reexecuted_role_ids
        ) != len(set(self.reexecuted_role_ids)):
            raise ValueError("reused and re-executed role IDs must be unique")
        if set(self.removed_role_ids) - {self.target_role_id} or len(
            self.removed_role_ids
        ) > 1:
            raise ValueError("DAG bypass may remove at most the single target role")
        if not self.safety.valid:
            return self
        required = (
            self.bypass_rule,
            self.bypassed_artifact,
            self.baseline_trace,
            self.counterfactual_trace,
            self.baseline_aggregation,
            self.replay_aggregation,
            self.counterfactual_aggregation,
        )
        if not all(item is not None for item in required):
            raise ValueError("valid DAG bypass requires complete execution evidence")
        assert self.baseline_trace is not None
        assert self.counterfactual_trace is not None
        assert self.baseline_aggregation is not None
        assert self.replay_aggregation is not None
        assert self.counterfactual_aggregation is not None
        assert self.bypass_rule is not None
        assert self.bypassed_artifact is not None
        if self.baseline_trace.run_id != self.baseline_run_id:
            raise ValueError("baseline trace must reference the baseline run")
        baseline_ids = [node.role_id for node in self.baseline_trace.nodes]
        retained_ids = [role_id for role_id in baseline_ids if role_id != self.target_role_id]
        counterfactual_ids = [node.role_id for node in self.counterfactual_trace.nodes]
        if counterfactual_ids != retained_ids:
            raise ValueError("counterfactual trace must omit exactly the target role")
        if self.removed_role_ids != [self.target_role_id]:
            raise ValueError("valid DAG bypass must remove exactly the target role")
        reused = set(self.reused_role_ids)
        reexecuted = set(self.reexecuted_role_ids)
        if reused & reexecuted or reused | reexecuted != set(retained_ids):
            raise ValueError("reused and re-executed roles must partition retained roles")
        if self.reused_role_ids != [
            node.role_id for node in self.counterfactual_trace.nodes if node.reused
        ]:
            raise ValueError("reused role IDs must match counterfactual node evidence")
        if self.reexecuted_role_ids != [
            node.role_id for node in self.counterfactual_trace.nodes if not node.reused
        ]:
            raise ValueError("re-executed role IDs must match counterfactual node evidence")
        if self.attempted_node_executions != self.counterfactual_trace.nodes:
            raise ValueError("valid bypass attempt evidence must match its complete trace")
        if any(
            node.role_seed != self.seeds.role_seeds.get(node.role_id)
            for node in self.counterfactual_trace.nodes
        ):
            raise ValueError("counterfactual nodes must preserve baseline role seeds")
        downstream_node = next(
            node
            for node in self.counterfactual_trace.nodes
            if node.role_id == self.bypass_rule.downstream_role_id
        )
        bypass_input = downstream_node.inputs.get(self.bypass_rule.downstream_input)
        if (
            bypass_input is None
            or bypass_input.payload_hash != self.bypassed_artifact.payload_hash
        ):
            raise ValueError("downstream input must contain the recorded bypass artifact")
        if self.baseline_aggregation.ordered_role_ids != baseline_ids:
            raise ValueError("baseline aggregation roles must match the baseline trace")
        if (
            self.replay_aggregation.role_output_hashes
            != self.baseline_aggregation.role_output_hashes
        ):
            raise ValueError("replay response hashes must match baseline hashes")
        if self.replay_aggregation.final_output_hash != self.baseline_aggregation.final_output_hash:
            raise ValueError("baseline aggregation replay must be byte-equivalent by hash")
        if self.counterfactual_aggregation.ordered_role_ids != retained_ids:
            raise ValueError("counterfactual aggregation must omit exactly the target role")
        counterfactual_hashes = {
            node.role_id: node.role_output_hash for node in self.counterfactual_trace.nodes
        }
        if self.counterfactual_aggregation.role_output_hashes != counterfactual_hashes:
            raise ValueError("counterfactual aggregation hashes must match node evidence")
        return self


class AggregationSnapshot(StrictModel):
    run_id: NonEmptyStr
    kind: AggregationRunKind
    ordered_role_ids: Annotated[list[NonEmptyStr], Field(min_length=1)]
    role_output_hashes: dict[str, Sha256Digest]
    aggregation_input_hash: Sha256Digest
    aggregation_seed: int = Field(ge=0)
    final_output: object
    final_output_hash: Sha256Digest

    @model_validator(mode="after")
    def validate_inputs(self) -> AggregationSnapshot:
        if len(self.ordered_role_ids) != len(set(self.ordered_role_ids)):
            raise ValueError("aggregation input roles must be unique")
        if set(self.ordered_role_ids) != set(self.role_output_hashes):
            raise ValueError("aggregation input roles and response hashes must match")
        expected_input_hash = canonical_json_hash(
            [
                {
                    "role_id": role_id,
                    "response_hash": self.role_output_hashes[role_id],
                }
                for role_id in self.ordered_role_ids
            ]
        )
        if self.aggregation_input_hash != expected_input_hash:
            raise ValueError("aggregation input hash does not match ordered inputs")
        if self.final_output_hash != canonical_json_hash(self.final_output):
            raise ValueError("final output hash does not match final output")
        return self


class ParallelRemovalSafetyReport(StrictModel):
    baseline_record_valid: bool
    manifest_matches: bool
    parallel_protocol: bool
    strategy_predeclared: bool
    frozen_other_responses: bool
    same_aggregation_protocol: bool
    new_team_version: bool
    target_exists: bool
    target_not_non_removable: bool
    target_not_final_or_unique_veto: bool
    independent_execution: bool
    no_required_target_dependency: bool
    no_exclusive_required_artifact: bool
    homogeneous_responses: bool
    nonempty_retained_responses: bool
    variable_arity_aggregation: bool
    replayable_aggregation: bool | None
    no_coverage_gap: bool
    no_compensation: bool
    no_joint_intervention: bool
    contract_topology_sufficient: bool
    other_responses_frozen: bool | None
    no_roles_reexecuted: bool
    removal_aggregation_succeeded: bool | None
    valid: bool
    invalid_reasons: list[NonEmptyStr] = Field(default_factory=list)
    not_run_checks: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_summary(self) -> ParallelRemovalSafetyReport:
        check_names = [
            name
            for name in type(self).model_fields
            if name not in {"valid", "invalid_reasons", "not_run_checks"}
        ]
        failed = [name for name in check_names if getattr(self, name) is False]
        not_run = [name for name in check_names if getattr(self, name) is None]
        if self.valid != all(getattr(self, name) is True for name in check_names):
            raise ValueError("valid must equal the conjunction of all safety checks")
        if self.valid and self.invalid_reasons:
            raise ValueError("a valid safety report cannot contain invalid reasons")
        if not self.valid and not self.invalid_reasons:
            raise ValueError("an invalid safety report requires reasons")
        if set(self.invalid_reasons) != set(failed):
            raise ValueError("invalid reasons must identify exactly the failed checks")
        if set(self.not_run_checks) != set(not_run):
            raise ValueError("not-run checks must identify exactly the unexecuted checks")
        return self


class ParallelRemovalRecord(StrictModel):
    record_id: NonEmptyStr
    intervention_id: NonEmptyStr
    experiment_id: NonEmptyStr
    baseline_run_id: NonEmptyStr
    task_id: NonEmptyStr
    team_id: NonEmptyStr
    input_team_version: NonEmptyStr
    output_team_version: NonEmptyStr
    protocol_id: NonEmptyStr
    removal_protocol_id: NonEmptyStr
    target_role_id: NonEmptyStr
    seeds: SeedBundle
    manifest_hash: Sha256Digest
    aggregator: AggregatorIdentity
    role_metrics: dict[str, RoleExecutionMetrics] = Field(default_factory=dict)
    baseline_aggregation: AggregationSnapshot | None = None
    replay_aggregation: AggregationSnapshot | None = None
    removal_aggregation: AggregationSnapshot | None = None
    reused_role_ids: list[NonEmptyStr] = Field(default_factory=list)
    reexecuted_role_ids: list[NonEmptyStr] = Field(default_factory=list)
    safety: ParallelRemovalSafetyReport
    mock: bool
    created_at: datetime

    @model_validator(mode="after")
    def validate_parallel_removal_evidence(self) -> ParallelRemovalRecord:
        if self.reexecuted_role_ids:
            raise ValueError("parallel removal cannot re-execute role nodes")
        if not self.safety.valid:
            return self
        if not all(
            (self.baseline_aggregation, self.replay_aggregation, self.removal_aggregation)
        ):
            raise ValueError("valid parallel removal requires all aggregation snapshots")
        assert self.baseline_aggregation is not None
        assert self.replay_aggregation is not None
        assert self.removal_aggregation is not None
        baseline_ids = self.baseline_aggregation.ordered_role_ids
        retained_ids = [role_id for role_id in baseline_ids if role_id != self.target_role_id]
        if self.replay_aggregation.ordered_role_ids != baseline_ids:
            raise ValueError("replay inputs must match baseline inputs")
        if (
            self.replay_aggregation.role_output_hashes
            != self.baseline_aggregation.role_output_hashes
        ):
            raise ValueError("replay response hashes must match baseline hashes")
        if (
            self.replay_aggregation.final_output_hash
            != self.baseline_aggregation.final_output_hash
        ):
            raise ValueError("replay output hash must match baseline output hash")
        if self.removal_aggregation.ordered_role_ids != retained_ids:
            raise ValueError("removal inputs must be baseline inputs without the target")
        retained_hashes = {
            role_id: self.baseline_aggregation.role_output_hashes[role_id]
            for role_id in retained_ids
        }
        if self.removal_aggregation.role_output_hashes != retained_hashes:
            raise ValueError("retained response hashes must match baseline hashes")
        if self.reused_role_ids != retained_ids:
            raise ValueError("reused roles must be exactly the retained roles")
        return self


class ExecutionRecord(StrictModel):
    run_id: NonEmptyStr
    experiment_id: NonEmptyStr
    task_id: NonEmptyStr
    team_id: NonEmptyStr
    team_version: NonEmptyStr
    protocol_id: NonEmptyStr
    removal_protocol_id: NonEmptyStr
    started_at: datetime
    finished_at: datetime
    status: ExecutionStatus
    seeds: SeedBundle
    role_outputs: dict[str, object] = Field(default_factory=dict)
    role_output_hashes: dict[str, str] = Field(default_factory=dict)
    role_metrics: dict[str, RoleExecutionMetrics] = Field(default_factory=dict)
    final_output: object | None = None
    utility: float | None = None
    token_cost: NonNegativeFloat = 0.0
    latency_ms: NonNegativeFloat = 0.0
    mock: bool = False
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timestamps(self) -> ExecutionRecord:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        if self.role_metrics and set(self.role_metrics) != set(self.role_outputs):
            raise ValueError("role metrics must match recorded role outputs")
        return self


class RepairCandidate(StrictModel):
    repair_id: NonEmptyStr
    target_role_id: NonEmptyStr
    parent_role_version: NonEmptyStr
    candidate_contract: RoleContract
    target_defects: list[NonEmptyStr] = Field(default_factory=list)
    changed_fields: Annotated[list[NonEmptyStr], Field(min_length=1)]
    preserved_fields: list[NonEmptyStr] = Field(default_factory=list)
    edit_rationale: NonEmptyStr
    generator_id: NonEmptyStr
    candidate_rank_before_value_prediction: int = Field(ge=1, le=3)
    contract_diff: dict[str, object]
    compatibility_passed: bool
    compatibility_evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_repair_scope(self) -> RepairCandidate:
        allowed_roots = {
            "responsibilities",
            "success_criteria",
            "non_goals",
            "prohibited_behaviors",
            "required_inputs",
            "optional_inputs",
            "outputs",
            "raw_prompt",
            "prompt_hash",
        }
        changed_roots = {path.split(".", maxsplit=1)[0] for path in self.changed_fields}
        forbidden = changed_roots - allowed_roots
        if forbidden:
            raise ValueError(f"repair changes forbidden fields: {sorted(forbidden)}")
        if self.candidate_contract.role_id != self.target_role_id:
            raise ValueError("repair candidate must preserve target role identity")
        if self.candidate_contract.parent_role_version != self.parent_role_version:
            raise ValueError("candidate contract must reference its parent role version")
        return self


class InterventionRecord(StrictModel):
    intervention_id: NonEmptyStr
    experiment_id: NonEmptyStr
    baseline_run_id: NonEmptyStr
    target_role_id: NonEmptyStr
    action: InterventionAction
    selected_repair_id: str | None = None
    input_team_version: NonEmptyStr
    output_team_version: NonEmptyStr
    removal_safe: bool = False
    coverage_gap_detected: bool = False
    joint_intervention_required: bool = False
    abstained: bool = False
    reason: list[NonEmptyStr] = Field(default_factory=list)
    created_at: datetime

    @model_validator(mode="after")
    def validate_action(self) -> InterventionRecord:
        if self.abstained and self.action is not InterventionAction.KEEP:
            raise ValueError("abstention must expose KEEP as the external action")
        if self.joint_intervention_required and self.action is not InterventionAction.KEEP:
            raise ValueError("joint intervention is unsupported in v1 and must default to KEEP")
        if self.action is InterventionAction.REWRITE and not self.selected_repair_id:
            raise ValueError("REWRITE requires selected_repair_id")
        if self.action is not InterventionAction.REWRITE and self.selected_repair_id is not None:
            raise ValueError("selected_repair_id is only valid for REWRITE")
        if self.action is InterventionAction.REMOVE:
            if not self.removal_safe or self.coverage_gap_detected:
                raise ValueError("REMOVE requires safe removal and no coverage gap")
        return self


class KeepValueRecord(StrictModel):
    record_id: NonEmptyStr
    experiment_id: NonEmptyStr
    task_id: NonEmptyStr
    team_id: NonEmptyStr
    role_id: NonEmptyStr
    information_setting: InformationSetting
    protocol_id: NonEmptyStr
    removal_protocol_id: NonEmptyStr

    predicted_delta_utility: float | None = None
    predicted_delta_cost: float | None = None
    predicted_delta_latency_ms: float | None = None
    model_uncertainty: NonNegativeFloat | None = None
    harmful_probability: Probability | None = None
    ood_risk: Probability
    contract_parse_risk: Probability

    observed_delta_utility: float | None = None
    observed_delta_cost: float | None = None
    observed_delta_latency_ms: float | None = None
    label_seed_variance: NonNegativeFloat | None = None

    current_task_outputs_used: Literal[False] = False
    current_task_gold_used: Literal[False] = False
    current_task_counterfactual_results_used: Literal[False] = False
    feature_manifest: list[str] = Field(default_factory=list)


class RepairValueRecord(StrictModel):
    record_id: NonEmptyStr
    experiment_id: NonEmptyStr
    task_id: NonEmptyStr
    team_id: NonEmptyStr
    role_id: NonEmptyStr
    repair_id: NonEmptyStr
    information_setting: InformationSetting
    protocol_id: NonEmptyStr

    predicted_delta_utility: float | None = None
    predicted_delta_cost: float | None = None
    predicted_delta_latency_ms: float | None = None
    model_uncertainty: NonNegativeFloat | None = None
    ood_risk: Probability
    contract_parse_risk: Probability

    observed_delta_utility: float | None = None
    observed_delta_cost: float | None = None
    observed_delta_latency_ms: float | None = None

    current_task_outputs_used: Literal[False] = False
    current_task_gold_used: Literal[False] = False
    current_task_counterfactual_results_used: Literal[False] = False
    feature_manifest: list[str] = Field(default_factory=list)


class DefectAssessment(StrictModel):
    defect_type: NonEmptyStr
    probability: Probability
    evidence: list[str] = Field(default_factory=list)


class RoleAuditReport(StrictModel):
    report_id: NonEmptyStr
    task_id: NonEmptyStr
    team_id: NonEmptyStr
    role_id: NonEmptyStr
    information_setting: InformationSetting

    contract_parse_confidence: Probability
    missing_fields: list[str] = Field(default_factory=list)
    defects: list[DefectAssessment] = Field(default_factory=list)

    keep_value: KeepValueRecord
    repair_candidates: Annotated[list[RepairCandidate], Field(max_length=3)] = Field(
        default_factory=list
    )
    repair_values: Annotated[list[RepairValueRecord], Field(max_length=3)] = Field(
        default_factory=list
    )

    recommended_action: InterventionAction
    selected_repair_id: str | None = None
    removal_safe: bool = False
    coverage_gap_detected: bool = False
    joint_intervention_required: bool = False
    abstained: bool = False
    evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_policy_output(self) -> RoleAuditReport:
        if self.keep_value.role_id != self.role_id:
            raise ValueError("keep-value record must match report role")
        candidate_ids = {candidate.repair_id for candidate in self.repair_candidates}
        if len(candidate_ids) != len(self.repair_candidates):
            raise ValueError("repair candidate IDs must be unique")
        if any(value.repair_id not in candidate_ids for value in self.repair_values):
            raise ValueError("repair values must reference listed candidates")
        if self.abstained and self.recommended_action is not InterventionAction.KEEP:
            raise ValueError("abstention must default to KEEP")
        if (
            self.joint_intervention_required
            and self.recommended_action is not InterventionAction.KEEP
        ):
            raise ValueError("joint intervention must default to KEEP in v1")
        if self.recommended_action is InterventionAction.REWRITE:
            if self.selected_repair_id not in candidate_ids:
                raise ValueError("REWRITE must select one listed repair candidate")
        elif self.selected_repair_id is not None:
            raise ValueError("selected_repair_id is only valid for REWRITE")
        if self.recommended_action is InterventionAction.REMOVE:
            if not self.removal_safe or self.coverage_gap_detected:
                raise ValueError("REMOVE requires safe bypass and no coverage gap")
        return self
