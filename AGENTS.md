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

- Pilot v0.3 Gate 6 has completed under research_docs/PILOT_V0.3_GATE6_RESULT.md and is awaiting independent review. Prior failed and aborted empirical attempts remain immutable evidence.
- Local work may validate Gate 6 execution, removal, evaluation, safety, and artifact manifests. Tests must not load a concrete model; test outputs are not empirical evidence.
- Do not overwrite, selectively rerun, or mix Gate 6 artifacts. Do not change prompts, roles, seeds, parser, aggregation policy, or frozen task membership.
- Do not implement or fit defect injection, keep-value or repair-value predictors, repair generators or repairers, AutoGen integration, or AgentInit integration.
- Stop after Gate 6 infrastructure review. Predictor training, calibration, a learned decision policy, or a larger formal experiment requires a separately reviewed protocol and explicit authorization.

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
