# Gate 6.2A Structured-Score Smoke Result

**Decision:** NO-GO. The pipeline stops before Gate 6.2B.

## Frozen execution identity

- execution revision: `44326e4`;
- model: pinned Qwen3-8B revision, BF16, unquantized;
- physical GPU: index 1, UUID `GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65`;
- generation: non-thinking, 384-token cap, frozen Gate 6.2A parameters;
- scope: 14 Pilot tasks x 3 roles x 1 seed = 42 role generations;
- generation time: 239.424 seconds (0.0665 GPU-hours, below the 1-hour cap).

The initial invocation stopped before model load because the execution plan contained a forbidden `gold_loaded` key. The preserved preflight-abort artifact records zero generations and zero GPU seconds. The sole permitted infrastructure retry removed only that redundant key; tasks, roles, prompts, seeds, model, GPU, decoding parameters, thresholds, and analysis definitions were unchanged.

## Observed output quality

All 42 generations completed. Only 25/42 (59.52%) passed the strict JSON/schema contract; 17/42 failed. Failures were dominated by `option_scores` totals not equal to 100; two outputs also exceeded the three-item evidence limit. There were zero `<think>` tags, zero 384-token-cap hits, zero quality retries, and zero role re-executions. GPU 1 returned to 14 MiB after unload.

The result suggests that non-thinking short generation removed the earlier unclosed-thinking/token-cap failure mode, but did not reliably enforce the arithmetic and evidence-cardinality contract without a separately reviewed design change.

## Gate decision and artifacts

The required 42/42 validity criterion failed. Complete baseline/removal evaluation was therefore ineligible, Gate 6.2B is prohibited, and the Predictor-readiness pipeline stops here.

- sealed root: `/data/qhy/rolecheck_server/artifacts/pilot-v0.4/gate-6-2a-v0.1`;
- root files hash: `sha256:125feb18c1ecbe09610738d6be0233645d5c1fda959610f7cb6c0b074834e531`;
- preserved abort: `/data/qhy/rolecheck_server/artifacts/pilot-v0.4/gate-6-2a-v0.1-preflight-abort`.

No threshold, Prompt, task, model, seed, generation parameter, or validity definition was changed after observing results. This No-Go does not authorize a retry. A future attempt requires a new reviewed protocol and a new artifact root.