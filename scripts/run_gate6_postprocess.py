from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from datasets import DatasetDict, load_from_disk

from rolecheck.benchmark.mmlu_pro import (
    MMLU_PRO_REVISION,
    MMLUProBenchmarkAdapter,
    MMLUProEvaluationRecord,
    MMLUProTaskRecord,
)
from rolecheck.hashing import canonical_json_hash, derive_seed, role_contract_hash
from rolecheck.manifest import create_manifest
from rolecheck.pilot import PILOT_EXPERIMENT_SEED, DeterministicMajorityAggregator, build_pilot_team
from rolecheck.pilot.gate6 import assign_removal_target, score_sealed_outputs
from rolecheck.runtime import ParallelRemovalRunner
from rolecheck.schemas import (
    ExecutionRecord,
    ExecutionStatus,
    RoleExecutionMetrics,
    SeedBundle,
    TaskSpec,
)

ROOT = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-6-controlled-pilot-v0.2")
EXECUTION = ROOT / "execution"
REMOVALS = ROOT / "removals"
EVALUATION = ROOT / "evaluation"
GATE3 = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-3-manifest-v0.1")
DATASET = Path("/data/qhy/rolecheck_server/datasets") / f"mmlu-pro-{MMLU_PRO_REVISION}"
EXPERIMENT_ID = "rolecheck-server-pilot-v0.3-gate6"
BASE_COMMIT = "e10bb09f33b76b34923c9e4b96b473feebd7cb09"
EXPECTED_TASKS = 56


def dump(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def file_inventory(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact-manifest.json"
    ]


def verify_execution_seal() -> tuple[dict[str, object], dict[str, object]]:
    result = json.loads((EXECUTION / "execution-result.json").read_text())
    seal = json.loads((EXECUTION / "artifact-manifest.json").read_text())
    if result["status"] != "SUCCEEDED" or result["task_records"] != EXPECTED_TASKS:
        raise RuntimeError("Gate 6 baseline execution is not complete")
    if result["role_executions"] != EXPECTED_TASKS * 3 or not seal["model_unloaded"]:
        raise RuntimeError("Gate 6 baseline execution seal is invalid")
    actual = file_inventory(EXECUTION)
    if actual != seal["files"] or canonical_json_hash(actual) != seal["files_hash"]:
        raise RuntimeError("Gate 6 baseline artifact seal mismatch")
    source = json.loads((GATE3 / "pilot-56-manifest.json").read_text())
    if len(source["tasks"]) != EXPECTED_TASKS:
        raise RuntimeError("Gate 6 source manifest must contain 56 tasks")
    return result, source


def checkpoint_record(
    checkpoint: dict[str, object], task: TaskSpec, team: object
) -> ExecutionRecord:
    role_outputs = dict(checkpoint["role_outputs"])
    role_hashes = dict(checkpoint["role_output_hashes"])
    stored_hash = str(checkpoint["checkpoint_hash"])
    unhashed = dict(checkpoint)
    del unhashed["checkpoint_hash"]
    if canonical_json_hash(unhashed) != stored_hash:
        raise RuntimeError(f"checkpoint hash mismatch: {task.task_id}")
    role_ids = list(team.execution_protocol.execution_order)
    for role_id in role_ids:
        if canonical_json_hash(role_outputs[role_id]) != role_hashes[role_id]:
            raise RuntimeError(f"role-output hash mismatch: {task.task_id}/{role_id}")
    metrics = {
        role_id: RoleExecutionMetrics(
            token_cost=float(
                role_outputs[role_id]["input_token_count"]
                + role_outputs[role_id]["output_token_count"]
            ),
            latency_ms=float(role_outputs[role_id]["latency_ms"]),
        )
        for role_id in role_ids
    }
    seeds = SeedBundle(
        experiment_seed=PILOT_EXPERIMENT_SEED,
        task_seed=derive_seed(PILOT_EXPERIMENT_SEED, "task", task.task_id),
        role_seeds={
            role_id: derive_seed(PILOT_EXPERIMENT_SEED, "role", role_id) for role_id in role_ids
        },
        aggregation_seed=derive_seed(PILOT_EXPERIMENT_SEED, "aggregation", team.team_id),
    )
    return ExecutionRecord(
        run_id="gate6-"
        + canonical_json_hash(
            {
                "experiment_id": EXPERIMENT_ID,
                "task_id": task.task_id,
                "checkpoint_hash": stored_hash,
            }
        ).removeprefix("sha256:")[:24],
        experiment_id=EXPERIMENT_ID,
        task_id=task.task_id,
        team_id=team.team_id,
        team_version=team.team_version,
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        started_at=datetime.fromisoformat(str(checkpoint["task_started_at"])),
        finished_at=datetime.fromisoformat(str(checkpoint["task_finished_at"])),
        status=ExecutionStatus.SUCCEEDED,
        seeds=seeds,
        role_outputs=role_outputs,
        role_output_hashes=role_hashes,
        role_metrics=metrics,
        final_output=checkpoint["aggregation"],
        token_cost=sum(metric.token_cost for metric in metrics.values()),
        latency_ms=sum(metric.latency_ms for metric in metrics.values()),
        mock=False,
    )


def gold_letter(row: dict[str, object]) -> tuple[int, str]:
    answer = row.get("answer")
    answer_index = row.get("answer_index")
    if isinstance(answer, str) and len(answer.strip()) == 1 and answer.strip() in "ABCDEFGHIJ":
        letter = answer.strip()
        index = ord(letter) - ord("A")
    elif isinstance(answer_index, int):
        index = answer_index
        letter = chr(ord("A") + index)
    elif isinstance(answer, int):
        index = answer
        letter = chr(ord("A") + index)
    else:
        raise RuntimeError("unsupported pinned MMLU-Pro answer representation")
    if isinstance(answer_index, int) and answer_index != index:
        raise RuntimeError("MMLU-Pro answer fields disagree")
    return index, letter


def main() -> None:
    if REMOVALS.exists() or EVALUATION.exists():
        raise RuntimeError("Gate 6 postprocess target already exists")
    execution_result, source = verify_execution_seal()
    team = build_pilot_team()
    aggregator = DeterministicMajorityAggregator()
    role_ids = list(team.execution_protocol.execution_order)
    manifest = create_manifest(
        experiment_id=EXPERIMENT_ID,
        git_commit=BASE_COMMIT,
        dataset_revision=MMLU_PRO_REVISION,
        task_split_hash=str(source["subset"]["manifest_hash"]),
        initializer_id="manual-frozen-pilot-v0.3",
        team_config_hash=canonical_json_hash(team.model_dump(mode="json")),
        runtime_id="rolecheck.transformers.qwen3_8b.single_gpu",
        runtime_version="v0.3",
        protocol_id=team.execution_protocol.protocol_id,
        removal_protocol_id=team.removal_protocol.removal_protocol_id,
        seed=PILOT_EXPERIMENT_SEED,
        config_hash=str(execution_result["plan_hash"]),
        model_versions={agent.agent_id: agent.model_id for agent in team.agents},
        tool_hashes={
            tool_id: canonical_json_hash({"tool_id": tool_id})
            for agent in team.agents
            for tool_id in agent.tool_ids
        },
        prompt_hashes={role.role_id: role.prompt_hash for role in team.roles},
        role_contract_hashes={
            role.role_id: role_contract_hash(role.model_dump(mode="json")) for role in team.roles
        },
        aggregator_id=aggregator.identity.aggregator_id,
        aggregator_version=aggregator.identity.aggregator_version,
        aggregator_config_hash=aggregator.identity.config_hash,
        mock=False,
        notes=[
            "Gate 6 removal; zero role re-execution; post-seal evaluation only."
        ],
    )
    REMOVALS.mkdir()
    (REMOVALS / "records").mkdir()
    dump(REMOVALS / "experiment-manifest.json", manifest.model_dump(mode="json"))
    tasks = [TaskSpec.model_validate(payload) for payload in source["tasks"]]
    checkpoint_paths = sorted((EXECUTION / "checkpoints").glob("*.json"))
    if len(checkpoint_paths) != EXPECTED_TASKS:
        raise RuntimeError("Gate 6 requires exactly 56 sealed checkpoints")
    checkpoint_by_task = {}
    for path in checkpoint_paths:
        payload = json.loads(path.read_text())
        checkpoint_by_task[str(payload["task_id"])] = payload
    baseline_answers: dict[str, str | None] = {}
    removal_answers: dict[str, str | None] = {}
    assignments: list[dict[str, object]] = []
    for index, task in enumerate(tasks):
        baseline = checkpoint_record(checkpoint_by_task[task.task_id], task, team)
        target = assign_removal_target(
            task_id=task.task_id, role_ids=role_ids, experiment_seed=PILOT_EXPERIMENT_SEED
        )
        outcome = ParallelRemovalRunner().run(
            baseline=baseline,
            task=task,
            team=team,
            target_role_id=target,
            output_team_version=f"{team.team_version}-gate6-remove-{target}",
            manifest=manifest,
            aggregator=aggregator,
            coverage_gap_detected=False,
            joint_intervention_required=False,
            contract_topology_sufficient=True,
        )
        if not outcome.record.safety.valid or outcome.record.reexecuted_role_ids:
            raise RuntimeError(f"unsafe controlled removal: {task.task_id}")
        record_payload = outcome.record.model_dump(mode="json")
        intervention_payload = outcome.intervention.model_dump(mode="json")
        dump(
            REMOVALS / "records" / f"{index:02d}-{task.task_id}.json",
            {
                "record": record_payload,
                "intervention": intervention_payload,
                "record_hash": canonical_json_hash(record_payload),
                "intervention_hash": canonical_json_hash(intervention_payload),
            },
        )
        baseline_output = baseline.final_output
        removal_output = outcome.record.removal_aggregation.final_output
        baseline_answers[task.task_id] = baseline_output.get("selected_answer")
        removal_answers[task.task_id] = removal_output.get("selected_answer")
        assignments.append(
            {
                "task_id": task.task_id,
                "target_role_id": target,
                "reused_role_ids": outcome.record.reused_role_ids,
                "reexecuted_role_ids": outcome.record.reexecuted_role_ids,
                "safe": outcome.record.safety.valid,
            }
        )
    summary = {
        "status": "SUCCEEDED",
        "task_count": len(assignments),
        "controlled_removals": len(assignments),
        "maximum_removals_per_task": 1,
        "role_reexecutions": 0,
        "all_safety_reports_valid": all(item["safe"] for item in assignments),
        "assignments": assignments,
        "evaluated": False,
        "model_loaded": False,
    }
    dump(REMOVALS / "removal-result.json", summary)
    removal_files = file_inventory(REMOVALS)
    dump(
        REMOVALS / "artifact-manifest.json",
        {
            "files": removal_files,
            "files_hash": canonical_json_hash(removal_files),
            "execution_seal_verified": True,
            "model_loaded": False,
            "evaluated": False,
        },
    )

    # Evaluation-only data is first loaded after execution and removal artifacts are sealed.
    dataset = load_from_disk(str(DATASET))
    if not isinstance(dataset, DatasetDict) or "test" not in dataset:
        raise RuntimeError("pinned MMLU-Pro test split unavailable")
    selected_ids = set(baseline_answers)
    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    gold: dict[str, str] = {}
    evaluation_records = []
    for index, row in enumerate(dataset["test"]):
        source_id = f"test:{row['question_id']}" if "question_id" in row else f"test:{index}"
        conversion = adapter.convert(
            MMLUProTaskRecord(
                source_record_id=source_id,
                question=row["question"],
                options=tuple(row["options"]),
                category=row["category"],
            )
        )
        if conversion.task is None or conversion.task.task_id not in selected_ids:
            continue
        answer_index, answer_letter = gold_letter(dict(row))
        record = MMLUProEvaluationRecord(
            task_id=conversion.task.task_id,
            answer_index=answer_index,
            answer_letter=answer_letter,
            gold_answer=answer_letter,
            reference_chain_of_thought=None,
        )
        evaluation_records.append(record.model_dump(mode="json"))
        gold[record.task_id] = record.answer_letter
    scored = score_sealed_outputs(
        baseline_answers=baseline_answers,
        removal_answers=removal_answers,
        gold_answers=gold,
    )
    EVALUATION.mkdir()
    dump(EVALUATION / "evaluation-records.json", evaluation_records)
    dump(
        EVALUATION / "evaluation-result.json",
        {
            **scored,
            "execution_artifacts_sealed_before_evaluation": True,
            "removal_artifacts_sealed_before_evaluation": True,
            "predictor_fitted": False,
            "repairer_run": False,
            "defect_injection_run": False,
        },
    )
    evaluation_files = file_inventory(EVALUATION)
    dump(
        EVALUATION / "artifact-manifest.json",
        {
            "files": evaluation_files,
            "files_hash": canonical_json_hash(evaluation_files),
            "post_execution_only": True,
            "model_loaded": False,
        },
    )
    root_files = file_inventory(ROOT)
    dump(
        ROOT / "artifact-manifest.json",
        {
            "files": root_files,
            "files_hash": canonical_json_hash(root_files),
            "gate6_complete": True,
            "model_unloaded_before_evaluation": True,
        },
    )
    print(json.dumps(scored, sort_keys=True))


if __name__ == "__main__":
    main()
