R54 IVEBench: five original-task Native videos

The five sources and original edit_prompt strings are fixed by design/PILOT_5_MANIFEST.json.
Inputs contain one silent reference video per job and no reference portrait. Run order:
short_0210, short_0230, short_0263, short_0352, short_0370; seed 2026101701 throughout.

Model canvas: 90 frames at24FPS, 1312x736. Actual valid prefixes:87,86,74,78,89.
The prepared source occupies1280x720 at(x16,y8). Evaluation removes this fixed spatial
padding and excludes the temporal tail. Original frame correspondence is frozen in
inputs/*_provenance.json. These five pilot tasks do not constitute the full benchmark.

Inference: existing Ref2VA INT8 weights, Euler20 video shift12/audio shift3, CFG1,
Native SDPA attention, no intervention, no LoRA. Preserve20 intermediate AV snapshots,
final AV, original noise, conditioning tensors, Comfy history and exact elapsed time.

Host41 profile is frozen in configs/runtime.json: GPU1 UUID GPU-REDACTED,
port8515. Shared core/models/dependencies remain external and checked by provenance.
Root performs final live resource admission and launch. No GPU inference was started
while building this bundle. At most2 owned GPUs are allowed on this host.

Runtime entry points on the host:
  python3 scripts/preflight.py
  python3 scripts/launch_remote.py --service-only
The latter requires configs/admission.json ready_for_launch=true, exact peer process
identities, empty selected GPU, and the root-controlled pre-CUDA go record. Root copies
processes/cuda_gate_ready.json atomically to processes/cuda_gate_go.json for this exact
generation, waits for HTTP readiness, then starts scripts/start_controller.py. Queue
runs all five jobs in sequence and retains the service for the paired Auto experiment.
Set queue.finalize=true for the normal owner-checked close/release path after archiving.

Post-run producer validation:
  RUNTIME_PYTHON scripts/verify_batch.py --root RUN_ROOT --output audit/RUN_GATE.json
Use scripts/service.py stats/stop only with the recorded exact owned generation.
