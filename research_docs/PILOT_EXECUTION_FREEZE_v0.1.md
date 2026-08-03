# RoleCheck Pilot Execution Freeze v0.1

**Status:** Gate 2-B implementation candidate; no Benchmark or model execution
is authorized by this file.

**Authority:** subordinate to `AGENTS.md`, the frozen research documents, and
`SERVER_PILOT_PLAN_v0.1.md`.

## Scope

This freeze covers the local, I/O-free execution configuration required before
MMLU-Pro materialization:

- three independent role Prompts and normalized Role Contracts;
- one-round parallel team and controlled-removal protocol;
- deterministic terminal-answer parsing;
- deterministic, variable-arity, model-free majority aggregation;
- the identity required from a future Qwen3-8B generation engine;
- an execution backend that accepts only that identity through dependency
  injection.

It does not contain a Transformers implementation, dataset loader, model load,
real generation, evaluation, predictor, repairer, or defect injection.

## Frozen identities

Canonical definitions live in `src/rolecheck/pilot`. Their reviewed hashes are:

| Object | SHA-256 |
| --- | --- |
| CanonicalTeamConfig | `sha256:3c768707410ed19e2a06eaee70b9116e0ef1a01380c5cf361166b38b7acaadac` |
| DeterministicMajorityAggregator config | `sha256:fe61484ff35764e87e5bf3bf2a4ca9881eac5d2ef274278284de1b5a6a11e31e` |
| domain_analyst Prompt | `sha256:bad560eb6ee9ce382fd2c4c884d05e5bdc3f658640602fd60bc3bc187c89799b` |
| domain_analyst RoleContract | `sha256:a95754e740fdb33bf3b28664557e7e0610a3b98e6d89936247f6e0fcfea883cd` |
| domain_analyst NormalizationResult | `sha256:95cb290ed219a0f3db419552a82ce67b2b4ca338249f04b8935081a078884c2b` |
| elimination_analyst Prompt | `sha256:15c17d7af4b63ebc82138556de0c74dd50f26d4f33723ce7de49e71bb0af5c4f` |
| elimination_analyst RoleContract | `sha256:edc6005c74019d312da6d84d90e2b479f005d5e831bf8aef131e3d99fda51f24` |
| elimination_analyst NormalizationResult | `sha256:70c495290b4451ecf10451707358b5009770b426c984cbcde6b850e4946b021b` |
| verification_analyst Prompt | `sha256:0e2c6cff40df14c1750e8729ba6bfb10b6cee1448e8ee56770c411ec1aa638a2` |
| verification_analyst RoleContract | `sha256:7d8f38e682f2b2d03e032b8be7f8c45c4c4d13dcd2e6276a3b0d6a381977f9b0` |
| verification_analyst NormalizationResult | `sha256:4514813f00d39d13d1111a6b1647013bd19a25c06acb419e064883e7d34ee5c2` |
| RuntimeEnvironmentIdentity | `sha256:75bd5f65b1c3acca4d364e2a67041db2aa57db5b3e0eedea42c2890d104ffc55` |
| answer-parser config | `sha256:782c7636a1dbcaec4ac0d56dfe974dea5c6342eeee99c5308a6015dc1f97cd9f` |
| required generation-engine config | `sha256:17f02120c9861c4e0bd34a5ef9396359eabdc389312effa38ca1202182f1f7a3` |
| PilotExecutionBackend config | `sha256:62beeb34048c7b6f29402449212c9831246ff047ec0adf67b0cdf3f4fcdfff1e` |
| SelfHostedRuntimeAdapter config | `sha256:3359697ecd6b32fe3f869cca2b4c1fc1cd712b34ec59a60d3d869297bcf9cf43` |

These hashes bind the audited Gate 2-A machine-readable environment artifact.
The dependency-lock and hardware-inventory values were copied from
`runtime-environment.json`; screenshot transcription is not an identity
source.

## Role normalization

Each Prompt states only the assigned analysis strategy and common execution
constraints. Structured explicit fields supply the strict input/output schema,
authority, visibility, resource, and interaction facts. The Normalizer does
not infer or optimize them.

All three contracts normalize with no missing or conflicting fields. The
following nullable facts are deliberately retained as `UNKNOWN` because no
positive source fact exists:

- `failure_output`;
- `conflict_resolution_rule`;
- `parent_role_version`.

No role may inspect another role response. Tools and network access are
disabled. Each role has voting authority only and emits one homogeneous
reasoning-and-answer artifact.

## Output parsing

The parser operates only on final visible model content. It accepts exactly a
terminal line of the form `Answer: <LETTER>`, with an uppercase letter inside
the supplied option range. It does not translate, repair, infer, retry, or map
free-form answer text.

Malformed thinking markers, missing terminal answers, lowercase answers,
punctuation after the letter, trailing content, and out-of-range letters are
invalid responses. Invalid responses remain recorded and receive no retry or
synthetic compensation.

## Aggregation

Valid letters are counted. A strict majority wins. If no strict majority
exists, the lexicographically smallest letter among the tied highest-count
letters wins. Invalid responses are excluded. If there are no valid votes, the
result records no selected answer.

The aggregator accepts variable response counts so the same implementation is
used for baseline replay and controlled single-role removal. It receives
frozen response payloads and hashes, rejects identity or hash mismatches, and
has no generation-engine dependency.

## Execution boundary

The local backend renders each role independently from only:

- that role's frozen raw Prompt;
- current question text;
- current ordered options;
- the fixed response-format instruction.

The role Prompt and current-task content remain separate system and user messages;
their ordered two-message representation is hashed before tokenizer templating.
It records the rendered Prompt hash, role seed, raw generated token IDs, raw
decoded output, raw-output hash, separated thinking/final content, answer-parse
result, token counts, and latency. No earlier role output enters a later role
request.

The required future engine identity binds the exact Qwen3-8B model assignment,
model/tokenizer/generation/environment hashes, single-GPU constraints,
generation configuration, and prohibited fallbacks. Identity is checked at
construction and before and after every role call.

The parser and aggregator configurations are identity-bound. Aggregator identity
drift is rejected before any role generation and around the aggregation call.

## Hard stop

Gate 2-B tests use only hand-authored MMLU-shaped records and a fake injected
generation engine. Do not call `load_dataset`, `from_pretrained`, or any real
generation API. Gate 3 may begin only after this change is reviewed and merged.
