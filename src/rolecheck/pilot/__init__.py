"""Reviewed, bounded configuration and local interfaces for Server Pilot v0.1."""

from rolecheck.pilot.aggregation import DeterministicMajorityAggregator
from rolecheck.pilot.config import (
    PILOT_EXPERIMENT_SEED,
    PILOT_GENERATION_CONFIG,
    PILOT_MODEL_ASSIGNMENT_ID,
    PILOT_MODEL_ID,
    PILOT_MODEL_REVISION,
    PILOT_SUBSET_SPLIT_SEED,
    build_pilot_normalizations,
    build_pilot_team,
    pilot_runtime_environment,
    pilot_team_hash,
)
from rolecheck.pilot.execution import (
    LocalGenerationEngine,
    PilotExecutionBackend,
    RoleGenerationRequest,
    answer_parser_identity,
    render_role_prompt,
    required_generation_engine_identity,
)
from rolecheck.pilot.models import (
    AnswerParseResult,
    AnswerParseStatus,
    MajorityVoteResult,
    ParsedModelText,
    PilotRoleOutput,
    RawGeneration,
    RenderedRolePrompt,
)
from rolecheck.pilot.parsing import parse_terminal_answer, split_model_text

__all__ = [
    "PILOT_EXPERIMENT_SEED",
    "PILOT_GENERATION_CONFIG",
    "PILOT_MODEL_ASSIGNMENT_ID",
    "PILOT_MODEL_ID",
    "PILOT_MODEL_REVISION",
    "PILOT_SUBSET_SPLIT_SEED",
    "AnswerParseResult",
    "AnswerParseStatus",
    "DeterministicMajorityAggregator",
    "LocalGenerationEngine",
    "MajorityVoteResult",
    "ParsedModelText",
    "PilotExecutionBackend",
    "PilotRoleOutput",
    "RawGeneration",
    "RenderedRolePrompt",
    "RoleGenerationRequest",
    "answer_parser_identity",
    "build_pilot_normalizations",
    "build_pilot_team",
    "parse_terminal_answer",
    "pilot_runtime_environment",
    "pilot_team_hash",
    "render_role_prompt",
    "required_generation_engine_identity",
    "split_model_text",
]
