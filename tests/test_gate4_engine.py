from __future__ import annotations

from rolecheck.pilot import required_generation_engine_identity
from rolecheck.pilot.transformers_engine import Qwen3SingleGpuGenerationEngine


def test_gate4_engine_exposes_frozen_identity_without_loading_model() -> None:
    engine = object.__new__(Qwen3SingleGpuGenerationEngine)

    assert engine.identity == required_generation_engine_identity()
