"""Read-only Gate 6 audit and deterministic exhaustive response-drop analysis."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, cast

from rolecheck.analysis.models import EvaluatedRemovalRecord, ExhaustiveRemovalRecord
from rolecheck.analysis.statistics import bootstrap_mean_ci, exact_mcnemar
from rolecheck.benchmark.gate3 import audit_preexecution_payload
from rolecheck.hashing import canonical_json_hash, derive_seed
from rolecheck.pilot import PILOT_EXPERIMENT_SEED, DeterministicMajorityAggregator, build_pilot_team
from rolecheck.pilot.models import MajorityVoteResult, PilotRoleOutput
from rolecheck.runtime.interfaces import AggregationRequest, FrozenRoleResponse
from rolecheck.schemas import TaskSpec

ANALYSIS_VERSION = "v0.1"
ANALYSIS_SEED = 6101
EXPECTED_ROLES = ("domain_analyst", "elimination_analyst", "verification_analyst")
EXPECTED_HASHES = {
    "root": "sha256:6e8bf5363c7cbc420dacc91fd9e7a67dba3581d48407197d7a2045914bc394e5",
    "pilot56": "sha256:5ad1b96bd7e28e4fa22131cfb518d3a3ecb87d983a1aa711c0b77fc0707e785a",
    "execution": "sha256:cbb0332c7861252f158a1ba9fd30bf12b0a09c83831f0d3d8101c13e9b6f1d3b",
    "removals": "sha256:b299840a31eee90a56f9f8b5db92b6dc4a73eb36a55759307bcb13328e53b173",
    "evaluation": "sha256:c3ab66bb924a8f3b8c80d0032dc6da79f7f70940185de2bf7b637f5c6f9a7070",
}


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _dump(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_inventory(root: Path) -> list[dict[str, object]]:
    """Reproduce the Gate 6 inventory convention."""
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": _digest(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact-manifest.json"
    ]


def _seal(root: Path, extra: Mapping[str, object]) -> dict[str, object]:
    inventory = file_inventory(root)
    seal = {"files": inventory, "files_hash": canonical_json_hash(inventory), **extra}
    _dump(root / "artifact-manifest.json", seal)
    return seal


def _tasks(gate3_root: Path) -> tuple[list[TaskSpec], dict[str, str]]:
    payload = _load(gate3_root / "pilot-56-manifest.json")
    assert isinstance(payload, dict)
    if payload["subset"]["manifest_hash"] != EXPECTED_HASHES["pilot56"]:
        raise RuntimeError("Pilot56 manifest hash mismatch")
    audit_preexecution_payload(payload)
    tasks = [TaskSpec.model_validate(item) for item in payload["tasks"]]
    categories = {task.task_id: str(task.public_metadata["category"]) for task in tasks}
    if len(tasks) != 56 or len(categories) != 56:
        raise RuntimeError("Pilot56 must contain 56 unique tasks")
    return tasks, categories


def _check_seal(root: Path, expected: str) -> dict[str, object]:
    seal = _load(root / "artifact-manifest.json")
    assert isinstance(seal, dict)
    inventory = file_inventory(root)
    if seal.get("files") != inventory or seal.get("files_hash") != canonical_json_hash(inventory):
        raise RuntimeError(f"artifact seal mismatch: {root}")
    if seal["files_hash"] != expected:
        raise RuntimeError(f"frozen files hash mismatch: {root}")
    return seal


def _aggregate(
    task: TaskSpec, outputs: Mapping[str, object], hashes: Mapping[str, str], roles: Sequence[str]
) -> MajorityVoteResult:
    aggregator = DeterministicMajorityAggregator()
    result = aggregator.aggregate(
        AggregationRequest(
            task=task,
            responses=tuple(
                FrozenRoleResponse(role_id=role, output=outputs[role], output_hash=hashes[role])
                for role in roles
            ),
            aggregation_seed=derive_seed(
                PILOT_EXPERIMENT_SEED, "aggregation", build_pilot_team().team_id
            ),
        )
    )
    return MajorityVoteResult.model_validate(result)


def preflight_gate6(source_root: Path, gate3_root: Path) -> dict[str, object]:
    """Strictly recompute Gate 6 identities and replay baseline/original removals."""
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    root_seal = _check_seal(source_root, EXPECTED_HASHES["root"])
    if root_seal.get("gate6_complete") is not True:
        raise RuntimeError("Gate 6 root is not complete")
    _check_seal(source_root / "execution", EXPECTED_HASHES["execution"])
    _check_seal(source_root / "removals", EXPECTED_HASHES["removals"])
    _check_seal(source_root / "evaluation", EXPECTED_HASHES["evaluation"])
    tasks, _ = _tasks(gate3_root)
    task_by_id = {task.task_id: task for task in tasks}
    checkpoints = sorted((source_root / "execution/checkpoints").glob("*.json"))
    if len(checkpoints) != 56:
        raise RuntimeError("expected exactly 56 checkpoints")
    plan = _load(source_root / "execution/execution-plan.json")
    assert isinstance(plan, dict)
    expected_identity = DeterministicMajorityAggregator().identity.model_dump(mode="json")
    if (
        plan.get("aggregator_identity") != expected_identity
        or tuple(plan.get("role_order", [])) != EXPECTED_ROLES
    ):
        raise RuntimeError("frozen aggregator or role identity mismatch")
    seen: set[str] = set()
    checkpoint_by_task: dict[str, dict[str, object]] = {}
    valid = 0
    for path in checkpoints:
        checkpoint = _load(path)
        assert isinstance(checkpoint, dict)
        task_id = str(checkpoint["task_id"])
        if task_id in seen or task_id not in task_by_id:
            raise RuntimeError("duplicate or unknown checkpoint task")
        seen.add(task_id)
        unhashed = dict(checkpoint)
        stored = unhashed.pop("checkpoint_hash")
        if canonical_json_hash(unhashed) != stored:
            raise RuntimeError(f"checkpoint hash mismatch: {task_id}")
        outputs = checkpoint["role_outputs"]
        hashes = checkpoint["role_output_hashes"]
        assert isinstance(outputs, dict) and isinstance(hashes, dict)
        if set(outputs) != set(EXPECTED_ROLES) or set(hashes) != set(EXPECTED_ROLES):
            raise RuntimeError(f"role set mismatch: {task_id}")
        for role in EXPECTED_ROLES:
            PilotRoleOutput.model_validate(outputs[role])
            if canonical_json_hash(outputs[role]) != hashes[role]:
                raise RuntimeError(f"role-output hash mismatch: {task_id}/{role}")
            valid += int(outputs[role]["answer_parse"]["status"] == "valid")
        replay = _aggregate(task_by_id[task_id], outputs, hashes, EXPECTED_ROLES)
        if canonical_json_hash(replay.model_dump(mode="json")) != checkpoint["aggregation_hash"]:
            raise RuntimeError(f"baseline replay mismatch: {task_id}")
        checkpoint_by_task[task_id] = checkpoint
    removal_paths = sorted((source_root / "removals/records").glob("*.json"))
    if len(removal_paths) != 56:
        raise RuntimeError("expected exactly 56 original removals")
    targets: Counter[str] = Counter()
    for path in removal_paths:
        payload = _load(path)
        assert isinstance(payload, dict)
        record = payload["record"]
        task_id = str(record["task_id"])
        target = str(record["target_role_id"])
        targets[target] += 1
        retained = [role for role in EXPECTED_ROLES if role != target]
        if record["reexecuted_role_ids"] or record["reused_role_ids"] != retained:
            raise RuntimeError(f"invalid original removal reuse: {task_id}")
        checkpoint = checkpoint_by_task[task_id]
        checkpoint_outputs = cast(dict[str, object], checkpoint["role_outputs"])
        checkpoint_hashes = cast(dict[str, str], checkpoint["role_output_hashes"])
        if record["removal_aggregation"]["role_output_hashes"] != {
            role: checkpoint_hashes[role] for role in retained
        }:
            raise RuntimeError(f"retained hash mismatch: {task_id}")
        replay = _aggregate(
            task_by_id[task_id],
            checkpoint_outputs,
            checkpoint_hashes,
            retained,
        )
        if (
            canonical_json_hash(replay.model_dump(mode="json"))
            != record["removal_aggregation"]["final_output_hash"]
        ):
            raise RuntimeError(f"original removal replay mismatch: {task_id}")
    if targets != Counter(
        {"domain_analyst": 18, "elimination_analyst": 18, "verification_analyst": 20}
    ):
        raise RuntimeError("original target allocation mismatch")
    return {
        "status": "PASSED",
        "source_root_hash": root_seal["files_hash"],
        "tasks": 56,
        "role_executions": 168,
        "valid_extractions": valid,
        "original_removals": 56,
        "original_target_allocation": dict(sorted(targets.items())),
    }


def _vote_pattern(result: MajorityVoteResult) -> str:
    if result.invalid_role_ids:
        return "contains_invalid"
    counts = sorted(result.vote_counts.values(), reverse=True)
    if counts == [3]:
        return "unanimous"
    if counts == [2, 1]:
        return "2_to_1"
    return "all_different"


def build_counterfactual_records(
    source_root: Path, gate3_root: Path, output_root: Path
) -> dict[str, object]:
    """Create and seal exactly 168 Gold-free offline removal records."""
    if output_root.exists():
        raise FileExistsError(output_root)
    preflight = preflight_gate6(source_root, gate3_root)
    tasks, categories = _tasks(gate3_root)
    output_root.mkdir(parents=True)
    records_dir = output_root / "counterfactual/records"
    records_dir.mkdir(parents=True)
    for task_index, task in enumerate(tasks):
        matches = list((source_root / "execution/checkpoints").glob(f"*-{task.task_id}.json"))
        if len(matches) != 1:
            raise RuntimeError(f"missing or duplicate checkpoint: {task.task_id}")
        checkpoint = _load(matches[0])
        assert isinstance(checkpoint, dict)
        outputs = checkpoint["role_outputs"]
        hashes = checkpoint["role_output_hashes"]
        assert isinstance(outputs, dict) and isinstance(hashes, dict)
        baseline = _aggregate(task, outputs, hashes, EXPECTED_ROLES)
        for role_index, target in enumerate(EXPECTED_ROLES):
            retained = [role for role in EXPECTED_ROLES if role != target]
            removal = _aggregate(task, outputs, hashes, retained)
            record = ExhaustiveRemovalRecord(
                task_id=task.task_id,
                category=categories[task.task_id],
                role_id=target,
                baseline_aggregation_hash=canonical_json_hash(baseline.model_dump(mode="json")),
                exhaustive_removal_aggregation_hash=canonical_json_hash(
                    removal.model_dump(mode="json")
                ),
                retained_role_ids=retained,
                retained_role_output_hashes={role: str(hashes[role]) for role in retained},
                removed_role_output_hash=str(hashes[target]),
                baseline_selected_answer=baseline.selected_answer,
                removed_selected_answer=removal.selected_answer,
                baseline_scorable=baseline.selected_answer is not None,
                removed_scorable=removal.selected_answer is not None,
                baseline_tie_break_applied=baseline.tie_break_applied,
                removal_tie_break_applied=removal.tie_break_applied,
                baseline_strict_majority=baseline.strict_majority,
                removal_strict_majority=removal.strict_majority,
                baseline_invalid_role_ids=baseline.invalid_role_ids,
                removal_invalid_role_ids=removal.invalid_role_ids,
                baseline_vote_pattern=_vote_pattern(baseline),
                protocol_id=build_pilot_team().execution_protocol.protocol_id,
                aggregator_identity=DeterministicMajorityAggregator().identity.model_dump(
                    mode="json"
                ),
                source_gate6_root_hash=str(preflight["source_root_hash"]),
            )
            _dump(
                records_dir / f"{task_index:02d}-{role_index}-{task.task_id}-{target}.json",
                record.model_dump(mode="json"),
            )
    result = {
        "status": "SEALED",
        "record_count": 168,
        "gold_loaded": False,
        "role_reexecutions": 0,
        "preflight": preflight,
    }
    _dump(output_root / "counterfactual/result.json", result)
    seal = _seal(
        output_root / "counterfactual",
        {"record_count": 168, "gold_loaded": False, "role_reexecutions": 0},
    )
    _dump(
        output_root / "analysis-state.json",
        {
            "counterfactual_sealed": True,
            "counterfactual_files_hash": seal["files_hash"],
            "gold_loaded": False,
        },
    )
    return result


Transition = Literal[
    "correct_to_wrong",
    "correct_to_correct",
    "wrong_to_correct",
    "wrong_to_wrong",
    "unscorable",
]


def _transition(baseline: bool | None, removal: bool | None) -> Transition:
    if baseline is None or removal is None:
        return "unscorable"
    return cast(
        Transition,
        {
            (True, False): "correct_to_wrong",
            (True, True): "correct_to_correct",
            (False, True): "wrong_to_correct",
            (False, False): "wrong_to_wrong",
        }[(baseline, removal)],
    )


def _summarize(records: Sequence[dict[str, object]]) -> dict[str, object]:
    transitions = Counter(str(row["outcome_transition"]) for row in records)
    labels = Counter(
        str(row["keep_value"]) if row["keep_value"] is not None else "unscorable" for row in records
    )

    def grouped(field: str) -> dict[str, dict[str, int]]:
        groups: dict[str, Counter[str]] = defaultdict(Counter)
        for row in records:
            key = str(row[field])
            label = str(row["keep_value"]) if row["keep_value"] is not None else "unscorable"
            groups[key][label] += 1
        return {key: dict(sorted(value.items())) for key, value in sorted(groups.items())}

    values = [
        float(cast(int, row["keep_value"])) for row in records if row["keep_value"] is not None
    ]
    return {
        "record_count": len(records),
        "valid_labels": len(values),
        "transitions": dict(sorted(transitions.items())),
        "keep_value_distribution": dict(sorted(labels.items())),
        "keep_value_mean": sum(values) / len(values) if values else None,
        "by_role": grouped("role_id"),
        "by_domain": grouped("category"),
        "exact_mcnemar_p": exact_mcnemar(
            transitions["correct_to_wrong"], transitions["wrong_to_correct"]
        ),
        "bootstrap_mean_ci": bootstrap_mean_ci(values, seed=ANALYSIS_SEED),
        "exploratory": True,
    }


def evaluate_records(source_root: Path, output_root: Path) -> dict[str, object]:
    """Load existing post-execution Gold only after counterfactual sealing."""
    state = _load(output_root / "analysis-state.json")
    assert isinstance(state, dict)
    counterfactual_seal = _check_seal(
        output_root / "counterfactual", str(state["counterfactual_files_hash"])
    )
    if (
        not state.get("counterfactual_sealed")
        or counterfactual_seal.get("gold_loaded") is not False
    ):
        raise RuntimeError("Gold cannot be loaded before counterfactual sealing")
    evaluation_dir = output_root / "evaluation"
    if evaluation_dir.exists():
        raise FileExistsError(evaluation_dir)
    gold_payload = _load(source_root / "evaluation/evaluation-records.json")
    assert isinstance(gold_payload, list)
    gold = {str(row["task_id"]): str(row["answer_letter"]) for row in gold_payload}
    evaluation_dir.mkdir()
    evaluated: list[dict[str, object]] = []
    for path in sorted((output_root / "counterfactual/records").glob("*.json")):
        raw = _load(path)
        assert isinstance(raw, dict)
        record = ExhaustiveRemovalRecord.model_validate(raw)
        baseline_correct = (
            record.baseline_selected_answer == gold[record.task_id]
            if record.baseline_scorable
            else None
        )
        removed_correct = (
            record.removed_selected_answer == gold[record.task_id]
            if record.removed_scorable
            else None
        )
        transition = _transition(baseline_correct, removed_correct)
        keep: Literal[-1, 0, 1] | None = (
            None
            if transition == "unscorable"
            else cast(
                Literal[-1, 0, 1],
                int(bool(baseline_correct)) - int(bool(removed_correct)),
            )
        )
        label = EvaluatedRemovalRecord(
            counterfactual_record_hash=canonical_json_hash(raw),
            task_id=record.task_id,
            category=record.category,
            role_id=record.role_id,
            baseline_correct=baseline_correct,
            removed_correct=removed_correct,
            outcome_transition=transition,
            answer_changed=(record.baseline_selected_answer != record.removed_selected_answer)
            if keep is not None
            else None,
            keep_value=keep,
            tie_dependent=record.baseline_tie_break_applied or record.removal_tie_break_applied,
            invalid_vote_related=bool(
                record.baseline_invalid_role_ids or record.removal_invalid_role_ids
            ),
        )
        payload = label.model_dump(mode="json")
        evaluated.append(payload)
        _dump(evaluation_dir / path.name, payload)
    summary = _summarize(evaluated)
    summary["tie_free_sensitivity"] = _summarize(
        [row for row in evaluated if not row["tie_dependent"]]
    )
    summary["invalid_vote_free_sensitivity"] = _summarize(
        [row for row in evaluated if not row["invalid_vote_related"]]
    )
    _dump(evaluation_dir / "statistics.json", summary)
    _seal(evaluation_dir, {"post_counterfactual_only": True, "analysis_seed": ANALYSIS_SEED})
    _dump(
        output_root / "analysis-state.json",
        {**state, "gold_loaded": True, "evaluation_sealed": True},
    )
    _seal(
        output_root, {"gate6_1a_complete": True, "source_gate6_root_hash": EXPECTED_HASHES["root"]}
    )
    return summary
