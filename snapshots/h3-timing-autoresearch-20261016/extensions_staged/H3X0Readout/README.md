# H3 passive x0 readout — staged v1

This is an observer diagnostic, not a new guidance method. It does not modify
attention, conditioning, noise, sigma schedule, model predictions or sampling
results. It copies x0 to CPU at zero-based Euler steps **5, 10, 15, 19** (model
calls 6, 11, 16, 20), normalizes these copies with the current H3 model, and writes
each immediately. Step 19 is explicitly an endpoint sanity observation.

Status: **staged, not installed in the live Comfy service**. The running model,
service and existing configs have not been changed by this implementation.

## Installation and exact graph change — root operator only

After the existing service has finished its queue and stopped, root can copy
this directory into the task's `extensions/H3X0Readout`, expose it under the
task's `custom_nodes/H3X0Readout` using the same approach as H3TemporalRouter,
and add `H3X0Readout` to the service's `--whitelist-custom-nodes` list. Do not
edit the shared Comfy core or frozen router extension.

For a new full-resolution graph, add an unused node ID (example 60):

```json
"60": {
  "class_type": "H3X0Readout",
  "inputs": {
    "model": ["50", 0],
    "run_id": "s05_full_seed1_native_x0_unique",
    "output_dir": "/data5/researcher/h3_runs/timing_autoresearch_20261016/audit/x0",
    "width": 1312,
    "height": 736,
    "length": 141
  }
}
```

Change only node `7` (`BasicGuider`) `inputs.model` from `["50",0]` to
`["60",0]`. Keep its conditioning unchanged. The recorder receives a clone of
the already patched model, so prior model wrappers and routing are retained.
Use new output/run audit names while retaining seed, conditioning, graph
geometry and sigma values. If using the 1024 good-case arm, set width/height to
1024/576; the node never resizes anything. It rejects a geometry mismatch.

The recorder accepts only the audited `sample_euler`, zero churn, 20-step path
with strictly decreasing sigmas ending at zero, float32 packed x0, batch one,
and exactly the expected H3 video/audio target streams. It rejects duplicate,
skipped or reordered callbacks and duplicate output directories. A run ID
cannot silently overwrite earlier science data. Use a new ID for a retry.

## Files and normalization

Each reserved `output_dir/run_id/` contains:

- `x0_step005.pt`, `x0_step010.pt`, `x0_step015.pt`, `x0_step019.pt`.
- `sampler_final.pt`, the actual final return from KSAMPLER before CFGGuider's
  subsequent normalization, saved after the same copy-only normalization.
- `manifest.json`, complete only after all 20 callbacks and all five saves.

Every `.pt` is a plain `dict(video=tensor, audio=tensor, metadata=dict)` and can
be read with `torch.load(..., map_location="cpu", weights_only=True)`. No custom
NestedTensor object is pickled. Files and manifests are atomically replaced
inside a newly and exclusively created run directory.

Video uses H3 latent scale 1.0 and is unchanged by `process_latent_out`. Audio
is divided by `model.audio_scale()` (4 for the current 12/3 flow shifts).
Snapshots retain VAE-normalized latent coordinates: **do not manually undo
the VAE mean/std**, because the native VAE decode already does that.

Metadata includes actual shapes/dtypes, per-stream raw-byte SHA256, initial
noise signature, seed, actual video sigma grid, each snapshot's video/audio
sigma, normalization stage, capture duration, callback count and endpoint
differences. Endpoint differences report max/mean/RMS absolute scale; exact
equality between x0 step19 and final Euler result is not required because the
last arithmetic update can round differently. The CPU integration test
already observes an audio maximum difference of approximately 3.73e-9.

At 1312×736/141 frames, each float32 dual-stream snapshot is about 14.56 MiB;
four x0 observations plus the actual sampler endpoint total about 72.81 MiB.
No GPU tensors are retained across callbacks. Synchronous CPU copying and
writing add wall time, so this run is not an uninstrumented speed benchmark.

## Offline decoder

`scripts/decode_x0.py` decodes **one** snapshot per invocation with the existing
FP16 H3 video VAE and core. It does not load DiT or the audio VAE. Run only after
the task's DiT has been released and the chosen GPU is idle. The script checks
an exact GPU UUID twice before Comfy/CUDA initialization, rejects any compute
process, memory above 64 MiB or nonzero utilization, and scopes visibility to
that one card. This is a last-moment admission check, not a cluster scheduler
lock; root must maintain its existing task lease.

CPU-only integrity validation:

```sh
python scripts/decode_x0.py /absolute/run/x0_step010.pt --validate-only
```

Real decode invocation (choose a new output path and the actual idle GPU UUID):

```sh
PYTHONPATH=/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps \
/home/researcher/miniconda3/envs/comfyui/bin/python scripts/decode_x0.py \
  /absolute/run/x0_step010.pt \
  --core /data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI \
  --runtime-deps /data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps \
  --vae /data5/researcher/ComfyUI/models/vae/minimax_h3_video_vae_fp16.safetensors \
  --gpu-uuid GPU-REPLACE-WITH-EXACT-IDLE-UUID \
  --output /absolute/derived/x0_step010.mp4
```

Optionally supply `--expected-vae-sha256` from the verified model manifest.
The script hashes the actual checkpoint and snapshot in all cases. It reuses
the existing `scripts/compatibility_bootstrap.py` schema/PyAV adapters without
launching the service or installing dependencies. Its model-management flags
match the relevant frozen service flags. Keep the staged extension directory
available at the script's task-root-relative `extensions_staged/H3X0Readout`
path, even after an installed copy is made.

Decode the full 42-latent sequence to 141 frames, then inspect/score the desired
physical frames. Do not independently decode a cropped latent time window.
The `.mp4` uses fixed 24 fps, original geometry, no interpolation or crop;
encoding is H264 CRF16 yuv420p. RGB conversion matches the native 8-bit
`VideoFromComponents.save_to` expression exactly:
`(frame * 255).clamp(0, 255).byte()` (truncation, without rounding).
Sidecar JSON records pre-encode RGB24 per-frame and whole-sequence hashes,
the raw floating-point VAE output hash streamed frame by frame, its
shape/dtype/range, and the encoder conversion. MP4 bytes must not be compared
across different encoder libraries as a normalization test, even at the same
CRF. The passive full-model paired check remains **Comfy final output with
capture versus the prior Comfy final output without capture** using the same
encoding path. The `.pt` files remain primary numerical evidence.

The decoder unloads VAE models, clears its own cache and exits. Root should
verify process exit/VRAM release before the next run. An untested GPU decoder
failure must remain recorded, not be treated as a missing-action result.

## Validation and limits

Local CPU unit tests: `python -m unittest discover -s tests -p test_x0_readout.py -v`.
They cover packed/nested inputs, CPU normalization, callback identity/count and
return forwarding, inputs and RNG unchanged, shape/dtype/finite/order errors,
failure manifests, no overwrite, snapshot hash validation, GPU admission with
mocked queries, and a real tiny FFmpeg encode/fps/geometry check.

The separate `tests/x0_core_cpu_smoke.py` was run against the current .9 Comfy
core with `CUDA_VISIBLE_DEVICES=''` and `--cpu`. It uses the real KSAMPLER,
Euler function, WrapperExecutor, NestedTensor, unpacking and H3 normalization
methods, with a deterministic toy denoiser and **no model weights**. Packed
and nested callback variants preserve the final result bit for bit and make
20 original callbacks. CUDA remains uninitialized. Evidence is in
`analysis/x0_core_cpu_smoke.json` and `.log`.

Still required after deployment: a real H3 passive-capture run, comparison
against its no-capture baseline, native VAE decode success and timing-readout
validation. CPU tests do not establish full-model/GPU equivalence or that
intermediate x0 reliably reveals motion timing. Low-confidence/occluded poses
must remain unknown rather than being labeled missing.
