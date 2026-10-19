# Round 2 CPU consumer — prepared, not started

`consumer_r2.py` is an analysis-only coordinator. Producer defaults to .41 (`H3_SERVER_B`, `/data3/researcher/h3_runs/timing_architecture_r2_20261016`); existing .9 Python/DWPose executes one serial CPU worker. Nothing has been uploaded or launched by preparation.

Only exact saved history filenames are accepted. Actual history must be complete success, actual graph must match producer config, and one exact SaveVideo output must exist. MP4 producer-before/local/producer-after SHA must agree. CPU worker verifies old frozen pose/metric/source hashes, source video hash, and geometry from producer config. Benchmark IDs are rejected. Detector/geometry/technical failures stay in the formal inventory and retain original media. The consumer does not decide scientific success or hardware equivalence.

Parent must first confirm producer sampling, .41 anchor job IDs and no other owned pose consumer. Then invoke explicit IDs (append native/full anchor IDs when supplied):

```sh
python3 /Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/consumer_r2.py \
  --run-id r2_s05_dynamic_6to14 --run-id r2_s05_static_6to14 \
  --wait --timeout-minutes 240
```

Without `--wait`, it performs one availability pass and exits; no inferred jobs or prefix globs. Coordinator and worker hold advisory locks; worker also refuses to run if an existing pose_probe is visible under the same account. Poll interval61s. No ComfyUI port, inference queue, package install, or GPU operation exists in this script. Torch/DWPose is only reached by the separate explicitly dispatched CPU worker.

Local outputs stay exclusively under this analysis/pose scope: `raw/`, `pilot/<run>_provenance/`, `pilot/*.pose.json`, frozen timing outputs and `consumer_state.json`. CPU mirror is `.9:/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/`. Original .41 output/runtime remains read-only.

Verification performed at preparation: Python syntax compile; pure-stdlib self-test accepts an exact success and rejects benchmark, incomplete history, path traversal, executed/config graph mismatch and missing SaveVideo output. No remote model, GPU, or DWPose was started. Actual producer read/transfer/CPU smoke remains intentionally unrun until launch authorization from parent.

Hardware gate: .41 native may differ from archived .9 A100 output. Do not interpret dynamic/static using an old full baseline if native replay differs. Require .41 full6..14 and compare only within the same machine/runtime/condition set; archived .9 values are historical context. Even if native replay is exact, verify new operator/runtime integrity before claiming a structural effect.
