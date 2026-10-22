#!/bin/sh
set -eu
MF_PACKAGE=/Users/researcher/DevProjects/h3-guidance-schedule-eval-r150-20261021/mf_preparation/host9_batches/short_0274
MF_REMOTE=/home/researcher/h3_runs/guidance_schedule_mf_r150_host9_20261021/short_0274
python3 - "$MF_PACKAGE" <<'CHECK'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
s=json.loads((p/'SEAL.json').read_text());r=json.loads((p/'ROOT_REVIEW.json').read_text())
assert r['passed'] and r.get('CPU_upload_authorized',r.get('GPU_execution_authorized',False))
assert r['seal_sha256']==h(p/'SEAL.json')
for rel,digest in s['files'].items():assert h(p/rel)==digest,rel
files=(p/'audit/DEPLOY_FILES.txt').read_text().splitlines()
assert len(files)==len(set(files))
assert all(not Path(x).is_absolute() and '..' not in Path(x).parts and not x.startswith('runtime/') for x in files)
print({'upload_files':len(files)+1,'upload_bytes':sum((p/f).stat().st_size for f in files)+(p/'ROOT_REVIEW.json').stat().st_size})
CHECK
ssh -o ProxyCommand=none H3_SERVER_A "mkdir -p '$MF_REMOTE'"
rsync -a -e 'ssh -o ProxyCommand=none' --files-from="$MF_PACKAGE/audit/DEPLOY_FILES.txt" "$MF_PACKAGE/" "H3_SERVER_A:$MF_REMOTE/"
rsync -a -e 'ssh -o ProxyCommand=none' "$MF_PACKAGE/ROOT_REVIEW.json" "H3_SERVER_A:$MF_REMOTE/ROOT_REVIEW.json"
ssh -o ProxyCommand=none H3_SERVER_A "cd '$MF_REMOTE' && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python audit/materialize_existing.py && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/researcher/miniconda3/envs/comfyui/bin/python audit/verify_inputs.py"
