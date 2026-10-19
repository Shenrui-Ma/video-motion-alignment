# R8 selected-normal feedback control

The online controller stayed off for the entire selected normal case. All15 observer readings (zero-based callback indices5–19) were accepted and classified OFF_ALIGNED: lag0 at indices5/6 and−1 thereafter. Actual routed forwards and routed attention blocks are both zero. The20-forward/1000-attention-call state-machine audit passes.

All actual conditioning fields, tokenization, packed layout, pair snapshots and actual video/audio noise match R7. The executed graph matches outside the declared feedback actuator and administrative fields. All9 common captures (indices5/6/7/8/9/10/15/19 and sampler_final) match bitwise in both video/audio tensors, including the preintervention index5. All141 decoded final RGB frames, frame timing, geometry and timebase also match. New final DWPose was therefore unnecessary; existing final pose and already independently evaluated R7 early snapshots can be inherited.

| Measurement inherited from pixel/tensor equality | Result |
|---|---|
|Final original four-window lag, threshold0.3|−1,−1,0,−1|
|Final original four-window lag, threshold0.5|−1,unknown,0,−1|
|Early main window50–65 at indices5/10/15|direction and wrist−1 at both thresholds; near-zero gate|
|Early all12 snapshot-window combined gates|8 near-zero;4 unknown; unknowns retained|

This establishes no observed intervention harm on this deliberately selected known-normal case. It does not establish correction efficacy, an independently sampled specificity rate, broad robustness or a new seed. It cannot cancel the R6 delayed-case failure. Other R7 intermediate snapshots have tensor equality but no separate pose truth.

The observer recorded21.90s of synchronous copy/validation/normalization/readout/decision work (JSON writes excluded). Zero routed blocks do not imply zero controller overhead or faster end-to-end inference; NFE remains20.

Evidence: `replication/complete_replay_gate.json`, `replication/native_replay_local_gate.json`, `replication/common_actual_tensors.json`, `operator_execution_gate.json`, `replication/inherited_pose_reference.json`, exact-history intake manifest, and `R8_COMPLETION.json`. Both intake61524 and finalizer32868 exited0. No new GPU or DWPose process was started by the evaluator.
