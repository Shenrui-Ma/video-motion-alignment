# R141b official MF: two new targets, one cached source

CPU preparation only. Nothing has been uploaded or launched. Native is bound now; finalization requires the actual paired consumer input, producer COMPLETE and exact-release receipt. The ordinary score is new because this is a new prompt/output; R113/R138 ordinary scores are not reused.

- Domain: source `short_0252`, physical frames 0–97, 24fps, crop `(16,8,1280,720)` from 1312×736 /107-frame H3 outputs. Padding 98–106 excluded.
- Official code, checkpoint identity, grid10 tracker and all ten execution scripts reuse the completed R138 package unchanged.
- Existing source score video, 98 decoded frame hashes, PTS, track/report hashes and checkpoint/protocol all verified. No source tracker required.
- Planned new trackers: `native`, then `forced`, serial, on one .41 GPU with at least40GiB free. Expected request: one research GPU; at most two simultaneous research GPUs allowed by the inherited admission policy.
- Protected service: PID1646285 /start20299235 /UID1004 /port8189 /GPU5 UUID `GPU-REDACTED`. Exact command hash is in `configs/EXISTING_SERVICES.json`; no signals are sent to it. The selected score GPU must differ.
- Entry memory policy unchanged: adjusted cgroup high/max≥12GiB, raw max≥8GiB, clean unmapped cache reserve6GiB, PSI≤1, host available≥32GiB. Resource use by8189 still counts. Fresh checks, peer identities and root authorization are required immediately before launch.
- R140 is not added to this batch.

## Local finalization after pair collection

Fill the three actual receipt/identity variables and the root-selected GPU UUID. The inventory ID is required rather than guessed. All paths are local until deployment.

```sh
R141B_PACKAGE=/Users/researcher/DevProjects/h3-oxygen-generic-retention-mf-r141b-20261020
PYTHONDONTWRITEBYTECODE=1 /Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python \
  "$R141B_PACKAGE/audit/prepare.py" \
  --paired-input /Users/researcher/DevProjects/h3-oxygen-generic-retention-metrics-r141b-host9-20261020/prepared/short_0252/paired/MF_INPUTS.json \
  --release "$R141B_RELEASE" --complete "$R141B_COMPLETE" \
  --gpu "$R141B_GPU_UUID" --inventory-id "$R141B_INVENTORY_ID"
```

This creates the final `SEAL.json` only after validating both actual videos, Native identity continuity, paired runtime gate and exact producer owner release. Root then reviews the final seal and writes `ROOT_REVIEW.json` with `passed=true`, `GPU_execution_authorized=true`, matching `seal_sha256` and selected `gpu`. The preparation seal is not a GPU authorization.

## Upload only new files; attach existing server cache/runtime

After finalization, use `audit/DEPLOY_FILES_AFTER_FINALIZE.txt` for a single upload to:
`H3_SERVER_B:/data4/researcher/h3_runs/ive_oxygen_generic_retention_mf_r141b_20261020/`.
Upload the new root review separately. This list excludes the runtime, existing source videos and source tracks. No model download/install is needed.

The exact pre-existing server links are in `audit/REMOTE_REUSE_PLAN.json`.
On .41, CPU-only setup/validation:

```sh
cd /data4/researcher/h3_runs/ive_oxygen_generic_retention_mf_r141b_20261020
PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/materialize_existing.py
PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/verify_inputs.py
```

The target check hashes the actual existing `runtime/ive/weights/baseline_offline.pth`. It must match `da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df`; the local checkpoint is intentionally absent and no local checkpoint check is claimed.

## Shortest fresh admission / launch / release commands

Root runs these only after its actual admission review. `configs/RUNTIME.json` already carries the GPU selected at finalization. If a live research peer must be added, include `--peer-root /data4/researcher/h3_runs/ACTUAL_PEER` in the local finalization command before freezing/review.

```sh
R141B_GPU_UUID=$(/data3/researcher/ComfyUI/.venv/bin/python -c 'import json; print(json.load(open("configs/RUNTIME.json"))["gpu"])')
CUDA_VISIBLE_DEVICES="$R141B_GPU_UUID" PYTHONDONTWRITEBYTECODE=1 \
  /data3/researcher/ComfyUI/.venv/bin/python -c \
  'import sys,json,os; sys.path.insert(0,"scripts"); from common import resource_check; print(json.dumps(resource_check(os.environ["CUDA_VISIBLE_DEVICES"])))' \
  > audit/FRESH_ADMISSION.json

CUDA_VISIBLE_DEVICES="$R141B_GPU_UUID" PYTHONDONTWRITEBYTECODE=1 \
  nohup /data3/researcher/ComfyUI/.venv/bin/python scripts/run_batch.py \
  --attempt actual_context_mf_attempt1 --gpu "$R141B_GPU_UUID" \
  --review ROOT_REVIEW.json --maximum-new-trackers 2 \
  > audit/launcher.log 2>&1 < /dev/null &
```

The runner rechecks admission itself before each tracker and at the exact ready/go boundary. It records wrapper/tracker identities, registers/removes any admitted research peer, monitors cgroup/OOM counters, scores on CPU, and releases each tracker exactly.

After the wrapper has exited:

```sh
PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python \
  audit/final_release.py --attempt actual_context_mf_attempt1
```

Then use the reused local `audit/collect.py` to collect MF receipts/results, and hand only the two verified scores plus `audit/FINAL_RELEASE_VERIFIED.json` to the sole inventory owner. No HTML/report write is part of this package.
