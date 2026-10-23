Direction-gated ten-case package

Deploy into host9a root /home/research-user/h3_runs/benchmark_schedule_20261022_host9a.
Copy graphs/* under that root's graphs/. pilot_jobs.json contains the initial two tasks; jobs.json all ten.
The six historical tasks restore original SHA-pinned conditioning tensors. Copy assets.json entries to their destination, then cache_manifests/<task>.json to innovation_cache/<task>/manifest.json.
Install custom_nodes/H3TrustedConditionCache and separately the existing innovation/direction_runtime plugin plus its frozen dependencies. H3StudyReference and H3StudyTiming come from the admitted H3Study runtime.
Historical cache reconstruction mirrors the previous H3CachedReferenceConditioning: validates tensor file hash, tensor value/dtype/shape hashes, target geometry, zero latent, reference layout and exact position IDs. No intermediate VAE decode, pose detector, x0 capture, or per-step tensor dump. Noise uses native RandomNoise with the original seed.
Cache loader SHA checks run at each executed graph invocation. Only trusted, pinned tensor files are accepted; torch.load(weights_only=True).
Deployment follow-up copied 41 inputs/cache assets, 6 manifests and the independent cache node to the authorized host9a directories. No GPU run or process/service modification was performed.
CPU verification: 9 tests passed; 10 graph references/prompt/seed/sigma bindings validated. All six historical caches also passed exact tensor/layout replay against the real remote Comfy runtime with CUDA disabled (CPU_REPLAY_VERIFIED.json). GPU execution remains a separate check.
Timing: H3StudyTiming records actual sampler; historical reference timing includes older audit overhead. Direction instrumentation enabled; all 50 layers, 20 steps, alpha upper limit0.25, min offset0.25, concentration0.15, norm1e-6.
Metadata explicitly sets cohort=innovation. Existing watcher must honor this instead of using only job ID prefix; root agent owns that change.
