"""Dependency-injected Pilot execution orchestration without model imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from rolecheck.hashing import canonical_json_hash, derive_seed
from rolecheck.pilot.aggregation import DeterministicMajorityAggregator
from rolecheck.pilot.config import (
    PILOT_GENERATION_CONFIG,
    PILOT_MODEL_ASSIGNMENT_ID,
    PILOT_TEAM_ID,
    PILOT_VERSION,
    build_pilot_team,
    pilot_runtime_environment,
    pilot_team_hash,
)
from rolecheck.pilot.models import (
    AnswerParseResult,
    AnswerParseStatus,
    PilotRoleOutput,
    RawGeneration,
    RenderedRolePrompt,
)
from rolecheck.pilot.parsing import parse_terminal_answer, split_model_text
from rolecheck.runtime.adapter import RuntimeExecutionRequest, SelfHostedExecutionBackend
from rolecheck.runtime.interfaces import (
    AggregationRequest,
    FrozenRoleResponse,
    isolated_role_copy,
    isolated_task_copy,
)
from rolecheck.schemas import (
    ExecutionRecord,
    ExecutionStatus,
    RoleContract,
    RoleExecutionMetrics,
    RuntimeAdapterIdentity,
    SeedBundle,
    TaskSpec,
)

_PROMPT_RENDERER_ID = "rolecheck.pilot.mmlu_pro_prompt_renderer"
_PROMPT_RENDERER_VERSION = "v0.1"


def answer_parser_identity() -> RuntimeAdapterIdentity:
    """Identity for deterministic thinking separation and answer extraction."""

    return RuntimeAdapterIdentity(
        runtime_id="rolecheck.pilot.answer_parser",
        runtime_version=PILOT_VERSION,
        config_hash=canonical_json_hash(
            {
                "thinking_markers": ["<think>", "</think>"],
                "thinking_marker_policy": "zero_or_one_balanced_block_v0.1",
                "terminal_answer_pattern": r"(?:^|\n)Answer: ([A-J])[ \t]*\Z",
                "option_range": [2, 10],
                "repair_or_retry": False,
            }
        ),
    )


def required_generation_engine_identity() -> RuntimeAdapterIdentity:
    """Identity a future Gate 4 Transformers engine must expose exactly."""

    environment = pilot_runtime_environment()
    return RuntimeAdapterIdentity(
        runtime_id="rolecheck.transformers.qwen3_8b.single_gpu",
        runtime_version=PILOT_VERSION,
        config_hash=canonical_json_hash(
            {
                "interface_contract": "two_message_chat_to_raw_generation_v0.1",
                "model_assignment_id": PILOT_MODEL_ASSIGNMENT_ID,
                "model_artifact_manifest_hash": environment.model_artifact_manifest_hash,
                "tokenizer_hash": environment.tokenizer_hash,
                "generation_config_file_hash": environment.generation_config_hash,
                "generation_config": dict(PILOT_GENERATION_CONFIG),
                "dtype": "bfloat16",
                "rope_scaling": None,
                "concurrent_role_generations": 1,
                "chat_template_applied_by_engine": True,
                "cuda_visible_devices": "0",
                "model_processes": 1,
                "concurrent_tasks": 1,
                "tensor_parallelism": False,
                "data_parallelism": False,
                "quantization": False,
                "cpu_offload": False,
                "model_compilation": False,
                "network_during_inference": False,
            }
        ),
    )


@dataclass(frozen=True)
class RoleGenerationRequest:
    """One isolated role request passed to the injected generation engine."""

    task: TaskSpec
    role: RoleContract
    prompt: RenderedRolePrompt
    role_seed: int
    generation_config: dict[str, object]


class LocalGenerationEngine(Protocol):
    """Gate 4 injection point; this module never imports or loads Transformers."""

    @property
    def identity(self) -> RuntimeAdapterIdentity: ...

    def generate(self, request: RoleGenerationRequest) -> RawGeneration: ...


def _mmlu_options(task: TaskSpec) -> tuple[str, ...]:
    if task.task_type != "multiple_choice":
        raise ValueError("Pilot execution requires a multiple-choice task")
    options = task.public_metadata.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 10:
        raise ValueError("Pilot task requires between 2 and 10 ordered options")
    if any(not isinstance(option, str) or not option.strip() for option in options):
        raise ValueError("Pilot task options must be non-empty strings")
    return tuple(options)


def render_role_prompt(role: RoleContract, task: TaskSpec) -> RenderedRolePrompt:
    """Render frozen system/user messages with label-free current-task content."""

    options = _mmlu_options(task)
    option_lines = [f"{chr(ord('A') + index)}. {option}" for index, option in enumerate(options)]
    user_prompt = "\n".join(
        [
            "# Current Task",
            task.task_text,
            "",
            "# Ordered Options",
            *option_lines,
            "",
            "# Required Response",
            "Reason independently. End the final visible response with exactly:",
            "Answer: <LETTER>",
        ]
    )
    messages = [
        {"role": "system", "content": role.raw_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return RenderedRolePrompt(
        system_prompt=role.raw_prompt,
        user_prompt=user_prompt,
        messages_hash=canonical_json_hash(messages),
    )


class PilotExecutionBackend(SelfHostedExecutionBackend):
    """Execute the frozen team through an injected, identity-checked engine."""

    def __init__(
        self,
        *,
        generation_engine: LocalGenerationEngine,
        aggregator: DeterministicMajorityAggregator,
    ) -> None:
        required_engine = required_generation_engine_identity()
        supplied_engine = RuntimeAdapterIdentity.model_validate(
            generation_engine.identity.model_dump(mode="json")
        )
        if supplied_engine != required_engine:
            raise ValueError("generation engine does not match the frozen Pilot identity")
        self._generation_engine = generation_engine
        self._generation_engine_identity = supplied_engine
        self._aggregator = aggregator
        self._aggregator_identity = aggregator.identity
        self._identity = RuntimeAdapterIdentity(
            runtime_id="rolecheck.pilot.execution_backend",
            runtime_version=PILOT_VERSION,
            config_hash=canonical_json_hash(
                {
                    "team_id": PILOT_TEAM_ID,
                    "team_hash": pilot_team_hash(),
                    "prompt_renderer_id": _PROMPT_RENDERER_ID,
                    "prompt_renderer_version": _PROMPT_RENDERER_VERSION,
                    "prompt_renderer_policy": ("system_role_prompt_plus_label_free_user_task_v0.1"),
                    "answer_parser": answer_parser_identity().model_dump(mode="json"),
                    "generation_engine": supplied_engine.model_dump(mode="json"),
                    "generation_config": dict(PILOT_GENERATION_CONFIG),
                    "aggregator": self._aggregator_identity.model_dump(mode="json"),
                    "execution_order": [
                        "domain_analyst",
                        "elimination_analyst",
                        "verification_analyst",
                    ],
                    "role_outputs_visible_between_roles": False,
                    "answer_quality_retries": 0,
                }
            ),
        )

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        return self._identity.model_copy(deep=True)

    def execute(self, request: RuntimeExecutionRequest) -> ExecutionRecord:
        if self._aggregator.identity != self._aggregator_identity:
            raise ValueError("aggregator identity changed before execution")
        team = request.team
        if canonical_json_hash(team.model_dump(mode="json")) != pilot_team_hash():
            raise ValueError("execution request does not contain the frozen Pilot team")
        if team != build_pilot_team():
            raise ValueError("execution request Pilot team differs despite its hash")
        task = isolated_task_copy(request.task)
        option_count = len(_mmlu_options(task))
        started_at = datetime.now(UTC)
        role_by_id = {role.role_id: role for role in team.roles}
        role_outputs: dict[str, object] = {}
        role_output_hashes: dict[str, str] = {}
        role_metrics: dict[str, RoleExecutionMetrics] = {}

        for role_id in team.execution_protocol.execution_order:
            if self._current_engine_identity() != self._generation_engine_identity:
                raise ValueError("generation engine identity changed before execution")
            role = isolated_role_copy(role_by_id[role_id])
            rendered_prompt = render_role_prompt(role, task)
            role_seed = derive_seed(request.experiment_manifest.seed, "role", role_id)
            generation = RawGeneration.model_validate(
                self._generation_engine.generate(
                    RoleGenerationRequest(
                        task=isolated_task_copy(task),
                        role=isolated_role_copy(role),
                        prompt=rendered_prompt,
                        role_seed=role_seed,
                        generation_config=dict(PILOT_GENERATION_CONFIG),
                    )
                ).model_dump(mode="json")
            )
            if self._current_engine_identity() != self._generation_engine_identity:
                raise ValueError("generation engine identity changed during execution")
            parsed = split_model_text(generation.raw_decoded_output)
            if parsed.structure_valid:
                answer = parse_terminal_answer(
                    parsed.final_content,
                    option_count=option_count,
                )
            else:
                answer = AnswerParseResult(
                    final_content_hash=canonical_json_hash(parsed.final_content),
                    option_count=option_count,
                    status=AnswerParseStatus.INVALID,
                    invalid_reason=f"invalid_model_text:{parsed.invalid_reason}",
                )
            role_output = PilotRoleOutput(
                role_id=role_id,
                role_seed=role_seed,
                rendered_prompt_hash=rendered_prompt.messages_hash,
                raw_token_ids=list(generation.raw_token_ids),
                raw_decoded_output=generation.raw_decoded_output,
                raw_output_hash=canonical_json_hash(generation.raw_decoded_output),
                parsed_reasoning=parsed.reasoning,
                parsed_final_content=parsed.final_content,
                answer_parse=answer,
                input_token_count=generation.input_token_count,
                output_token_count=generation.output_token_count,
                latency_ms=generation.latency_ms,
            )
            dumped = role_output.model_dump(mode="json")
            role_outputs[role_id] = dumped
            role_output_hashes[role_id] = canonical_json_hash(dumped)
            role_metrics[role_id] = RoleExecutionMetrics(
                token_cost=float(generation.input_token_count + generation.output_token_count),
                latency_ms=generation.latency_ms,
            )

        aggregation_seed = derive_seed(
            request.experiment_manifest.seed,
            "aggregation",
            team.team_id,
        )
        responses = tuple(
            FrozenRoleResponse(
                role_id=role_id,
                output=role_outputs[role_id],
                output_hash=role_output_hashes[role_id],
            )
            for role_id in team.execution_protocol.execution_order
        )
        if self._aggregator.identity != self._aggregator_identity:
            raise ValueError("aggregator identity changed before aggregation")
        final_output = self._aggregator.aggregate(
            AggregationRequest(
                task=isolated_task_copy(task),
                responses=responses,
                aggregation_seed=aggregation_seed,
            )
        )
        if self._aggregator.identity != self._aggregator_identity:
            raise ValueError("aggregator identity changed during aggregation")
        finished_at = datetime.now(UTC)
        seeds = SeedBundle(
            experiment_seed=request.experiment_manifest.seed,
            task_seed=derive_seed(
                request.experiment_manifest.seed,
                "task",
                task.task_id,
            ),
            role_seeds={
                role_id: derive_seed(
                    request.experiment_manifest.seed,
                    "role",
                    role_id,
                )
                for role_id in team.execution_protocol.execution_order
            },
            aggregation_seed=aggregation_seed,
        )
        return ExecutionRecord(
            run_id=(
                "pilot-"
                + canonical_json_hash(
                    {
                        "experiment_id": request.experiment_manifest.experiment_id,
                        "task_id": task.task_id,
                        "team_hash": pilot_team_hash(),
                        "backend": self.identity.model_dump(mode="json"),
                        "seeds": seeds.model_dump(mode="json"),
                    }
                ).removeprefix("sha256:")[:24]
            ),
            experiment_id=request.experiment_manifest.experiment_id,
            task_id=task.task_id,
            team_id=team.team_id,
            team_version=team.team_version,
            protocol_id=team.execution_protocol.protocol_id,
            removal_protocol_id=team.removal_protocol.removal_protocol_id,
            started_at=started_at,
            finished_at=finished_at,
            status=ExecutionStatus.SUCCEEDED,
            seeds=seeds,
            role_outputs=role_outputs,
            role_output_hashes=role_output_hashes,
            role_metrics=role_metrics,
            final_output=final_output,
            token_cost=sum(metric.token_cost for metric in role_metrics.values()),
            latency_ms=sum(metric.latency_ms for metric in role_metrics.values()),
            mock=False,
        )

    def _current_engine_identity(self) -> RuntimeAdapterIdentity:
        return RuntimeAdapterIdentity.model_validate(
            self._generation_engine.identity.model_dump(mode="json")
        )
