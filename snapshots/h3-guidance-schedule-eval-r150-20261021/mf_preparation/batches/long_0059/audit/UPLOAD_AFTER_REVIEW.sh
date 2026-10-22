#!/bin/sh
set -eu
MF_PACKAGE=/Users/researcher/DevProjects/h3-guidance-schedule-eval-r150-20261021/mf_preparation/batches/long_0059
MF_REMOTE=/data4/researcher/h3_runs/guidance_schedule_mf_r150_20261021/long_0059
python3 - "$MF_PACKAGE" <<'CHECK'
import json,hashlib,sys
from pathlib import Path
p=Path(sys.argv[1]);h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
s=json.loads((p/'SEAL.json').read_text());r=json.loads((p/'ROOT_REVIEW.json').read_text())
assert s['final_inputs_bound'] and r['passed'] and r.get('CPU_upload_authorized', r.get('GPU_execution_authorized', False))
assert r['seal_sha256']==h(p/'SEAL.json')
assert r['gpu']==json.loads((p/'configs/RUNTIME.json').read_text())['gpu']
for rel,want in s['files'].items(): assert h(p/rel)==want,rel
files=(p/'audit/DEPLOY_FILES.txt').read_text().splitlines()
assert len(files)==len(set(files))
assert all(not Path(x).is_absolute() and '..' not in Path(x).parts and not x.startswith('runtime/') for x in files)
print({'upload_files':len(files)+1,'upload_bytes':sum((p/f).stat().st_size for f in files)+(p/'ROOT_REVIEW.json').stat().st_size})
CHECK
ssh H3_SERVER_B "mkdir -p '$MF_REMOTE'"
rsync -a --files-from="$MF_PACKAGE/audit/DEPLOY_FILES.txt" "$MF_PACKAGE/" "H3_SERVER_B:$MF_REMOTE/"
rsync -a "$MF_PACKAGE/ROOT_REVIEW.json" "H3_SERVER_B:$MF_REMOTE/ROOT_REVIEW.json"
ssh H3_SERVER_B "cd '$MF_REMOTE' && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/materialize_existing.py && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /data3/researcher/ComfyUI/.venv/bin/python audit/verify_inputs.py"
