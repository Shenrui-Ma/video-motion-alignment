#!/bin/sh
# CPU deployment only. Run after root verifies the reboot, the final seal and GPU binding.
set -eu
MF_PACKAGE=/Users/researcher/DevProjects/h3-timing-phase-combined-eval-r148-20261020/mf_preparation
MF_REMOTE=/data4/researcher/h3_runs/timing_phase_combined_mf_r148_20261020
python3 - "$MF_PACKAGE" <<'CHECK'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1])
h=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
s=json.loads((p/'SEAL.json').read_text())
r=json.loads((p/'ROOT_REVIEW.json').read_text())
c=json.loads((p/'configs/RUNTIME.json').read_text())
assert s['final_inputs_bound'] is True
assert r['passed'] is True and r['GPU_execution_authorized'] is True
assert r['seal_sha256']==h(p/'SEAL.json') and r['gpu']==c['gpu']
for rel,expected in s['files'].items():assert h(p/rel)==expected,rel
files=(p/'audit/DEPLOY_FILES.txt').read_text().splitlines()
assert len(files)==len(set(files))
reuse=json.loads((p/'audit/REMOTE_REUSE_PLAN.json').read_text())
for rel in files:
 assert not Path(rel).is_absolute() and '..'not in Path(rel).parts
 assert rel not in reuse and not rel.startswith('runtime/')
 assert (p/rel).is_file()
print(json.dumps({'files':len(files),'bytes':sum((p/r).stat().st_size for r in files),'seal':h(p/'SEAL.json')}))
CHECK
ssh H3_SERVER_B "mkdir -p '$MF_REMOTE'"
rsync -a --files-from="$MF_PACKAGE/audit/DEPLOY_FILES.txt" "$MF_PACKAGE/" "H3_SERVER_B:$MF_REMOTE/"
rsync -a "$MF_PACKAGE/ROOT_REVIEW.json" "H3_SERVER_B:$MF_REMOTE/ROOT_REVIEW.json"
ssh H3_SERVER_B "cd '$MF_REMOTE' && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/materialize_existing.py && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/verify_inputs.py"
