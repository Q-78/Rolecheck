"""YAML configuration loading with explicit, limited environment overrides."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from rolecheck.hashing import canonical_json_hash
from rolecheck.schemas import InformationSetting


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ProjectConfig(ConfigModel):
    name: str = "RoleCheck"
    version: str = "0.1.0"
    research_spec_version: str = "v0.2"


class RunConfig(ConfigModel):
    experiment_id: str
    seed: int = Field(ge=0)
    output_dir: Path = Path("outputs/runs")
    overwrite: bool = False
    information_setting: InformationSetting = InformationSetting.STRICT


class LoggingConfig(ConfigModel):
    level: str = "INFO"
    json_lines: bool = False
    filename: str = "rolecheck.log"


class MockRuntimeConfig(ConfigModel):
    enabled: bool = True
    runtime_id: str = "mock-runtime-v1"
    synthetic_latency_ms_per_role: float = Field(default=1.0, ge=0.0)
    synthetic_tokens_per_role: int = Field(default=0, ge=0)


class AppConfig(ConfigModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    run: RunConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    mock_runtime: MockRuntimeConfig = Field(default_factory=MockRuntimeConfig)

    def stable_hash(self) -> str:
        """Hash the validated configuration using canonical JSON."""

        return canonical_json_hash(self.model_dump(mode="json"))


def _apply_environment_overrides(raw: dict[str, object]) -> dict[str, object]:
    run_raw = raw.get("run", {})
    logging_raw = raw.get("logging", {})

    run = run_raw.copy() if isinstance(run_raw, dict) else {}
    logging = logging_raw.copy() if isinstance(logging_raw, dict) else {}

    if seed := os.getenv("ROLECHECK_SEED"):
        run["seed"] = int(seed)
    if output_dir := os.getenv("ROLECHECK_OUTPUT_DIR"):
        run["output_dir"] = output_dir
    if log_level := os.getenv("ROLECHECK_LOG_LEVEL"):
        logging["level"] = log_level

    updated = dict(raw)
    updated["run"] = run
    updated["logging"] = logging
    return updated


def load_config(path: str | Path) -> AppConfig:
    """Load and validate an application configuration from YAML."""

    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"configuration file not found: {config_path}")

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise ValueError("top-level YAML configuration must be a mapping")

    raw: dict[str, object] = {str(key): value for key, value in loaded.items()}
    return AppConfig.model_validate(_apply_environment_overrides(raw))
