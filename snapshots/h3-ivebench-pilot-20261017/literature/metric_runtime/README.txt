IVEBench official MF adapter

Author code: ../official_source/metrics/fidelity/motion_fidelity.py
Source/task manifest: ../../inputs_selection/PILOT_5_MANIFEST.json
Checkpoint: ../weights/baseline_offline.pth

1. Copy this literature runtime subtree to a dedicated remote directory, preserving
   official_source/, weights/, OFFICIAL_SOURCE_SHA.json and metric_runtime/.
2. Set TMPDIR/TMP/TEMP to that directory's temp/ on /data5; the server root /tmp
   was full. Reuse the existing comfyui Python environment; no install needed.
3. CPU compatibility check (uses existing remote consumer.lock):
   CUDA_VISIBLE_DEVICES='' python metric_runtime/run_cpu_check.py
   This constructs the exact offline CoTracker3 on CPU and runs seven numerical/
   timebase tests. It performs zero tracking forwards and requires CUDA remain
   uninitialized. Exit75 means the shared CPU lock is currently occupied.
4. Once real generated outputs and release records exist, bind all five tasks
   using INPUT_SCHEMA_EXAMPLE.json. The example is not an executable manifest.
   Each source/target scoring MP4 must contain the complete unshifted effective
   24fps prefix at1280x720. source_prepared_video binds the actual H3 90-frame
   input; source_preparation_record binds R54 input provenance, original SHA,
   exact frame map and decoded hashes. Source score pixels must equal its
   crop/prefix; output score pixels must equal the generated full-video crop.
5. CPU media preflight, under experiment owner CPU lock:
   python metric_runtime/ive_mf_adapter.py --manifest REAL.json \
     --selection REAL_PILOT_5_MANIFEST.json --output CHECK.json --check-only
6. After root's GPU admission and exact CUDA_VISIBLE_DEVICES selection:
   python metric_runtime/ive_mf_adapter.py --manifest REAL.json \
     --selection REAL_PILOT_5_MANIFEST.json --output RESULTS.json --device cuda
   This runs only official MF. It does not compute the 12-metric overall score.

Status: exact official model construction passed on .9 and .41 with no new
packages. .41 passed17 CPU tests and all5 source media preflights. Root admitted
source tracking on .41 GPU2; per-case receipts and completion state are recorded
separately. See host41/ and ../LAUNCH_PROTOCOL_HOST41.txt. Generated video scores
await the R54/R55 released outputs and root GPU admission.

The adapter checks manifest IDs/SHAs, sampling, PTS, source pixel mapping, and
output exact crop/prefix. Upstream generation/release JSONs are SHA-bound, while
their internal experiment semantics remain the producer/reviewer responsibility.
The source model is loaded only from pinned checkpoint path, avoiding hub fallback.
Original metric interpolation and matching formulas are unchanged, including its
compression of invisible-time gaps. Report pose physical timing separately.
