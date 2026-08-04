# RoleCheck Codex Working Agreement

This file applies to the entire repository. Treat the frozen research documents as the source of truth, with `research_docs/RESEARCH_SPEC_v0.2.md` taking precedence, followed by `research_docs/DECISION_LOG.md`, `research_docs/INTERVENTION_PROTOCOL.md`, `research_docs/CLAIM_EVIDENCE_MAP.md`, `research_docs/RISK_REGISTER.md`, and `ROLECHECK_RESEARCH_HANDOFF.md`. Do not silently change a frozen research decision in code.

## Research hierarchy

- The primary task is predicting a role's protocol-conditioned keep value before complete execution of the current task.
- The secondary task is predicting and ranking the value of a finite set of concrete repair candidates.
- Defect diagnosis is auxiliary. It may support explanation, feature construction, and repair-candidate generation, but it must not replace keep-value or repair-value prediction.
- Do not reframe RoleCheck as generic prompt optimization, post-execution failure localization, budget-constrained team selection, or unrestricted MAS design.

## Frozen v1 boundaries

- The v1 intervention space is single-role `KEEP / REWRITE / REMOVE` only. At most one role may be intervened on per round; any further intervention requires re-normalization and re-auditing of the revised team.
- Do not add roles or perform joint multi-role rewrites or removals. Strongly coupled cases must be marked as requiring joint intervention and must default to `KEEP`/abstention in v1.
- Model assignments, tools and permissions, communication topology, execution rounds, aggregation protocol, and global stopping rules are immutable. Do not modify them as part of an intervention.
- `Strict Task-Level Pre-Execution` is the primary setting. Current-task role outputs, full-team results, gold answers, current-task counterfactual outcomes, and current-task execution traces must not enter features or decisions. `Probe-Assisted Pre-Deployment` is only an explicitly separated enhancement setting.
- Removal and replacement must follow the controlled, replayable protocols in `research_docs/INTERVENTION_PROTOCOL.md`. An unsafe or undefined removal must abstain and expose `KEEP` as the external action.

## Current implementation phase

- The active phase is Gate 4 review of the approved bounded server pilot in
  `research_docs/SERVER_PILOT_PLAN_v0.1.md`. Gate 3 is merged; the first BF16
  model load and one-task, one-role smoke artifacts are frozen outside Git and
  recorded in `research_docs/GATE4_SMOKE_FREEZE_v0.2.md`.
- Local work may validate the concrete offline single-GPU generation engine,
  smoke runner, immutable execution evidence, parser output, and unload state.
  Tests must not load a concrete model; test outputs are not empirical evidence.
- Do not run the 14-task dry run, execute multiple roles, aggregate empirical
  outputs, perform removal/replay, or evaluate MMLU-Pro answers.
- Do not implement defect injection, keep-value or repair-value predictors,
  repair generators/repairers, AutoGen integration, or AgentInit integration.
  Do not migrate old experimental logic into this repository.
- Stop before Gate 5 dry-run execution. Gate 4 must pass review and merge
  separately before any 14-task or multi-role execution is allowed.

## Role Contract Normalizer constraints

- The Normalizer is an extraction and normalization layer, not a role authoring or optimization layer.
- Preserve the original prompt/text and source provenance. Distinguish explicit, parsed, inferred, defaulted, missing, and unknown information, and retain field-level confidence or parse-risk information.
- Never create, optimize, embellish, repair, or fill in role goals, responsibilities, success criteria, non-goals, prohibited behaviors, inputs, outputs, authority, dependencies, capabilities, or other role information that is absent from the source.
- Missing or ambiguous source information must remain missing/unknown and be surfaced through warnings, provenance, confidence, or parse-risk fields. Do not hide information loss behind plausible defaults.
- Normalization must not alter model, tool, topology, protocol, round, aggregation, or stopping-rule data.

## Engineering and validation

- Preserve the strict Pydantic schema style, deterministic hashing/seeding, immutable manifests, replayability, and explicit leakage guards already established in the repository.
- Keep changes scoped to the requested phase and add or update tests for behavior changes.
- Before completing any task, run all of the following from the repository's WSL virtual environment and report the exact results:

  ```bash
  ruff check .
  mypy src
  pytest
  python -m compileall src tests
  ```

- A task is not complete if any required check was skipped or failed. Report blockers honestly; do not weaken checks, suppress errors, or claim success without evidence.

## Git safety

- Without the user's explicit permission, do not commit, push, merge, delete branches, rebase, reset, amend, force-push, or otherwise rewrite Git history.
- Do not stage changes unless the user explicitly asks. Preserve unrelated user changes and never discard them to make the working tree clean.
