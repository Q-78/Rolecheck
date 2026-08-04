from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from datasets import DatasetDict, load_dataset, load_dataset_builder, load_from_disk
from huggingface_hub import hf_hub_download

from rolecheck.benchmark.gate3 import audit_preexecution_payload, build_gate3_subset_manifests
from rolecheck.benchmark.mmlu_pro import (
    MMLU_PRO_DATASET_ID,
    MMLU_PRO_REVISION,
    MMLUProBenchmarkAdapter,
    MMLUProTaskRecord,
)
from rolecheck.hashing import canonical_json_hash

DATA_ROOT = Path("/data/qhy/rolecheck_server/datasets")
ARTIFACT_ROOT = Path("/data/qhy/rolecheck_server/artifacts/pilot-v0.1")
CACHE_ROOT = Path("/data/qhy/rolecheck_server/cache/huggingface")
DATASET_DIR = DATA_ROOT / f"mmlu-pro-{MMLU_PRO_REVISION}"
GATE3_DIR = ARTIFACT_ROOT / "gate-3-v0.2"
BASE_COMMIT = "27b3d7399df0d043bd6431802380b687251325fe"
SUPERSEDES_ARTIFACT_HASH = "sha256:441fc16a46861f6785e47b7ab225ff6477273cd4a05a5e34cae35868be727abd"


def dump_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_manifest(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def main() -> None:
    if GATE3_DIR.exists():
        raise RuntimeError("Gate 3 v0.2 target already exists; refusing to overwrite")
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()

    builder = load_dataset_builder(
        MMLU_PRO_DATASET_ID, revision=MMLU_PRO_REVISION, cache_dir=str(CACHE_ROOT)
    )
    card_path = Path(
        hf_hub_download(
            repo_id=MMLU_PRO_DATASET_ID,
            filename="README.md",
            repo_type="dataset",
            revision=MMLU_PRO_REVISION,
            cache_dir=str(CACHE_ROOT),
        )
    )
    card_text = card_path.read_text(encoding="utf-8")
    card_match = re.search(r"(?m)^license:\s*([^\s]+)\s*$", card_text)
    license_value = (builder.info.license or (card_match.group(1) if card_match else "")).strip()
    if license_value.lower() != "mit":
        raise RuntimeError(f"unexpected dataset license: {license_value!r}")
    if DATASET_DIR.exists():
        dataset = load_from_disk(str(DATASET_DIR))
    else:
        dataset = load_dataset(
            MMLU_PRO_DATASET_ID, revision=MMLU_PRO_REVISION, cache_dir=str(CACHE_ROOT)
        )
        if not isinstance(dataset, DatasetDict):
            raise RuntimeError("pinned MMLU-Pro must materialize as DatasetDict")
        dataset.save_to_disk(str(DATASET_DIR))
    if not isinstance(dataset, DatasetDict) or "test" not in dataset:
        raise RuntimeError("pinned MMLU-Pro must contain a test split")

    adapter = MMLUProBenchmarkAdapter(dataset_revision=MMLU_PRO_REVISION)
    tasks = []
    task_by_id = {}
    for index, row in enumerate(dataset["test"]):
        # Evaluation-only columns are deliberately never read here.
        source_id = f"test:{row['question_id']}" if "question_id" in row else f"test:{index}"
        record = MMLUProTaskRecord(
            source_record_id=source_id,
            question=row["question"],
            options=tuple(row["options"]),
            category=row["category"],
        )
        conversion = adapter.convert(record)
        if not conversion.accepted or conversion.task is None:
            raise RuntimeError(f"valid record rejected: {source_id}")
        tasks.append(conversion.task)
        task_by_id[conversion.task.task_id] = conversion.task
    small, large = build_gate3_subset_manifests(tasks)
    code_identity = {
        "subset_module_sha256": sha256_file(
            Path(build_gate3_subset_manifests.__code__.co_filename)
        ),
        "materializer_sha256": sha256_file(Path(__file__)),
    }

    GATE3_DIR.mkdir()
    selected_payloads = {}
    for manifest in (small, large):
        task_payloads = [
            task_by_id[task_id].model_dump(mode="json") for task_id in manifest.task_ids
        ]
        payload = {
            "dataset_id": MMLU_PRO_DATASET_ID,
            "dataset_revision": MMLU_PRO_REVISION,
            "base_commit": BASE_COMMIT,
            "code_identity": code_identity,
            "adapter": adapter.identity.model_dump(mode="json"),
            "subset": manifest.model_dump(mode="json"),
            "tasks": task_payloads,
            "tasks_hash": canonical_json_hash(task_payloads),
        }
        audit_preexecution_payload(payload)
        selected_payloads[manifest.name] = payload
        dump_json(GATE3_DIR / f"{manifest.name}-manifest.json", payload)

    dataset_files = file_manifest(DATASET_DIR)
    inventory = {
        "dataset_id": MMLU_PRO_DATASET_ID,
        "requested_revision": MMLU_PRO_REVISION,
        "base_commit": BASE_COMMIT,
        "code_identity": code_identity,
        "supersedes_artifact_files_hash": SUPERSEDES_ARTIFACT_HASH,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "license": license_value,
        "license_source": "pinned_dataset_card_front_matter",
        "dataset_card_sha256": sha256_file(card_path),
        "split_names": sorted(dataset.keys()),
        "row_counts": {name: len(split) for name, split in sorted(dataset.items())},
        "features": {name: split.features.to_dict() for name, split in sorted(dataset.items())},
        "dataset_directory": str(DATASET_DIR),
        "dataset_files": dataset_files,
        "dataset_files_hash": canonical_json_hash(dataset_files),
        "subset_manifest_hashes": {
            name: payload["subset"]["manifest_hash"] for name, payload in selected_payloads.items()
        },
        "gold_leakage_audit": "PASS",
        "model_loaded": False,
        "role_outputs_generated": False,
    }
    dump_json(GATE3_DIR / "dataset-inventory.json", inventory)
    artifacts = file_manifest(GATE3_DIR)
    dump_json(
        GATE3_DIR / "gate3-artifacts.json",
        {"files": artifacts, "files_hash": canonical_json_hash(artifacts)},
    )
    print(json.dumps(inventory, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        abort_dir = ARTIFACT_ROOT / "gate-3-abort"
        abort_dir.mkdir(parents=True, exist_ok=True)
        dump_json(
            abort_dir / "abort.json",
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "dataset_revision": MMLU_PRO_REVISION,
                "base_commit": BASE_COMMIT,
            },
        )
        raise
