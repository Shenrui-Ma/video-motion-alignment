Frozen CPU offline feature mapping check, 2026-10-16

Scope
Only this analysis directory changes. No model, inference service, GPU, dependency install, queue, feature capture or rendering is touched. Actual post-attention/pre-W_O X has both source and target context mixed. It is not V, isolated motion, or correct edited-action ground truth. The fitted native target may have wrong timing. A passing numerical gate does not establish correction, novelty or generalization.

Data and exact order
1. Freeze source activity groups BEFORE reading target features. Use actual EventAudit prepared RGB tensor by metadata path, CPU torch.load(mmap=True). Do not download the 1.63 GB tensor. Verify actual contents SHA and shape [141,736,1312,3], plus clean-reference hash before reusing position-bin map.
2. Wait for block25 step006/010/014.pt and their actual router capture records. Preserve BF16 source storage, [1,4,42,23,41,128], strip only validated batch1; fit individual tiles in FP64. No all-feature FP64 allocation.
3. Per-head pooled NMSE then equal four-head mean. Call6 val and post each need >=10% gain over the best equal-head I/D/A mean, >=3 heads improving over their own best baseline, with all four heads satisfying >=80% common support and >=25% identifiable energy. Do not drop a failed head. Rank0 unknown; rank1+ reported without adding a threshold. This interpretation was confirmed by protocol author before actual target data were read.
4. Calls10/14 are diagnostic. The event split never selects parameters. Unknowns and failed support remain recorded. All parameters, temporal bins, samples, spatial tiles and heads are frozen in FROZEN_PROTOCOL.txt.
5. Native replay passivity requires the root's independent same-hardware output comparison. This CPU tool reports it as not certified; it cannot replace that gate.

Existing Python: /home/researcher/miniconda3/envs/comfyui/bin/python
Remote analysis directory: /data5/researcher/h3_runs/timing_spatial_r3_20261016/analysis/feature_mapping
Run from remote root /data5/researcher/h3_runs/timing_spatial_r3_20261016.
Use environment CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1, and nice -n 10 if appropriate. No CUDA-visible device. Python explicitly also disables CUDA and uses one torch thread.

First command:
/home/researcher/miniconda3/envs/comfyui/bin/python analysis/feature_mapping/evaluate_mapping.py freeze-groups --condition audit/r3_s05_native_conditioning.json --locator analysis/feature_mapping/encoded_reference_locator.json --audit-root audit --output analysis/feature_mapping/source_groups.json

Second command, after all three snapshots exist:
/home/researcher/miniconda3/envs/comfyui/bin/python analysis/feature_mapping/evaluate_mapping.py evaluate --condition audit/r3_s05_native_conditioning.json --locator analysis/feature_mapping/encoded_reference_locator.json --groups analysis/feature_mapping/source_groups.json --router audit/router/r3_s05_native.json --feature-dir audit/native_features/r3_s05_native --noise audit/r3_s05_native_noise.json --runtime-provenance configs/runtime_provenance.json --output analysis/feature_mapping/results_native

Outputs are exclusive: source_groups.json, results_native/frozen_input_audit.json, per-call fits/edges/summary and RESULTS.json. Failed execution leaves its directory for audit; do not overwrite or alter parameters. All numeric unknowns stay JSON null or explicit unknown, not zero error.

Twelve local CPU synthetic tests cover known off-diagonal map, coordinate equivariance, fixed ridge, no future target use for advection, one-token cutoff, zero/rank/nonfinite rejection, shared support, summed NMSE, zero-signal full-grid pipeline, actual-content hash rejection, source ranking tie rule and ROI tampering. These tests are not real H3 scientific evidence. Real feature hashes/metadata are checked separately at execution.
