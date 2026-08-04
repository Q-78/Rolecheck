"""Controlled parallel single-role removal with frozen baseline responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from rolecheck.hashing import canonical_json_hash, role_contract_hash
from rolecheck.manifest import ExperimentManifest
from rolecheck.runtime.interfaces import (
    AggregationRequest,
    Aggregator,
    FrozenRoleResponse,
    isolated_json_copy,
    isolated_task_copy,
)
from rolecheck.schemas import (
    AggregationRunKind,
    AggregationSnapshot,
    AggregatorIdentity,
    AuthorityLevel,
    CanonicalTeamConfig,
    ExecutionRecord,
    ExecutionStatus,
    InteractionMode,
    InterventionAction,
    InterventionRecord,
    ParallelRemovalRecord,
    ParallelRemovalSafetyReport,
    ProtocolKind,
    RemovalStrategy,
    TaskSpec,
)


@dataclass(frozen=True)
class ParallelRemovalOutcome:
    """The evidence record and externally visible intervention decision."""

    record: ParallelRemovalRecord
    intervention: InterventionRecord


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


def _output_signature(team: CanonicalTeamConfig, role_id: str) -> tuple[object, ...]:
    role = next(role for role in team.roles if role.role_id == role_id)
    return tuple(
        (
            output.semantic_type,
            output.format,
            output.schema_ref,
            tuple(output.required_fields),
        )
        for output in role.outputs
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


def _manifest_matches(
    manifest: ExperimentManifest,
    baseline: ExecutionRecord,
    team: CanonicalTeamConfig,
    aggregator_identity: AggregatorIdentity,
) -> bool:
    expected_models = {agent.agent_id: agent.model_id for agent in team.agents}
    expected_prompts = {role.role_id: role.prompt_hash for role in team.roles}
    expected_contracts = {
        role.role_id: role_contract_hash(role.model_dump(mode="json"))
        for role in team.roles
    }
    expected_tool_ids = {
        tool_id for agent in team.agents for tool_id in agent.tool_ids
    }
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
        and manifest.mock == baseline.mock
    )


class ParallelRemovalRunner:
    """Replay aggregation after dropping exactly one frozen response."""

    def run(
        self,
        *,
        baseline: ExecutionRecord,
        task: TaskSpec,
        team: CanonicalTeamConfig,
        target_role_id: str,
        output_team_version: str,
        manifest: ExperimentManifest,
        aggregator: Aggregator,
        coverage_gap_detected: bool,
        joint_intervention_required: bool,
        contract_topology_sufficient: bool,
    ) -> ParallelRemovalOutcome:
        role_ids = team.execution_protocol.execution_order
        retained_ids = [role_id for role_id in role_ids if role_id != target_role_id]
        roles_by_id = {role.role_id: role for role in team.roles}
        target = roles_by_id.get(target_role_id)
        manifest_hash = canonical_json_hash(manifest.model_dump(mode="json"))
        aggregator_identity = AggregatorIdentity.model_validate(
            aggregator.identity.model_dump(mode="json")
        )

        required_edges = [
            edge
            for edge in team.edges
            if edge.required
            and target_role_id in {edge.source_role_id, edge.target_role_id}
        ]
        outgoing_required_edges = [
            edge
            for edge in required_edges
            if edge.source_role_id == target_role_id
        ]
        required_contract_dependencies = [
            dependency
            for role in team.roles
            for dependency in role.upstream_dependencies
            if dependency.required and dependency.role_id == target_role_id
        ]
        required_inputs = [
            input_spec
            for role in team.roles
            for input_spec in role.required_inputs
            if input_spec.producer_role_id == target_role_id
        ]
        target_is_unique_final_or_veto = False
        if target is not None and target.authority_level in {
            AuthorityLevel.FINAL,
            AuthorityLevel.VETO,
        }:
            same_authority = [
                role
                for role in team.roles
                if role.authority_level is target.authority_level
            ]
            target_is_unique_final_or_veto = len(same_authority) == 1

        homogeneous = False
        if target is not None and retained_ids:
            signatures = {_output_signature(team, role_id) for role_id in role_ids}
            homogeneous = len(signatures) == 1

        checks = {
            "baseline_record_valid": _baseline_valid(baseline, task, team),
            "manifest_matches": _manifest_matches(
                manifest,
                baseline,
                team,
                aggregator_identity,
            ),
            "parallel_protocol": (
                team.execution_protocol.kind is ProtocolKind.PARALLEL_INDEPENDENT
            ),
            "strategy_predeclared": (
                team.removal_protocol.strategy
                is RemovalStrategy.PARALLEL_AGGREGATION_REMOVAL
            ),
            "frozen_other_responses": team.removal_protocol.freeze_other_responses,
            "same_aggregation_protocol": (
                team.removal_protocol.reaggregate_with_same_protocol
                and (
                    aggregator_identity.aggregator_id
                    == team.execution_protocol.aggregation_protocol
                    or getattr(aggregator, "protocol_descriptor", None)
                    == team.execution_protocol.aggregation_protocol
                )
            ),
            "new_team_version": output_team_version != team.team_version,
            "target_exists": target is not None,
            "target_not_non_removable": (
                target_role_id not in team.removal_protocol.non_removable_role_ids
            ),
            "target_not_final_or_unique_veto": not target_is_unique_final_or_veto,
            "independent_execution": all(
                role.interaction_mode is InteractionMode.INDEPENDENT for role in team.roles
            ),
            "no_required_target_dependency": not (
                required_edges or required_contract_dependencies or required_inputs
            ),
            "no_exclusive_required_artifact": not (
                outgoing_required_edges
                or required_contract_dependencies
                or required_inputs
            ),
            "homogeneous_responses": homogeneous,
            "nonempty_retained_responses": bool(retained_ids),
            "variable_arity_aggregation": aggregator.accepts_variable_responses,
            "replayable_aggregation": None,
            "no_coverage_gap": not coverage_gap_detected,
            "no_compensation": not team.removal_protocol.compensation_message_allowed,
            "no_joint_intervention": not joint_intervention_required,
            "contract_topology_sufficient": contract_topology_sufficient,
            "other_responses_frozen": None,
            "no_roles_reexecuted": True,
            "removal_aggregation_succeeded": None,
        }

        baseline_snapshot: AggregationSnapshot | None = None
        replay_snapshot: AggregationSnapshot | None = None
        removal_snapshot: AggregationSnapshot | None = None
        preflight_names = {
            name
            for name in checks
            if name
            not in {
                "replayable_aggregation",
                "other_responses_frozen",
                "removal_aggregation_succeeded",
            }
        }
        if all(checks[name] is True for name in preflight_names):
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
                baseline=baseline,
                task=task,
                role_ids=role_ids,
                aggregator=aggregator,
            )
            checks["replayable_aggregation"] = (
                replay_snapshot is not None
                and replay_snapshot.final_output_hash == baseline_snapshot.final_output_hash
            )
            if checks["replayable_aggregation"]:
                removal_snapshot = self._aggregate_snapshot(
                    kind=AggregationRunKind.PARALLEL_REMOVAL,
                    baseline=baseline,
                    task=task,
                    role_ids=retained_ids,
                    aggregator=aggregator,
                )
                checks["removal_aggregation_succeeded"] = removal_snapshot is not None
                checks["other_responses_frozen"] = (
                    removal_snapshot is not None
                    and removal_snapshot.role_output_hashes
                    == {
                        role_id: baseline.role_output_hashes[role_id]
                        for role_id in retained_ids
                    }
                )

        failed_checks = [name for name, passed in checks.items() if passed is False]
        not_run_checks = [name for name, passed in checks.items() if passed is None]
        valid = all(passed is True for passed in checks.values())
        safety_payload: dict[str, object] = {
            **checks,
            "valid": valid,
            "invalid_reasons": failed_checks,
            "not_run_checks": not_run_checks,
        }
        safety = ParallelRemovalSafetyReport.model_validate(
            safety_payload,
        )
        identity_payload = {
            "baseline_run_id": baseline.run_id,
            "target_role_id": target_role_id,
            "manifest_hash": manifest_hash,
            "aggregator": aggregator_identity.model_dump(mode="json"),
        }
        intervention_id = _stable_id("intervention", identity_payload)
        record_id = _stable_id("parallel-removal", identity_payload)
        effective_output_version = output_team_version if valid else team.team_version
        record = ParallelRemovalRecord(
            record_id=record_id,
            intervention_id=intervention_id,
            experiment_id=baseline.experiment_id,
            baseline_run_id=baseline.run_id,
            task_id=task.task_id,
            team_id=team.team_id,
            input_team_version=team.team_version,
            output_team_version=effective_output_version,
            protocol_id=team.execution_protocol.protocol_id,
            removal_protocol_id=team.removal_protocol.removal_protocol_id,
            target_role_id=target_role_id,
            seeds=baseline.seeds,
            manifest_hash=manifest_hash,
            aggregator=aggregator_identity,
            role_metrics=baseline.role_metrics,
            baseline_aggregation=baseline_snapshot,
            replay_aggregation=replay_snapshot,
            removal_aggregation=removal_snapshot,
            reused_role_ids=retained_ids if valid else [],
            reexecuted_role_ids=[],
            safety=safety,
            mock=baseline.mock,
            created_at=datetime.now(UTC),
        )
        intervention = InterventionRecord(
            intervention_id=intervention_id,
            experiment_id=baseline.experiment_id,
            baseline_run_id=baseline.run_id,
            target_role_id=target_role_id,
            action=InterventionAction.REMOVE if valid else InterventionAction.KEEP,
            input_team_version=team.team_version,
            output_team_version=effective_output_version,
            removal_safe=valid,
            coverage_gap_detected=coverage_gap_detected,
            joint_intervention_required=joint_intervention_required,
            abstained=not valid,
            reason=failed_checks,
            created_at=record.created_at,
        )
        return ParallelRemovalOutcome(record=record, intervention=intervention)

    @staticmethod
    def _aggregate_snapshot(
        *,
        kind: AggregationRunKind,
        baseline: ExecutionRecord,
        task: TaskSpec,
        role_ids: list[str],
        aggregator: Aggregator,
    ) -> AggregationSnapshot | None:
        try:
            responses = tuple(
                FrozenRoleResponse(
                    role_id=role_id,
                    output=isolated_json_copy(baseline.role_outputs[role_id]),
                    output_hash=baseline.role_output_hashes[role_id],
                )
                for role_id in role_ids
            )
            final_output = aggregator.aggregate(
                AggregationRequest(
                    task=isolated_task_copy(task),
                    responses=responses,
                    aggregation_seed=baseline.seeds.aggregation_seed,
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
                "baseline_run_id": baseline.run_id,
                "role_ids": role_ids,
                "hashes": {
                    role_id: baseline.role_output_hashes[role_id] for role_id in role_ids
                },
                "aggregation_seed": baseline.seeds.aggregation_seed,
                "final_output": final_output,
            },
        )
        return _snapshot(
            run_id=run_id,
            kind=kind,
            role_ids=role_ids,
            hashes=baseline.role_output_hashes,
            aggregation_seed=baseline.seeds.aggregation_seed,
            final_output=final_output,
        )
