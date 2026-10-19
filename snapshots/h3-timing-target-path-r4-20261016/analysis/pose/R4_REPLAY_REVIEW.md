# R4 same-host passive replay gate

**PASS.** `r4_s05_native_path_probe` matches the archived .41 `r2_s05_native` baseline in all required checks: actual video/reference/text conditioning, full tokenization and packed positions, actual video/audio noise; all five common x0/final snapshots loaded on CPU and compared elementwise with raw tensor hashes verified against manifests; all141 decoded RGB frames, frame timing and video geometry. Both operator traces contain20 model forwards ×50 native blocks and zero routed updates.

This validates that the passive recording did not change the sampled native trajectory. It does not establish that a path in target features can repair motion, that the proposal is correct motion, or that a new architecture succeeded. Those are separate feasibility/intervention tests owned by the root lane.

No new DWPose run was needed. The previously frozen .41 native estimates are reused only after exact replay: confidence.3 lags14,12,11,6; confidence.5 lags14,unknown,11,6, over windows50–65/69–81/80–92/99–111. These are not additional independent samples. `replication/inherited_pose_reference.json` identifies their exact files and hashes.

R4 captures at zero-based forward indices6/10/14 mean the7th/11th/15th model forwards. The primary capture remains index6, not `x0_step005`. See `INDEXING_NOTE.md`; no execution or metric changed.

Exact evidence: `replication/native_replay_local_gate.json`, `replication/native_replay_actual_tensors.json`, `replication/native_replay_complete_gate.json`, and `pilot/r4_s05_native_path_probe_provenance/archive_manifest.json`. The failed initial warmup and repaired admission guard remain in the producer's separate archive and are not counted as scientific outputs.
