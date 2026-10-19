# H3 spatial routing R3 — local prepared bundle, not deployed

This is an independent .9 runtime. No upload, remote write, service, GPU action,
or comparison-media generation was performed while preparing this directory.
R2 on .41 and the earlier round1 files were not modified. Root owns deployment.

## Fixed experiment

Remote root: `/data5/researcher/h3_runs/timing_spatial_r3_20261016`
Host SSH alias: `H3_SERVER_A` (.9)
GPU2 UUID: `GPU-REDACTED`
HTTP: `127.0.0.1:8464`
Python: `/home/researcher/miniconda3/envs/comfyui/bin/python`
Core/deps/KJ: `/data5/researcher/h3_runs/short_event_pilot_20261013/`
Read-only models: `/data5/researcher/ComfyUI/models`

The sealed queue contains a two-call spatial benchmark followed by four formal
20-call arms: native, full mass-preserving same-frame routing, dynamic residual,
and spatial-marginal preserving same-frame routing. Formal graphs differ only
in node50 class/mode and administrative run/output identifiers. All preserve
source05, Sam portrait, prompt, seed2026101311, 1312x736, 141 frames at24fps,
manual sigmas/Euler, model weights, semantic2fps/phase0, original reference,
source window50–65, alpha1, radius0/offset0, blocks[0,50), calls[6,15).
Those calls are zero-based6..14 / one-based7..15, nine interventions out of20.
The target window covers H3 bins14..19 (positional coverage47–67).

The benchmark has sigmas `1,0.995633187773,0`, interval[0,2), and bypasses
H3X0Readout entirely. It is a speed/admission test, not the first two formal
Euler updates: its second update makes a terminal jump to zero. It is never a
quality sample. This avoids the verified recorder's intentional Euler20 guard.

Native/full/dynamic use the R2 TemporalRouter computational implementation;
spatial uses the frozen staged SpatialMarginalRouter. Independent actual .9
native/full/dynamic outputs are collected to avoid substituting RTX output
for A100 output. A cheaper native+spatial-only queue could be chosen by root
before deployment, with a newly reviewed sealed queue/manifest, but it would
not by itself supply same-host DC/full component comparisons. The default is
all four formal arms.

## Passive observation, identical in all four formal arms

Only the R3 recorder's CAPTURE_STEPS changed to zero-based5,6,7,8,9,10,15,19.
Eight x0 estimates plus sampler_final are saved as CPU tensors with existing
normalization/hash/atomic-write checks. No online VAE decode or pose inference
occurs. NFE, sigmas, noise, callback arguments/returns, RNG and sampler result
are unchanged in CPU contracts. Each video+audio snapshot contains about
15,268,864 raw bytes; nine files are about137,419,776 bytes per run before
serialization overhead. More copying/hashing can increase wall time.

Both router packages have byte-identical copies of the independently provided
`component_probe.py`. At block25 and zero-based calls6,10,14, BEFORE routing,
they read actual Q/K/V and attach a sparse diagnostic to the existing audit.
It selects up to8 heads and8 central spatial queries per selected bin, evaluates
FP32 analytic native/full/dynamic/static/spatial branches, and records actual
video sampler sigma. It does not report audio sigma as if it were the same.
It does not return a model value or modify Q/K/V/RNG/global TF32. Existing
forward audit flush saves the records; no extra per-probe file write is added.
Errors propagate. The benchmark does not reach these checkpoints.

This is an FP32 analytic estimate at sampled actual QKV, NOT the exact BF16
Flash-kernel correction, NOT a full-head/full-spatial statistic, and NOT motion
ground truth. The stable version computes same-frame conditional probabilities
directly from that frame's logits to avoid underflow followed by0/0. Native
replay must still compare the five previously recorded common snapshots
(step005/010/015/019 and final) and decoded RGB against the actual old .9 native
control. The newly added006..009 snapshots have no old direct counterpart.

## Lifecycle and root-owned gates

The reused service pins the exact UUID, refuses any compute process on that
GPU, and rejects unpermitted same-user compute processes on other GPUs. Other
users on other GPUs remain allowed. Admission has no wildcard or preapproved
PIDs. A process-identity registry binds uid/PID/start_ticks/cmdline/GPU/port;
cleanup only terminates that exact service. The queue is sequential, sealed,
submit-once, aborts unknown/error/uncertain status, and has timeouts plus an
independent watchdog. No model install or shared-core patch is performed.
EventAudit's path guard was tightened to the exact canonical R3 root; actual
configuration audit paths all belong to it. The current package is not a
sandbox for executing untrusted arbitrary Comfy graphs.

Before running, root must verify: (1) prior owned .9 jobs/processes have ended
with their exact cleanup records, (2) GPU2 UUID is still the expected device,
compute list empty, memory near idle and enough host RAM/free disk, (3)8464 is
free, (4) no unintended same-user inference exists, (5) this remote root is new
or every previous attempt has been explicitly archived, (6) final package
manifest and passive-probe GPU validation are accepted. Do not allow another
owned GPU process merely to bypass admission. Existing .41 R2 is a different
host and is not touched.

The launcher validates model size/mtime against prior known hashes, compares
all9 pinned core-file SHA256 values, records actual code provenance, creates
only task-local symlinks/input copies, and checks SpatialMarginalRouter and
its mode plus the dynamic-residual mode are registered before queue startup.
Recorded prior model hashes are not represented as fresh full checkpoint
rehashing in this launch.

## Commands for root AFTER review/admission (not executed here)

Read-only host/GPU check:

```sh
ssh -o BatchMode=yes H3_SERVER_A 'nvidia-smi --query-gpu=index,uuid,memory.used,memory.free,utilization.gpu --format=csv,noheader; nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader'
```

Create only a new task directory, then upload the reviewed files (stop if it
already exists; do not overwrite an unknown previous attempt):

```sh
ssh -o BatchMode=yes H3_SERVER_A 'test ! -e /data5/researcher/h3_runs/timing_spatial_r3_20261016 && mkdir /data5/researcher/h3_runs/timing_spatial_r3_20261016'
rsync -a --exclude=__pycache__ --exclude='*.pyc' /Users/researcher/DevProjects/h3-timing-spatial-r3-20261016/ H3_SERVER_A:/data5/researcher/h3_runs/timing_spatial_r3_20261016/
```

On .9, CPU-only imports/contracts and the real-Comfy wrapper check:

```sh
cd /data5/researcher/h3_runs/timing_spatial_r3_20261016
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python tests/x0_core_cpu_smoke.py --comfy-root /data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI --recorder-core extensions/H3X0Readout/core.py --compat-bootstrap scripts/compatibility_bootstrap.py
```

Root may run this package's tensor-only kernel smoke after idle-GPU admission
if needed; previous successful staged-core evidence does not verify a changed
loaded hook. Never run it beside the R3 service on GPU2:

```sh
CUDA_VISIBLE_DEVICES=GPU-REDACTED OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python scripts/gpu_spatial_marginal_smoke.py --actual-shape --output audit/spatial_gpu_smoke.json
```

After that process has exited and GPU2 is idle again:

```sh
python3 -u scripts/launch_remote.py
```

Read-only progress/owned-instance cleanup (only if needed, not broad process
matching): `python3 scripts/service.py stats` / `python3 scripts/service.py stop`.
Do not auto-resubmit if the job result is uncertain. At end inspect saved
success histories, exact submitted graphs, shared condition/noise hashes,
expected1000 block calls/450 active calls,3 sparse probes,8 x0 captures+final,
then cleanup.json and GPU compute absence. No result or novelty claim follows
from package preparation alone.

## Intentional native-only passive feature archive

Only the native arm additionally saves block25 attention outputs at zero-based
steps6/10/14, after route_attention and before W_O. Selected heads[0,14,28,42]
cover every42x23x41 bin/grid position in both reference and target segments.
Stored axes are [batch,selected_head,time,row,col,head_channel], preserving
BF16 with CPU copies. Two tensors total81,113,088 raw bytes per checkpoint;
three checkpoints total243,339,264 bytes. Exclusive atomic publication refuses
name reuse; both file/tensor SHA and actual layout/sigma/head/stage metadata
are retained in the native router audit. Contextual reference features are NOT
ground-truth action descriptors. No additional attention/model invocation or
QKV/output mutation occurs. CPU/disk overhead is intentionally native-only and
must be excluded from claims of equal wall-clock runtime. Sampler/weights/NFE
remain equal; verify actual native passive replay before claiming numerical
equivalence. This observation can avoid rerunning a full native trajectory
for later offline correspondence diagnostics.

The previous frozen manifest is preserved verbatim at
`audit/bundle_before_native_feature_capture.json`. The service already sets
the correct PYTHONPATH; the real-Comfy CPU smoke command above now also sets
it explicitly so it does not resolve an incompatible base-environment kitchen.
