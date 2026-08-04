"""Execute the frozen Gate 6.2A structured-score Smoke on the authorized server."""

from __future__ import annotations

import hashlib
import json
import signal
import time
from datetime import UTC, datetime
from pathlib import Path

from rolecheck.benchmark.gate3 import audit_preexecution_payload
from rolecheck.hashing import canonical_json_hash, derive_seed
from rolecheck.pilot import build_pilot_team
from rolecheck.pilot.execution import RoleGenerationRequest
from rolecheck.pilot.models import RenderedRolePrompt
from rolecheck.pilot.transformers_engine import Qwen3SingleGpuGenerationEngine
from rolecheck.schemas import TaskSpec
from rolecheck.signal.aggregation import DeterministicScoreAggregator
from rolecheck.signal.evaluation import evaluate_keep_value
from rolecheck.signal.models import RoleScoreEvidence, StructuredRemovalEvaluation
from rolecheck.signal.parsing import parse_structured_role_output

ROOT = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.4/gate-6-2a-v0.1")
GATE3 = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-3-manifest-v0.1")
GATE6 = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-6-controlled-pilot-v0.2")
GATE61 = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-6-1a-posthoc-analysis-v0.1")
MODEL = Path(
    "/data/qhy/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218"
)
MASTER_SEED = 2026080302
GPU_INDEX = 1
GPU_UUID = "GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65"
TIMEOUT = 180
BUDGET = 3600
CONFIG: dict[str, object] = {
    "enable_thinking": False,
    "max_new_tokens": 384,
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 20,
    "do_sample": True,
}
PROMPTS = {
    "domain_analyst": "Use domain definitions, facts, and theory applicability.",
    "elimination_analyst": "Use violated constraints, contradictions, and elimination.",
    "verification_analyst": "Use boundary cases, counterexamples, and consistency checks.",
}
COMMON = """Work independently on the multiple-choice task. Score every option with integer support from 0 to 100; scores must sum to 100. Return only JSON with exactly option_scores and key_evidence. key_evidence has at most 3 brief visible items. Do not emit <think>, chain-of-thought, an answer field, KEEP/REMOVE, repairs, markdown, or extra text."""  # noqa: E501


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root: Path) -> list[dict[str, object]]:
    return [
        {"path": p.relative_to(root).as_posix(), "size": p.stat().st_size, "sha256": file_sha(p)}
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "artifact-manifest.json"
    ]


def seal(root: Path, extra: dict[str, object]) -> str:
    files = inventory(root)
    digest = canonical_json_hash(files)
    dump(root / "artifact-manifest.json", {"files": files, "files_hash": digest, **extra})
    return digest


def timeout_handler(signum: int, frame: object) -> None:
    raise TimeoutError("Gate 6.2A role generation exceeded 180 seconds")


def prompt(role_id: str, task: TaskSpec) -> RenderedRolePrompt:
    options = task.public_metadata["options"]
    user = (
        task.task_text
        + "\n"
        + "\n".join(f"{chr(65 + i)}. {value}" for i, value in enumerate(options))
    )
    system = PROMPTS[role_id] + "\n" + COMMON
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return RenderedRolePrompt(
        system_prompt=system, user_prompt=user, messages_hash=canonical_json_hash(messages)
    )


def main() -> None:
    if ROOT.exists():
        raise FileExistsError(ROOT)
    manifest = json.loads((GATE3 / "pilot-14-manifest.json").read_text())
    audit_preexecution_payload(manifest)
    if len(manifest["tasks"]) != 14:
        raise RuntimeError("Gate 6.2A requires exactly 14 frozen tasks")
    team = build_pilot_team()
    roles = list(PROMPTS)
    role_by_id = {role.role_id: role for role in team.roles}
    aggregator = DeterministicScoreAggregator()
    plan = {
        "gate": "6.2A",
        "tasks": manifest["subset"]["task_ids"],
        "roles": roles,
        "master_seed": MASTER_SEED,
        "generation_config": CONFIG,
        "gpu_index": GPU_INDEX,
        "gpu_uuid": GPU_UUID,
        "budget_seconds": BUDGET,
        "model": str(MODEL),
    }
    audit_preexecution_payload(plan)
    ROOT.mkdir(parents=True)
    dump(ROOT / "execution/plan.json", plan)
    elapsed = 0.0
    engine = None
    try:
        engine = Qwen3SingleGpuGenerationEngine(
            model_path=MODEL,
            generation_config=CONFIG,
            runtime_version="gate62a-v0.1",
            cuda_visible_devices=str(GPU_INDEX),
        )
        for index, raw_task in enumerate(manifest["tasks"]):
            task = TaskSpec.model_validate(raw_task)
            task_hash = canonical_json_hash(task.model_dump(mode="json"))
            records: dict[str, object] = {}
            for role_id in roles:
                rendered = prompt(role_id, task)
                seed = derive_seed(MASTER_SEED, "gate62a-role", f"{task.task_id}|{role_id}")
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(TIMEOUT)
                started = time.perf_counter()
                try:
                    generated = engine.generate(
                        RoleGenerationRequest(
                            task=task,
                            role=role_by_id[role_id],
                            prompt=rendered,
                            role_seed=seed,
                            generation_config=CONFIG,
                        )
                    )
                finally:
                    elapsed += time.perf_counter() - started
                    signal.alarm(0)
                parsed = parse_structured_role_output(
                    generated.raw_decoded_output,
                    [chr(65 + i) for i in range(len(task.public_metadata["options"]))],
                )
                records[role_id] = {
                    "role_id": role_id,
                    "seed": seed,
                    "raw_output": generated.raw_decoded_output,
                    "raw_token_ids": generated.raw_token_ids,
                    "input_tokens": generated.input_token_count,
                    "output_tokens": generated.output_token_count,
                    "latency_ms": generated.latency_ms,
                    "parse": parsed.model_dump(mode="json"),
                }
                if elapsed >= BUDGET:
                    raise RuntimeError("Gate 6.2A GPU budget exhausted")
            dump(
                ROOT / f"execution/records/{index:02d}-{task.task_id}.json",
                {"task_id": task.task_id, "task_hash": task_hash, "roles": records},
            )
        dump(
            ROOT / "execution/result.json",
            {
                "status": "SUCCEEDED",
                "generation_seconds": elapsed,
                "role_executions": 42,
                "engine_identity": engine.identity.model_dump(mode="json"),
                "runtime_state": engine.runtime_state,
            },
        )
    except Exception as exc:
        dump(
            ROOT / "abort.json",
            {
                "status": "ABORTED",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "generation_seconds": elapsed,
                "finished_at": datetime.now(UTC).isoformat(),
            },
        )
        seal(ROOT, {"gate62a_complete": False})
        raise
    finally:
        if engine is not None:
            engine.close()
    execution_hash = seal(ROOT / "execution", {"gold_loaded": False})

    removals: list[StructuredRemovalEvaluation] = []
    baselines: dict[str, object] = {}
    invalid = 0
    for path in sorted((ROOT / "execution/records").glob("*.json")):
        record = json.loads(path.read_text())
        evidence: list[RoleScoreEvidence | None] = []
        for role_id in roles:
            parsed = record["roles"][role_id]["parse"]
            if parsed["status"] != "valid":
                evidence.append(None)
                invalid += 1
            else:
                from rolecheck.signal.models import StructuredRoleOutput

                output = StructuredRoleOutput.model_validate(parsed["output"])
                evidence.append(
                    RoleScoreEvidence(
                        role_id=role_id, output=output, output_hash=parsed["output_hash"]
                    )
                )
        letters = list(
            next(item for item in evidence if item is not None).output.option_scores.scores
        )
        baseline = aggregator.aggregate(
            task_id=record["task_id"],
            task_hash=record["task_hash"],
            option_letters=letters,
            required_role_ids=roles,
            role_outputs=evidence,
        )
        baselines[record["task_id"]] = baseline.model_dump(mode="json")
        if not baseline.scorable:
            continue
        valid_evidence = [item for item in evidence if item is not None]
        hashes = {item.role_id: item.output_hash for item in valid_evidence}
        for target in roles:
            retained = [role for role in roles if role != target]
            kept = [item for item in valid_evidence if item.role_id != target]
            removal = aggregator.aggregate(
                task_id=record["task_id"],
                task_hash=record["task_hash"],
                option_letters=letters,
                required_role_ids=retained,
                role_outputs=kept,
            )
            obj = StructuredRemovalEvaluation(
                task_id=record["task_id"],
                task_hash=record["task_hash"],
                removed_role_id=target,
                baseline_input_hash=canonical_json_hash(hashes),
                removal_input_hash=canonical_json_hash({r: hashes[r] for r in retained}),
                baseline_role_output_hashes=hashes,
                removal_role_output_hashes={r: hashes[r] for r in retained},
                baseline=baseline,
                removal=removal,
                retained_role_ids=retained,
            )
            removals.append(obj)
            dump(
                ROOT / f"removals/records/{record['task_id']}-{target}.json",
                obj.model_dump(mode="json"),
            )
    dump(ROOT / "removals/baselines.json", baselines)
    dump(
        ROOT / "removals/result.json",
        {
            "baselines": len(baselines),
            "removals": len(removals),
            "invalid_outputs": invalid,
            "role_reexecutions": 0,
        },
    )
    removal_hash = seal(ROOT / "removals", {"gold_loaded": False, "role_reexecutions": 0})

    gold_rows = json.loads((GATE6 / "evaluation/evaluation-records.json").read_text())
    gold = {row["task_id"]: row["answer_letter"] for row in gold_rows}
    evaluations = []
    for item in removals:
        hard, soft = evaluate_keep_value(item, gold_answer=gold[item.task_id])
        row = {
            "task_id": item.task_id,
            "role_id": item.removed_role_id,
            "counterfactual_hash": item.canonical_hash,
            "hard": hard.model_dump(mode="json"),
            "soft": soft.model_dump(mode="json"),
        }
        evaluations.append(row)
        dump(ROOT / f"evaluation/records/{item.task_id}-{item.removed_role_id}.json", row)
    nonzero = sum(row["soft"]["soft_keep_value"]["numerator"] != 0 for row in evaluations)
    nonzero_tie = sum(
        row["soft"]["soft_keep_value"]["numerator"] != 0 and row["hard"]["tie_dependent"]
        for row in evaluations
    )
    diverse = 0
    for path in sorted((ROOT / "execution/records").glob("*.json")):
        row = json.loads(path.read_text())
        vectors = [canonical_json_hash(row["roles"][r]["parse"].get("output")) for r in roles]
        diverse += len(set(vectors)) > 1
    summary = {
        "valid_outputs": 42 - invalid,
        "baseline_scorable": sum(v["scorable"] for v in baselines.values()),
        "removal_scorable": len(removals),
        "nonzero_soft": nonzero,
        "nonzero_soft_tie_dependent": nonzero_tie,
        "diverse_tasks": diverse,
        "generation_seconds": elapsed,
    }
    summary["gate_passed"] = (
        invalid == 0
        and len(removals) == 42
        and diverse >= 10
        and nonzero >= 9
        and nonzero_tie < nonzero
        and elapsed < BUDGET
    )
    dump(ROOT / "evaluation/summary.json", summary)
    evaluation_hash = seal(ROOT / "evaluation", {"post_counterfactual_only": True})
    seal(
        ROOT,
        {
            "gate62a_complete": True,
            "gate_passed": summary["gate_passed"],
            "execution_hash": execution_hash,
            "removal_hash": removal_hash,
            "evaluation_hash": evaluation_hash,
        },
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
