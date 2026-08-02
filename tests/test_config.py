from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rolecheck.config import load_config
from rolecheck.schemas import InformationSetting


def test_load_base_config() -> None:
    config = load_config(Path("configs/base.yaml"))
    assert config.run.information_setting is InformationSetting.STRICT
    assert config.mock_runtime.enabled is True
    assert config.stable_hash().startswith("sha256:")


def test_environment_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "run:\n  experiment_id: env-test\n  seed: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROLECHECK_SEED", "42")
    config = load_config(path)
    assert config.run.seed == 42


def test_unknown_config_field_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(
        "run:\n  experiment_id: invalid\n  seed: 1\nunknown_section: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(path)
