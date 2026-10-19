R55 IVEBench paired Auto preparation

Five original R54 tasks. Model:90@24,1312x736; reference:one silent video,zero images.
Effective source prefixes:87,86,74,78,89 frames. Feature scale, window candidates, lag
matching, null comparisons and common support use only each valid prefix. Full90
K/V remains in the H3 computation. Intervention operates on complete latent bins;
every decision retains bin_coverage with any nominal padding spillover.

Current component policy is byte-exact delay-only R50. The independently tested R53
signed policy is retained in configs/policy_candidates. Root selects the production
policy using R53 before sealing R55. IVEBench outputs do not determine thresholds.

GPU plan:host41 GPU1 main model (dee80...),GPU2 isolated VAE decoder (7328...). One
DiT process and at most two owned GPUs. Each decode validates the exact current main
process identity, idle decoder device and remaining owned GPU slot; CPU pose runs
after decoder exit with a shared lock. Live GPU/resource checks belong to root.
CPU lock:/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock

This directory is a CPU component preparation, with production launch blocked by
configs/PARENT_CLOSURE.json.ready=false and the pending policy decision. It has no
successful R54 inference evidence yet. Production binding, verification, deployment
and launch entry points are prepared; README_PRODUCTION.txt lists their order.
Actual five-parent binding, 27-bin layout kernel execution, full90 decoder resource
measurement and production seal follow R54 Native archives and source-pose90.
analysis belongs to root/consumer.

Tests use synthetic tensors/pose and the actual installed Comfy sampler interfaces.
Their PASS certifies geometry, deterministic transaction mechanics, padding exclusion
and admission rules. Video quality remains an inference/benchmark measurement.
