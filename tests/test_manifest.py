from __future__ import annotations

from pathlib import Path

import pytest

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
