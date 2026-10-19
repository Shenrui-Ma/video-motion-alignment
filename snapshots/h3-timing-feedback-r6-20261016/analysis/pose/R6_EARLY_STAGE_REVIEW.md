# R6 independent saved-stage pose checks

The first preintervention x0 (zero-based index5) contains a reliably delayed primary event: direction and normalized wrist position both give14 frames at confidence0.3 and0.5, with the frozen conservative gate accepting phase for manual review. This confirms a delayed state before the first possible routed forward6. The latent controller readout was11, a3-frame underestimate here; it still has the correct coarse trigger category, but is not an exact timing measurement.

| x0 index |50–65 direction (.3/.5)|69–81 direction|80–92 direction|99–111 direction|
|---|---|---|---|---|
|5|14/14; wrist14/14, phase available|unknown/unknown|12/unknown|9/9; wrist8/unknown, combined unknown|
|10|13/unknown; wristunknown, combined unknown|unknown/unknown|10/10; wrist10/unknown, combined unknown|6/6; wrist6/6, phase available|
|15|unknown/unknown|11/unknown|9/9; wrist10/unknown, combined unknown|6/6; wrist6/6, phase available|

The combined conservative gate yields3 phase-available cells and9 unknown cells across the12 snapshot-window combinations. Unknown does not mean aligned or failed. The remaining delayed final result is separately established by final-pose analysis; this sparse stage check cannot identify exactly when persistent correction failed.

The requested indices6/7/8 were never saved by the actual R6 recorder. The earlier four-point plan was cancelled before CPU evaluation; no reconstructed surrogate was substituted. Consequently the controller-log sequence11→1→12 at indices5/6/7 has not been independently verified as decoded-pose rebound. The existing5/10/15 files are stage checks only. New runs with broader capture can test the mechanism, but cannot retroactively supply missing R6 tensors.

All three decode records were complete and bound to the actual producer snapshot SHA and capture metadata; actual141-frame1312×736/24fps geometry was verified. Frozen source-pose, evaluator, protocol, windows and confidence thresholds were retained. CPU evaluation was serial and used no GPU.

Evidence: `early/compact_summary.json`, `early/results/x0_step005.observer.json` (and010/015), `early/intake_manifest.json`, `EARLY_STAGE_PROTOCOL.json`, and `early/EARLY_STAGE_COMPLETION.json`.
