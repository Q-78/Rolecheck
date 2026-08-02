"""Immutable experiment manifest creation and persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ExperimentManifest(BaseModel):
    """Minimum reproducibility record required by the frozen research spec."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    git_commit: str
    timestamp: datetime
    dataset_revision: str
    task_split_hash: str
    initializer_id: str
    runtime_id: str
    protocol_id: str
    removal_protocol_id: str
    model_versions: dict[str, str] = Field(default_factory=dict)
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    role_contract_hashes: dict[str, str] = Field(default_factory=dict)
    seed: int = Field(ge=0)
    predictor_config: dict[str, object] = Field(default_factory=dict)
    calibration_config: dict[str, object] = Field(default_factory=dict)
    decision_thresholds: dict[str, float] = Field(default_factory=dict)
    config_hash: str
    mock: bool = False
    notes: list[str] = Field(default_factory=list)


def create_manifest(
    *,
    experiment_id: str,
    git_commit: str,
    dataset_revision: str,
    task_split_hash: str,
    initializer_id: str,
    runtime_id: str,
    protocol_id: str,
    removal_protocol_id: str,
    seed: int,
    config_hash: str,
    model_versions: dict[str, str] | None = None,
    prompt_hashes: dict[str, str] | None = None,
    role_contract_hashes: dict[str, str] | None = None,
    predictor_config: dict[str, object] | None = None,
    calibration_config: dict[str, object] | None = None,
    decision_thresholds: dict[str, float] | None = None,
    mock: bool = False,
    notes: list[str] | None = None,
) -> ExperimentManifest:
    """Create a timestamped, validated manifest."""

    return ExperimentManifest(
        experiment_id=experiment_id,
        git_commit=git_commit,
        timestamp=datetime.now(UTC),
        dataset_revision=dataset_revision,
        task_split_hash=task_split_hash,
        initializer_id=initializer_id,
        runtime_id=runtime_id,
        protocol_id=protocol_id,
        removal_protocol_id=removal_protocol_id,
        model_versions=model_versions or {},
        prompt_hashes=prompt_hashes or {},
        role_contract_hashes=role_contract_hashes or {},
        seed=seed,
        predictor_config=predictor_config or {},
        calibration_config=calibration_config or {},
        decision_thresholds=decision_thresholds or {},
        config_hash=config_hash,
        mock=mock,
        notes=notes or [],
    )


def write_manifest(
    manifest: ExperimentManifest,
    run_dir: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write manifest.json, refusing to overwrite by default."""

    target_dir = Path(run_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "manifest.json"
    if target.exists() and not overwrite:
        raise FileExistsError(f"manifest already exists: {target}")
    target.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return target
