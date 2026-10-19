# R7 final native replay verification

R7 exactly reproduces the selected old 1024×576 native final output: all actual conditioning fields and actual video/audio noise match; 20 forwards × 50 native calls and zero routed calls are verified; all 141 decoded RGB frames, frame timing and stream geometry/timebase match. Container hashes differ, which does not invalidate decoded equality.

Only final pose measurements are inherited. The early x0 callback-index5 pose has not yet been independently evaluated. A normal final result does not establish that an early readout is already normal. There is no old x0 capture against which to claim intermediate replay equality.

This is a deliberately selected known-normal negative control, not a new independently sampled example.

| Confidence threshold | Original four-window signed lags (frames) |
|---|---|
| 0.3 | -1, -1, 0, -1 |
| 0.5 | -1, unknown, 0, -1 |

Positive lag means edited motion is later. Frozen confidence/coverage/ambiguity rejection remains unchanged.

Evidence: `replication/native_replay_local_gate.json`, `replication/inherited_final_pose_reference.json`, exact-history intake manifest, and `R7_FINAL_REPLAY_COMPLETION.json`. One CPU-only intake/replay chain completed with exit0; no new DWPose or GPU process was started.
