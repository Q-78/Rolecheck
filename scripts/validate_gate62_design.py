"""CPU-only synthetic validation for the Gate 6.2 design."""

from __future__ import annotations

import json

from rolecheck.hashing import canonical_json_hash
from rolecheck.signal.aggregation import DeterministicScoreAggregator
from rolecheck.signal.models import (
    OptionScoreVector,
    RoleScoreEvidence,
    StructuredRemovalEvaluation,
    StructuredRoleOutput,
)
from rolecheck.signal.verifier import verify_removal


def evidence(role_id: str, scores: dict[str, int]) -> RoleScoreEvidence:
    output = StructuredRoleOutput(
        option_scores=OptionScoreVector(scores=scores), key_evidence=["Synthetic fixture."]
    )
    return RoleScoreEvidence(role_id=role_id, output=output, output_hash=output.canonical_hash)


def main() -> None:
    roles = ["domain_analyst", "elimination_analyst", "verification_analyst"]
    outputs = [
        evidence(roles[0], {"A": 60, "B": 20, "C": 10, "D": 10}),
        evidence(roles[1], {"A": 20, "B": 60, "C": 10, "D": 10}),
        evidence(roles[2], {"A": 30, "B": 20, "C": 40, "D": 10}),
    ]
    task_hash = canonical_json_hash({"task_id": "synthetic-gate62", "options": list("ABCD")})
    aggregator = DeterministicScoreAggregator()
    baseline = aggregator.aggregate(
        task_id="synthetic-gate62",
        task_hash=task_hash,
        option_letters=list("ABCD"),
        required_role_ids=roles,
        role_outputs=outputs,
    )
    retained = roles[1:]
    removal = aggregator.aggregate(
        task_id="synthetic-gate62",
        task_hash=task_hash,
        option_letters=list("ABCD"),
        required_role_ids=retained,
        role_outputs=outputs[1:],
    )
    artifact = StructuredRemovalEvaluation(
        task_id="synthetic-gate62",
        task_hash=task_hash,
        removed_role_id=roles[0],
        baseline_input_hash=canonical_json_hash(
            {item.role_id: item.output_hash for item in outputs}
        ),
        removal_input_hash=canonical_json_hash(
            {item.role_id: item.output_hash for item in outputs[1:]}
        ),
        baseline_role_output_hashes={item.role_id: item.output_hash for item in outputs},
        removal_role_output_hashes={item.role_id: item.output_hash for item in outputs[1:]},
        baseline=baseline,
        removal=removal,
        retained_role_ids=retained,
    )
    print(json.dumps(verify_removal(artifact), sort_keys=True))


if __name__ == "__main__":
    main()
