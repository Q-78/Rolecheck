# Gate 6.2A Structured-Score Smoke Protocol v0.1

**Status:** FROZEN before execution.
**Purpose:** bounded format/signal viability test, not Predictor evidence.

## Frozen identities and inputs

- Existing frozen Pilot14: sha256:4ba4870594cd08b79dee57b73892dce22b6a024e0366ae599a641d6726da20b7.
- Qwen3-8B revision b968826d9c46dd6066d109eabc6255188de91218, BF16.
- Physical GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65 1, UUID GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65, sole visible GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65.
- Roles: domain, elimination, verification analysts; parallel independent; no tools.
- Master seed 2026080302; task-role seed derives canonically with namespace gate62a-role.
- Gate 6.2 v0.1 schema, aggregator, tie-break, invalid policy, and utilities.

## Frozen generation

enable_thinking=false, max_new_tokens=384, temperature=0.2,
top_p=0.9, top_k=20, do_sample=true. Strict JSON only. No quality
retry, parse repair, task replacement, parameter change, model fallback, or
constrained-decoding dependency. One infrastructure retry is allowed only
after preserving an abort artifact and must reuse every identity and seed.

Maximum generation budget: **1 GPU-hour**. One replica, sequential tasks and
roles, 180-second per-role timeout.

## Execution and sealing

Run 14 x 3 = 42 generations and seal execution. Produce 14 baselines and 42
single-role frozen-response removals and seal them. Only then load Gold into a
separate evaluation artifact. No Gold may occur in execution or removal.
Independent verification and root sealing follow evaluation.

## Hard Go/No-Go

All required: 42/42 valid JSON/schema; zero think tags, unclosed thinking blocks,
or systematic cap truncation; 14/14 scorable baselines; 42/42 scorable
removals; zero reexecution and identity/hash/leakage/mutation/replay violations;
at least 10/14 tasks with non-identical role vectors; at least 9/42 nonzero soft
Keep Values; nonzero soft values not all tie-dependent; soft values not a
single constant; independently reproducible tie-breaks; unchanged Gate 6 root
sha256:6e8bf5363c7cbc420dacc91fd9e7a67dba3581d48407197d7a2045914bc394e5; unchanged Gate 6.1A root sha256:7e1e8784385050b54e4be91db1a3e77ccbbac5b36cf0392be750529c4eb5776c; and generation below one GPU-hour.

Any failure is sealed and stops the pipeline. No threshold, prompt, task, or
generation setting may change after results are observed.
