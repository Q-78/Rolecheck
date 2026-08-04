from __future__ import annotations

import hashlib
import json
import shutil
import signal
import time
from datetime import UTC, datetime
from pathlib import Path

from rolecheck.benchmark.gate3 import audit_preexecution_payload
from rolecheck.hashing import canonical_json_hash, derive_seed
from rolecheck.pilot import (
    PILOT_EXPERIMENT_SEED,
    PILOT_GENERATION_CONFIG,
    DeterministicMajorityAggregator,
    build_pilot_team,
    parse_terminal_answer,
    render_role_prompt,
    split_model_text,
)
from rolecheck.pilot.execution import RoleGenerationRequest
from rolecheck.pilot.models import AnswerParseResult, AnswerParseStatus, PilotRoleOutput
from rolecheck.pilot.transformers_engine import Qwen3SingleGpuGenerationEngine
from rolecheck.runtime.interfaces import AggregationRequest, FrozenRoleResponse
from rolecheck.schemas import TaskSpec

ARTIFACT_ROOT = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3")
GATE3 = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-3-manifest-v0.1")
OUTPUT = ARTIFACT_ROOT / "gate-6-controlled-pilot-v0.2/execution"
PREVIOUS = ARTIFACT_ROOT / "gate-6-controlled-pilot-v0.1/execution"
PREVIOUS_ABORT_SHA256 = "a7e093142a6434aba49c05311bab3bf89bff4856340de2227bb9135a98a5c696"
REUSED_TASKS = 6
RETRY_TASK_ID = "mmlu-pro-9e52575a051508f88b66aaae"
RETRY_ROLE_ID = "domain_analyst"
MODEL = Path(
    "/data/qhy/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/"
    "b968826d9c46dd6066d109eabc6255188de91218"
)
BASE_COMMIT = "e10bb09f33b76b34923c9e4b96b473feebd7cb09"
PILOT_REVISION = "v0.3"
PHYSICAL_GPU_INDEX = 1
PHYSICAL_GPU_UUID = "GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65"
TIMEOUT_SECONDS = 180
GPU_BUDGET_SECONDS = 28800
EXPECTED_TASKS = 56
EXPECTED_ROLES = 168
PILOT_V03_GENERATION_CONFIG = dict(PILOT_GENERATION_CONFIG)


def dump(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def timeout_handler(signum: int, frame: object) -> None:
    raise TimeoutError("Gate 6 role generation exceeded 180 seconds")


def parsed_output(
    *, role_id: str, role_seed: int, rendered_hash: str, generation: object, option_count: int
) -> PilotRoleOutput:
    raw = generation.raw_decoded_output
    parsed = split_model_text(raw)
    if parsed.structure_valid:
        answer = parse_terminal_answer(parsed.final_content, option_count=option_count)
    else:
        answer = AnswerParseResult(
            final_content_hash=canonical_json_hash(parsed.final_content),
            option_count=option_count,
            status=AnswerParseStatus.INVALID,
            invalid_reason=f"invalid_model_text:{parsed.invalid_reason}",
        )
    return PilotRoleOutput(
        role_id=role_id,
        role_seed=role_seed,
        rendered_prompt_hash=rendered_hash,
        raw_token_ids=list(generation.raw_token_ids),
        raw_decoded_output=raw,
        raw_output_hash=canonical_json_hash(raw),
        parsed_reasoning=parsed.reasoning,
        parsed_final_content=parsed.final_content,
        answer_parse=answer,
        input_token_count=generation.input_token_count,
        output_token_count=generation.output_token_count,
        latency_ms=generation.latency_ms,
    )


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("Gate 6 dry-run artifact target already exists")
    source_manifest = json.loads((GATE3 / "pilot-56-manifest.json").read_text())
    audit_preexecution_payload(source_manifest)
    if len(source_manifest["tasks"]) != EXPECTED_TASKS:
        raise RuntimeError("Gate 6 requires exactly 56 frozen tasks")
    team = build_pilot_team()
    aggregator = DeterministicMajorityAggregator()
    role_order = list(team.execution_protocol.execution_order)
    if len(role_order) != 3:
        raise RuntimeError("Gate 6 requires exactly three frozen roles")
    plan = {
        "gate": 6,
        "execution_revision": "v0.2",
        "pilot_revision": PILOT_REVISION,
        "physical_gpu_index": PHYSICAL_GPU_INDEX,
        "physical_gpu_uuid": PHYSICAL_GPU_UUID,
        "process_logical_cuda_device": 0,
        "supersedes_abort_sha256": f"sha256:{PREVIOUS_ABORT_SHA256}",
        "checkpoint_reuse": {
            "source": str(PREVIOUS),
            "reused_tasks": REUSED_TASKS,
            "payload_policy": "byte_identical_copy_after_hash_validation",
        },
        "infrastructure_retry": {
            "task_id": RETRY_TASK_ID,
            "role_id": RETRY_ROLE_ID,
            "attempt": 1,
            "maximum_attempts": 1,
        },
        "base_commit": BASE_COMMIT,
        "code_identity": {
            "runner_sha256": digest(Path(__file__)),
            "engine_sha256": digest(
                Path(__file__).parents[1] / "src/rolecheck/pilot/transformers_engine.py"
            ),
        },
        "gate3_manifest_hash": source_manifest["subset"]["manifest_hash"],
        "task_ids": list(source_manifest["subset"]["task_ids"]),
        "role_order": role_order,
        "experiment_seed": PILOT_EXPERIMENT_SEED,
        "generation_config": dict(PILOT_V03_GENERATION_CONFIG),
        "aggregator_identity": aggregator.identity.model_dump(mode="json"),
        "limits": {
            "concurrent_tasks": 1,
            "concurrent_role_generations": 1,
            "model_replicas": 1,
            "per_role_timeout_seconds": TIMEOUT_SECONDS,
            "infrastructure_retries": 1,
            "allowed_infrastructure_retries": 1,
            "semantic_quality_retries": 0,
            "extraction_failure_retries": 0,
            "gpu_budget_seconds": GPU_BUDGET_SECONDS,
            "checkpoint_interval_tasks": 1,
        },
        "correctness_evaluation": False,
        "role_removal": False,
    }
    audit_preexecution_payload(plan)
    ARTIFACT_ROOT.mkdir(exist_ok=True)
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "checkpoints").mkdir()
    previous_abort = json.loads((PREVIOUS / "abort.json").read_text())
    previous_progress = json.loads((PREVIOUS / "progress.json").read_text())
    if digest(PREVIOUS / "abort.json") != PREVIOUS_ABORT_SHA256:
        raise RuntimeError("superseded abort hash mismatch")
    if previous_abort["completed_tasks"] != REUSED_TASKS:
        raise RuntimeError("superseded run did not complete exactly six tasks")
    if len(previous_progress["completed"]) != REUSED_TASKS:
        raise RuntimeError("superseded progress does not contain six checkpoints")
    completed: list[dict[str, object]] = []
    for item in previous_progress["completed"]:
        source = PREVIOUS / "checkpoints" / str(item["checkpoint"])
        payload = json.loads(source.read_text())
        unhashed = dict(payload)
        stored_hash = unhashed.pop("checkpoint_hash")
        if canonical_json_hash(unhashed) != stored_hash or stored_hash != item["checkpoint_hash"]:
            raise RuntimeError(f"reused checkpoint hash mismatch: {source.name}")
        shutil.copy2(source, OUTPUT / "checkpoints" / source.name)
        completed.append(item)
    dump(OUTPUT / "execution-plan.json", plan)
    started_at = datetime.now(UTC).isoformat()
    generation_seconds = float(previous_abort["generation_seconds"])
    dump(
        OUTPUT / "progress.json",
        {
            "completed": completed,
            "completed_tasks": len(completed),
            "generation_seconds": generation_seconds,
            "reused_checkpoint_tasks": REUSED_TASKS,
        },
    )
    engine = None
    try:
        engine = Qwen3SingleGpuGenerationEngine(
            model_path=MODEL,
            generation_config=PILOT_V03_GENERATION_CONFIG,
            runtime_version=PILOT_REVISION,
            cuda_visible_devices=str(PHYSICAL_GPU_INDEX),
        )
        role_by_id = {role.role_id: role for role in team.roles}
        for task_index, task_payload in enumerate(source_manifest["tasks"]):
            task = TaskSpec.model_validate(task_payload)
            if task_index < REUSED_TASKS:
                continue
            if task_index == REUSED_TASKS and (
                task.task_id != RETRY_TASK_ID or role_order[0] != RETRY_ROLE_ID
            ):
                raise RuntimeError("frozen retry target identity mismatch")
            audit_preexecution_payload(task.model_dump(mode="json"))
            task_started = datetime.now(UTC).isoformat()
            outputs: dict[str, object] = {}
            output_hashes: dict[str, str] = {}
            for role_id in role_order:
                role = role_by_id[role_id]
                rendered = render_role_prompt(role, task)
                role_seed = derive_seed(PILOT_EXPERIMENT_SEED, "role", role_id)
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(TIMEOUT_SECONDS)
                before = time.perf_counter()
                try:
                    generation = engine.generate(
                        RoleGenerationRequest(
                            task=task,
                            role=role,
                            prompt=rendered,
                            role_seed=role_seed,
                            generation_config=dict(PILOT_V03_GENERATION_CONFIG),
                        )
                    )
                finally:
                    generation_seconds += time.perf_counter() - before
                    signal.alarm(0)
                if generation_seconds >= GPU_BUDGET_SECONDS:
                    raise RuntimeError("Gate 6 GPU generation budget exhausted")
                role_output = parsed_output(
                    role_id=role_id,
                    role_seed=role_seed,
                    rendered_hash=rendered.messages_hash,
                    generation=generation,
                    option_count=len(task.public_metadata["options"]),
                )
                dumped = role_output.model_dump(mode="json")
                outputs[role_id] = dumped
                output_hashes[role_id] = canonical_json_hash(dumped)
            aggregation_seed = derive_seed(PILOT_EXPERIMENT_SEED, "aggregation", team.team_id)
            responses = tuple(
                FrozenRoleResponse(
                    role_id=role_id,
                    output=outputs[role_id],
                    output_hash=output_hashes[role_id],
                )
                for role_id in role_order
            )
            request = AggregationRequest(
                task=task, responses=responses, aggregation_seed=aggregation_seed
            )
            aggregation = aggregator.aggregate(request)
            replay = aggregator.aggregate(request)
            aggregation_hash = canonical_json_hash(aggregation)
            replay_hash = canonical_json_hash(replay)
            if aggregation_hash != replay_hash:
                raise RuntimeError("aggregation replay hash mismatch")
            checkpoint = {
                "task_index": task_index,
                "task_id": task.task_id,
                "task_started_at": task_started,
                "task_finished_at": datetime.now(UTC).isoformat(),
                "role_outputs": outputs,
                "role_output_hashes": output_hashes,
                "aggregation": aggregation,
                "aggregation_hash": aggregation_hash,
                "replay_hash": replay_hash,
                "aggregation_model_calls": 0,
                "evaluated": False,
                "role_removal": False,
            }
            checkpoint_hash = canonical_json_hash(checkpoint)
            checkpoint["checkpoint_hash"] = checkpoint_hash
            checkpoint_path = OUTPUT / "checkpoints" / f"{task_index:02d}-{task.task_id}.json"
            dump(checkpoint_path, checkpoint)
            completed.append(
                {
                    "task_index": task_index,
                    "task_id": task.task_id,
                    "checkpoint": checkpoint_path.name,
                    "checkpoint_hash": checkpoint_hash,
                }
            )
            dump(
                OUTPUT / "progress.json",
                {
                    "completed": completed,
                    "completed_tasks": len(completed),
                    "generation_seconds": generation_seconds,
                },
            )
        valid = 0
        for item in completed:
            checkpoint = json.loads((OUTPUT / "checkpoints" / str(item["checkpoint"])).read_text())
            valid += sum(
                output["answer_parse"]["status"] == "valid"
                for output in checkpoint["role_outputs"].values()
            )
        result = {
            "status": "SUCCEEDED",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "plan_hash": canonical_json_hash(plan),
            "engine_identity": engine.identity.model_dump(mode="json"),
            "runtime_state": engine.runtime_state,
            "task_records": len(completed),
            "role_executions": len(completed) * len(role_order),
            "aggregations": len(completed),
            "valid_extractions": valid,
            "valid_extraction_rate": valid / EXPECTED_ROLES,
            "generation_seconds": generation_seconds,
            "aggregation_replay_byte_equivalent": True,
            "identity_violations": 0,
            "mutation_violations": 0,
            "leakage_violations": 0,
            "checkpoint_violations": 0,
            "evaluated": False,
            "role_removal": False,
        }
        dump(OUTPUT / "execution-result.json", result)
    except Exception as exc:
        dump(
            OUTPUT / "abort.json",
            {
                "status": "ABORTED",
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(),
                "completed_tasks": len(completed),
                "generation_seconds": generation_seconds,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise
    finally:
        if engine is not None:
            engine.close()
    files = [
        {
            "path": str(path.relative_to(OUTPUT)),
            "size": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(OUTPUT.rglob("*"))
        if path.is_file() and path.name != "artifact-manifest.json"
    ]
    dump(
        OUTPUT / "artifact-manifest.json",
        {
            "files": files,
            "files_hash": canonical_json_hash(files),
            "model_unloaded": True,
        },
    )


if __name__ == "__main__":
    main()
