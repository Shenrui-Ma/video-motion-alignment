# R15: independently decode the stopping-observer diagnostic

Prepared 2026-10-16. This is a seven-VAE diagnostic, zero new DiT/NFE. This agent has not launched a GPU. The root agent schedules GPU admission and execution.

## Actual inputs and minimum work

All seven exact files exist on `.9` and their actual SHA values match the original complete run records. Full paths, file SHA, normalized video SHA, seed, physical sigma and index are in `input_inventory.json`. `input_cpu_validation.json` checks the real tensors and schemas, finite FP32, raw/normalized signatures, original objects unchanged and no CUDA initialization. Seven bad-hash cases and an unregistered input are rejected. The input files and original decoders are untouched.

| Original run | Physical indices, zero-based | Interpretation | New VAE decodes |
|---|---|---|---|
| `r10_s05_fixed_full_probe` | 11,12,13,14 | Native counterfactual predictions on the fixed Full-at-6..14 chosen trajectory; these four predictions were not selected sampler callbacks | 4 |
| `r14_s05_seed1313_native_host9` | 5,10,15 | Native selected x0 estimates, policy OFF, new seed 2026101313 | 3 |

No matching decoded cache was found in the audited R1/R3/R10/R12/R14 known decoder output locations or the local R10/R14 trees. R12 index10 is already decoded at `/data5/researcher/h3_runs/timing_native_observer_r12_20261016/analysis/pose/x0_decoded/x0_step010.mp4` and is reused only as the left anchor: its normalized video/audio tensors equal R10 native10 by the completed R13 bridge. Its independent direction and wrist estimates are 4/4 frames. R14 final pose is already measured and can be reused as final anchor (direction/wrist −1/−1); early labels remain unknown until independently measured. R12 index15 must not replace R10 index15: the histories differ.

## Exact model and runnable commands

Host `H3_SERVER_A`, remote root `/data5/researcher/h3_runs/timing_pose_observer_r15_20261016`, existing Python `/home/researcher/miniconda3/envs/comfyui/bin/python`.

The thin `scripts/decode_endpoint.py` imports unchanged R12 `scripts/decode_x0.py`, SHA `799e64e1d2e1dab3582fe4600fea810c388facbab447fd0887dc51f4a1494014`. For R14 it retains the original loader. For R10 it validates the original branch audit and returns the exact same tensor objects with transparent counterfactual metadata; it does not forge a chosen callback or alter/scalize the video tensor. The original video VAE decode and encoder functions are reused unchanged.

VAE `/data5/researcher/ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors`, SHA `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522`; existing Comfy core `/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI`, dependencies sibling `runtime_deps`. Native full-latent FP16 VAE,141 frames,1312×736,24fps,no interpolation,H264CRF16; compare tensor/preencode RGB for replay, not MP4 container SHA alone.

Print all exact commands, without starting a GPU:

```sh
/home/researcher/miniconda3/envs/comfyui/bin/python /data5/researcher/h3_runs/timing_pose_observer_r15_20261016/scripts/run_seven_decodes.py
```

Root-only scheduled start, after live GPU2 UUID admission and ensuring no owned model process remains:

```sh
/home/researcher/miniconda3/envs/comfyui/bin/python -u /data5/researcher/h3_runs/timing_pose_observer_r15_20261016/scripts/run_seven_decodes.py --execute
```

It sequentially launches seven fresh decoder processes, each independently checks UUID `GPU-REDACTED` is ≤64MiB,0% and compute-empty twice before CUDA. It refuses overwrite/retry of an existing batch, records every command/PID/exit/wall time, output hashes and per-child GPU cleanup. No global CPU lock is held while waiting on VAE. Failure stops the batch and preserves evidence. Root separately checks final launcher/decoder PIDs absent and GPU empty before any next task.

## Minimum measurement and interpretation gates

1. Admit only complete decode JSON bound to the exact source file SHA, same VAE SHA, finite141×736×1312×3 output, actual141frames/24fps/uniform PTS. Preserve failed/unknown outputs.
2. Frozen DWPose and timing scripts, original source05 pose; no new thresholds. Four original windows50–65,69–81,80–92,99–111, thresholds0.3 and0.5, ±24-frame lag search, direction and wrist plus existing sensitivity features. Use a single CPU worker under the shared lock only during actual extraction/evaluation, ≤4threads.
3. A measured checkpoint is reliably within ±2 only when BOTH direction and wrist are known at BOTH thresholds and all four absolute lags ≤2. Keep every unknown/multimodal/low-confidence result; never fill it with final-video labels. This strict summary is additional reporting and does not alter frozen metric code or its existing status labels.
4. Report the first passing checkpoint **among the measured indices**, not globally earliest denoising time. Record shape/common support and all four windows; inspect only fixed55/86/105 frames if needed. No threshold scan, changed windows or hidden exclusions.
5. R10 reads native endpoints at Full-evolved states; seeing a corrected endpoint does not prove stopping intervention there would retain correction through the remaining sampler steps. R14 is one preselected naturally normal final example, not independent population calibration or general validity.
6. Record NFE0, VAE wall time, CPU pose time, failures and archived hashes. Efficiency is logged only, no speed-focused experiments.

The shared remote CPU lock is `/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock`. A coordinator wait must not hold it. No new runtime, package installation or configuration/extension edits are part of this task.

`scripts/consume_completed.py` is the unique local coordinator. It waits at61-second intervals without the global CPU lock, admits the completed seven-child execution and cleanup records, downloads hash-bound MP4/JSON/logs, then acquires the shared local CPU lock for one remote call to `scripts/evaluate_decoded.py --execute`. That evaluator independently takes the shared remote CPU lock only during actual processing. The original protocol text is copied byte-for-byte into `analysis/intermediate_observer_protocol.txt` because the old remote configs location did not contain it; its frozen SHA is checked. All metric code and source pose remain at their old paths and are SHA-checked before use.

The coordinator was started only after the root announced the real VAE batch launch. It is single-instance through `analysis/consumer_coordinator.lock`; no second coordinator should be started while it owns that lock. `analysis/consumer_state.json` exposes PID, phase and whether the global CPU lock is held. A failed SSH during CPU work requires inspecting the existing remote process before retrying; there is no automatic duplicate worker.
