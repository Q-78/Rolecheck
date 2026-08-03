"""Immutable experiment manifest creation and persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from rolecheck.schemas import RuntimeEnvironmentIdentity


def _deep_freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType(
            {str(key): _deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_deep_thaw(item) for item in value]
    return value


class ExperimentManifest(BaseModel):
    """Minimum reproducibility record required by the frozen research spec."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_id: str
    git_commit: str
    timestamp: datetime
    dataset_revision: str
    task_split_hash: str
    initializer_id: str
    team_config_hash: str | None = None
    runtime_id: str
    runtime_version: str | None = None
    runtime_config_hash: str | None = None
    runtime_environment: RuntimeEnvironmentIdentity | None = None
    protocol_id: str
    removal_protocol_id: str
    model_versions: Mapping[str, str] = Field(default_factory=dict)
    tool_hashes: Mapping[str, str] = Field(default_factory=dict)
    prompt_hashes: Mapping[str, str] = Field(default_factory=dict)
    role_contract_hashes: Mapping[str, str] = Field(default_factory=dict)
    aggregator_id: str | None = None
    aggregator_version: str | None = None
    aggregator_config_hash: str | None = None
    node_executor_id: str | None = None
    node_executor_version: str | None = None
    node_executor_config_hash: str | None = None
    seed: int = Field(ge=0)
    predictor_config: Mapping[str, object] = Field(default_factory=dict)
    calibration_config: Mapping[str, object] = Field(default_factory=dict)
    decision_thresholds: Mapping[str, float] = Field(default_factory=dict)
    config_hash: str
    mock: bool = False
    notes: Sequence[str] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def freeze_nested_values(self) -> ExperimentManifest:
        nested_fields = (
            "model_versions",
            "tool_hashes",
            "prompt_hashes",
            "role_contract_hashes",
            "predictor_config",
            "calibration_config",
            "decision_thresholds",
            "notes",
        )
        for field_name in nested_fields:
            object.__setattr__(
                self,
                field_name,
                _deep_freeze(getattr(self, field_name)),
            )
        return self

    @field_serializer(
        "model_versions",
        "tool_hashes",
        "prompt_hashes",
        "role_contract_hashes",
        "predictor_config",
        "calibration_config",
        "decision_thresholds",
        "notes",
    )
    def serialize_nested_values(self, value: object) -> object:
        return _deep_thaw(value)


def create_manifest(
    *,
    experiment_id: str,
    git_commit: str,
    dataset_revision: str,
    task_split_hash: str,
    initializer_id: str,
    team_config_hash: str | None = None,
    runtime_id: str,
    runtime_version: str | None = None,
    runtime_config_hash: str | None = None,
    runtime_environment: RuntimeEnvironmentIdentity | None = None,
    protocol_id: str,
    removal_protocol_id: str,
    seed: int,
    config_hash: str,
    model_versions: dict[str, str] | None = None,
    tool_hashes: dict[str, str] | None = None,
    prompt_hashes: dict[str, str] | None = None,
    role_contract_hashes: dict[str, str] | None = None,
    aggregator_id: str | None = None,
    aggregator_version: str | None = None,
    aggregator_config_hash: str | None = None,
    node_executor_id: str | None = None,
    node_executor_version: str | None = None,
    node_executor_config_hash: str | None = None,
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
        team_config_hash=team_config_hash,
        runtime_id=runtime_id,
        runtime_version=runtime_version,
        runtime_config_hash=runtime_config_hash,
        runtime_environment=runtime_environment,
        protocol_id=protocol_id,
        removal_protocol_id=removal_protocol_id,
        model_versions=model_versions or {},
        tool_hashes=tool_hashes or {},
        prompt_hashes=prompt_hashes or {},
        role_contract_hashes=role_contract_hashes or {},
        aggregator_id=aggregator_id,
        aggregator_version=aggregator_version,
        aggregator_config_hash=aggregator_config_hash,
        node_executor_id=node_executor_id,
        node_executor_version=node_executor_version,
        node_executor_config_hash=node_executor_config_hash,
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
