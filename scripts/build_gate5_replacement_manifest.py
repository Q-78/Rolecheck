from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from datasets import DatasetDict, load_from_disk

from rolecheck.benchmark.gate3 import Gate3SubsetManifest, audit_preexecution_payload
from rolecheck.benchmark.mmlu_pro import (
    MMLU_PRO_DATASET_ID,
    MMLU_PRO_REVISION,
    MMLUProBenchmarkAdapter,
    MMLUProTaskRecord,
)
from rolecheck.hashing import canonical_json_hash

DATASET_DIR = Path("/data/qhy/rolecheck_server/datasets") / f"mmlu-pro-{MMLU_PRO_REVISION}"
OUTPUT = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-3-manifest-v0.1")
FAILED_TASK_ID = "mmlu-pro-1cbdceede7c09ce4321f6812"
FAILED_DOMAIN = "business"
SEED = 2026080301


def dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def digest(path: Path) -> str:
    v = hashlib.sha256()
    v.update(path.read_bytes())
    return v.hexdigest()


def make_manifest(name: str, pairs: list[tuple[str, str]]) -> Gate3SubsetManifest:
    ids = [x for x, _ in pairs]
    domains = [x for _, x in pairs]
    counts = dict(sorted(Counter(domains).items()))
    p = {
        "name": name,
        "seed": SEED,
        "task_ids": ids,
        "task_domains": domains,
        "task_ids_hash": canonical_json_hash(ids),
        "domain_counts": counts,
    }
    p["manifest_hash"] = canonical_json_hash(p)
    return Gate3SubsetManifest.model_validate(p)


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("Pilot v0.3 manifest target already exists")
    dataset = load_from_disk(str(DATASET_DIR))
    if not isinstance(dataset, DatasetDict) or "test" not in dataset:
        raise RuntimeError("pinned dataset unavailable")
    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    task_by_id = {}
    by_domain: dict[str, list[str]] = defaultdict(list)
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
        if not conversion.accepted or conversion.task is None:
            raise RuntimeError(f"valid record rejected: {source_id}")
        task = conversion.task
        audit_preexecution_payload(task.model_dump(mode="json"))
        task_by_id[task.task_id] = task
        by_domain[str(task.public_metadata["category"])].append(task.task_id)
    ordered = {
        domain: sorted(
            ids,
            key=lambda task_id: (
                canonical_json_hash({"seed": SEED, "domain": domain, "task_id": task_id}),
                task_id,
            ),
        )
        for domain, ids in by_domain.items()
    }
    if ordered[FAILED_DOMAIN][0] != FAILED_TASK_ID:
        raise RuntimeError("failed task is not original canonical selection")
    replacement = ordered[FAILED_DOMAIN][1]
    small = make_manifest(
        "pilot-14", [(ordered[d][1 if d == FAILED_DOMAIN else 0], d) for d in sorted(ordered)]
    )
    large = make_manifest(
        "pilot-56",
        [
            (task_id, d)
            for d in sorted(ordered)
            for task_id in (ordered[d][1:5] if d == FAILED_DOMAIN else ordered[d][:4])
        ],
    )
    if not set(small.task_ids).issubset(large.task_ids):
        raise RuntimeError("Pilot14 is not a Pilot56 subset")
    OUTPUT.mkdir(parents=True)
    for subset in (small, large):
        selected = [task_by_id[x].model_dump(mode="json") for x in subset.task_ids]
        payload = {
            "dataset_id": MMLU_PRO_DATASET_ID,
            "dataset_revision": MMLU_PRO_REVISION,
            "selection_revision": "posthoc-systematic-nontermination-replacement-v0.1",
            "excluded_task_id": FAILED_TASK_ID,
            "replacement_task_id": replacement,
            "replacement_rule": "next_same_domain_task_in_original_canonical_order",
            "subset": subset.model_dump(mode="json"),
            "tasks": selected,
            "tasks_hash": canonical_json_hash(selected),
        }
        audit_preexecution_payload(payload)
        dump(OUTPUT / f"{subset.name}-manifest.json", payload)
    files = [
        {"path": p.name, "size": p.stat().st_size, "sha256": digest(p)}
        for p in sorted(OUTPUT.iterdir())
        if p.is_file()
    ]
    dump(
        OUTPUT / "artifact-manifest.json",
        {
            "files": files,
            "files_hash": canonical_json_hash(files),
            "model_loaded": False,
            "role_outputs_generated": False,
        },
    )
    print(
        json.dumps(
            {
                "replacement_task_id": replacement,
                "pilot14": small.model_dump(mode="json"),
                "pilot56": large.model_dump(mode="json"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
