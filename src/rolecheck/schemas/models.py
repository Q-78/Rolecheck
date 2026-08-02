"""Canonical RoleCheck schemas.

This module intentionally contains data contracts only. It does not implement
role auditing, value prediction, repair generation, or real model execution.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonEmptyStr = Annotated[str, Field(min_length=1)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]


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
