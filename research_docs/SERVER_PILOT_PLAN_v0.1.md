# RoleCheck Server Pilot Plan v0.1

**Status:** DRAFT -- execution is not approved

**Authority:** subordinate to AGENTS.md and all frozen research documents

**Purpose:** define the first tightly bounded empirical infrastructure pilot.
This document does not authorize Benchmark materialization or model loading by
itself.

## 1. Decision summary

The proposed first pairing is conditionally accepted:

- Benchmark: TIGER-Lab/MMLU-Pro;
- model: Qwen/Qwen3-8B;
- execution: self-hosted, BF16, one NVIDIA A100-SXM4-40GB;
- primary information setting: Strict Task-Level Pre-Execution;
- pilot role: infrastructure and protocol validation only.

MMLU-Pro is suitable because it supplies challenging, reasoning-oriented,
multiple-choice tasks across 14 domains. It is not, by itself, a RoleCheck
Benchmark: the scientific object remains a multi-role team's
protocol-conditioned role value. No single-model MMLU-Pro score may be
presented as evidence for keep-value prediction.

## 2. Frozen source identities

### 2.1 Code

- repository: https://github.com/Q-78/Rolecheck
- code revision:
  725d537e0d9b56979c9d0cbd00b9fc6ff4d16dc1
- code state: merged mainline after Stage 3 local scaffold
- required pre-run checks: ruff, mypy, pytest, and compileall must all pass

### 2.2 Benchmark

- dataset identifier: TIGER-Lab/MMLU-Pro
- source: https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro
- immutable revision:
  b189ec765aa7ed75c8acfea42df31fdae71f97be
- dataset-card license: MIT
- official evaluation-code repository:
  https://github.com/TIGER-AI-Lab/MMLU-Pro
- evaluation-code license: Apache-2.0
- language: English
- expected domains: 14

Dataset and evaluation-code licenses are recorded separately. The pinned
dataset revision must be passed explicitly to the download/materialization
layer; floating main is forbidden.

### 2.3 Model

- model identifier: Qwen/Qwen3-8B
- local Hugging Face revision:
  b968826d9c46dd6066d109eabc6255188de91218
- local cache root:
  /data/qhy/huggingface/hub/models--Qwen--Qwen3-8B
- snapshot path:
  `/data/qhy/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218`
- license: Apache-2.0
- architecture: Qwen3ForCausalLM
- parameter class: 8B dense
- dtype declared by config: bfloat16
- hidden layers: 36
- hidden size: 4096
- attention heads: 32
- key/value heads: 8
- max_position_embeddings: 40960

The server preflight produced SHA-256 manifests for model configuration files
and all five safetensors shards under:

    /data/qhy/rolecheck_server/artifacts/pilot-v0.1/preflight/

The recorded configuration hashes are:

- `config.json`: `f7c4eadfbbf522470667b797a3c89be2524832d2d599797248dc304fff447c30`
- `generation_config.json`: `2325da0f15bb848e018c5ae071b7943332e9f871d6b60e2ed22ca97d4cb993d2`
- `tokenizer_config.json`: `d5d09f07b48c3086c508b300d1c9114bd1189145b74e982a265350c923acd8101`
- `tokenizer.json`: `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492daa4`
- `vocab.json`: `ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910`
- `merges.txt`: `8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f7440c5308a904d5`
- `model.safetensors.index.json`: `f9fdbcb91c23971c13ec5d5f2573d2349e8f61f2f049371ec699281748fdb1bc`

The five recorded shard hashes are:

- `model-00001-of-00005.safetensors`: `31d6a825ae35f11fb85b195b4c42c146c051e446433125a215336abdf95cbf5f`
- `model-00002-of-00005.safetensors`: `5991236cea6fe21f3d43cab0f0e84448734fbbe0789816202989f2ddc9d18282`
- `model-00003-of-00005.safetensors`: `c5185c4794be2d8a9784d5753c9922db38df478ce11f9ed0b415b7304d896836`
- `model-00004-of-00005.safetensors`: `b5ee7de71fbf17db3d5704e0c8f2bc7d005ca9e1d7ca2aeb19827b0cfcaa917a`
- `model-00005-of-00005.safetensors`: `20c2d6366ab85c90786ccdd829cd2b9e7d30ef3b2ebbb998280e7e4014b542ff`

All recorded configuration and shard hashes must be rechecked before the first
model load. A mismatch is a hard abort.

## 3. Why one GPU

Qwen3-8B BF16 weights require approximately 16.4 GB before runtime overhead,
so one 40 GB A100 is sufficient for the bounded context and concurrency in
this pilot. The server topology places GPU 0-1 and GPU 2-3 in separate local
pairs and does not report NVLink. Four-GPU execution would add unnecessary
distributed-runtime and topology variables.

Pilot allocation is frozen to:

- CUDA_VISIBLE_DEVICES=0;
- one model process;
- one task in flight;
- no tensor parallelism;
- no data parallelism;
- no quantization;
- no CPU offload;
- no model compilation.

## 4. Required empirical-boundary redesign

The Stage 3 local contracts intentionally force Benchmark conversions and
Runtime Adapter results to be synthetic and non-empirical. They must not be
bypassed or mislabeled for this pilot.

Before downloading data or loading the model, a reviewed implementation change
must:

1. add an explicit evidence classification that distinguishes synthetic
   non-empirical records from empirical unevaluated records;
2. keep existing synthetic adapters and tests backward compatible;
3. prevent gold answers, answer indices, reference rationales, role outputs,
   traces, and counterfactual outcomes from entering TaskSpec or pre-execution
   inputs;
4. add a dataset-specific MMLU-Pro adapter that accepts only the pinned
   revision;
5. add a self-hosted Runtime Adapter behind dependency injection;
6. return mock=false only for actual model executions;
7. retain exact model, tokenizer, dependency, Prompt, contract, team,
   protocol, split, seed, and hardware identities;
8. reject every identity mismatch before execution;
9. update AGENTS.md to activate only this approved server pilot scope.

No real call may be hidden behind FakeRuntimeAdapter or
SyntheticBenchmarkAdapter.

## 5. MMLU-Pro task boundary

### 5.1 Allowed pre-execution task content

TaskSpec may contain:

- stable question identifier;
- question text;
- ordered answer options;
- category/domain;
- pinned dataset revision;
- non-sensitive source metadata required for provenance.

### 5.2 Evaluation-only content

The following must remain in a separate evaluation record unavailable to the
Normalizer, roles, aggregator, intervention decision, and pre-execution
features:

- answer letter;
- answer index;
- gold answer;
- reference chain-of-thought;
- correctness;
- per-category or overall score;
- current-task role outputs and traces;
- current-task removal outcome.

Sampling must use identifiers, category, revision, and the split seed only. It
must not inspect labels, answers, reference rationales, or model outputs.

### 5.3 Prompting policy

This pilot is zero-shot and is not intended to reproduce the official
leaderboard's common five-shot setting. That choice removes few-shot example
selection as an infrastructure variable. Results must be labelled
non-comparable to the official leaderboard.

Each role receives the question and ordered options plus a fixed output
instruction. The final visible answer must end with:

    Answer: <LETTER>

Answer extraction uses one deterministic parser over the final answer content.
Failure to extract is recorded as an invalid response and is never retried as
an answer-quality retry.

## 6. Proposed team and protocol

The pilot team contains three independent roles:

1. domain_analyst: solve using relevant domain knowledge and explicit
   assumptions;
2. elimination_analyst: solve primarily by testing and eliminating options;
3. verification_analyst: independently check logical, numerical, and wording
   consistency before selecting an option.

Frozen properties:

- all three roles use the same Qwen3-8B revision;
- no role can read another role's response;
- protocol kind is parallel_independent;
- one execution round;
- tools disabled;
- network disabled during inference;
- each role emits reasoning plus one final answer letter;
- aggregation parses letters and applies deterministic majority vote;
- if no strict majority exists, choose the lexicographically smallest valid
  letter among tied answers;
- invalid/missing letters do not receive synthetic compensation messages;
- aggregation never calls the model.

Exact raw Prompts, normalized Role Contracts, team configuration, aggregation
implementation, and their hashes must be reviewed in a later implementation
commit before execution. The Normalizer may extract only explicit source facts.

## 7. Model generation configuration

The proposed Qwen3-8B condition is thinking mode enabled:

- enable_thinking: true;
- dtype: bfloat16;
- do_sample: true;
- temperature: 0.6;
- top_p: 0.95;
- top_k: 20;
- min_p: 0.0;
- max_new_tokens: 4096;
- no YaRN or other RoPE scaling;
- one role generation at a time;
- role-specific seed from the existing seed hierarchy.

Greedy decoding is prohibited for this condition because the official Qwen3
guidance warns that it can degrade thinking-mode behavior and cause
repetition. Thinking and non-thinking modes are not mixed in Pilot v0.1.

Raw generated token IDs, raw decoded output, parsed reasoning, parsed final
content, answer letter, token counts, latency, seed, and hashes must all be
retained. Current-task reasoning and output remain execution evidence and must
not be fed into a pre-execution predictor.

## 8. Deterministic task subsets

The pinned test split is sampled independently within each of the 14 domains
using a stable canonical hash of:

- dataset revision;
- split seed;
- category;
- stable question identifier.

Frozen seeds:

- subset split seed: 2026080301;
- experiment seed: 2026080302.

Subsets:

- smoke: one task total, used only after all preflight checks;
- dry run: 14 tasks, one per domain;
- pilot: 56 tasks, four per domain, including the dry-run tasks.

The adapter must record the exact task identifiers and canonical subset hash.
Any category with insufficient valid records is a hard abort, not a reason to
silently rebalance.

## 9. Execution sequence

### Gate 0 -- plan approval

- merge this plan only after review;
- record explicit user approval;
- do not download or materialize MMLU-Pro;
- do not load Qwen3-8B.

### Gate 1 -- empirical-boundary implementation

- implement the minimum schema boundary described in Section 4;
- add leakage, identity, rejection, mutation, determinism, compatibility, and
  failure-evidence tests;
- use only hand-authored fixtures;
- run all repository checks;
- review and merge separately.

### Gate 2 -- dependency and environment freeze

Create a new server environment separate from rolecheck-stage3. Freeze:

- Python version;
- PyTorch build and CUDA runtime;
- Transformers version, at least 4.51.0;
- Safetensors and tokenizer dependencies;
- NVIDIA driver;
- GPU name and UUID;
- complete pip freeze;
- Runtime Adapter identity and config hash.

Dependency installation is allowed only after Gate 1. Model loading remains
forbidden until the environment lock and model shard verification pass.

### Gate 3 -- Benchmark materialization

- resolve the pinned revision again;
- materialize only that revision under the isolated dataset directory;
- record file hashes, row counts, schema, split names, and license;
- build the 14-task and 56-task manifests without inspecting answer content;
- run the gold-leakage audit;
- stop and review the resulting manifests.

### Gate 4 -- first model load and one-task smoke test

- recheck model shard hashes;
- reserve GPU 0 only;
- verify free GPU memory;
- load the model once in BF16;
- execute one predeclared task and one role;
- unload and inspect artifacts before any further run.

### Gate 5 -- 14-task dry run

- execute all three role outputs for each task;
- aggregate without model calls;
- verify output parsing, hashes, seeds, manifests, checkpointing, and leakage
  guards;
- do not perform role removal yet.

### Gate 6 -- 56-task controlled pilot

- execute one baseline team per task;
- assign at most one removal target per task by stable task hash;
- reuse frozen non-target responses;
- run controlled parallel removal with no role re-execution;
- evaluate baseline and counterfactual accuracy only after all execution
  artifacts are sealed;
- do not train or fit any predictor.

The hash-assigned removal target is an infrastructure test of the controlled
intervention protocol. It is not a RoleCheck prediction, a recommended action,
or evidence that the decision policy can identify valuable roles.

## 10. Concurrency, retry, timeout, and resource limits

- concurrent tasks: 1;
- concurrent role generations: 1;
- model replicas: 1;
- per-role timeout: 180 seconds;
- infrastructure retry: at most 1;
- wrong-answer retry: 0;
- extraction-failure retry: 0;
- dry-run GPU budget: 1 GPU-hour;
- full Pilot GPU budget: 8 GPU-hours;
- minimum free artifact-disk space before start: 100 GB;
- maximum generated tokens per role: 4096;
- checkpoint interval: after every task;
- resumability key: experiment, task, team, protocol, model, and seed hashes.

Retries must retain the original seed and record the first failed attempt.

## 11. Logging, secrets, and artifacts

Artifact root:

    /data/qhy/rolecheck_server/artifacts/pilot-v0.1

Required immutable records:

- approved plan revision;
- code revision;
- dataset revision and hashes;
- model revision and all file hashes;
- environment lock;
- hardware inventory;
- task split manifests;
- normalized Role Contracts and provenance;
- Prompt, contract, team, protocol, aggregator, and adapter hashes;
- seed bundles;
- raw and parsed role outputs;
- baseline and intervention records;
- safety reports;
- error and retry records;
- final post-execution evaluation records.

No API key is required for the self-hosted pilot. Secrets, credentials, caches,
model files, dataset files, and runtime outputs must remain outside Git.

## 12. Acceptance criteria

Gate 4 smoke acceptance:

- exact model and dependency identities recorded;
- model loads on GPU 0 without CPU offload or quantization;
- one role completes within timeout;
- raw and parsed output hashes validate;
- no gold or reference rationale appears in the request or role input.

Gate 5 dry-run acceptance:

- all 14 task records validate;
- all 42 role executions complete;
- all 14 aggregations complete without model calls;
- at least 95 percent of role outputs have a valid final answer extraction;
- replay aggregation is byte-equivalent by hash;
- no identity, mutation, leakage, or checkpoint violation occurs;
- total usage remains below one GPU-hour.

Gate 6 Pilot acceptance:

- all 56 baselines produce complete evidence;
- each task has zero or one controlled removal intervention;
- no retained role is re-executed during removal;
- all manifests and safety reports validate;
- evaluation remains post-execution and separate;
- no predictor, repairer, or defect injection is introduced;
- total usage remains below eight GPU-hours.

Passing the Pilot authorizes only a review of infrastructure readiness. It does
not validate the RoleCheck research hypotheses.

## 13. Hard abort criteria

Abort immediately if any of the following occurs:

- code, dataset, model, Prompt, contract, team, protocol, dependency, or shard
  hash mismatch;
- dataset resolution uses floating main;
- gold answer or reference rationale enters TaskSpec, a Prompt, aggregation,
  role input, pre-execution feature, or intervention decision;
- a retained role is re-executed during parallel removal;
- more than one role is intervened on for a task;
- any tool or external network access occurs during inference;
- model uses an unrecorded fallback, quantization, CPU offload, or extra GPU;
- two CUDA out-of-memory failures occur;
- role execution error rate exceeds 5 percent;
- free artifact disk falls below 100 GB;
- dry-run or Pilot GPU-hour cap is reached;
- required artifact, manifest, checkpoint, or safety evidence is missing;
- mock and empirical evidence are mislabeled or mixed.

On abort, preserve completed immutable evidence, write an abort record, and do
not silently resume with changed configuration.

## 14. Explicit exclusions

Pilot v0.1 does not include:

- full MMLU-Pro evaluation;
- leaderboard submission or comparison;
- formal research claims;
- keep-value or repair-value predictors;
- defect injection;
- repair candidate generation;
- role rewriting;
- multiple simultaneous removals;
- DAG bypass;
- AgentInit or AutoGen integration;
- model fine-tuning;
- hosted APIs;
- multi-GPU inference;
- probe-assisted features.

## 15. Remaining approval fields

The following must be filled and reviewed before Gate 3 or Gate 4:

- exact empirical schema/API design and compatibility migration;
- exact dependency versions and pip-freeze hash;
- exact Prompt texts and hashes;
- normalized Role Contracts and hashes;
- CanonicalTeamConfig hash;
- aggregation implementation identity and hash;
- empirical Benchmark Adapter identity and hash;
- empirical Runtime Adapter identity and hash;
- materialized dataset file hashes and split schema;
- server GPU UUID;
- explicit approval timestamp and approver.

Until every applicable field is frozen, external action remains abstention:
do not materialize the Benchmark and do not load the model.

## 16. Primary sources

- MMLU-Pro dataset:
  https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro
- MMLU-Pro evaluation repository:
  https://github.com/TIGER-AI-Lab/MMLU-Pro
- MMLU-Pro paper:
  https://arxiv.org/abs/2406.01574
- Qwen3-8B model card:
  https://huggingface.co/Qwen/Qwen3-8B
- Qwen3 repository:
  https://github.com/QwenLM/Qwen3
