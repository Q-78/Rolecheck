from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from rolecheck.manifest import create_manifest, write_manifest


def test_manifest_refuses_overwrite(tmp_path: Path) -> None:
    manifest = create_manifest(
        experiment_id="repo-init-test",
        git_commit="not-a-git-repo",
        dataset_revision="not-applicable",
        task_split_hash="not-applicable",
        initializer_id="manual-test",
        runtime_id="mock-runtime-v1",
        protocol_id="parallel-v1",
        removal_protocol_id="parallel-removal-v1",
        seed=7,
        config_hash="sha256:" + "0" * 64,
        mock=True,
    )
    target = write_manifest(manifest, tmp_path)
    assert target.is_file()
    with pytest.raises(FileExistsError):
        write_manifest(manifest, tmp_path)


def test_manifest_is_frozen_and_records_aggregator_identity() -> None:
    manifest = create_manifest(
        experiment_id="frozen-test",
        git_commit="abc",
        dataset_revision="none",
        task_split_hash="none",
        initializer_id="manual",
        runtime_id="mock-runtime-v1",
        protocol_id="parallel-v1",
        removal_protocol_id="parallel-removal-v1",
        seed=1,
        config_hash="sha256:" + "0" * 64,
        tool_hashes={"search": "sha256:" + "1" * 64},
        aggregator_id="fixed-mock-aggregation",
        aggregator_version="v1",
        aggregator_config_hash="sha256:" + "2" * 64,
        predictor_config={"nested": {"thresholds": [0.1, 0.2]}},
        mock=True,
    )
    assert manifest.aggregator_version == "v1"
    with pytest.raises(ValidationError):
        manifest.seed = 2
    with pytest.raises(TypeError):
        manifest.tool_hashes["search"] = "sha256:" + "3" * 64
    nested = manifest.predictor_config["nested"]
    assert isinstance(nested, Mapping)
    with pytest.raises(TypeError):
        nested["thresholds"] = []
