# Gate 6.2 Role-Value Signal Redesign v0.1

**Status:** proposed, offline design only; human review required before Gate 6.2A.  
**Condition:** Pilot v0.4 / Gate 6.2 Structured-Score Condition.

## 1. Background and research question

Gate 6.1A found that the old three-letter majority vote discarded nearly all
information in role analyses. Of 168 task-role removals, 143 scorable labels
were zero and every nonzero label depended on a tie. Removing tie-dependent
records left only zero labels. All 19 invalid outputs ended at the 4096-token
cap with an unclosed thinking block. These immutable observations are not
reinterpreted here.

Gate 6.2 asks whether a controlled vector of option support can provide a richer
protocol-conditioned role-value signal while preserving deterministic replay,
Gold isolation, and single-response removal. It does not establish predictor
feasibility, causality, stability, or a paper result.

## 2. Non-goals and invariant condition

This phase does not run a model, GPU, API, benchmark task, predictor, repairer,
defect injection, AutoGen, or AgentInit. It changes no frozen Gate 6/6.1A file.
The new condition retains Qwen3-8B, three roles, `parallel_independent`
topology, no tools, no cross-role visibility, the frozen benchmark, and one
explicit task-role seed. It is a separate experimental condition rather than a
mutation of the Gate 6 majority aggregator.

## 3. Structured role output

The only visible role output is strict JSON:

```json
{"option_scores":{"A":5,"B":15,"C":70,"D":10},"key_evidence":["Brief visible evidence."]}
```

Keys must exactly equal the task option letters. Scores are strict integers in
0..100 and sum to 100. `key_evidence` contains at most three nonblank strings,
each at most 240 characters. There is no answer field; the preferred option is
program-derived. Code fences, leading/trailing text, unknown fields, missing or
extra options, coercion, repair, and retry are rejected. The canonical JSON
projection is hashed as `StructuredRoleOutput.v0.1`; chain-of-thought is neither
requested nor retained.

## 4. Role prompts

All prompts say: read the same question and every option independently; emit
only the schema above; never emit `<think>` or detailed reasoning; provide only
short visible evidence; allocate exactly 100 support points; do not access Gold,
mention other roles, decide KEEP/REMOVE, or propose repairs.

- `domain_analyst`: score definitions, facts, domain knowledge, and theory fit.
- `elimination_analyst`: score through constraint failures, contradictions, and
  elimination of incorrect options.
- `verification_analyst`: score through boundary cases, counterexamples, and
  consistency checks.

No role receives a general solver mandate; all share the same schema.

## 5. Proposed generation condition (human approval required)

Qwen3-8B, BF16, one GPU, `enable_thinking=false`, `max_new_tokens=384`,
`temperature=0.2`, `top_p=0.9`, `top_k=20`, one explicit seed per task-role,
strict JSON instruction, no quality retry, and no parse repair. The short cap is
intended to fit the bounded JSON/evidence contract; low temperature limits
format drift while nonzero sampling preserves the frozen explicit-seed
requirement. Every value must be recorded rather than inherited from defaults.
These are recommendations, not validated settings, and require human approval.

## 6. Exact aggregation

For role set C and option o:

`S_C(o) = sum_i s_i(o) / |C|`.

The implementation stores reduced numerator/denominator pairs, never floats.
The selected answer maximizes the mean. Mean rather than total is retained
because baseline has three roles and removal has two; totals would confound
support with team size and corrupt Gold-margin comparisons.

The result records role order, valid/invalid partitions, per-role vectors,
totals, exact means, selected answer, top/second/margin, tied options, tie
application and order/hash, aggregator ID/version, and config hash.

## 7. Task-hash tie break

Each option receives a canonical SHA-256 key over public `task_id`, public task
hash, aggregator version, fixed namespace, and the option letter. Sorting these
keys yields a deterministic task-specific permutation. Gold, model output,
execution outcome, Python `hash`, and randomness are excluded. The permutation
and its canonical hash are retained. Any baseline or removal tie marks the label
tie-dependent; reporting must include a tie-free sensitivity analysis.

## 8. Invalid and unscorable policy

If any required baseline role is invalid, the baseline and every removal for
that task are unscorable. Removal starts only from a complete valid baseline,
and both retained roles must remain valid. No invalid role is silently dropped;
no default score, compensation text, or automatic retry exists. Unscorable is
not incorrect and is not Keep Value zero. This prevents validity-dependent team
sizes from manufacturing labels and makes missing evidence auditable.

## 9. Removal replay and artifacts

Baseline and removal use the identical aggregator identity/config. Removal
deletes exactly one sealed `StructuredRoleOutput`; the other two byte/hash-bound
outputs are reused without execution or mutation. Gold-free removal artifacts
record task/protocol identity, baseline/removal input hashes, retained and
removed roles, both aggregation results, and `role_reexecutions=0`.

## 10. Gold isolation and evaluation

Gold is loaded only after baseline and all removal artifacts are separately
sealed and verified. It appears only in a downstream evaluation input, never in
prompts, output parsing, task hashing, tie breaking, aggregation, or removal
records.

Hard utility is primary: `U_hard(C)=1[selected_answer(C)==gold]`.
Hard Keep Value is `U_hard(C)-U_hard(C\{a_i})` in {-1,0,+1}. Evaluation records
the four correct/wrong transitions, answer change, and tie dependency.

Soft utility is auxiliary:
`U_soft(C)=S_C(gold)-max_{o != gold} S_C(o)`.
Soft Keep Value is the baseline margin minus removal margin. Exact baseline and
removed Gold score, best-wrong score, margin, delta, and exact-zero flag are
retained. No near-zero classification threshold is set here; any future
threshold must be frozen on a development split, not selected from test tasks.

## 11. Identity, safety, and verifier

All new Pydantic contracts reject extras and are frozen. Canonical hashes bind
schemas, role outputs, protocol config, tie order, and replay inputs. Execution,
counterfactual, and evaluation evidence remain distinct. The independent
verifier recomputes totals, exact means, task-hash order, selection, single-role
deletion, zero re-execution, and Gold absence without calling the production
aggregator. The package imports no model, network, GPU, or statistical library.

## 12. Gate 6.2A Structured-Score Smoke (not executed)

Proposed scope: the frozen 14 tasks, three roles, one explicit seed, 42 role
generations, Qwen3-8B/BF16 on one GPU, non-thinking strict JSON, new aggregation
only, no benchmark change, predictor, repair, or multi-seed work.

Recommended Go criteria, all pending human approval:

- JSON/schema validity at least 98%;
- zero unclosed thinking blocks and zero systematic token-cap truncations;
- baseline and removal scorable-rate thresholds explicitly approved before run;
- option-vector legality fully reported;
- soft Keep Value is neither constant nor all zero;
- nonzero soft values are not all tie-dependent;
- role vectors are not exactly identical on a large majority of tasks;
- no identity, hash, Gold, replay, or zero-reexecution violation;
- baseline accuracy, hard/soft distributions, role similarity, and total cost
  reported descriptively, without tuning thresholds on these 14 tasks.

No-Go includes any integrity/leakage/replay violation, systematic truncation,
unapproved configuration drift, or signal degeneracy above. A passing Smoke
only authorizes review of whether to design Gate 6.2B; it proves neither
predictability nor stability.

## 13. Decisions still requiring human confirmation

Approve or revise the generation values, evidence length cap, minimum baseline
and removal scorable rates, the quantitative role-homogeneity cutoff, and all
Go/No-Go thresholds before freezing Gate 6.2A. Multi-seed stability must be a
separate Gate 6.2B protocol after a passing single-seed Smoke.

**Hard stop:** this document and its implementation are offline design
artifacts. No model or real task is run in Gate 6.2.
