R55 production preparation and root launch interface

1. Root selects an existing policy using an independent R53 JSON result:
   python scripts/choose_policy.py --choice delay_only_R50|signed_R53 \
     --evidence <local R53 result JSON> --reason '<scientific reason>' --root-decision
   This records exact policy bytes and preserves independent evidence. Current state
   remains ROOT_DECISION_PENDING until root executes the command.

2. After all five R54 Native cases and source-pose90 are complete:
   PY_WITH_NUMPY_TORCH scripts/bind_actual_parents.py \
     --archive <R54 analysis/postrun/captured/batch> \
     --source-poses <R54 analysis/source_pose90>
   Requires RUN_GATE, RUNTIME_GATE, FILE_INVENTORY, exact R54 seal; each complete
   source-pose record and local outputs/*.pose.json. Every source is finite-validated.
   Original R54 inputs are copied byte-exact. This binds 28 actual tensor entities
   per case:6 condition files,1 cached AV noise,21 Native AV endpoints.

3. Validate metadata and seal:
   python scripts/preflight.py --metadata-only
   python scripts/build_manifest.py --manifest deploy_manifest.json \
     --bundle audit/runtime_bundle_v1.tar.gz
   Deploy the bundle at /data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017.
   Copy its frozen inputs separately or copy exact matching R54 inputs on host41.
   No inference is permitted while source/parent/policy binding is incomplete.

4. Root GPU gates, both zero DiT:
   GPU1 (dee80...): scripts/gpu_dynamic_union_smoke.py --root-admitted \
     --output audit/gpu_dynamic_union_gate.json
   GPU2 (7328...): scripts/known_endpoint_90_gate.py --root-admitted \
     --output audit/known_endpoint_90_gate.json
   The latter records decoder_ready.json under audit/observations/known_endpoint_90;
   root writes decoder_go.json {root_approved:true,identity:<exact ready identity>,
   gpu_uuid:<exact ready UUID>} before CUDA. Observe full90 decoding and capacity.
   Root binds both gate SHAs and current protocol in audit/resource_admission.json
   using schema r55-root-two-GPU-resource-admission-v1 (see prelaunch_gates.py).
   Capacity is checked separately for main GPU and isolated decoder GPU.

5. Root sets admission.ready_for_launch=true and root_live_review_required=false;
   verifies current exact peer records/empty planned cards; runs launch_remote.py
   --service-only, authorizes exact cuda_gate_ready -> cuda_gate_go, waits HTTP
   readiness, then runs start_controller.py. Five cases run sequentially on GPU1;
   temporary VAE decoder uses GPU2 and releases before CPU pose. Runtime GPU caps
   include at most2 owned GPUs. Port8516. Pose lock matches R54 source/postrun CPU.

6. Producer postrun gate:
   RUNTIME_PYTHON scripts/verify_completed.py --allow-resident --output <new JSON>
   Archive first, then root closes queue.finalize or service.stop for exact owned
   process cleanup. Source score videos should reuse R54 archived source_score.mp4
   bytes; edited score crops use the same16,8,1280,720 and valid temporal prefix.

Current synthetic CPU validation tests transaction mechanics and valid-domain rules.
Actual GPU kernel, full90 decoder resource, parent pairing and video-quality outcomes
are separate recorded gates. Full90 K/V remains active; complete-bin interventions
can affect padding positions, explicitly listed in each decision bin_coverage.
