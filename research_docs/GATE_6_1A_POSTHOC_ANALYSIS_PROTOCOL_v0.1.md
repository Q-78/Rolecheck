# Gate 6.1A Posthoc Analysis Protocol v0.1

**Status:** NON-FROZEN, subordinate exploratory analysis protocol.  
**Scope:** Existing sealed Gate 6 outputs only. This document neither changes nor supersedes Gate 6 or any frozen research decision.

The original 56 hash-assigned removals are infrastructure acceptance evidence. Gate 6.1A adds 56×3=168 exhaustive, offline, single-role response-drop re-aggregations as post-Gate-6 exploratory analysis. It creates no role output, calls no model, uses no GPU, and changes no prompt, contract, team, task, seed, tool, topology, execution protocol, removal protocol, or aggregator. Results cannot establish predictor validity or support a formal paper claim. Multi-seed work requires a separate Gate 6.1B protocol and approval.

## Frozen inputs and identities

- Gate 6 root: `/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-6-controlled-pilot-v0.2`
- root files hash: `sha256:6e8bf5363c7cbc420dacc91fd9e7a67dba3581d48407197d7a2045914bc394e5`
- Pilot56 hash: `sha256:5ad1b96bd7e28e4fa22131cfb518d3a3ecb87d983a1aa711c0b77fc0707e785a`
- execution hash: `sha256:cbb0332c7861252f158a1ba9fd30bf12b0a09c83831f0d3d8101c13e9b6f1d3b`
- original removal hash: `sha256:b299840a31eee90a56f9f8b5db92b6dc4a73eb36a55759307bcb13328e53b173`
- evaluation hash: `sha256:c3ab66bb924a8f3b8c80d0032dc6da79f7f70940185de2bf7b637f5c6f9a7070`
- roles: `domain_analyst`, `elimination_analyst`, `verification_analyst`
- aggregator: the repository's frozen `DeterministicMajorityAggregator` v0.1.

## Preflight and aborts

Before analysis, recompute every inventory, checkpoint, role-output, baseline replay, and original-removal replay. Verify unique 56 tasks, three outputs per task, 168 executions, 56 safe original removals with no re-execution, exact identities, TaskSpec leakage guards, and separate Gold artifacts. Any mismatch, ambiguity, missing/duplicate record, source mutation, replay failure, or pre-execution evaluation field aborts before exhaustive analysis.

## Counterfactual construction

For each task and each role, first replay the full three-response baseline, then drop only the target response and aggregate the two retained, byte-identical responses. Invalid votes are excluded without compensation. If no valid vote remains the result is unscorable. Tied leaders use the frozen lexicographically smallest-leader rule and are explicitly marked. Unscorable is never converted to incorrect or zero.

Gold-free records contain task/category/target, baseline and removal hashes and answers, retained and removed output hashes, scorable/majority/tie/invalid metadata, protocol and aggregator identities, source root hash, version, validity, and zero re-executions. Exactly 168 records are written and sealed in a new, non-existing artifact root. Overwrite is forbidden.

## Gold isolation and labels

Gold may be read only after the counterfactual seal exists and verifies. Evaluation is a separate artifact and is never written back to counterfactual records. For two scorable conditions, correctness yields transitions `correct_to_wrong`, `correct_to_correct`, `wrong_to_correct`, or `wrong_to_wrong`, and keep value is baseline utility minus removal utility in {-1,0,+1}. Otherwise the transition is `unscorable` and keep value is null.

## Statistics and interpretation

Report the original 56 and exhaustive 168 transition/label distributions, accuracy, answer changes, ties, invalid votes, roles, domains, per-task vectors, vote patterns, extraction quality, and separately marked tie-free and invalid-vote-free sensitivities. Exact McNemar/binomial tests and a deterministic fixed-seed bootstrap are exploratory only. Net accuracy difference alone does not determine individual role values. No result demonstrates a predictor, repairer, causal generalization, multi-seed stability, or formal scientific conclusion.

## Sealing and final verification

Inventories are sorted relative paths with byte size and SHA-256, excluding files named `artifact-manifest.json`; their canonical JSON hash is the files hash. Counterfactual, evaluation, and final roots are independently sealed. A verifier that does not invoke the main analysis recomputes counts, uniqueness, separation, hashes, summaries, and absence of model weights, caches, secrets, or private raw copies. Finally, recompute the original Gate 6 root hash and require exact equality with its pre-analysis value.
