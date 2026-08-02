from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rolecheck.hashing import sha256_text
from rolecheck.schemas import (
    InformationSetting,
    InterventionAction,
    InterventionRecord,
    KeepValueRecord,
    RepairCandidate,
    RoleContract,
)


def test_role_contract_requires_nonempty_responsibilities() -> None:
    prompt = "Do something."
    with pytest.raises(ValidationError):
        RoleContract(
            role_id="empty",
            role_name="Empty",
            source_initializer="test",
            raw_prompt=prompt,
            prompt_hash=sha256_text(prompt),
            goal="Test validation.",
            responsibilities=[],
            outputs=[],
        )


def test_team_factory_builds_valid_team(team_factory: Callable[[], object]) -> None:
    team = team_factory()
    assert team.team_id == "team-test"


def test_repair_candidate_rejects_model_change(
    role_factory: Callable[..., RoleContract],
) -> None:
    candidate_contract = role_factory(
        "solver",
        role_version="v1-r1",
        parent_role_version="v1",
    )
    with pytest.raises(ValidationError, match="forbidden fields"):
        RepairCandidate(
            repair_id="repair-1",
            target_role_id="solver",
            parent_role_version="v1",
            candidate_contract=candidate_contract,
            changed_fields=["model_id"],
            edit_rationale="Forbidden model change.",
            generator_id="test-generator",
            candidate_rank_before_value_prediction=1,
            contract_diff={"model_id": ["old", "new"]},
            compatibility_passed=False,
        )


def test_keep_value_schema_blocks_current_task_leakage() -> None:
    with pytest.raises(ValidationError):
        KeepValueRecord(
            record_id="kv-1",
            experiment_id="exp-1",
            task_id="task-1",
            team_id="team-1",
            role_id="solver",
            information_setting=InformationSetting.STRICT,
            protocol_id="protocol-1",
            removal_protocol_id="removal-1",
            ood_risk=0.1,
            contract_parse_risk=0.1,
            current_task_outputs_used=True,
        )


def test_abstention_must_expose_keep() -> None:
    with pytest.raises(ValidationError, match="abstention"):
        InterventionRecord(
            intervention_id="intervention-1",
            experiment_id="exp-1",
            baseline_run_id="run-1",
            target_role_id="solver",
            action=InterventionAction.REMOVE,
            input_team_version="v1",
            output_team_version="v1",
            removal_safe=True,
            abstained=True,
            created_at=datetime.now(UTC),
        )


def test_remove_requires_no_coverage_gap() -> None:
    with pytest.raises(ValidationError, match="coverage gap"):
        InterventionRecord(
            intervention_id="intervention-2",
            experiment_id="exp-1",
            baseline_run_id="run-1",
            target_role_id="solver",
            action=InterventionAction.REMOVE,
            input_team_version="v1",
            output_team_version="v2",
            removal_safe=True,
            coverage_gap_detected=True,
            created_at=datetime.now(UTC),
        )
