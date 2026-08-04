# RoleCheck Gate 3 Benchmark Freeze v0.2

**Status:** Gate 3 artifact candidate awaiting independent review. Gate 4 has
not started and no model load or role execution is authorized by this file.

**Approved:** 2026-08-04, after PR #8 merged at
`27b3d7399df0d043bd6431802380b687251325fe`.

## Frozen source

- dataset: `TIGER-Lab/MMLU-Pro`;
- revision: `b189ec765aa7ed75c8acfea42df31fdae71f97be`;
- license: `mit`, read from the pinned dataset-card front matter;
- dataset-card SHA-256:
  `4bd710f67da3fa359a33edce1b4b5816b3de416c823c2624ba5e89c2557d2a47`;
- splits: `test` (12,032 rows), `validation` (70 rows).

The materialized dataset remains outside Git at
`/data/qhy/rolecheck_server/datasets/mmlu-pro-b189ec765aa7ed75c8acfea42df31fdae71f97be`.
Its full file inventory hash is
`sha256:767a91b009ecc8ea260a70ad10950aa33557c19421af1750895fc9c8e3f713d9`.

## Label-blind Pilot subsets

Selection used only the frozen seed `2026080301`, category, and the
content-addressed label-free TaskSpec identity. It did not read answer,
answer-index, gold, label, rationale, or chain-of-thought fields.

- 14-task manifest: one task per each of 14 domains,
  `sha256:09a3cad7aa615aa99a5e353ee18b9137f906fc48d5e9642257472375b3399b62`;
- 56-task manifest: four tasks per each of 14 domains,
  `sha256:c3053f881ca4ec1c0b150055d7cea865985e13ba992cd5ad51cbdddffdaf0a5b`;
- the 14-task set is a strict subset of the 56-task set.

This freeze supersedes the v0.1 artifact inventory
`sha256:441fc16a46861f6785e47b7ab225ff6477273cd4a05a5e34cae35868be727abd`,
which lacked execution-code identity and task-to-domain bindings.

The v0.2 manifests and inventory remain outside Git at
`/data/qhy/rolecheck_server/artifacts/pilot-v0.1/gate-3-v0.2`. The artifact-file
inventory hash is
`sha256:d792508bcae6acf71cd7fb56d7687ba82b1b52d0fd7b32c160ef4dd317a2597d`.

## Independent verification

The v0.2 artifacts bind the executed materializer as
`sha256:07297a5a8d933cf93c9baaf3dea5c975135307385a5449fb5b943cf5797b5619`
and subset module as
`sha256:8484a7e28ddfacb470100cbf20bef5142dd40f7603b581b1df7086a8bafb07f6`.
Each task ID is positionally bound to its domain.

An independent verifier re-read every dataset and Gate 3 artifact file,
recomputed sizes and SHA-256 values, validated both strict Pydantic manifests,
confirmed 14-domain balance and 14-within-56 nesting, and recursively scanned
all pre-execution payload keys for evaluation-only fields. Result: `PASS`.

The inventory explicitly records `model_loaded=false` and
`role_outputs_generated=false`. Two earlier controlled aborts were retained in
`gate-3-abort`: direct Hub connectivity timed out, then the Dataset builder
reported an empty license field. Materialization succeeded only after using
the configured proxy and resolving MIT from the same pinned dataset card.

## Hard stop

Do not load Qwen3-8B, run a one-task smoke test, generate role outputs, execute
baseline/removal/replay conditions, or evaluate answers. Those actions belong
to Gate 4 or later and require separate review and explicit approval.
