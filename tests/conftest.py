from __future__ import annotations

from collections.abc import Callable

import pytest

from rolecheck.hashing import sha256_text
from rolecheck.schemas import (
    AgentInstance,
    CanonicalTeamConfig,
    ExecutionProtocol,
    OutputSpec,
    ProtocolKind,
    RemovalProtocol,
    RemovalStrategy,
    RoleContract,
)


@pytest.fixture
def role_factory() -> Callable[..., RoleContract]:
    def make_role(
        role_id: str = "solver",
        *,
        role_version: str = "v1",
        parent_role_version: str | None = None,
    ) -> RoleContract:
        prompt = f"Act as {role_id} and produce a structured answer."
        return RoleContract(
            role_id=role_id,
            role_name=role_id.title(),
            role_version=role_version,
            source_initializer="manual-test",
            raw_prompt=prompt,
            prompt_hash=sha256_text(prompt),
            goal=f"Fulfil the {role_id} responsibility.",
            responsibilities=[f"Produce the {role_id} artifact."],
            outputs=[
                OutputSpec(
                    name=f"{role_id}_output",
                    semantic_type="test_artifact",
                    consumers=[],
                )
            ],
            parent_role_version=parent_role_version,
        )

    return make_role


@pytest.fixture
def team_factory(
    role_factory: Callable[..., RoleContract],
) -> Callable[[], CanonicalTeamConfig]:
    def make_team() -> CanonicalTeamConfig:
        solver = role_factory("solver")
        critic = role_factory("critic")
        return CanonicalTeamConfig(
            team_id="team-test",
            roles=[solver, critic],
            agents=[
                AgentInstance(agent_id="agent-solver", role_id="solver", model_id="mock-model"),
                AgentInstance(agent_id="agent-critic", role_id="critic", model_id="mock-model"),
            ],
            execution_protocol=ExecutionProtocol(
                protocol_id="parallel-v1",
                kind=ProtocolKind.PARALLEL_INDEPENDENT,
                communication_protocol="independent",
                aggregation_protocol="fixed-mock-aggregation",
                termination_protocol="fixed-rounds",
                execution_order=["solver", "critic"],
                fixed_rounds=1,
            ),
            removal_protocol=RemovalProtocol(
                removal_protocol_id="parallel-removal-v1",
                strategy=RemovalStrategy.PARALLEL_AGGREGATION_REMOVAL,
                freeze_other_responses=True,
                reaggregate_with_same_protocol=True,
                non_removable_role_ids=[],
            ),
            source_initializer="manual-test",
        )

    return make_team
