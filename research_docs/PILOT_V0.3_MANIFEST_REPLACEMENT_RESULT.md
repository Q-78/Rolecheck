# Pilot v0.3 Manifest-Replacement Gate 5 Result

**Decision:** Gate 5 passed after an explicitly authorized post-hoc task
replacement. Gate 6 remains subject to separate review.

## Manifest revision

The systematically nonterminating business task
`mmlu-pro-1cbdceede7c09ce4321f6812` was removed. It was replaced by
`mmlu-pro-2f26cf3d46b486e19a37a4e9`, the next unused business task in the
original label-blind canonical order.

- revised Pilot14 manifest: `sha256:4ba4870594cd08b79dee57b73892dce22b6a024e0366ae599a641d6726da20b7`;
- revised Pilot56 manifest: `sha256:5ad1b96bd7e28e4fa22131cfb518d3a3ecb87d983a1aa711c0b77fc0707e785a`;
- replacement manifest files hash: `sha256:7dc207d7ba7bd3cd85026befed4780299b41fb3bca37d6ab6146ee46183e39c0`.

No answer, rationale, label, role output, or correctness field was consulted when
selecting the replacement. Pilot14 remains a subset of Pilot56.

## Execution condition

The only scientific condition changed from Pilot v0.1 is the task manifest.
Thinking mode, 4096-token maximum, sampling, Prompts, roles, parser, seeds,
aggregation, retry rules, and one-GPU-hour budget were restored unchanged.

GPU 0 was occupied by an unrelated service. With explicit approval, execution
used physical GPU 1
(`GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65`) as the sole visible device;
inside the process it remained logical `cuda:0`.

## Gate 5 result

- tasks: 14/14;
- role executions: 42/42;
- valid extractions: 42/42 (100 percent);
- model-free aggregations: 14/14;
- generation time: 1,375.828 seconds;
- engine identity: `sha256:f8b0365f4d0bd832b4edfbfeab3f20c8b3113702635c62a155b8d90714d8e476`;
- plan hash: `sha256:2c846310609c3085c32646b0e58aa70d4fb5cec90b77742d73850001aac63d8e`;
- artifact manifest SHA-256: `afcaac6bf605de35ac0bbb928f5fe90c68cce984f23527ffc351ea766b7dc2d7`;
- artifact files hash: `sha256:ecfc2405629391e4787854b6dab88afbc016076da38b352835dae3ef8009b6aa`;
- identity, mutation, leakage, and checkpoint violations: 0;
- aggregation replay: byte-equivalent by hash;
- evaluation and role removal: not performed.

An independent read-only verifier recomputed every inventory, checkpoint, role
output, and aggregation hash. GPU 1 returned to 14 MiB after unload. The
unrelated GPU 0 process was not modified.

## Claim limitation and hard stop

This pass supports infrastructure readiness only for the revised executable
task set. Because replacement was triggered after observing systematic model
nontermination, the result is not an unbiased estimate of format reliability
under the original MMLU-Pro sampling rule.

Do not enter Gate 6 until this implementation, the revised Pilot56 manifest,
the post-hoc selection limitation, and the physical GPU revision are reviewed
and merged separately.
