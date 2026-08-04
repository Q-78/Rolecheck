"""Independent read-only Gate 6.2A artifact verification."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from rolecheck.hashing import canonical_json_hash
from rolecheck.signal.models import StructuredRemovalEvaluation
from rolecheck.signal.tie_break import deterministic_tie_order

ROOT = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.4/gate-6-2a-v0.1")


def load(p: Path) -> object:
    return json.loads(p.read_text())


def inventory(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": p.relative_to(root).as_posix(),
            "size": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "artifact-manifest.json"
    ]


def check_seal(root: Path) -> dict[str, object]:
    seal = load(root / "artifact-manifest.json")
    assert isinstance(seal, dict)
    files = inventory(root)
    if seal["files"] != files or seal["files_hash"] != canonical_json_hash(files):
        raise RuntimeError(f"seal mismatch:{root}")
    return seal


def main() -> None:
    root = check_seal(ROOT)
    check_seal(ROOT / "execution")
    check_seal(ROOT / "removals")
    check_seal(ROOT / "evaluation")
    executions = sorted((ROOT / "execution/records").glob("*.json"))
    removals = sorted((ROOT / "removals/records").glob("*.json"))
    evaluations = sorted((ROOT / "evaluation/records").glob("*.json"))
    if (len(executions), len(removals), len(evaluations)) != (14, 42, 42):
        raise RuntimeError("artifact count mismatch")
    pairs = set()
    labels = []
    for path in removals:
        raw = load(path)
        assert isinstance(raw, dict)
        item = StructuredRemovalEvaluation.model_validate(raw)
        pair = (item.task_id, item.removed_role_id)
        if pair in pairs:
            raise RuntimeError("duplicate task-role")
        pairs.add(pair)
        for agg in (item.baseline, item.removal):
            totals = {
                o: sum(agg.per_role_scores[r][o] for r in agg.valid_role_ids)
                for o in agg.total_scores
            }
            if totals != agg.total_scores:
                raise RuntimeError("total mismatch")
            if any(
                agg.mean_scores[o].as_fraction() != Fraction(v, len(agg.valid_role_ids))
                for o, v in totals.items()
            ):
                raise RuntimeError("mean mismatch")
            order, digest = deterministic_tie_order(
                list(totals),
                task_id=item.task_id,
                task_hash=item.task_hash,
                aggregator_version=agg.aggregator_version,
                namespace="rolecheck.gate62.tie-break.v0.1",
            )
            if order != agg.tie_break_order or digest != agg.tie_break_order_hash:
                raise RuntimeError("tie mismatch")
    for path in evaluations:
        row = load(path)
        assert isinstance(row, dict)
        labels.append(row)
        if "gold" in json.dumps(load(ROOT / "removals/records" / path.name)):
            raise RuntimeError("Gold leakage")
    summary = load(ROOT / "evaluation/summary.json")
    assert isinstance(summary, dict)
    nonzero = Counter(row["soft"]["soft_keep_value"]["numerator"] != 0 for row in labels)[True]
    if nonzero != summary["nonzero_soft"]:
        raise RuntimeError("summary mismatch")
    print(
        json.dumps(
            {
                "status": "PASSED",
                "tasks": 14,
                "removals": 42,
                "root_hash": root["files_hash"],
                "gate_passed": summary["gate_passed"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
