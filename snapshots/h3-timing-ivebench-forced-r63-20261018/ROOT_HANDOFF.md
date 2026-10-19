# R63: first Native / forced-ON pair

Producer is CPU prepared. Root alone starts GPU processes. Five P0 tasks are ordered per-source: 0210 Native→ON, 0230 Native→ON, 0263 Native→ON, 0352 Native→ON, 0370 Native→ON. Both members use the exact original P0 edit prompt, input, seed, 20 Euler steps, INT8/FP4 kernels, and host/memory profile. This is the existing fixed same-time routing control.

ON uses H3TemporalRouter `mass_preserve`, alpha=1, all 27 video time bins/all spatial queries, 50 blocks, zero-based sampling indices 6…14. Formula `O' = O + m_ref (O_same_time − O_ref)` preserves reference-group attention mass. Each run has 20 model predictions and 20 Euler updates. Online observer is absent. Original R54 numerical router and recording kernels are byte identical.

Current .9 profile: GPU index 2, UUID `GPU-REDACTED`, port 8529; `--disable-dynamic-vram --reserve-vram 8`, normal memory mode. Comfy's actual free-memory calculation determines layer offload. Other available profiles: `.9 GPU0/GPU2 × normal/lowvram/novram` and `.41 normal`, in configs/runtime_profiles.json. A profile switch requires a fresh service and same-profile Native/ON. Never compare a new-profile ON against an old-profile Native as the paired claim.

## Deployment

Copy this whole directory to `/data5/researcher/h3_runs/timing_ivebench_forced_r63_20261018`. Input payload is ~84MB. Python commands below run from that remote directory with system python3 until stated otherwise.

1. Inspect actual free GPU memory, UUID/index mapping, host RAM, and all own CUDA jobs. Update `configs/admission.json`: `ready_for_launch=true`, `scope=own_user_video_jobs`, `existing_comfy_port=null`, and exact hashed identities for own pre-existing compute processes (same format used by R57/R55). The union of own devices plus selected GPU must contain at most two cards. Foreign users' jobs are allowed when fresh free-memory/health checks pass.
2. `python3 scripts/preflight.py`
3. `python3 scripts/execution_gate.py seal`
4. `python3 scripts/execution_gate.py approve-first-pair --root-admitted`
5. `python3 scripts/launch_remote.py --service-only`
6. Register the exact new service PID in any peer admission records before releasing its pre-CUDA wait. Copy the exact `processes/cuda_gate_ready.json` atomically to `processes/cuda_gate_go.json`.
7. After HTTP `/object_info/H3TemporalRouter` succeeds, read PID/start_ticks from `processes/service.json`, then `python3 scripts/start_controller.py --pid PID --start-ticks TICKS`.

Default first-pair trial requires ≥20GiB driver free memory, temperature<85°C, valid UUID/index mapping and ≥20GiB host available RAM. This is explicitly a capacity trial; it makes no claim that full-trajectory capacity has already passed. The first complete Native run supplies actual capacity evidence. If either run fails/OOM, the controller performs exact-own-service cleanup and preserves the primary error; inspect `logs/controller_state.json`, `processes/cleanup.json`, and cleanup error records. Any offload fallback should be placed in a fresh attempt root, preserving the failed attempt and repeating Native→ON under that profile.

## First-pair stop and continuation

After the first two jobs finish, controller status becomes `awaiting_first_pair_review`; service remains for up to 1800s. Root runs the independent actual tensor/runtime pair check and inspects outputs. Once `analysis/postrun/short_0210/PAIR_RUNTIME_GATE.json` passes:

`python3 scripts/execution_gate.py approve-rest --root-admitted`

This binds continuation to the exact pair receipt SHA and unchanged runtime profile. Remaining eight jobs then continue automatically. `configs/queue.json finalize=true` asks for final release when all ten complete; otherwise the bounded hold releases after 1800s. Root can stop the exact owned service when finished.

## Outputs / assessment interface

Actual videos resolve from `logs/<run>_history.json -> outputs['14']['images']`; usual path `output/<run>_00001_.mp4`. Job records include observed/submitted wall time; passive captures record all 20 x0 snapshots plus final sampler AV tensors under `audit/x0/<run>/`. Router execution counters under `audit/router/<run>.json` must be 20 forwards, 1000 block calls, and 0 Native / 450 ON routed calls.

A separate CPU pair verifier will emit schema `r63-paired-runtime-gate-v1`, source_id, prompt_version P0, runtime_profile_sha256, checks (actual_clean_conditions_equal, actual_initial_AV_noise_equal, Native_prefix_0_5_equal), and runs native/forced with actual video path/SHA, NFE20, routed_blocks0/450, valid_frames, job_wall_seconds. Consumer must use only the original effective frame count and crop `(16,8,1280,720)`: 0210=87,0230=86,0263=74,0352=78,0370=89. Equality is assessed between freshly generated same-profile arms; historical R54 .41 remains provenance.

## Verification status

Static preflight and all Python compilation passed. CPU numerical/operational tests and independent pair verifier are being completed beside the producer, in tests/ and analysis/postrun/. These locations do not mutate frozen scripts/extensions. No R63 GPU run has been launched by this preparation agent.

Optional two-prediction capacity scripts are retained but unnecessary for the preferred complete first-Native trial; they have not been GPU validated. R59 four-arm candidate remains separately preserved and paused.
