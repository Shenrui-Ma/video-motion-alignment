# R7 independent early-pose review

The primary event window50–65 is already near-aligned at x0 indices5/10/15: arm direction and normalized wrist position both give −1 frame at confidence thresholds0.3 and0.5. This independently supports the no-delay interpretation for the early states of this selected normal example. It does not estimate a population false-trigger rate.

Indices are zero-based model forwards:5/10/15 correspond to the6th/11th/16th completed model forwards. The original four windows and frozen metrics were used without outcome-driven selection.

| Snapshot index |50–65|69–81|80–92|99–111|
|---|---|---|---|---|
|5|near zero; direction/wrist −1/−1 at both thresholds|unknown|near zero;0/0|direction0 but wrist unavailable; unknown|
|10|near zero; −1/−1|.3 gives−1; .5 lacks coverage; unknown|near zero;0/0|near zero;−1/−1|
|15|near zero; −1/−1|.3 gives−1; .5 lacks coverage; unknown|near zero;0/0|near zero;−1/−1|

The conservative combined gate accepts8 of12 snapshot-window cells as near zero and retains4 as unknown. Each141-frame clip has one selected person in every frame and no multiple-person or selection-ambiguity frames. Local joint confidence and lag-shape ambiguity can still make an event unobservable; complete person detection is not sufficient.

All three decoder records and capture metadata were complete, each decode was tied by SHA to the independently downloaded actual x0 tensor, and actual141-frame1024×576/24fps geometry was checked. Pose was CPU-only, one worker at a time, with the old frozen evaluator/protocol. The setup-path failure occurred before any pose result and is retained separately.

This was chosen because its old final video was already normal. Final replay was exact at all141 RGB frames and actual conditioning/noise, but early labels above come from separate decoded-pose measurements. Other unmeasured x0 checkpoints remain without independent pose truth. Gap5 comparisons may use these labels without tuning thresholds; agreement on this single case is not a general observer validation.

Evidence: `early/compact_summary.json`, `early/results/x0_step005.observer.json` (and010/015), `early/intake_manifest.json`, `early/EARLY_POSE_COMPLETION.json`, and `replication/native_replay_local_gate.json`.
