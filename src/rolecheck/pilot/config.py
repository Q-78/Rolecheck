"""Frozen Prompt, Role Contract, team, protocol, and server identities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from rolecheck.hashing import canonical_json_hash
from rolecheck.normalization import NormalizationResult, RoleContractNormalizer
from rolecheck.schemas import (
    AgentInstance,
    AuthorityLevel,
    CanonicalTeamConfig,
    ExecutionProtocol,
    FormatStrictness,
    InteractionMode,
    ProtocolKind,
    RemovalProtocol,
    RemovalStrategy,
    ResourceLimits,
    RuntimeEnvironmentIdentity,
    Visibility,
)

PILOT_VERSION: Final = "v0.1"
PILOT_SOURCE_INITIALIZER: Final = "rolecheck.server_pilot.v0.1"
PILOT_TEAM_ID: Final = "rolecheck.mmlu_pro.parallel_three_role"
PILOT_MODEL_ID: Final = "Qwen/Qwen3-8B"
PILOT_MODEL_REVISION: Final = "b968826d9c46dd6066d109eabc6255188de91218"
PILOT_MODEL_ASSIGNMENT_ID: Final = f"{PILOT_MODEL_ID}@{PILOT_MODEL_REVISION}"

PILOT_SUBSET_SPLIT_SEED: Final = 2026080301
PILOT_EXPERIMENT_SEED: Final = 2026080302

PILOT_GENERATION_CONFIG: Final[Mapping[str, object]] = MappingProxyType(
    {
        "enable_thinking": True,
        "do_sample": True,
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "max_new_tokens": 4096,
    }
)


@dataclass(frozen=True, slots=True)
class _RoleDefinition:
    role_id: str
    role_name: str
    goal: str
    responsibilities: tuple[str, ...]
    required_capabilities: tuple[str, ...]


_COMMON_SUCCESS_CRITERIA = (
    "Reason independently from the supplied question and ordered options.",
    "End the final visible response with exactly one line in the form Answer: <LETTER>.",
    "Select only a letter corresponding to one of the supplied ordered options.",
)
_COMMON_NON_GOALS = (
    "Do not aggregate or inspect another role's response.",
    "Do not evaluate correctness or predict any role's keep value.",
)
_COMMON_PROHIBITED_BEHAVIORS = (
    "Do not use tools, network access, external files, or hidden answer keys.",
    "Do not request or use gold answers, reference rationales, traces, or other role outputs.",
    "Do not add, remove, reorder, translate, or rewrite the supplied answer options.",
)
_COMMON_PRIORITY_RULES = (
    "Preserve the supplied question and option ordering.",
    "Prefer an explicit invalid response over fabricating unavailable information.",
    "Follow the terminal answer format after completing the independent analysis.",
)

_ROLE_DEFINITIONS: Final = (
    _RoleDefinition(
        role_id="domain_analyst",
        role_name="Domain Analyst",
        goal="Select the best answer using relevant domain knowledge and explicit assumptions.",
        responsibilities=(
            "Analyze the supplied question and ordered options independently.",
            "Apply relevant domain knowledge and state assumptions used in the analysis.",
            "Produce reasoning followed by one terminal answer-letter line.",
        ),
        required_capabilities=("domain reasoning", "assumption tracking"),
    ),
    _RoleDefinition(
        role_id="elimination_analyst",
        role_name="Elimination Analyst",
        goal="Select the best answer by testing and eliminating the supplied options.",
        responsibilities=(
            "Analyze the supplied question and ordered options independently.",
            "Test candidate options and eliminate options that conflict with the question.",
            "Produce elimination reasoning followed by one terminal answer-letter line.",
        ),
        required_capabilities=("option comparison", "constraint checking"),
    ),
    _RoleDefinition(
        role_id="verification_analyst",
        role_name="Verification Analyst",
        goal=(
            "Select the best answer after independently checking logical, numerical, "
            "and wording consistency."
        ),
        responsibilities=(
            "Analyze the supplied question and ordered options independently.",
            "Check logical, numerical, and wording consistency before selecting an option.",
            "Produce verification reasoning followed by one terminal answer-letter line.",
        ),
        required_capabilities=("logical verification", "numerical consistency checking"),
    ),
)


def _render_raw_prompt(definition: _RoleDefinition) -> str:
    sections = [
        f"You are the {definition.role_name}.",
        "",
        "# Goal",
        definition.goal,
        "",
        "# Responsibilities",
        *(f"- {item}" for item in definition.responsibilities),
        "",
        "# Success Criteria",
        *(f"- {item}" for item in _COMMON_SUCCESS_CRITERIA),
        "",
        "# Non-goals",
        *(f"- {item}" for item in _COMMON_NON_GOALS),
        "",
        "# Prohibited Behaviors",
        *(f"- {item}" for item in _COMMON_PROHIBITED_BEHAVIORS),
        "",
        "# Priority Rules",
        *(f"- {item}" for item in _COMMON_PRIORITY_RULES),
    ]
    return "\n".join(sections)


def _explicit_fields(definition: _RoleDefinition) -> dict[str, Any]:
    return {
        "goal": definition.goal,
        "responsibilities": list(definition.responsibilities),
        "success_criteria": list(_COMMON_SUCCESS_CRITERIA),
        "non_goals": list(_COMMON_NON_GOALS),
        "prohibited_behaviors": list(_COMMON_PROHIBITED_BEHAVIORS),
        "priority_rules": list(_COMMON_PRIORITY_RULES),
        "required_inputs": [
            {
                "name": "task",
                "semantic_type": "multiple_choice_task",
                "required": True,
                "format": "plain_text",
                "description": "Current question and ordered answer options only.",
            }
        ],
        "optional_inputs": [],
        "input_visibility": Visibility.GLOBAL,
        "context_assumptions": [
            "The supplied option order is authoritative for answer-letter mapping."
        ],
        "outputs": [
            {
                "name": "independent_answer",
                "semantic_type": "multiple_choice_reasoning_and_answer",
                "consumers": ["deterministic_majority_aggregator"],
                "format": "plain_text",
                "required_fields": ["reasoning", "terminal_answer_letter"],
                "description": (
                    "Independent reasoning whose final visible line is exactly Answer: <LETTER>."
                ),
            }
        ],
        "output_visibility": Visibility.SHARED,
        "failure_output": None,
        "format_strictness": FormatStrictness.STRICT,
        "authority_level": AuthorityLevel.VOTING,
        "can_override": [],
        "requires_approval_from": [],
        "decision_scope": ["independent answer-letter vote"],
        "conflict_resolution_rule": None,
        "upstream_dependencies": [],
        "downstream_consumers": ["deterministic_majority_aggregator"],
        "interaction_mode": InteractionMode.INDEPENDENT,
        "max_interaction_rounds": 1,
        "termination_signal": "terminal Answer: <LETTER> line",
        "handoff_conditions": [],
        "required_capabilities": list(definition.required_capabilities),
        "resource_limits": ResourceLimits(
            max_tokens=4096,
            max_latency_ms=180_000,
            max_tool_calls=0,
        ),
        "parent_role_version": None,
    }


def build_pilot_normalizations() -> tuple[NormalizationResult, ...]:
    """Normalize the three reviewed definitions without inferred role facts."""

    normalizer = RoleContractNormalizer()
    results = []
    for definition in _ROLE_DEFINITIONS:
        result = normalizer.normalize(
            role_id=definition.role_id,
            role_name=definition.role_name,
            role_version=PILOT_VERSION,
            source_initializer=PILOT_SOURCE_INITIALIZER,
            source_node_id=definition.role_id,
            raw_prompt=_render_raw_prompt(definition),
            explicit_fields=_explicit_fields(definition),
        )
        if result.contract is None:
            raise ValueError(f"Pilot role did not normalize: {definition.role_id}")
        expected_unknown = {
            "failure_output",
            "conflict_resolution_rule",
            "parent_role_version",
        }
        if (
            result.missing_fields
            or set(result.unknown_fields) != expected_unknown
            or result.conflicting_fields
        ):
            raise ValueError(f"Pilot role normalization is incomplete: {definition.role_id}")
        results.append(result)
    return tuple(results)


def build_pilot_team() -> CanonicalTeamConfig:
    """Return a new validated copy of the frozen three-role Pilot team."""

    roles = []
    for result in build_pilot_normalizations():
        if result.contract is None:  # pragma: no cover - guarded above
            raise AssertionError("normalization unexpectedly lacked a contract")
        roles.append(result.contract)
    role_ids = [role.role_id for role in roles]
    agents = [
        AgentInstance(
            agent_id=f"{role_id}.qwen3_8b",
            role_id=role_id,
            model_id=PILOT_MODEL_ASSIGNMENT_ID,
            sampling_config=dict(PILOT_GENERATION_CONFIG),
            resource_limits=ResourceLimits(
                max_tokens=4096,
                max_latency_ms=180_000,
                max_tool_calls=0,
            ),
            runtime_metadata={
                "model_id": PILOT_MODEL_ID,
                "model_revision": PILOT_MODEL_REVISION,
            },
        )
        for role_id in role_ids
    ]
    return CanonicalTeamConfig(
        team_id=PILOT_TEAM_ID,
        team_version=PILOT_VERSION,
        roles=roles,
        agents=agents,
        edges=[],
        execution_protocol=ExecutionProtocol(
            protocol_id="rolecheck.parallel_independent.single_round.v0.1",
            kind=ProtocolKind.PARALLEL_INDEPENDENT,
            communication_protocol="no inter-role communication",
            aggregation_protocol=(
                "parse terminal answer letters; strict majority; lexicographically "
                "smallest tied leader"
            ),
            termination_protocol="one fixed round with no answer-quality retry",
            execution_order=role_ids,
            fixed_rounds=1,
            protocol_version=PILOT_VERSION,
        ),
        removal_protocol=RemovalProtocol(
            removal_protocol_id="rolecheck.parallel_aggregation_removal.v0.1",
            strategy=RemovalStrategy.PARALLEL_AGGREGATION_REMOVAL,
            protocol_version=PILOT_VERSION,
            freeze_other_responses=True,
            reaggregate_with_same_protocol=True,
        ),
        resource_constraints=ResourceLimits(
            max_tokens=12_288,
            max_latency_ms=540_000,
            max_tool_calls=0,
        ),
        source_initializer=PILOT_SOURCE_INITIALIZER,
    )


def pilot_team_hash() -> str:
    return canonical_json_hash(build_pilot_team().model_dump(mode="json"))


def pilot_runtime_environment() -> RuntimeEnvironmentIdentity:
    """Return the audited Gate 2-A server identity captured outside Git."""

    return RuntimeEnvironmentIdentity(
        model_id=PILOT_MODEL_ID,
        model_revision=PILOT_MODEL_REVISION,
        model_assignment_id=PILOT_MODEL_ASSIGNMENT_ID,
        model_artifact_manifest_hash=(
            "sha256:866aaf6607fe6c4bc59ac58d599710e97555710114c1925c99ed392d452862a1"
        ),
        tokenizer_hash=("sha256:aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492daa4"),
        generation_config_hash=(
            "sha256:2325da0f15bb848e018c5ae071b7943332e9f871d6b60e2ed22ca97d4cb993d2"
        ),
        dependency_lock_hash=(
            "sha256:9e8ce3b71f339a891420046befbdaf3ab8c370a06a37e28e578dcba125bddf6c"
        ),
        hardware_inventory_hash=(
            "sha256:89d3a5849c7f6c6dcfd1802e95ee2ebbd77ff804ca9ed0c873346c7d1363b9f4"
        ),
    )
