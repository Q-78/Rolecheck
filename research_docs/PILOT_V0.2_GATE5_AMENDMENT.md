# Pilot v0.2 Gate 5 Protocol Amendment

**Status:** Explicitly approved on 2026-08-04 for a complete Gate 5 restart.

**Authority:** This amendment supersedes only the Pilot v0.1 generation-length,
per-role timeout, and dry-run GPU-budget fields. All other frozen decisions in
`SERVER_PILOT_PLAN_v0.1.md` remain unchanged.

## Motivation

Pilot v0.1 Gate 5 completed all 42 role generations but produced 39/42 valid
extractions. All three invalid outputs came from one task and ended at the
4096-token cap with an unclosed thinking block. They were valid model outcomes,
not infrastructure failures, and were not retried.

## Revised condition

- protocol version: Pilot v0.2;
- `max_new_tokens`: 8192;
- per-role timeout: 300 seconds;
- Gate 5 GPU budget: 2 GPU-hours;
- full restart: all 14 tasks and all three roles;
- artifact root: `/data/qhy/rolecheck_server/artifacts/pilot-v0.2`;
- extraction-failure, semantic-quality, and wrong-answer retries: 0;
- infrastructure retry: at most 1, same seed, first failure retained.

The model revision, BF16 mode, sampling parameters, dataset manifests, task
order, Prompts, Role Contracts, seeds, parser, aggregation, concurrency,
network prohibition, and no-removal/no-evaluation boundary are unchanged.

## Evidence separation

Pilot v0.1 artifacts remain immutable and must not be overwritten or mixed with
Pilot v0.2. The v0.2 plan records the v0.1 file-list hash it supersedes. Passing
v0.2 Gate 5 requires the original Gate 5 acceptance criteria, including at
least 95 percent valid extraction and byte-equivalent aggregation replay.

## Hard stop

A successful v0.2 Gate 5 authorizes review only. Gate 6 remains prohibited
until the v0.2 artifacts and implementation are separately reviewed and merged.
