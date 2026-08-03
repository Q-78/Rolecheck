# RoleCheck

**Frozen research title**

> RoleCheck: Plug-and-Play Multi-Agent Initialization Auditing and Minimal Repair via Counterfactual Role-Value Prediction

## Current stage

This repository contains the **research freeze, controlled execution protocols,
and local Stage 3 offline scaffold**. It does not contain formal experiments or
a working RoleCheck predictor.

Implemented now:

- frozen `RESEARCH_SPEC_v0.2.md`;
- decision, risk, intervention, and claim-evidence documents;
- Python 3.11 package scaffold;
- canonical Pydantic schemas;
- YAML configuration loading;
- standard/JSON-lines logging;
- immutable experiment manifests;
- deterministic Mock Runtime;
- deterministic English/Chinese Role Contract Normalizer v0.1;
- controlled parallel single-role removal with frozen-response re-aggregation;
- controlled schema-preserving sequential DAG bypass;
- dataset-agnostic offline task conversion with synthetic/non-empirical provenance;
- deterministic train/development/test split manifests;
- manifest-gated Fake and Recording Runtime Adapters with no network or model path;
- schema, configuration, manifest, and mock-runtime tests.

Explicitly not implemented:

- real LLM/API calls;
- Benchmark download or dataset construction;
- defect injection;
- Static Defect Auditor;
- Keep-Value Predictor;
- repair candidate generator;
- Repair-Value Predictor;
- AgentInit or other initializer adapters;
- formal intervention experiments;
- migration of old experimental code.

The controlled-execution and Stage 3 components remain mock-only,
non-empirical plumbing. Stop before downloading or materializing a formal
Benchmark revision, sending a hosted model request, or loading a self-hosted
model. Crossing that boundary requires the separately approved server-pilot
plan described in research_docs/PHASE_3_IMPLEMENTATION_PLAN.md.

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
