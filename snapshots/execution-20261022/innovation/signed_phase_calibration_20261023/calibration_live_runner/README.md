# Live-pair CPU calibration runner

This entry point connects the frozen live-trajectory validators and probability
analysis. It does not run or modify the model. The only admitted experiment is
`short_0358`, new `native` and `global_weak` trajectories, denoising steps 9 and
19, block 25, all 56 heads and the eight preselected spatial probes.

## Inputs and gating

`--inputs` is a JSON document with schema
`h3-live-calibration-runner-input-v1`. Paths may be absolute or relative to this
document. The required structure is:

```json
{
  "schema": "h3-live-calibration-runner-input-v1",
  "annotations": "new_paired_annotations.json",
  "methods": {
    "native": {
      "science_contract": "native_contract.json",
      "trajectory_gate": "native/TRAJECTORY_GATE.json",
      "observation_manifest": "native/OBSERVATION.json",
      "video": "native/final.mp4",
      "annotation_record": "native/ANNOTATION.json",
      "captures": {
        "9": {"qk": "native/qk_step009.pt", "state": "native/state_step009.pt", "numerical_check": "numerical/native/step009.json"},
        "19": {"qk": "native/qk_step019.pt", "state": "native/state_step019.pt", "numerical_check": "numerical/native/step019.json"}
      }
    },
    "global_weak": {
      "science_contract": "global_weak_contract.json",
      "trajectory_gate": "global_weak/TRAJECTORY_GATE.json",
      "observation_manifest": "global_weak/OBSERVATION.json",
      "video": "global_weak/final.mp4",
      "annotation_record": "global_weak/ANNOTATION.json",
      "captures": {
        "9": {"qk": "global_weak/qk_step009.pt", "state": "global_weak/state_step009.pt", "numerical_check": "numerical/global_weak/step009.json"},
        "19": {"qk": "global_weak/qk_step019.pt", "state": "global_weak/state_step019.pt", "numerical_check": "numerical/global_weak/step019.json"}
      }
    }
  }
}
```

Both complete gates, both new-video annotation records, all four QK and full AV
state files, and all four frozen-oracle numerical receipts are mandatory. The
runner checks their byte hashes and cross-links. It rehashes the actual packed
FP32 `x` and `x0` tensors against each forward identity. The full 21-point sigma
grid, initial noise hash, science contracts, complete 20-forward/1000-block
execution, no extra forwards, and original sampler return evidence must match.

Numerical receipts must come from the unchanged `replay_diagnostics/diagnose.py`
oracle. The runner validates their capture and forward identity, fixed policy
hash, all three branches and all 56 individual per-head bounds. It consumes
these existing oracle results rather than running the expensive oracle again.
This is an attestation boundary: a deliberately forged receipt is outside the
trusted local workflow. Numeric acceptance concerns the definition of captured
Q/K only.

The two videos have 107 encoded frames; all 105 valid frames must have been
reviewed. Three source event definitions are frozen. Each single-video record
must match the merged annotation, including unresolved events and reasons.
The video bytes are rehashed; frame count is the trusted prior video inspection
receipt, not a second video decode by this CPU entry point.

Across all four captures, spatial indices, full time support, padding mask,
time roles, tensor shapes, Q/K norm weights and epsilons, physical positions,
and stored RoPE values must agree exactly. No intersection, broadcasting, head
selection or omitted time step is permitted. The last physical bin spans
103–106 and is excluded because it crosses the 105-frame valid boundary.

Missing prerequisites and explicit unfinished observer/annotation states yield
`pending`. A failed gate, unknown method/step, changed hash, malformed metadata,
or failed numerical head yields `invalid`. In either case the output contains
only `STATUS.json`; there are no partial probability results. Use a **new output
directory** on every attempt. Existing outputs are never replaced.

## Execution and outputs

Run only on the host holding the actual tensors, after independent review:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  python calibration_live_runner/run.py --inputs inputs.json --output new_analysis_directory
```

All prerequisites pass before any probability computation. Output publication
is an atomic directory rename. The two NPZ files preserve all `[56,32,8,32]`
probabilities for `QnKn`, `QwKw`, `QwKn`, `QnKw`, and both reference-self readouts.
They also retain full per-head/probe paired means, self drift, contrast,
time-centered diagnostic, and symmetric Q/K attribution. Padding rows and
columns are zero. Small JSON summaries use the frozen source event windows;
generated-event-selected readouts are separately named descriptive results.

The symmetric attribution satisfies `DeltaQ + DeltaK = paired total`. It splits
the change in this retrieval readout by changed queries and keys. The result
does not label those components as motion or appearance and does not produce
an alpha controller. Actual tensor files and NPZ arrays stay remote; only the
small summary, status and hash receipts should return to the local workspace.

## Validation scope

Synthetic tests use complete H3-shaped QK tensors and full packed AV state
shapes with zero/known values. Their videos are synthetic byte identities, not
decoded video fixtures. The successful integration executes the actual frozen
normalization, retrieval, paired comparison and cross-key functions. Negative
tests exercise prerequisite classification, failed gates, wrong media/state
identity, actual state tensor signature, norm/layout mismatch, malformed
per-head numerical receipts, changed source windows, and atomic zero-results
failure behavior. No live capture is read by these tests.
