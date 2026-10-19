# R15 independent decoded-endpoint measurement

Seven new VAE-only decodes and frozen CPU pose evaluations completed successfully. This provides a measured stopping-observer discrepancy on the development trajectory, and an early normal-case check. It does not establish a new stopping rule or its final-video efficacy.

## Primary window50–65

All indices below are zero-based physical Euler indices. Positive lag means the edited motion is later. Direction and wrist values list confidence0.3/0.5; the strict ±2 summary requires all four values known and inside the interval.

| History and endpoint | Internal native readout | Independent direction lag | Independent wrist lag | Strict ±2 |
|---|---:|---|---|---|
| R10 native10, exact R12 reuse | 2 | 4/4 | 4/4 | no |
| R10 native11 | 1 | 3/3 | 3/3 | no |
| R10 native12 | 0 | 2/2 | 2/2 | yes, first among these measured points |
| R10 native13 | 0 | 1/1 | 1/1 | yes |
| R10 native14 | 0 | 1/1 | 1/1 | yes |
| R14 native5 | −1 | −1/−1 | −1/−1 | yes |
| R14 native10 | −1 | −1/−1 | −1/−1 | yes |
| R14 native15 | −1 | −1/−1 | −1/−1 | yes |

R10's internal readout underestimates the independently measured lag by2 frames at10–12 and1 frame at13–14. This directly supports an observation-resolution/bias explanation for declaring the index10 native endpoint aligned too early; the endpoint itself still measures4 frames late. It does not justify a universal error margin or changing the threshold to0 based on this one history. R14's three early observations agree with independent pose on the primary window, rather than inheriting its normal final label.

Crucial trajectory limit: R10 native11–14 are counterfactual predictions evaluated on the actual fixed Full-at6..14 history. Full, not native, was chosen for those sampler updates. Consequently native12 reaching2 frames does **not** prove that choosing native12 and stopping the intervention would maintain the result at the end. Nor is index12 the globally first aligned denoising instant: only the specified points were independently measured here. R12 native10 reuse is supported by the actual R13 tensor bridge; R12 native15 is not substituted into this history.

## Same-support shape evidence and retained unknowns

On the intersection of source and all four R10 checkpoints, primary arm-direction support is1.000 at0.3 and0.875 at0.5. Same-frame errors at11/12/13/14 are respectively:

- confidence0.3:0.3360 /0.2152 /0.1683 /0.1337;
- confidence0.5:0.3081 /0.1844 /0.1355 /0.1041.

Thus the target-window improvement is not obtained by giving different checkpoints disjoint valid joints. R14's three-way primary support is1.000/0.96875; errors are0.1123/0.1168/0.1341 at0.3 and0.1104/0.1092/0.1293 at0.5. Stable phase does not mean every shape error monotonically improves.

All original windows and both thresholds remain in `pose/compact_summary.json` and the per-checkpoint observer files. Notable retained limits:

- Window69–81 is unknown at confidence0.5 for every checkpoint in both histories. Common arm support there is only0.6154 for R10 and0.5769 for R14, below the0.8 common-support criterion; its numerical errors cannot be promoted into a reliable main result.
- R14 native5 also has unknown direction phase at confidence0.3 in69–81 despite wrist0. This is not replaced with a final-label guess.
- R14 native15 window80–92 has direction−1/−1 but wrist0/unknown; its combined observability is unknown. The other measured R14 points in that window give direction/wrist0/0.
- R10 windows80–92 and99–111 remain near zero among measured checkpoints. Before0–46 and tail112–140 common-support direction errors do not show a gross increase over11→14; this is an exploratory shape screen, not a comprehensive quality pass.
- R14 tail112–140 error rises0.1086→0.1437→0.1469 across5/10/15. All are native endpoints, so this is trajectory evolution, not a treatment-side-effect estimate.

## Limited visual check

Actually inspected: R10native12 frames55/86/105; R10native14 frame55; R14native5 frame55; R14native15 frames86/105. The adult male gray-shirt/black-trouser edit and gross curtain/bench/table/cabinet layout remain visible. Hands have blur/soft outlines, particularly the wide-arm frame105; fine hand anatomy and exact identity are not certified. No full-video flicker or ghosting review was performed. R14 lacks the source upper-right logo, already a baseline edit difference, so pixel-perfect background preservation is not claimed. Other saved overlays are retained but not presented as reviewed.

## Integrity, cost and archive

Actual seven input files, complete source audits, branch/native type, seed, physical sigma, raw and normalized signatures were validated on CPU before decode. The R10 thin adapter returns the same video/audio objects and bytes and transparently labels counterfactual endpoints; it does not fabricate a chosen callback. R14 uses the original loader. The unchanged R12 decoder and same FP16 H3 VAE are SHA-bound. All output records are complete, all141 frames and24fps/uniform PTS pass, and all MP4 hashes match their records.

The root-scheduled VAE work adds0 DiT NFE. Seven sequential decoder process walls were42.63,44.34,42.03,44.53,43.55,46.72,44.79 seconds (sum308.57 seconds). Each exited0 with no remaining compute process; final GPU2 was8MiB/0%, independently rechecked by root. Two immediate intermediate utilization snapshots were7% with compute empty; the following decoder's strict idle admission and final idle check passed.

Frozen CPU evaluation took495.39 seconds, with pose extraction67.36–73.19 seconds per clip. No parameter sweep, new detector, package or threshold/window change occurred. ConsumerPID63214 and SSHPID65325 exited0 and the shared CPU lock was released. The initial preparation schema rejection and corrected exact metadata-key guard are retained in `PREPARATION_NOTE.md`.

Evidence: `input_inventory.json`, `input_cpu_validation.json`, `internal_readouts.json`, `reused_anchors.json`, `x0_decoded_execution.json`, `pose/intake_manifest.json`, `pose/completion.json`, all `pose/*.observer.json` and `pose/*common_support*.json`. Full raw MP4/JSON/logs are under `analysis/x0_decoded/`. `FINAL_ARCHIVE_MANIFEST.json` records the initial90-file completed download; `FINAL_REVIEW_MANIFEST.json` additionally binds this final review and summaries.

Both histories concern the same already studied source05: one selected problematic seed and one selected naturally normal seed. This is developmental evidence about these endpoints, not statistical observer calibration, a failure-rate estimate, or generalization to other videos.
