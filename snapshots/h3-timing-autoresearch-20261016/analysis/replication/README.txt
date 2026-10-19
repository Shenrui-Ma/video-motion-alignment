Archived Sam05 x3 reuse review — preparation, 2026-10-16

Current decision: ELIGIBLE AS ARCHIVED PAIRED CONTROL. All listed gates passed; see archived_pair_reuse_audit.json. Do not count the old x3 as a newly executed result.

The archived pair is genuinely paired at recorded input level:
- Baseline and x3 executed graphs match both the stored Comfy history and job graph SHA.
- Both histories completed successfully; each intervention audit completed 50 blocks × 20 forwards.
- The actual conditioning snapshots, including both reference latents, embedding, token tags, target geometry and position IDs, are equal.
- Video and audio initial-noise hashes are equal. Both noise streams and both stored clean reference latents were reloaded on CPU and rehashed successfully.
- The x3 history explicitly lists node 5 as cached, corroborating its shared-condition provenance.
- The full-resolution new graphs now bypass ImageScale, preserving the original source path. Scientific fields match the archived graphs after removing only task IDs/output paths and normalizing the native inactive-patch interface.
- H3EventEmphasis and H3PairAudit source hashes match the original executed provenance. H3EventAudit differs only in allowed task directory strings. Bootstrap and INT8 row-chunk code are also identical.

Gates that were required and have now passed:
1. New full-native history must show success and the reviewed graph.
2. New full-native actual conditioning and noise signatures must equal the old baseline (not merely the configured seed).
3. Every decoded RGB24 frame with its timing record must match the old baseline. The check includes all 141 frames, not a montage or pose score.
4. Parent must retain current runtime preflight evidence. Shared core/model manifests here are inherited evidence, not a fresh remote package/checkpoint sweep.

Run after those files are local:
/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python /Users/researcher/DevProjects/h3-timing-autoresearch-20261016/analysis/replication/check_archived_pair_reuse.py

The script is CPU-only, never imports ComfyUI or contacts a server, and writes only under this replication directory. It will keep eligibility false on missing artifacts or any mismatch. It also records original baseline/x3 frame hashes, input file hashes, actual condition signatures, noise hashes, graph hashes, and explicit limitations in archived_pair_reuse_audit.json.

If eligible: use the old result as an ARCHIVED paired control with the old run ID/date, not as another seed, independent sample, new runtime measurement, or evidence that the new mechanism succeeded. Its computational result may be reused to avoid redundant execution; its evidential weight is not increased by reuse.

If any gate fails: do not silently relax the criterion or substitute visual similarity. Diagnose the mismatch and rerun x3 in the new environment for the strict comparison. Full native decoded equality is stronger than approximate pose similarity but still does not prove every hidden tensor or final latent is bitwise identical, since the archived videos are lossy H.264.

Review caution: ImageScale at an unchanged requested size has no identity early return. Its Lanczos branch round-trips through PIL uint8; this is exact for uint8/255 samples, but not for arbitrary float32 image values. Removing that unneeded node from the full-resolution reproduction was the cleanest solution.
