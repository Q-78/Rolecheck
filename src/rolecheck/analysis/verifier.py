"""Independent read-only verifier for Gate 6.1A artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from rolecheck.analysis.models import EvaluatedRemovalRecord, ExhaustiveRemovalRecord
from rolecheck.hashing import canonical_json_hash


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _inventory(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact-manifest.json"
    ]


def verify_analysis(output_root: Path, *, expected_source_hash: str) -> dict[str, object]:
    """Recompute inventories, identities, separation, counts, and label totals."""
    root_seal = _load(output_root / "artifact-manifest.json")
    assert isinstance(root_seal, dict)
    inventory = _inventory(output_root)
    if root_seal.get("files") != inventory or root_seal.get("files_hash") != canonical_json_hash(
        inventory
    ):
        raise RuntimeError("analysis root seal mismatch")
    if root_seal.get("source_gate6_root_hash") != expected_source_hash:
        raise RuntimeError("analysis source hash mismatch")
    state = _load(output_root / "analysis-state.json")
    assert isinstance(state, dict)
    if not state.get("counterfactual_sealed") or not state.get("evaluation_sealed"):
        raise RuntimeError("Gold/counterfactual ordering evidence is incomplete")
    record_paths = sorted((output_root / "counterfactual/records").glob("*.json"))
    if len(record_paths) != 168:
        raise RuntimeError("expected exactly 168 exhaustive records")
    pairs: set[tuple[str, str]] = set()
    counterfactual_hashes: dict[tuple[str, str], str] = {}
    for path in record_paths:
        payload = _load(path)
        assert isinstance(payload, dict)
        record = ExhaustiveRemovalRecord.model_validate(payload)
        pair = (record.task_id, record.role_id)
        if pair in pairs:
            raise RuntimeError("duplicate task-role record")
        pairs.add(pair)
        if len(record.retained_role_ids) != 2 or record.role_id in record.retained_role_ids:
            raise RuntimeError("record does not remove exactly one role")
        if set(record.retained_role_ids) != set(record.retained_role_output_hashes):
            raise RuntimeError("retained role/hash mismatch")
        if record.role_reexecutions != 0 or not record.valid_execution:
            raise RuntimeError("role re-execution or invalid counterfactual detected")
        counterfactual_hashes[pair] = canonical_json_hash(payload)
        forbidden = {
            "gold_answer",
            "baseline_correct",
            "removed_correct",
            "keep_value",
            "outcome_transition",
        }
        if forbidden & set(payload):
            raise RuntimeError("evaluation leaked into counterfactual record")
    labels: list[EvaluatedRemovalRecord] = []
    for path in sorted((output_root / "evaluation").glob("*.json")):
        if path.name in {"statistics.json", "artifact-manifest.json"}:
            continue
        payload = _load(path)
        assert isinstance(payload, dict)
        label = EvaluatedRemovalRecord.model_validate(payload)
        if (
            label.counterfactual_record_hash
            != counterfactual_hashes[(label.task_id, label.role_id)]
        ):
            raise RuntimeError("evaluation does not reference sealed counterfactual")
        labels.append(label)
    if len(labels) != 168:
        raise RuntimeError("expected exactly 168 evaluation records")
    summary = _load(output_root / "evaluation/statistics.json")
    assert isinstance(summary, dict)
    transitions = Counter(label.outcome_transition for label in labels)
    distribution = Counter(
        str(label.keep_value) if label.keep_value is not None else "unscorable" for label in labels
    )
    if summary.get("transitions") != dict(sorted(transitions.items())):
        raise RuntimeError("transition summary mismatch")
    if summary.get("keep_value_distribution") != dict(sorted(distribution.items())):
        raise RuntimeError("label summary mismatch")
    suspicious = {"pytorch_model.bin", "model.safetensors", "token", "secret", "credential"}
    if any(any(marker in str(item["path"]).lower() for marker in suspicious) for item in inventory):
        raise RuntimeError("sensitive/model artifact detected")
    return {
        "status": "PASSED",
        "records": 168,
        "task_role_pairs": 168,
        "root_files_hash": root_seal["files_hash"],
    }
