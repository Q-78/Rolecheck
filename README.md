# RoleCheck

**Frozen research title**

> RoleCheck: Plug-and-Play Multi-Agent Initialization Auditing and Minimal Repair via Counterfactual Role-Value Prediction

## Current stage

This repository is the **research-freeze and foundation initialization** deliverable. It does not contain formal experiments or a working RoleCheck predictor.

Implemented now:

- frozen `RESEARCH_SPEC_v0.2.md`;
- decision, risk, intervention, and claim-evidence documents;
- Python 3.11 package scaffold;
- canonical Pydantic schemas;
- YAML configuration loading;
- standard/JSON-lines logging;
- immutable experiment manifests;
- deterministic Mock Runtime;
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

The next stage, only after this scaffold passes quality checks, is:

> implement the two controlled execution protocols and the Role Contract Normalizer.

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
```

## Mock Runtime warning

`MockRuntime` only validates wiring, deterministic seeds, hashes, records, and manifests. It emits placeholder outputs, reports `utility=None`, and sets `mock=true`. Mock results must never be used as empirical evidence.

## Research source of truth

Use this order:

1. `research_docs/RESEARCH_SPEC_v0.2.md`
2. `research_docs/DECISION_LOG.md`
3. `research_docs/INTERVENTION_PROTOCOL.md`
4. `research_docs/CLAIM_EVIDENCE_MAP.md`
5. `research_docs/RISK_REGISTER.md`
6. original seven research documents
7. `ROLECHECK_RESEARCH_HANDOFF.md`
