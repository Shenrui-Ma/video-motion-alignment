R64 CPU package ready

Directory: /Users/researcher/DevProjects/h3-timing-ivebench-heldout-r64-20261018
Remote target: /data3/researcher/h3_runs/timing_ivebench_heldout_r64_20261018
Host H3_SERVER_B (.41), GPU2 UUID GPU-REDACTED, port8534; normal memory, reserve-vram8. Live port/GPU/resource admission remains root-owned. No GPU/deployment performed.

Four frozen official P0 tasks, eight sequential jobs:
- short_0092: Remove the plants in the room. T73, effective58, video latent22, audio latent122. Route bins[0,18), position coverage frames0..59; bins18..21 are pure padding.
- short_0114: Replace the basketball with a neon-lit ball. T107, effective105, video latent32, audio latent178. Route bins[0,32), coverage0..106. The last bin overlaps valid frames and two padding frames; there is no pure-padding bin.
- short_0126: Add a cat on the bed next to the man. T124, effective109, video latent37, audio latent207. Route bins[0,33), coverage0..110; bins33..36 are pure padding.
- short_0392: Remove the ornate fireplace. T73, effective57, video latent22, audio latent122. Route bins[0,18), coverage0..59; bins18..21 are pure padding.

Each pair has the same prompt/input/seed2026101701/canvas1312x736/manual20Euler schedule/CFG1/INT8 model/Qwen/VAEs. Both arms use exactly the same valid physical-frame mask, steps[6,15), blocks[0,50), alpha1, radius0, offset0. The only scientific pair difference is router mode native versus mass_preserve. R63 numerical router/layout/readout cores, INT8 row chunker and compatibility/backend code are byte-identical. Per-run wrappers change bindings and dynamic geometry only. No online observer. Sparse source event checkpoints are evaluation-only.

Original source/input provenance and official metadata were frozen before any H3 output. This group edits props/background while preserving visible human movement. Report separately from the previous five person/clothing editing tasks. Denominator stays four including failures, unchanged outputs and unobservable cases. Original0392 has audio, but all prepared reference videos are silent and the graph has no reference-audio connection. Generated audio stream remains present as in R63.

CPU evidence:
- audit/CPU_TESTS_FINAL.txt: 26 tests pass. Includes pinned actual core temporal_shape, inherited frame-bin mapping, same-source input/geometry/prompt restrictions, unchanged numerical router and small dense attention oracle, actual-noise/condition/prefix mutation rejection, pure-pad and reference-shape rejection, exact process binding and first-pair gate tests.
- audit/CPU_PREFLIGHT.json: eight jobs pass; launch_admitted=false.
- audit/ACTUAL_INPUT_STREAM_CHECK.json: copied input SHA, actual ffprobe geometry/frame count/fps and silent reference scope checked for all four.
- audit/INHERITANCE.json: exact current/parent source hashes.
- PREPARATION_MANIFEST.json: local CPU package hash inventory. No actual inference evidence is included or claimed.

Deployment and execution reuse R63's lifecycle:
1. Copy package to the stated new remote root, excluding __pycache__. Confirm existing model/core SHAs and current port/resources. `python3 scripts/execution_gate.py seal` seals producer sources, graph, input bindings and consumer verifier. Root fills configs/admission.json exact own-process registrations and ready_for_launch.
2. Root admits actual first-pair memory trial with `python3 scripts/execution_gate.py approve-first-pair --root-admitted --free-mib <actual-policy-minimum>` (existing >=20480MiB lower bound; this is an engineering trial, not measured full124 capacity).
3. `python3 scripts/launch_remote.py --service-only`; inspect exact PID/start/cmd ready record, register exact peer identity, copy equal ready JSON atomically to cuda_gate_go.json. Wait HTTP readiness, then `python3 scripts/start_controller.py --pid <actual> --start-ticks <actual>`.
4. After the first Native/ON pair, CPU `CUDA_VISIBLE_DEVICES='' <runtime-python> analysis/postrun/verify_pair.py --source short_0092`. It verifies both actual same-host runs, stored AV noise, six clean condition blobs, all21 AV captures, actual dynamic geometry/masks/counts, output video properties, and bitwise equal steps0..5. Review resources and `python3 scripts/execution_gate.py approve-rest --root-admitted` to release remaining fixed queue.
5. Repeat verify_pair for all four sources. Score valid prefix and fixed crop[16,8,1280,720]; source-time mapping is copied exactly from frozen provenance. Assess editing success/content preservation alongside timing/MF.

Capacity caveat for root admission: a completed T73 first pair cannot certify T107/T124 capacity. This CPU package does not claim reserve8 savings or all-shape capacity. Root must examine actual resource margin before the larger Native and ON jobs; numerical parameters must remain fixed within each pair. Final exact-owned cleanup is inherited from R63; foreign users are allowed when memory and own-UID two-GPU admission permit.
