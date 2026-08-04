# Pilot v0.2 Gate 5 Result

**Decision:** Gate 5 execution completed but acceptance failed. Gate 6 is not
authorized.

## Frozen result

- tasks: 14/14;
- role executions: 42/42;
- model-free aggregations: 14/14;
- valid extractions: 39/42 (92.857 percent);
- required extraction threshold: at least 95 percent;
- generation time: 2,037.858 seconds;
- generation-engine identity: `sha256:7390c0df46c60faf4889877ffc71b451fb394e73164bcb217a9fc9ec133384a9`;
- plan hash: `sha256:63433dfd6d3139f69ce0e75f5572275500154e75ad29ac2598d10cb91fafa831`;
- artifact manifest SHA-256: `03d2922710171b0ebaba0752f56325a084e98fc692da34c5d629f400aed5914d`;
- artifact file-list hash: `sha256:49c415c16dc1725e65d34f3edcf8bdde87b607ba5b249e66fd9def100b839e15`;
- identity, mutation, leakage, and checkpoint violations: 0;
- aggregation replay: byte-equivalent by hash;
- evaluation and role removal: not performed.

All three invalid outputs were again produced for
`mmlu-pro-1cbdceede7c09ce4321f6812`. Each role emitted exactly 8192 tokens
and was rejected as `invalid_model_text:unclosed_thinking_block`.

An independent read-only verifier recomputed all inventory hashes, 14
checkpoint hashes, 42 role-output hashes, and 14 aggregation replays. It
passed. The model was unloaded and GPU 0 returned to 14 MiB used.

## Interpretation and hard stop

Increasing the cap from 4096 to 8192 did not improve the extraction rate. The
failure is systematic for this task under the frozen thinking-mode condition,
not a transient infrastructure failure. Do not rerun the task, increase the
cap again, loosen parsing, or enter Gate 6 without a new research review.
