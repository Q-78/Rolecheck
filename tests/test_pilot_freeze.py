from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from pydantic import ValidationError

from rolecheck.benchmark import create_task_split_manifest
from rolecheck.benchmark.mmlu_pro import (
    MMLU_PRO_DATASET_ID,
    MMLU_PRO_REVISION,
    MMLUProBenchmarkAdapter,
    MMLUProTaskRecord,
)
from rolecheck.hashing import canonical_json_hash, role_contract_hash
from rolecheck.manifest import create_manifest
from rolecheck.pilot import (
    PILOT_EXPERIMENT_SEED,
    PILOT_GENERATION_CONFIG,
    PILOT_MODEL_ASSIGNMENT_ID,
    PILOT_SUBSET_SPLIT_SEED,
    AnswerParseStatus,
    DeterministicMajorityAggregator,
    MajorityVoteResult,
    PilotExecutionBackend,
    PilotRoleOutput,
    RawGeneration,
    RenderedRolePrompt,
    RoleGenerationRequest,
    answer_parser_identity,
    build_pilot_normalizations,
    build_pilot_team,
    parse_terminal_answer,
    pilot_runtime_environment,
    pilot_team_hash,
    render_role_prompt,
    required_generation_engine_identity,
    split_model_text,
)
from rolecheck.runtime import (
    AggregationRequest,
    FrozenRoleResponse,
    RuntimeExecutionRequest,
    SelfHostedRuntimeAdapter,
)
from rolecheck.schemas import (
    AggregatorIdentity,
    EvidenceClass,
    InteractionMode,
    ProtocolKind,
    RemovalStrategy,
    RuntimeAdapterIdentity,
    SourceType,
)


class FakeGenerationEngine:
    def __init__(self, outputs: Mapping[str, str]) -> None:
        self.outputs = dict(outputs)
        self.requests: list[RoleGenerationRequest] = []
        self._identity = required_generation_engine_identity()

    @property
    def identity(self) -> RuntimeAdapterIdentity:
        return self._identity.model_copy(deep=True)

    def generate(self, request: RoleGenerationRequest) -> RawGeneration:
        self.requests.append(request)
        raw_output = self.outputs[request.role.role_id]
        token_ids = list(range(100, 100 + len(raw_output.split())))
        return RawGeneration(
            raw_token_ids=token_ids,
            raw_decoded_output=raw_output,
            input_token_count=len(
                (request.prompt.system_prompt + request.prompt.user_prompt).split()
            ),
            output_token_count=len(token_ids),
            latency_ms=12.5,
        )


def _task_and_adapter() -> tuple[object, MMLUProBenchmarkAdapter]:
    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    result = adapter.convert(
        MMLUProTaskRecord(
            source_record_id="fixture-001",
            question="Which option is selected by this label-free fixture?",
            options=("first", "second", "third", "fourth"),
            category="fixture-domain",
        )
    )
    assert result.task is not None
    return result.task, adapter


def _runtime_request(
    backend: PilotExecutionBackend,
    aggregator: DeterministicMajorityAggregator,
) -> RuntimeExecutionRequest:
    task_object, benchmark_adapter = _task_and_adapter()
    from rolecheck.schemas import TaskSpec

    task = cast(TaskSpec, task_object)
    team = build_pilot_team()
    split = create_task_split_manifest(
        [task.task_id],
        dataset_id=MMLU_PRO_DATASET_ID,
        dataset_revision=MMLU_PRO_REVISION,
        adapter=benchmark_adapter.identity,
        seed=PILOT_SUBSET_SPLIT_SEED,
        evidence_class=EvidenceClass.EMPIRICAL_UNEVALUATED,
    )
    runtime = SelfHostedRuntimeAdapter(
        backend=backend,
        environment=pilot_runtime_environment(),
        aggregator=aggregator.identity,
    )
    manifest = create_manifest(
        experiment_id="pilot-fixture",
        git_commit="be3f2552d93cc967249c6000959a4d49fbdfd713",
        dataset_revision=MMLU_PRO_REVISION,
        task_split_hash=split.split_hash,
        initializer_id=team.source_initializer,
        team_config_hash=pilot_team_hash(),
        runtime_id=runtime.identity.runtime_id,
        runtime_version=runtime.identity.runtime_version,
        runtime_config_hash=runtime.identity.config_hash,
        runtime_environment=pilot_runtime_environment(),
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        seed=PILOT_EXPERIMENT_SEED,
        config_hash=canonical_json_hash({"fixture": "pilot-v0.1"}),
        model_versions={agent.agent_id: agent.model_id for agent in team.agents},
        prompt_hashes={role.role_id: role.prompt_hash for role in team.roles},
        role_contract_hashes={
            role.role_id: role_contract_hash(role.model_dump(mode="json")) for role in team.roles
        },
        aggregator_id=aggregator.identity.aggregator_id,
        aggregator_version=aggregator.identity.aggregator_version,
        aggregator_config_hash=aggregator.identity.config_hash,
        mock=False,
    )
    return RuntimeExecutionRequest(
        task=task,
        team=team,
        experiment_manifest=manifest,
        task_split_manifest=split,
    )


def _role_output(role_id: str, letter: str | None) -> PilotRoleOutput:
    final_content = "analysis"
    if letter is not None:
        final_content += f"\nAnswer: {letter}"
    parse = parse_terminal_answer(final_content, option_count=4)
    raw = f"<think>private</think>\n{final_content}"
    return PilotRoleOutput(
        role_id=role_id,
        role_seed=1,
        rendered_prompt_hash=canonical_json_hash("prompt"),
        raw_token_ids=[1, 2],
        raw_decoded_output=raw,
        raw_output_hash=canonical_json_hash(raw),
        parsed_reasoning="private",
        parsed_final_content=final_content,
        answer_parse=parse,
        input_token_count=3,
        output_token_count=2,
        latency_ms=1.0,
    )


def _aggregation_request(votes: list[tuple[str, str | None]]) -> AggregationRequest:
    responses = []
    for role_id, letter in votes:
        output = _role_output(role_id, letter).model_dump(mode="json")
        responses.append(
            FrozenRoleResponse(
                role_id=role_id,
                output=output,
                output_hash=canonical_json_hash(output),
            )
        )
    task_object, _ = _task_and_adapter()
    from rolecheck.schemas import TaskSpec

    return AggregationRequest(
        task=cast(TaskSpec, task_object),
        responses=tuple(responses),
        aggregation_seed=123,
    )


def test_pilot_roles_normalize_without_missing_unknown_or_conflicting_fields() -> None:
    results = build_pilot_normalizations()
    assert len(results) == 3
    assert {result.draft.role_id for result in results} == {
        "domain_analyst",
        "elimination_analyst",
        "verification_analyst",
    }
    for result in results:
        assert result.contract is not None
        assert result.missing_fields == []
        assert set(result.unknown_fields) == {
            "failure_output",
            "conflict_resolution_rule",
            "parent_role_version",
        }
        assert result.conflicting_fields == []
        assert result.unparsed_segments == []
        assert result.contract_parse_risk == 0.0
        assert all(
            metadata.status in {SourceType.EXPLICIT, SourceType.UNKNOWN}
            for metadata in result.field_metadata
        )


def test_pilot_team_freezes_independence_model_tools_and_removal_protocol() -> None:
    team = build_pilot_team()
    assert team.execution_protocol.kind is ProtocolKind.PARALLEL_INDEPENDENT
    assert team.execution_protocol.fixed_rounds == 1
    assert team.edges == []
    assert team.removal_protocol.strategy is RemovalStrategy.PARALLEL_AGGREGATION_REMOVAL
    assert team.removal_protocol.freeze_other_responses is True
    assert team.removal_protocol.reaggregate_with_same_protocol is True
    assert team.removal_protocol.compensation_message_allowed is False
    assert team.removal_protocol.non_removable_role_ids == []
    assert {role.interaction_mode for role in team.roles} == {InteractionMode.INDEPENDENT}
    assert {agent.model_id for agent in team.agents} == {PILOT_MODEL_ASSIGNMENT_ID}
    assert all(agent.tool_ids == [] for agent in team.agents)
    assert all(agent.sampling_config == PILOT_GENERATION_CONFIG for agent in team.agents)
    assert pilot_team_hash() == canonical_json_hash(team.model_dump(mode="json"))


def test_pilot_environment_matches_gate_2_a_evidence() -> None:
    environment = pilot_runtime_environment()
    assert environment.model_assignment_id == PILOT_MODEL_ASSIGNMENT_ID
    assert environment.dependency_lock_hash == (
        "sha256:9e8ce3b71f339a891420046befbdaf3ab8c370a06a37e28e578dcba125bddf6c"
    )
    assert environment.hardware_inventory_hash == (
        "sha256:89d3a5849c7f6c6dcfd1802e95ee2ebbd77ff804ca9ed0c873346c7d1363b9f4"
    )


def test_pilot_generation_config_is_immutable() -> None:
    with pytest.raises(TypeError):
        PILOT_GENERATION_CONFIG["temperature"] = 0.0  # type: ignore[index]


@pytest.mark.parametrize(
    ("content", "option_count", "status", "letter", "reason"),
    [
        ("Reason.\nAnswer: A", 4, AnswerParseStatus.VALID, "A", None),
        ("Answer: D", 4, AnswerParseStatus.VALID, "D", None),
        ("Answer: E", 4, AnswerParseStatus.INVALID, None, "answer_out_of_option_range"),
        ("Answer: a", 4, AnswerParseStatus.INVALID, None, "missing_terminal_answer"),
        ("Answer: A.", 4, AnswerParseStatus.INVALID, None, "missing_terminal_answer"),
        ("Answer:A", 4, AnswerParseStatus.INVALID, None, "missing_terminal_answer"),
        ("Answer: A\nextra", 4, AnswerParseStatus.INVALID, None, "missing_terminal_answer"),
        ("", 4, AnswerParseStatus.INVALID, None, "missing_terminal_answer"),
    ],
)
def test_terminal_answer_parser_is_exact(
    content: str,
    option_count: int,
    status: AnswerParseStatus,
    letter: str | None,
    reason: str | None,
) -> None:
    result = parse_terminal_answer(content, option_count=option_count)
    assert result.status is status
    assert result.answer_letter == letter
    assert result.invalid_reason == reason


def test_terminal_answer_parser_rejects_invalid_option_count() -> None:
    with pytest.raises(ValueError, match="option_count"):
        parse_terminal_answer("Answer: A", option_count=1)


@pytest.mark.parametrize(
    ("raw", "valid", "reasoning", "final", "reason"),
    [
        (
            "<think>work</think>\nAnswer: B",
            True,
            "work",
            "Answer: B",
            None,
        ),
        ("Answer: C", True, None, "Answer: C", None),
        (
            "<think>work",
            False,
            None,
            "<think>work",
            "unclosed_thinking_block",
        ),
        (
            "prefix<think>work</think>Answer: A",
            False,
            None,
            "prefix<think>work</think>Answer: A",
            "text_before_thinking_block",
        ),
        (
            "</think>Answer: A",
            False,
            None,
            "</think>Answer: A",
            "thinking_close_without_open",
        ),
    ],
)
def test_thinking_output_split_is_deterministic(
    raw: str,
    valid: bool,
    reasoning: str | None,
    final: str,
    reason: str | None,
) -> None:
    parsed = split_model_text(raw)
    assert parsed.structure_valid is valid
    assert parsed.reasoning == reasoning
    assert parsed.final_content == final
    assert parsed.invalid_reason == reason


def test_aggregator_applies_strict_majority_without_model_calls() -> None:
    aggregator = DeterministicMajorityAggregator()
    result = MajorityVoteResult.model_validate(
        aggregator.aggregate(_aggregation_request([("r1", "B"), ("r2", "B"), ("r3", "A")]))
    )
    assert result.selected_answer == "B"
    assert result.strict_majority is True
    assert result.tie_break_applied is False


def test_aggregator_uses_lexicographic_tie_break_and_excludes_invalid_votes() -> None:
    aggregator = DeterministicMajorityAggregator()
    result = MajorityVoteResult.model_validate(
        aggregator.aggregate(_aggregation_request([("r1", "C"), ("r2", "A"), ("r3", None)]))
    )
    assert result.selected_answer == "A"
    assert result.strict_majority is False
    assert result.tie_break_applied is True
    assert result.invalid_role_ids == ["r3"]


def test_aggregator_records_no_valid_vote_without_compensation() -> None:
    aggregator = DeterministicMajorityAggregator()
    result = MajorityVoteResult.model_validate(
        aggregator.aggregate(_aggregation_request([("r1", None), ("r2", None)]))
    )
    assert result.selected_answer is None
    assert result.vote_counts == {}
    assert result.invalid_role_ids == ["r1", "r2"]


def test_aggregator_rejects_mutated_output_and_role_identity() -> None:
    aggregator = DeterministicMajorityAggregator()
    request = _aggregation_request([("r1", "A")])
    response = request.responses[0]
    with pytest.raises(ValueError, match="hash mismatch"):
        aggregator.aggregate(
            AggregationRequest(
                task=request.task,
                responses=(
                    FrozenRoleResponse(
                        role_id=response.role_id,
                        output=response.output,
                        output_hash=canonical_json_hash("wrong"),
                    ),
                ),
                aggregation_seed=1,
            )
        )
    dumped = _role_output("different", "A").model_dump(mode="json")
    with pytest.raises(ValueError, match="role identity"):
        aggregator.aggregate(
            AggregationRequest(
                task=request.task,
                responses=(
                    FrozenRoleResponse(
                        role_id="r1",
                        output=dumped,
                        output_hash=canonical_json_hash(dumped),
                    ),
                ),
                aggregation_seed=1,
            )
        )


def test_aggregator_rejects_answer_evidence_from_a_different_option_count() -> None:
    aggregator = DeterministicMajorityAggregator()
    request = _aggregation_request([("r1", "A")])
    output = dict(request.responses[0].output)
    answer_parse = dict(output["answer_parse"])
    answer_parse["option_count"] = 5
    output["answer_parse"] = answer_parse
    with pytest.raises(ValueError, match="option-count mismatch"):
        aggregator.aggregate(
            AggregationRequest(
                task=request.task,
                responses=(
                    FrozenRoleResponse(
                        role_id="r1",
                        output=output,
                        output_hash=canonical_json_hash(output),
                    ),
                ),
                aggregation_seed=1,
            )
        )


def test_prompt_renderer_contains_only_role_task_and_ordered_options() -> None:
    task_object, _ = _task_and_adapter()
    from rolecheck.schemas import TaskSpec

    task = cast(TaskSpec, task_object)
    prompt = render_role_prompt(build_pilot_team().roles[0], task)
    assert prompt.system_prompt == build_pilot_team().roles[0].raw_prompt
    assert task.task_text in prompt.user_prompt
    assert "A. first\nB. second\nC. third\nD. fourth" in prompt.user_prompt
    assert "fixture-001" not in prompt.user_prompt
    assert "fixture-domain" not in prompt.user_prompt
    assert MMLU_PRO_REVISION not in prompt.user_prompt
    assert prompt.user_prompt.endswith("Answer: <LETTER>")
    assert prompt.messages_hash == canonical_json_hash(
        [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": prompt.user_prompt},
        ]
    )


def test_rendered_prompt_rejects_a_hash_for_different_messages() -> None:
    with pytest.raises(ValidationError, match="frozen messages"):
        RenderedRolePrompt(
            system_prompt="system",
            user_prompt="user",
            messages_hash=canonical_json_hash("different"),
        )


def test_backend_rejects_unfrozen_generation_engine_identity() -> None:
    engine = FakeGenerationEngine({})
    engine._identity = RuntimeAdapterIdentity(
        runtime_id="wrong",
        runtime_version="v0.1",
        config_hash=canonical_json_hash({"wrong": True}),
    )
    with pytest.raises(ValueError, match="frozen Pilot identity"):
        PilotExecutionBackend(
            generation_engine=engine,
            aggregator=DeterministicMajorityAggregator(),
        )


def test_backend_rejects_aggregator_identity_drift_before_execution() -> None:
    aggregator = DeterministicMajorityAggregator()
    backend = PilotExecutionBackend(
        generation_engine=FakeGenerationEngine({}),
        aggregator=aggregator,
    )
    aggregator._identity = AggregatorIdentity(
        aggregator_id="wrong",
        aggregator_version="v0.1",
        config_hash=canonical_json_hash({"wrong": True}),
    )
    request = _runtime_request(backend, aggregator)
    with pytest.raises(ValueError, match="changed before execution"):
        backend.execute(request)


def test_self_hosted_pilot_execution_retains_evidence_and_isolates_roles() -> None:
    engine = FakeGenerationEngine(
        {
            "domain_analyst": "<think>domain-secret</think>\nDomain.\nAnswer: B",
            "elimination_analyst": "<think>elimination-secret</think>\nEliminate.\nAnswer: B",
            "verification_analyst": "<think>verification-secret</think>\nVerify.\nAnswer: A",
        }
    )
    aggregator = DeterministicMajorityAggregator()
    backend = PilotExecutionBackend(generation_engine=engine, aggregator=aggregator)
    request = _runtime_request(backend, aggregator)
    runtime = SelfHostedRuntimeAdapter(
        backend=backend,
        environment=pilot_runtime_environment(),
        aggregator=aggregator.identity,
    )
    result = runtime.execute(request)
    assert result.accepted is True
    assert result.evidence_class is EvidenceClass.EMPIRICAL_UNEVALUATED
    assert result.execution is not None
    assert result.execution.mock is False
    assert result.execution.status.value == "succeeded"
    final = MajorityVoteResult.model_validate(result.execution.final_output)
    assert final.selected_answer == "B"
    assert len(engine.requests) == 3
    assert [item.role.role_id for item in engine.requests] == (
        request.team.execution_protocol.execution_order
    )
    assert all(item.generation_config == PILOT_GENERATION_CONFIG for item in engine.requests)
    assert "domain-secret" not in engine.requests[1].prompt.user_prompt
    assert "elimination-secret" not in engine.requests[2].prompt.user_prompt
    for role_id, raw in result.execution.role_outputs.items():
        output = PilotRoleOutput.model_validate(raw)
        assert output.role_id == role_id
        assert output.raw_token_ids
        assert output.raw_output_hash == canonical_json_hash(output.raw_decoded_output)
        assert (
            output.rendered_prompt_hash
            == engine.requests[
                request.team.execution_protocol.execution_order.index(role_id)
            ].prompt.messages_hash
        )


def test_raw_generation_and_role_evidence_reject_inconsistent_hashes_and_counts() -> None:
    with pytest.raises(ValidationError, match="output token count"):
        RawGeneration(
            raw_token_ids=[1],
            raw_decoded_output="Answer: A",
            input_token_count=1,
            output_token_count=2,
            latency_ms=1.0,
        )
    output = _role_output("r1", "A").model_dump(mode="json")
    output["raw_output_hash"] = canonical_json_hash("tampered")
    with pytest.raises(ValidationError, match="raw output hash"):
        PilotRoleOutput.model_validate(output)


def test_reviewed_pilot_hashes_are_frozen() -> None:
    normalizations = {result.draft.role_id: result for result in build_pilot_normalizations()}
    expected = {
        "domain_analyst": (
            "sha256:bad560eb6ee9ce382fd2c4c884d05e5bdc3f658640602fd60bc3bc187c89799b",
            "sha256:a95754e740fdb33bf3b28664557e7e0610a3b98e6d89936247f6e0fcfea883cd",
            "sha256:95cb290ed219a0f3db419552a82ce67b2b4ca338249f04b8935081a078884c2b",
        ),
        "elimination_analyst": (
            "sha256:15c17d7af4b63ebc82138556de0c74dd50f26d4f33723ce7de49e71bb0af5c4f",
            "sha256:edc6005c74019d312da6d84d90e2b479f005d5e831bf8aef131e3d99fda51f24",
            "sha256:70c495290b4451ecf10451707358b5009770b426c984cbcde6b850e4946b021b",
        ),
        "verification_analyst": (
            "sha256:0e2c6cff40df14c1750e8729ba6bfb10b6cee1448e8ee56770c411ec1aa638a2",
            "sha256:7d8f38e682f2b2d03e032b8be7f8c45c4c4d13dcd2e6276a3b0d6a381977f9b0",
            "sha256:4514813f00d39d13d1111a6b1647013bd19a25c06acb419e064883e7d34ee5c2",
        ),
    }
    for role_id, (prompt_hash, contract_hash, normalization_hash) in expected.items():
        result = normalizations[role_id]
        assert result.contract is not None
        assert result.contract.prompt_hash == prompt_hash
        assert role_contract_hash(result.contract.model_dump(mode="json")) == contract_hash
        assert result.normalization_id == normalization_hash

    aggregator = DeterministicMajorityAggregator()
    engine = FakeGenerationEngine({})
    backend = PilotExecutionBackend(generation_engine=engine, aggregator=aggregator)
    runtime = SelfHostedRuntimeAdapter(
        backend=backend,
        environment=pilot_runtime_environment(),
        aggregator=aggregator.identity,
    )
    assert pilot_team_hash() == (
        "sha256:3c768707410ed19e2a06eaee70b9116e0ef1a01380c5cf361166b38b7acaadac"
    )
    assert aggregator.identity.config_hash == (
        "sha256:fe61484ff35764e87e5bf3bf2a4ca9881eac5d2ef274278284de1b5a6a11e31e"
    )
    assert canonical_json_hash(pilot_runtime_environment().model_dump(mode="json")) == (
        "sha256:75bd5f65b1c3acca4d364e2a67041db2aa57db5b3e0eedea42c2890d104ffc55"
    )
    assert answer_parser_identity().config_hash == (
        "sha256:782c7636a1dbcaec4ac0d56dfe974dea5c6342eeee99c5308a6015dc1f97cd9f"
    )
    assert required_generation_engine_identity().config_hash == (
        "sha256:17f02120c9861c4e0bd34a5ef9396359eabdc389312effa38ca1202182f1f7a3"
    )
    assert backend.identity.config_hash == (
        "sha256:62beeb34048c7b6f29402449212c9831246ff047ec0adf67b0cdf3f4fcdfff1e"
    )
    assert runtime.identity.config_hash == (
        "sha256:3359697ecd6b32fe3f869cca2b4c1fc1cd712b34ec59a60d3d869297bcf9cf43"
    )
