# RoleCheck Stage 3 Local Scaffold Plan

**Status:** implementation plan, not a frozen research specification

**Authority:** subordinate to all frozen research documents listed in `AGENTS.md`

## 1. Purpose

Stage 3 prepares deterministic task ingestion and runtime adapter boundaries
without downloading a formal Benchmark or invoking a real model. It connects
the already-frozen schemas, normalizer, manifests, and controlled execution
protocols to future empirical infrastructure while keeping all current tests
offline and non-empirical.

Stage 3 does not change the scientific task, intervention space, information
setting, removal semantics, immutable team properties, or leakage rules.

## 2. Prerequisites

Implementation starts only after the mainline contains:

- Role Contract Normalizer v0.1;
- deterministic hashes, seed hierarchy, and immutable manifests;
- controlled parallel single-role removal;
- controlled schema-preserving sequential DAG bypass;
- passing repository-wide lint, type, test, and compile checks.

## 3. Work package A: dataset-agnostic task intake

Implement data contracts and interfaces for converting already-available,
offline source records into `TaskSpec` values. The interface must retain:

- adapter identity and version;
- dataset identifier and immutable revision;
- stable source record identifier;
- task identifier and task text;
- public metadata and sensitive-field declarations;
- conversion warnings or rejection reasons;
- an explicit synthetic/non-empirical marker.

Tests use only small, hand-authored synthetic fixtures. No dataset-specific
download client, credential, remote URL, leaderboard, or evaluation metric is
allowed in this work package.

## 4. Work package B: deterministic split manifests

Implement deterministic train/development/test assignment over validated task
identifiers. The split layer must:

- reject empty or duplicate task identifiers;
- be independent of input record ordering;
- use a recorded non-negative seed;
- make partitions disjoint and exhaustive;
- retain dataset and adapter revisions;
- record per-partition task identifiers and hashes;
- expose one canonical split hash suitable for `ExperimentManifest`;
- reproduce byte-equivalent canonical output for the same inputs and seed.

No split may use labels, gold answers, role outputs, execution traces, or
counterfactual outcomes.

## 5. Work package C: offline runtime adapter boundary

Implement a runtime adapter protocol plus fake/recording implementations. The
boundary must accept validated task/team inputs and frozen manifests, preserve
model/tool/prompt/contract identities and the seed hierarchy, and return the
existing execution evidence schemas.

The local implementation must:

- have no network or subprocess model-execution path;
- reject manifest or protocol mismatches before execution;
- never mutate task, team, role, Prompt, model, tool, topology, aggregation, or
  stopping-rule inputs;
- mark every fake output as mock/non-empirical;
- preserve failure and partial-execution evidence;
- support dependency injection for later server-only providers without naming
  or importing a provider SDK.

## 6. Validation and publication

Each work package is a separate major change. For each package:

1. implement the smallest scoped change;
2. add positive, rejection, determinism, mutation, and compatibility tests;
3. perform a strict read-only audit and fix blocking findings;
4. run `ruff check .`, `mypy src`, `pytest`, and
   `python -m compileall src tests`;
5. commit and push only after all checks pass.

Synthetic fixtures, generated caches, credentials, real datasets, and runtime
outputs must not be committed.

## 7. Server boundary

Stop local implementation before either of these actions:

1. downloading or materializing the first formal Benchmark revision;
2. sending the first request to a hosted model API or loading a self-hosted
   model for empirical execution.

Before crossing that boundary, approve a separate pilot plan that freezes:

- Benchmark name, license, revision, and task subset;
- model/provider identifiers and exact versions;
- Prompt, role contract, team, protocol, and adapter hashes;
- task and role seed sets;
- concurrency, timeout, retry, and budget limits;
- secret storage and redaction;
- artifact storage, checkpointing, and immutable manifests;
- pilot acceptance and abort criteria.
