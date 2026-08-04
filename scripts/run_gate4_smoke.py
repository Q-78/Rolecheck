from __future__ import annotations

import hashlib
import json
import signal
from datetime import UTC, datetime
from pathlib import Path

from rolecheck.benchmark.gate3 import audit_preexecution_payload
from rolecheck.hashing import canonical_json_hash, derive_seed
from rolecheck.pilot import (
    PILOT_EXPERIMENT_SEED,
    PILOT_GENERATION_CONFIG,
    build_pilot_team,
    parse_terminal_answer,
    render_role_prompt,
    split_model_text,
)
from rolecheck.pilot.execution import RoleGenerationRequest
from rolecheck.pilot.models import AnswerParseResult, AnswerParseStatus, PilotRoleOutput
from rolecheck.pilot.transformers_engine import Qwen3SingleGpuGenerationEngine
from rolecheck.schemas import TaskSpec

ARTIFACT_ROOT = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.1")
GATE3 = ARTIFACT_ROOT / "gate-3-v0.2"
OUTPUT = ARTIFACT_ROOT / "gate-4-smoke-v0.2"
MODEL = Path(
    "/data/qhy/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218"
)
ROLE_ID = "domain_analyst"
TIMEOUT_SECONDS = 180
SUPERSEDES_ARTIFACT_HASH = "sha256:d6d26d14d5fedcdb759428596a5c2c70fc9cb8686a61d2599686eb66d16bb270"


def dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def timeout_handler(signum: int, frame: object) -> None:
    raise TimeoutError("Gate 4 role generation exceeded 180 seconds")


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("Gate 4 smoke artifact target already exists")
    manifest = json.loads((GATE3 / "pilot-14-manifest.json").read_text())
    audit_preexecution_payload(manifest)
    selected_task_id = manifest["subset"]["task_ids"][0]
    task_payload = next(task for task in manifest["tasks"] if task["task_id"] == selected_task_id)
    task = TaskSpec.model_validate(task_payload)
    team = build_pilot_team()
    role = next(role for role in team.roles if role.role_id == ROLE_ID)
    rendered = render_role_prompt(role, task)
    role_seed = derive_seed(PILOT_EXPERIMENT_SEED, "role", ROLE_ID)
    plan = {
        "gate": 4,
        "supersedes_artifact_files_hash": SUPERSEDES_ARTIFACT_HASH,
        "base_commit": "3509b8af80d8e4ec2ed55fe138af082980a8749c",
        "code_identity": {
            "runner_sha256": digest(Path(__file__)),
            "engine_sha256": digest(
                Path(__file__).parents[1] / "src/rolecheck/pilot/transformers_engine.py"
            ),
        },
        "selection_rule": "first_task_in_canonical_pilot14_order",
        "task_id": task.task_id,
        "role_id": ROLE_ID,
        "role_seed": role_seed,
        "rendered_messages_hash": rendered.messages_hash,
        "gate3_manifest_hash": manifest["subset"]["manifest_hash"],
        "generation_config": dict(PILOT_GENERATION_CONFIG),
        "timeout_seconds": TIMEOUT_SECONDS,
        "model_path": str(MODEL),
        "model_load": {
            "dtype": "bfloat16",
            "visible_gpu": 0,
            "quantization": False,
            "cpu_offload": False,
            "local_files_only": True,
        },
    }
    audit_preexecution_payload(plan)
    OUTPUT.mkdir()
    dump(OUTPUT / "smoke-plan.json", plan)
    started = datetime.now(UTC).isoformat()
    engine = None
    try:
        engine = Qwen3SingleGpuGenerationEngine(model_path=MODEL)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(TIMEOUT_SECONDS)
        try:
            generation = engine.generate(
                RoleGenerationRequest(
                    task=task,
                    role=role,
                    prompt=rendered,
                    role_seed=role_seed,
                    generation_config=dict(PILOT_GENERATION_CONFIG),
                )
            )
        finally:
            signal.alarm(0)
        parsed = split_model_text(generation.raw_decoded_output)
        if parsed.structure_valid:
            parsed_answer = parse_terminal_answer(
                parsed.final_content,
                option_count=len(task.public_metadata["options"]),
            )
        else:
            parsed_answer = AnswerParseResult(
                final_content_hash=canonical_json_hash(parsed.final_content),
                option_count=len(task.public_metadata["options"]),
                status=AnswerParseStatus.INVALID,
                invalid_reason=f"invalid_model_text:{parsed.invalid_reason}",
            )
        output = PilotRoleOutput(
            role_id=ROLE_ID,
            role_seed=role_seed,
            rendered_prompt_hash=rendered.messages_hash,
            raw_token_ids=generation.raw_token_ids,
            raw_decoded_output=generation.raw_decoded_output,
            raw_output_hash=canonical_json_hash(generation.raw_decoded_output),
            parsed_reasoning=parsed.reasoning,
            parsed_final_content=parsed.final_content,
            answer_parse=parsed_answer,
            input_token_count=generation.input_token_count,
            output_token_count=generation.output_token_count,
            latency_ms=generation.latency_ms,
        )
        result = {
            "status": "SUCCEEDED",
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "plan_hash": canonical_json_hash(plan),
            "engine_identity": engine.identity.model_dump(mode="json"),
            "runtime_state": engine.runtime_state,
            "role_output": output.model_dump(mode="json"),
            "role_output_hash": canonical_json_hash(output.model_dump(mode="json")),
            "evaluated": False,
        }
        dump(OUTPUT / "smoke-result.json", result)
    except Exception as exc:
        dump(
            OUTPUT / "abort.json",
            {
                "status": "ABORTED",
                "started_at": started,
                "finished_at": datetime.now(UTC).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise
    finally:
        if engine is not None:
            engine.close()
    files = [
        {"path": path.name, "size": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(OUTPUT.iterdir())
        if path.is_file()
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
