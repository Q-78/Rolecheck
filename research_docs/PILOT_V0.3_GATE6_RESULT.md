# Pilot v0.3 Gate 6 Controlled-Pilot Result

**Decision:** Gate 6 passed its bounded infrastructure acceptance criteria. This authorizes review of infrastructure readiness only; it does not validate the RoleCheck prediction or repair hypotheses.

## Frozen execution condition

Gate 6 used the revised Pilot56 manifest
`sha256:5ad1b96bd7e28e4fa22131cfb518d3a3ecb87d983a1aa711c0b77fc0707e785a`
and the same three-role Pilot v0.3 condition accepted at Gate 5. Physical GPU 1
(`GPU-4e95c047-cd1c-adaf-4f25-aaa9fdbe6b65`) was the sole visible device;
inside the process it was logical `cuda:0`.

The first Gate 6 attempt stopped after six complete task checkpoints when the
seventh task's `domain_analyst` exceeded the frozen 180-second role timeout.
The immutable abort record was retained. Gate 6 v0.2 superseded that attempt,
validated and byte-copied the six checkpoint payloads, retained the original
seed, and consumed the one allowed infrastructure retry for the failed role.
The retry succeeded. No answer-quality or extraction retry occurred.

## Baseline execution

- complete task records: 56/56;
- role executions: 168/168;
- model-free aggregations: 56/56;
- valid terminal-answer extractions: 149/168 (88.69 percent);
- aggregation replay: byte-equivalent by hash;
- identity, mutation, leakage, and checkpoint violations: 0;
- generation time, including the superseded attempt: 8,865.097 seconds
  (2.463 GPU-hours, below the 8 GPU-hour cap);
- plan hash: `sha256:51b58ee4bfe877a9ee41dbe02c4dcb506461c0155fc4a15f1a7250693e42118e`;
- execution files hash:
  `sha256:cbb0332c7861252f158a1ba9fd30bf12b0a09c83831f0d3d8101c13e9b6f1d3b`.

Invalid answer extraction is retained as an invalid vote and is not a runtime
execution error. Gate 6 has no minimum extraction-rate acceptance threshold;
this observed rate must nevertheless remain visible in any later analysis.

## Controlled removal

Stable task-hash assignment selected exactly one target for each task:

- `domain_analyst`: 18;
- `elimination_analyst`: 18;
- `verification_analyst`: 20.

All 56 safety reports validated. Every intervention reused the two retained
baseline outputs, reproduced the baseline aggregation before removal, performed
only model-free re-aggregation, and recorded zero role re-executions.

The first removal postprocessor invocation safely abstained on the first task
because the generic runner compared the frozen human-readable aggregation
protocol descriptor only with the aggregator machine ID. No gold was loaded.
That attempt is preserved as `removals-attempt-1-abort`. The implementation was
repaired without changing the frozen team: the deterministic aggregator now
exposes its frozen protocol descriptor, and the runner accepts either a machine
ID binding or an exact explicit descriptor binding. The repaired first-task
preflight passed every safety check before the complete removal run began.

Removal files hash:
`sha256:b299840a31eee90a56f9f8b5db92b6dc4a73eb36a55759307bcb13328e53b173`.

## Post-execution evaluation

Gold labels were first loaded after execution and removal artifacts were
separately sealed.

- baseline: 43/56, accuracy 0.767857;
- controlled removal: 41/56, accuracy 0.732143;
- absolute delta: -0.035714 (-3.57 percentage points).

Evaluation files hash:
`sha256:c3ab66bb924a8f3b8c80d0032dc6da79f7f70940185de2bf7b637f5c6f9a7070`.
The final root files hash is
`sha256:6e8bf5363c7cbc420dacc91fd9e7a67dba3581d48407197d7a2045914bc394e5`,
and the root seal records `gate6_complete: true`.

No predictor was fit, no repairer ran, and no defect injection was performed.
GPU 1 returned to 14 MiB after model unload.

## Interpretation and stop boundary

The hash-assigned target is an infrastructure test, not a RoleCheck prediction
or recommended intervention. The observed accuracy delta does not show that a
learned pre-execution policy can identify valuable roles. The Pilot56 set also
retains the disclosed post-hoc task-replacement limitation from Gate 5.

Stop after Gate 6 review. Do not begin predictor fitting, calibration, defect
injection, repair generation, or a larger formal experiment without a new
reviewed protocol and explicit authorization.
