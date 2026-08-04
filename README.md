# RoleCheck

**Frozen research title**

> RoleCheck: Plug-and-Play Multi-Agent Initialization Auditing and Minimal Repair via Counterfactual Role-Value Prediction

## Current stage

Pilot v0.3 Gate 6 has completed its bounded controlled-pilot infrastructure run and is awaiting independent review. The authoritative result is research_docs/PILOT_V0.3_GATE6_RESULT.md.

Gate 6 produced 56 complete baselines and 56 valid controlled removals with zero retained-role re-executions. Baseline accuracy was 43/56; hash-assigned removal accuracy was 41/56. This is infrastructure evidence only: assigned targets are not RoleCheck predictions, and no predictor, repairer, calibration, or defect injection was run.

Model, dataset, cache, and empirical artifacts remain outside Git. Stop after Gate 6 review. Predictor fitting or a larger formal experiment requires a separately reviewed protocol and explicit authorization.

## Frozen scientific hierarchy

1. **Primary task:** predict a role's protocol-conditioned keep value before full execution of the current task.
2. **Secondary task:** rank the value of at most three concrete repair candidates.
3. **Auxiliary task:** diagnose defects for explanation, features, and candidate generation; diagnosis cannot substitute for value prediction.

The v1 action space is single-role `KEEP / REWRITE / REMOVE`. Model, tools, topology, execution rounds, aggregation protocol, and global stopping rules are immutable.

## Repository layout

```text
RoleCheck/
├── configs/base.yaml
├── research_docs/
│   ├── RESEARCH_SPEC_v0.2.md
│   ├── DECISION_LOG.md
│   ├── RISK_REGISTER.md
│   ├── INTERVENTION_PROTOCOL.md
│   ├── CLAIM_EVIDENCE_MAP.md
│   └── original seven research documents
├── src/rolecheck/
│   ├── schemas/
│   ├── runtime/mock.py
│   ├── config.py
│   ├── logging_utils.py
│   ├── manifest.py
│   └── hashing.py
├── tests/
├── ROLECHECK_RESEARCH_HANDOFF.md
└── pyproject.toml
```

## Setup

Python 3.11 is the target environment.

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Validate configuration

```bash
python -m rolecheck configs/base.yaml
```

## Quality checks

```bash
ruff check .
mypy src
pytest
python -m compileall src tests
```

## Role Contract Normalizer

`RoleContractNormalizer` preserves the exact source text and deterministically extracts only source-supported English or Chinese role facts. It records per-field spans, provenance status, parse risk, missing or unknown fields, explicit-source conflicts, and unparsed text.

Normalization deliberately separates two representations:

- `RoleContractDraft` holds partial facts. `None` means unavailable or unresolved; an explicit empty list means the source states that there are no entries.
- `RoleContract` remains the strict, backward-compatible execution contract. `NormalizationResult.contract` is populated only when the draft validates against that strict schema.

Format names such as JSON, YAML, XML, Markdown, and plain text are recognized only when explicitly stated. The Normalizer does not parse those formats, infer schemas from examples, diagnose role defects, translate, summarize, optimize, repair, or fill absent role information.

## Mock Runtime warning

`MockRuntime` only validates wiring, deterministic seeds, hashes, records, and manifests. It emits placeholder outputs, reports `utility=None`, and sets `mock=true`. Mock results must never be used as empirical evidence.

## Stage 3 offline adapters

SyntheticBenchmarkAdapter converts only already-available, hand-authored
synthetic records into TaskSpec values. create_task_split_manifest assigns
validated task identifiers by a recorded seed and verifies exhaustive,
disjoint partitions and canonical hashes. Neither interface accepts labels,
gold answers, role outputs, traces, or counterfactual outcomes.

FakeRuntimeAdapter verifies the frozen task split, complete team hash,
runtime/aggregator identities, model/tool/Prompt/contract identities, protocol
IDs, and seed hierarchy before invoking MockRuntime. RecordingRuntimeAdapter
stores isolated in-memory call evidence. Both mark all results synthetic, mock,
and non-empirical, and neither contains a network, subprocess model-execution,
or provider-SDK path.

## Gate 1 empirical boundary

`EvidenceClass` distinguishes `synthetic_non_empirical` from
`empirical_unevaluated` while retaining the legacy `synthetic` and
`non_empirical` flags with strict consistency checks. Default synthetic split,
manifest, and request hash payloads remain compatible with Stage 3.

`MMLUProBenchmarkAdapter` accepts only the frozen MMLU-Pro revision and only a
label-free `MMLUProTaskRecord`. Answer indices, answer letters, gold text, and
reference rationales live in the separate `MMLUProEvaluationRecord` and cannot
validate as pre-execution task input. The adapter performs no file or network
I/O.

`SelfHostedRuntimeAdapter` accepts an injected `SelfHostedExecutionBackend`;
preflight binds the team, protocol, split, Prompt and contract hashes, exact
model assignment, runtime environment, aggregator, and backend identity before
any backend call. Empirical results must be `mock=false`; Fake Runtime evidence
must remain synthetic and `mock=true`.

## Gate 2-B execution freeze

`rolecheck.pilot` freezes the three independent MMLU-Pro role Prompts,
normalized Role Contracts, CanonicalTeamConfig, one-round protocol, Qwen3-8B
generation condition, and audited server-environment boundary. The core
RoleContract and execution Schemas are unchanged.

The terminal-answer parser accepts only a final `Answer: <LETTER>` line in the
available option range. `DeterministicMajorityAggregator` performs strict
majority voting with the frozen lexicographic tie rule, excludes invalid votes
without compensation, accepts variable response counts, and never calls a
model.

`PilotExecutionBackend` is orchestration around an identity-checked injected
`LocalGenerationEngine`. It renders independent role requests and retains raw
token IDs, decoded output, separated thinking/final content, parse evidence,
seeds, hashes, token counts, and latency. No Transformers implementation,
dataset loader, model load, or real generation call is included. Exact hashes
and the Gate 3 hard stop are recorded in
`research_docs/PILOT_EXECUTION_FREEZE_v0.1.md`.

## Controlled parallel removal

`ParallelRemovalRunner` implements response-drop + fixed-other-responses +
same-protocol re-aggregation for declared `parallel_independent` teams. It first
replays the baseline aggregation from frozen response hashes, then removes one
target response and re-aggregates with the same injected aggregator identity and
aggregation seed. The runner has no role-execution callback; retained roles are
never re-run.

Any failed applicability, replay, coverage, dependency, non-removable-role, or
provenance check produces an abstaining external `KEEP`. The implementation
does not add absence messages, infer bypasses, or call a real model.

## Controlled sequential DAG bypass

`DagBypassRunner` applies one pre-registered `BypassRule` to a declared
`sequential_dag`. It passes one upstream artifact to one downstream required
input without semantic or format conversion; the only permitted payload edit
is a pre-declared, collision-free field-name mapping. Nodes whose input hashes
are unchanged reuse baseline evidence. Only the changed-input downstream
closure may be executed through an injected `NodeExecutor`, using the original
role seeds, model/tool/prompt manifests, and aggregation protocol.

The included `MockNodeExecutor` is deterministic and explicitly mock. Missing
schema evidence, unsafe mappings, irreversible transformations, security gates,
coverage gaps, executor failures, or replay failures abstain to external
`KEEP`.

## Research source of truth

Use this order:

1. `research_docs/RESEARCH_SPEC_v0.2.md`
2. `research_docs/DECISION_LOG.md`
3. `research_docs/INTERVENTION_PROTOCOL.md`
4. `research_docs/CLAIM_EVIDENCE_MAP.md`
5. `research_docs/RISK_REGISTER.md`
6. original seven research documents
7. `ROLECHECK_RESEARCH_HANDOFF.md`
