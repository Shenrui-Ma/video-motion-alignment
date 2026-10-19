C/Y target-path feasibility — frozen CPU tool, 2026-10-16

Scope
This directory is self-contained. It does not import the H3 runtime, create a model, contact a server, render video, train M, change a queue, or start GPU work. CUDA_VISIBLE_DEVICES is cleared before any lazy torch import; torch uses one CPU thread. Existing numpy and torch are the only non-stdlib packages. No packages were installed.

Inputs and authority
The design is R2/literature/next_after_mapping_gate.txt, fingerprinted in protocol.json and copied as FROZEN_DESIGN.txt. The source-only group file and locator were copied byte-for-byte from the R3 mapping protocol before any real target feature read. The tool verifies those hashes and its own exact scientific constants. These23 fixed tiles came from R3 .9 PyAV16 RGB, not R4 .41 actual RGB. They are deliberately reused without recomputation or target-driven selection. The pinned source_runtime_evidence.json and source_runtime_report.txt establish the same original MP4 and all141 native YUV frames across R2/R3, but different decoded/prepared RGB and VAE latents. R4 decoded RGB, prepared RGB and clean reference latent must each match the archived R2 .41 fingerprints exactly; an arbitrary mismatch is refused. The input audit records both selection and current-runtime fingerprints and their differences. It does not reread the1.63GB RGB tensor: the prior source-only audit remains the provenance of these groups. This policy was fixed before any real target read; it is not a claim that R3's high-activity ranking is unchanged after the decoder conversion.

All actual captures must be from ONE native run on ONE machine/backend. Candidate C is the same-forward hypothetical full actuator output at block25, not a correct-action label. Never substitute R or mix .9 Y with .41 C. Inputs must have shape target[1,4,42,23,41,128], candidate[1,4,6,23,41,128], BF16, heads0/14/28/42, candidate bins14..19; mass is FP32. Router capture records provide whole-file SHA and byte count; tensor contents are hashed and checked again after CPU weights_only/mmap loading. Actual layout/call/sigma and metadata must agree. The completed20x50 native-call evidence is required; a stale router status='sampling' alone is not a rejection when the actual counts are complete.

The CLI validates/fingerprints source grouping and run JSONs and writes frozen_input_audit.json BEFORE opening any .pt. Files are read only; results require a new, nonexisting directory. Failure leaves evidence rather than overwriting another attempt. Output provenance keeps native capture passivity explicitly uncertified: root must independently confirm that passive captures did not alter the output, and that the candidate producer matches formal full numerics.

Frozen scientific details
Window10..25, event14..19, endpoints fixed, radius4bins, adjacent increments0/1/2. The actual nonuniform position-bin frame centres are used for reported advance; +4bins gives13/14.5/14.5/13/13/13frames across the event. A repeated/skipped state is reported, never called inherently smooth.

Source high23 tiles are sorted(y,x). Even-indexed12 tiles and heads0/28 fit the path; odd-indexed11 tiles and heads14/42 are held out. All9 positions per tile participate. Each head cost is divided by target temporal variance on fit spatial positions. The DP ties prefer minimum total distance from identity, then lexicographic path. No held-out candidate values influence the path.

Call6 is primary; calls10/14 cannot rescue it. Each held-out head must improve its Epath+B against E0. Pooled1-sum(Epath+B)/sum(E0)>=25%, median event advance>=4physical frames. B is the full non-event buffer cost. The free per-query NN residual is an optimistic lower bound; if its pooled ratio>0.75, even an unconstrained path cannot meet the25% target. Fixed+4bin readout is reported as a descriptive baseline, not a feasible endpoint-preserving path.

Negative controls use the same fitting/scoring rules:
1. time-constant event correction b=mean_t(C-Y), Cnull=Y+b;
2. reverse the event candidate order.
If either also passes the main gate, reject. An indeterminate negative control makes the overall decision unknown. An exactly zero-correction negative control is a safe no-op only; generic unknowns are not counted as negative-control success.

Numerical policies frozen before target reads
- No dropping any head, spatial point or nonfinite capture. Valid scoring support is100%, conservatively satisfying the earlier80% floor. Selected-array tests report actual finite-row fraction but refuse any incomplete set; production capture hash/finite errors are invalid inputs.
- near-zero proposal: E0 <=64*float64_eps*native_event_energy (or exactzero). near-constant path: variance <=64*float64_eps*mean_square_native. These give unknown; they are numerical guards, not motion-confidence criteria.
- DP cost ties:64*float64_eps*max(1,abs(cost_a),abs(cost_b)). This is numerical determinism, not a parameter selected from videos.
- Whole tensors remain BF16 on disk; only selected positions are converted to FP64. No claim that saved information becomes higher precision.

Interpretation
advance_to_generation_test means only that the limited same-forward proposal is representable on the native target path and the frozen artificial controls did not pass. It proves neither correct actions nor quality, generalization, an online clock, or novelty. The target output combines modalities; retiming its full O would also retime text/audio/self contributions, while the outer residual stays at the original time. That compatibility requires a later causal test.

Known prior work
The design document links the exact TokenFlow argmax/gather code, FRESCO and FLATTEN target-feature propagation, FlowMotion difference guidance, and SPF/ReTime's temporal RoPE implementation. These are required comparisons, not automatic reasons to abandon any combination. Do not call DP, target tokens, training-free operation or feature propagation independently new.

Commands — no GPU
Local tests use the existing interpreter:
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python -m unittest discover -s /Users/researcher/DevProjects/h3-timing-target-path-r4-20261016/analysis/target_path_feasibility -p 'test_target_path.py' -v

After root installs this frozen directory and all three genuine captures are complete, from remote R4 root /data3/researcher/h3_runs/timing_target_path_r4_20261016:
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python analysis/target_path_feasibility/evaluate_target_path.py --router audit/router/r4_s05_native_path_probe.json --condition audit/r4_s05_native_path_probe_conditioning.json --noise audit/r4_s05_native_path_probe_noise.json --capture-dir audit/target_path_features/r4_s05_native_path_probe --output analysis/target_path_feasibility/results_native_attempt1

Check actual audit filenames first. The tool accepts paths, not a server address, and refuses a different run_id or mismatched source. Do not overwrite a failed attempt; preserve its EXECUTION_ERROR.json and use a new output directory after the specific input issue is resolved.

Outputs
frozen_input_audit.json; step006.json, step010.json, step014.json; RESULTS.json. Per-call files include path, physical advances, repeats/skips, fit objective, held-out E0/Epath/boundary/free-NN/fixed+4 costs, negative controls, hashes and claim limits. RESULTS.json carries only call6's status and software versions. There is no automatic deployment or queue action.

Synthetic verification
Tests use temporary synthetic tensors only, including one real-shape BF16 three-checkpoint save/load/hash pipeline. They cover zero/known paths, crossing and reversed order, near-zero denominators, constant paths, held-out non-leakage, boundary costs, a static-offset false positive rejected by its negative control, incomplete support, metadata/content tampering, exact axis-value preservation, cross-runtime source identity/geometry checks and exclusive outputs. They are implementation evidence, not H3 experiment results. No real target capture has been read during preparation.
