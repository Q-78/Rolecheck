"""Deterministic mock runtime.

The mock runtime validates plumbing and reproducibility only. It never calls a
language model and must not be used to support empirical claims.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rolecheck.config import MockRuntimeConfig
from rolecheck.hashing import canonical_json_hash, derive_seed, sha256_text
from rolecheck.schemas import (
    CanonicalTeamConfig,
    ExecutionRecord,
    ExecutionStatus,
    SeedBundle,
    TaskSpec,
)


class MockRuntime:
    """Create deterministic placeholder outputs for each configured role."""

    def __init__(self, config: MockRuntimeConfig) -> None:
        if not config.enabled:
            raise ValueError("mock runtime is disabled by configuration")
        self._config = config

    def run(
        self,
        *,
        task: TaskSpec,
        team: CanonicalTeamConfig,
        experiment_id: str,
        experiment_seed: int,
    ) -> ExecutionRecord:
        role_seeds = {
            role.role_id: derive_seed(experiment_seed, "role", role.role_id) for role in team.roles
        }
        task_seed = derive_seed(experiment_seed, "task", task.task_id)
        aggregation_seed = derive_seed(experiment_seed, "aggregation", team.team_id)

        role_outputs: dict[str, object] = {}
        role_output_hashes: dict[str, str] = {}
        for role in team.roles:
            output = {
                "mock": True,
                "task_id": task.task_id,
                "team_id": team.team_id,
                "role_id": role.role_id,
                "role_version": role.role_version,
                "seed": role_seeds[role.role_id],
                "message": "placeholder output; no model was called",
            }
            role_outputs[role.role_id] = output
            role_output_hashes[role.role_id] = canonical_json_hash(output)

        final_output = {
            "mock": True,
            "ordered_roles": team.execution_protocol.execution_order,
            "role_output_hashes": role_output_hashes,
        }
        run_fingerprint = canonical_json_hash(
            {
                "experiment_id": experiment_id,
                "task_id": task.task_id,
                "team_id": team.team_id,
                "team_version": team.team_version,
                "seed": experiment_seed,
                "outputs": role_output_hashes,
            }
        ).removeprefix("sha256:")[:16]

        started_at = datetime.now(UTC)
        latency_ms = self._config.synthetic_latency_ms_per_role * len(team.roles)
        finished_at = started_at + timedelta(milliseconds=latency_ms)
        token_cost = float(self._config.synthetic_tokens_per_role * len(team.roles))

        return ExecutionRecord(
            run_id=f"mock-{run_fingerprint}",
            experiment_id=experiment_id,
            task_id=task.task_id,
            team_id=team.team_id,
            team_version=team.team_version,
            protocol_id=team.execution_protocol.protocol_id,
            removal_protocol_id=team.removal_protocol.removal_protocol_id,
            started_at=started_at,
            finished_at=finished_at,
            status=ExecutionStatus.SUCCEEDED,
            seeds=SeedBundle(
                experiment_seed=experiment_seed,
                task_seed=task_seed,
                role_seeds=role_seeds,
                aggregation_seed=aggregation_seed,
            ),
            role_outputs=role_outputs,
            role_output_hashes=role_output_hashes,
            final_output=final_output,
            utility=None,
            token_cost=token_cost,
            latency_ms=latency_ms,
            mock=True,
            errors=[],
        )

    @property
    def runtime_id(self) -> str:
        return self._config.runtime_id

    @staticmethod
    def warning_hash() -> str:
        return sha256_text("MOCK_RUNTIME_NO_EMPIRICAL_CLAIMS")
