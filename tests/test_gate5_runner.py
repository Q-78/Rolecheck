from __future__ import annotations

import ast
from pathlib import Path


def test_gate5_runner_preserves_frozen_scale_and_limits() -> None:
    tree = ast.parse(Path("scripts/run_gate5_dry_run.py").read_text())
    constants = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id
        in {
            "EXPECTED_TASKS",
            "EXPECTED_ROLES",
            "TIMEOUT_SECONDS",
            "PHYSICAL_GPU_INDEX",
            "PILOT_REVISION",
        }
    }
    assert constants == {
        "TIMEOUT_SECONDS": 180,
        "EXPECTED_TASKS": 14,
        "EXPECTED_ROLES": 42,
        "PHYSICAL_GPU_INDEX": 1,
        "PILOT_REVISION": "v0.3",
    }


def test_replacement_manifest_rule_is_frozen() -> None:
    source = Path("scripts/build_gate5_replacement_manifest.py").read_text()
    assert 'FAILED_TASK_ID = "mmlu-pro-1cbdceede7c09ce4321f6812"' in source
    assert 'FAILED_DOMAIN = "business"' in source
    assert "ordered[FAILED_DOMAIN][1]" in source
    assert '"max_new_tokens": 8192' not in Path("scripts/run_gate5_dry_run.py").read_text()
