# RoleCheck Gate 4 Smoke Freeze v0.2

**Status:** Gate 4 artifact candidate awaiting independent review. Gate 5 has
not started and is not authorized by this file.

**Base:** PR #9 merge commit
`3509b8af80d8e4ec2ed55fe138af082980a8749c`.

## Preflight

- Gate 2-A model configuration and all five model-shard hashes reverified;
- only GPU 0 was exposed during inference;
- GPU 0 UUID: `GPU-6514ee9f-3332-392a-8523-032a122d9969`;
- pre-load free memory: 40,313 MiB;
- no compute process was present;
- artifact disk free: 1,295 GB;
- inference used offline/local-files-only mode.

## Predeclared smoke

- selection: first task in the canonical Gate 3 v0.2 Pilot-14 order;
- task: `mmlu-pro-b756577dff7531985319392a`;
- role: `domain_analyst` only;
- model: pinned Qwen3-8B revision, BF16, GPU 0;
- quantization: false;
- CPU offload: false;
- timeout: 180 seconds;
- answer evaluation: not performed.

## v0.2 result

- status: `PASS`;
- input tokens: 413;
- output tokens: 631;
- generation latency: 21,221.73 ms;
- terminal-answer parse: valid;
- role-output hash:
  `sha256:3590d42d8772849d121b692910bfd03b1d812db1a86af0b7f325190d010feeb9`;
- artifact-file inventory:
  `sha256:c90eaadd9c6f9174fabd59f17357154af20b781d36153540219f78b649c0299f`;
- engine source:
  `sha256:15b173be27269250cc63416d493fdf2976e01111a67376f95ae756756ffdcd0c`;
- runner source:
  `sha256:99305f7a803f863e4fba8c18eeed3262d947e1d508c50bdab1e4b17d2c2e0c72`.

Artifacts remain outside Git at
`/data/qhy/rolecheck_server/artifacts/pilot-v0.1/gate-4-smoke-v0.2`.
An independent verifier validated the predeclared plan, code hashes, engine
identity, BF16 GPU placement, raw/parsed output model, output hash, latency,
artifact hashes, and non-evaluation boundary.

After unloading, GPU 0 returned to 14 MiB used / 40,313 MiB free with no
compute process.

## Superseded v0.1 evidence

The preserved v0.1 artifact inventory
`sha256:d6d26d14d5fedcdb759428596a5c2c70fc9cb8686a61d2599686eb66d16bb270`
completed successfully but emitted a Transformers warning because no explicit
attention mask was supplied when pad and EOS token IDs were equal. v0.2 passes
an explicit all-ones attention mask and produced no such warning.

## Hard stop

Do not run the 14-task dry run until this Gate 4 code and artifact freeze are
independently reviewed and merged. Gate 5 must remain a separate branch and PR.
