# Gate 6.1A Result Summary

**Status:** exploratory post-Gate-6 analysis completed; not a frozen scientific conclusion.

## Identity and scope

The source was the sealed Gate 6 root `/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-6-controlled-pilot-v0.2`, files hash `sha256:6e8bf5363c7cbc420dacc91fd9e7a67dba3581d48407197d7a2045914bc394e5`. Gate 6.1A used only the 168 sealed role outputs and the frozen deterministic aggregator. No model, GPU, hosted API, network data source, role re-execution, predictor, repairer, or defect injection was used.

The strict preflight independently verified all frozen root/execution/removal/evaluation/Pilot56 hashes, 56 unique tasks, the exact three roles, 168 unique task-role outputs, 149 valid output extractions, every role-output/checkpoint hash, aggregator identity, 56 baseline replays, 56 original response-drop replays, zero retained-role re-executions, Gold/TaskSpec separation, and the original 18/18/20 target allocation.

## Original 56 hash-assigned removals

The legacy all-task scoring replay is baseline 43/56 (76.79%) and removal 41/56 (73.21%), delta -3.57 percentage points. Under Gate 6.1A's stricter scorable distinction, six removal outcomes are unscorable and must not be treated as wrong or zero. The transition matrix is: correct→wrong 2, correct→correct 39, wrong→correct 2, wrong→wrong 7, unscorable 6. Thus the net difference alone only gives `correct_to_wrong - wrong_to_correct = 0` over jointly scorable cases; the legacy two-answer difference also includes two baseline-correct/removal-unscorable cases and cannot imply that every role has positive value.

Keep values are +1: 2, 0: 46, -1: 2, unscorable: 6. By target: domain 1/15/0/2; elimination 0/15/2/1; verification 1/16/0/3 (order +1/0/-1/unscorable). Seven answers changed. Baseline tie-breaks: 1/56; removal tie-breaks: 5/56; invalid-vote-related: 8/56. All four nonzero jointly scorable labels were tie-dependent.

## Exhaustive 168 removals

There are 153 valid labels and 15 unscorable records. Distribution: +1: 6, 0: 143, -1: 4, unscorable: 15; mean keep value over scorable labels is 0.01307, deterministic bootstrap 95% percentile interval [-0.02614, 0.05229] (10,000 samples, seed 6101). The transition matrix is correct→wrong 6, correct→correct 121, wrong→correct 4, wrong→wrong 22, unscorable 15. Exact exploratory McNemar/binomial p=0.75390625.

By role (+1/0/-1/unscorable): domain 1/49/1/5; elimination 3/47/2/4; verification 2/47/1/6.

By domain (+1/0/-1/unscorable): biology 0/12/0/0; business 0/6/0/6; chemistry 0/11/0/1; computer science 0/12/0/0; economics 0/12/0/0; engineering 2/4/0/6; health 0/12/0/0; history 2/10/0/0; law 2/8/2/0; math 0/11/0/1; other 0/9/2/1; philosophy 0/12/0/0; physics 0/12/0/0; psychology 0/12/0/0. The sealed statistics retain the complete per-task three-role vectors.

Baseline vote patterns across the 168 task-role records are unanimous 123, 2:1 18, all-different 3, and contains-invalid 24. Eleven removal answers changed (6.55%). Baseline tie-breaks occurred in 3/168 records and removal tie-breaks in 15/168; 15/168 labels were tie-dependent. All 10 nonzero labels were tie-dependent, so excluding tie-dependent records leaves 138 zero labels and 15 unscorable records, mean 0. Excluding invalid-vote-related records leaves +1:6, 0:134, -1:4, unscorable:0, mean 0.01389. These sensitivity results supplement rather than replace the main result.

## Extraction quality

Recomputed extraction was 149/168 valid. By role: domain 50 valid/6 invalid, elimination 49/7, verification 50/6. All 19 invalid records are `invalid_model_text:unclosed_thinking_block`, all exactly 4096 output tokens; valid outputs average 1167.42 tokens, median 853, maximum 3814. Invalids occur in business 6, chemistry 3, engineering 6, math 2, and other 2; the other nine domains have none. The role invalid rates (10.7%, 12.5%, 10.7%) do not show a large role-specific disparity in this bounded sample; the failures are instead perfectly concentrated at the token cap with unclosed thinking.

## Artifacts, verification, and limits

The independent Gate 6.1A artifact is `/data/qhy/rolecheck_server/artifacts/pilot-v0.3/gate-6-1a-posthoc-analysis-v0.1`, files hash `sha256:7e1e8784385050b54e4be91db1a3e77ccbbac5b36cf0392be750529c4eb5776c`. Its independent verifier passed 168 unique task-role records, exact single-role drops, retained hashes, zero re-executions, Gold separation/order evidence, summary reconstruction, inventory, and sensitive/model-file checks.

These results support only deterministic, single-seed, fixed-response marginal contribution descriptions for this sealed Pilot56 run and aggregator. They do not establish predictor feasibility, causal generalization, repair value, model robustness, multi-seed stability, or a formal paper conclusion. A separately reviewed Gate 6.1B multi-seed protocol is recommended before any stability claim, but this summary does not authorize it.
