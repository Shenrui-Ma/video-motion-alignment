# R50 158-frame resource analysis

The current co-resident certificate cannot be inherited unchanged. The sampled R49 Native peak is 64,903 MiB (68,055,728,128 bytes), above the previous 63,946,358,784-byte resident estimate. Combining this observed peak with the old routing increment leaves 9,209,643,008 bytes (8.577 GiB) before decoding, below the required 12 GiB. These samples are observations, not a proven upper bound.

## Which allocations overlap

`extensions/H3AutomaticWindowRouter/core.py:328` completes the Native DiT prediction before the observer at lines 356–358. During the observer, model parameters, the sampler state, and the Native prediction remain alive. Attention temporaries have left scope, but PyTorch may retain their reserved memory. After a Full recomputation, its reserved cache may also remain through the next Native and observer. No parent empty-cache or model-offload operation occurs in this path. The exact parent guard checks model residency, tensors, RNG, and conditioning before and after the observer.

Consequently, active attention scratch space and the decoder are sequential; cached reservation can still overlap the decoder. Adding isolated peak allocated bytes to an arbitrary end-of-job footprint is not justified. Replacing the sum with a maximum is also not justified without measured callback residency and allocator retention.

`transport.py:121` requires at least 12,288 MiB free before admitting the decoder. That condition remains intact.

## Existing evidence

`RESOURCE_PHASE_EVIDENCE.json` records read-only R49 resource-log provenance and phase-adjacent samples. The one_leg endpoint 1 timestamp is 0.254 seconds after a 64,903 MiB sample; endpoint 10 also lies within the same high-memory plateau. All five jobs have a substantial drop during final decoding. Their final 41,821 MiB occupancy is unsuitable as a denoising-observer residency estimate.

The old R27 allocator profile measured Native/Full/Native with one actual packed input, without simultaneous oracle outputs and without empty-cache. Native reserved memory was 5,047,844,864 bytes; Full raised it to 13,067,354,112 bytes and subsequent Native retained that reservation. The retained NVML increment was 8,097,103,872 bytes; adding 512 MiB yielded the old routing bound 8,633,974,784 bytes. Its shape was 42 bins × 943 rows, not the current 47 × 864.

The completed R50 correctness gate uses an additional packed-input clone, keeps a Native oracle output, and, in its Full check, holds a second sealed Full result. Its 8,451,098,112-byte incremental allocated peak includes work absent from the production lifecycle. It proves the numerical checks and records that particular check's allocation, but does not measure Native-to-Full persistent reservation.

The full 158-frame decoder gate passed with peak reserved memory 5,981,077,504 bytes. This does not establish the parent occupancy at its invocation.

## Proposed next measurement

`root_allocator_profile_158_proposed.py` reproduces actual current packed layouts, uses the sealed attention operator, and runs Native → Full → Native → Full → Native with no simultaneous oracle result and no empty-cache. By default it selects one_leg, the largest actual sequence (89,636 tokens); `--all-cases` preserves the five-case order. It records allocated/reserved peaks, output-alive and after-output-release NVML values, input integrity and CUDA RNG checks. It loads no model weights and uses zero DiT evaluations. The largest-sequence run measures that case only; it is not a general upper-bound proof.

Root execution example after exact PID admission:

```sh
CUDA_VISIBLE_DEVICES=GPU-REDACTED /home/researcher/miniconda3/envs/comfyui/bin/python /data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017/audit/root_allocator_profile_158_proposed.py --root /data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017 --output /data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017/audit/root_allocator_profile_158.json --root-admitted
```

The script must be run on an empty GPU3; no execution is authorized or performed by this analysis. A small retained increment may make co-residence plausible, but the actual callback's strict free-memory check remains necessary. A large retained increment supports the already-authorized split deployment: main model on GPU3 and isolated decoder on GPU2 after R53 release, using the reviewed R55 transport/admission structure. That engineering revision needs new bindings and seal while preserving the numerical protocol, full 158-frame decoding, precision, and both-GPU cap.

## Read-only provenance

- R27 allocator script SHA256: adb038e24b47eb57ce9d8f9d8bb0f5b8586d03ef19b4ec31fbfe638c76066140
- R27 allocator report SHA256: b3309e4058ae2594f289e9652d18e7a767555a3711e19a5126749dafad028395
- R27 parent residency report SHA256: a9ca7fb5fb8c8501b222fa532e8b972e34bc8dc7e1dd9dae08cfd80ec27a66f4
- R50 actual kernel report SHA256: 60ee5965b8c79e45572a98561e5cfa0b135720be815ede3e6b321bbc0ad4b237
- R50 full decoder report SHA256: a1493b1e2b2f14c13ae04b634ca3a58a2a50f8feeadeaa7c74c458251dd74dde

No sealed producer, live process, numerical method, or resource threshold was modified. The proposed profiler passed local Python compilation; its CUDA path has not been executed by this agent.
